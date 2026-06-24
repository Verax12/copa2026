"""
Track record do modelo: backtest SEM vazamento dos jogos da Copa já disputados.

Treina o modelo de gols usando SÓ os dados de antes da Copa (corte em 11/06/2026)
e prevê os jogos da Copa com esse modelo "congelado". Como ele nunca viu nenhum
resultado da Copa, cada previsão é honestamente pré-jogo — e reproduzível (não
depende de termos salvo a previsão no momento certo). À medida que novos jogos
acontecem (entram via `data --update`), o track record se atualiza sozinho.

Métricas (sobre o resultado V/E/D, não sobre o placar exato — placar é loteria):
  - winner_acc : % de vezes que o resultado mais provável (V/E/D) se confirmou
  - brier      : erro quadrático das probabilidades (0 = perfeito; ~0.67 = chute)
  - logloss    : log-loss das probabilidades (quanto menor, melhor)
Compara contra dois baselines: chute uniforme (1/3) e o favorito por Elo.

Uso:  python -m wc2026.track
"""
from __future__ import annotations

import argparse

import numpy as np

from .data import load_matches, load_played_wc2026
from .elo import compute_elo, win_probabilities, HOME_ADVANTAGE, BASE_RATING
from .outcome_calibration import CalibratedGoalModel, fit_outcome_calibrator

CUP_START = "2026-06-11"


def _outcome(hs: int, a_s: int) -> int:
    return 0 if hs > a_s else (1 if hs == a_s else 2)


def _build_model(matches, engine: str = "ensemble", w: float = 0.5):
    if engine == "ensemble":
        from .ensemble import build_ensemble
        return build_ensemble(matches, w=w)
    if engine == "ml":
        from .features import build_features, current_state
        from .groups import all_teams
        from .ml_model import MLGoalModel, train
        return MLGoalModel(train(build_features(matches)), current_state(matches), all_teams())
    from .goal_model import fit_dixon_coles
    return fit_dixon_coles(matches)


def backtest(cutoff: str = CUP_START, engine: str = "ensemble",
             calibrated: bool = True, w: float = 0.5, calibration_alpha: float = 0.5) -> dict:
    matches = load_matches()
    played = load_played_wc2026()
    train = matches[matches["date"] < cutoff]

    model = _build_model(train, engine=engine, w=w)  # modelo "congelado" pré-Copa
    if calibrated:
        cal = fit_outcome_calibrator(matches, valid_until=cutoff, engine=engine, w=w)
        model = CalibratedGoalModel(model, cal, alpha=calibration_alpha)
    elo = compute_elo(train)                        # Elo só com dados pré-Copa (baseline)

    games = []
    n = win_ok = prob_ok = exact_ok = base_ok = 0
    brier = logloss = brier_unif = brier_elo = 0.0

    for r in played.itertuples(index=False):
        neutral = bool(r.neutral)
        ph, pd_, pa = model.outcome_probs(r.home_team, r.away_team, neutral=neutral)
        M = model.score_matrix(r.home_team, r.away_team, neutral=neutral)
        gi, gj = np.unravel_index(int(M.argmax()), M.shape)

        actual = _outcome(r.home_score, r.away_score)
        probs = [ph, pd_, pa]
        # "acerto do resultado" = resultado (V/E/D) do PLACAR PREVISTO (a moda exibida)
        # vs o real — coerente com o que o painel mostra ("prev. X-Y").
        pred = _outcome(int(gi), int(gj))
        prob_pred = int(np.argmax(probs))
        I = [0, 0, 0]; I[actual] = 1

        # baseline Elo (pela probabilidade, só como referência)
        eh = elo.get(r.home_team, BASE_RATING) + (0 if neutral else HOME_ADVANTAGE)
        ea = elo.get(r.away_team, BASE_RATING)
        eprobs = list(win_probabilities(eh, ea))
        base_pred = int(np.argmax(eprobs))

        n += 1
        win_ok += (pred == actual)
        prob_ok += (prob_pred == actual)
        base_ok += (base_pred == actual)
        exact_ok += (int(gi) == int(r.home_score) and int(gj) == int(r.away_score))
        brier += sum((probs[k] - I[k]) ** 2 for k in range(3))
        logloss += -np.log(max(probs[actual], 1e-12))
        brier_unif += sum((1/3 - I[k]) ** 2 for k in range(3))
        brier_elo += sum((eprobs[k] - I[k]) ** 2 for k in range(3))

        games.append({
            "date": str(r.date)[:10], "home": r.home_team, "away": r.away_team,
            "ph": round(float(ph), 3), "pd": round(float(pd_), 3), "pa": round(float(pa), 3),
            "predScore": [int(gi), int(gj)], "actual": [int(r.home_score), int(r.away_score)],
            "winnerHit": bool(pred == actual), "probHit": bool(prob_pred == actual),
            "predResult": int(prob_pred),
            "exactHit": bool(int(gi) == int(r.home_score) and int(gj) == int(r.away_score)),
        })

    summary = {
        "n": n,
        "winnerCorrect": int(win_ok),
        "winnerAcc": round(win_ok / n, 3) if n else 0.0,
        "probCorrect": int(prob_ok),
        "probAcc": round(prob_ok / n, 3) if n else 0.0,
        "exactCorrect": int(exact_ok),
        "brier": round(brier / n, 3) if n else 0.0,
        "logloss": round(logloss / n, 3) if n else 0.0,
        "baselineEloAcc": round(base_ok / n, 3) if n else 0.0,
        "brierUniform": round(brier_unif / n, 3) if n else 0.0,
        "brierElo": round(brier_elo / n, 3) if n else 0.0,
        "cutoff": cutoff,
        "engine": engine,
        "calibrated": bool(calibrated),
        "calibrationAlpha": float(calibration_alpha) if calibrated else 0.0,
    }
    return {"summary": summary, "games": games}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["dixon", "ml", "ensemble"], default="ensemble")
    ap.add_argument("--no-calibration", action="store_true")
    args = ap.parse_args()

    res = backtest(engine=args.engine, calibrated=not args.no_calibration)
    s = res["summary"]
    cal = "calibrado" if s["calibrated"] else "sem calibração"
    print(f"Backtest pré-Copa ({s['engine']}, {cal}; treino < {s['cutoff']}):\n")
    print(f"  Jogos avaliados:        {s['n']}")
    print(f"  Acerto do resultado:    {s['winnerCorrect']}/{s['n']} ({s['winnerAcc']:.0%})")
    print(f"  Acerto V/E/D (argmax):  {s['probCorrect']}/{s['n']} ({s['probAcc']:.0%})")
    print(f"     baseline (só Elo):   {s['baselineEloAcc']:.0%}")
    print(f"  Placar exato:           {s['exactCorrect']}/{s['n']}")
    print(f"  Brier:                  {s['brier']:.3f}  (chute={s['brierUniform']:.3f}, Elo={s['brierElo']:.3f}; menor=melhor)")
    print(f"  Log-loss:               {s['logloss']:.3f}")
    print("\nJogo a jogo:")
    for g in res["games"]:
        mark = "✓" if g["winnerHit"] else "✗"
        print(f"  {mark} {g['home']:>16} {g['actual'][0]}x{g['actual'][1]} {g['away']:<16}"
              f"  prev {g['predScore'][0]}-{g['predScore'][1]}  "
              f"(V {g['ph']:.0%} / E {g['pd']:.0%} / D {g['pa']:.0%})")
