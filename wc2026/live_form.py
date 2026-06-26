"""
Ajuste de "forma ao vivo" a partir dos dados granulares da API-Football.

Ideia central
-------------
O placar de um jogo é uma amostra ruidosa do que aconteceu em campo. Uma seleção
pode vencer por 1x0 finalizando 3 vezes (sorte) ou empatar em 0x0 acertando 8
chutes no alvo (azar). Os dados granulares (finalizações, chutes no alvo, posse,
escanteios) revelam o desempenho POR BAIXO do placar — um proxy de xG.

Esta camada olha SÓ para os jogos da Copa 2026 JÁ disputados, estima quanto cada
seleção produziu de xG-proxy (ataque) e quanto cedeu (defesa), compara com o que
o modelo de gols *esperava* para aqueles confrontos e gera, por seleção, um
multiplicador de ataque e de defesa. Esses multiplicadores reescalam o λ (gols
esperados) dos confrontos FUTUROS na simulação de Monte Carlo.

Sem vazamento temporal
----------------------
Só usa jogos já ocorridos. Na simulação, os jogos já disputados entram com placar
real (ver `simulate._played_lookup`), então o multiplicador só muda os jogos ainda
não jogados — que é exatamente onde a informação nova deve atuar.

Encolhimento (shrinkage)
------------------------
Com 1-2 jogos por seleção a evidência é fraca. O multiplicador é encolhido em
direção a 1.0 por `n / (n + TAU)`: poucos jogos → confia no modelo; mais jogos →
confia mais no observado. Tudo é clipado para uma faixa segura.

Uso
---
    from wc2026.live_form import AdjustedGoalModel, build_team_adjustments
    adj = build_team_adjustments(base_model, played_df)        # dicts de multiplicadores
    model = AdjustedGoalModel(base_model, adj)                 # mesma interface do motor
    # ...passa `model` para simulate() normalmente.

Inspeção:
    python -m wc2026.live_form            # roda com o cache real (api_cache/)
    python -m wc2026.live_form --demo     # gera dados sintéticos e mostra o efeito
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parent.parent / "api_cache"

# Conversão chute-no-alvo -> xG-proxy. ~0.30 gol por chute no alvo é uma
# regularidade empírica conhecida; o chute para fora contribui bem menos.
XG_PER_SOT = 0.30
XG_PER_OFFTARGET = 0.03

# Encolhimento: nº de "jogos equivalentes" de prior no modelo. Maior => mais
# conservador (multiplicador mais perto de 1 com poucos jogos).
SHRINK_TAU = 2.0

# Faixa segura dos multiplicadores (evita explodir com amostras minúsculas).
MULT_LO, MULT_HI = 0.65, 1.55

# Quanto pesa o sinal de finalização vs o sinal de posse/escanteio ao montar o
# xG-proxy. Posse e escanteios são proxies mais fracos; entram com peso pequeno.
W_FINISHING = 1.0
W_TERRITORY = 0.0  # desligado por padrão; chutes já capturam quase tudo

# ---------------------------------------------------------------------------
# Mapa de grafia API-Football -> dataset histórico (martj42).
# A API usa nomes que às vezes divergem do dataset; mapeie de/para aqui.
# Só precisa listar os que DIFEREM — nomes idênticos passam direto.
# ---------------------------------------------------------------------------
NAME_MAP_API_TO_DATASET = {
    "USA": "United States",
    "United States of America": "United States",
    "South Korea": "South Korea",
    "Korea Republic": "South Korea",
    "Republic of Korea": "South Korea",
    "Iran": "Iran",
    "IR Iran": "Iran",
    "Czech Republic": "Czech Republic",
    "Czechia": "Czech Republic",
    "Ivory Coast": "Ivory Coast",
    "Côte d'Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "DR Congo": "DR Congo",
    "Congo DR": "DR Congo",
    "Cabo Verde": "Cape Verde",
    "Türkiye": "Turkey",
    "Turkiye": "Turkey",
    "Bosnia": "Bosnia and Herzegovina",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",  # grafia do TheSportsDB
    "Curacao": "Curaçao",                              # Flashscore (sem cedilha)
}


def normalize_team(name: str) -> str:
    """Converte um nome vindo da API-Football para a grafia do dataset."""
    return NAME_MAP_API_TO_DATASET.get(name, name)


# ---------------------------------------------------------------------------
# Parser do cache
# ---------------------------------------------------------------------------
def _stat_value(team_block: dict, key: str) -> float:
    for item in team_block.get("statistics", []):
        if item.get("type") == key:
            v = item.get("value")
            if v is None:
                return 0.0
            if isinstance(v, str):
                v = v.strip()
                if v.endswith("%"):
                    return float(v.rstrip("%")) / 100.0
                try:
                    return float(v)
                except ValueError:
                    return 0.0
            return float(v)
    return 0.0


def _load_fixtures_index(cache_dir: Path) -> dict[int, dict]:
    """Mapa fixture_id -> {home, away, hg, ag, date, status} a partir de fixtures.json."""
    fp = cache_dir / "fixtures.json"
    if not fp.exists():
        return {}
    data = json.loads(fp.read_text())
    out: dict[int, dict] = {}
    for fx in data.get("response", []):
        fid = fx["fixture"]["id"]
        goals = fx.get("goals", {})
        out[fid] = {
            "home": normalize_team(fx["teams"]["home"]["name"]),
            "away": normalize_team(fx["teams"]["away"]["name"]),
            "hg": goals.get("home"),
            "ag": goals.get("away"),
            "date": fx["fixture"].get("date"),
            "status": fx["fixture"]["status"]["short"],
        }
    return out


def parse_cache(cache_dir: Path = CACHE) -> pd.DataFrame:
    """Lê os stats_*.json do cache e devolve uma linha por (jogo, seleção) com
    finalizações, chutes no alvo, posse, escanteios e — quando há fixtures.json —
    os gols a favor/contra. Tolerante a arquivos faltando."""
    cache_dir = Path(cache_dir)
    if not cache_dir.exists():
        return pd.DataFrame()

    fixtures = _load_fixtures_index(cache_dir)
    rows = []
    for fp in sorted(cache_dir.glob("stats_*.json")):
        try:
            fid = int(fp.stem.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        data = json.loads(fp.read_text())
        blocks = data.get("response", [])
        if len(blocks) != 2:
            # stats incompletos (jogo não finalizado, ou erro de coleta)
            continue
        fx = fixtures.get(fid, {})
        teams = [normalize_team(b["team"]["name"]) for b in blocks]
        for i, b in enumerate(blocks):
            opp = teams[1 - i]
            team = teams[i]
            # gols a favor/contra a partir do fixture (se disponível)
            gf = ga = None
            if fx:
                if team == fx.get("home"):
                    gf, ga = fx.get("hg"), fx.get("ag")
                elif team == fx.get("away"):
                    gf, ga = fx.get("ag"), fx.get("hg")
            rows.append({
                "fixture": fid,
                "date": fx.get("date"),
                "team": team,
                "opponent": opp,
                "shots_total": _stat_value(b, "Total Shots"),
                "shots_on_target": _stat_value(b, "Shots on Goal"),
                "possession": _stat_value(b, "Ball Possession"),
                "corners": _stat_value(b, "Corner Kicks"),
                "goals_for": gf,
                "goals_against": ga,
            })
    df = pd.DataFrame(rows)
    if not df.empty and "date" in df:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    return df


def gather_live_stats(cache_dir: Path = CACHE) -> pd.DataFrame:
    """Reúne os dados granulares de TODAS as fontes disponíveis em um só DataFrame
    (mesmo schema de parse_cache). Hoje: API-Football (stats_*.json) + TheSportsDB
    (tsdb_*.json). Faz dedup por confronto+data, preferindo a API-Football quando
    o mesmo jogo aparece nas duas (stats mais ricas)."""
    frames = []
    api = parse_cache(cache_dir)           # API-Football (vazio no plano grátis)
    if not api.empty:
        api = api.assign(_src="apifootball")
        frames.append(api)
    try:
        from .thesportsdb import load_stats as _tsdb_load
        tsdb = _tsdb_load()
        if not tsdb.empty:
            frames.append(tsdb.assign(_src="thesportsdb"))
    except Exception:
        pass

    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)

    # chave de confronto independente de fonte: par de times (ordenado) + dia
    def _match_key(r):
        pair = tuple(sorted((str(r["team"]), str(r["opponent"]))))
        day = str(r["date"])[:10] if pd.notna(r.get("date")) else ""
        return (pair, day)

    df["_mk"] = df.apply(_match_key, axis=1)
    # preferência: apifootball (0) antes de thesportsdb (1)
    order = {"apifootball": 0, "thesportsdb": 1}
    df["_pref"] = df["_src"].map(order).fillna(9)
    df = (df.sort_values("_pref")
            .drop_duplicates(subset=["_mk", "team"], keep="first")
            .drop(columns=["_mk", "_pref", "_src"])
            .reset_index(drop=True))
    return df


# ---------------------------------------------------------------------------
# xG-proxy e multiplicadores
# ---------------------------------------------------------------------------
def xg_proxy(shots_on_target: float, shots_total: float) -> float:
    """xG-proxy de um time num jogo a partir das finalizações.
    Chutes no alvo valem ~0.30 gol; chutes para fora, bem menos."""
    off_target = max(shots_total - shots_on_target, 0.0)
    return W_FINISHING * (XG_PER_SOT * shots_on_target + XG_PER_OFFTARGET * off_target)


@dataclass
class TeamAdjustments:
    """Multiplicadores por seleção + diagnóstico, para inspeção/depuração."""
    attack: dict[str, float] = field(default_factory=dict)
    defense: dict[str, float] = field(default_factory=dict)
    diag: pd.DataFrame = field(default_factory=pd.DataFrame)

    def att(self, team: str) -> float:
        return self.attack.get(team, 1.0)

    def deff(self, team: str) -> float:
        return self.defense.get(team, 1.0)


def _shrink(ratio: float, n: float) -> float:
    """Encolhe um ratio em direção a 1.0 conforme a amostra (n jogos)."""
    if n <= 0:
        return 1.0
    w = n / (n + SHRINK_TAU)
    mult = 1.0 + w * (ratio - 1.0)
    return float(np.clip(mult, MULT_LO, MULT_HI))


def build_team_adjustments(base_model, stats: pd.DataFrame) -> TeamAdjustments:
    """A partir das estatísticas dos jogos já disputados, gera multiplicadores de
    ataque e defesa por seleção, comparando o xG-proxy observado com o λ que o
    modelo previa para cada confronto.

    base_model: qualquer motor com expected_goals(home, away, neutral=True).
    stats:      DataFrame de parse_cache() (uma linha por jogo+seleção).
    """
    if stats is None or stats.empty:
        return TeamAdjustments()

    # acumula, por seleção: xG-proxy a favor/contra e λ esperado a favor/contra
    acc: dict[str, dict[str, float]] = {}

    def bump(team: str, **kw):
        d = acc.setdefault(team, {"xg_for": 0.0, "xg_against": 0.0,
                                  "lam_for": 0.0, "lam_against": 0.0, "n": 0.0})
        for k, v in kw.items():
            d[k] += v

    # agrupa por jogo para obter os dois lados juntos
    from .venue import expected_goals_with_venue
    for fid, g in stats.groupby("fixture"):
        if len(g) != 2:
            continue
        a_row, b_row = g.iloc[0], g.iloc[1]
        ta, tb = a_row["team"], b_row["team"]
        xg_a = xg_proxy(a_row["shots_on_target"], a_row["shots_total"])
        xg_b = xg_proxy(b_row["shots_on_target"], b_row["shots_total"])
        # λ esperado pelo modelo: Copa neutra, exceto para México/EUA/Canadá
        # quando enfrentam uma seleção não-anfitriã.
        lam_a, lam_b = expected_goals_with_venue(base_model, ta, tb)
        bump(ta, xg_for=xg_a, xg_against=xg_b, lam_for=lam_a, lam_against=lam_b, n=1)
        bump(tb, xg_for=xg_b, xg_against=xg_a, lam_for=lam_b, lam_against=lam_a, n=1)

    attack, defense, diag_rows = {}, {}, []
    for team, d in acc.items():
        n = d["n"]
        # ataque: produziu mais (ou menos) xG do que o modelo esperava?
        att_ratio = d["xg_for"] / d["lam_for"] if d["lam_for"] > 1e-9 else 1.0
        # defesa: cedeu mais (ou menos) xG do que o esperado? >1 => defesa pior
        def_ratio = d["xg_against"] / d["lam_against"] if d["lam_against"] > 1e-9 else 1.0
        att_mult = _shrink(att_ratio, n)
        def_mult = _shrink(def_ratio, n)
        attack[team] = att_mult
        defense[team] = def_mult
        diag_rows.append({
            "team": team, "n": int(n),
            "xg_for": round(d["xg_for"], 2), "lam_for": round(d["lam_for"], 2),
            "att_ratio": round(att_ratio, 2), "att_mult": round(att_mult, 3),
            "xg_against": round(d["xg_against"], 2), "lam_against": round(d["lam_against"], 2),
            "def_ratio": round(def_ratio, 2), "def_mult": round(def_mult, 3),
        })

    diag = (pd.DataFrame(diag_rows).sort_values("att_mult", ascending=False)
            .reset_index(drop=True)) if diag_rows else pd.DataFrame()
    return TeamAdjustments(attack=attack, defense=defense, diag=diag)


# ---------------------------------------------------------------------------
# Wrapper do modelo: mesma interface dos motores, com λ ajustado
# ---------------------------------------------------------------------------
class AdjustedGoalModel:
    """Envolve um motor de gols (DixonColes ou MLGoalModel) e reescala o λ de cada
    confronto pelos multiplicadores de forma ao vivo. Expõe expected_goals e
    score_matrix idênticos, então simulate() usa sem mudança.

        lam' = lam * att[home] * def[away]
        mu'  = mu  * att[away] * def[home]
    """
    # teto de gols na matriz; espelha o MAX_GOALS dos motores
    _MAXG = 10

    def __init__(self, base_model, adjustments: TeamAdjustments):
        self.base = base_model
        self.adj = adjustments
        self.rho = float(getattr(base_model, "rho", 0.0))

    def expected_goals(self, home: str, away: str, neutral: bool = True) -> tuple[float, float]:
        lam, mu = self.base.expected_goals(home, away, neutral=neutral)
        lam *= self.adj.att(home) * self.adj.deff(away)
        mu *= self.adj.att(away) * self.adj.deff(home)
        return float(np.clip(lam, 0.05, 8)), float(np.clip(mu, 0.05, 8))

    def score_matrix(self, home: str, away: str, neutral: bool = True) -> np.ndarray:
        from scipy.stats import poisson
        lam, mu = self.expected_goals(home, away, neutral=neutral)
        g = np.arange(self._MAXG + 1)
        ph = poisson.pmf(g, lam)
        pa = poisson.pmf(g, mu)
        m = np.outer(ph, pa)
        rho = self.rho
        m[0, 0] *= 1.0 - lam * mu * rho
        m[0, 1] *= 1.0 + lam * rho
        m[1, 0] *= 1.0 + mu * rho
        m[1, 1] *= 1.0 - rho
        m = np.clip(m, 1e-12, None)
        return m / m.sum()


# ---------------------------------------------------------------------------
# Demo com dados sintéticos (para validar sem chave de API)
# ---------------------------------------------------------------------------
def _demo_stats() -> pd.DataFrame:
    """Gera estatísticas sintéticas no formato de parse_cache() para dois jogos:
    - Brazil domina mas finaliza pouco no alvo contra Morocco (deveria SUBIR pouco)
    - Spain bombardeia o gol contra Uruguay sem fazer muitos gols (azar -> SUBIR)
    """
    rows = [
        # fixture 1: Brazil 0 x 0 Morocco — Brasil com posse mas pouco perigo
        {"fixture": 1, "team": "Brazil", "opponent": "Morocco",
         "shots_total": 9, "shots_on_target": 2, "possession": 0.62, "corners": 6,
         "goals_for": 0, "goals_against": 0},
        {"fixture": 1, "team": "Morocco", "opponent": "Brazil",
         "shots_total": 5, "shots_on_target": 1, "possession": 0.38, "corners": 2,
         "goals_for": 0, "goals_against": 0},
        # fixture 2: Spain 1 x 0 Uruguay — Espanha criou MUITO mais do que o placar
        {"fixture": 2, "team": "Spain", "opponent": "Uruguay",
         "shots_total": 22, "shots_on_target": 9, "possession": 0.68, "corners": 11,
         "goals_for": 1, "goals_against": 0},
        {"fixture": 2, "team": "Uruguay", "opponent": "Spain",
         "shots_total": 4, "shots_on_target": 1, "possession": 0.32, "corners": 1,
         "goals_for": 0, "goals_against": 1},
    ]
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true",
                    help="usa dados sintéticos em vez do cache real")
    args = ap.parse_args()

    from wc2026.data import load_matches
    from wc2026.goal_model import fit_dixon_coles

    print("Ajustando modelo base (Dixon-Coles) para calcular o λ esperado...")
    base = fit_dixon_coles(load_matches())

    if args.demo:
        stats = _demo_stats()
        print("\n[modo demo] estatísticas sintéticas de 2 jogos.\n")
    else:
        stats = gather_live_stats()
        if stats.empty:
            print(f"\nCache vazio em {CACHE}/. Rode uma das fontes:")
            print("  python -m wc2026.thesportsdb --pull          # gratuito")
            print('  export API_FOOTBALL_KEY="..."  &&  python -m wc2026.api_football --pull-stats')
            print("\nOu veja a demonstração: python -m wc2026.live_form --demo")
            return
        print(f"\n{stats['fixture'].nunique()} jogos com estatística no cache.\n")

    adj = build_team_adjustments(base, stats)
    if adj.diag.empty:
        print("Nenhum ajuste calculado.")
        return

    print("Multiplicadores de forma ao vivo (att>1 ataca acima do esperado; "
          "def>1 defende abaixo):")
    print(adj.diag.to_string(index=False))

    # mostra o efeito num confronto futuro hipotético
    model = AdjustedGoalModel(base, adj)
    print("\nEfeito no λ de confrontos futuros (xg base -> xg ajustado):")
    sample = []
    teams_seen = list(adj.attack.keys())
    for h in teams_seen:
        for a in teams_seen:
            if h != a:
                sample.append((h, a))
    for h, a in sample[:6]:
        lb, mb = base.expected_goals(h, a, neutral=True)
        la, ma = model.expected_goals(h, a, neutral=True)
        print(f"  {h} x {a}: {lb:.2f}-{mb:.2f}  ->  {la:.2f}-{ma:.2f}")


if __name__ == "__main__":
    main()
