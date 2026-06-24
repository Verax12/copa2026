"""
Teste de predição contra os jogos reais já disputados da Copa 2026.

O teste treina o modelo apenas com dados anteriores ao início da Copa, prevê os
jogos da Copa já disponíveis na base local e valida contra os resultados reais.

Uso:
    python -m wc2026.prediction_test
    python -m wc2026.prediction_test --json
"""
from __future__ import annotations

import argparse
import json

from .track import CUP_START, backtest


def _run_case(name: str, engine: str, calibrated: bool) -> dict:
    res = backtest(cutoff=CUP_START, engine=engine, calibrated=calibrated)
    s = res["summary"]
    return {
        "name": name,
        "engine": engine,
        "calibrated": calibrated,
        "games": s["n"],
        "wdl_correct": s["probCorrect"],
        "wdl_accuracy": s["probAcc"],
        "score_mode_correct": s["winnerCorrect"],
        "score_mode_accuracy": s["winnerAcc"],
        "exact_score_correct": s["exactCorrect"],
        "brier": s["brier"],
        "logloss": s["logloss"],
        "elo_baseline_accuracy": s["baselineEloAcc"],
    }


def run_prediction_test(include_comparisons: bool = True) -> list[dict]:
    rows = [_run_case("Sistema atual", "ensemble", True)]
    if include_comparisons:
        rows.extend([
            _run_case("Ensemble sem calibração", "ensemble", False),
            _run_case("Dixon-Coles sem calibração", "dixon", False),
        ])
    return rows


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="imprime saída JSON")
    ap.add_argument("--current-only", action="store_true",
                    help="roda só o sistema atual, sem comparativos")
    args = ap.parse_args()

    rows = run_prediction_test(include_comparisons=not args.current_only)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    print(f"Teste de predição pré-Copa -> resultados reais atuais (corte: {CUP_START})\n")
    print(f"{'Modelo':<28}{'V/E/D':>12}{'Modo placar':>14}{'Exato':>10}{'Brier':>9}{'Log-loss':>10}")
    for r in rows:
        wdl = f"{r['wdl_correct']}/{r['games']} ({_pct(r['wdl_accuracy'])})"
        mode = f"{r['score_mode_correct']}/{r['games']} ({_pct(r['score_mode_accuracy'])})"
        exact = f"{r['exact_score_correct']}/{r['games']}"
        print(f"{r['name']:<28}{wdl:>12}{mode:>14}{exact:>10}"
              f"{r['brier']:>9.3f}{r['logloss']:>10.3f}")

    current = rows[0]
    print("\nRating atual do sistema:")
    print(f"  Acerto V/E/D: {current['wdl_correct']}/{current['games']} "
          f"({_pct(current['wdl_accuracy'])})")
    print(f"  Brier: {current['brier']:.3f} | Log-loss: {current['logloss']:.3f}")
    print(f"  Baseline só Elo: {_pct(current['elo_baseline_accuracy'])}")


if __name__ == "__main__":
    main()
