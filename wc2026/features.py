"""
Engenharia de features por jogo, SEM vazamento temporal.

Faz um único passe cronológico por toda a base. Para cada jogo, registra o
estado ANTES da partida (Elo, forma recente, perfil ofensivo do ano anterior)
e só DEPOIS atualiza esse estado com o resultado. Assim o modelo nunca "vê o
futuro" — condição essencial para validar honestamente.

Saída: um DataFrame com uma linha por jogo (a partir de `since`), com features
pré-jogo + os rótulos (gols de cada lado e resultado).
"""
from __future__ import annotations

from collections import defaultdict, deque

import numpy as np
import pandas as pd

from .elo import HOME_ADVANTAGE, _k_factor, _expected, BASE_RATING
from .players import load_goalscorers, yearly_profiles

FORM_N = 5  # nº de jogos recentes p/ medir forma

TOURN_WEIGHT = {
    "FIFA World Cup": 1.0, "FIFA World Cup qualification": 0.7,
    "UEFA Euro": 0.85, "Copa América": 0.85, "African Cup of Nations": 0.8,
    "AFC Asian Cup": 0.8, "UEFA Nations League": 0.6, "Friendly": 0.2,
}


def build_features(matches: pd.DataFrame, since: str = "2015-01-01") -> pd.DataFrame:
    elo: dict[str, float] = defaultdict(lambda: BASE_RATING)
    pts_hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=FORM_N))
    gf_hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=FORM_N))
    ga_hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=FORM_N))

    profiles = yearly_profiles(load_goalscorers())

    def prof(team: str, year: int, key: str) -> float:
        return profiles.get((team, year - 1), {}).get(key, 0.0)

    def mean(d: deque, default: float = 0.0) -> float:
        return float(np.mean(d)) if len(d) else default

    rows = []
    since_ts = pd.Timestamp(since)

    for r in matches.itertuples(index=False):
        h, a = r.home_team, r.away_team
        rh, ra = elo[h], elo[a]
        adv = 0.0 if r.neutral else HOME_ADVANTAGE

        if r.date >= since_ts:
            yr = r.date.year
            rows.append({
                "date": r.date, "home_team": h, "away_team": a,
                "neutral": int(r.neutral),
                "elo_home": rh, "elo_away": ra,
                "elo_diff": (rh + adv) - ra,
                "form_home": mean(pts_hist[h]), "form_away": mean(pts_hist[a]),
                "gf_home": mean(gf_hist[h], 1.0), "ga_home": mean(ga_hist[h], 1.0),
                "gf_away": mean(gf_hist[a], 1.0), "ga_away": mean(ga_hist[a], 1.0),
                "tourn_w": TOURN_WEIGHT.get(r.tournament, 0.4),
                "off_goals_home": prof(h, yr, "goals"), "off_nscor_home": prof(h, yr, "n_scorers"),
                "off_topshare_home": prof(h, yr, "top_share"), "off_penrate_home": prof(h, yr, "pen_rate"),
                "off_goals_away": prof(a, yr, "goals"), "off_nscor_away": prof(a, yr, "n_scorers"),
                "off_topshare_away": prof(a, yr, "top_share"), "off_penrate_away": prof(a, yr, "pen_rate"),
                "y_home_goals": r.home_score, "y_away_goals": r.away_score,
                "y_result": 0 if r.home_score > r.away_score else (1 if r.home_score == r.away_score else 2),
            })

        # --- atualiza estado DEPOIS de registrar (sem vazamento) ---
        exp_home = _expected(rh + adv, ra)
        sh = 1.0 if r.home_score > r.away_score else (0.5 if r.home_score == r.away_score else 0.0)
        k = _k_factor(r.tournament, abs(r.home_score - r.away_score))
        delta = k * (sh - exp_home)
        elo[h] = rh + delta
        elo[a] = ra - delta

        ph = 3 if sh == 1.0 else (1 if sh == 0.5 else 0)
        pts_hist[h].append(ph); pts_hist[a].append(3 - ph if ph != 1 else 1)
        gf_hist[h].append(r.home_score); ga_hist[h].append(r.away_score)
        gf_hist[a].append(r.away_score); ga_hist[a].append(r.home_score)

    return pd.DataFrame(rows)


