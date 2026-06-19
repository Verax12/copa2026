"""
Exporta os dados REAIS do modelo para o dashboard web (web/wc_data.js).

Roda o pipeline (Elo + motor de gols + Monte Carlo) e grava um arquivo JS que
define `window.WC_DATA` com tudo que o frontend precisa, na estrutura estável:

  WC_DATA = {
    teams:      [{ id, en, pt, iso, strength, groupId }],
    groupLabels:["A".."L"],
    groups:     [{ id, label, teamIds, table:[{id,pos,pts,adv}] }],
    titleProb:  { id: % },  finalProb/semiProb/advProb idem,
    qualifierIds, seeds,
    bracketSpec:{ r32:[[a,b]x16], r16Pairs, qfPairs, sfPairs },
    lambdas:    [[ [lamA,lamB] ... 48] ... 48],   # gols esperados neutros por par
    venues:     [...],
    meta:       { engine, sims, live, generatedFrom }
  }

Uso:
    python -m wc2026.export_web                 # Dixon-Coles, 20k sims
    python -m wc2026.export_web --engine ml --live --sims 30000
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .data import load_matches, load_played_wc2026
from .elo import compute_elo
from .groups import GROUPS, all_teams
from .shootout import calibrate, load_shootouts
from .simulate import simulate
from . import bracket as B

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# nome PT + código ISO (flagcdn / flag-icons) para as 48 seleções reais da Copa 2026.
# gb-eng / gb-sct para Inglaterra / Escócia.
TEAM_META = {
    "Mexico": ("México", "mx"), "South Africa": ("África do Sul", "za"),
    "South Korea": ("Coreia do Sul", "kr"), "Czech Republic": ("Tchéquia", "cz"),
    "Canada": ("Canadá", "ca"), "Qatar": ("Catar", "qa"),
    "Switzerland": ("Suíça", "ch"), "Bosnia and Herzegovina": ("Bósnia e Herzegovina", "ba"),
    "Brazil": ("Brasil", "br"), "Morocco": ("Marrocos", "ma"),
    "Haiti": ("Haiti", "ht"), "Scotland": ("Escócia", "gb-sct"),
    "United States": ("Estados Unidos", "us"), "Paraguay": ("Paraguai", "py"),
    "Australia": ("Austrália", "au"), "Turkey": ("Turquia", "tr"),
    "Germany": ("Alemanha", "de"), "Curaçao": ("Curaçao", "cw"),
    "Ivory Coast": ("Costa do Marfim", "ci"), "Ecuador": ("Equador", "ec"),
    "Netherlands": ("Holanda", "nl"), "Japan": ("Japão", "jp"),
    "Tunisia": ("Tunísia", "tn"), "Sweden": ("Suécia", "se"),
    "Belgium": ("Bélgica", "be"), "Egypt": ("Egito", "eg"),
    "Iran": ("Irã", "ir"), "New Zealand": ("Nova Zelândia", "nz"),
    "Spain": ("Espanha", "es"), "Cape Verde": ("Cabo Verde", "cv"),
    "Saudi Arabia": ("Arábia Saudita", "sa"), "Uruguay": ("Uruguai", "uy"),
    "France": ("França", "fr"), "Senegal": ("Senegal", "sn"),
    "Norway": ("Noruega", "no"), "Iraq": ("Iraque", "iq"),
    "Argentina": ("Argentina", "ar"), "Algeria": ("Argélia", "dz"),
    "Austria": ("Áustria", "at"), "Jordan": ("Jordânia", "jo"),
    "Portugal": ("Portugal", "pt"), "Uzbekistan": ("Uzbequistão", "uz"),
    "Colombia": ("Colômbia", "co"), "DR Congo": ("RD Congo", "cd"),
    "England": ("Inglaterra", "gb-eng"), "Croatia": ("Croácia", "hr"),
    "Ghana": ("Gana", "gh"), "Panama": ("Panamá", "pa"),
}

# 16 sedes (estádios) — EUA/MEX/CAN. x/y em % para o mapa estilizado do design.
VENUES = [
    {"city": "Vancouver", "country": "CAN", "stadium": "BC Place", "x": 11, "y": 16},
    {"city": "Seattle", "country": "USA", "stadium": "Lumen Field", "x": 12, "y": 24},
    {"city": "San Francisco Bay", "country": "USA", "stadium": "Levi's Stadium", "x": 13, "y": 45},
    {"city": "Los Angeles", "country": "USA", "stadium": "SoFi Stadium", "x": 17, "y": 55},
    {"city": "Guadalajara", "country": "MEX", "stadium": "Estadio Akron", "x": 26, "y": 78},
    {"city": "Mexico City", "country": "MEX", "stadium": "Estadio Azteca", "x": 33, "y": 82},
    {"city": "Monterrey", "country": "MEX", "stadium": "Estadio BBVA", "x": 34, "y": 68},
    {"city": "Houston", "country": "USA", "stadium": "NRG Stadium", "x": 43, "y": 64},
    {"city": "Dallas", "country": "USA", "stadium": "AT&T Stadium", "x": 42, "y": 54},
    {"city": "Kansas City", "country": "USA", "stadium": "Arrowhead Stadium", "x": 48, "y": 44},
    {"city": "Atlanta", "country": "USA", "stadium": "Mercedes-Benz Stadium", "x": 62, "y": 56},
    {"city": "Miami", "country": "USA", "stadium": "Hard Rock Stadium", "x": 70, "y": 70},
    {"city": "Toronto", "country": "CAN", "stadium": "BMO Field", "x": 66, "y": 33},
    {"city": "Philadelphia", "country": "USA", "stadium": "Lincoln Financial Field", "x": 76, "y": 40},
    {"city": "New York / NJ", "country": "USA", "stadium": "MetLife Stadium", "x": 79, "y": 37},
    {"city": "Boston", "country": "USA", "stadium": "Gillette Stadium", "x": 83, "y": 33},
]


# microestatísticas por jogo que a fonte gratuita (TheSportsDB) fornece.
# (key no JSON, rótulo PT, rótulo EN)
STAT_LABELS = [
    ("Total Shots", "Finalizações", "Total shots"),
    ("Shots on Goal", "No alvo", "On target"),
    ("Shots off Goal", "Para fora", "Off target"),
    ("Blocked Shots", "Bloqueadas", "Blocked"),
    ("Shots insidebox", "Dentro da área", "Inside box"),
]


def build_match_stats(idx: dict) -> list[dict]:
    """Lê api_cache/tsdb_stats_*.json e devolve as microestatísticas por jogo,
    mapeadas para os ids dos times. Só inclui o que a fonte tem (finalizações)."""
    import glob
    import json as J
    from .thesportsdb import CACHE, _to_float
    from .live_form import normalize_team

    ev_fp = CACHE / "tsdb_events.json"
    if not ev_fp.exists():
        return []
    events = {e["idEvent"]: e for e in (J.loads(ev_fp.read_text()).get("events") or [])}

    out = []
    for fp in sorted(glob.glob(str(CACHE / "tsdb_stats_*.json"))):
        eid = Path(fp).stem.replace("tsdb_stats_", "")
        st = J.loads(Path(fp).read_text()).get("eventstats")
        ev = events.get(eid)
        if not st or not ev:
            continue
        h = normalize_team(ev["strHomeTeam"])
        a = normalize_team(ev["strAwayTeam"])
        if h not in idx or a not in idx:
            continue
        smap = {s.get("strStat"): s for s in st}
        stats = []
        for key, pt, en in STAT_LABELS:
            if key in smap:
                stats.append({"pt": pt, "en": en,
                              "home": _to_float(smap[key].get("intHome")),
                              "away": _to_float(smap[key].get("intAway"))})
        if stats:
            out.append({"h": idx[h], "a": idx[a], "stats": stats, "src": "TheSportsDB"})

    # Flashscore (local, mais rico: posse/escanteios/cartões) tem prioridade por jogo
    by_pair = {frozenset((r["h"], r["a"])): r for r in out}
    try:
        from . import flashscore
        for r in flashscore.match_stats_rows(idx):
            by_pair[frozenset((r["h"], r["a"]))] = r   # sobrepõe o TheSportsDB
    except Exception:
        pass
    return list(by_pair.values())


# openfootball 'ground' (cidade) -> (cidade exibida, estádio)
GROUND_TO_STADIUM = {
    "Atlanta": ("Atlanta", "Mercedes-Benz Stadium"),
    "Boston (Foxborough)": ("Boston", "Gillette Stadium"),
    "Dallas (Arlington)": ("Dallas", "AT&T Stadium"),
    "Guadalajara (Zapopan)": ("Guadalajara", "Estadio Akron"),
    "Houston": ("Houston", "NRG Stadium"),
    "Kansas City": ("Kansas City", "Arrowhead Stadium"),
    "Los Angeles (Inglewood)": ("Los Angeles", "SoFi Stadium"),
    "Mexico City": ("Cidade do México", "Estadio Azteca"),
    "Miami (Miami Gardens)": ("Miami", "Hard Rock Stadium"),
    "Monterrey (Guadalupe)": ("Monterrey", "Estadio BBVA"),
    "New York/New Jersey (East Rutherford)": ("Nova York / NJ", "MetLife Stadium"),
    "Philadelphia": ("Filadélfia", "Lincoln Financial Field"),
    "San Francisco Bay Area (Santa Clara)": ("São Francisco", "Levi's Stadium"),
    "Seattle": ("Seattle", "Lumen Field"),
    "Toronto": ("Toronto", "BMO Field"),
    "Vancouver": ("Vancouver", "BC Place"),
}


def _parse_kickoff(s: str) -> dict:
    """'13:00 UTC-6' -> hora local + conversão para Brasília (UTC-3)."""
    out = {"local": "", "offset": "", "br": "", "brShift": 0}
    if not s:
        return out
    parts = s.split()
    out["local"] = parts[0]
    if len(parts) > 1:
        out["offset"] = parts[1]
    try:
        h, mi = map(int, parts[0].split(":"))
        offnum = int(parts[1].replace("UTC", "")) if len(parts) > 1 else 0
        total = h + (-offnum - 3)          # Brasília = local - offset - 3
        shift = 0
        while total >= 24:
            total -= 24; shift += 1
        while total < 0:
            total += 24; shift -= 1
        out["br"] = f"{total:02d}:{mi:02d}"
        out["brShift"] = shift
    except Exception:
        pass
    return out


def build_calendar(idx: dict, model, played, track_record: dict) -> list[dict]:
    """Calendário da fase de grupos (openfootball) + previsão de cada jogo.
    Futuro: previsão do modelo atual. Disputado: resultado real + previsão
    pré-jogo (honesta, do track record) para o detalhe comparar."""
    import json as J
    import numpy as np
    from .thesportsdb import CACHE
    from .live_form import normalize_team
    fp = CACHE / "openfootball_2026.json"
    if not fp.exists():
        return []
    matches = J.loads(fp.read_text()).get("matches", [])

    pre = {}
    for g in (track_record or {}).get("games", []):
        pre[frozenset((g["home"], g["away"]))] = g

    cal = []
    for m in matches:
        if not str(m.get("group", "")).startswith("Group"):
            continue
        h, a = normalize_team(m.get("team1", "")), normalize_team(m.get("team2", ""))
        if h not in idx or a not in idx:
            continue
        M = model.score_matrix(h, a, neutral=True)
        gi, gj = np.unravel_index(int(M.argmax()), M.shape)
        ph = float(np.tril(M, -1).sum()); pdr = float(np.trace(M)); pa = float(np.triu(M, 1).sum())
        lh, la = model.expected_goals(h, a, neutral=True)
        city, stadium = GROUND_TO_STADIUM.get(m.get("ground", ""), (m.get("ground", ""), ""))
        ft = (m.get("score") or {}).get("ft")
        entry = {
            "date": m.get("date"), "kickoff": _parse_kickoff(m.get("time", "")),
            "group": m.get("group", "").replace("Group ", ""),
            "city": city, "stadium": stadium,
            "home": idx[h], "away": idx[a], "played": ft is not None,
            "pred": {"ph": round(ph, 3), "pd": round(pdr, 3), "pa": round(pa, 3),
                     "score": [int(gi), int(gj)], "xg": [round(float(lh), 2), round(float(la), 2)]},
            "actual": None, "pre": None,
        }
        if ft is not None:
            entry["actual"] = [int(ft[0]), int(ft[1])]
            g = pre.get(frozenset((h, a)))
            if g:
                # orienta a previsão pré-jogo para a ordem (home=h, away=a)
                flip = g["home"] != h
                entry["pre"] = {
                    "ph": g["pa"] if flip else g["ph"], "pd": g["pd"],
                    "pa": g["ph"] if flip else g["pa"],
                    "score": [g["predScore"][1], g["predScore"][0]] if flip else g["predScore"],
                }
        cal.append(entry)
    return cal


def build_match_dates(idx: dict, played) -> dict:
    """Data (e hora, quando houver) dos jogos. Data vem dos jogos já disputados
    (results.csv); a hora vem do TheSportsDB quando disponível. Jogos futuros e
    mata-mata ficam de fora (sem calendário carregado) → o painel deixa em branco."""
    import json as J
    from .thesportsdb import CACHE
    from .live_form import normalize_team

    times = {}
    ev_fp = CACHE / "tsdb_events.json"
    if ev_fp.exists():
        for e in (J.loads(ev_fp.read_text()).get("events") or []):
            h = normalize_team(e.get("strHomeTeam", ""))
            a = normalize_team(e.get("strAwayTeam", ""))
            tm = (e.get("strTime") or "")[:5]   # HH:MM
            times[(h, a)] = tm
            times[(a, h)] = tm

    out = {}
    for r in played.itertuples(index=False):
        if r.home_team not in idx or r.away_team not in idx:
            continue
        iso = str(r.date)[:10]
        ddmm = f"{iso[8:10]}/{iso[5:7]}" if len(iso) == 10 else iso
        tm = times.get((r.home_team, r.away_team), "")
        entry = {"date": ddmm, "time": tm}
        out[f"{idx[r.home_team]}-{idx[r.away_team]}"] = entry
        out[f"{idx[r.away_team]}-{idx[r.home_team]}"] = entry
    return out


def build_model(engine: str, live: bool):
    matches = load_matches()
    played = load_played_wc2026()
    elo = compute_elo(matches)
    beta = calibrate(load_shootouts(), elo)
    if engine == "ml":
        from .features import build_features, current_state
        from .ml_model import train, MLGoalModel
        feats = build_features(matches)
        model = MLGoalModel(train(feats), current_state(matches), all_teams())
    elif engine == "ensemble":
        from .ensemble import build_ensemble
        model = build_ensemble(matches, w=0.5)   # blend Dixon-Coles + ML (vence out-of-time)
    else:
        from .goal_model import fit_dixon_coles
        model = fit_dixon_coles(matches)
    if live:
        from .live_form import gather_live_stats, build_team_adjustments, AdjustedGoalModel
        stats = gather_live_stats()
        if not stats.empty:
            model = AdjustedGoalModel(model, build_team_adjustments(model, stats))
    return matches, played, elo, beta, model


def export(engine: str = "dixon", sims: int = 20000, live: bool = False) -> Path:
    matches, played, elo, beta, model = build_model(engine, live)
    table = simulate(model, elo, played, n_sims=sims, shootout_beta=beta)

    teams_order = all_teams()                      # ids 0..47 nesta ordem
    idx = {t: i for i, t in enumerate(teams_order)}
    row = {r["team"]: r for _, r in table.iterrows()}

    # --- força normalizada (Elo -> 45..99) ---
    from .elo import BASE_RATING
    elos = [elo.get(t, BASE_RATING) for t in teams_order]
    emin, emax = min(elos), max(elos)
    def strength(t):
        e = elo.get(t, BASE_RATING)
        return round(45 + (e - emin) / (emax - emin + 1e-9) * 54)

    teams = []
    group_of = {}
    for gi, (g, gteams) in enumerate(GROUPS.items()):
        for t in gteams:
            group_of[t] = gi
    for t in teams_order:
        pt, iso = TEAM_META[t]
        teams.append({"id": idx[t], "en": t, "pt": pt, "iso": iso,
                      "strength": strength(t), "groupId": group_of[t]})

    # --- tabelas de grupo (ordenadas pela colocação esperada) ---
    def rank_score(t):
        r = row[t]
        return 3 * r["p_first_%"] + 2 * r["p_second_%"] + 1 * r["p_third_%"]

    group_labels = list(GROUPS.keys())
    groups = []
    predicted_first, predicted_second, predicted_third = {}, {}, {}
    for gi, (g, gteams) in enumerate(GROUPS.items()):
        ordered = sorted(gteams, key=rank_score, reverse=True)
        predicted_first[g] = ordered[0]
        predicted_second[g] = ordered[1]
        predicted_third[g] = ordered[2]
        tbl = []
        for pos, t in enumerate(ordered):
            tbl.append({"id": idx[t], "pos": pos + 1,
                        "pts": round(row[t]["exp_pts"]),
                        "adv": round(row[t]["advance_%"])})
        groups.append({"id": gi, "label": g,
                       "teamIds": [idx[t] for t in gteams], "table": tbl})

    # --- probabilidades por seleção (id -> %) ---
    def probmap(col):
        return {idx[t]: round(row[t][col], 2) for t in teams_order}
    title_prob = probmap("champion_%")
    final_prob = probmap("finalist_%")
    semi_prob = probmap("semifinal_%")
    adv_prob = probmap("advance_%")

    # --- bracket representativo: 8 melhores terceiros previstos + tabela oficial ---
    thirds_ranked = sorted(group_labels, key=lambda g: row[predicted_third[g]]["advance_%"],
                           reverse=True)
    best_third_groups = sorted(thirds_ranked[:8])
    qualified = {}
    third_by_group = {}
    for g in group_labels:
        qualified[f"1{g}"] = predicted_first[g]
        qualified[f"2{g}"] = predicted_second[g]
        third_by_group[g] = predicted_third[g]
    r32_pairs_names = B.resolve_r32(qualified, third_by_group, best_third_groups)
    r32 = [[idx[h], idx[a]] for h, a in r32_pairs_names]
    qualifier_ids = sorted({i for pair in r32 for i in pair})
    seeds = sorted(qualifier_ids, key=lambda i: title_prob[i], reverse=True)

    bracket_spec = {
        "r32": r32,
        "r16Pairs": [list(p) for p in B.R16_PAIRS],
        "qfPairs": [list(p) for p in B.QF_PAIRS],
        "sfPairs": [list(p) for p in B.SF_PAIRS],
    }

    # --- gols esperados + PLACAR MAIS PROVÁVEL (moda da matriz) por par ---
    # o placar exibido é a moda da matriz de placares (argmax) — simétrico por
    # construção, então o mesmo jogo mostra o mesmo placar de qualquer perspectiva.
    import numpy as np
    n = len(teams_order)
    lambdas = [[[0.0, 0.0] for _ in range(n)] for _ in range(n)]
    scorelines = [[[0, 0] for _ in range(n)] for _ in range(n)]
    # winScores[i][j] = placar mais provável em que i (mandante) VENCE j.
    # usado no mata-mata (que não pode empatar) — mais variado que somar +1.
    win_scores = [[[1, 0] for _ in range(n)] for _ in range(n)]
    for i, h in enumerate(teams_order):
        for j, a in enumerate(teams_order):
            if i == j:
                continue
            lh, la = model.expected_goals(h, a, neutral=True)
            lambdas[i][j] = [round(float(lh), 3), round(float(la), 3)]
            M = model.score_matrix(h, a, neutral=True)
            gi, gj = np.unravel_index(int(M.argmax()), M.shape)
            scorelines[i][j] = [int(gi), int(gj)]
            # moda restrita às vitórias do mandante (linha > coluna)
            rows, cols = np.indices(M.shape)
            Mwin = np.where(rows > cols, M, -1.0)
            wi, wj = np.unravel_index(int(Mwin.argmax()), M.shape)
            win_scores[i][j] = [int(wi), int(wj)]

    # --- jogos JÁ disputados (placar real) p/ o painel exibir o resultado real ---
    played_rows = []
    for r in played.itertuples(index=False):
        if r.home_team in idx and r.away_team in idx:
            played_rows.append([idx[r.home_team], idx[r.away_team],
                                int(r.home_score), int(r.away_score)])

    # --- microestatísticas por jogo (o que a fonte gratuita fornece: finalizações) ---
    match_stats = build_match_stats(idx)

    # --- data/hora dos jogos (data dos disputados + hora do TheSportsDB) ---
    match_dates = build_match_dates(idx, played)

    # --- track record: backtest sem vazamento dos jogos já disputados ---
    from .track import backtest
    track_record = backtest()

    # --- calendário da fase de grupos (datas/horas/estádios + previsão por jogo) ---
    calendar = build_calendar(idx, model, played, track_record)

    data = {
        "teams": teams,
        "groupLabels": group_labels,
        "groups": groups,
        "played": played_rows,
        "matchStats": match_stats,
        "trackRecord": track_record,
        "calendar": calendar,
        "titleProb": title_prob,
        "finalProb": final_prob,
        "semiProb": semi_prob,
        "advProb": adv_prob,
        "qualifierIds": qualifier_ids,
        "seeds": seeds,
        "bracketSpec": bracket_spec,
        "lambdas": lambdas,
        "scorelines": scorelines,
        "winScores": win_scores,
        "matchDates": match_dates,
        "venues": VENUES,
        "meta": {
            "engine": engine, "sims": sims, "live": live,
            "playedMatches": int(len(played)),
            "topFavorite": teams[seeds[0]]["en"] if seeds else None,
        },
    }

    WEB_DIR.mkdir(exist_ok=True)
    out = WEB_DIR / "wc_data.js"
    out.write_text("/* GERADO por wc2026.export_web — NÃO editar à mão. */\n"
                   "window.WC_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["dixon", "ml", "ensemble"], default="ensemble")
    ap.add_argument("--sims", type=int, default=20000)
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    print(f"Rodando modelo (engine={args.engine}, sims={args.sims:,}, live={args.live})...")
    out = export(args.engine, args.sims, args.live)
    size_kb = out.stat().st_size / 1024
    print(f"Exportado: {out}  ({size_kb:.0f} KB)")
    import json as J
    d = J.loads(out.read_text().split("=", 1)[1].rsplit(";", 1)[0])
    fav = d["meta"]["topFavorite"]
    print(f"Favorito: {fav}  |  {len(d['teams'])} selecoes, "
          f"{len(d['bracketSpec']['r32'])} jogos no R32, "
          f"{d['meta']['playedMatches']} jogos da Copa ja realizados")


if __name__ == "__main__":
    main()
