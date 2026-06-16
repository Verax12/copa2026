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
    """Baixa a versão mais recente da base (rode antes de cada nova análise).
    Também atualiza a fonte fresca (openfootball), que costuma ter os jogos do dia
    antes da martj42."""
    print(f"Baixando base de {DATA_URL} ...")
    urllib.request.urlretrieve(DATA_URL, path)
    print(f"Salvo em {path}")
    try:
        from . import openfootball
        n = openfootball.fetch()
        print(f"openfootball: {n} jogos da Copa com placar (fonte fresca).")
    except Exception as e:
        print(f"openfootball indisponível ({e}); seguindo só com a martj42.")


def _overlay_openfootball(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta os jogos da Copa 2026 que o openfootball já tem com placar e que
    ainda não estão na base martj42 (dedup por data + par de seleções). A martj42
    continua autoritativa para o que ela já tem; o openfootball só preenche o gap."""
    try:
        from . import openfootball
        extra = openfootball.played_games()
    except Exception:
        return df
    if extra is None or extra.empty:
        return df
    have = set()
    wc = df[(df["tournament"] == "FIFA World Cup") & (df["date"] >= "2026-01-01")]
    for r in wc.itertuples(index=False):
        have.add((str(r.date)[:10], frozenset((r.home_team, r.away_team))))
    add = [r._asdict() for r in extra.itertuples(index=False)
           if (str(r.date)[:10], frozenset((r.home_team, r.away_team))) not in have]
    if not add:
        return df
    merged = pd.concat([df, pd.DataFrame(add)], ignore_index=True)
    return merged.sort_values("date").reset_index(drop=True)


def load_matches(path: Path = CSV_PATH) -> pd.DataFrame:
    """Carrega os jogos JÁ realizados (com placar), tipados e ordenados por data.
    Sobrepõe os jogos recentes do openfootball (fonte mais fresca) se houver cache."""
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.dropna(subset=["home_score", "away_score"]).copy()
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)
    df["neutral"] = df["neutral"].astype(str).str.upper().eq("TRUE")
    df = df.sort_values("date").reset_index(drop=True)
    return _overlay_openfootball(df)


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
