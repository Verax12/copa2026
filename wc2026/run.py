"""
Pipeline completo: dados -> Elo -> (Dixon-Coles | ML com jogadores) -> Monte Carlo.

Uso:
    python -m wc2026.run                      # motor Dixon-Coles, 10k simulacoes
    python -m wc2026.run --engine ml          # motor de ML (boosting + jogadores)
    python -m wc2026.run --sims 50000          # mais simulacoes = mais estavel
    python -m wc2026.run --update              # rebaixa a base antes de rodar
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
    ap.add_argument("--sims", type=int, default=10000)
    ap.add_argument("--engine", choices=["dixon", "ml", "ensemble"], default="dixon")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--live", action="store_true",
                    help="aplica o ajuste de forma ao vivo (dados granulares da "
                         "API-Football em api_cache/); ignora se o cache estiver vazio")
    ap.add_argument("--path", metavar="SELECAO",
                    help="mostra o caminho fixo da seleção no mata-mata (1º e 2º do "
                         "grupo) segundo o bracket oficial, e sai")
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
    elif args.engine == "ensemble":
        print("3/5  Ensemble (Dixon-Coles + ML)...")
        from .ensemble import build_ensemble
        model = build_ensemble(matches, w=0.5)
    else:
        print("3/5  Ajustando modelo de gols Dixon-Coles...")
        model = fit_dixon_coles(matches)

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

    print(f"4/5  Simulando o torneio {args.sims:,}x (Monte Carlo)...")
    table = simulate(model, elo, played, n_sims=args.sims, shootout_beta=beta)

    print("5/5  Pronto.\n")
    print(f"=== PROBABILIDADE DE CAMPEAO -- Copa 2026  "
          f"[motor: {args.engine}]  ({args.sims:,} simulacoes) ===\n")
    top = table.head(15)
    print(f"{'#':>2}  {'Selecao':<24}{'Campeao':>9}{'Final':>8}{'Semi':>8}{'Avanca':>9}{'Elo':>8}")
    for i, (_, r) in enumerate(top.iterrows(), 1):
        print(f"{i:>2}  {r['team']:<24}{r['champion_%']:>8.1f}%{r['finalist_%']:>7.1f}%"
              f"{r['semifinal_%']:>7.1f}%{r['advance_%']:>8.1f}%{r['elo']:>8.0f}")
    print(f"\nConcluido em {time.time() - t0:.1f}s.")


if __name__ == "__main__":
    main()
