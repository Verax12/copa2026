"""
Definição da Copa do Mundo 2026: as 48 seleções em 12 grupos.

Os nomes das seleções seguem EXATAMENTE a grafia do dataset histórico
(martj42/international_results), senão o modelo não encontra os jogos.

Os 48 participantes já estão 100% confirmados (a Copa começou em 11/06/2026).
Os 4 slots que eram playoff no sorteio foram resolvidos assim:
  - Grupo B (Europa A)            -> Bosnia and Herzegovina
  - Grupo D (Europa C)            -> Turkey
  - Grupo I (Repescagem Mundial 2)-> Iraq
  - Grupo K (Repescagem Mundial 1)-> DR Congo
"""

GROUPS: dict[str, list[str]] = {
    "A": ["Mexico", "South Africa", "South Korea", "Czech Republic"],
    "B": ["Canada", "Qatar", "Switzerland", "Bosnia and Herzegovina"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Paraguay", "Australia", "Turkey"],
    "E": ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Tunisia", "Sweden"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Norway", "Iraq"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "Uzbekistan", "Colombia", "DR Congo"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

# Países-sede (vantagem leve mesmo em jogo "neutro" da FIFA)
HOSTS = {"United States", "Canada", "Mexico"}


def all_teams() -> list[str]:
    return [t for teams in GROUPS.values() for t in teams]


if __name__ == "__main__":
    teams = all_teams()
    assert len(teams) == 48, f"esperado 48, veio {len(teams)}"
    assert len(set(teams)) == 48, "tem seleção repetida"
    print(f"OK: {len(teams)} seleções em {len(GROUPS)} grupos.")
