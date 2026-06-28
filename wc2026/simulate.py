"""
Simulação de Monte Carlo do torneio inteiro.

Para cada uma das N simulações:
  1) Joga os 6 confrontos de cada grupo. Jogos JÁ realizados usam o placar real;
     o resto é amostrado do modelo Dixon-Coles.
  2) Classifica: 1º e 2º de cada grupo + os 8 melhores 3º colocados -> 32 times.
  3) Mata-mata até a final (placar amostrado; empate decidido nos pênaltis,
     com leve vantagem para o time de maior Elo).
Ao fim, agrega em quantas simulações cada seleção foi campeã, finalista, etc.

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
             n_sims: int = 10000, seed: int = 42, shootout_beta: float = 0.0011) -> pd.DataFrame:
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

    pairs = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]

    def play(h: str, a: str) -> tuple[int, int]:
        if (h, a) in real:
            return real[(h, a)]
        if (a, h) in real:                # confronto real com mando invertido
            ag, hg = real[(a, h)]
            return hg, ag
        if hasattr(model, 'sample_score'):
            # use model's sample which may include dispersion
            return model.sample_score(h, a, rng, neutral=True)
        return _sample(cache, (h, a), rng)

    def knockout(h: str, a: str) -> str:
        hg, ag = _sample(cache, (h, a), rng)
        if hg > ag:
            return h
        if ag > hg:
            return a
        # pênaltis: probabilidade calibrada no histórico real (quase 50/50)
        pa = 1.0 / (1.0 + np.exp(-shootout_beta * (elo_of[h] - elo_of[a])))
        return h if rng.random() < pa else a

    for _ in range(n_sims):
        thirds = []                 # (pts, sg, gf, gname) dos terceiros
        qualified = {}              # rótulo -> time (ex.: "1A", "2C")
        third_by_group = {}         # gname -> time que terminou em 3º

        for gname, gteams in GROUPS.items():
            pts = {t: 0 for t in gteams}
            gf = {t: 0 for t in gteams}
            ga = {t: 0 for t in gteams}
            for i, j in pairs:
                h, a = gteams[i], gteams[j]
                hg, ag = play(h, a)
                gf[h] += hg; ga[h] += ag; gf[a] += ag; ga[a] += hg
                if hg > ag:
                    pts[h] += 3
                elif ag > hg:
                    pts[a] += 3
                else:
                    pts[h] += 1; pts[a] += 1
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
        r32 = resolve_r32(qualified, third_by_group, best_third_groups)
        w32 = [knockout(h, a) for h, a in r32]                  # 16 vencedores (R32)
        w16 = [knockout(w32[i], w32[j]) for i, j in R16_PAIRS]  # 8 (oitavas)
        w8 = [knockout(w16[i], w16[j]) for i, j in QF_PAIRS]    # 4 = semifinalistas
        for t in w8:
            semi[t] += 1
        finalists = [knockout(w8[i], w8[j]) for i, j in SF_PAIRS]  # 2
        for t in finalists:
            final[t] += 1
        champ[knockout(finalists[0], finalists[1])] += 1

    rows = []
    for t in teams:
        pc = pos_count[t]
        rows.append({
            "team": t,
            "champion_%": 100 * champ[t] / n_sims,
            "finalist_%": 100 * final[t] / n_sims,
            "semifinal_%": 100 * semi[t] / n_sims,
            "advance_%": 100 * advance[t] / n_sims,
            "p_first_%": 100 * pc[0] / n_sims,
            "p_second_%": 100 * pc[1] / n_sims,
            "p_third_%": 100 * pc[2] / n_sims,
            "p_fourth_%": 100 * pc[3] / n_sims,
            "exp_pts": pts_sum[t] / n_sims,
            "elo": elo_of[t],
        })
    return (pd.DataFrame(rows)
            .sort_values("champion_%", ascending=False)
            .reset_index(drop=True))
