# Roadmap de Melhorias no Motor de Predição - Copa 2026

**Objetivo:** Aumentar a precisão das predições do motor (probabilidades de campeão, fases, etc.).

**Abordagem:** Implementar melhorias de forma incremental, priorizando impacto em precisão vs. esforço. Validar com backtests usando dados reais da Copa (até rodada N para prever rodada N+1 e mata-mata).

**Status atual do motor (2026-06-28):**
- Ensemble (Dixon-Coles + ML com features de jogadores)
- Ajuste ao vivo via finalizações (TheSportsDB)
- Calibração de V/E/D
- Simulações Monte Carlo com bracket oficial FIFA
- Validação out-of-time e backtest contra jogos reais

## Os 5 Pontos Prioritários (em ordem)

### 1. Modelar melhor a variância dos gols (Overdispersion)
- **Problema:** Modelos atuais usam Poisson pura, que subestima variância real dos placares (mais empates e extremos do que previsto).
- **Impacto:** Melhora calibração de empates, placares altos e probabilidades de eliminação/previsão de upsets.
- **Sugestões:**
  - Substituir ou estender Poisson por Negative Binomial no ML e/ou Dixon-Coles.
  - Adicionar parâmetro de dispersão.
  - Na simulação, inflar variância de forma controlada.
- **Validação:** Comparar Brier/Log-loss e distribuição de placares previstos vs reais.

### 2. Enriquecer o Ajuste ao Vivo (live_form.py)
- **Problema:** Proxy de xG muito básico (só chutes no alvo com XG_PER_SOT fixo). Poucos dados granulares, shrinkage conservador.
- **Impacto:** Grande para fase de grupos atual, pois ajusta λs futuros com performance real observada.
- **Sugestões:**
  - Melhorar proxy xG (usar mais stats quando disponíveis: posse, escanteios, big chances).
  - Tornar XG_PER_SOT e SHRINK_TAU adaptativos por seleção/jogos.
  - Incluir sinal de território (W_TERRITORY > 0).
  - Adicionar correlação entre ataque e defesa da mesma seleção.
- **Validação:** Ver efeito nos multiplicadores e impacto nas predições vs jogos reais subsequentes.

### 3. Features mais ricas no modelo ML
- **Problema:** Features atuais boas mas limitadas (Elo, forma simples últimos 5, perfil ofensivo anual).
- **Impacto:** Permite ao ML capturar nuances que o Dixon-Coles não vê.
- **Sugestões:**
  - Forma ponderada pela força do oponente (Elo-adjusted).
  - Features de fadiga/viagem/distância entre sedes (específico da Copa 2026 multi-país).
  - Dias de descanso entre jogos.
  - Head-to-head específico.
  - Interações (ex: elo_diff * form).
- **Validação:** Feature importance + ganho em validação out-of-time e backtest.

**Status (2026-06-28, branch improvements/motor-precisao):** Implementado.
- Adicionadas: form_adj_home/away/diff (elo-weighted pts recentes via opp elo ratio), rest_days_home/away (via datas de último jogo por time), h2h_gd (média gd em até 5 h2h passados, sinal correto), elo_x_form (interação), além das gd/form_diff prévias.
- Atualizados: build_features (com tracking last_dates/adj/h2h sem vazamento temporal), current_state (expoe adj_form/last_dates/h2h), match_row (suporta match_date opcional + computa features), FEATURE_COLS (agora 29).
- MLGoalModel: adicionado outcome_probs p/ compat interface (usado em backtests).
- Testes: build_features roda (11k+ rows), ml_model oot (h2h_gd #2 imp 0.092, elo_x_form #4, form_adj #8), prediction_test + backtest(ml) passam end-to-end sem erro.
- Proxy fadiga: rest_days (dias de descanso; viagem implícita em Copa multi-sede via schedule). Sem data de venue para distância full histórica, mas datas permitem rest.
- Sem quebra de callers (ensemble, run, track, etc). Retrain runtime.

### 4. Melhoria na Calibração e no Ensemble
- **Problema:** Ensemble fixo 50/50. Calibração de V/E/D é simples (logistic com features limitadas). Não calibra diretamente probs de fases/campeão.
- **Impacto:** Melhora confiança nas probabilidades finais (evita over/under-confidence).
- **Sugestões:**
  - Peso dinâmico no ensemble (baseado em validação recente ou por tipo de jogo).
  - Calibrador mais avançado (isotonic, por engine, ou baseado em simulações completas).
  - Calibração de probs de campeão/fase diretamente via simulações históricas.
- **Validação:** Brier score nas probs de campeão e acerto de "top N".

### 5. Dinâmicas dentro da simulação
- **Problema:** Jogos tratados como independentes (exceto bracket). Ignora fadiga, momentum, cartões, etc.
- **Impacto:** Mais realismo no mata-mata e grupos longos.
- **Sugestões:**
  - Modelo simples de fadiga (desempenho decresce com jogos seguidos / pouco descanso).
  - Probabilidade de cartões vermelhos e impacto (redução de força).
  - Correlação entre λs de jogos consecutivos da mesma seleção.
- **Validação:** Ver se distribuições de resultados no mata-mata ficam mais realistas vs histórico de Copas.
- **Status (2026-06-28, implemented on improvements/motor-precisao):** DONE.
  - Basic count fatigue in simulate.py evolved to full dynamics.
  - Improved fatigue using games count + rest days (dates from schedule matchdays + KO rounds).
  - Simple red card: per-team prob ~2.2%, impact ~22% goal reduction if drawn.
  - Momentum: streak from recent (within-sim + init from played) +/- ~3.5% per unit.
  - Config via `dynamics=dict(...)` kwarg to `simulate()` (fatigue/red_cards/momentum + tunable factors). Defaults ON for all runs.
  - Groups simulated in chrono md order for state carry; KO rounds use spaced dates + apply dynamics.
  - Real matches use fixed scores (no dyn adjust) but update counts/dates for subsequent.
  - Tests (test_bracket invariants + full sums 100/200/400) + manual + `run.py --sims 100` pass end-to-end.
  - Still works for groups+knockout. Callers unchanged (default enables).
  - No other files changed for this point.

## Próximos Passos
- Implementar ponto por ponto na branch.
- Para cada ponto: código + atualização de docs + teste com dados reais da Copa.
- Validação: Usar dados até rodada X para prever rodada X+1 e mata-mata; comparar com resultados reais.
- Manter branch separada até validação completa.

**Data de criação deste roadmap:** 2026-06-28

## Status Update (2026-06-28)
- Ponto 1 (Overdispersion): Implemented (dispersion ~1.58, NB in models/sampling/matrix). Positive impact on variance.
- Ponto 2 (live_form): Completed by parallel subagent. Richer proxy, adaptive, configurable, inspection.
- Ponto 3,4,5: In progress by parallel subagents (see below).
- Testing: Round-based validation (up to R2 vs R3) shows ~72.2% WDL accuracy with current improvements (positive, proceed).
- Parallel agents dispatched for remaining tasks.

Agents:
- Point 3: 019f0fc6-efc6-77d3-a948-5d21d8cf83f1 (richer ML features)
- Point 4: 019f0fc7-0772-7000-9864-c174aaa17cbd (calib/ensemble)
- Point 5: 019f0fc7-0772-7000-9864-c18608c60c7d (sim dynamics)
- Testing/Validation: 019f0fc7-6b53-7d73-93b3-f06120e2a10c

Monitor with get_command_or_subagent_output.

Next: Integrate results, test, proceed.
