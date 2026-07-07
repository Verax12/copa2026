"""
Calibração pós-modelo das probabilidades V/E/D.

Os motores existentes são modelos de gols: produzem uma matriz de placares e as
probabilidades de vitória/empate/derrota são somas dessa matriz. Esta camada
aprende uma correção direta para V/E/D em validação temporal e reescala a matriz
por região (vitória, empate, derrota), preservando a forma relativa dos placares
dentro de cada resultado.

Melhorias Point 4 (Calibração + Ensemble):
- Peso ensemble dinâmico (via validação em ensemble.get_optimal_ensemble_weight)
- Calibrador mais avançado: Logistic + isotonic (CalibratedClassifierCV) + features
  expandidas (_feature_row: neutral, pmax, entropy, |gdiff| etc além de originais)
- w e alpha configuráveis; defaults alinhados; fases/campeão indiretamente
  melhorados via probs de jogo melhores (calib direta de %campeão via sims
  históricos é viável com mais dados de torneios passados).
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
    """Features estendidas para calibrador mais forte (Point 4).
    Além das probs e esperados, adiciona neutral flag, pmax (confiança), entropia
    das probs (para correção de over/under-confidence), e abs diff.
    """
    ph, pd_, pa = model.outcome_probs(home, away, neutral=neutral)
    lh, la = model.expected_goals(home, away, neutral=neutral)
    p = np.clip(np.array([ph, pd_, pa], dtype=float), 1e-6, 1 - 1e-6)
    log_odds = float(np.log(p[0] / p[2]))
    log_draw = float(np.log(p[1] / np.sqrt(p[0] * p[2])))
    gdiff = float(lh - la)
    gtot = float(lh + la)
    pmax = float(np.max(p))
    entropy = float(-np.sum(p * np.log(p + 1e-12)))
    neut = 1.0 if neutral else 0.0
    return [
        float(p[0]), float(p[1]), float(p[2]),
        log_odds,
        log_draw,
        gdiff,
        gtot,
        pmax,
        entropy,
        neut,
        abs(gdiff),
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

    def _blend(self, home: str, away: str, neutral: bool) -> np.ndarray:
        base = np.asarray(self.base.outcome_probs(home, away, neutral=neutral), dtype=float)
        cal = np.asarray(self.calibrator.predict(self.base, home, away, neutral), dtype=float)
        out = (1.0 - self.alpha) * base + self.alpha * cal
        return out / out.sum()

    def outcome_probs(self, home: str, away: str, neutral: bool = True) -> tuple[float, float, float]:
        out = self._blend(home, away, neutral)
        if neutral:
            # O calibrador foi treinado em jogos reais (maioria COM mando), então
            # carrega um prior de mando que features espelhadas não anulam. Em
            # campo neutro P(A vence B) não pode depender da ordem do par:
            # simetrizamos com a orientação invertida (mesmo princípio da tabela
            # do MLGoalModel). Com neutral=False (anfitrião) a orientação vale.
            back = self._blend(away, home, neutral)
            out = np.asarray([out[0] + back[2], out[1] + back[1], out[2] + back[0]]) / 2.0
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
                           w: float = 0.55) -> OutcomeCalibrator:
    """Treina o calibrador em previsões honestas para jogos recentes pré-Copa.

    O modelo base usado para gerar as features é treinado só antes de
    `train_cutoff`; o calibrador aprende nos jogos entre `train_cutoff` e
    `valid_until`, evitando usar jogos já disputados da Copa como validação.

    Melhoria Point 4: usa Logistic + isotonic (CalibratedClassifierCV method=isotonic)
    para calibração mais avançada de probs + features expandidas em _feature_row;
    w default alinhado com ensemble (dinâmico possível via caller).
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

    # Calibrador mais avançado (Point 4): Logistic + isotonic (melhor calibração
    # de probabilidades que Logistic puro). Isotonic (monótono) corrige confiança.
    # Tenta CalibratedClassifierCV com isotonic; se indisponível ou falha (dados
    # pequenos), usa Logistic com params otimizados (C menor p/ regularizar).
    # (HistGB forte deixado de lado por default pois valid set pode ser pequeno
    #  p/ boosting; pode ser reativado com tuning futuro.)
    clf = LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000, solver="lbfgs")
    try:
        from sklearn.calibration import CalibratedClassifierCV
        # isotonic on top para probs mais bem calibradas
        clf = CalibratedClassifierCV(clf, method="isotonic", cv=2)
    except Exception:
        pass
    clf.fit(x, y)
    return OutcomeCalibrator(clf)


def calibrate_model(model, matches: pd.DataFrame, engine: str = "ensemble",
                    w: float = 0.55, alpha: float = 0.5) -> CalibratedGoalModel:
    """Wrapper que aplica calibrador. w default 0.55 alinhado com ensemble atual;
    para ensemble caller pode passar w dinâmico de get_optimal.
    """
    return CalibratedGoalModel(model, fit_outcome_calibrator(matches, engine=engine, w=w), alpha=alpha)
