"""
Conector gratuito da TheSportsDB para dados granulares ao vivo da Copa 2026.

Por que esta fonte
-------------------
O plano grátis da API-Football NÃO libera a season 2026 (só 2022-2024). A
TheSportsDB, por outro lado, expõe a Copa 2026 (league=4429, season=2026) com a
chave pública gratuita "3", incluindo estatísticas de finalização por jogo
(chutes no alvo, total, bloqueados, dentro da área) — exatamente o sinal que a
camada `live_form` usa como xG-proxy.

Limitações honestas
-------------------
- Sem chave paga, a cobertura tem ATRASO e pode vir incompleta (nem todos os
  jogos já disputados aparecem, e métricas como posse/escanteios podem faltar).
  Coletamos o que houver; conforme o TheSportsDB ingere mais jogos, mais aparece.
- Só finalizações (sem posse/xG no tier grátis). Chutes no alvo bastam para o
  xG-proxy de `live_form` (≈0.30 gol por chute no alvo).

Saída
-----
`load_stats()` devolve um DataFrame no MESMO schema de `live_form.parse_cache`
(uma linha por jogo+seleção), então alimenta `build_team_adjustments` direto.
O JSON cru fica em cache em `api_cache/tsdb_*.json` para não rebaixar.

Uso
---
    python -m wc2026.thesportsdb --pull       # baixa eventos + stats para o cache
    python -m wc2026.thesportsdb              # mostra o que já está no cache
    python -m wc2026.run --live               # usa no pipeline (via live_form)
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

from .live_form import normalize_team

# Chave pública gratuita do TheSportsDB (documentada). Pode trocar por uma chave
# própria (Patreon) na env TSDB_KEY para mais cobertura/rate.
import os
KEY = os.environ.get("TSDB_KEY", "3")
BASE = f"https://www.thesportsdb.com/api/v1/json/{KEY}"
WC_LEAGUE = 4429   # FIFA World Cup
SEASON = "2026"
CACHE = Path(__file__).resolve().parent.parent / "api_cache"

# nº de chutes no alvo -> nome de stat no TheSportsDB
STAT_ON_TARGET = "Shots on Goal"
STAT_TOTAL = "Total Shots"
STAT_CORNERS = "Corner Kicks"        # pode não vir no tier grátis
STAT_POSSESSION = "Possession %"     # idem


def _get(url: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "wc2026/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# janela do torneio (Copa 2026): 11/jun a 19/jul
WC_START = "2026-06-11"
WC_END = "2026-07-19"


def _wc_dates() -> list[str]:
    import datetime
    d0 = datetime.date.fromisoformat(WC_START)
    d1 = datetime.date.fromisoformat(WC_END)
    out, d = [], d0
    while d <= d1:
        out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def _collect_events(verbose: bool) -> dict:
    """Agrega os eventos da Copa de DUAS fontes do TheSportsDB e dedup por idEvent:
      1) eventsseason.php (pega o que houver de uma vez);
      2) eventsday.php?d=<data>&l=<liga> por dia — ESSENCIAL, porque o eventsseason
         do tier grátis costuma travar nos primeiros jogos, enquanto o eventsday
         entrega os jogos recentes (com estatística) normalmente.
    """
    events = {}
    try:
        data = _get(f"{BASE}/eventsseason.php?id={WC_LEAGUE}&s={SEASON}")
        for e in (data.get("events") or []):
            events[e["idEvent"]] = e
    except Exception:
        pass
    for d in _wc_dates():
        try:
            r = _get(f"{BASE}/eventsday.php?d={d}&l={WC_LEAGUE}")
            for e in (r.get("events") or []):
                events[e["idEvent"]] = e
            time.sleep(0.25)  # gentil com o serviço grátis
        except Exception:
            continue
    if verbose:
        print(f"{len(events)} eventos da Copa 2026 (eventsseason + eventsday, chave '{KEY}').")
    return events


def pull(verbose: bool = True) -> int:
    """Baixa eventos da Copa (todas as datas) + stats de cada jogo finalizado.
    Devolve o nº de jogos com estatística salvos."""
    CACHE.mkdir(exist_ok=True)
    events = _collect_events(verbose)
    (CACHE / "tsdb_events.json").write_text(json.dumps({"events": list(events.values())}))

    saved = 0
    for e in events.values():
        # considera jogo válido se tem placar
        if e.get("intHomeScore") in (None, "") or e.get("intAwayScore") in (None, ""):
            continue
        eid = e["idEvent"]
        fp = CACHE / f"tsdb_stats_{eid}.json"
        st = None
        if fp.exists():
            try:
                st = json.loads(fp.read_text())
            except Exception:
                st = None
        if not (st and st.get("eventstats")):   # (re)baixa se não cacheado ou cache vazio
            # o tier grátis costuma throttlear em lote (retorna vazio); 1 retry com
            # pausa resolve a maioria. Só grava quando vem estatística de fato, então
            # jogos throttlados são re-tentados no próximo run (cache persistido no repo).
            st = {}
            for attempt in (0, 1):
                try:
                    st = _get(f"{BASE}/lookupeventstats.php?id={eid}")
                except Exception:
                    st = {}
                if st.get("eventstats"):
                    fp.write_text(json.dumps(st))
                    break
                time.sleep(1.5)
        if st.get("eventstats"):
            saved += 1
            if verbose:
                print(f"  {e['dateEvent']}  {e['strHomeTeam']} {e['intHomeScore']}"
                      f"x{e['intAwayScore']} {e['strAwayTeam']}  "
                      f"({len(st['eventstats'])} stats)")
    if verbose:
        print(f"Pronto: {saved} jogos com estatística em {CACHE}/")
    return saved


def _stat(stats: list[dict], name: str) -> float | None:
    for s in stats:
        if s.get("strStat") == name:
            return s
    return None


def _to_float(v) -> float:
    if v in (None, ""):
        return 0.0
    if isinstance(v, str):
        v = v.strip().rstrip("%")
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def load_stats() -> pd.DataFrame:
    """Lê o cache do TheSportsDB e devolve uma linha por (jogo, seleção) no mesmo
    schema de live_form.parse_cache: fixture, date, team, opponent, shots_total,
    shots_on_target, possession, corners, goals_for, goals_against."""
    ev_fp = CACHE / "tsdb_events.json"
    if not ev_fp.exists():
        return pd.DataFrame()
    events = {e["idEvent"]: e for e in (json.loads(ev_fp.read_text()).get("events") or [])}

    rows = []
    for fp in sorted(CACHE.glob("tsdb_stats_*.json")):
        eid = fp.stem.split("tsdb_stats_", 1)[1]
        st = json.loads(fp.read_text()).get("eventstats")
        ev = events.get(eid)
        if not st or not ev:
            continue
        home = normalize_team(ev["strHomeTeam"])
        away = normalize_team(ev["strAwayTeam"])
        hg, ag = ev.get("intHomeScore"), ev.get("intAwayScore")
        hg = int(hg) if hg not in (None, "") else None
        ag = int(ag) if ag not in (None, "") else None

        sot = _stat(st, STAT_ON_TARGET)
        tot = _stat(st, STAT_TOTAL)
        corn = _stat(st, STAT_CORNERS)
        poss = _stat(st, STAT_POSSESSION)

        def side(is_home: bool):
            k = "intHome" if is_home else "intAway"
            return {
                "fixture": eid,
                "date": ev.get("dateEvent"),
                "team": home if is_home else away,
                "opponent": away if is_home else home,
                "shots_total": _to_float(tot[k]) if tot else 0.0,
                "shots_on_target": _to_float(sot[k]) if sot else 0.0,
                "possession": (_to_float(poss[k]) / 100.0) if poss else 0.0,
                "corners": _to_float(corn[k]) if corn else 0.0,
                "goals_for": (hg if is_home else ag),
                "goals_against": (ag if is_home else hg),
            }

        rows.append(side(True))
        rows.append(side(False))

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", action="store_true", help="baixa eventos + stats para o cache")
    args = ap.parse_args()

    if args.pull:
        pull()
        print()

    df = load_stats()
    if df.empty:
        print(f"Cache TheSportsDB vazio em {CACHE}/. Rode: python -m wc2026.thesportsdb --pull")
        return
    print(f"{df['fixture'].nunique()} jogos | {len(df)} linhas (time x jogo):\n")
    cols = ["date", "team", "opponent", "shots_total", "shots_on_target",
            "goals_for", "goals_against"]
    print(df[cols].to_string(index=False))


if __name__ == "__main__":
    main()
