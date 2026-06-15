# HANDOFF — Projeto "Copa 2026: Análise Preditiva do Campeão"

> Documento para o **Claude Code** assumir o projeto e continuar o desenvolvimento
> localmente na máquina do William (Mac M4 Pro). Lê isto primeiro, depois o `README.md`.

---

## 1. O que é o projeto

Um pipeline em Python que estima a **probabilidade de cada uma das 48 seleções
vencer a Copa do Mundo de 2026**. A Copa está acontecendo AGORA (começou em
11/06/2026, fase de grupos até 27/06). A ideia não é prever do zero: o modelo
treina no histórico e **reavalia conforme os jogos reais acontecem** — jogos já
disputados entram com placar real, o resto é simulado.

O dono do projeto é o **William** (Senior Software Engineer, forte em Python).
Ele quer previsão cada vez mais assertiva, com granularidade de dados de jogo e
de jogadores. Tudo roda **local** (não precisa de nuvem; futebol de seleção não
é big data).

---

## 2. Estado atual — TUDO ABAIXO JÁ FUNCIONA

O pipeline está completo e validado ponta a ponta. Camadas:

1. **Dados** (`wc2026/data.py`, `wc2026/players.py`) — histórico de todos os jogos
   de seleções desde 1872 + autores de gols + disputas de pênalti.
   Fonte: repositório público `martj42/international_results` (licença CC0).
   `python -m wc2026.data --update` rebaixa os três CSVs.

2. **Elo** (`wc2026/elo.py`) — rating de força por seleção, passe cronológico.
   K-factor por importância do jogo, vantagem de mando, multiplicador de margem.

3. **Perfil de jogadores** (`wc2026/players.py`) — por (seleção, ano): nº de
   marcadores distintos, dependência do artilheiro (`top_share`), taxa de pênalti,
   concentração (HHI). Sai de `goalscorers.csv`.

4. **Dois motores de gols** (selecionáveis por `--engine`):
   - `dixon` → **Dixon-Coles** (`wc2026/goal_model.py`): duas Poisson acopladas,
     MLE com decaimento temporal (meia-vida 2 anos).
   - `ml` → **gradient boosting Poisson** (`wc2026/ml_model.py`): XGBoost (com
     fallback automático para `HistGradientBoostingRegressor` do sklearn) sobre
     features ricas geradas em `wc2026/features.py`.

5. **Pênaltis calibrados** (`wc2026/shootout.py`) — P(vencer disputa) ajustada
   por regressão logística em 678 disputas reais. Resultado: ≈ 50/50 com leve
   vantagem ao favorito (beta ≈ 0.0011).

6. **Monte Carlo** (`wc2026/simulate.py`) — joga o torneio N vezes. Fase de grupos
   (1º+2º + 8 melhores terceiros = 32) e mata-mata até a final. Agrega % de título,
   final, semifinal e classificação por seleção.

7. **Conector API-Football** (`wc2026/api_football.py`) — PRONTO mas ainda NÃO
   integrado às features (ver seção 5). Baixa escanteios, cartões, posse,
   finalizações, escalações e ratings 0-10 por jogador. Precisa de chave.

### Resultados de referência (sanity check)
Com `--engine dixon`, ~10k sims, as favoritas saem Espanha (~27%), Argentina
(~26%), Inglaterra (~10%), França (~9%), Brasil (~8%) — coerente com Elo, ranking
FIFA e casas de apostas. Com `--engine ml`, Argentina e Espanha trocam de lugar
(o ML valoriza o ataque produtivo da Argentina via features de jogador).

### Validação honesta do ML
Out-of-time (treino < 2024, teste 2024+): acurácia ~60% (≈ baseline de Elo), mas
**log-loss melhora de 0.91 → 0.87**. No futebol o teto de acurácia é baixo (muito
acaso); o ganho real do ML está na **calibração** das probabilidades, que é o que
o Monte Carlo aproveita. NÃO prometer ao William saltos de acurácia — o valor está
na calibração e na granularidade.

---

## 3. Setup e comandos

```bash
cd copa2026
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # se xgboost reclamar de OpenMP: brew install libomp

# os CSVs já vêm no zip; para atualizar com os jogos mais recentes da Copa:
python -m wc2026.data --update

# rodar o pipeline:
python -m wc2026.run                       # Dixon-Coles, 10k sims
python -m wc2026.run --engine ml --sims 50000

# inspecionar módulos isolados:
python -m wc2026.elo
python -m wc2026.players
python -m wc2026.shootout
python -m wc2026.ml_model                  # validação out-of-time + importância
python -m wc2026.features
```

### Permissões que você (Claude Code) vai precisar
- **Rede**: `raw.githubusercontent.com` (dados) e, se for usar o conector,
  `v3.football.api-sports.io` (API-Football).
- **Instalar pacotes** via pip (xgboost, scikit-learn, requests).
- **Ler/escrever arquivos** dentro de `copa2026/` (gera `api_cache/`, pode gerar
  saídas em CSV/parquet).

