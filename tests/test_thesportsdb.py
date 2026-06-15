"""
Teste autônomo do conector TheSportsDB (wc2026/thesportsdb.py) e do
gather_live_stats (combinação de fontes com dedup).

Valida o parsing contra JSON SINTÉTICO no formato do TheSportsDB v1 e a
deduplicação quando o mesmo jogo aparece em duas fontes.

    .venv/bin/python tests/test_thesportsdb.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wc2026 import thesportsdb as tsdb
from wc2026 import live_form as lf


def _write_tsdb_cache(tmp: Path) -> None:
    """Escreve tsdb_events.json + tsdb_stats_*.json no formato TheSportsDB v1."""
    events = {
        "events": [
            {"idEvent": "2391730", "dateEvent": "2026-06-13",
             "strHomeTeam": "Brazil", "strAwayTeam": "Morocco",
             "intHomeScore": "1", "intAwayScore": "1", "strStatus": "FT"},
            # "USA" precisa virar "United States" via mapa
            {"idEvent": "2391731", "dateEvent": "2026-06-13",
             "strHomeTeam": "USA", "strAwayTeam": "Paraguay",
             "intHomeScore": "4", "intAwayScore": "1", "strStatus": "FT"},
            # jogo sem placar ainda: deve ser ignorado
            {"idEvent": "2391999", "dateEvent": "2026-06-20",
             "strHomeTeam": "Spain", "strAwayTeam": "Uruguay",
             "intHomeScore": None, "intAwayScore": None, "strStatus": "NS"},
        ]
    }
    (tmp / "tsdb_events.json").write_text(json.dumps(events))

    def stat_rows(home_sot, away_sot, home_tot, away_tot):
        return {"eventstats": [
            {"strStat": "Shots on Goal", "intHome": home_sot, "intAway": away_sot},
            {"strStat": "Total Shots", "intHome": home_tot, "intAway": away_tot},
            {"strStat": "Shots off Goal", "intHome": "5", "intAway": "5"},
        ]}

    (tmp / "tsdb_stats_2391730.json").write_text(json.dumps(stat_rows("4", "2", "12", "12")))
    (tmp / "tsdb_stats_2391731.json").write_text(json.dumps(stat_rows("6", "1", "16", "9")))


def test_load_stats_schema_and_names():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_tsdb_cache(tmp)
        old = tsdb.CACHE
        tsdb.CACHE = tmp
        try:
            df = tsdb.load_stats()
        finally:
            tsdb.CACHE = old

    # 2 jogos com placar * 2 lados = 4 linhas (o jogo sem placar não tem stats)
    assert len(df) == 4, f"esperava 4 linhas, veio {len(df)}"
    assert "United States" in set(df["team"]), "USA não mapeado p/ United States"
    # colunas no schema esperado por build_team_adjustments
    for col in ["fixture", "date", "team", "opponent", "shots_total",
                "shots_on_target", "goals_for", "goals_against"]:
        assert col in df.columns, f"faltou coluna {col}"
    usa = df[df["team"] == "United States"].iloc[0]
    assert usa["shots_on_target"] == 6.0 and usa["goals_for"] == 4
    print("  ok  load_stats: 4 linhas, nomes mapeados, schema compatível")


def test_gather_dedup_prefers_apifootball():
    """O mesmo jogo em duas fontes deve contar UMA vez, preferindo API-Football."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_tsdb_cache(tmp)
        # API-Football: o MESMO Brazil x Morocco (fixtures.json + stats_*.json)
        (tmp / "fixtures.json").write_text(json.dumps({"response": [{
            "fixture": {"id": 555, "date": "2026-06-13T18:00:00+00:00",
                        "status": {"short": "FT"}},
            "teams": {"home": {"name": "Brazil"}, "away": {"name": "Morocco"}},
            "goals": {"home": 1, "away": 1}}]}))
        (tmp / "stats_555.json").write_text(json.dumps({"response": [
            {"team": {"name": "Brazil"}, "statistics": [
                {"type": "Shots on Goal", "value": 9},      # valor diferente do TSDB
                {"type": "Total Shots", "value": 20}]},
            {"team": {"name": "Morocco"}, "statistics": [
                {"type": "Shots on Goal", "value": 1},
                {"type": "Total Shots", "value": 6}]},
        ]}))
        old_t, old_l = tsdb.CACHE, lf.CACHE
        tsdb.CACHE = tmp
        try:
            df = lf.gather_live_stats(tmp)
        finally:
            tsdb.CACHE, lf.CACHE = old_t, old_l

    # jogos distintos: Brazil-Morocco (1) + USA-Paraguay (1) = 2 jogos
    brazil = df[df["team"] == "Brazil"]
    assert len(brazil) == 1, f"Brazil duplicado entre fontes: {len(brazil)} linhas"
    # preferiu API-Football (SoT=9), não o TheSportsDB (SoT=4)
    assert brazil.iloc[0]["shots_on_target"] == 9.0, "dedup não preferiu API-Football"
    # USA-Paraguay (só no TheSportsDB) continua presente
    assert "United States" in set(df["team"])
    print("  ok  gather_live_stats: dedup por confronto, prefere API-Football")


def test_to_float_handles_percent_and_null():
    assert tsdb._to_float("62%") == 62.0
    assert tsdb._to_float(None) == 0.0
    assert tsdb._to_float("") == 0.0
    assert tsdb._to_float("7") == 7.0
    print("  ok  _to_float: trata %, None e vazio")


if __name__ == "__main__":
    tests = [test_to_float_handles_percent_and_null,
             test_load_stats_schema_and_names,
             test_gather_dedup_prefers_apifootball]
    print(f"Rodando {len(tests)} testes de thesportsdb...\n")
    for t in tests:
        t()
    print(f"\nTodos os {len(tests)} testes passaram.")
