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
    python -m wc2026.export_web                           # ensemble (padrão), 20k sims
    python -m wc2026.export_web --engine ml --live --sims 50000
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
from .scoreline import favored_scoreline
from . import bracket as B
from .venue import expected_goals_with_venue, score_matrix_with_venue

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
    (mata-mata vem do supplement em export() usando bracket + played winners)."""
    import json as J
    import numpy as np
    from .thesportsdb import CACHE
    from .live_form import normalize_team
    from .venue import expected_goals_with_venue, score_matrix_with_venue
    fp = CACHE / "openfootball_2026.json"
    if not fp.exists():
        return []
    matches = J.loads(fp.read_text()).get("matches", [])

    pre = {}
    for g in (track_record or {}).get("games", []):
        pre[frozenset((g["home"], g["away"]))] = g

    # mídia/contexto extra do TheSportsDB (highlight, thumb, estádio oficial)
    tsdb = {}
    ev_fp = CACHE / "tsdb_events.json"
    if ev_fp.exists():
        for e in (J.loads(ev_fp.read_text()).get("events") or []):
            hh = normalize_team(e.get("strHomeTeam", ""))
            aa = normalize_team(e.get("strAwayTeam", ""))
            tsdb[frozenset((hh, aa))] = {
                "video": e.get("strVideo") or "",
                "thumb": e.get("strThumb") or "",
                "venue": e.get("strVenue") or "",
            }

    def _goals(raw):
        """Normaliza a lista de gols do openfootball (autor, minuto, pênalti)."""
        out = []
        for ev in (raw or []):
            if not ev.get("name"):
                continue
            out.append({
                "name": ev.get("name", ""),
                "minute": str(ev.get("minute", "")),
                "penalty": bool(ev.get("penalty", False)),
                "owngoal": bool(ev.get("owngoal", False)),
            })
        # ordena por minuto (trata '90+4' etc.)
        def _mk(g):
            mm = g["minute"].replace("'", "").split("+")
            try:
                return int(mm[0]) * 100 + (int(mm[1]) if len(mm) > 1 else 0)
            except Exception:
                return 9999
        return sorted(out, key=_mk)

    cal = []
    for m in matches:
        grp = str(m.get("group", ""))
        is_group = grp.startswith("Group")
        if not is_group:
            continue
        h, a = normalize_team(m.get("team1", "")), normalize_team(m.get("team2", ""))
        if h not in idx or a not in idx:
            continue
        M = score_matrix_with_venue(model, h, a)
        # placar coerente com o resultado favorito (não a moda global) — evita
        # "previsto 1-1" junto de "favorito: mandante vence".
        _, (gi, gj), (ph, pdr, pa) = favored_scoreline(M)
        lh, la = expected_goals_with_venue(model, h, a)
        # top 3 placares mais prováveis (para o modal de jogo futuro)
        flat = M.ravel()
        topk = np.argsort(flat)[::-1][:3]
        top = [[int(k // M.shape[1]), int(k % M.shape[1]), round(float(flat[k]), 3)] for k in topk]
        city, stadium = GROUND_TO_STADIUM.get(m.get("ground", ""), (m.get("ground", ""), ""))
        ft = (m.get("score") or {}).get("ft")
        media = tsdb.get(frozenset((h, a)), {})
        entry = {
            "date": m.get("date"), "kickoff": _parse_kickoff(m.get("time", "")),
            "group": m.get("group", "").replace("Group ", "") if is_group else "",
            "round": "",
            "num": m.get("num"),
            "city": city, "stadium": stadium,
            "home": idx[h], "away": idx[a], "played": ft is not None,
            "pred": {"ph": round(ph, 3), "pd": round(pdr, 3), "pa": round(pa, 3),
                     "score": [int(gi), int(gj)], "xg": [round(float(lh), 2), round(float(la), 2)],
                     "top": top},
            "actual": None, "pre": None,
            "video": media.get("video", ""), "thumb": media.get("thumb", ""),
        }
        if ft is not None:
            entry["actual"] = [int(ft[0]), int(ft[1])]
            htsc = (m.get("score") or {}).get("ht")
            if htsc:
                entry["ht"] = [int(htsc[0]), int(htsc[1])]
            entry["goals"] = {"home": _goals(m.get("goals1")), "away": _goals(m.get("goals2"))}
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


def build_model(engine: str, live: bool, calibrated: bool = True):
    matches = load_matches()
    played = load_played_wc2026()
    elo = compute_elo(matches)
    beta = calibrate(load_shootouts(), elo)
    if engine == "ml":
        from .features import build_features, current_state
        from .ml_model import train, MLGoalModel
        feats = build_features(matches)
        model = MLGoalModel(train(feats), current_state(matches), all_teams())
        w = 0.0
    elif engine == "ensemble":
        from .ensemble import build_ensemble, get_optimal_ensemble_weight
        w = 0.55
        try:
            w = get_optimal_ensemble_weight()  # peso dinâmico via validação (Point 4)
        except Exception:
            pass
        model = build_ensemble(matches, w=w)   # blend Dixon-Coles + ML (dinâmico)
    else:
        from .goal_model import fit_dixon_coles
        model = fit_dixon_coles(matches)
        w = 1.0
    if live:
        from .live_form import gather_live_stats, build_team_adjustments, AdjustedGoalModel
        stats = gather_live_stats()
        if not stats.empty:
            model = AdjustedGoalModel(model, build_team_adjustments(model, stats))
    if calibrated:
        from .outcome_calibration import calibrate_model
        cal_w = w if engine == "ensemble" else 0.5
        model = calibrate_model(model, matches, engine=engine, w=cal_w)
    return matches, played, elo, beta, model


def export(engine: str = "dixon", sims: int = 20000, live: bool = False,
           calibrated: bool = True) -> Path:
    from .venue import expected_goals_with_venue, score_matrix_with_venue

    matches, played, elo, beta, model = build_model(engine, live, calibrated)
    table = simulate(model, elo, played, n_sims=sims, shootout_beta=beta, return_ci=True)

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

    # --- standings reais dos grupos (agora que fase de grupos está completa) ---
    # Usado para resolver R32 exato no calendário (mata-mata) com times que realmente passaram.
    from collections import defaultdict
    team_to_group = {}
    for gname, gteams in GROUPS.items():
        for t in gteams:
            team_to_group[t] = gname
    actual_pts = defaultdict(int)
    actual_gf = defaultdict(int)
    actual_ga = defaultdict(int)
    for r in played.itertuples(index=False):
        h, a = r.home_team, r.away_team
        if h not in team_to_group or a not in team_to_group:
            continue
        if team_to_group[h] != team_to_group[a]:
            continue  # só partidas dentro do mesmo grupo
        hg, ag = int(r.home_score), int(r.away_score)
        actual_gf[h] += hg; actual_ga[h] += ag
        actual_gf[a] += ag; actual_ga[a] += hg
        if hg > ag:
            actual_pts[h] += 3
        elif ag > hg:
            actual_pts[a] += 3
        else:
            actual_pts[h] += 1
            actual_pts[a] += 1
    actual_first, actual_second, actual_third = {}, {}, {}
    for gname, gteams in GROUPS.items():
        order = sorted(gteams, key=lambda t: (actual_pts[t], actual_gf[t] - actual_ga[t], actual_gf[t]), reverse=True)
        actual_first[gname] = order[0]
        actual_second[gname] = order[1]
        actual_third[gname] = order[2]

    # patch the exported groups tables to show real pts (now that groups are complete)
    for g in groups:
        gname = g["label"]
        for entry in g["table"]:
            tname = next((nm for nm, i in idx.items() if i == entry["id"]), None)
            if tname and tname in actual_pts:
                entry["pts"] = actual_pts[tname]

    # --- probabilidades por seleção (id -> %) ---
    def probmap(col):
        return {idx[t]: round(row[t][col], 2) for t in teams_order}
    title_prob = probmap("champion_%")
    final_prob = probmap("finalist_%")
    semi_prob = probmap("semifinal_%")
    adv_prob = probmap("advance_%")

    # uncertainty bands (if return_ci) -- enhance export for later stages (KO).
    # bandas são probabilidades em %: limitar a [0, 100] (nunca negativas).
    def _clamp_band(lo, hi):
        return [round(max(0.0, lo), 1), round(min(100.0, hi), 1)]
    def probmap_ci(basecol):
        lk = basecol.replace("%", "_ci_low")
        hk = basecol.replace("%", "_ci_high")
        has_ci = lk in row[teams_order[0]] if teams_order else False
        if not has_ci:
            # fallback small bands based on point est
            return {idx[t]: _clamp_band(row[t][basecol] - 4, row[t][basecol] + 4) for t in teams_order}
        return {idx[t]: _clamp_band(row[t][lk], row[t][hk]) for t in teams_order}
    title_prob_ci = probmap_ci("champion_%")
    final_prob_ci = probmap_ci("finalist_%")
    semi_prob_ci = probmap_ci("semifinal_%")
    adv_prob_ci = probmap_ci("advance_%")

    # --- bracket representativo: use standings REAIS quando grupos completos (para R32 do calendário) ---
    # Critério FIFA para 3ºs: pts, saldo de gols, gols pró
    actual_thirds_ranked = sorted(
        group_labels,
        key=lambda g: (actual_pts[actual_third[g]], actual_gf[actual_third[g]] - actual_ga[actual_third[g]], actual_gf[actual_third[g]]),
        reverse=True
    )
    best_third_groups = sorted(actual_thirds_ranked[:8])
    qualified = {}
    third_by_group = {}
    for g in group_labels:
        qualified[f"1{g}"] = actual_first.get(g, predicted_first[g])
        qualified[f"2{g}"] = actual_second.get(g, predicted_second[g])
        third_by_group[g] = actual_third.get(g, predicted_third[g])
    r32_pairs_names = B.resolve_r32(qualified, third_by_group, best_third_groups)
    r32 = [[idx[h], idx[a]] for h, a in r32_pairs_names]
    qualifier_ids = sorted({i for pair in r32 for i in pair})
    seeds = sorted(qualifier_ids, key=lambda i: title_prob[i], reverse=True)

    # supplement calendar with R32 mata-mata using resolved teams (from current sim, which fixes played groups)
    # this way daily export inserts the teams that passed groups into the KO slots
    import json as J
    import numpy as np
    from .thesportsdb import CACHE
    ko_cal = []
    fpk = CACHE / "openfootball_2026.json"
    # build played lookup for KO overlay
    played_lookup = {}
    for r in played.itertuples(index=False):
        if r.home_team in idx and r.away_team in idx:
            played_lookup[(idx[r.home_team], idx[r.away_team])] = (int(r.home_score), int(r.away_score))
            played_lookup[(idx[r.away_team], idx[r.home_team])] = (int(r.away_score), int(r.home_score))
    played_winners = {}

    def _draw_aware_winner(actual, home_id, away_id, ph, pa):
        """Quem avança num confronto de mata-mata já disputado.
        Vitória no tempo normal → o vencedor. Empate (foi aos pênaltis, mas a
        base gratuita não guarda o placar da disputa) → placeholder pelo favorito
        pré-jogo (maior prob. de vitória no modelo), em vez de assumir o visitante.
        Vale só enquanto o openfootball ainda não reescreveu o rótulo para o nome
        do classificado real — quando reescreve, esse nome (autoritativo) prevalece."""
        if actual[0] > actual[1]:
            return home_id
        if actual[0] < actual[1]:
            return away_id
        return home_id if (ph or 0) >= (pa or 0) else away_id

    if fpk.exists():
        ko_matches = [m for m in J.loads(fpk.read_text()).get("matches", []) if m.get("round") == "Round of 32"]
        for i, m in enumerate(ko_matches):
            if i >= len(r32_pairs_names): break
            hname, aname = r32_pairs_names[i]
            if hname not in idx or aname not in idx: continue
            hh, aa = idx[hname], idx[aname]
            city, stadium = GROUND_TO_STADIUM.get(m.get("ground", ""), (m.get("ground", ""), ""))
            # prefer actual played result if available (for pre-fill and correct played flag)
            actual = played_lookup.get((hh, aa))
            ft = actual is not None
            # still compute pred from model (for upcoming or reference)
            M = score_matrix_with_venue(model, hname, aname)
            _, (gi, gj), (ph, pdr, pa) = favored_scoreline(M)
            lh, la = expected_goals_with_venue(model, hname, aname)
            flat = M.ravel()
            topk = np.argsort(flat)[::-1][:3]
            top = [[int(k // M.shape[1]), int(k % M.shape[1]), round(float(flat[k]), 3)] for k in topk]
            entry = {
                "date": m.get("date"), "kickoff": _parse_kickoff(m.get("time", "")),
                "group": "", "round": "R32", "num": m.get("num"),
                "city": city, "stadium": stadium,
                "home": hh, "away": aa, "played": ft,
                "pred": {"ph": round(ph, 3), "pd": round(pdr, 3), "pa": round(pa, 3),
                         "score": [int(gi), int(gj)], "xg": [round(float(lh), 2), round(float(la), 2)],
                         "top": top},
                "actual": list(actual) if actual else None,
                "goals": {"home": [], "away": []},
                "video": "", "thumb": "",
            }
            if ft:
                winner = _draw_aware_winner(actual, hh, aa, ph, pa)
                played_winners[m.get("num")] = winner
            ko_cal.append(entry)

    # Add other KO rounds (R16+) using winner labels from prior, pre-filling known advancers.
    # Process round-by-round so that when a round's results are in played (daily update),
    # its winners are inserted into the next round's calendar entries (known team vs "aguardando").
    from .live_form import normalize_team  # reconcilia grafia do openfootball com o idx

    def _resolve_winner(label, winners):
        """Resolve o rótulo de um confronto de mata-mata para o id da seleção.
        Dois formatos convivem no openfootball para o MESMO slot:
          1) "W<num>" (ex.: "W74") enquanto o jogo anterior não terminou →
             busca o vencedor já apurado em `winners` (None se ainda indefinido);
          2) o NOME literal do classificado (ex.: "Canada", "Brazil") — o
             openfootball reescreve "W74" para o nome assim que o jogo termina.
             Antes isso caía fora e o slot ficava "A definir" mesmo com o
             classificado conhecido: resolve pelo idx (com normalização de grafia).
        O nome literal é a fonte AUTORITATIVA (inclui quem passou nos pênaltis)."""
        label = (label or "").strip()
        if not label:
            return None
        if label[0] == "W" and label[1:].isdigit():   # rótulo "W74"
            return winners.get(int(label[1:]))
        return idx.get(normalize_team(label))          # rótulo = nome do classificado

    ROUND_ORDER = ["Round of 16", "Quarter-final", "Semi-final", "Final", "Match for third place"]
    if fpk.exists():
        all_matches = J.loads(fpk.read_text()).get("matches", [])
        for rnd in ROUND_ORDER:
            rnd_matches = [m for m in all_matches if m.get("round") == rnd]
            for m in rnd_matches:
                t1 = m.get("team1", "")
                t2 = m.get("team2", "")
                hh = _resolve_winner(t1, played_winners)
                aa = _resolve_winner(t2, played_winners)
                city, stadium = GROUND_TO_STADIUM.get(m.get("ground", ""), (m.get("ground", ""), ""))
                # compute real pred only when both participants known (otherwise neutral placeholder)
                pred = {"ph": 0.5, "pd": 0, "pa": 0.5, "score": [1, 0], "xg": [1.5, 1.5], "top": []}
                if hh is not None and aa is not None:
                    hname = next((nm for nm, i in idx.items() if i == hh), None)
                    aname = next((nm for nm, i in idx.items() if i == aa), None)
                    if hname and aname:
                        M = score_matrix_with_venue(model, hname, aname)
                        _, (gi, gj), (phh, pdd, paa) = favored_scoreline(M)
                        lh, la = expected_goals_with_venue(model, hname, aname)
                        flat = M.ravel()
                        topk = np.argsort(flat)[::-1][:3]
                        top = [[int(k // M.shape[1]), int(k % M.shape[1]), round(float(flat[k]), 3)] for k in topk]
                        pred = {"ph": round(phh, 3), "pd": round(pdd, 3), "pa": round(paa, 3),
                                "score": [int(gi), int(gj)], "xg": [round(float(lh), 2), round(float(la), 2)],
                                "top": top}
                entry = {
                    "date": m.get("date"), "kickoff": _parse_kickoff(m.get("time", "")),
                    "group": "", "round": rnd, "num": m.get("num"),
                    "city": city, "stadium": stadium,
                    "home": hh, "away": aa,
                    "played": False,
                    "pred": pred,
                    "actual": None,
                    "goals": {"home": [], "away": []},
                    "video": "", "thumb": "",
                    "tbd_home": t1 if hh is None else None,
                    "tbd_away": t2 if aa is None else None,
                }
                ko_cal.append(entry)
            # After adding this round's fixtures, overlay any actual played results for pairs we now know.
            # If a match finished, record its winner so the *next* round gets pre-filled on this/ future daily exports.
            for e in [e for e in ko_cal if e.get("round") == rnd]:
                if e.get("home") is not None and e.get("away") is not None:
                    act = played_lookup.get((e["home"], e["away"]))
                    if act:
                        e["played"] = True
                        e["actual"] = list(act)
                        pr = e.get("pred") or {}
                        win = _draw_aware_winner(act, e["home"], e["away"], pr.get("ph", 0), pr.get("pa", 0))
                        played_winners[e.get("num")] = win
    # will extend calendar after build

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
            lh, la = expected_goals_with_venue(model, h, a)
            lambdas[i][j] = [round(float(lh), 3), round(float(la), 3)]
            M = score_matrix_with_venue(model, h, a)
            # placar coerente com o resultado favorito (vide wc2026/scoreline.py)
            _, (gi, gj), _ = favored_scoreline(M)
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
    track_record = backtest(engine=engine, calibrated=calibrated)

    # --- calendário da fase de grupos (datas/horas/estádios + previsão por jogo) ---
    calendar = build_calendar(idx, model, played, track_record)
    calendar.extend(ko_cal)

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
        "titleProbCI": title_prob_ci,
        "finalProbCI": final_prob_ci,
        "semiProbCI": semi_prob_ci,
        "advProbCI": adv_prob_ci,
        "qualifierIds": qualifier_ids,
        "seeds": seeds,
        "bracketSpec": bracket_spec,
        "lambdas": lambdas,
        "scorelines": scorelines,
        "winScores": win_scores,
        "matchDates": match_dates,
        "venues": VENUES,
        "meta": {
            "engine": engine, "sims": sims, "live": live, "calibrated": calibrated,
            "playedMatches": int(len(played)),
            "topFavorite": teams[seeds[0]]["en"] if seeds else None,
            "hostAdvantageTeams": sorted(["Canada", "Mexico", "United States"]),
            "koEnhancements": "r32_venue_explicit + et_pens + ko_var + ci_bands",
            "ciEnabled": True,
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
    ap.add_argument("--no-calibration", action="store_true",
                    help="desliga a calibração pós-modelo de V/E/D")
    args = ap.parse_args()
    calibrated = not args.no_calibration
    print(f"Rodando modelo (engine={args.engine}, sims={args.sims:,}, "
          f"live={args.live}, calibrated={calibrated})...")
    out = export(args.engine, args.sims, args.live, calibrated)
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
