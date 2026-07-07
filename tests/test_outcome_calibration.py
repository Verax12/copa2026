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
    # neutral=False (mando real): sem simetrização — testa o reescalonamento
    # puro das regiões V/E/D para o alvo calibrado.
    m = model.score_matrix("A", "B", neutral=False)
    ph = float(np.tril(m, -1).sum())
    pd = float(np.trace(m))
    pa = float(np.triu(m, 1).sum())

    assert abs(m.sum() - 1.0) < 1e-9
    assert abs(ph - 0.50) < 1e-9
    assert abs(pd - 0.30) < 1e-9
    assert abs(pa - 0.20) < 1e-9


def test_calibrated_goal_model_symmetric_on_neutral():
    """Em campo neutro P(A vence B) não pode depender da ordem do par: o
    calibrador (treinado em jogos COM mando) é simetrizado com a orientação
    invertida. O fake devolve (0.50, 0.30, 0.20) nas duas orientações, então
    o alvo simetrizado é ((0.5+0.2)/2, 0.3, (0.2+0.5)/2) = (0.35, 0.30, 0.35)."""
    model = CalibratedGoalModel(FakeBase(), FakeCalibrator(), alpha=1.0)
    ph1, pd1, pa1 = model.outcome_probs("A", "B", neutral=True)
    ph2, pd2, pa2 = model.outcome_probs("B", "A", neutral=True)
    assert abs(ph1 - pa2) < 1e-12 and abs(pa1 - ph2) < 1e-12 and abs(pd1 - pd2) < 1e-12
    assert abs(ph1 - 0.35) < 1e-9
    assert abs(pd1 - 0.30) < 1e-9
    assert abs(pa1 - 0.35) < 1e-9


if __name__ == "__main__":
    test_calibrated_goal_model_rescales_outcome_regions()
    test_calibrated_goal_model_symmetric_on_neutral()
    print("ok  outcome_calibration: reescala V/E/D + simetria em campo neutro")
