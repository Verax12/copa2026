import numpy as np

from wc2026.venue import host_advantage_side, expected_goals_with_venue, score_matrix_with_venue


class TinyModel:
    def expected_goals(self, home, away, neutral=True):
        # Em neutro: 1.0 x 1.0. Com mando: mandante recebe bônus claro.
        return (1.4, 0.8) if not neutral else (1.0, 1.0)

    def score_matrix(self, home, away, neutral=True):
        # Matriz 2x2 orientada como (home, away). Com mando, mais massa em 1-0.
        if neutral:
            return np.array([[0.25, 0.25], [0.25, 0.25]])
        return np.array([[0.15, 0.15], [0.55, 0.15]])


def test_host_advantage_side_only_hosts_against_non_hosts():
    assert host_advantage_side("Mexico", "Brazil") == 1
    assert host_advantage_side("Brazil", "Mexico") == -1
    assert host_advantage_side("Brazil", "Scotland") == 0
    assert host_advantage_side("Mexico", "Canada") == 0  # anfitrião vs anfitrião: neutro


def test_expected_goals_preserves_requested_orientation():
    m = TinyModel()
    assert expected_goals_with_venue(m, "Mexico", "Brazil") == (1.4, 0.8)
    assert expected_goals_with_venue(m, "Brazil", "Mexico") == (0.8, 1.4)
    assert expected_goals_with_venue(m, "Brazil", "Scotland") == (1.0, 1.0)


def test_score_matrix_transposes_when_host_is_second_team():
    m = TinyModel()
    host_first = score_matrix_with_venue(m, "Mexico", "Brazil")
    host_second = score_matrix_with_venue(m, "Brazil", "Mexico")
    assert np.allclose(host_first, np.array([[0.15, 0.15], [0.55, 0.15]]))
    assert np.allclose(host_second, np.array([[0.15, 0.55], [0.15, 0.15]]))
