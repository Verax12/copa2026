"""
Calibração de disputas de pênalti a partir do histórico real (shootouts.csv).

Pergunta: o time mais forte (maior Elo) leva vantagem nos pênaltis, ou é
moeda ao ar? Medimos empiricamente com que frequência o favorito venceu a
disputa, em função da diferença de Elo, e ajustamos uma logística simples.

Resultado típico no futebol: a disputa é quase 50/50, com sinal MUITO leve
para o favorito — bem menos previsível que o jogo em si.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CSV_PATH = Path(__file__).resolve().parent.parent / "shootouts.csv"


def load_shootouts(path: Path = CSV_PATH) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["date"]).dropna(subset=["winner"])


def calibrate(shootouts: pd.DataFrame, elo: dict[str, float]) -> float:
    """
    Ajusta P(favorito vence) = 1/(1+exp(-beta*elo_diff)) e devolve beta.
    beta ~ 0 => puro azar; beta alto => favorito domina. Espera-se beta pequeno.
    """
    diffs, wins = [], []
    for r in shootouts.itertuples(index=False):
        if r.home_team not in elo or r.away_team not in elo:
            continue
        d = elo[r.home_team] - elo[r.away_team]
        diffs.append(d)
        wins.append(1.0 if r.winner == r.home_team else 0.0)
    diffs = np.array(diffs)
    wins = np.array(wins)
    if len(diffs) < 30:
        return 0.0

    # regressão logística 1D por máxima verossimilhança (Newton simples)
    beta = 0.0
    for _ in range(50):
        p = 1.0 / (1.0 + np.exp(-beta * diffs))
        grad = np.sum(diffs * (wins - p))
        hess = -np.sum(diffs**2 * p * (1 - p))
        if abs(hess) < 1e-9:
            break
        beta -= grad / hess
    return float(beta)


def shootout_prob(elo_a: float, elo_b: float, beta: float) -> float:
    """P(A vence a disputa de pênaltis contra B)."""
    return 1.0 / (1.0 + np.exp(-beta * (elo_a - elo_b)))


if __name__ == "__main__":
    from wc2026.data import load_matches
    from wc2026.elo import compute_elo

    elo = compute_elo(load_matches())
    s = load_shootouts()
    beta = calibrate(s, elo)
    print(f"{len(s)} disputas de pênalti | beta calibrado = {beta:.5f}")
    for d in (0, 100, 300):
        print(f"  diferença de {d:>3} Elo -> favorito vence {shootout_prob(d, 0, beta):.1%} das vezes")
