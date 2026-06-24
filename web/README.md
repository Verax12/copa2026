# Dashboard web — Copa 2026

Painel visual das predições do modelo (design FIFA 2026 do Claude Design, ligado
aos dados **reais** do pipeline). React (sem build, via Babel no browser) + um JSON
gerado pelo modelo.

## Como rodar

```bash
# 1) gerar os dados reais a partir do modelo (cria web/wc_data.js)
python -m wc2026.export_web                      # Dixon-Coles, 20k sims
python -m wc2026.export_web --engine ml --live   # opções: motor de ML + ajuste ao vivo
scripts/generate_web_data.sh                     # padrão do projeto: ensemble, 200k sims

# 2) servir (precisa de HTTP — o Babel carrega os .jsx via fetch)
python -m http.server 8765 --directory web
# abra http://127.0.0.1:8765
```

Ou use o atalho: `./web/serve.sh` (gera os dados e sobe o servidor).

## Abas

- **Visão geral** — favorita ao título + termômetro (top 12 por prob. de campeã).
- **Etapas** — fase de grupos (classificação prevista + % de avanço) e **mata-mata
  com o bracket OFICIAL da FIFA**, interativo ("e se?": clique para mudar um vencedor).
- **Por seleção** — prob. título, avanço, gols no grupo, força e a jornada prevista.
- **Comparador** — duas seleções lado a lado (título, avanço, força, fase prevista).
- **Sedes** — mapa das 16 cidades-sede.

## De onde vêm os dados

`wc2026/export_web.py` roda o pipeline (Elo → motor de gols → Monte Carlo com o
bracket oficial) e grava `web/wc_data.js` (`window.WC_DATA`). O `data.js` monta
`window.DATA`/`window.WC` a partir disso, mantendo a estrutura que as views usam:

- probabilidades (título/final/semi/avanço) vêm direto do Monte Carlo;
- placares previstos e o simulador "e se?" derivam da matriz de gols esperados (λ);
- o chaveamento usa a estrutura oficial (`wc2026/bracket.py`).

Para atualizar durante a Copa: `python -m wc2026.data --update` →
`python -m wc2026.thesportsdb --pull` (opcional, p/ `--live`) →
`scripts/generate_web_data.sh` → recarregue a página.

## Deep links úteis

O painel aceita URLs compartilháveis:

- `#/calendario` ou `#/calendario?team=brasil&group=C`
- `#/selecao/brasil`
- `#/comparador/brasil/argentina`
- `#/jogo/2026-06-13-brazil-vs-morocco`

Os filtros do calendário (status, seleção, grupo e estádio/cidade) ficam na URL,
então dá para compartilhar uma visão específica.

## Notas

- Bandeiras vêm do flagcdn.com (online). O resto é local.
- O aviso "in-browser Babel transformer" no console é esperado (uso local); para
  produção, dá para pré-compilar os `.jsx`.

## Estatísticas ricas dos jogos (opcional, via Flashscore — local)

A página de detalhe do jogo mostra microestatísticas. As finalizações vêm do
TheSportsDB (grátis, HTTP). Para ter **posse, escanteios e cartões**, use o
scraper do Flashscore (passo **local**, não entra no `/atualizar` da nuvem):

```bash
# 1) rode o scraper (github.com/gustavofariaa/FlashscoreScraping) para a Copa,
#    exportando JSON. 2) salve o arquivo aqui:
#       api_cache/flashscore.json
# 3) regenere:
python -m wc2026.flashscore        # confere o que foi lido
python -m wc2026.export_web --engine ensemble --live   # publica no painel
```

O `flashscore.py` só LÊ o JSON (sem navegador, sem dependência nova). Quando há
dados do Flashscore para um jogo, eles têm prioridade sobre o TheSportsDB.
