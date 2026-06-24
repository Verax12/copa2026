"""
Calibração pós-modelo das probabilidades V/E/D.

Os motores existentes são modelos de gols: produzem uma matriz de placares e as
probabilidades de vitória/empate/derrota são somas dessa matriz. Esta camada
aprende uma correção direta para V/E/D em validação temporal e reescala a matriz
por região (vitória, empate, derrota), preservando a forma relativa dos placares
dentro de cada resultado.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

CUP_START = "2026-06-11"
DEFAULT_TRAIN_CUTOFF = "2024-01-01"


def _outcome(hs: int, a_s: int) -> int:
    return 0 if hs > a_s else (1 if hs == a_s else 2)


def _matrix_outcome_probs(m: np.ndarray) -> tuple[float, float, float]:
    return float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())


def _feature_row(model, home: str, away: str, neutral: bool) -> list[float]:
    ph, pd_, pa = model.outcome_probs(home, away, neutral=neutral)
    lh, la = model.expected_goals(home, away, neutral=neutral)
    p = np.clip(np.array([ph, pd_, pa], dtype=float), 1e-6, 1 - 1e-6)
    return [
        float(p[0]), float(p[1]), float(p[2]),
        float(np.log(p[0] / p[2])),
        float(np.log(p[1] / np.sqrt(p[0] * p[2]))),
        float(lh - la),
        float(lh + la),
    ]


def _features_for_matches(model, matches: pd.DataFrame) -> np.ndarray:
    rows = [
        _feature_row(model, r.home_team, r.away_team, bool(r.neutral))
        for r in matches.itertuples(index=False)
    ]
    return np.asarray(rows, dtype=float)


@dataclass
class OutcomeCalibrator:
    clf: object

    def predict(self, model, home: str, away: str, neutral: bool = True) -> tuple[float, float, float]:
        x = np.asarray([_feature_row(model, home, away, neutral)], dtype=float)
        raw = np.asarray(self.clf.predict_proba(x)[0], dtype=float)
        out = np.zeros(3, dtype=float)
        for i, cls in enumerate(getattr(self.clf, "classes_", [0, 1, 2])):
            out[int(cls)] = raw[i]
        s = out.sum()
        if s <= 0:
            return model.outcome_probs(home, away, neutral=neutral)
        out /= s
        return float(out[0]), float(out[1]), float(out[2])


class CalibratedGoalModel:
    """Wrapper com a mesma interface dos motores de gols."""

    def __init__(self, base, calibrator: OutcomeCalibrator, alpha: float = 0.5):
        self.base = base
        self.calibrator = calibrator
        self.alpha = float(alpha)
        self.rho = float(getattr(base, "rho", -0.05))

    def outcome_probs(self, home: str, away: str, neutral: bool = True) -> tuple[float, float, float]:
        base = np.asarray(self.base.outcome_probs(home, away, neutral=neutral), dtype=float)
        cal = np.asarray(self.calibrator.predict(self.base, home, away, neutral), dtype=float)
        out = (1.0 - self.alpha) * base + self.alpha * cal
        out /= out.sum()
        return float(out[0]), float(out[1]), float(out[2])

    def score_matrix(self, home: str, away: str, neutral: bool = True) -> np.ndarray:
        m = self.base.score_matrix(home, away, neutral=neutral).copy()
        base_probs = np.clip(np.asarray(_matrix_outcome_probs(m)), 1e-12, None)
        target = np.asarray(self.outcome_probs(home, away, neutral=neutral))

        rows, cols = np.indices(m.shape)
        masks = (rows > cols, rows == cols, rows < cols)
        for k, mask in enumerate(masks):
            m[mask] *= target[k] / base_probs[k]
        return m / m.sum()

    def expected_goals(self, home: str, away: str, neutral: bool = True) -> tuple[float, float]:
        m = self.score_matrix(home, away, neutral=neutral)
        g = np.arange(m.shape[0])
        return float((m.sum(axis=1) * g).sum()), float((m.sum(axis=0) * g).sum())


def fit_outcome_calibrator(matches: pd.DataFrame,
                           train_cutoff: str = DEFAULT_TRAIN_CUTOFF,
                           valid_until: str = CUP_START,
                           engine: str = "ensemble",
                           w: float = 0.5) -> OutcomeCalibrator:
    """Treina o calibrador em previsões honestas para jogos recentes pré-Copa.

    O modelo base usado para gerar as features é treinado só antes de
    `train_cutoff`; o calibrador aprende nos jogos entre `train_cutoff` e
    `valid_until`, evitando usar jogos já disputados da Copa como validação.
    """
    from sklearn.linear_model import LogisticRegression

    train = matches[matches["date"] < train_cutoff]
    valid = matches[(matches["date"] >= train_cutoff) & (matches["date"] < valid_until)]
    from .groups import all_teams
    teams = set(all_teams())
    valid = valid[valid["home_team"].isin(teams) & valid["away_team"].isin(teams)]
    if valid.empty:
        raise ValueError("sem jogos de validação para calibrar V/E/D")

    if engine == "ensemble":
        from .ensemble import build_ensemble
        base = build_ensemble(train, w=w)
    elif engine == "ml":
        from .features import build_features, current_state
        from .ml_model import MLGoalModel, train as train_ml
        base = MLGoalModel(train_ml(build_features(train)), current_state(train), all_teams())
    else:
        from .goal_model import fit_dixon_coles
        base = fit_dixon_coles(train)

    x = _features_for_matches(base, valid)
    y = np.asarray([_outcome(r.home_score, r.away_score) for r in valid.itertuples(index=False)])
    clf = LogisticRegression(C=0.5, max_iter=1000)
    clf.fit(x, y)
    return OutcomeCalibrator(clf)


def calibrate_model(model, matches: pd.DataFrame, engine: str = "ensemble",
                    w: float = 0.5, alpha: float = 0.5) -> CalibratedGoalModel:
    return CalibratedGoalModel(model, fit_outcome_calibrator(matches, engine=engine, w=w), alpha=alpha)
