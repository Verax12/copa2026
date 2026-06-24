import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wc2026.outcome_calibration import CalibratedGoalModel


class FakeBase:
    rho = -0.05

    def score_matrix(self, home, away, neutral=True):
        return np.array([
            [0.10, 0.08, 0.02],
            [0.12, 0.20, 0.05],
            [0.18, 0.15, 0.10],
        ])

    def outcome_probs(self, home, away, neutral=True):
        m = self.score_matrix(home, away, neutral)
        return float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())

    def expected_goals(self, home, away, neutral=True):
        return 1.4, 1.1


class FakeCalibrator:
    def predict(self, model, home, away, neutral=True):
        return 0.50, 0.30, 0.20


def test_calibrated_goal_model_rescales_outcome_regions():
    model = CalibratedGoalModel(FakeBase(), FakeCalibrator(), alpha=1.0)
    m = model.score_matrix("A", "B")
    ph = float(np.tril(m, -1).sum())
    pd = float(np.trace(m))
    pa = float(np.triu(m, 1).sum())

    assert abs(m.sum() - 1.0) < 1e-9
    assert abs(ph - 0.50) < 1e-9
    assert abs(pd - 0.30) < 1e-9
    assert abs(pa - 0.20) < 1e-9


if __name__ == "__main__":
    test_calibrated_goal_model_rescales_outcome_regions()
    print("ok  outcome_calibration: matriz reescalada para V/E/D calibrado")
