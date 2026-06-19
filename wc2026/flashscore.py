"""
Ingestão LOCAL de estatísticas do Flashscore para os jogos da Copa 2026.

O Flashscore tem escanteios/cartões/posse, mas só via SCRAPING (precisa de
navegador) — e bloqueia IPs de datacenter, então NÃO dá pra automatizar na nuvem
(/atualizar). O fluxo é local e manual:

  1. Rode o scraper github.com/gustavofariaa/FlashscoreScraping no seu Mac, para a
     competição da Copa, exportando JSON.
  2. Salve o arquivo em  api_cache/flashscore.json  (ou flashscore_*.json).
  3. Rode  python -m wc2026.export_web ...  — as stats entram no detalhe do jogo.

Este módulo NÃO raspa nada (sem dependência de navegador): só LÊ o JSON exportado.
Formato esperado (do scraper): objeto { matchId: { home:{name}, away:{name},
date, statistics:[{category, homeValue, awayValue}], ... } }.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / "api_cache"

# categoria do Flashscore -> (rótulo PT, rótulo EN). Inclui apelidos comuns.
# A ordem aqui é a ordem de exibição no painel.
STAT_MAP = [
    (("Ball Possession", "Possession"), "Posse de bola", "Possession"),
    (("Goal Attempts", "Total Shots", "Shots"), "Finalizações", "Total shots"),
    (("Shots on Goal", "Shots on Target"), "No alvo", "On target"),
    (("Shots off Goal", "Shots off Target"), "Para fora", "Off target"),
    (("Blocked Shots",), "Bloqueadas", "Blocked"),
    (("Corner Kicks", "Corners"), "Escanteios", "Corners"),
    (("Fouls", "Fouls Committed"), "Faltas", "Fouls"),
    (("Yellow Cards",), "Cartões amarelos", "Yellow cards"),
    (("Red Cards",), "Cartões vermelhos", "Red cards"),
    (("Offsides",), "Impedimentos", "Offsides"),
    (("Goalkeeper Saves", "Saves"), "Defesas", "Saves"),
]


def _num(v) -> float:
    if v is None:
        return 0.0
    s = str(v).strip().replace("%", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _iter_matches(data):
    """Aceita { id: match } (formato do scraper) ou uma lista de matches."""
    if isinstance(data, dict):
        # pode ser o dict de matches OU {matches:[...]}/{response:[...]}
        if "matches" in data and isinstance(data["matches"], (list, dict)):
            yield from _iter_matches(data["matches"])
            return
        for v in data.values():
            if isinstance(v, dict) and ("home" in v or "statistics" in v):
                yield v
    elif isinstance(data, list):
        for v in data:
            if isinstance(v, dict):
                yield v


def match_stats_rows(idx: dict) -> list[dict]:
    """Lê os JSONs do Flashscore em api_cache/ e devolve linhas de estatística por
    jogo, com a grafia/ids do nosso dataset. Pula jogos cujos times não estão em idx."""
    from .live_form import normalize_team
    out = []
    for fp in sorted(glob.glob(str(CACHE / "flashscore*.json"))):
        try:
            data = json.loads(Path(fp).read_text())
        except Exception:
            continue
        for m in _iter_matches(data):
            home = m.get("home", {})
            away = m.get("away", {})
            hn = normalize_team((home.get("name") if isinstance(home, dict) else home) or "")
            an = normalize_team((away.get("name") if isinstance(away, dict) else away) or "")
            if hn not in idx or an not in idx:
                continue
            raw = {s.get("category"): s for s in (m.get("statistics") or [])}
            stats = []
            for aliases, pt, en in STAT_MAP:
                hit = next((raw[c] for c in aliases if c in raw), None)
                if hit is not None:
                    stats.append({"pt": pt, "en": en,
                                  "home": _num(hit.get("homeValue")),
                                  "away": _num(hit.get("awayValue"))})
            if stats:
                out.append({"h": idx[hn], "a": idx[an], "stats": stats, "src": "Flashscore"})
    return out


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from wc2026.groups import all_teams
    idx = {t: i for i, t in enumerate(all_teams())}
    rows = match_stats_rows(idx)
    inv = {i: t for t, i in idx.items()}
    if not rows:
        print("Nenhum JSON do Flashscore em api_cache/ (flashscore*.json).")
        print("Rode o scraper e salve o export lá. Formato: {id:{home,away,statistics}}.")
    else:
        print(f"{len(rows)} jogos com estatística do Flashscore:")
        for r in rows:
            cats = ", ".join(s["pt"] for s in r["stats"])
            print(f"  {inv[r['h']]} x {inv[r['a']]}: {cats}")
