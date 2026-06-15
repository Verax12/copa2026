"""
Perfil ofensivo por seleção, derivado de QUEM marca os gols (goalscorers.csv).

Em vez de tratar a seleção como uma caixa-preta de placares, olhamos a
estrutura do ataque. Por (seleção, ano) calculamos:
  - goals          : total de gols marcados no período
  - n_scorers      : nº de marcadores distintos (profundidade ofensiva)
  - top_share      : % dos gols feita pelo artilheiro principal (dependência)
  - pen_rate       : % dos gols que saíram de pênalti
  - hhi            : índice de concentração (1 = um só goleador; ~0 = bem distribuído)

Uso no modelo: features pré-jogo SEM vazamento — para um jogo no ano D,
usamos o perfil do ano D-1 (já consolidado). Para a Copa 2026, usamos 2024-2026.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CSV_PATH = Path(__file__).resolve().parent.parent / "goalscorers.csv"


def load_goalscorers(path: Path = CSV_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.dropna(subset=["team", "scorer"]).copy()
    df["own_goal"] = df["own_goal"].astype(str).str.upper().eq("TRUE")
    df["penalty"] = df["penalty"].astype(str).str.upper().eq("TRUE")
    df = df[~df["own_goal"]]  # gol contra não é mérito ofensivo do 'team'
    df["year"] = df["date"].dt.year
    return df


def _profile(rows: pd.DataFrame) -> dict[str, float]:
    n = len(rows)
    if n == 0:
        return {"goals": 0, "n_scorers": 0, "top_share": 0.0, "pen_rate": 0.0, "hhi": 0.0}
    by_scorer = rows["scorer"].value_counts()
    shares = (by_scorer / n).to_numpy()
    return {
        "goals": n,
        "n_scorers": int(by_scorer.size),
        "top_share": float(shares[0]),
        "pen_rate": float(rows["penalty"].mean()),
        "hhi": float(np.sum(shares ** 2)),
    }


def yearly_profiles(df: pd.DataFrame) -> dict[tuple[str, int], dict[str, float]]:
    """{(seleção, ano): perfil}. Consultado com ano-1 para evitar vazamento."""
    out: dict[tuple[str, int], dict[str, float]] = {}
    for (team, year), rows in df.groupby(["team", "year"]):
        out[(team, year)] = _profile(rows)
    return out


def window_profile(df: pd.DataFrame, team: str, year_from: int, year_to: int) -> dict[str, float]:
    """Perfil agregado de uma janela de anos (ex.: 2024-2026 para a Copa)."""
    rows = df[(df["team"] == team) & (df["year"] >= year_from) & (df["year"] <= year_to)]
    return _profile(rows)


def top_scorers(df: pd.DataFrame, team: str, year_from: int, n: int = 5) -> pd.Series:
    rows = df[(df["team"] == team) & (df["year"] >= year_from)]
    return rows["scorer"].value_counts().head(n)


if __name__ == "__main__":
    df = load_goalscorers()
    print(f"{len(df):,} gols catalogados ({df.year.min()}-{df.year.max()})\n")
    for team in ["Brazil", "Argentina", "France"]:
        p = window_profile(df, team, 2024, 2026)
        print(f"{team} (2024-26): {p['goals']} gols, {p['n_scorers']} marcadores, "
              f"top_share={p['top_share']:.0%}, pênaltis={p['pen_rate']:.0%}")
        print("   artilheiros:", dict(top_scorers(df, team, 2024, 3)))
