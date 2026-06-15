"""
Teste autônomo do chaveamento oficial (wc2026/bracket.py + bracket_data.py).

Valida: cobertura das 495 combinações, elegibilidade dos terceiros em TODAS elas,
e que resolve_r32 produz exatamente 32 times distintos (24 + 8 terceiros).

    .venv/bin/python tests/test_bracket.py
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wc2026 import bracket as B
from wc2026.bracket_data import THIRD_PLACE_TABLE, SLOT_ORDER
from wc2026.groups import GROUPS

# elegibilidade oficial por slot (grupos cujos terceiros aquele slot pode receber)
ELIG = {"A": set("CEFHI"), "B": set("EFGIJ"), "D": set("BEFIJ"), "E": set("ABCDF"),
        "G": set("AEHIJ"), "I": set("CDFGH"), "K": set("DEIJL"), "L": set("EHIJK")}


def test_table_coverage():
    # C(12,8) = 495 combinações, todas presentes e únicas
    assert len(THIRD_PLACE_TABLE) == 495, len(THIRD_PLACE_TABLE)
    expected = {"".join(c) for c in itertools.combinations("ABCDEFGHIJKL", 8)}
    assert set(THIRD_PLACE_TABLE) == expected, "faltam/sobram combinações na tabela"
    # cada valor usa cada terceiro da chave exatamente uma vez
    for key, val in THIRD_PLACE_TABLE.items():
        assert len(val) == 8 and set(val) == set(key), (key, val)
    print("  ok  tabela cobre as 495 combinações, cada terceiro usado 1x")


def test_eligibility_all_combos():
    errs = 0
    for combo in itertools.combinations("ABCDEFGHIJKL", 8):
        assign = B.third_assignment(combo)
        for slot, src in assign.items():
            if src not in ELIG[slot]:
                errs += 1
    assert errs == 0, f"{errs} atribuições fora da elegibilidade"
    print("  ok  elegibilidade respeitada nas 495 combinações")


def test_resolve_r32_distinct_32():
    pos, third = {}, {}
    for g, ts in GROUPS.items():
        pos[f"1{g}"] = ts[0]
        pos[f"2{g}"] = ts[1]
        third[g] = ts[2]
    best = list("ABCDEFGH")
    r32 = B.resolve_r32(pos, third, best)
    flat = [t for pair in r32 for t in pair]
    assert len(flat) == 32 and len(set(flat)) == 32, "R32 não tem 32 times distintos"
    expected = set(pos.values()) | {third[g] for g in best}
    assert set(flat) == expected, "R32 != 24 classificados + 8 terceiros"
    print("  ok  resolve_r32: 32 times distintos = 24 (1º/2º) + 8 terceiros")


def test_tree_shape():
    # a árvore consome todos os vencedores sem furos
    assert len(B.R32_SPECS) == 16
    assert len(B.R16_PAIRS) == 8 and sorted(i for p in B.R16_PAIRS for i in p) == list(range(16))
    assert len(B.QF_PAIRS) == 4 and sorted(i for p in B.QF_PAIRS for i in p) == list(range(8))
    assert len(B.SF_PAIRS) == 2 and sorted(i for p in B.SF_PAIRS for i in p) == list(range(4))
    # os 8 slots que recebem terceiros são exatamente SLOT_ORDER
    tslots = sorted(s[1] for pair in B.R32_SPECS for s in pair if s.startswith("T"))
    assert tslots == sorted(SLOT_ORDER)
    print("  ok  árvore R32→R16→QF→SF→Final consome todos os vencedores")


def test_simulation_invariants():
    from wc2026.data import load_matches, load_played_wc2026
    from wc2026.elo import compute_elo
    from wc2026.goal_model import fit_dixon_coles
    from wc2026.simulate import simulate

    m = load_matches()
    elo = compute_elo(m)
    model = fit_dixon_coles(m)
    tab = simulate(model, elo, load_played_wc2026(), n_sims=3000, seed=7)
    # 1 campeão, 2 finalistas, 4 semifinalistas por simulação
    assert abs(tab["champion_%"].sum() - 100) < 1e-6
    assert abs(tab["finalist_%"].sum() - 200) < 1e-6
    assert abs(tab["semifinal_%"].sum() - 400) < 1e-6
    # monotonicidade: champ <= final <= semi <= advance
    bad = tab[(tab["champion_%"] > tab["finalist_%"] + 1e-9) |
              (tab["finalist_%"] > tab["semifinal_%"] + 1e-9) |
              (tab["semifinal_%"] > tab["advance_%"] + 1e-9)]
    assert len(bad) == 0, f"{len(bad)} violações de monotonicidade"
    print("  ok  simulação: somas 100/200/400 e champ≤final≤semi≤avança")


if __name__ == "__main__":
    tests = [test_table_coverage, test_eligibility_all_combos,
             test_resolve_r32_distinct_32, test_tree_shape,
             test_simulation_invariants]
    print(f"Rodando {len(tests)} testes de bracket...\n")
    for t in tests:
        t()
    print(f"\nTodos os {len(tests)} testes passaram.")
