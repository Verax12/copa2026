"""
Ensemble dos dois motores de gols: blend (mistura) das distribuições de placar do
Dixon-Coles e do ML (boosting + jogadores).

    M_ensemble = w · M_dixon + (1-w) · M_ml

Como as probabilidades de V/E/D são funcionais lineares da matriz de placares, o
blend da matriz equivale ao blend das probabilidades — então a avaliação por
V/E/D abaixo reflete exatamente o que o motor de ensemble produz.

`evaluate_engines()` compara Dixon, ML e o blend OUT-OF-TIME (treino < cutoff,
teste depois) por log-loss/Brier — a régua honesta pra decidir se o ensemble vale.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .goal_model import fit_dixon_coles
from .ml_model import train, MLGoalModel, _result_probs_from_goals
from .features import build_features, current_state, FEATURE_COLS
from .groups import all_teams


class EnsembleGoalModel:
    """Mesma interface dos motores (score_matrix / expected_goals / outcome_probs),
    misturando Dixon-Coles e ML com peso w (w=1 só Dixon, w=0 só ML)."""

    def __init__(self, dc, ml, w: float = 0.5):
        self.dc, self.ml, self.w = dc, ml, float(w)
        self.rho = float(getattr(dc, "rho", -0.05))   # p/ o ajuste ao vivo (AdjustedGoalModel)

    def score_matrix(self, home: str, away: str, neutral: bool = True) -> np.ndarray:
        M = self.w * self.dc.score_matrix(home, away, neutral) \
            + (1 - self.w) * self.ml.score_matrix(home, away, neutral)
        s = M.sum()
        return M / s if s else M

    def expected_goals(self, home: str, away: str, neutral: bool = True) -> tuple[float, float]:
        M = self.score_matrix(home, away, neutral)
        g = np.arange(M.shape[0])
        return float((M.sum(axis=1) * g).sum()), float((M.sum(axis=0) * g).sum())

    def outcome_probs(self, home: str, away: str, neutral: bool = True) -> tuple[float, float, float]:
        M = self.score_matrix(home, away, neutral)
        return float(np.tril(M, -1).sum()), float(np.trace(M)), float(np.triu(M, 1).sum())


def build_ensemble(matches: pd.DataFrame, w: float = 0.5) -> EnsembleGoalModel:
    dc = fit_dixon_coles(matches)
    ml = MLGoalModel(train(build_features(matches)), current_state(matches), all_teams())
    return EnsembleGoalModel(dc, ml, w)


def _scores(probs: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Devolve (acurácia, log-loss, brier multiclasse)."""
    p = np.clip(probs, 1e-12, 1)
    acc = float((p.argmax(1) == y).mean())
    ll = float(-np.mean(np.log(p[np.arange(len(y)), y])))
    onehot = np.zeros_like(p); onehot[np.arange(len(y)), y] = 1
    brier = float(np.mean(((p - onehot) ** 2).sum(1)))
    return acc, ll, brier


def evaluate_engines(cutoff: str = "2024-01-01", dc_rho: float = -0.05) -> pd.DataFrame:
    """Treina antes do cutoff e testa depois. Compara Dixon, ML e blends por
    acurácia, log-loss e Brier (V/E/D). Tudo OUT-OF-TIME (sem ver o teste)."""
    from .data import load_matches
    matches = load_matches()
    feats = build_features(matches)
    train_df = feats[feats["date"] < cutoff]
    test_df = feats[feats["date"] >= cutoff].reset_index(drop=True)

    dc = fit_dixon_coles(matches[matches["date"] < cutoff])
    ml = train(train_df, rho=dc_rho)

    # probabilidades V/E/D no teste
    dc_p = np.array([dc.outcome_probs(r.home_team, r.away_team, neutral=bool(r.neutral))
                     for r in test_df.itertuples(index=False)])
    lam, mu = ml.expected_goals(test_df)
    ml_p = np.array([_result_probs_from_goals(l, m, dc_rho) for l, m in zip(lam, mu)])
    y = test_df["y_result"].to_numpy()

    rows = []
    for w in [1.0, 0.75, 0.6, 0.5, 0.4, 0.25, 0.0]:
        blend = w * dc_p + (1 - w) * ml_p
        acc, ll, br = _scores(blend, y)
        label = ("Dixon-Coles" if w == 1.0 else "ML" if w == 0.0 else f"Ensemble w={w:g}")
        rows.append({"motor": label, "w_dixon": w, "acuracia": round(acc, 4),
                     "log_loss": round(ll, 4), "brier": round(br, 4)})
    return pd.DataFrame(rows).sort_values("log_loss").reset_index(drop=True)


if __name__ == "__main__":
    print("Avaliação OUT-OF-TIME (treino <2024, teste 2024+) — V/E/D:\n")
    df = evaluate_engines()
    print(df.to_string(index=False))
    best = df.iloc[0]
    print(f"\nMelhor por log-loss: {best['motor']} (log-loss {best['log_loss']}, brier {best['brier']})")
