"""
Pipeline completo: dados -> Elo -> (Dixon-Coles | ML com jogadores) -> Monte Carlo.

Motor recomendado: "ensemble" (mistura Dixon-Coles + ML com features de jogadores).
Dixon-Coles é mais rápido para experimentos, mas ensemble costuma dar melhores resultados.

Uso:
    python -m wc2026.run                           # usa ensemble (padrão recomendado)
    python -m wc2026.run --engine dixon            # motor clássico Dixon-Coles
    python -m wc2026.run --engine ml --sims 50000  # só ML + muitas simulações
    python -m wc2026.run --update --live           # atualiza dados + aplica ajuste ao vivo
"""
from __future__ import annotations

import argparse
import time

from .data import load_matches, load_played_wc2026, update_csv
from .elo import compute_elo
from .goal_model import fit_dixon_coles
from .groups import all_teams
from .shootout import calibrate, load_shootouts
from .simulate import simulate


def _show_path(team: str) -> None:
    """Imprime o caminho fixo de uma seleção no mata-mata (como 1º e como 2º do grupo)."""
    from .bracket import format_path
    from .groups import GROUPS
    grp = next((g for g, ts in GROUPS.items() if team in ts), None)
    if grp is None:
        from .groups import all_teams
        print(f"Selecao '{team}' nao esta na Copa 2026. Opcoes: {', '.join(sorted(all_teams()))}")
        return
    print(f"(Brackets oficiais da FIFA — {team} esta no Grupo {grp})\n")
    print(format_path(team, f"1{grp}"))
    print()
    print(format_path(team, f"2{grp}"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=10000,
                    help="número de simulações Monte Carlo (mais = mais estável, mas mais lento)")
    ap.add_argument("--engine", choices=["dixon", "ml", "ensemble"], default="ensemble",
                    help="motor de gols: dixon (clássico), ml (boosting + jogadores) ou ensemble (padrão recomendado)")
    ap.add_argument("--update", action="store_true",
                    help="atualiza a base de resultados históricos antes de rodar")
    ap.add_argument("--live", action="store_true",
                    help="aplica ajuste de forma ao vivo usando finalizações da Copa 2026 (api_cache/). "
                         "Requer ter rodado thesportsdb --pull antes.")
    ap.add_argument("--no-calibration", action="store_true",
                    help="desliga a calibração pós-modelo de probabilidades V/E/D")
    ap.add_argument("--path", metavar="SELECAO",
                    help="mostra apenas o caminho fixo da seleção no mata-mata oficial (1º e 2º do grupo) e sai")
    args = ap.parse_args()

    if args.path:
        _show_path(args.path)
        return

    if args.update:
        update_csv()

    t0 = time.time()
    print("1/5  Carregando historico...")
    matches = load_matches()
    played = load_played_wc2026()
    print(f"     {len(matches):,} jogos | {len(played)} jogos da Copa 2026 ja realizados")

    print("2/5  Ratings Elo + calibracao de penaltis...")
    elo = compute_elo(matches)
    beta = calibrate(load_shootouts(), elo)

    if args.engine == "ml":
        print("3/5  Treinando modelo de gols (boosting Poisson + features de jogador)...")
        from .features import build_features, current_state
        from .ml_model import train, MLGoalModel
        feats = build_features(matches)
        goal_ml = train(feats)
        state = current_state(matches)
        model = MLGoalModel(goal_ml, state, all_teams())
        w = 0.0  # n/a
    elif args.engine == "ensemble":
        print("3/5  Ensemble (Dixon-Coles + ML)...")
        from .ensemble import build_ensemble, get_optimal_ensemble_weight
        w = 0.55
        try:
            w = get_optimal_ensemble_weight()  # peso dinâmico via validação (Point 4)
        except Exception:
            pass
        model = build_ensemble(matches, w=w)
    else:
        print("3/5  Ajustando modelo de gols Dixon-Coles...")
        model = fit_dixon_coles(matches)
        w = 1.0  # n/a

    if args.live:
        from .live_form import (parse_cache, build_team_adjustments,
                                AdjustedGoalModel, gather_live_stats)
        stats = gather_live_stats()
        if stats.empty:
            print("     [--live] sem dados granulares (api_cache/ vazio); "
                  "seguindo sem ajuste ao vivo.")
        else:
            adj = build_team_adjustments(model, stats)
            model = AdjustedGoalModel(model, adj)
            n_teams = len(adj.attack)
            print(f"     [--live] ajuste aplicado a {n_teams} selecoes "
                  f"({stats['fixture'].nunique()} jogos com stats).")

    if not args.no_calibration:
        print("     Calibrando probabilidades V/E/D em validação temporal...")
        from .outcome_calibration import calibrate_model
        cal_w = w if args.engine == "ensemble" else 0.5
        model = calibrate_model(model, matches, engine=args.engine, w=cal_w)

    live_str = " + live adjustment" if args.live else ""
    cal_str = "" if args.no_calibration else " + calibração V/E/D"
    print(f"     Config: engine={args.engine}{live_str}{cal_str}, sims={args.sims:,}")
    print(f"4/5  Simulando o torneio {args.sims:,}x (Monte Carlo)...")
    table = simulate(model, elo, played, n_sims=args.sims, shootout_beta=beta)

    print("5/5  Pronto.\n")
    cal = "calibrado" if not args.no_calibration else "sem calibração"
    live = " + live-form" if args.live else ""
    print(f"=== PROBABILIDADE DE CAMPEÃO — Copa 2026  "
          f"[motor: {args.engine}{live}, {cal}]  ({args.sims:,} simulações) ===\n")
    top = table.head(15)
    print(f"{'#':>2}  {'Selecao':<24}{'Campeao':>9}{'Final':>8}{'Semi':>8}{'Avanca':>9}{'Elo':>8}")
    for i, (_, r) in enumerate(top.iterrows(), 1):
        print(f"{i:>2}  {r['team']:<24}{r['champion_%']:>8.1f}%{r['finalist_%']:>7.1f}%"
              f"{r['semifinal_%']:>7.1f}%{r['advance_%']:>8.1f}%{r['elo']:>8.0f}")
    print(f"\nConcluido em {time.time() - t0:.1f}s.")


if __name__ == "__main__":
    main()
