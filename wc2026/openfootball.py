"""
Conector openfootball/worldcup.json — fonte GRATUITA e de domínio público dos
resultados da Copa 2026, em geral MAIS FRESCA que a martj42 (costuma ter os jogos
do mesmo dia). JSON limpo, sem chave de API.

Serve para preencher os resultados recentes que a base histórica (martj42) ainda
não propagou. `data.load_matches()` sobrepõe esses jogos automaticamente.

    python -m wc2026.openfootball --update   # baixa e mostra os jogos com placar
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd

URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
CACHE = Path(__file__).resolve().parent.parent / "api_cache"
CACHE_FILE = CACHE / "openfootball_2026.json"


def fetch() -> int:
    """Baixa o JSON do openfootball para o cache. Devolve nº de jogos com placar."""
    CACHE.mkdir(exist_ok=True)
    urllib.request.urlretrieve(URL, CACHE_FILE)
    data = json.loads(CACHE_FILE.read_text())
    return sum(1 for m in data.get("matches", []) if (m.get("score") or {}).get("ft"))


def played_games() -> pd.DataFrame:
    """Lê o cache e devolve os jogos da Copa 2026 JÁ disputados (com placar),
    com a grafia de seleção normalizada para a da base histórica."""
    if not CACHE_FILE.exists():
        return pd.DataFrame()
    from .live_form import normalize_team   # lazy: evita import circular
    data = json.loads(CACHE_FILE.read_text())
    rows = []
    for m in data.get("matches", []):
        ft = (m.get("score") or {}).get("ft")
        if not ft:
            continue   # jogo ainda não disputado (placeholders 1A/W73/... entram aqui)
        rows.append({
            "date": m.get("date"),
            "home_team": normalize_team(m.get("team1", "")),
            "away_team": normalize_team(m.get("team2", "")),
            "home_score": int(ft[0]), "away_score": int(ft[1]),
            "tournament": "FIFA World Cup", "city": m.get("ground", ""),
            "country": "", "neutral": True,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


if __name__ == "__main__":
    if "--update" in sys.argv or not CACHE_FILE.exists():
        print(f"{fetch()} jogos com placar baixados para {CACHE_FILE}")
    df = played_games()
    print(f"{len(df)} jogos da Copa 2026 com placar (openfootball):")
    for r in df.sort_values("date").tail(10).itertuples(index=False):
        print(f"  {r.date.date()} {r.home_team} {r.home_score}x{r.away_score} {r.away_team}")
