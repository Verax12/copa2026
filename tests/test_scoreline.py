"""Testa o placar coerente com o resultado favorito (wc2026/scoreline.py)."""
import numpy as np

from wc2026.scoreline import favored_scoreline, outcome_probs_from_matrix


def _matrix_draw_mode_but_home_favored():
    """Matriz onde a MODA global é um empate (1-1), mas a soma das vitórias do
    mandante é o resultado mais provável. É exatamente o caso 'Brasil x Marrocos'
    que gerava a contradição 'previsto 1-1' + 'favorito vence'."""
    M = np.zeros((4, 4))
    M[0, 0], M[1, 1], M[2, 2] = 0.06, 0.20, 0.04          # empates: soma 0.30
    M[1, 0], M[2, 1], M[2, 0], M[3, 1] = 0.12, 0.13, 0.10, 0.08  # mandante: 0.43
    M[0, 1], M[0, 2], M[1, 2] = 0.10, 0.10, 0.08          # visitante: 0.28
    return M


def test_global_mode_is_a_draw():
    M = _matrix_draw_mode_but_home_favored()
    gi, gj = np.unravel_index(int(M.argmax()), M.shape)
    assert (gi, gj) == (1, 1)            # a moda global É um empate


def test_favored_scoreline_picks_a_home_win():
    M = _matrix_draw_mode_but_home_favored()
    favored, (gi, gj), (ph, pd, pa) = favored_scoreline(M)
    assert favored == 0                  # resultado favorito = vitória do mandante
    assert gi > gj                       # o placar escolhido É uma vitória (não empate)
    assert (gi, gj) == (2, 1)            # placar mais provável dentro das vitórias
    assert ph > pd and ph > pa


def test_outcome_consistency_invariant():
    """Invariante central: o resultado do placar escolhido SEMPRE bate com o
    favorito (vence/empata/perde). É o que garante winnerHit == probHit."""
    rng = np.random.default_rng(0)
    for _ in range(200):
        M = rng.random((6, 6))
        M /= M.sum()
        favored, (gi, gj), _ = favored_scoreline(M)
        outcome = 0 if gi > gj else (1 if gi == gj else 2)
        assert outcome == favored


def test_probs_override_decides_favorite():
    """Quando se passa probs oficiais (ex.: calibradas), o favorito segue elas e
    só o placar é buscado na matriz."""
    M = _matrix_draw_mode_but_home_favored()
    # força empate como favorito via probs explícitas
    favored, (gi, gj), _ = favored_scoreline(M, probs=(0.2, 0.6, 0.2))
    assert favored == 1
    assert gi == gj                      # placar é um empate
    assert (gi, gj) == (1, 1)            # empate mais provável


def test_outcome_probs_sum_and_regions():
    M = _matrix_draw_mode_but_home_favored()
    ph, pd, pa = outcome_probs_from_matrix(M)
    assert abs((ph + pd + pa) - M.sum()) < 1e-9
    assert ph > pa                       # mandante mais provável que visitante
