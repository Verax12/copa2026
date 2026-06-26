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

/* props para tornar um <div>/<span> clicável acessível por teclado
   (Enter/Espaço ativam). Use: <div {...clickable(() => acao())}>          */
function clickable(handler, label) {
  return {
    role: "button", tabIndex: 0,
    onClick: handler,
    onKeyDown: (e) => {
      if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") { e.preventDefault(); handler(e); }
    },
    "aria-label": label,
  };
}

/* ---------- Modal genérico (overlay + esc + scroll lock + acessibilidade) ----------
   - Escape e clique no overlay fecham
   - trava o scroll do body
   - focus trap: Tab/Shift+Tab circulam só dentro do modal
   - foco inicial no initialFocusSelector (ex.: .mm-close) ou no 1º focável
   - restaura o foco para o elemento que abriu o modal ao fechar              */
const FOCUSABLE_SEL = 'a[href],button:not([disabled]),input:not([disabled]),' +
  'select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

function Modal({ open, onClose, children, labelledBy, initialFocusSelector }) {
  const shellRef = useRef(null);
  const openerRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    // guarda quem tinha o foco para restaurar depois
    openerRef.current = document.activeElement;
    const shell = shellRef.current;
    const focusables = () => shell
      ? Array.prototype.slice.call(shell.querySelectorAll(FOCUSABLE_SEL))
          .filter(el => el.offsetParent !== null || el === document.activeElement)
      : [];

    const focusInitial = () => {
      let target = initialFocusSelector && shell ? shell.querySelector(initialFocusSelector) : null;
      if (!target) target = focusables()[0] || shell;
      if (target && target.focus) target.focus();
    };
    const t = setTimeout(focusInitial, 0);

    const onKey = (e) => {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key !== "Tab") return;
      const f = focusables();
      if (!f.length) { e.preventDefault(); if (shell) shell.focus(); return; }
      const first = f[0], last = f[f.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || !shell.contains(active))) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && active === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      clearTimeout(t);
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      // restaura o foco para o elemento que abriu o modal
      const opener = openerRef.current;
      if (opener && opener.focus && document.contains(opener)) {
        setTimeout(() => { try { opener.focus(); } catch (_e) {} }, 0);
      }
    };
  }, [open, onClose, initialFocusSelector]);

  if (!open) return null;
  return (
    <div className="modal-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-shell" role="dialog" aria-modal="true" aria-labelledby={labelledBy}
           ref={shellRef} tabIndex={-1}>
        {children}
      </div>
    </div>
  );
}

/* Selo do resultado favorito ("Brasil vence · 40%" / "Empate provável · 32%").
   Deixa explícito quem o modelo aponta como favorito — o mesmo resultado a que o
   placar previsto agora obedece. `size="sm"` para encaixar em tiles/linhas. */
function FavoriteBadge({ ph, pd, pa, home, away, lang, size }) {
  const pt = lang === "pt";
  const probs = [ph, pd, pa];
  const fav = probs.indexOf(Math.max(...probs));
  const pct = Math.round(probs[fav] * 100);
  const cls = "fav-badge " + (fav === 1 ? "draw" : "win") + (size ? " " + size : "");
  if (fav === 1) {
    return (
      <span className={cls} title={pt ? "Resultado mais provável" : "Most likely result"}>
        <span className="fav-ico" aria-hidden="true">🤝</span>
        <b>{pt ? "Empate provável" : "Draw likely"}</b><em>{pct}%</em>
      </span>
    );
  }
  const team = fav === 0 ? home : away;
  return (
    <span className={cls} title={pt ? "Favorito ao resultado" : "Result favorite"}>
      <Flag id={team} w={16} />
      <b>{WC.name(team, lang)} {pt ? "vence" : "wins"}</b><em>{pct}%</em>
    </span>
  );
}

/* expõe para os outros arquivos babel */
Object.assign(window, {
  D, WC,
  I18N, Flag, TeamChip, roundLabel, Modal, clickable, FavoriteBadge,
  useState, useMemo, useEffect, useRef
});