FEATURE_COLS = [
    "neutral", "elo_home", "elo_away", "elo_diff", "form_home", "form_away",
    "gf_home", "ga_home", "gf_away", "ga_away", "tourn_w",
    "off_goals_home", "off_nscor_home", "off_topshare_home", "off_penrate_home",
    "off_goals_away", "off_nscor_away", "off_topshare_away", "off_penrate_away",
]


def current_state(matches: pd.DataFrame) -> dict:
    """Passe cronológico que devolve o estado MAIS RECENTE de cada seleção
    (Elo, forma, gols recentes) + os perfis ofensivos anuais. Usado para montar
    features dos confrontos da Copa 2026."""
    elo: dict[str, float] = defaultdict(lambda: BASE_RATING)
    pts_hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=FORM_N))
    gf_hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=FORM_N))
    ga_hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=FORM_N))

    for r in matches.itertuples(index=False):
        h, a = r.home_team, r.away_team
        rh, ra = elo[h], elo[a]
        adv = 0.0 if r.neutral else HOME_ADVANTAGE
        exp_home = _expected(rh + adv, ra)
        sh = 1.0 if r.home_score > r.away_score else (0.5 if r.home_score == r.away_score else 0.0)
        k = _k_factor(r.tournament, abs(r.home_score - r.away_score))
        delta = k * (sh - exp_home)
        elo[h] = rh + delta; elo[a] = ra - delta
        ph = 3 if sh == 1.0 else (1 if sh == 0.5 else 0)
        pts_hist[h].append(ph); pts_hist[a].append(3 - ph if ph != 1 else 1)
        gf_hist[h].append(r.home_score); ga_hist[h].append(r.away_score)
        gf_hist[a].append(r.away_score); ga_hist[a].append(r.home_score)

    return {
        "elo": dict(elo),
        "form": {t: (float(np.mean(d)) if d else 1.0) for t, d in pts_hist.items()},
        "gf": {t: (float(np.mean(d)) if d else 1.0) for t, d in gf_hist.items()},
        "ga": {t: (float(np.mean(d)) if d else 1.0) for t, d in ga_hist.items()},
        "profiles": yearly_profiles(load_goalscorers()),
    }


def match_row(state: dict, home: str, away: str, neutral: bool = True,
              ref_year: int = 2026) -> pd.DataFrame:
    """Monta uma linha de features (mesmas colunas do treino) para um confronto."""
    eh = state["elo"].get(home, BASE_RATING)
    ea = state["elo"].get(away, BASE_RATING)
    adv = 0.0 if neutral else HOME_ADVANTAGE

    def prof(team: str, key: str) -> float:
        # usa o perfil ofensivo mais recente disponível (2025, senão 2024)
        for y in (ref_year - 1, ref_year - 2):
            p = state["profiles"].get((team, y))
            if p:
                return p.get(key, 0.0)
        return 0.0

    row = {
        "neutral": int(neutral),
        "elo_home": eh, "elo_away": ea, "elo_diff": (eh + adv) - ea,
        "form_home": state["form"].get(home, 1.0), "form_away": state["form"].get(away, 1.0),
        "gf_home": state["gf"].get(home, 1.0), "ga_home": state["ga"].get(home, 1.0),
        "gf_away": state["gf"].get(away, 1.0), "ga_away": state["ga"].get(away, 1.0),
        "tourn_w": 1.0,
        "off_goals_home": prof(home, "goals"), "off_nscor_home": prof(home, "n_scorers"),
        "off_topshare_home": prof(home, "top_share"), "off_penrate_home": prof(home, "pen_rate"),
        "off_goals_away": prof(away, "goals"), "off_nscor_away": prof(away, "n_scorers"),
        "off_topshare_away": prof(away, "top_share"), "off_penrate_away": prof(away, "pen_rate"),
    }
    return pd.DataFrame([row])


if __name__ == "__main__":
    from wc2026.data import load_matches
    feats = build_features(load_matches())
    print(f"{len(feats):,} jogos com features (de {feats.date.min().date()} a {feats.date.max().date()})")
    print("colunas de feature:", len(FEATURE_COLS))
    print(feats[["date", "home_team", "away_team", "elo_diff", "form_home", "off_goals_home", "y_home_goals"]].tail(5).to_string(index=False))
