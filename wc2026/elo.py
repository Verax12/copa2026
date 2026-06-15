"""
Ratings Elo no estilo "World Football Elo".

Percorre todos os jogos da história em ordem cronológica e mantém um rating
por seleção. Quanto maior o rating, mais forte. É a feature mais estável
e barata para medir força relativa entre seleções.

Ajustes aplicados:
  - Vantagem de mando (home advantage) só quando o jogo NÃO é em campo neutro.
  - K-factor maior para jogos importantes (Copa > continental > eliminatória > amistoso).
  - Multiplicador de margem de gols: golear vale mais que vencer por 1.
"""
from __future__ import annotations

import pandas as pd

BASE_RATING = 1500.0
HOME_ADVANTAGE = 65.0  # pontos de Elo somados ao mandante em jogo não-neutro

# Peso (K) por tipo de torneio. Quanto mais importante, mais o rating se move.
K_BY_TOURNAMENT = {
    "FIFA World Cup": 60,
    "FIFA World Cup qualification": 40,
    "UEFA Euro": 50,
    "Copa América": 50,
    "African Cup of Nations": 50,
    "AFC Asian Cup": 50,
    "Gold Cup": 45,
    "UEFA Nations League": 40,
    "Confederations Cup": 45,
    "Friendly": 20,
}
K_DEFAULT = 30


def _k_factor(tournament: str, goal_diff: int) -> float:
    base = K_BY_TOURNAMENT.get(tournament, K_DEFAULT)
    # Multiplicador de margem (mesma lógica do World Football Elo)
    if goal_diff <= 1:
        g = 1.0
    elif goal_diff == 2:
        g = 1.5
    else:
        g = (11 + goal_diff) / 8.0
    return base * g


def _expected(rating_a: float, rating_b: float) -> float:
    """Probabilidade esperada de A pontuar contra B (já com mando embutido em rating_a)."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def compute_elo(matches: pd.DataFrame) -> dict[str, float]:
    """Retorna {seleção: rating_elo} após processar toda a base cronologicamente."""
    ratings: dict[str, float] = {}

    for row in matches.itertuples(index=False):
        home, away = row.home_team, row.away_team
        rh = ratings.get(home, BASE_RATING)
        ra = ratings.get(away, BASE_RATING)

        adv = 0.0 if row.neutral else HOME_ADVANTAGE
        exp_home = _expected(rh + adv, ra)

        if row.home_score > row.away_score:
            score_home = 1.0
        elif row.home_score < row.away_score:
            score_home = 0.0
        else:
            score_home = 0.5

        gd = abs(row.home_score - row.away_score)
        k = _k_factor(row.tournament, gd)
        delta = k * (score_home - exp_home)

        ratings[home] = rh + delta
        ratings[away] = ra - delta

    return ratings


def win_probabilities(rating_a: float, rating_b: float, neutral: bool = True) -> tuple[float, float, float]:
    """(P_vitória_A, P_empate, P_vitória_B). Empate estimado empiricamente a partir do Elo."""
    adv = 0.0 if neutral else HOME_ADVANTAGE
    e = _expected(rating_a + adv, rating_b)
    # Fração de empates cai conforme a diferença de força aumenta.
    draw = 0.27 * (1.0 - 2.0 * abs(e - 0.5))
    draw = max(0.05, draw)
    p_a = e - draw / 2.0
    p_b = 1.0 - e - draw / 2.0
    return max(p_a, 0.01), draw, max(p_b, 0.01)


if __name__ == "__main__":
    from wc2026.data import load_matches
    from wc2026.groups import all_teams

    elo = compute_elo(load_matches())
    ranked = sorted(((t, elo.get(t, BASE_RATING)) for t in all_teams()),
                    key=lambda x: -x[1])
    print("Top 12 da Copa 2026 por Elo:")
    for i, (t, r) in enumerate(ranked[:12], 1):
        print(f"{i:2d}. {t:<22} {r:7.1f}")
