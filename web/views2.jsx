/* ===== views2.jsx v2 — Por Seleção + Comparador + Mapa (light, FIFA brand) ===== */

/* ========== POR SELEÇÃO ========== */
function TeamView({ lang, initId }) {
  const T = I18N[lang];
  const finish   = useMemo(() => D.computeFinish(D.baseBracket), []);
  const [id, setId] = useState(initId != null ? initId : D.baseBracket.champion);
  const [openStat, setOpenStat] = useState(null);  // opp id do jogo com painel de stats aberto

  useEffect(() => { if (initId != null) setId(initId); }, [initId]);
  useEffect(() => { setOpenStat(null); }, [id]);

  const team    = D.byId(id);
  const groupObj = D.groups[team.groupId];
  const grpRow  = groupObj.table.find(r => r.id === id);
  const fk      = finish[id];

  const groupMatches = useMemo(() => D.groupMatchesFor(id), [id]);
  const koMatches    = useMemo(() => {
    const ms = [];
    D.ROUND_KEYS.forEach(rk => {
      D.baseBracket.rounds[rk].forEach(m => {
        if (m.a === id || m.b === id) ms.push({ ...m, rk });
      });
    });
    const finishOrder = ["R32","R16","QF","SF","F","CHAMP"];
    return ms.filter(m => {
      const mIdx = finishOrder.indexOf(m.rk);
      const fIdx = finishOrder.indexOf(fk === "CHAMP" ? "CHAMP" : fk);
      return mIdx < fIdx || m.winner === id || fk === "CHAMP";
    });
  }, [id, fk]);

  const sortedTeams = useMemo(() =>
    [...D.teams].sort((a, b) => WC.name(a.id, lang).localeCompare(WC.name(b.id, lang))), [lang]);

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
      <div className="section-head" style={{ marginBottom: "14px" }}>
        <div><div className="eyebrow">{T.teamTitle}</div></div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap", marginBottom: "20px" }}>
        <div className="select-wrap">
          <select className="tsel" value={id} onChange={e => setId(Number(e.target.value))}>
            {sortedTeams.map(t => (
              <option key={t.id} value={t.id}>{WC.name(t.id, lang)}</option>
            ))}
          </select>
        </div>
        <span className="pill">{lang === "pt" ? "Grupo" : "Group"} {groupObj.label}</span>
        {isSeed && <span className="pill red">{T.seedN}{seedPos + 1}</span>}
      </div>

      {/* Head card */}
      <div className="journey-head card card-accent-black">
        <img
          className="big-flag flag"
          src={WC.flag(team.iso, 160)}
          srcSet={WC.flag(team.iso, 160) + " 1x, " + WC.flag(team.iso, 320) + " 2x"}
          alt={team.en}
        />
        <div>
          <div className="jh-name">{WC.name(id, lang)}</div>
          <div className="jh-meta">
            <span className="pill">{lang === "pt" ? "Grupo" : "Group"} {groupObj.label} · {grpRow ? grpRow.pos + "º" : ""}</span>
            <span className={"pill " + (fk === "CHAMP" ? "black" : fk === "GROUP" ? "red" : "")}>
              {T.reaches}: {fk === "CHAMP"
                ? (lang === "pt" ? "🏆 Campeã!" : "🏆 Champion!")
                : D.ROUND_SHORT[fk] ? D.ROUND_SHORT[fk][lang] : fk}
            </span>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="jstats">
        <div className="jstat card accent-red">
          <div className="l">{T.statTitle}</div>
          <div className="v">{titlePct.toFixed(1)}<small>%</small></div>
        </div>
        <div className="jstat card accent-purple">
          <div className="l">{T.statAdvance}</div>
          <div className="v">{grpRow ? grpRow.adv : "—"}<small>%</small></div>
        </div>
        <div className="jstat card accent-teal">
          <div className="l">{lang === "pt" ? "Gols no grupo" : "Group goals"}</div>
          <div className="v">{groupGF}<small>:{groupGA}</small></div>
        </div>
        <div className="jstat card accent-lime">
          <div className="l">{lang === "pt" ? "Força" : "Strength"}</div>
          <div className="v">{team.strength}<small>/100</small></div>
        </div>
      </div>

      {/* Journey path */}
      <div className="card card-accent-black" style={{ padding: "20px 22px 22px", marginBottom: "18px" }}>
        <div className="eyebrow" style={{ marginBottom: "14px" }}>
          {lang === "pt" ? "Jornada prevista" : "Predicted path"}
        </div>
        <div className="path-track">
          {pathNodes.map(node => {
            const st = nodeState(node.key);
            return (
              <div key={node.key} className={"pnode " + st}>
                <div className="pdot" />
                <div className="rl">{node.label}</div>
                <div className="rs">
                  {st === "out" && "❌"}
                  {st === "done" && node.key === "CHAMP" && "🏆"}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Matches */}
      <div className="card" style={{ padding: "18px 20px" }}>
        <div className="eyebrow" style={{ marginBottom: "14px" }}>{T.journeyMatches}</div>
        <div className="mlist">
          {groupMatches.map((m, i) => {
            const res = m.gf > m.ga ? "w" : m.gf < m.ga ? "l" : "d";
            const tag = m.played
              ? (lang === "pt" ? "Resultado" : "Result")
              : (lang === "pt" ? "Previsto" : "Predicted");
            const ms = m.played ? D.getMatchStats(id, m.opp) : null;
            const open = openStat === m.opp;
            return (
              <div key={"g" + i} style={{ marginBottom: "8px" }}>
                <div className={"mrow card" + (ms ? " clickable" : "")}
                     onClick={() => ms && setOpenStat(open ? null : m.opp)}>
                  <span className="ph">
                    {lang === "pt" ? "Grupos" : "Groups"} · {groupObj.label}
                    {m.date && <span className="whenm">{m.date}{m.time ? " · " + m.time : ""}</span>}
                    <span className={"tagm" + (m.played ? " real" : "")}>{m.played ? "● " : ""}{tag}</span>
                  </span>
                  <div className="vs">
                    <TeamChip id={id} lang={lang} />
                    <span className="sep">vs</span>
                    <TeamChip id={m.opp} lang={lang} />
                  </div>
                  <div className={"res " + res}>
                    {m.gf}–{m.ga}
                    {ms && <span className="statschev">{open ? "▾" : "›"}</span>}
                  </div>
                </div>
                {open && ms && (
                  <div className="matchstats card">
                    <div className="ms-hd">
                      <span>{WC.name(id, lang)}</span>
                      <span className="ms-src">{lang === "pt" ? "Estatísticas" : "Stats"} · {ms.source}</span>
                      <span>{WC.name(m.opp, lang)}</span>
                    </div>
                    {ms.stats.map((s, j) => {
                      const tot = (s.you + s.them) || 1;
                      const youW = s.you > s.them, themW = s.them > s.you;
                      return (
                        <div key={j} className="ms-row">
                          <span className={"ms-v" + (youW ? " win" : "")}>{s.you}</span>
                          <div className="ms-bars">
                            <div className="ms-label">{lang === "pt" ? s.pt : s.en}</div>
                            <div className="ms-track">
                              <i className="you" style={{ width: (s.you / tot * 100) + "%" }} />
                              <i className="them" style={{ width: (s.them / tot * 100) + "%" }} />
                            </div>
                          </div>
                          <span className={"ms-v them" + (themW ? " win" : "")}>{s.them}</span>
                        </div>
                      );
                    })}
                    <div className="ms-foot">
                      {lang === "pt"
                        ? "Fonte gratuita só fornece finalizações — escanteios/cartões exigem dados pagos."
                        : "Free source only provides shots — corners/cards need paid data."}
                    </div>
                  </div>
                )}
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
                <span className="ph">{rkLabel}</span>
                <div className="vs">
                  <TeamChip id={id} lang={lang} />
                  <span className="sep">vs</span>
                  <TeamChip id={opp} lang={lang} />
                </div>
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
function CompareView({ lang }) {
  const T = I18N[lang];
  const sortedTeams = useMemo(() =>
    [...D.teams].sort((a, b) => WC.name(a.id, lang).localeCompare(WC.name(b.id, lang))), [lang]);

  const [aId, setAId] = useState(D.seeds[0]);
  const [bId, setBId] = useState(D.seeds[1]);
  const finish = useMemo(() => D.computeFinish(D.baseBracket), []);
  const finishOrder = ["GROUP","R32","R16","QF","SF","F","CHAMP"];
  const finishRank  = (id) => finishOrder.indexOf(finish[id]);

  const aT = D.byId(aId), bT = D.byId(bId);

  const METRICS = [
    { key: "title",  label: T.metricTitle,    a: D.titleProb[aId],  b: D.titleProb[bId],  fmt: v => v.toFixed(1) + "%", max: null },
    {
      key: "adv", label: T.metricAdvance,
      a: D.groups[aT.groupId].table.find(r => r.id === aId)?.adv || 0,
      b: D.groups[bT.groupId].table.find(r => r.id === bId)?.adv || 0,
      fmt: v => v + "%", max: 100
    },
    { key: "str",    label: T.metricStrength, a: aT.strength,       b: bT.strength,       fmt: v => v + "/100", max: 100 },
    {
      key: "reach", label: T.metricReach,
      a: finishRank(aId), b: finishRank(bId),
      fmt: (v, id) => { const fk = finish[id]; return D.ROUND_SHORT[fk] ? D.ROUND_SHORT[fk][lang] : fk; },
      max: finishOrder.length - 1, isRank: true
    }
  ];

  let h2hMatch = null;
  D.ROUND_KEYS.forEach(rk => {
    D.baseBracket.rounds[rk].forEach(m => {
      if ((m.a === aId && m.b === bId) || (m.a === bId && m.b === aId)) h2hMatch = m;
    });
  });

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
          <p>{T.compareSub}</p>
        </div>
      </div>

      <div className="cmp-pickers">
        <TeamSel value={aId} onChange={setAId} excludeId={bId} />
        <div className="cmp-vs" style={{ color: "var(--red)", fontFamily: "var(--font-display)", fontSize: "32px", textAlign: "center" }}>VS</div>
        <TeamSel value={bId} onChange={setBId} excludeId={aId} />
      </div>

      {/* Flag cards */}
      <div className="cmp-cards">
        <div className="cmp-card card card-accent">
          <Flag id={aId} w={120} />
          <div className="nm">{WC.name(aId, lang)}</div>
          <div style={{ marginTop: "8px" }}><span className="pill">{lang === "pt" ? "Grupo" : "Group"} {D.groups[aT.groupId].label}</span></div>
        </div>
        <div className="cmp-card card card-accent-purple">
          <Flag id={bId} w={120} />
          <div className="nm">{WC.name(bId, lang)}</div>
          <div style={{ marginTop: "8px" }}><span className="pill">{lang === "pt" ? "Grupo" : "Group"} {D.groups[bT.groupId].label}</span></div>
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
          <div className="sc">
            <span style={{ color: h2hMatch.winner === aId ? "var(--red)" : "var(--text-muted)" }}>{WC.name(aId, lang)}</span>
            <em>{h2hMatch.score[h2hMatch.a === aId ? 0 : 1]}–{h2hMatch.score[h2hMatch.a === aId ? 1 : 0]}</em>
            <span style={{ color: h2hMatch.winner === bId ? "var(--purple)" : "var(--text-muted)" }}>{WC.name(bId, lang)}</span>
          </div>
        ) : (
          <div style={{ marginTop: "10px", color: "var(--text-muted)", fontFamily: "var(--font-cond)", fontSize: "14px" }}>
            {lang === "pt" ? "Sem confronto direto previsto no chaveamento base." : "No predicted direct clash in the base bracket."}
          </div>
        )}
        {h2hMatch && (
          <div style={{ fontFamily: "var(--font-cond)", fontSize: "12px", color: "var(--text-muted)", marginTop: "8px" }}>
            {D.ROUND_SHORT[h2hMatch.round] ? D.ROUND_SHORT[h2hMatch.round][lang] : h2hMatch.round}
          </div>
        )}
      </div>
    </div>
  );
}

/* ========== MAPA ========== */
function MapView({ lang }) {
  const T = I18N[lang];
  const [hovered,  setHovered]  = useState(null);
  const [selected, setSelected] = useState(null);
  const active = selected != null ? selected : hovered;

  const mapSVG = `<svg viewBox="0 0 440 330" xmlns="http://www.w3.org/2000/svg" style="position:absolute;inset:0;width:100%;height:100%;">
  <defs>
    <linearGradient id="ocean26" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#C8DFF5"/>
      <stop offset="100%" stop-color="#A8C8E8"/>
    </linearGradient>
  </defs>
  <rect width="440" height="330" fill="url(#ocean26)"/>
  <!-- Canada -->
  <path d="M40,20 L370,20 L380,50 L360,60 L340,55 L310,65 L280,60 L260,70 L230,65 L200,72 L170,68 L140,75 L110,70 L80,78 L55,72 L38,60 Z" fill="#E8E8E0" stroke="#C8C8B8" stroke-width="1"/>
  <!-- USA -->
  <path d="M55,72 L80,78 L110,70 L140,75 L170,68 L200,72 L230,65 L260,70 L280,60 L310,65 L340,55 L360,60 L370,85 L360,120 L340,145 L320,160 L300,175 L270,185 L240,190 L210,192 L180,190 L155,185 L130,175 L105,165 L80,155 L60,140 L45,120 L42,95 Z" fill="#F0F0E8" stroke="#C8C8B8" stroke-width="1"/>
  <!-- Mexico -->
  <path d="M105,165 L130,175 L155,185 L180,190 L210,192 L220,210 L215,230 L200,248 L185,255 L170,250 L158,238 L148,220 L138,205 L125,195 L110,188 Z" fill="#E8E8E0" stroke="#C8C8B8" stroke-width="1"/>
  <!-- Gulf -->
  <path d="M210,192 L240,190 L260,205 L265,225 L250,245 L230,255 L210,248 L200,248 L215,230 L220,210 Z" fill="url(#ocean26)" stroke="none"/>
  <!-- Florida -->
  <path d="M280,175 L290,188 L285,200 L270,198 L265,185 Z" fill="#F0F0E8" stroke="#C8C8B8" stroke-width="0.8"/>
  <!-- Great Lakes -->
  <ellipse cx="265" cy="110" rx="22" ry="10" fill="#C8DFF5" opacity="0.9"/>
  <ellipse cx="230" cy="105" rx="12" ry="6" fill="#C8DFF5" opacity="0.9"/>
  <!-- Grid -->
  <line x1="0" y1="90"  x2="440" y2="90"  stroke="#B8C8D8" stroke-width="0.4" stroke-dasharray="5,10"/>
  <line x1="0" y1="140" x2="440" y2="140" stroke="#B8C8D8" stroke-width="0.4" stroke-dasharray="5,10"/>
  <line x1="0" y1="190" x2="440" y2="190" stroke="#B8C8D8" stroke-width="0.4" stroke-dasharray="5,10"/>
  <line x1="110" y1="0" x2="110" y2="330" stroke="#B8C8D8" stroke-width="0.4" stroke-dasharray="5,10"/>
  <line x1="220" y1="0" x2="220" y2="330" stroke="#B8C8D8" stroke-width="0.4" stroke-dasharray="5,10"/>
  <line x1="330" y1="0" x2="330" y2="330" stroke="#B8C8D8" stroke-width="0.4" stroke-dasharray="5,10"/>
  </svg>`;

  return (
    <div className="fade-in">
      <div className="section-head">
        <div>
          <div className="eyebrow">{T.mapTitle}</div>
          <h2>{lang === "pt" ? "Cidades-sede" : "Host cities"}</h2>
          <p>{T.mapSub}</p>
        </div>
      </div>

      <div className="map-wrap">
        <div>
          <div className="map-canvas">
            <div className="map-land" dangerouslySetInnerHTML={{ __html: mapSVG }} />
            {D.venues.map((v, i) => (
              <div
                key={i}
                className={"venue-dot " + v.country + (active === i ? " on" : "")}
                style={{ left: v.x + "%", top: v.y + "%" }}
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => setSelected(selected === i ? null : i)}
              />
            ))}
            {active != null && (
              <div className="venue-tip" style={{ left: D.venues[active].x + "%", top: D.venues[active].y + "%" }}>
                <div className="c">{D.venues[active].city}</div>
                <div className="s">{D.venues[active].stadium}</div>
              </div>
            )}
          </div>
          <div className="map-legend">
            <span><i style={{ background: "var(--red)" }}></i>USA (11)</span>
            <span><i style={{ background: "var(--teal)" }}></i>{lang === "pt" ? "México" : "Mexico"} (3)</span>
            <span><i style={{ background: "var(--purple)" }}></i>{lang === "pt" ? "Canadá" : "Canada"} (2)</span>
          </div>
        </div>

        <div className="card venue-list">
          <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--border)", fontFamily: "var(--font-cond)", fontWeight: 700, fontSize: "13px", textTransform: "uppercase", letterSpacing: "2px", color: "var(--text-muted)" }}>
            {T.venuesHead}
          </div>
          {D.venues.map((v, i) => (
            <div
              key={i}
              className={"vrow" + (active === i ? " on" : "")}
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => setSelected(selected === i ? null : i)}
            >
              <span className={"vi " + v.country} />
              <div>
                <div className="c">{v.city}</div>
                <div className="s">{v.stadium}</div>
              </div>
              <div className="cc">{v.country}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ========== ROADMAP ========== */
function RoadmapView({ lang }) {
  const T = I18N[lang];
  const items = lang === "pt" ? [
    { ic: "🔄", title: "Atualização por rodada",   body: "Reexecutar o modelo a cada nova rodada (python -m wc2026.export_web) e recarregar.", tag: "Pipeline" },
    { ic: "🔔", title: "Alertas de resultado",    body: "Notificação push quando um jogo for encerrado e o chaveamento se atualizar.", tag: "Notificações" },
    { ic: "📊", title: "Gráfico de forma",        body: "Mostrar os últimos 10 jogos de uma seleção como barra de momentum.", tag: "Visualização" },
    { ic: "🎯", title: "xG & estatísticas",       body: "Gols esperados, posse, chutes, comparativo histórico por confronto.", tag: "Stats" },
    { ic: "📤", title: "Exportar chaveamento",    body: "Gerar imagem PNG ou PDF do chaveamento personalizado para compartilhar.", tag: "Export" },
    { ic: "🏟️", title: "Agenda por estádio",     body: "Filtrar partidas por cidade/estádio e exibir capacidade e data.", tag: "Calendário" },
  ] : [
    { ic: "🔄", title: "Refresh per round",        body: "Re-run the model each round (python -m wc2026.export_web) and reload.", tag: "Pipeline" },
    { ic: "🔔", title: "Result alerts",           body: "Push notification when a match ends and the bracket updates.", tag: "Notifications" },
    { ic: "📊", title: "Form chart",              body: "Show last 10 matches as a momentum bar for any team.", tag: "Visualisation" },
    { ic: "🎯", title: "xG & stats",              body: "Expected goals, possession, shots, historic head-to-head breakdown.", tag: "Stats" },
    { ic: "📤", title: "Export bracket",          body: "Generate a PNG or PDF of the custom bracket to share.", tag: "Export" },
    { ic: "🏟️", title: "Venue schedule",         body: "Filter matches by city/stadium and display capacity and date.", tag: "Calendar" },
  ];

  return (
    <div className="roadmap">
      <div className="eyebrow" style={{ marginBottom: "10px" }}>{T.roadmapTitle}</div>
      <div className="roadmap-grid">
        {items.map((item, i) => (
          <div key={i} className="rmcard card">
            <div className="h"><span className="ic">{item.ic}</span>{item.title}</div>
            <p>{item.body}</p>
            <div className="tag"># {item.tag}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { TeamView, CompareView, MapView, RoadmapView });