### Chave da API-Football (para dados granulares ao vivo)
```bash
export API_FOOTBALL_KEY="a_chave_do_william"   # criar em dashboard.api-football.com
python -m wc2026.api_football --pull-stats      # baixa stats+lineups+players para api_cache/
```
Plano grátis ~100 req/dia; cada jogo gasta ~3 req. O cache evita rebaixar.
A Copa é `league=1`, `season=2026`.

---

## 4. Decisões de design e armadilhas (LEIA antes de mexer)

- **Sem vazamento temporal**: `features.build_features` faz um único passe
  cronológico e grava o estado ANTES de cada jogo, atualizando só DEPOIS. Se for
  adicionar features novas, mantenha essa regra — nunca use dado pós-jogo no
  vetor de features daquele jogo.
- **Grafia das seleções**: os nomes em `wc2026/groups.py` precisam bater
  EXATAMENTE com o dataset (`Czech Republic`, `Ivory Coast`, `DR Congo`,
  `Curaçao`, `South Korea`, `Bosnia and Herzegovina`...). Se introduzir outra
  fonte (ex.: API-Football usa outros nomes), faça um mapa de/para.
- **4 vagas de playoff resolvidas**: Grupo B → Bosnia and Herzegovina; D → Turkey;
  I → Iraq; K → DR Congo (confirmadas pelos jogos reais já na base).
- **xgboost é opcional**: `ml_model._make_regressor()` cai no sklearn se faltar.
  Não quebrar esse fallback.
- **MLGoalModel** (em `ml_model.py`) pré-computa os gols esperados de todos os
  pares de uma vez (rápido) e expõe `score_matrix` igual ao Dixon-Coles, então o
  `simulate.py` usa qualquer um dos motores sem mudança.
- **Os CSVs NÃO devem ir pro git** se virar repositório (são dados externos
  reproduzíveis via `--update`). Incluídos no zip só por conveniência.

---

## 5. O que falta — backlog priorizado

### P1 — Integrar os dados granulares da API-Football ao modelo (maior valor)
O `api_football.py` já baixa tudo, mas `features.py` ainda só usa Elo + forma +
perfil de gols. Tarefa:
1. Escrever um parser dos JSONs em `api_cache/` (há um começo: `api_football.stats_to_rows`).
2. Construir, por seleção e janela recente, médias de: posse, finalizações,
   finalizações no alvo, escanteios, cartões, faltas — e ratings médios de
   escalação por posição (a partir de `/fixtures/players`).
3. Adicionar essas colunas em `features.FEATURE_COLS` e em `features.match_row`,
   garantindo o tratamento sem vazamento (usar janela até a data do jogo).
4. Re-treinar e re-validar com `evaluate_out_of_time`; comparar log-loss.

### P2 — Bracket oficial da FIFA no mata-mata
Hoje `simulate.py` usa re-seeding por Elo (aproximação). O William quer ver o
caminho real do Brasil. Implementar a tabela fixa de chaveamento da Copa 2026,
incluindo a regra de alocação dos 8 melhores terceiros (depende de QUAIS grupos
classificam o 3º — a FIFA tem uma tabela de combinações). Substituir o laço
`while len(round_teams) > 1` por emparelhamento fixo (1A, 1B, ... + terceiros).

### P3 — Calibração contínua durante a Copa
Criar um script que, a cada rodada, roda `--update`, recalcula as probabilidades
e mede Brier score / log-loss contra os resultados que foram saindo. Usar isso
para afinar `goal_model.half_life_days` e o `K_BY_TOURNAMENT` do Elo.

### P4 (nice-to-have)
- Dashboard simples (Streamlit) mostrando a % de campeão e a evolução por rodada.
- Persistir os ratings/treinos em disco para não recomputar a cada run.
- Modo ensemble: blend das probabilidades Dixon-Coles + ML.

---

## 6. Mapa de arquivos

```
copa2026/
  README.md            visão geral e uso
  HANDOFF.md           este arquivo
  requirements.txt
  results.csv          snapshot do histórico de jogos (atualizar com --update)
  goalscorers.csv      snapshot dos autores de gols
  shootouts.csv        snapshot das disputas de pênalti
  wc2026/
    __init__.py
    data.py            carga/atualização dos CSVs
    groups.py          os 12 grupos / 48 seleções da Copa 2026
    elo.py             ratings Elo
    players.py         perfil ofensivo por seleção (dados de jogador)
    goal_model.py      motor Dixon-Coles
    features.py        engenharia de features sem vazamento + estado atual
    ml_model.py        motor de ML (boosting Poisson) + validação + MLGoalModel
    shootout.py        calibração de pênaltis
    simulate.py        Monte Carlo do torneio
    api_football.py    conector da API-Football (escanteios/cartões/lineups/ratings)
    run.py             orquestra tudo (CLI)
```

Boa! O projeto está saudável e modular. Comece validando que `python -m wc2026.run`
roda limpo, depois ataque o P1. — Claude (web)
