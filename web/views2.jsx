/* ===== views2.jsx — Por Seleção + Comparador (light, FIFA brand) ===== */

/* ========== POR SELEÇÃO ========== */
function TeamView({ lang, initId, openPair, onTeamRoute }) {
  const T = I18N[lang];
  const finish   = useMemo(() => D.computeFinish(D.baseBracket), []);
  const [id, setId] = useState(initId != null ? initId : null);
  const [query, setQuery] = useState("");

  useEffect(() => { if (initId != null) setId(initId); }, [initId]);

  // grade de bandeiras (ordenada por nome) quando nenhuma seleção escolhida
  const sortedTeams = useMemo(() =>
    [...D.teams].sort((a, b) => WC.name(a.id, lang).localeCompare(WC.name(b.id, lang))), [lang]);

  // hooks dependentes da seleção — SEMPRE chamados (regras de hooks),
  // com guarda interna para quando nenhuma seleção está escolhida.
  const groupMatches = useMemo(() => id == null ? [] : D.groupMatchesFor(id), [id]);
  const koMatches = useMemo(() => {
    if (id == null) return [];
    const ms = [];
    D.ROUND_KEYS.forEach(rk => {
      D.baseBracket.rounds[rk].forEach(m => {
        if (m.a === id || m.b === id) ms.push({ ...m, rk });
      });
    });
    const finishOrder = ["R32","R16","QF","SF","F","CHAMP"];
    const fk = finish[id];
    return ms.filter(m => {
      const mIdx = finishOrder.indexOf(m.rk);
      const fIdx = finishOrder.indexOf(fk === "CHAMP" ? "CHAMP" : fk);
      return mIdx < fIdx || m.winner === id || fk === "CHAMP";
    });
  }, [id, finish]);

  if (id == null) {
    const filtered = sortedTeams.filter(t =>
      WC.name(t.id, lang).toLowerCase().includes(query.trim().toLowerCase()));
    return (
      <div className="fade-in">
        <div className="section-head">
          <div>
            <div className="eyebrow">{T.teamTitle}</div>
            <h2>{lang === "pt" ? "Escolha uma seleção" : "Pick a team"}</h2>
            <p>{lang === "pt" ? "Clique numa bandeira para ver probabilidade de título, avanço, força e a jornada prevista." : "Click a flag to see title probability, advancement, strength and the predicted journey."}</p>
          </div>
          <div className="select-wrap team-search">
            <input className="tsearch" type="text" placeholder={lang === "pt" ? "Buscar seleção…" : "Search team…"}
                   value={query} onChange={e => setQuery(e.target.value)} />
          </div>
        </div>
        <div className="flag-grid">
          {filtered.map(t => (
            <button key={t.id} className="flag-cell" onClick={() => (onTeamRoute ? onTeamRoute(t.id) : setId(t.id))}>
              <img className="flag" src={WC.flag(t.iso, 160)}
                   srcSet={WC.flag(t.iso, 160) + " 1x, " + WC.flag(t.iso, 320) + " 2x"} alt={t.en} loading="lazy" />
              <span className="fc-name">{WC.name(t.id, lang)}</span>
              <span className="fc-grp">{lang === "pt" ? "Grupo" : "Grp"} {D.groups[t.groupId].label}</span>
              <span className="fc-prob">{D.titleProb[t.id].toFixed(1)}%</span>
            </button>
          ))}
          {!filtered.length && <div className="datanote" style={{ gridColumn: "1/-1" }}><span>🔍</span><span>{lang === "pt" ? "Nenhuma seleção encontrada." : "No team found."}</span></div>}
        </div>
      </div>
    );
  }

  const team    = D.byId(id);
  const groupObj = D.groups[team.groupId];
  const grpRow  = groupObj.table.find(r => r.id === id);
  const fk      = finish[id];

  const finishOrder = ["GROUP","R32","R16","QF","SF","F","CHAMP"];
  const finishIdx   = finishOrder.indexOf(fk);
  function nodeState(key) {
    const idx = finishOrder.indexOf(key);
    if (fk === "CHAMP") return "done";
    if (idx < finishIdx) return "done";
    if (key === fk) return "out";
    return "";
  }

  const pathNodes = [
    { key: "GROUP", label: lang === "pt" ? "Grupos" : "Groups" },
    { key: "R32",   label: D.ROUND_SHORT["R32"][lang]   },
    { key: "R16",   label: D.ROUND_SHORT["R16"][lang]   },
    { key: "QF",    label: D.ROUND_SHORT["QF"][lang]    },
    { key: "SF",    label: D.ROUND_SHORT["SF"][lang]    },
    { key: "CHAMP", label: D.ROUND_SHORT["CHAMP"][lang] },
  ];

  const isSeed     = D.seeds.indexOf(id) >= 0;
  const seedPos    = D.seeds.indexOf(id);
  const titlePct   = D.titleProb[id];
  const groupGF    = groupMatches.reduce((s, m) => s + m.gf, 0);
  const groupGA    = groupMatches.reduce((s, m) => s + m.ga, 0);

  return (
    <div className="fade-in">
      <div className="team-topbar">
        <button className="btn" onClick={() => (onTeamRoute ? onTeamRoute(null) : setId(null))}>← {lang === "pt" ? "Todas as seleções" : "All teams"}</button>
        <div className="select-wrap">
          <select className="tsel" value={id} onChange={e => {
            const next = Number(e.target.value);
            if (onTeamRoute) onTeamRoute(next);
            else setId(next);
          }}>
            {sortedTeams.map(t => (<option key={t.id} value={t.id}>{WC.name(t.id, lang)}</option>))}
          </select>
        </div>
      </div>

      {/* Head card */}
      <div className="journey-head card card-accent-black">
        <img className="big-flag flag" src={WC.flag(team.iso, 160)}
             srcSet={WC.flag(team.iso, 160) + " 1x, " + WC.flag(team.iso, 320) + " 2x"} alt={team.en} />
        <div>
          <div className="jh-name">{WC.name(id, lang)}</div>
          <div className="jh-meta">
            <span className="pill">{lang === "pt" ? "Grupo" : "Group"} {groupObj.label} · {grpRow ? grpRow.pos + "º" : ""}</span>
            {isSeed && <span className="pill red">{T.seedN}{seedPos + 1}</span>}
            <span className={"pill " + (fk === "CHAMP" ? "black" : fk === "GROUP" ? "red" : "")}>
              {T.reaches}: {fk === "CHAMP" ? (lang === "pt" ? "🏆 Campeã!" : "🏆 Champion!") : D.ROUND_SHORT[fk] ? D.ROUND_SHORT[fk][lang] : fk}
            </span>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="jstats">
        <div className="jstat card accent-red"><div className="l">{T.statTitle}</div><div className="v">{titlePct.toFixed(1)}<small>%</small></div></div>
        <div className="jstat card accent-purple"><div className="l">{T.statAdvance}</div><div className="v">{grpRow ? grpRow.adv : "—"}<small>%</small></div></div>
        <div className="jstat card accent-teal"><div className="l">{lang === "pt" ? "Gols no grupo" : "Group goals"}</div><div className="v">{groupGF}<small>:{groupGA}</small></div></div>
        <div className="jstat card accent-lime"><div className="l">{lang === "pt" ? "Força" : "Strength"}</div><div className="v">{team.strength}<small>/100</small></div></div>
      </div>

      {/* Journey path */}
      <div className="card card-accent-black" style={{ padding: "20px 22px 22px", marginBottom: "18px" }}>
        <div className="eyebrow" style={{ marginBottom: "14px" }}>{lang === "pt" ? "Jornada prevista" : "Predicted path"}</div>
        <div className="path-track">
          {pathNodes.map(node => {
            const st = nodeState(node.key);
            return (
              <div key={node.key} className={"pnode " + st}>
                <div className="pdot" />
                <div className="rl">{node.label}</div>
                <div className="rs">{st === "out" && "❌"}{st === "done" && node.key === "CHAMP" && "🏆"}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Matches — clicáveis abrem o modal de detalhe */}
      <div className="card" style={{ padding: "18px 20px" }}>
        <div className="eyebrow" style={{ marginBottom: "14px" }}>{T.journeyMatches}</div>
        <div className="mlist">
          {groupMatches.map((m, i) => {
            const res = m.gf > m.ga ? "w" : m.gf < m.ga ? "l" : "d";
            const tag = m.played ? (lang === "pt" ? "Resultado" : "Result") : (lang === "pt" ? "Previsto" : "Predicted");
            const canOpen = !!D.calendarEntry(id, m.opp);
            return (
              <div key={"g" + i} className={"mrow card" + (canOpen ? " clickable" : "")}
                   {...(canOpen ? clickable(() => openPair(id, m.opp), (lang === "pt" ? "Ver detalhes do jogo" : "See match details")) : {})}
                   title={canOpen ? (lang === "pt" ? "Ver detalhes do jogo" : "See match details") : ""}>
                <span className="ph">
                  {lang === "pt" ? "Grupos" : "Groups"} · {groupObj.label}
                  {m.date && <span className="whenm">{m.date}{m.time ? " · " + m.time : ""}</span>}
                  <span className={"tagm" + (m.played ? " real" : "")}>{m.played ? "● " : ""}{tag}</span>
                </span>
                <div className="vs">
                  <TeamChip id={id} lang={lang} /><span className="sep">vs</span><TeamChip id={m.opp} lang={lang} />
                </div>
                <div className={"res " + res}>{m.gf}–{m.ga}{canOpen && <span className="statschev">›</span>}</div>
              </div>
            );
          })}
          {koMatches.map((m, i) => {
            const isA = m.a === id;
            const gf = isA ? m.score[0] : m.score[1];
            const ga = isA ? m.score[1] : m.score[0];
            const opp = isA ? m.b : m.a;
            const res = m.winner === id ? "w" : "l";
            const rkLabel = D.ROUND_SHORT[m.rk] ? D.ROUND_SHORT[m.rk][lang] : m.rk;
            return (
              <div key={"k" + i} className="mrow card" style={{ marginBottom: "8px" }}>
                <span className="ph">{rkLabel}<span className="tagm">{lang === "pt" ? "Previsto" : "Predicted"}</span></span>
                <div className="vs"><TeamChip id={id} lang={lang} /><span className="sep">vs</span><TeamChip id={opp} lang={lang} /></div>
                <div className={"res " + res}>{gf}–{ga}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ========== COMPARADOR ========== */
function CompareView({ lang, openPair, initPair, onCompareRoute }) {
  const T = I18N[lang];
  const sortedTeams = useMemo(() =>
    [...D.teams].sort((a, b) => WC.name(a.id, lang).localeCompare(WC.name(b.id, lang))), [lang]);

  const [aId, setAId] = useState(initPair?.aId ?? D.seeds[0]);
  const [bId, setBId] = useState(initPair?.bId ?? D.seeds[1]);
  useEffect(() => {
    if (initPair?.aId != null && initPair.aId !== aId) setAId(initPair.aId);
    if (initPair?.bId != null && initPair.bId !== bId) setBId(initPair.bId);
  }, [initPair?.aId, initPair?.bId]);
  const finish = useMemo(() => D.computeFinish(D.baseBracket), []);
  const finishOrder = ["GROUP","R32","R16","QF","SF","F","CHAMP"];
  const finishRank  = (id) => finishOrder.indexOf(finish[id]);

  const aT = D.byId(aId), bT = D.byId(bId);

  function pickA(next) {
    setAId(next);
    if (onCompareRoute) onCompareRoute(next, bId);
  }
  function pickB(next) {
    setBId(next);
    if (onCompareRoute) onCompareRoute(aId, next);
  }

  const METRICS = [
    { key: "title",  label: T.metricTitle,    a: D.titleProb[aId],  b: D.titleProb[bId],  fmt: v => v.toFixed(1) + "%", max: null },
    { key: "adv", label: T.metricAdvance,
      a: D.groups[aT.groupId].table.find(r => r.id === aId)?.adv || 0,
      b: D.groups[bT.groupId].table.find(r => r.id === bId)?.adv || 0,
      fmt: v => v + "%", max: 100 },
    { key: "str",    label: T.metricStrength, a: aT.strength,       b: bT.strength,       fmt: v => v + "/100", max: 100 },
    { key: "reach", label: T.metricReach,
      a: finishRank(aId), b: finishRank(bId),
      fmt: (v, id) => { const fk = finish[id]; return D.ROUND_SHORT[fk] ? D.ROUND_SHORT[fk][lang] : fk; },
      max: finishOrder.length - 1, isRank: true }
  ];

  let h2hMatch = null;
  D.ROUND_KEYS.forEach(rk => {
    D.baseBracket.rounds[rk].forEach(m => {
      if ((m.a === aId && m.b === bId) || (m.a === bId && m.b === aId)) h2hMatch = m;
    });
  });
  const calEntry = D.calendarEntry(aId, bId);

  function TeamSel({ value, onChange, excludeId }) {
    return (
      <div className="select-wrap">
        <select className="tsel" value={value} onChange={e => onChange(Number(e.target.value))} style={{ width: "100%" }}>
          {sortedTeams.filter(t => t.id !== excludeId).map(t => (
            <option key={t.id} value={t.id}>{WC.name(t.id, lang)}</option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div className="fade-in">
      <div className="section-head">
        <div>
          <div className="eyebrow">{T.compareTitle}</div>
          <h2>{T.compareTitle}</h2>
          <p>{T.compareSub}</p>
        </div>
      </div>

      {/* cabeçalho dos dois times com seletores embutidos */}
      <div className="cmp-head card">
        <div className="cmp-head-side a">
          <Flag id={aId} w={96} />
          <div className="nm">{WC.name(aId, lang)}</div>
          <span className="pill red">{lang === "pt" ? "Grupo" : "Group"} {D.groups[aT.groupId].label}</span>
          <TeamSel value={aId} onChange={pickA} excludeId={bId} />
        </div>
        <div className="cmp-head-vs">VS</div>
        <div className="cmp-head-side b">
          <Flag id={bId} w={96} />
          <div className="nm">{WC.name(bId, lang)}</div>
          <span className="pill purple">{lang === "pt" ? "Grupo" : "Group"} {D.groups[bT.groupId].label}</span>
          <TeamSel value={bId} onChange={pickB} excludeId={aId} />
        </div>
      </div>

      {/* Metrics */}
      <div className="card" style={{ padding: "6px 20px" }}>
        {METRICS.map(m => {
          const rawA = m.isRank ? finishRank(aId) : (typeof m.a === "number" ? m.a : 0);
          const rawB = m.isRank ? finishRank(bId) : (typeof m.b === "number" ? m.b : 0);
          const maxV = m.max != null ? m.max : Math.max(rawA, rawB, 0.01);
          const pA   = Math.min(100, rawA / maxV * 100);
          const pB   = Math.min(100, rawB / maxV * 100);
          const aW   = rawA > rawB, bW = rawB > rawA;
          return (
            <div key={m.key} className="cmp-metric">
              <div className="ml">{m.label}</div>
              <div className="mvals">
                <div className="va">
                  <span className={"num" + (aW ? " win" : "")}>{m.fmt(m.isRank ? finishRank(aId) : m.a, aId)}</span>
                  <div className="barwrap"><i style={{ width: pA + "%", background: "var(--red)" }} /></div>
                </div>
                <div className="mid">{aW ? "▶" : bW ? "◀" : "="}</div>
                <div className="vb">
                  <span className={"num" + (bW ? " win" : "")} style={bW ? { color: "var(--purple)" } : {}}>
                    {m.fmt(m.isRank ? finishRank(bId) : m.b, bId)}
                  </span>
                  <div className="barwrap"><i style={{ width: pB + "%", background: "var(--purple)" }} /></div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* H2H */}
      <div className="cmp-h2h card card-accent-black" style={{ marginTop: "14px" }}>
        <div className="l">{T.h2h}</div>
        {h2hMatch ? (
          <React.Fragment>
            <div className="sc">
              <span style={{ color: h2hMatch.winner === aId ? "var(--red)" : "var(--text-muted)" }}>{WC.name(aId, lang)}</span>
              <em>{h2hMatch.score[h2hMatch.a === aId ? 0 : 1]}–{h2hMatch.score[h2hMatch.a === aId ? 1 : 0]}</em>
              <span style={{ color: h2hMatch.winner === bId ? "var(--purple)" : "var(--text-muted)" }}>{WC.name(bId, lang)}</span>
            </div>
            <div style={{ fontFamily: "var(--font-cond)", fontSize: "12px", color: "var(--text-muted)", marginTop: "8px" }}>
              {D.ROUND_SHORT[h2hMatch.round] ? D.ROUND_SHORT[h2hMatch.round][lang] : h2hMatch.round}
            </div>
          </React.Fragment>
        ) : (
          <div style={{ marginTop: "10px", color: "var(--text-muted)", fontFamily: "var(--font-cond)", fontSize: "14px" }}>
            {lang === "pt" ? "Sem confronto direto previsto no chaveamento base." : "No predicted direct clash in the base bracket."}
          </div>
        )}
        {calEntry && (
          <button className="btn" style={{ marginTop: "14px" }} onClick={() => openPair(aId, bId)}>
            {lang === "pt" ? "Ver jogo da fase de grupos" : "See group-stage match"}
          </button>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { TeamView, CompareView });
