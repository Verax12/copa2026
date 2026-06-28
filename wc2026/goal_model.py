"""
Modelo de gols Dixon-Coles (1997).

Modela os gols como duas Poisson acopladas:
    gols_mandante ~ Poisson(lambda),  log(lambda) = ataque_A + defesa_B + mando
    gols_visitante ~ Poisson(mu),      log(mu)     = ataque_B + defesa_A
mais a correção 'rho' de Dixon-Coles para placares baixos (0-0, 1-0, 0-1, 1-1),
que a Poisson pura subestima.

Estimação por máxima verossimilhança com DECAIMENTO TEMPORAL: jogos mais
recentes pesam mais (meia-vida configurável). Assim a força reflete o time de hoje.

Saídas:
  - score_matrix(A, B): matriz de probabilidade de cada placar
  - outcome_probs(A, B): (P_vitória_A, P_empate, P_vitória_B)
  - sample_score(A, B, rng): amostra um placar (usado no Monte Carlo)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import nbinom, poisson

MAX_GOALS = 10  # teto de gols por time ao montar a matriz de placares


@dataclass
class DixonColes:
    teams: list[str]
    attack: np.ndarray
    defence: np.ndarray
    home_adv: float
    rho: float
    _idx: dict[str, int]
    avg_attack: float
    avg_defence: float
    dispersion: float = 1.0  # 1.0 = Poisson; >1 = NegativeBinomial overdispersion

    # ---- parâmetros de um time (com fallback p/ seleção fraca/ausente) ----
    def _a(self, team: str) -> float:
        i = self._idx.get(team)
        return self.attack[i] if i is not None else self.avg_attack

    def _d(self, team: str) -> float:
        i = self._idx.get(team)
        return self.defence[i] if i is not None else self.avg_defence

    def expected_goals(self, home: str, away: str, neutral: bool = True) -> tuple[float, float]:
        adv = 0.0 if neutral else self.home_adv
        lam = np.exp(self._a(home) + self._d(away) + adv)
        mu = np.exp(self._a(away) + self._d(home))
        return float(lam), float(mu)

    def score_matrix(self, home: str, away: str, neutral: bool = True) -> np.ndarray:
        lam, mu = self.expected_goals(home, away, neutral)
        gh = np.arange(MAX_GOALS + 1)
        disp = getattr(self, 'dispersion', 1.0)
        if disp <= 1.0:
            ph = _pois_pmf(gh, lam)
            pa = _pois_pmf(gh, mu)
        else:
            ph = _nb_pmf(gh, lam, disp)
            pa = _nb_pmf(gh, mu, disp)
        m = np.outer(ph, pa)
        # correção Dixon-Coles nos quatro placares baixos
        m[0, 0] *= 1.0 - lam * mu * self.rho
        m[0, 1] *= 1.0 + lam * self.rho
        m[1, 0] *= 1.0 + mu * self.rho
        m[1, 1] *= 1.0 - self.rho
        m = np.clip(m, 1e-12, None)
        return m / m.sum()

    def outcome_probs(self, home: str, away: str, neutral: bool = True) -> tuple[float, float, float]:
        m = self.score_matrix(home, away, neutral)
        p_home = np.tril(m, -1).sum()  # mandante faz mais gols
        p_draw = np.trace(m)
        p_away = np.triu(m, 1).sum()
        return float(p_home), float(p_draw), float(p_away)

    def sample_score(self, home: str, away: str, rng: np.random.Generator,
                     neutral: bool = True) -> tuple[int, int]:
        lam, mu = self.expected_goals(home, away, neutral)
        disp = getattr(self, 'dispersion', 1.0)
        if disp <= 1.0:
            # Poisson
            g_home = rng.poisson(lam)
            g_away = rng.poisson(mu)
        else:
            # Negative Binomial approximation for overdispersion
            # var = mean * disp; use nbinom with appropriate params
            def _nb_sample(mean, disp, rng):
                if mean <= 0:
                    return 0
                # Common parametrization: n = mean / (disp-1), p = 1/disp
                n = mean / (disp - 1)
                p = 1.0 / disp
                return int(rng.negative_binomial(n, p))
            g_home = _nb_sample(lam, disp, rng)
            g_away = _nb_sample(mu, disp, rng)
        return int(g_home), int(g_away)


def _pois_pmf(k: np.ndarray, lam: float) -> np.ndarray:
    return np.exp(k * np.log(lam) - lam - gammaln(k + 1.0))

def _nb_pmf(k: np.ndarray, mean: float, disp: float) -> np.ndarray:
    """Negative binomial PMF approximation for overdispersed counts.
    var = mean * disp
    """
    if mean <= 0:
        return np.zeros_like(k, dtype=float)
    n = mean / (disp - 1.0)
    p = 1.0 / disp
    # nbinom.pmf(k, n, p) where mean = n*(1-p)/p
    return nbinom.pmf(k, n, p)


def fit_dixon_coles(matches: pd.DataFrame, half_life_days: float = 730.0,
                    since: str = "2017-01-01", min_games: int = 8) -> DixonColes:
    """Ajusta o modelo. half_life_days controla o quão rápido o passado 'esquece'."""
    df = matches[matches["date"] >= since].copy()

    # mantém só times com jogos suficientes (evita parâmetros instáveis)
    counts = pd.concat([df["home_team"], df["away_team"]]).value_counts()
    keep = set(counts[counts >= min_games].index)
    df = df[df["home_team"].isin(keep) & df["away_team"].isin(keep)].reset_index(drop=True)

    teams = sorted(set(df["home_team"]) | set(df["away_team"]))
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    hi = df["home_team"].map(idx).to_numpy()
    ai = df["away_team"].map(idx).to_numpy()
    hg = df["home_score"].to_numpy(dtype=float)
    ag = df["away_score"].to_numpy(dtype=float)
    neut = df["neutral"].to_numpy(dtype=bool)

    # pesos temporais: exp(-ln2 * dias_atras / meia_vida)
    ref = df["date"].max()
    days = (ref - df["date"]).dt.days.to_numpy(dtype=float)
    w = np.exp(-np.log(2.0) * days / half_life_days)

    lgh = gammaln(hg + 1.0)
    lga = gammaln(ag + 1.0)

    def neg_loglik(theta: np.ndarray) -> float:
        atk = theta[:n]
        atk = atk - atk.mean()           # identificabilidade: média de ataque = 0
        dfc = theta[n:2 * n]
        gamma = theta[2 * n]
        rho = theta[2 * n + 1]

        log_lam = atk[hi] + dfc[ai] + gamma * (~neut)
        log_mu = atk[ai] + dfc[hi]
        lam = np.exp(log_lam)
        mu = np.exp(log_mu)

        ll = hg * log_lam - lam - lgh + ag * log_mu - mu - lga

        # correção Dixon-Coles (em log), só nos placares baixos
        tau = np.ones_like(ll)
        m00 = (hg == 0) & (ag == 0)
        m01 = (hg == 0) & (ag == 1)
        m10 = (hg == 1) & (ag == 0)
        m11 = (hg == 1) & (ag == 1)
        tau[m00] = 1.0 - lam[m00] * mu[m00] * rho
        tau[m01] = 1.0 + lam[m01] * rho
        tau[m10] = 1.0 + mu[m10] * rho
        tau[m11] = 1.0 - rho
        ll = ll + np.log(np.clip(tau, 1e-9, None))

        reg = 1e-3 * (np.sum(theta[:2 * n] ** 2))  # regularização leve
        return -np.sum(w * ll) + reg

    x0 = np.concatenate([np.zeros(n), np.zeros(n), [0.2, -0.1]])
    bounds = [(-3, 3)] * (2 * n) + [(-0.5, 1.0), (-0.2, 0.2)]
    res = minimize(neg_loglik, x0, method="L-BFGS-B", bounds=bounds,
                   options={"maxiter": 400, "maxfun": 60000})

    atk = res.x[:n]
    atk = atk - atk.mean()
    dfc = res.x[n:2 * n]
    disp = estimate_dispersion(df)  # rough from the filtered df used in fit
    return DixonColes(
        teams=teams, attack=atk, defence=dfc,
        home_adv=float(res.x[2 * n]), rho=float(res.x[2 * n + 1]),
        _idx=idx, avg_attack=float(atk.mean()), avg_defence=float(dfc.mean()),
        dispersion=float(np.clip(disp, 1.0, 2.0)),
    )


def estimate_dispersion(matches: pd.DataFrame, min_mean: float = 0.5) -> float:
    """Estima dispersão média (var / mean) dos gols históricos.
    >1 indica overdispersion."""
    hg = matches['home_score'].to_numpy()
    ag = matches['away_score'].to_numpy()
    means = []
    for g in [hg, ag]:
        m = np.mean(g)
        v = np.var(g)
        if m > min_mean:
            means.append(v / m)
    return float(np.mean(means)) if means else 1.0


if __name__ == "__main__":
    from wc2026.data import load_matches

    matches = load_matches()
    model = fit_dixon_coles(matches)
    disp = estimate_dispersion(matches)
    print(f"home_adv={model.home_adv:.3f}  rho={model.rho:.3f}  times={len(model.teams)}  estimated_dispersion={disp:.2f}")
    for h, a in [("Brazil", "Morocco"), ("Argentina", "Jordan"), ("Spain", "Uruguay")]:
        ph, pd_, pa = model.outcome_probs(h, a)
        lam, mu = model.expected_goals(h, a)
        print(f"{h} x {a}: V {ph:.0%} | E {pd_:.0%} | D {pa:.0%}  (xg {lam:.2f}-{mu:.2f})")
