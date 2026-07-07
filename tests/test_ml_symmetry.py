"""Regressão da invariante de campo neutro do MLGoalModel.

O bug original: o booster devolvia λs dependentes da ORDEM do par (bônus
sistemático ao "visitante"), fazendo Espanha×Argentina favorecer a Argentina E
Argentina×Espanha favorecer a Espanha — e o passeio determinístico do bracket
coroava quem estivesse listado em 2º. A tabela pré-computada é simetrizada no
construtor; este teste pinna essa invariante na classe REAL (com um GoalML fake
propositalmente assimétrico, para o teste ficar barato e determinístico).
"""
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wc2026.features as features
from wc2026.ml_model import MLGoalModel


class FakeGoalML:
    """Devolve gols esperados que dependem só da POSIÇÃO da linha no lote —
    ou seja, da ordem (h, a) do par: assimetria máxima de propósito."""
    rho = -0.05
    dispersion = 1.0

    def expected_goals(self, X):
        n = len(X)
        lam = np.linspace(0.8, 1.9, n)
        mu = np.linspace(1.7, 0.6, n)
        return lam, mu


def _fake_match_row(state, h, a, neutral=True):
    return pd.DataFrame([{"home": h, "away": a}])


def test_ml_goal_model_symmetric_on_neutral(monkeypatch):
    monkeypatch.setattr(features, "match_row", _fake_match_row)
    m = MLGoalModel(FakeGoalML(), state={}, teams=["A", "B", "C", "D"])

    for h, a in [("A", "B"), ("A", "C"), ("A", "D"), ("B", "C"), ("B", "D"), ("C", "D")]:
        lh, la = m.expected_goals(h, a)
        lh2, la2 = m.expected_goals(a, h)
        # espelho EXATO: o λ de A contra B não depende da ordem do par
        assert lh == la2 and la == lh2

        ph, pdr, pa = m.outcome_probs(h, a)
        ph2, pdr2, pa2 = m.outcome_probs(a, h)
        assert abs(ph - pa2) < 1e-12 and abs(pa - ph2) < 1e-12 and abs(pdr - pdr2) < 1e-12

        M1 = m.score_matrix(h, a)
        M2 = m.score_matrix(a, h)
        assert np.abs(M1 - M2.T).max() < 1e-12


if __name__ == "__main__":
    class _MP:
        def setattr(self, obj, name, value): setattr(obj, name, value)
    test_ml_goal_model_symmetric_on_neutral(_MP())
    print("ok  ml_model: tabela neutra simétrica (espelho exato por par)")
