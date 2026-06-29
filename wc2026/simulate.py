"""
Simulação de Monte Carlo do torneio inteiro.

Para cada uma das N simulações:
  1) Joga os 6 confrontos de cada grupo. Jogos JÁ realizados usam o placar real;
     o resto é amostrado do modelo Dixon-Coles.
  2) Classifica: 1º e 2º de cada grupo + os 8 melhores 3º colocados -> 32 times.
  3) Mata-mata até a final (placar amostrado; empate decidido nos pênaltis,
     com leve vantagem para o time de maior Elo).
Ao fim, agrega em quantas simulações cada seleção foi campeã, finalista, etc.

Dinâmicas (Point 5 do roadmap):
  - Fadiga melhorada: baseada em #jogos + dias de descanso (usando datas dos jogos).
  - Cartões vermelhos: probabilidade simples por time por jogo, reduzindo gols se ocorrer.
  - Momentum: forma recente (resultados simulados) afeta performance no próximo jogo.
  Configurável via dict `dynamics` (fatigue, red_cards, momentum, fatores).
  Jogos reais não sofrem ajuste dinâmico (usam placar fixo), mas contam para contagem/última data.
  Simula grupos em ordem cronológica aproximada (matchdays) para propagar estado corretamente.
  KO também usa dinâmicas com datas de rodadas.

NOTA sobre mando: jogos da Copa são tratados como neutros, exceto quando uma das
três seleções anfitriãs (México, EUA ou Canadá) enfrenta uma não-anfitriã. Nesse
caso aplicamos a vantagem de mando do motor de gols ao anfitrião, sem tentar
inferir torcida para outras seleções.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from .elo import BASE_RATING
from .goal_model import DixonColes
from .groups import GROUPS
from .bracket import resolve_r32, R16_PAIRS, QF_PAIRS, SF_PAIRS
from .venue import score_matrix_with_venue


def _played_lookup(played: pd.DataFrame) -> dict[tuple[str, str], tuple[int, int]]:
    d = {}
    for r in played.itertuples(index=False):
        d[(r.home_team, r.away_team)] = (r.home_score, r.away_score)
    return d


def _precompute(model: DixonColes, teams: list[str]) -> dict[tuple[str, str], np.ndarray]:
    """Cumulativo do flatten da matriz de placar p/ cada par (amostragem rápida)."""
    cache = {}
    for h in teams:
        for a in teams:
            if h == a:
                continue
            m = score_matrix_with_venue(model, h, a)
            cache[(h, a)] = (np.cumsum(m.ravel()), m.shape[1])
    return cache


def _sample(cache, key, rng) -> tuple[int, int]:
    cum, ncols = cache[key]
    k = int(np.searchsorted(cum, rng.random() * cum[-1]))
    return k // ncols, k % ncols


def simulate(model, elo: dict[str, float], played: pd.DataFrame,
             n_sims: int = 10000, seed: int = 42, shootout_beta: float = 0.0011,
             dynamics: dict | None = None,
             return_ci: bool = False) -> pd.DataFrame:
    """Run full tournament MC sims. dynamics dict enables/configs in-sim dynamics (KO modeling Point).
    return_ci adds simple bootstrap/ MC error intervals (normal approx) on phase %s.
    Fatigue uses real rest days from dates (played + simulated schedule); more sophisticated
    accumulation + short rest; red cards reduce effective goals; momentum from recent wins
    scales expected goals in sims. Configurable.
    """
    if dynamics is None:
        dynamics = {}
    # defaults: conservative values for realism without over-effect
    enable_fatigue = dynamics.get("fatigue", True)
    enable_reds = dynamics.get("red_cards", True)
    enable_momentum = dynamics.get("momentum", True)
    fatigue_per_game = float(dynamics.get("fatigue_per_game", 0.035))
    max_fatigue = float(dynamics.get("max_fatigue", 0.15))
    rest_penalty = float(dynamics.get("rest_penalty", 0.025))  # extra fatigue for <4 rest days
    red_prob = float(dynamics.get("red_card_prob", 0.022))
    red_impact = float(dynamics.get("red_impact", 0.22))
    mom_factor = float(dynamics.get("momentum_factor", 0.035))

    rng = np.random.default_rng(seed)
    teams = [t for g in GROUPS.values() for t in g]
    cache = _precompute(model, teams)
    real = _played_lookup(played)
    elo_of = {t: elo.get(t, BASE_RATING) for t in teams}

    champ = defaultdict(int)
    final = defaultdict(int)
    semi = defaultdict(int)
    advance = defaultdict(int)  # passou da fase de grupos
    pos_count = defaultdict(lambda: [0, 0, 0, 0])  # nº de vezes em 1º/2º/3º/4º do grupo
    pts_sum = defaultdict(float)                    # soma de pontos no grupo (p/ média)

    # Precompute initial last dates + momentum streak from real played (chronological)
    last_real: dict[str, pd.Timestamp] = {}
    recent_pts: dict[str, list[int]] = defaultdict(list)
    if not played.empty:
        for r in played.sort_values("date").itertuples(index=False):
            d = pd.Timestamp(r.date)
            ht, at = r.home_team, r.away_team
            hs, as_ = int(r.home_score), int(r.away_score)
            last_real[ht] = d
            last_real[at] = d
            if hs > as_:
                recent_pts[ht].append(3)
                recent_pts[at].append(0)
            elif as_ > hs:
                recent_pts[ht].append(0)
                recent_pts[at].append(3)
            else:
                recent_pts[ht].append(1)
                recent_pts[at].append(1)
    init_momentum: dict[str, float] = {}
    for t in teams:
        pts = recent_pts.get(t, [])[-3:]
        # net form: positive good (wins contribute +)
        net = sum((p - 1) for p in pts) / 2.0
        init_momentum[t] = float(np.clip(net, -2.5, 2.5))

    # matchday dates (approx, based on 2026 schedule; groups staggered but sufficient)
    MD_DATES: list[pd.Timestamp] = [
        pd.Timestamp("2026-06-12"),
        pd.Timestamp("2026-06-19"),
        pd.Timestamp("2026-06-25"),
    ]
    # partition of pairs so each "md" each team plays exactly once; process in chrono order
    MD_PAIRS: list[list[tuple[int, int]]] = [
        [(0, 1), (2, 3)],
        [(0, 2), (1, 3)],
        [(0, 3), (1, 2)],
    ]

    # KO round dates for rest/fatigue between rounds
    KO_DATES: dict[str, pd.Timestamp] = {
        "r32": pd.Timestamp("2026-06-30"),
        "r16": pd.Timestamp("2026-07-05"),
        "qf": pd.Timestamp("2026-07-10"),
        "sf": pd.Timestamp("2026-07-14"),
        "final": pd.Timestamp("2026-07-19"),
    }

    def _match_score(h: str, a: str, match_date: pd.Timestamp | None = None) -> tuple[int, int]:
        """Sample (or lookup real) score, applying dynamics if enabled. Updates state only for simulated matches.
        match_date used for rest days calc (fatigue). Always counts games for later fatigue even on reals.
        """
        if match_date is None:
            match_date = pd.Timestamp("2026-06-20")

        if (h, a) in real:
            hg, ag = real[(h, a)]
            games_played[h] += 1
            games_played[a] += 1
            last_date[h] = max(last_date.get(h, match_date), match_date)
            last_date[a] = max(last_date.get(a, match_date), match_date)
            return hg, ag
        if (a, h) in real:  # real with reversed home/away
            ag, hg = real[(a, h)]
            games_played[h] += 1
            games_played[a] += 1
            last_date[h] = max(last_date.get(h, match_date), match_date)
            last_date[a] = max(last_date.get(a, match_date), match_date)
            return hg, ag

        # --- simulated match: apply dynamics ---
        # rest days
        prev_h = last_date.get(h, match_date - pd.Timedelta(days=7))
        prev_a = last_date.get(a, match_date - pd.Timedelta(days=7))
        rest_h = max(0, (match_date - prev_h).days)
        rest_a = max(0, (match_date - prev_a).days)

        fat_h = 0.0
        fat_a = 0.0
        if enable_fatigue:
            gp_h = games_played.get(h, 0)
            gp_a = games_played.get(a, 0)
            fat_base_h = min(max_fatigue, fatigue_per_game * max(0, gp_h - 2))
            fat_base_a = min(max_fatigue, fatigue_per_game * max(0, gp_a - 2))
            short_h = max(0, (4 - rest_h)) * rest_penalty
            short_a = max(0, (4 - rest_a)) * rest_penalty
            fat_h = min(max_fatigue, fat_base_h + short_h)
            fat_a = min(max_fatigue, fat_base_a + short_a)

        mom_h = 0.0
        mom_a = 0.0
        if enable_momentum:
            m_h = momentum.get(h, 0.0)
            m_a = momentum.get(a, 0.0)
            mom_h = float(np.clip(m_h * mom_factor, -0.10, 0.10))
            mom_a = float(np.clip(m_a * mom_factor, -0.10, 0.10))

        adj_h = max(0.55, 1.0 - fat_h + mom_h)
        adj_a = max(0.55, 1.0 - fat_a + mom_a)

        if hasattr(model, "sample_score"):
            g1, g2 = model.sample_score(h, a, rng, neutral=True)
            g1 = max(0, int(g1 * adj_h))
            g2 = max(0, int(g2 * adj_a))
        else:
            g1, g2 = _sample(cache, (h, a), rng)
            g1 = max(0, int(g1 * adj_h))
            g2 = max(0, int(g2 * adj_a))

        # red cards (independent per team)
        if enable_reds:
            if rng.random() < red_prob:
                g1 = max(0, int(g1 * (1.0 - red_impact)))
            if rng.random() < red_prob:
                g2 = max(0, int(g2 * (1.0 - red_impact)))

        # commit state for this match
        games_played[h] += 1
        games_played[a] += 1
        last_date[h] = match_date
        last_date[a] = match_date

        # momentum update from *this* outcome (sim only)
        if enable_momentum:
            if g1 > g2:
                momentum[h] = min(3.0, momentum.get(h, 0.0) + 1.0)
                momentum[a] = max(-3.0, momentum.get(a, 0.0) - 1.0)
            elif g2 > g1:
                momentum[h] = max(-3.0, momentum.get(h, 0.0) - 1.0)
                momentum[a] = min(3.0, momentum.get(a, 0.0) + 1.0)
            else:
                momentum[h] = momentum.get(h, 0.0) * 0.6
                momentum[a] = momentum.get(a, 0.0) * 0.6

        return g1, g2

    # legacy alias for minimal diff in group code
    def play(h: str, a: str, match_date: pd.Timestamp | None = None) -> tuple[int, int]:
        return _match_score(h, a, match_date)

    def knockout(h: str, a: str, match_date: pd.Timestamp | None = None) -> str:
        """Knockout match with dynamics (samples score via _match_score then decides)."""
        hg, ag = _match_score(h, a, match_date)
        if hg > ag:
            return h
        if ag > hg:
            return a
        # pênaltis: probabilidade calibrada no histórico real (quase 50/50)
        pa = 1.0 / (1.0 + np.exp(-shootout_beta * (elo_of[h] - elo_of[a])))
        return h if rng.random() < pa else a

    def _prop_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
        """Simple uncertainty interval (MC sampling error) for %; approx bootstrap normal."""
        if n <= 0:
            return 0.0, 0.0
        p = k / float(n)
        se = (p * (1.0 - p) / n) ** 0.5
        lo = max(0.0, p - z * se)
        hi = min(1.0, p + z * se)
        return round(100 * lo, 2), round(100 * hi, 2)

    for _ in range(n_sims):
        # per-simulation state for dynamics (Point 5)
        games_played: dict[str, int] = defaultdict(int)
        last_date: dict[str, pd.Timestamp] = {t: last_real.get(t, pd.Timestamp("2026-06-01")) for t in teams}
        momentum: dict[str, float] = {t: init_momentum.get(t, 0.0) for t in teams}

        thirds = []                 # (pts, sg, gf, gname) dos terceiros
        qualified = {}              # rótulo -> time (ex.: "1A", "2C")
        third_by_group = {}         # gname -> time que terminou em 3º

        # init pts/gf/ga per group (accumulate across matchdays)
        group_pts: dict[str, dict[str, int]] = {}
        group_gf: dict[str, dict[str, int]] = {}
        group_ga: dict[str, dict[str, int]] = {}
        for gname, gteams in GROUPS.items():
            group_pts[gname] = {t: 0 for t in gteams}
            group_gf[gname] = {t: 0 for t in gteams}
            group_ga[gname] = {t: 0 for t in gteams}

        # group stage in matchday order (chrono) for correct rest/momentum/fatigue
        for md_idx, md_pairs in enumerate(MD_PAIRS):
            md_date = MD_DATES[md_idx]
            for gname, gteams in GROUPS.items():
                pts = group_pts[gname]
                gf = group_gf[gname]
                ga = group_ga[gname]
                for i, j in md_pairs:
                    h, a = gteams[i], gteams[j]
                    hg, ag = play(h, a, md_date)
                    gf[h] += hg; ga[h] += ag; gf[a] += ag; ga[a] += hg
                    if hg > ag:
                        pts[h] += 3
                    elif ag > hg:
                        pts[a] += 3
                    else:
                        pts[h] += 1; pts[a] += 1

        # classify after full group stage (all 3 mds accumulated)
        for gname, gteams in GROUPS.items():
            pts = group_pts[gname]
            gf = group_gf[gname]
            ga = group_ga[gname]
            order = sorted(gteams, key=lambda t: (pts[t], gf[t] - ga[t], gf[t]),
                           reverse=True)
            qualified[f"1{gname}"] = order[0]
            qualified[f"2{gname}"] = order[1]
            t3 = order[2]
            third_by_group[gname] = t3
            thirds.append((pts[t3], gf[t3] - ga[t3], gf[t3], gname))
            for rank, t in enumerate(order):
                pos_count[t][rank] += 1
                pts_sum[t] += pts[t]
            for t in order[:2]:
                advance[t] += 1

        # 8 melhores terceiros (critérios FIFA: pts, saldo, gols pró)
        thirds.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
        best_third_groups = [t[3] for t in thirds[:8]]
        for gname in best_third_groups:
            advance[third_by_group[gname]] += 1

        # mata-mata: bracket FIXO oficial da FIFA (jogos 73-104)
        # apply dynamics + dates for rest/momentum between rounds
        r32 = resolve_r32(qualified, third_by_group, best_third_groups)
        w32 = [knockout(h, a, KO_DATES["r32"]) for h, a in r32]
        w16 = [knockout(w32[i], w32[j], KO_DATES["r16"]) for i, j in R16_PAIRS]
        w8 = [knockout(w16[i], w16[j], KO_DATES["qf"]) for i, j in QF_PAIRS]
        for t in w8:
            semi[t] += 1
        finalists = [knockout(w8[i], w8[j], KO_DATES["sf"]) for i, j in SF_PAIRS]
        for t in finalists:
            final[t] += 1
        champ[knockout(finalists[0], finalists[1], KO_DATES["final"])] += 1

    rows = []
    for t in teams:
        pc = pos_count[t]
        ch_k = champ[t]
        fi_k = final[t]
        se_k = semi[t]
        ad_k = advance[t]
        row = {
            "team": t,
            "champion_%": 100 * ch_k / n_sims,
            "finalist_%": 100 * fi_k / n_sims,
            "semifinal_%": 100 * se_k / n_sims,
            "advance_%": 100 * ad_k / n_sims,
            "p_first_%": 100 * pc[0] / n_sims,
            "p_second_%": 100 * pc[1] / n_sims,
            "p_third_%": 100 * pc[2] / n_sims,
            "p_fourth_%": 100 * pc[3] / n_sims,
            "exp_pts": pts_sum[t] / n_sims,
            "elo": elo_of[t],
        }
        if return_ci:
            ch_lo, ch_hi = _prop_ci(ch_k, n_sims)
            fi_lo, fi_hi = _prop_ci(fi_k, n_sims)
            se_lo, se_hi = _prop_ci(se_k, n_sims)
            ad_lo, ad_hi = _prop_ci(ad_k, n_sims)
            row.update({
                "champion_ci_low": ch_lo, "champion_ci_high": ch_hi,
                "finalist_ci_low": fi_lo, "finalist_ci_high": fi_hi,
                "semifinal_ci_low": se_lo, "semifinal_ci_high": se_hi,
                "advance_ci_low": ad_lo, "advance_ci_high": ad_hi,
            })
        rows.append(row)
    return (pd.DataFrame(rows)
            .sort_values("champion_%", ascending=False)
            .reset_index(drop=True))
