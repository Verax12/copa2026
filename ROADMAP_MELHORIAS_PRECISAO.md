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

## Próximos Passos
- Implementar ponto por ponto na branch.
- Para cada ponto: código + atualização de docs + teste com dados reais da Copa.
- Validação: Usar dados até rodada X para prever rodada X+1 e mata-mata; comparar com resultados reais.
- Manter branch separada até validação completa.

**Data de criação deste roadmap:** 2026-06-28
