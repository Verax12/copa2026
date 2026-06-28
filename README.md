# Copa 2026 — Análise Preditiva do Campeão

Pipeline em Python que estima a probabilidade de cada uma das 48 seleções
vencer a Copa do Mundo de 2026. Combina ratings Elo, modelo de gols, uma camada
de Machine Learning com dados de jogadores e simulação de Monte Carlo. Roda 100% local.

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m wc2026.run --update                 # usa ensemble (padrão recomendado) + atualiza dados
python -m wc2026.run --engine ml --sims 50000 # motor de ML puro com features de jogador
python -m wc2026.run --engine dixon           # Dixon-Coles clássico (mais rápido)
```

No Mac M4 Pro roda em segundos. Se o `xgboost` reclamar de OpenMP: `brew install libomp`
(ou deixe sem xgboost — o código cai automaticamente no boosting do scikit-learn).

## Arquitetura (camadas)

1. **Dados** (`data.py`, `players.py`) — histórico de TODOS os jogos de seleções
   desde 1872 + quem marcou cada gol (autor, minuto, pênalti) + disputas de pênalti.
   Fonte: `martj42/international_results` (CC0). `--update` rebaixa tudo.

2. **Elo** (`elo.py`) — força por seleção, processada cronologicamente. K-factor por
   importância do jogo, vantagem de mando, placar elástico.

3. **Perfil de jogadores** (`players.py`) — por (seleção, ano): nº de marcadores,
   dependência do artilheiro (top_share), taxa de pênalti, concentração (HHI).
   Capta a ESTRUTURA do ataque, não só o placar.

4. **Motores de gols** (escolha com `--engine`, padrão = `ensemble`):
   - `ensemble` — **recomendado**: blend 50/50 das matrizes de placar de Dixon-Coles + ML.
   - `dixon` — **Dixon-Coles** clássico: duas Poisson acopladas + correção rho + decaimento temporal.
   - `ml` — **gradient boosting Poisson** (XGBoost ou sklearn) com features de Elo + perfil de jogadores.

5. **Calibração V/E/D** (`outcome_calibration.py`) — correção pós-modelo treinada
   em validação temporal, reescalando a matriz de placares para melhorar as
   probabilidades de vitória/empate/derrota. Desligue com `--no-calibration`.

6. **Pênaltis calibrados** (`shootout.py`) — probabilidade de vencer a disputa
   ajustada no histórico real (≈ moeda ao ar, leve vantagem ao favorito).

7. **Monte Carlo** (`simulate.py` + `bracket.py`) — joga o torneio N vezes. Jogos
   já realizados entram com placar real; o resto é amostrado. Classifica 1º+2º de
   cada grupo + 8 melhores terceiros (formato 2026) e roda o mata-mata usando o
   **chaveamento OFICIAL da FIFA** (jogos 73-104), incluindo a tabela das 495
   combinações de alocação dos terceiros (Annex C, embutida em `bracket_data.py`).
   Ver o caminho de uma seleção: `python -m wc2026.run --path Brazil`.

## Dados granulares ao vivo (finalizações, chutes no alvo, ...)

Esses dados não estão na base pública. Duas fontes estão conectadas, ambas
gravando em cache local (`api_cache/`):

**1. TheSportsDB — gratuito, é o que usamos hoje** (`thesportsdb.py`). A chave
pública "3" libera a Copa 2026 (league=4429) com estatísticas de finalização por
jogo (chutes no alvo/total/bloqueados). É a fonte ativa porque o plano grátis da
API-Football NÃO dá acesso à season 2026 (ver abaixo).

```bash
python -m wc2026.thesportsdb --pull     # baixa eventos + stats da Copa 2026
python -m wc2026.thesportsdb            # mostra o que já está em cache
```

Limitações honestas do tier grátis: cobertura com atraso (nem todos os jogos já
disputados aparecem) e só finalizações (sem posse/xG). Chutes no alvo bastam para
o xG-proxy do `live_form`. Uma chave própria via `TSDB_KEY` amplia a cobertura.

**2. API-Football** (`api_football.py`) — mais rica (posse, escanteios, escalações,
ratings 0-10), mas o **plano grátis só cobre seasons 2022–2024**; a Copa 2026 exige
plano pago. O conector está pronto e o pipeline combina as duas fontes
automaticamente (com dedup, preferindo a API-Football quando ambas têm o jogo):

```bash
export API_FOOTBALL_KEY="sua_chave"          # dashboard.api-football.com (plano pago p/ 2026)
python -m wc2026.api_football --pull-stats    # baixa stats + lineups + jogadores
```

### Ajuste de forma ao vivo (`live_form.py`)

Os dados granulares só existem para os jogos da própria Copa 2026 (a base pública
não os tem), então NÃO entram como colunas de treino do modelo de gols — ficariam
vazias em ~todas as 49 mil linhas históricas. Em vez disso, alimentam uma camada
de **ajuste ao vivo**: a partir das finalizações/chutes no alvo dos jogos já
disputados, estima-se o xG-proxy de cada seleção, compara-se com o que o modelo
esperava e gera-se um multiplicador de ataque/defesa por seleção (com encolhimento
por tamanho de amostra). Esses multiplicadores reescalam o λ dos jogos FUTUROS na
simulação — sem vazamento, pois os jogos já disputados entram com placar real.

```bash
python -m wc2026.thesportsdb --pull          # 1) baixa os dados granulares (grátis)
python -m wc2026.run --live                  # 2) ensemble (padrão) + ajuste ao vivo
python -m wc2026.run --engine ml --live      #    motor ML + ajuste ao vivo
python -m wc2026.run --engine dixon --live   #    Dixon-Coles + ajuste ao vivo
python -m wc2026.live_form                    # inspeciona os multiplicadores reais
python -m wc2026.live_form --demo            # demonstra o efeito com dados sintéticos
.venv/bin/python tests/test_live_form.py     # testes do parser e dos multiplicadores
.venv/bin/python tests/test_thesportsdb.py   # testes do conector + dedup de fontes
```

Sem cache (`api_cache/` vazio), `--live` apenas avisa e segue sem ajuste.

## Como cada coisa testa

Cada módulo roda sozinho para inspeção:
```bash
python -m wc2026.elo          # top seleções por Elo
python -m wc2026.players      # perfil ofensivo e artilheiros
python -m wc2026.shootout     # calibração de pênaltis
python -m wc2026.ml_model     # validação out-of-time + importância das features
python -m wc2026.prediction_test  # backtest pré-Copa vs jogos reais atuais
```

## Dashboard web

Painel visual (design FIFA 2026) ligado aos dados reais do modelo, em `web/`:

```bash
scripts/generate_web_data.sh       # gera web/wc_data.js (ensemble por padrão, 200k sims)
python -m http.server 8765 --directory web   # abra http://127.0.0.1:8765
# ou: ./web/serve.sh
```

5 abas: visão geral (termômetro de título), etapas (grupos + bracket oficial
interativo), calendário com filtros/deep links, por seleção e comparador.
Detalhes em [web/README.md](web/README.md).

## Limitações e próximos passos

- ~~**Chaveamento do mata-mata**: re-seeding por Elo~~ — **FEITO**: agora usa o
  bracket oficial da FIFA (`bracket.py`), com a tabela completa dos 8 terceiros.
  O re-seeding antigo inflava os favoritos (mantinha-os afastados); o bracket fixo
  dá caminhos honestos e mostra o "lado da chave" de cada seleção (`--path`).
- **Dados granulares no modelo**: integrados via ajuste de forma ao vivo
  (`live_form.py`, flag `--live`), não como colunas de treino — ver acima o porquê.
  Evoluções possíveis: incorporar o rating médio da escalação real (`/fixtures/players`)
  ao multiplicador, e calibrar `XG_PER_SOT`/`SHRINK_TAU` contra os resultados que
  forem saindo.
- **Calibração contínua**: rodar `--update` a cada rodada e medir Brier/log-loss
  contra os resultados reais para afinar `half_life_days` e o K-factor.
