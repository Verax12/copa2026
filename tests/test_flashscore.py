"""
Teste autônomo do leitor de estatísticas do Flashscore (wc2026/flashscore.py).

Valida o parsing do JSON exportado pelo scraper (formato {id:{home,away,statistics}}),
o mapa de nomes e o descarte de jogos com times fora da Copa.

    .venv/bin/python tests/test_flashscore.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wc2026 import flashscore
from wc2026.groups import all_teams

IDX = {t: i for i, t in enumerate(all_teams())}


def _write(tmp: Path):
    data = {
        "AbC123": {
            "stage": "GROUP C", "date": "13.06.2026 18:00", "status": "FINISHED",
            "home": {"name": "Brazil"}, "away": {"name": "Morocco"},
            "statistics": [
                {"category": "Ball Possession", "homeValue": "58%", "awayValue": "42%"},
                {"category": "Goal Attempts", "homeValue": "14", "awayValue": "9"},
                {"category": "Corner Kicks", "homeValue": "7", "awayValue": "3"},
                {"category": "Yellow Cards", "homeValue": "2", "awayValue": "3"},
            ],
        },
        # nomes que precisam do mapa: USA -> United States, Curacao -> Curaçao
        "XyZ999": {
            "home": {"name": "USA"}, "away": {"name": "Curacao"},
            "statistics": [{"category": "Ball Possession", "homeValue": "61%", "awayValue": "39%"}],
        },
        # jogo de clube / time fora da Copa -> deve ser ignorado
        "Zzz000": {
            "home": {"name": "Flamengo RJ"}, "away": {"name": "Palmeiras"},
            "statistics": [{"category": "Corner Kicks", "homeValue": "5", "awayValue": "4"}],
        },
    }
    (tmp / "flashscore.json").write_text(json.dumps(data))


def test_parse_and_map():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write(tmp)
        old = flashscore.CACHE
        flashscore.CACHE = tmp
        try:
            rows = flashscore.match_stats_rows(IDX)
        finally:
            flashscore.CACHE = old

    # 2 jogos válidos (o de clube é descartado)
    assert len(rows) == 2, f"esperava 2, veio {len(rows)}"
    inv = {i: t for t, i in IDX.items()}
    pairs = {frozenset((inv[r["h"]], inv[r["a"]])) for r in rows}
    assert frozenset(("Brazil", "Morocco")) in pairs
    assert frozenset(("United States", "Curaçao")) in pairs, "USA/Curacao não mapearam"

    bm = next(r for r in rows if frozenset((inv[r["h"]], inv[r["a"]])) == frozenset(("Brazil", "Morocco")))
    cats = {s["pt"] for s in bm["stats"]}
    assert {"Posse de bola", "Finalizações", "Escanteios", "Cartões amarelos"} <= cats, cats
    poss = next(s for s in bm["stats"] if s["pt"] == "Posse de bola")
    assert poss["home"] == 58.0 and poss["away"] == 42.0, "posse não parseou (% -> número)"
    assert bm["src"] == "Flashscore"
    print("  ok  flashscore: 2 jogos, nomes mapeados, clube descartado, posse 58/42")


def test_empty_is_safe():
    with tempfile.TemporaryDirectory() as d:
        old = flashscore.CACHE
        flashscore.CACHE = Path(d)
        try:
            rows = flashscore.match_stats_rows(IDX)
        finally:
            flashscore.CACHE = old
    assert rows == []
    print("  ok  sem arquivo: devolve [] (seguro)")


if __name__ == "__main__":
    tests = [test_parse_and_map, test_empty_is_safe]
    print(f"Rodando {len(tests)} testes de flashscore...\n")
    for t in tests:
        t()
    print(f"\nTodos os {len(tests)} testes passaram.")
