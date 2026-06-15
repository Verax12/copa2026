/* ===== ui.jsx — i18n + componentes compartilhados ===== */
const { useState, useMemo, useEffect, useRef } = React;
const D = window.DATA;
const WC = window.WC;

/* ---------- traduções ---------- */
const I18N = {
  pt: {
    sub: "Painel de predições · 48 seleções · 16 sedes",
    hosts: "EUA · México · Canadá · Jun–Jul 2026",
    navHero: "Visão geral", navStages: "Etapas", navTeam: "Por seleção",
    navCompare: "Comparador", navMap: "Sedes",
    heroTitle: "Quem levanta a taça em 2026?",
    heroSub: "Probabilidades, chaveamento previsto e o caminho de cada seleção até a final — tudo em um só painel, atualizável quando os dados reais chegarem.",
    favLabel: "Favorita ao título", titleChance: "chance de título",
    thermoTitle: "Termômetro do título", thermoSub: "Top 12 · prob. de campeã",
    stagesTitle: "Etapas do torneio", groups: "Fase de grupos", knockout: "Mata-mata",
    groupsSub: "12 grupos de 4. Avançam os 2 primeiros + os 8 melhores terceiros. % = chance de avançar.",
    advance: "avança", first: "1º", second: "2º", third: "3º", out: "Fora",
    bracketSub: "Chaveamento previsto. Clique em qualquer seleção para alterar o vencedor — o restante do chaveamento se ajusta.",
    simTitle: "Simulador \u201ce se?\u201d", simBody: "Clique numa seleção para fazê-la vencer aquele confronto. As fases seguintes recalculam automaticamente.",
    reset: "Restaurar predição", champion: "Campeã prevista",
    teamTitle: "Caminho da seleção", pick: "Escolha uma seleção",
    pld: "Vai até", grpFinish: "Fase de grupos", reaches: "Predição de campanha",
    statTitle: "Prob. título", statAdvance: "Avança do grupo", statReach: "Chega até", statSeed: "Cabeça",
    journeyMatches: "Jogos previstos", groupPhase: "Grupos", scorePredicted: "placar previsto",
    compareTitle: "Comparador", compareSub: "Coloque duas seleções lado a lado.",
    metricTitle: "Prob. de título", metricAdvance: "Avança do grupo", metricStrength: "Índice de força", metricReach: "Fase prevista",
    h2h: "Confronto direto previsto", roundLabelHead: "",
    mapTitle: "Cidades-sede", mapSub: "16 estádios nos três países anfitriões.",
    venuesHead: "Estádios",
    dataNote: "Dados de demonstração.", dataNoteBody: "As probabilidades e placares são fictícios, gerados a partir de um índice de força para ilustrar o painel. Estrutura pronta para receber seus dados reais.",
    roadmapTitle: "Próximas ideias para o painel",
    seedN: "Cabeça nº",
    langName: "Português"
  },
  en: {
    sub: "Predictions dashboard · 48 teams · 16 venues",
    hosts: "USA · Mexico · Canada · Jun–Jul 2026",
    navHero: "Overview", navStages: "Stages", navTeam: "By team",
    navCompare: "Compare", navMap: "Venues",
    heroTitle: "Who lifts the trophy in 2026?",
    heroSub: "Probabilities, the predicted bracket and every team's path to the final — all in one panel, ready to refresh when the real data lands.",
    favLabel: "Title favourite", titleChance: "title chance",
    thermoTitle: "Title thermometer", thermoSub: "Top 12 · champion prob.",
    stagesTitle: "Tournament stages", groups: "Group stage", knockout: "Knockout",
    groupsSub: "12 groups of 4. Top 2 + 8 best third-placed advance. % = chance to advance.",
    advance: "advance", first: "1st", second: "2nd", third: "3rd", out: "Out",
    bracketSub: "Predicted bracket. Click any team to change the winner — the rest of the bracket adjusts.",
    simTitle: "\u201cWhat if?\u201d simulator", simBody: "Click a team to make it win that tie. Later rounds recompute automatically.",
    reset: "Reset prediction", champion: "Predicted champion",
    teamTitle: "Team path", pick: "Pick a team",
    pld: "Reaches", grpFinish: "Group stage", reaches: "Campaign prediction",
    statTitle: "Title prob.", statAdvance: "Advance from group", statReach: "Reaches", statSeed: "Seed",
    journeyMatches: "Predicted matches", groupPhase: "Groups", scorePredicted: "predicted score",
    compareTitle: "Compare", compareSub: "Put two teams side by side.",
    metricTitle: "Title prob.", metricAdvance: "Advance from group", metricStrength: "Strength index", metricReach: "Predicted stage",
    h2h: "Predicted head-to-head", roundLabelHead: "",
    mapTitle: "Host cities", mapSub: "16 stadiums across the three host nations.",
    venuesHead: "Stadiums",
    dataNote: "Demo data.", dataNoteBody: "Probabilities and scores are fictional, derived from a strength index to illustrate the panel. Structure is ready for your real data.",
    roadmapTitle: "Next ideas for the dashboard",
    seedN: "Seed #",
    langName: "English"
  }
};

/* ---------- pequenos componentes ---------- */
function Flag({ id, w, cls }) {
  const t = D.byId(id);
  return React.createElement("img", {
    className: "flag " + (cls || ""), src: WC.flag(t.iso, (w || 40) * 2),
    alt: t.en, loading: "lazy", width: (w || 40), height: Math.round((w || 40) * 3 / 4)
  });
}

function TeamChip({ id, lang, size }) {
  return (
    <span className={"tchip " + (size || "")}>
      <Flag id={id} w={size === "lg" ? 48 : 40} />
      <span className="nm">{WC.name(id, lang)}</span>
    </span>
  );
}

function roundLabel(rk, lang, kind) {
  const src = kind === "short" ? D.ROUND_SHORT : D.ROUND_LABEL;
  return src[rk] ? src[rk][lang] : rk;
}

/* expõe para os outros arquivos babel */
Object.assign(window, {
  D, WC,
  I18N, Flag, TeamChip, roundLabel,
  useState, useMemo, useEffect, useRef
});
