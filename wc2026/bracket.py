"""
Chaveamento OFICIAL do mata-mata da Copa 2026 (FIFA), substituindo o re-seeding
por Elo que era usado como aproximação.

Formato 2026: 12 grupos. Avançam 1º e 2º de cada grupo (24) + os 8 melhores
terceiros = 32 seleções para o Round of 32. A árvore é FIXA: a posição no grupo
determina o confronto, e o caminho de cada seleção até a final é pré-definido.
Isso importa para a probabilidade de título — em bracket fixo o "lado da chave"
em que a seleção caiu pesa (favoritos podem estar na mesma metade), coisa que o
re-seeding por Elo apagava ao manter os fortes sempre afastados.

A parte complexa é a alocação dos 8 terceiros aos 8 slots que os recebem: depende
de QUAIS 8 dos 12 grupos classificaram o 3º. A FIFA publicou uma tabela com as
C(12,8)=495 combinações (Annex C); ela está embutida em `bracket_data.py`.

Referência da estrutura: jogos 73-104 do match schedule oficial.
"""
from __future__ import annotations

from .bracket_data import THIRD_PLACE_TABLE, SLOT_ORDER

# --- Round of 32 (jogos 73-88) -------------------------------------------------
# Cada confronto é um par de "specs" de slot:
#   "1A"/"2B" = vencedor/vice do grupo;  "TE" = o terceiro alocado ao slot do 1E.
R32_SPECS: list[tuple[str, str]] = [
    ("2A", "2B"),   # 73
    ("1E", "TE"),   # 74
    ("1F", "2C"),   # 75
    ("1C", "2F"),   # 76
    ("1I", "TI"),   # 77
    ("2E", "2I"),   # 78
    ("1A", "TA"),   # 79
    ("1L", "TL"),   # 80
    ("1D", "TD"),   # 81
    ("1G", "TG"),   # 82
    ("2K", "2L"),   # 83
    ("1H", "2J"),   # 84
    ("1B", "TB"),   # 85
    ("1J", "2H"),   # 86
    ("1K", "TK"),   # 87
    ("2D", "2G"),   # 88
]

# --- árvore a partir dos vencedores do R32 (índices 0-15 em R32_SPECS) ---------
# Round of 16 (jogos 89-96): cada par produz w16[0..7]
R16_PAIRS = [(1, 4), (0, 2), (3, 5), (6, 7), (10, 11), (8, 9), (13, 15), (12, 14)]
# Quartas (97-100) sobre os índices de w16: produz w8[0..3] (= semifinalistas)
QF_PAIRS = [(0, 1), (4, 5), (2, 3), (6, 7)]
# Semis (101-102) sobre w8: produz os 2 finalistas
SF_PAIRS = [(0, 1), (2, 3)]


def third_assignment(qualifying_third_groups) -> dict[str, str]:
    """Dado o conjunto dos 8 grupos cujos terceiros se classificaram, devolve o
    mapa {grupo_vencedor_slot: grupo_fonte_do_terceiro} conforme a tabela FIFA.
    Ex.: {"A": "E", "E": "F", ...} -> o 1A enfrenta o 3º do grupo E."""
    key = "".join(sorted(qualifying_third_groups))
    assigned = THIRD_PLACE_TABLE[key]   # string de 8 letras na ordem de SLOT_ORDER
    return {slot: src for slot, src in zip(SLOT_ORDER, assigned)}


def resolve_r32(pos: dict[str, str], third_team_by_group: dict[str, str],
                qualifying_third_groups) -> list[tuple[str, str]]:
    """Monta os 16 confrontos do R32 com os times reais.

    pos: {"1A": time, "2A": time, ...} para os 12 grupos.
    third_team_by_group: {grupo: time que terminou em 3º}.
    qualifying_third_groups: os 8 grupos cujos terceiros avançaram.
    """
    assign = third_assignment(qualifying_third_groups)

    def team(spec: str) -> str:
        if spec.startswith("T"):                 # slot de terceiro: "TE" -> 1E vs 3(assign[E])
            return third_team_by_group[assign[spec[1]]]
        return pos[spec]

    return [(team(a), team(b)) for a, b in R32_SPECS]


# --- traçado do caminho de uma seleção até a final ----------------------------
_ROUND_BASE = {"R32": 73, "R16": 89, "QF": 97, "SF": 101}


