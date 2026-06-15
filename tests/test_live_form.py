"""
Teste autônomo da camada de forma ao vivo (wc2026/live_form.py).

Valida o parser contra JSON SINTÉTICO no formato exato da API-Football
(api-sports.io v3) — para garantir que, quando o cache real for populado, o
parsing funcione. Também checa o mapa de nomes, o cálculo de multiplicadores e
o wrapper do modelo.

Roda sem dependências extras (não precisa de pytest):

    .venv/bin/python tests/test_live_form.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# garante que o pacote wc2026 é importável quando rodado direto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wc2026 import live_form as lf


def _write_cache(tmp: Path) -> None:
    """Escreve fixtures.json + stats_*.json no formato real da api-sports."""
    fixtures = {
        "response": [
            {
                "fixture": {"id": 101, "date": "2026-06-13T18:00:00+00:00",
                            "status": {"short": "FT"}},
                "teams": {"home": {"name": "Brazil"}, "away": {"name": "Morocco"}},
                "goals": {"home": 0, "away": 0},
            },
            {
                "fixture": {"id": 102, "date": "2026-06-14T21:00:00+00:00",
                            "status": {"short": "FT"}},
                # nome que PRECISA passar pelo mapa: "USA" -> "United States"
                "teams": {"home": {"name": "Spain"}, "away": {"name": "USA"}},
                "goals": {"home": 1, "away": 0},
            },
        ]
    }
    (tmp / "fixtures.json").write_text(json.dumps(fixtures))

    def stats_block(name, total, sot, poss_pct, corners):
        return {
            "team": {"id": 0, "name": name},
            "statistics": [
                {"type": "Shots on Goal", "value": sot},
                {"type": "Total Shots", "value": total},
                {"type": "Ball Possession", "value": f"{poss_pct}%"},
                {"type": "Corner Kicks", "value": corners},
                {"type": "Fouls", "value": 12},
                {"type": "Yellow Cards", "value": 2},
                {"type": "Red Cards", "value": None},   # api manda null às vezes
                {"type": "Offsides", "value": 1},
                {"type": "Goalkeeper Saves", "value": sot},
            ],
        }

    (tmp / "stats_101.json").write_text(json.dumps({
        "response": [
            stats_block("Brazil", 9, 2, 62, 6),
            stats_block("Morocco", 5, 1, 38, 2),
        ]
    }))
    (tmp / "stats_102.json").write_text(json.dumps({
        "response": [
            stats_block("Spain", 22, 9, 68, 11),
            stats_block("USA", 4, 1, 32, 1),
        ]
    }))
    # arquivo incompleto (jogo não finalizado): deve ser ignorado, não quebrar
    (tmp / "stats_103.json").write_text(json.dumps({"response": []}))


def test_parse_cache():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_cache(tmp)
        df = lf.parse_cache(tmp)

    assert not df.empty, "parser devolveu vazio"
    # 2 jogos válidos * 2 times = 4 linhas (o stats_103 incompleto é ignorado)
    assert len(df) == 4, f"esperava 4 linhas, veio {len(df)}"
    # mapa de nomes aplicado
    assert "United States" in set(df["team"]), "USA não foi mapeado p/ United States"
    assert "USA" not in set(df["team"]), "nome cru 'USA' vazou sem mapeamento"
    # posse vira fração
    spain = df[df["team"] == "Spain"].iloc[0]
    assert abs(spain["possession"] - 0.68) < 1e-9, "posse não foi convertida de %"
    assert spain["shots_on_target"] == 9
    # gols a favor/contra cruzados do fixture
    assert spain["goals_for"] == 1 and spain["goals_against"] == 0
    print("  ok  parse_cache: 4 linhas, nomes mapeados, posse fracionada, gols cruzados")


def test_name_map():
    assert lf.normalize_team("USA") == "United States"
    assert lf.normalize_team("Czechia") == "Czech Republic"
    assert lf.normalize_team("Türkiye") == "Turkey"
    # nome idêntico passa direto
    assert lf.normalize_team("Brazil") == "Brazil"
    print("  ok  normalize_team: mapeia divergências e preserva idênticos")


def test_xg_proxy_monotonic():
    # mais chutes no alvo => maior xG-proxy
    low = lf.xg_proxy(shots_on_target=1, shots_total=5)
    high = lf.xg_proxy(shots_on_target=9, shots_total=22)
    assert high > low > 0
    print(f"  ok  xg_proxy crescente: {low:.2f} < {high:.2f}")


class _StubModel:
    """Motor fake com λ fixo, para testar multiplicadores e wrapper sem treinar."""
    rho = -0.05

    def expected_goals(self, home, away, neutral=True):
        return 1.0, 1.0  # base neutra: qualquer desvio vem do xG-proxy


def test_adjustments_and_wrapper():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_cache(tmp)
        stats = lf.parse_cache(tmp)

    base = _StubModel()
    adj = lf.build_team_adjustments(base, stats)

    # Spain finalizou MUITO (9 no alvo) com base λ=1 => ataque deve subir (>1)
    assert adj.att("Spain") > 1.0, f"Spain att deveria subir, veio {adj.att('Spain')}"
    # United States quase não finalizou => ataque deve cair (<1)
    assert adj.att("United States") < 1.0, "United States att deveria cair"
    # multiplicadores dentro da faixa segura
    for t, v in {**adj.attack, **adj.defense}.items():
        assert lf.MULT_LO <= v <= lf.MULT_HI, f"{t} fora da faixa: {v}"

    # wrapper reescala o λ e mantém a interface
    model = lf.AdjustedGoalModel(base, adj)
    lam, mu = model.expected_goals("Spain", "United States", neutral=True)
    assert lam > 1.0 and mu < 1.0, f"wrapper não reescalou como esperado: {lam:.2f}-{mu:.2f}"
    # score_matrix é uma distribuição de probabilidade válida
    m = model.score_matrix("Spain", "United States", neutral=True)
    assert abs(m.sum() - 1.0) < 1e-6, "score_matrix não soma 1"
    assert (m >= 0).all(), "score_matrix tem probabilidade negativa"
    print(f"  ok  ajuste+wrapper: Spain λ {lam:.2f} > 1, USA λ {mu:.2f} < 1, matriz soma 1")


def test_empty_cache_is_safe():
    with tempfile.TemporaryDirectory() as d:
        df = lf.parse_cache(Path(d))   # cache vazio
    assert df.empty
    adj = lf.build_team_adjustments(_StubModel(), df)
    assert adj.attack == {} and adj.defense == {}
    # att/deff devolvem 1.0 (neutro) para time desconhecido
    assert adj.att("Brazil") == 1.0 and adj.deff("Brazil") == 1.0
    print("  ok  cache vazio: sem ajustes, multiplicadores neutros (1.0)")


if __name__ == "__main__":
    tests = [test_name_map, test_xg_proxy_monotonic, test_parse_cache,
             test_adjustments_and_wrapper, test_empty_cache_is_safe]
    print(f"Rodando {len(tests)} testes de live_form...\n")
    for t in tests:
        t()
    print(f"\nTodos os {len(tests)} testes passaram.")
