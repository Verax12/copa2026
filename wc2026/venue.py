"""
Regras de vantagem de mando para a Copa 2026.

A Copa é oficialmente "neutra" em muitos metadados, mas os três anfitriões
(México, EUA e Canadá) têm uma vantagem estrutural quando jogam contra uma
seleção não-anfitriã. Não tentamos inferir vantagem de torcida para outros
países — isso varia por cidade/jogo e exigiria dados externos de público.
"""
from __future__ import annotations

import numpy as np

from .groups import HOSTS


def host_advantage_side(team_a: str, team_b: str) -> int:
    """Retorna 1 se A é anfitrião contra não-anfitrião, -1 se B é anfitrião
    contra não-anfitrião, 0 caso contrário (neutro ou anfitrião vs anfitrião)."""
    a_host = team_a in HOSTS
    b_host = team_b in HOSTS
    if a_host and not b_host:
        return 1
    if b_host and not a_host:
        return -1
    return 0


def score_matrix_with_venue(model, team_a: str, team_b: str) -> np.ndarray:
    """Matriz orientada como (team_a, team_b), aplicando mando apenas se um
    dos dois for anfitrião da Copa 2026.

    Se team_b for o anfitrião, calculamos B como mandante e transponemos a
    matriz para continuar devolvendo placar na ordem (A, B)."""
    side = host_advantage_side(team_a, team_b)
    if side > 0:
        return model.score_matrix(team_a, team_b, neutral=False)
    if side < 0:
        return model.score_matrix(team_b, team_a, neutral=False).T
    return model.score_matrix(team_a, team_b, neutral=True)


def expected_goals_with_venue(model, team_a: str, team_b: str) -> tuple[float, float]:
    """Gols esperados orientados como (team_a, team_b), com a mesma regra de
    `score_matrix_with_venue`."""
    side = host_advantage_side(team_a, team_b)
    if side > 0:
        return model.expected_goals(team_a, team_b, neutral=False)
    if side < 0:
        gb, ga = model.expected_goals(team_b, team_a, neutral=False)
        return ga, gb
    return model.expected_goals(team_a, team_b, neutral=True)
