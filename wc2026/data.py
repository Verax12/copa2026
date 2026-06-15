"""
Carga dos dados históricos de jogos de seleções.

Fonte: martj42/international_results (CC0, atualizado quase em tempo real).
Cobre 1872 -> hoje, incluindo os jogos da Copa 2026 já realizados.

Para atualizar a base durante a Copa, basta rodar:
    python -m wc2026.data --update
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import pandas as pd

DATA_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
CSV_PATH = Path(__file__).resolve().parent.parent / "results.csv"


def update_csv(path: Path = CSV_PATH) -> None:
    """Baixa a versão mais recente da base (rode antes de cada nova análise)."""
    print(f"Baixando base de {DATA_URL} ...")
    urllib.request.urlretrieve(DATA_URL, path)
    print(f"Salvo em {path}")


def load_matches(path: Path = CSV_PATH) -> pd.DataFrame:
    """Carrega os jogos JÁ realizados (com placar), tipados e ordenados por data."""
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.dropna(subset=["home_score", "away_score"]).copy()
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)
    df["neutral"] = df["neutral"].astype(str).str.upper().eq("TRUE")
    return df.sort_values("date").reset_index(drop=True)


def load_played_wc2026(path: Path = CSV_PATH) -> pd.DataFrame:
    """Jogos da Copa 2026 que JÁ aconteceram (para fixar resultados na simulação)."""
    df = load_matches(path)
    mask = (df["tournament"] == "FIFA World Cup") & (df["date"] >= "2026-01-01")
    return df[mask].reset_index(drop=True)


if __name__ == "__main__":
    if "--update" in sys.argv:
        update_csv()
    m = load_matches()
    print(f"{len(m):,} jogos carregados ({m.date.min().date()} a {m.date.max().date()}).")
    print(f"Jogos da Copa 2026 já realizados: {len(load_played_wc2026())}")
