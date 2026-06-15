"""
Conector da API-Football (api-sports.io) para os dados granulares da Copa 2026:
escalações, estatísticas de jogo (escanteios, cartões, posse, finalizações,
faltas) e ratings/stats por jogador.

>>> NÃO roda no sandbox do Claude (precisa de chave e acesso ao domínio).
>>> Rode no SEU Mac:

    export API_FOOTBALL_KEY="sua_chave_aqui"      # crie em dashboard.api-football.com
    python -m wc2026.api_football --pull-fixtures   # baixa todos os jogos da Copa
    python -m wc2026.api_football --pull-stats      # baixa stats + lineups + jogadores

Os dados são salvos em cache local (pasta api_cache/) como JSON, para você
processar offline e alimentar o modelo. A Copa é league=1, season=2026.

Plano gratuito: ~100 req/dia. Cada jogo gasta ~3 req (stats+lineups+players),
então dá para varrer a Copa aos poucos; o cache evita rebaixar o que já tem.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import requests

BASE = "https://v3.football.api-sports.io"
WORLD_CUP_LEAGUE = 1
SEASON = 2026
CACHE = Path(__file__).resolve().parent.parent / "api_cache"
CACHE.mkdir(exist_ok=True)


def _headers() -> dict[str, str]:
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise RuntimeError("Defina a variável de ambiente API_FOOTBALL_KEY.")
    return {"x-apisports-key": key}


def _get(endpoint: str, params: dict, cache_name: str | None = None) -> dict:
    """GET com cache em disco. Respeita um intervalo mínimo entre chamadas."""
    if cache_name:
        fp = CACHE / f"{cache_name}.json"
        if fp.exists():
            return json.loads(fp.read_text())
    resp = requests.get(f"{BASE}/{endpoint}", headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if cache_name:
        (CACHE / f"{cache_name}.json").write_text(json.dumps(data))
    time.sleep(1.0)  # gentil com o rate limit
    return data


def pull_fixtures() -> list[dict]:
    """Todos os jogos da Copa 2026 (id, times, placar, status)."""
    data = _get("fixtures", {"league": WORLD_CUP_LEAGUE, "season": SEASON}, "fixtures")
    fixtures = data.get("response", [])
    print(f"{len(fixtures)} jogos da Copa 2026 obtidos.")
    return fixtures


def pull_fixture_statistics(fixture_id: int) -> dict:
    """Estatísticas de time por jogo: posse, escanteios, finalizações, cartões, faltas..."""
    return _get("fixtures/statistics", {"fixture": fixture_id}, f"stats_{fixture_id}")


def pull_lineups(fixture_id: int) -> dict:
    """Escalações: titulares, formação tática e banco."""
    return _get("fixtures/lineups", {"fixture": fixture_id}, f"lineup_{fixture_id}")


def pull_fixture_players(fixture_id: int) -> dict:
    """Stats por jogador no jogo, incluindo rating 0-10, passes, dribles, desarmes."""
    return _get("fixtures/players", {"fixture": fixture_id}, f"players_{fixture_id}")


def pull_team_squad_stats(team_id: int) -> dict:
    """Stats agregadas de cada jogador da seleção na temporada."""
    return _get("players", {"team": team_id, "season": SEASON, "league": WORLD_CUP_LEAGUE},
                f"squad_{team_id}")


def pull_all_stats() -> None:
    """Varre todos os jogos JÁ realizados e baixa stats + lineups + players."""
    fixtures = pull_fixtures()
    done = 0
    for fx in fixtures:
        status = fx["fixture"]["status"]["short"]
        if status not in ("FT", "AET", "PEN"):   # só jogos finalizados têm stats completas
            continue
        fid = fx["fixture"]["id"]
        pull_fixture_statistics(fid)
        pull_lineups(fid)
        pull_fixture_players(fid)
        done += 1
        print(f"  baixado fixture {fid} "
              f"({fx['teams']['home']['name']} x {fx['teams']['away']['name']})")
    print(f"Pronto: {done} jogos com estatística detalhada em {CACHE}/")


# ---- normalização: dos JSONs crus para tabelas que alimentam o modelo ----
STAT_KEYS = ["Ball Possession", "Total Shots", "Shots on Goal", "Corner Kicks",
             "Fouls", "Yellow Cards", "Red Cards", "Offsides", "Goalkeeper Saves"]


def stats_to_rows(stats_json: dict) -> list[dict]:
    """Converte o JSON de /fixtures/statistics em linhas {time, métrica: valor}."""
    rows = []
    for team_block in stats_json.get("response", []):
        team = team_block["team"]["name"]
        row = {"team": team}
        for item in team_block["statistics"]:
            if item["type"] in STAT_KEYS:
                v = item["value"]
                if isinstance(v, str) and v.endswith("%"):
                    v = float(v.rstrip("%")) / 100.0
                row[item["type"]] = v
        rows.append(row)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull-fixtures", action="store_true")
    ap.add_argument("--pull-stats", action="store_true")
    args = ap.parse_args()
    if args.pull_fixtures:
        pull_fixtures()
    if args.pull_stats:
        pull_all_stats()
    if not (args.pull_fixtures or args.pull_stats):
        print(__doc__)
