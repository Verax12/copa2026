"""
Camada de Machine Learning: gradient boosting com perda de Poisson para prever
os gols esperados de cada lado, usando as features ricas (Elo, forma, perfil
ofensivo de jogadores).

Usa XGBoost se disponível; senão cai no HistGradientBoostingRegressor do
sklearn (também boosting nativo, perda Poisson) — assim roda em qualquer máquina.

Inclui validação OUT-OF-TIME: treina em jogos <= 2023 e testa em 2024+,
comparando a acurácia/log-loss contra dois baselines (só Elo e o Dixon-Coles),
para mostrar quanto a granularidade extra realmente ajuda.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import poisson, nbinom

from .features import FEATURE_COLS

try:
    from xgboost import XGBRegressor
    _HAS_XGB = True
except Exception:
    _HAS_XGB = False
    from sklearn.ensemble import HistGradientBoostingRegressor


def _make_regressor():
    if _HAS_XGB:
        return XGBRegressor(objective="count:poisson", n_estimators=400,
                            max_depth=4, learning_rate=0.05, subsample=0.8,
                            colsample_bytree=0.8, min_child_weight=5, n_jobs=-1)
    return HistGradientBoostingRegressor(loss="poisson", max_iter=400,
                                         max_depth=4, learning_rate=0.05,
                                         min_samples_leaf=20)


@dataclass
class GoalML:
    reg_home: object
    reg_away: object
    rho: float  # correção Dixon-Coles reaproveitada para placares baixos

    def expected_goals(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        lam = np.clip(self.reg_home.predict(X[FEATURE_COLS]), 0.05, 8)
        mu = np.clip(self.reg_away.predict(X[FEATURE_COLS]), 0.05, 8)
        return lam, mu


def _result_probs_from_goals(lam: float, mu: float, rho: float, maxg: int = 10) -> tuple[float, float, float]:
    g = np.arange(maxg + 1)
    ph = poisson.pmf(g, lam)
    pa = poisson.pmf(g, mu)
    m = np.outer(ph, pa)
    m[0, 0] *= 1 - lam * mu * rho
    m[0, 1] *= 1 + lam * rho
    m[1, 0] *= 1 + mu * rho
    m[1, 1] *= 1 - rho
    m = np.clip(m, 1e-12, None); m /= m.sum()
    return float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())


def train(feats: pd.DataFrame, rho: float = -0.05, dispersion: float = 1.25) -> GoalML:
    rh = _make_regressor(); rh.fit(feats[FEATURE_COLS], feats["y_home_goals"])
    ra = _make_regressor(); ra.fit(feats[FEATURE_COLS], feats["y_away_goals"])
    gm = GoalML(rh, ra, rho)
    gm.dispersion = float(dispersion)  # attach for sampling
    return gm


def _logloss(probs: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(probs[np.arange(len(y)), y], 1e-9, 1)
    return float(-np.mean(np.log(p)))


def evaluate_out_of_time(feats: pd.DataFrame, cutoff: str = "2024-01-01",
                         dc_rho: float = -0.05) -> pd.DataFrame:
    """Treina antes do cutoff, testa depois. Compara ML vs baseline de Elo."""
    train_df = feats[feats["date"] < cutoff]
    test_df = feats[feats["date"] >= cutoff].reset_index(drop=True)

    model = train(train_df, rho=dc_rho)
    lam, mu = model.expected_goals(test_df)

    # probabilidades do ML
    ml_probs = np.array([_result_probs_from_goals(l, m, dc_rho) for l, m in zip(lam, mu)])

    # baseline: só Elo (mapeia diferença de Elo -> W/D/L com a heurística de empate)
    from .elo import win_probabilities
    base = np.array([win_probabilities(r.elo_home + (0 if r.neutral else 65), r.elo_away)
                     for r in test_df.itertuples(index=False)])

    y = test_df["y_result"].to_numpy()
    ml_acc = (ml_probs.argmax(1) == y).mean()
    base_acc = (base.argmax(1) == y).mean()
    return pd.DataFrame({
        "modelo": ["Baseline (só Elo)", "ML (boosting Poisson + jogadores)"],
        "acurácia": [base_acc, ml_acc],
        "log_loss": [_logloss(base, y), _logloss(ml_probs, y)],
        "n_teste": [len(y), len(y)],
    })


def feature_importance(model: GoalML, top: int = 10) -> pd.Series | None:
    if not _HAS_XGB:
        return None
    imp = pd.Series(model.reg_home.feature_importances_, index=FEATURE_COLS)
    return imp.sort_values(ascending=False).head(top)


class MLGoalModel:
    """Adaptador com a MESMA interface do DixonColes (score_matrix / expected_goals),
    para o Monte Carlo poder usar o motor de ML sem mudanças. Pré-calcula os
    gols esperados de todos os pares de seleções de uma vez (rápido)."""

    def __init__(self, goal_ml: GoalML, state: dict, teams: list[str]):
        self.gm = goal_ml
        self.rho = goal_ml.rho
        self.dispersion = getattr(goal_ml, 'dispersion', 1.25)
        # monta todas as linhas de features (pares ordenados) de uma vez
        from .features import match_row
        rows, keys = [], []
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                rows.append(match_row(state, h, a, neutral=True))
                keys.append((h, a))
        big = pd.concat(rows, ignore_index=True)
        lam, mu = goal_ml.expected_goals(big)
        self._lam = {k: float(l) for k, l in zip(keys, lam)}
        self._mu = {k: float(m) for k, m in zip(keys, mu)}

    def expected_goals(self, home: str, away: str, neutral: bool = True) -> tuple[float, float]:
        return self._lam[(home, away)], self._mu[(home, away)]

    def score_matrix(self, home: str, away: str, neutral: bool = True) -> np.ndarray:
        lam, mu = self.expected_goals(home, away)
        disp = getattr(self, 'dispersion', 1.0)
        g = np.arange(11)
        if disp <= 1.0:
            ph = poisson.pmf(g, lam)
            pa = poisson.pmf(g, mu)
        else:
            # approx NB pmf for overdisp
            def _nb_pmf(k, mean, disp):
                if mean <= 0: return np.zeros_like(k, dtype=float)
                n = mean / (disp - 1)
                p = 1.0 / disp
                return nbinom.pmf(k, n, p)
            ph = _nb_pmf(g, lam, disp)
            pa = _nb_pmf(g, mu, disp)
        m = np.outer(ph, pa)
        m[0, 0] *= 1 - lam * mu * self.rho
        m[0, 1] *= 1 + lam * self.rho
        m[1, 0] *= 1 + mu * self.rho
        m[1, 1] *= 1 - self.rho
        m = np.clip(m, 1e-12, None)
        return m / m.sum()

    def sample_score(self, home: str, away: str, rng: np.random.Generator,
                     neutral: bool = True) -> tuple[int, int]:
        lam, mu = self.expected_goals(home, away, neutral)
        disp = getattr(self, 'dispersion', 1.0)
        if disp <= 1.0:
            g_home = rng.poisson(lam)
            g_away = rng.poisson(mu)
        else:
            def _nb_sample(mean, disp, rng):
                if mean <= 0:
                    return 0
                n = mean / (disp - 1)
                p = 1.0 / disp
                return int(rng.negative_binomial(n, p))
            g_home = _nb_sample(lam, disp, rng)
            g_away = _nb_sample(mu, disp, rng)
        return int(g_home), int(g_away)


if __name__ == "__main__":
    from wc2026.data import load_matches
    from wc2026.features import build_features

    print("backend:", "XGBoost" if _HAS_XGB else "sklearn HistGradientBoosting")
    feats = build_features(load_matches())
    print("\nValidação out-of-time (treino <2024, teste 2024+):")
    print(evaluate_out_of_time(feats).to_string(index=False))

    full = train(feats)
    fi = feature_importance(full)
    if fi is not None:
        print("\nFeatures mais importantes (gols do mandante):")
        for k, v in fi.items():
            print(f"  {k:<22}{v:.3f}")