def _r32_index_of(slot: str) -> int:
    for i, (a, b) in enumerate(R32_SPECS):
        if slot in (a, b):
            return i
    raise ValueError(f"slot {slot!r} não está no Round of 32 (use 1X/2X)")


def _subtrees():
    """Conjuntos de índices de R32 sob cada nó de R16/QF/SF (para descrever os
    'potes' de adversários de cada rodada)."""
    r16 = [set(p) for p in R16_PAIRS]
    qf = [r16[i] | r16[j] for i, j in QF_PAIRS]
    sf = [qf[i] | qf[j] for i, j in SF_PAIRS]
    return r16, qf, sf


def path_to_final(slot: str) -> list[tuple[str, int, list[str]]]:
    """Caminho FIXO de uma seleção que ocupa `slot` (ex.: '1C') até a final.
    Devolve, por rodada: (rodada, nº do jogo, lista de slots-adversários possíveis).
    No R32 o adversário é único; nas rodadas seguintes é um 'pote' de slots."""
    s = _r32_index_of(slot)
    r16, qf, sf = _subtrees()
    a, b = R32_SPECS[s]
    opp_r32 = b if a == slot else a

    # índices dos nós que contêm `s` em cada nível
    r16k = next(k for k, st in enumerate(r16) if s in st)
    qfk = next(k for k, st in enumerate(qf) if s in st)
    sfk = next(k for k, st in enumerate(sf) if s in st)

    def slots_of(r32_indices) -> list[str]:
        out = []
        for i in sorted(r32_indices):
            out.extend(R32_SPECS[i])
        return out

    # potes de adversários: o "outro lado" de cada chave
    opp_r16 = (r16[r16k] - {s})                       # 1 jogo de R32 -> 2 slots
    qi, qj = QF_PAIRS[qfk]
    opp_qf = (qf[qfk] - r16[r16k])                    # a outra chave de R16 -> 4 slots
    si, sj = SF_PAIRS[sfk]
    opp_sf = (sf[sfk] - qf[qfk])                      # a outra chave de QF -> 8 slots
    opp_final = (set(range(16)) - sf[sfk])            # toda a outra metade -> 16 slots

    return [
        ("R32", _ROUND_BASE["R32"] + s, [opp_r32]),
        ("R16", _ROUND_BASE["R16"] + r16k, slots_of(opp_r16)),
        ("QF",  _ROUND_BASE["QF"] + qfk, slots_of(opp_qf)),
        ("SF",  _ROUND_BASE["SF"] + sfk, slots_of(opp_sf)),
        ("Final", 104, slots_of(opp_final)),
    ]


def format_path(team: str, slot: str) -> str:
    rounds = path_to_final(slot)
    lines = [f"Caminho de {team} entrando como {slot}:"]
    names = {"R32": "Round of 32", "R16": "Oitavas", "QF": "Quartas",
             "SF": "Semifinal", "Final": "Final"}
    for rnd, mno, opp in rounds:
        if len(opp) == 1:
            desc = f"vs {opp[0]}"
        else:
            desc = "vs vencedor de {" + ", ".join(opp) + "}"
        lines.append(f"  {names[rnd]:<12} (jogo {mno})  {desc}")
    return "\n".join(lines)


if __name__ == "__main__":
    # sanity: estrutura coerente e cobertura total da tabela
    assert len(R32_SPECS) == 16
    assert len(THIRD_PLACE_TABLE) == 495, len(THIRD_PLACE_TABLE)
    slots_with_third = [s for pair in R32_SPECS for s in pair if s.startswith("T")]
    assert sorted(s[1] for s in slots_with_third) == sorted(SLOT_ORDER)
    # toda combinação aponta para grupos elegíveis e usa cada terceiro 1x
    for key, val in THIRD_PLACE_TABLE.items():
        assert len(val) == 8 and set(val) == set(key), (key, val)
    print(f"OK: R32 com 16 jogos, {len(THIRD_PLACE_TABLE)} combinacoes de terceiros.")
    print("Slots que recebem terceiros:", sorted(s[1] for s in slots_with_third))
    print("Exemplo (terceiros de E,F,G,H,I,J,K,L):", third_assignment(set("EFGHIJKL")))
    # caminho do Brasil (grupo C) ganhando ou ficando em 2º
    print()
    print(format_path("Brazil", "1C"))
    print()
    print(format_path("Brazil", "2C"))
