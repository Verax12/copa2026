/* =====================================================================
   Copa 2026 — camada de dados REAIS do dashboard.
   Lê window.WC_DATA (gerado por wc2026.export_web a partir do modelo) e
   expõe window.DATA / window.WC na MESMA estrutura que as views esperam.
   Probabilidades vêm do Monte Carlo; placares previstos e o bracket
   interativo ("e se?") derivam da matriz de gols esperados (λ) do modelo.
   ===================================================================== */
(function () {
  "use strict";
  const WD = window.WC_DATA;
  if (!WD) { console.error("WC_DATA ausente — rode: python -m wc2026.export_web"); return; }

  // ---- RNG determinístico (placar estável por confronto) -------------
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function hashStr(s) {
    let h = 1779033703 ^ s.length;
    for (let i = 0; i < s.length; i++) {
      h = Math.imul(h ^ s.charCodeAt(i), 3432918353);
      h = (h << 13) | (h >>> 19);
    }
    return h >>> 0;
  }
  const rngFor = (seed) => mulberry32(hashStr(String(seed)));

  const teams = WD.teams;
  const byId = (id) => teams[id];

  // ---- groups: anexa referência rápida ------------------------------
  const groups = WD.groups;

  // ---- placar previsto = MODA da matriz de placares do modelo --------
  // (exportado por par; simétrico por construção, então o mesmo jogo mostra o
  //  mesmo placar de qualquer perspectiva — A vs B é o espelho de B vs A)
  function predScore(aId, bId) {
    const sl = WD.scorelines && WD.scorelines[aId] && WD.scorelines[aId][bId];
    if (sl) return [sl[0], sl[1]];
    const lab = WD.lambdas[aId] && WD.lambdas[aId][bId];   // fallback
    return [Math.round(lab ? lab[0] : 1), Math.round(lab ? lab[1] : 1)];
  }

  // ---- vencedor de confronto eliminatório (favorito pelo λ) ----------
  // placar = moda das vitórias do favorito (winScores), variado e sem empate.
  function simWinner(aId, bId, seed) {
    const lab = WD.lambdas[aId] && WD.lambdas[aId][bId];
    const la = lab ? lab[0] : 1.1, lb = lab ? lab[1] : 1.1;
    let winner;
    if (Math.abs(la - lb) < 1e-6) winner = byId(aId).strength >= byId(bId).strength ? aId : bId;
    else winner = la > lb ? aId : bId;
    const ws = WD.winScores;
    let ga, gb;
    if (winner === aId) {
      const w = ws && ws[aId] && ws[aId][bId];
      [ga, gb] = w ? [w[0], w[1]] : [1, 0];
    } else {
      const w = ws && ws[bId] && ws[bId][aId];   // b vence a; orienta para (a,b)
      [ga, gb] = w ? [w[1], w[0]] : [0, 1];
    }
    return { winner, score: [ga, gb] };
  }

  // ---- bracket OFICIAL (estrutura fixa da FIFA) + "e se?" ------------
  const ROUND_KEYS = ["R32", "R16", "QF", "SF", "F"];
  function buildBracket(overrides) {
    overrides = overrides || {};
    const spec = WD.bracketSpec;
    const mk = (aId, bId, rk, i) => {
      const id = rk + "-" + i;
      const sim = simWinner(aId, bId, id);
      const winner = overrides[id] != null ? overrides[id] : sim.winner;
      return { id, round: rk, idx: i, a: aId, b: bId, score: sim.score, winner, def: sim.winner };
    };
    const rounds = {};
    rounds.R32 = spec.r32.map((p, i) => mk(p[0], p[1], "R32", i));
    const playRound = (prev, pairs, rk) =>
      pairs.map((pr, i) => mk(prev[pr[0]].winner, prev[pr[1]].winner, rk, i));
    rounds.R16 = playRound(rounds.R32, spec.r16Pairs, "R16");
    rounds.QF = playRound(rounds.R16, spec.qfPairs, "QF");
    rounds.SF = playRound(rounds.QF, spec.sfPairs, "SF");
    rounds.F = playRound(rounds.SF, [[0, 1]], "F");
    return { rounds, champion: rounds.F[0].winner };
  }

  const baseBracket = buildBracket({});

  // ---- até onde cada seleção vai (a partir de um bracket) ------------
  function computeFinish(bracket) {
    const finish = {};
    teams.forEach(t => { finish[t.id] = WD.qualifierIds.includes(t.id) ? "R32" : "GROUP"; });
    const next = { R32: "R16", R16: "QF", QF: "SF", SF: "F", F: "CHAMP" };
    ROUND_KEYS.forEach(rk => {
      bracket.rounds[rk].forEach(m => {
        const loser = m.winner === m.a ? m.b : m.a;
        if (rk === "F") { finish[m.winner] = "CHAMP"; finish[loser] = "F"; }
        else { finish[loser] = rk; finish[m.winner] = next[rk]; }
      });
    });
    return finish;
  }

  // ---- jogos já disputados (placar real) -----------------------------
  const playedMap = {};
  (WD.played || []).forEach(([h, a, hg, ag]) => {
    playedMap[h + "-" + a] = [hg, ag];
    playedMap[a + "-" + h] = [ag, hg];
  });

  // ---- microestatísticas por jogo (orientadas à seleção escolhida) ---
  const statMap = {};
  (WD.matchStats || []).forEach(m => { statMap[m.h + "-" + m.a] = m; statMap[m.a + "-" + m.h] = m; });
  function getMatchStats(teamId, oppId) {
    const m = statMap[teamId + "-" + oppId];
    if (!m) return null;
    const flip = m.h !== teamId;   // seleção escolhida era o visitante no registro
    return {
      source: m.src,
      stats: m.stats.map(s => ({
        pt: s.pt, en: s.en,
        you: flip ? s.away : s.home,
        them: flip ? s.home : s.away
      }))
    };
  }

  // ---- jogos da fase de grupos de uma seleção ------------------------
  // usa o RESULTADO REAL se o jogo já aconteceu; senão, o placar previsto.
  function groupMatchesFor(teamId) {
    const t = byId(teamId);
    const g = groups[t.groupId];
    const dates = WD.matchDates || {};
    return g.teamIds.filter(id => id !== teamId).map(oId => {
      const md = dates[teamId + "-" + oId] || null;
      const when = md ? { date: md.date, time: md.time } : { date: "", time: "" };
      const real = playedMap[teamId + "-" + oId];
      if (real) return { opp: oId, gf: real[0], ga: real[1], group: g.label, played: true, ...when };
      const [ga, gb] = predScore(teamId, oId);
      return { opp: oId, gf: ga, ga: gb, group: g.label, played: false, ...when };
    });
  }

  // ---- rótulos de rodada (corrigidos p/ Copa de 48 / 32 no mata-mata)-
  const ROUND_LABEL = {
    GROUP: { pt: "Fase de grupos", en: "Group stage" },
    R32: { pt: "32-avos de final", en: "Round of 32" },
    R16: { pt: "Oitavas de final", en: "Round of 16" },
    QF: { pt: "Quartas de final", en: "Quarter-finals" },
    SF: { pt: "Semifinal", en: "Semi-finals" },
    F: { pt: "Final", en: "Final" },
    CHAMP: { pt: "Campeã", en: "Champion" }
  };
  const ROUND_SHORT = {
    GROUP: { pt: "Grupos", en: "Groups" },
    R32: { pt: "32-avos", en: "R32" },
    R16: { pt: "Oitavas", en: "R16" },
    QF: { pt: "Quartas", en: "QF" },
    SF: { pt: "Semis", en: "SF" },
    F: { pt: "Vice", en: "Runner-up" },
    CHAMP: { pt: "Campeã", en: "Champion" }
  };

  // ---- export --------------------------------------------------------
  window.DATA = {
    teams, groups, venues: WD.venues,
    qualifierIds: WD.qualifierIds, seeds: WD.seeds,
    titleProb: WD.titleProb,
    finalProb: WD.finalProb, semiProb: WD.semiProb, advProb: WD.advProb,
    baseBracket, buildBracket, computeFinish, groupMatchesFor, getMatchStats, predScore, byId,
    ROUND_KEYS, ROUND_LABEL, ROUND_SHORT,
    GROUP_LABELS: WD.groupLabels,
    trackRecord: WD.trackRecord || null,
    calendar: WD.calendar || [],
    meta: WD.meta
  };
  // flagcdn só serve larguras fixas — arredonda PARA CIMA para a válida mais próxima
  function snapW(w) { return w <= 40 ? 40 : w <= 80 ? 80 : w <= 160 ? 160 : w <= 320 ? 320 : 640; }
  window.WC = {
    flag: (iso, w) => `https://flagcdn.com/w${snapW(w || 40)}/${iso}.png`,
    name: (id, lang) => (lang === "en" ? byId(id).en : byId(id).pt)
  };
})();
