/* ===== views3.jsx — Calendário (grade) + Modal de detalhe do jogo ===== */

const MONTHS = { pt: ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"],
                 en: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"] };
const WEEKD = { pt: ["Dom","Seg","Ter","Qua","Qui","Sex","Sáb"],
                en: ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"] };
const MONTHS_LONG = { pt: ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"],
                      en: ["January","February","March","April","May","June","July","August","September","October","November","December"] };

function fmtDate(iso, lang) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return { wd: WEEKD[lang][dt.getUTCDay()], dd: d, mo: MONTHS[lang][m - 1], moLong: MONTHS_LONG[lang][m - 1] };
}

/* barra de probabilidade Vitória / Empate / Derrota */
function WDLBar({ ph, pd, pa, lang }) {
  const pct = (x) => Math.round(x * 100);
  return (
    <div className="wdl">
      <div className="wdl-bar">
        <i style={{ width: pct(ph) + "%", background: "var(--red)" }} />
        <i style={{ width: pct(pd) + "%", background: "var(--text-muted)" }} />
        <i style={{ width: pct(pa) + "%", background: "var(--purple)" }} />
      </div>
      <div className="wdl-lbl">
        <span style={{ color: "var(--red)" }}>{pct(ph)}% {lang === "pt" ? "vitória" : "win"}</span>
        <span>{pct(pd)}% {lang === "pt" ? "empate" : "draw"}</span>
        <span style={{ color: "var(--purple)" }}>{pct(pa)}% {lang === "pt" ? "derrota" : "loss"}</span>
      </div>
    </div>
  );
}

function venueKey(g) {
  return D.slug((g.city || "") + "-" + (g.stadium || ""));
}
function normalizeTeamFilter(v) {
  if (!v || v === "all") return "all";
  const id = D.teamFromKey(v);
  return id == null ? "all" : D.teamSlug(id, "en");
}

/* ---------- CALENDÁRIO (grade de cards por dia) ---------- */
function CalendarView({ lang, openMatch, initFilters, onRouteChange }) {
  const pt = lang === "pt";
  const days = useMemo(() => {
    const by = {};
    (D.calendar || []).forEach(c => { (by[c.date] = by[c.date] || []).push(c); });
    return Object.keys(by).sort().map(date => ({
      date,
      games: by[date].slice().sort((a, b) => (a.kickoff.local || "").localeCompare(b.kickoff.local || "")),
    }));
  }, []);

  const [filters, setFilters] = useState(() => ({
    status: initFilters?.status || "all",
    team: normalizeTeamFilter(initFilters?.team),
    group: initFilters?.group || "all",
    venue: initFilters?.venue || "all",
    date: initFilters?.date || "",
  }));
  useEffect(() => {
    setFilters(f => ({
      status: initFilters?.status || "all",
      team: normalizeTeamFilter(initFilters?.team),
      group: initFilters?.group || "all",
      venue: initFilters?.venue || "all",
      date: initFilters?.date || f.date || "",
    }));
  }, [initFilters?.status, initFilters?.team, initFilters?.group, initFilters?.venue, initFilters?.date]);

  // Ao abrir a aba Calendário, rola direto para o dia atual. Se não houver
  // jogos exatamente hoje, usa o próximo dia do calendário; se a Copa já passou,
  // cai para o último dia disponível.
  const todayIso = useMemo(() => {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const d = String(now.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }, []);
  const targetDate = useMemo(() => {
    if (!days.length) return "";
    if (filters.date && days.some(d => d.date === filters.date)) return filters.date;
    if (days.some(d => d.date === todayIso)) return todayIso;
    const next = days.find(d => d.date >= todayIso);
    return next ? next.date : days[days.length - 1].date;
  }, [days, todayIso, filters.date]);
  const exactToday = targetDate === todayIso;
  const targetFmt = targetDate ? fmtDate(targetDate, lang) : null;

  function scrollToCurrentDay(behavior) {
    if (!targetDate) return;
    const el = document.querySelector(`[data-cal-date="${targetDate}"]`);
    if (el) el.scrollIntoView({ behavior: behavior || "smooth", block: "start" });
  }

  useEffect(() => {
    const timer = setTimeout(() => scrollToCurrentDay("auto"), 120);
    return () => clearTimeout(timer);
  }, [targetDate]);

  const total = (D.calendar || []).length;
  const playedN = (D.calendar || []).filter(g => g.played).length;
  const upcomingN = total - playedN;
  const koN = (D.calendar || []).filter(g => g.round).length;

  const sortedTeams = useMemo(() =>
    [...D.teams].sort((a, b) => WC.name(a.id, lang).localeCompare(WC.name(b.id, lang))), [lang]);
  const venueOptions = useMemo(() => {
    const map = {};
    (D.calendar || []).forEach(g => { map[venueKey(g)] = { key: venueKey(g), label: `${g.city || g.stadium} · ${g.stadium}` }; });
    return Object.values(map).sort((a, b) => a.label.localeCompare(b.label));
  }, []);

  function updateFilter(key, value) {
    const next = { ...filters, [key]: value };
    // ao trocar filtros, volta para o alvo dinâmico (hoje/próximo dia), exceto
    // se o usuário clicou explicitamente no botão de data.
    if (key !== "date") next.date = "";
    setFilters(next);
    if (onRouteChange) onRouteChange(next);
  }
  function clearFilters() {
    const next = { status: "all", team: "all", group: "all", venue: "all", date: "" };
    setFilters(next);
    if (onRouteChange) onRouteChange(next);
  }

  const filtered = days
    .map(day => ({ ...day, games: day.games.filter(g => {
      if (filters.status !== "all" && (filters.status === "played") !== !!g.played) return false;
      if (filters.team !== "all") {
        const tid = D.teamFromKey(filters.team);
        if (tid == null || (g.home !== tid && g.away !== tid)) return false;
      }
      if (filters.group === "__ko" && !g.round) return false;
      if (filters.group !== "all" && filters.group !== "__ko" && g.group !== filters.group) return false;
      if (filters.venue !== "all" && venueKey(g) !== filters.venue) return false;
      return true;
    }) }))
    .filter(day => day.games.length);
  const filteredN = filtered.reduce((s, d) => s + d.games.length, 0);

  if (!days.length) return <div className="datanote">Sem calendário disponível.</div>;

  return (
    <div className="fade-in">
      <div className="section-head">
        <div>
          <div className="eyebrow">{filters.group === "__ko" ? (pt ? "Mata-mata (R32+)" : "Knockout stage (R32+)") : (pt ? "Fase de grupos" : "Group stage")}</div>
          <h2>{pt ? "Calendário" : "Calendar"}</h2>
          <p>{pt ? "Clique em qualquer jogo para abrir os detalhes (escalação de gols, estatísticas e previsão) sem sair desta página."
                 : "Click any game to open its details (goals, stats and prediction) without leaving this page."}</p>
          {targetFmt && (
            <button className="btn cal-today-btn" onClick={() => scrollToCurrentDay("smooth")}>
              📍 {exactToday ? (pt ? "Hoje" : "Today") : (pt ? "Próximo dia" : "Next matchday")}: {targetFmt.dd} {targetFmt.moLong}
            </button>
          )}
        </div>
        <div className="cal-filter">
          <button className={"chip" + (filters.status === "all" ? " on" : "")} onClick={() => updateFilter("status", "all")}>{pt ? "Todos" : "All"} <b>{total}</b></button>
          <button className={"chip" + (filters.status === "played" ? " on" : "")} onClick={() => updateFilter("status", "played")}>{pt ? "Realizados" : "Played"} <b>{playedN}</b></button>
          <button className={"chip" + (filters.status === "upcoming" ? " on" : "")} onClick={() => updateFilter("status", "upcoming")}>{pt ? "A jogar" : "Upcoming"} <b>{upcomingN}</b></button>
          <button className={"chip" + (filters.group === "__ko" ? " on" : "")} onClick={() => updateFilter("group", "__ko")}>{pt ? "Mata-mata" : "KO"} <b>{koN}</b></button>
        </div>
      </div>

      <div className="cal-advanced card">
        <div className="cal-adv-title">{pt ? "Filtros rápidos" : "Quick filters"} <span>{filteredN}/{total} {pt ? "jogos" : "games"}</span></div>
        <div className="cal-controls">
          <label>
            <span>{pt ? "Seleção" : "Team"}</span>
            <select value={filters.team} onChange={e => updateFilter("team", e.target.value)}>
              <option value="all">{pt ? "Todas" : "All"}</option>
              {sortedTeams.map(t => <option key={t.id} value={D.teamSlug(t.id, "en")}>{WC.name(t.id, lang)}</option>)}
            </select>
          </label>
          <label>
            <span>{pt ? "Grupo" : "Group"}</span>
            <select value={filters.group} onChange={e => updateFilter("group", e.target.value)}>
              <option value="all">{pt ? "Todos" : "All"}</option>
              {D.GROUP_LABELS.map(g => <option key={g} value={g}>{pt ? "Grupo" : "Group"} {g}</option>)}
              <option value="__ko">{pt ? "Mata-mata (R32+)" : "Knockout (R32+)"}</option>
            </select>
          </label>
          <label>
            <span>{pt ? "Estádio / cidade" : "Venue / city"}</span>
            <select value={filters.venue} onChange={e => updateFilter("venue", e.target.value)}>
              <option value="all">{pt ? "Todos" : "All"}</option>
              {venueOptions.map(v => <option key={v.key} value={v.key}>{v.label}</option>)}
            </select>
          </label>
          <button className="btn cal-clear" onClick={clearFilters}>{pt ? "Limpar" : "Clear"}</button>
        </div>
      </div>

      <div className="cal-days">
        {filtered.length ? filtered.map(day => {
          const f = fmtDate(day.date, lang);
          const isTarget = day.date === targetDate;
          return (
            <div key={day.date} data-cal-date={day.date} className={"cal-dayblock" + (isTarget ? " today" : "")}>
              <div className="cal-dayhdr">
                <span className="cd-num">{f.dd}</span>
                <div className="cd-meta">
                  <b>{f.wd}, {f.dd} {f.moLong}</b>
                  <span>
                    {isTarget && <em>{exactToday ? (pt ? "Hoje" : "Today") : (pt ? "Dia-alvo" : "Target day")} · </em>}
                    {day.games.length} {pt ? (day.games.length === 1 ? "jogo" : "jogos") : (day.games.length === 1 ? "game" : "games")}
                  </span>
                </div>
              </div>
              <div className="cal-grid">
                {day.games.map((g, i) => (
                  <MatchTile key={i} g={g} lang={lang} onClick={() => openMatch(g)} />
                ))}
              </div>
            </div>
          );
        }) : (
          <div className="datanote"><span>🔎</span><span>{pt ? "Nenhum jogo encontrado com os filtros atuais." : "No games found with the current filters."}</span></div>
        )}
      </div>
    </div>
  );
}

/* card de um jogo na grade do calendário */
function MatchTile({ g, lang, onClick }) {
  const pt = lang === "pt";
  const time = g.kickoff.br || g.kickoff.local;
  const homeWin = g.played && g.actual[0] > g.actual[1];
  const awayWin = g.played && g.actual[1] > g.actual[0];
  const roundMap = {
    "R32": pt ? "R32" : "R32",
    "Round of 16": pt ? "Oitavas" : "R16",
    "Quarter-final": pt ? "Quartas" : "QF",
    "Semi-final": pt ? "Semifinais" : "SF",
    "Final": pt ? "Final" : "Final",
    "Match for third place": pt ? "3º lugar" : "3rd",
  };
  const phaseLabel = g.round ? (roundMap[g.round] || g.round) : (g.group ? `${pt ? "Grupo" : "Grp"} ${g.group}` : "");
  return (
    <button className={"mtile" + (g.played ? " played" : "") + (g.round ? " ko" : "")} onClick={onClick}
            title={pt ? "Ver detalhes do jogo" : "See match details"}>
      <div className="mtile-top">
        <span className="mtile-grp">{phaseLabel}</span>
        <span className={"mtile-status" + (g.played ? " ft" : "")}>{g.played ? (pt ? "Encerrado" : "Full-time") : time}</span>
      </div>
      <div className="mtile-kickoff">🕒 {time}{g.kickoff && g.kickoff.br ? " BR" : ""}</div>
      <div className="mtile-row">
        <span className={"mtile-team" + (homeWin ? " win" : "")}>
          {g.home != null ? <Flag id={g.home} w={26} /> : null}
          <span className="nm">{g.tbd_home ? `Vencedor jogo ${g.tbd_home.slice(1)}` : (g.home != null ? WC.name(g.home, lang) : "TBD")}</span>
        </span>
        <span className="mtile-sc">{g.played ? g.actual[0] : ""}</span>
      </div>
      <div className="mtile-row">
        <span className={"mtile-team" + (awayWin ? " win" : "")}>
          {g.away != null ? <Flag id={g.away} w={26} /> : null}
          <span className="nm">{g.tbd_away ? `Vencedor jogo ${g.tbd_away.slice(1)}` : (g.away != null ? WC.name(g.away, lang) : "TBD")}</span>
        </span>
        <span className="mtile-sc">{g.played ? g.actual[1] : ""}</span>
      </div>
      <div className="mtile-foot">
        <span className="mtile-stad">🏟️ {g.stadium}</span>
        {!g.played && g.pred && g.pred.score && <span className="mtile-pred">{pt ? "Prev." : "Pred."} {g.pred.score[0]}–{g.pred.score[1]}</span>}
      </div>
      {!g.played && g.pred && g.home != null && g.away != null && (
        <div className="mtile-fav">
          <FavoriteBadge ph={g.pred.ph} pd={g.pred.pd} pa={g.pred.pa} home={g.home} away={g.away} lang={lang} size="sm" />
        </div>
      )}
    </button>
  );
}

/* lista de gols (autor · minuto · pênalti/contra) de um lado */
function GoalsList({ goals, align }) {
  if (!goals || !goals.length) return <div className={"goals-col " + align} />;
  return (
    <div className={"goals-col " + align}>
      {goals.map((gl, i) => (
        <div key={i} className="goal-item">
          <span className="g-ball">⚽</span>
          <span className="g-name">{gl.name}{gl.penalty ? " (P)" : ""}{gl.owngoal ? " (GC)" : ""}</span>
          <span className="g-min">{gl.minute}'</span>
        </div>
      ))}
    </div>
  );
}

/* minuto "90+4" -> número ordenável */
function minToNum(min) {
  const mm = String(min || "").replace("'", "").split("+");
  const a = parseInt(mm[0], 10);
  return isNaN(a) ? 9999 : a * 100 + (mm[1] ? parseInt(mm[1], 10) || 0 : 0);
}

/* linha do tempo dos gols (mandante à esquerda, visitante à direita) */
function GoalsTimeline({ entry, lang }) {
  const g = entry.goals;
  if (!g || (!(g.home || []).length && !(g.away || []).length)) return null;
  const pt = lang === "pt";
  const events = [
    ...(g.home || []).map(x => ({ ...x, side: "home" })),
    ...(g.away || []).map(x => ({ ...x, side: "away" })),
  ].sort((a, b) => minToNum(a.minute) - minToNum(b.minute));
  const label = (e) => `${e.name}${e.penalty ? " (P)" : ""}${e.owngoal ? (pt ? " (contra)" : " (OG)") : ""}`;
  return (
    <div className="mm-timeline" aria-label={pt ? "Gols do jogo" : "Match goals"}>
      {events.map((e, i) => (
        <div key={i} className={"tl-row " + e.side}>
          <span className="tl-cell left">{e.side === "home" && <span className="tl-goal">⚽ {label(e)}</span>}</span>
          <span className="tl-min">{e.minute}'</span>
          <span className="tl-cell right">{e.side === "away" && <span className="tl-goal">{label(e)} ⚽</span>}</span>
        </div>
      ))}
    </div>
  );
}

/* ---------- MODAL DE DETALHE / PREVISÃO DE UM JOGO ---------- */
/* Hero do modal: pôster oficial do TheSportsDB quando existe; senão, um banner
   gerado no estilo Copa 2026 (bandeiras + marca + data/estádio) — assim TODO
   jogo ganha o mesmo header visual. */
function MatchPoster({ entry, f, k, lang }) {
  const pt = lang === "pt";
  const home = D.byId(entry.home), away = D.byId(entry.away);
  const timeline = `${k.local || ""}${k.offset ? " " + k.offset : ""}`.trim();
  const place = `${entry.stadium || ""}${entry.city ? " · " + entry.city : ""}`.trim();
  const aria = `${WC.name(entry.home, lang)} × ${WC.name(entry.away, lang)}`;
  if (entry.thumb) return <img className="mm-poster" src={entry.thumb} alt={aria} loading="lazy" />;
  return (
    <div className="mm-hero" role="img" aria-label={aria}>
      <div className="mm-hero-row">
        {home ? <img className="mm-hero-flag" src={WC.flag(home.iso, 160)} alt="" loading="lazy" /> : <span className="mm-hero-flag mm-hero-tbd" />}
        <div className="mm-hero-badge">
          <span className="mm-hero-26">26</span>
          <span className="mm-hero-cup">FIFA · {pt ? "Copa do Mundo" : "World Cup"}</span>
        </div>
        {away ? <img className="mm-hero-flag" src={WC.flag(away.iso, 160)} alt="" loading="lazy" /> : <span className="mm-hero-flag mm-hero-tbd" />}
      </div>
      <div className="mm-hero-meta">
        <span>📅 {f.wd}, {f.dd} {f.moLong} 2026</span>
        {timeline ? <span>🕐 {timeline}</span> : null}
        {place ? <span>🏟️ {place}</span> : null}
      </div>
    </div>
  );
}

function MatchModal({ lang, entry, onClose }) {
  const pt = lang === "pt";
  const open = !!entry;
  if (!open) return <Modal open={false} onClose={onClose} />;

  const f = fmtDate(entry.date, lang);
  const k = entry.kickoff || {};
  const stats = entry.played ? D.getMatchStats(entry.home, entry.away) : null;
  const brTxt = k.br ? `${k.br} ${pt ? "Brasília" : "BRT"}${k.brShift > 0 ? " (+1d)" : k.brShift < 0 ? " (-1d)" : ""}` : "";
  const goals = entry.goals || null;

  let hit = null, exact = false;
  if (entry.played && entry.pre) {
    const oc = (a, b) => (a > b ? 0 : a === b ? 1 : 2);
    // "acertou o resultado" = V/E/D MAIS PROVÁVEL (argmax), coerente com o
    // "acerto de resultado" do painel de Desempenho. "cravou o placar" (exact) é
    // o placar exato, mostrado como selo 🎯 à parte — os dois podem divergir.
    const probs = [entry.pre.ph, entry.pre.pd, entry.pre.pa];
    const predOc = probs.indexOf(Math.max(...probs));
    hit = predOc === oc(entry.actual[0], entry.actual[1]);
    exact = entry.actual[0] === entry.pre.score[0] && entry.actual[1] === entry.pre.score[1];
  }

  return (
    <Modal open={open} onClose={onClose} labelledBy="mm-title" initialFocusSelector=".mm-close">
      <div className="mm-bar">
        <span className="mm-comp">{pt ? "Copa do Mundo 2026" : "World Cup 2026"} · {pt ? "Grupo" : "Group"} {entry.group}{entry.round ? " · " + entry.round : ""}{entry.num ? " · #" + entry.num : ""}</span>
        <button className="mm-close" onClick={onClose} aria-label={pt ? "Fechar" : "Close"}>✕</button>
      </div>

      <div className="mm-body">
        {/* hero do jogo: pôster oficial quando há, senão banner gerado */}
        <MatchPoster entry={entry} f={f} k={k} lang={lang} />

        {/* placar / confronto */}
        <div className="mm-score" id="mm-title">
          <div className="mm-team">
            <Flag id={entry.home} w={66} />
            <div className="nm">{WC.name(entry.home, lang)}</div>
          </div>
          <div className="mm-mid">
            {entry.played
              ? <div className="mm-result">{entry.actual[0]}<span>–</span>{entry.actual[1]}</div>
              : <div className="mm-vs">VS</div>}
            <div className="mm-state">
              {entry.played
                ? (pt ? "Encerrado" : "Full-time") + (entry.ht ? ` · ${pt ? "INT" : "HT"} ${entry.ht[0]}–${entry.ht[1]}` : "")
                : (pt ? "Previsão do modelo" : "Model prediction")}
            </div>
          </div>
          <div className="mm-team">
            <Flag id={entry.away} w={66} />
            <div className="nm">{WC.name(entry.away, lang)}</div>
          </div>
        </div>

        {/* linha do tempo dos gols */}
        {entry.played ? <GoalsTimeline entry={entry} lang={lang} /> : null}

        {/* info do jogo */}
        <div className="mm-info">
          <span>📅 {f.wd}, {f.dd} {f.moLong} 2026</span>
          <span>🕐 {k.local}{k.offset ? " " + k.offset : ""}{brTxt ? " · " + brTxt : ""}</span>
          <span>🏟️ {entry.stadium}{entry.city ? " · " + entry.city : ""}</span>
        </div>

        {/* resultado x previsão (se já aconteceu) */}
        {entry.played && entry.pre && (
          <div className="mm-card teal">
            <div className="mm-cap">{pt ? "Resultado real × previsão do projeto" : "Actual vs project prediction"}</div>
            <div className="mm-cmp">
              <div><div className="lb">{pt ? "Real" : "Actual"}</div><div className="v">{entry.actual[0]}–{entry.actual[1]}</div></div>
              <div className="mm-cmp-mid">{hit ? "✅" : "❌"}<span>{
                pt ? (hit ? "acertou o resultado" : "errou o resultado")
                   : (hit ? "right result" : "wrong result")
              }</span>{exact && <span className="mm-exact" title={pt ? "o placar exato bateu" : "exact scoreline matched"}>🎯 {pt ? "cravou o placar!" : "exact score!"}</span>}</div>
              <div><div className="lb">{pt ? "Previsto" : "Predicted"}</div><div className="v" style={{ color: "var(--text-muted)" }}>{entry.pre.score[0]}–{entry.pre.score[1]}</div></div>
            </div>
            <div style={{ marginTop: "12px" }}><WDLBar ph={entry.pre.ph} pd={entry.pre.pd} pa={entry.pre.pa} lang={lang} /></div>
            <div className="mm-fav">
              <span className="mm-fav-lbl">{pt ? "Favorito previsto" : "Predicted favorite"}</span>
              <FavoriteBadge ph={entry.pre.ph} pd={entry.pre.pd} pa={entry.pre.pa} home={entry.home} away={entry.away} lang={lang} />
            </div>
          </div>
        )}

        {/* estatísticas detalhadas (se já aconteceu) */}
        {entry.played && (stats ? (
          <div className="mm-card">
            <div className="mm-cap">{pt ? "Estatísticas do jogo" : "Match stats"} · {stats.source}</div>
            <div className="ms-hd"><span>{WC.name(entry.home, lang)}</span><span className="ms-src">×</span><span>{WC.name(entry.away, lang)}</span></div>
            {stats.stats.map((s, j) => {
              const tot = (s.you + s.them) || 1;
              return (
                <div key={j} className="ms-row">
                  <span className={"ms-v" + (s.you > s.them ? " win" : "")}>{s.you}</span>
                  <div className="ms-bars">
                    <div className="ms-label">{pt ? s.pt : s.en}</div>
                    <div className="ms-track"><i className="you" style={{ width: (s.you / tot * 100) + "%" }} /><i className="them" style={{ width: (s.them / tot * 100) + "%" }} /></div>
                  </div>
                  <span className={"ms-v them" + (s.them > s.you ? " win" : "")}>{s.them}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="datanote" style={{ margin: "4px 0 0" }}><span>ℹ️</span><span>{pt ? "Estatísticas detalhadas não disponíveis para este jogo (a fonte gratuita cobre apenas alguns)." : "Detailed stats not available for this game."}</span></div>
        ))}

        {/* previsão (se ainda não aconteceu) */}
        {!entry.played && (
          <div className="mm-card accent">
            <div className="mm-cap">{pt ? "Previsão do projeto" : "Project prediction"}</div>
            <div className="md-predrow">
              <div className="md-pred">{entry.pred.score[0]}<span>–</span>{entry.pred.score[1]}</div>
              <div className="md-xg"><div className="lb">{pt ? "gols esperados (xG)" : "expected goals (xG)"}</div><div className="v">{entry.pred.xg[0]} – {entry.pred.xg[1]}</div></div>
            </div>
            <WDLBar ph={entry.pred.ph} pd={entry.pred.pd} pa={entry.pred.pa} lang={lang} />
            <div className="mm-fav">
              <span className="mm-fav-lbl">{pt ? "Favorito" : "Favorite"}</span>
              <FavoriteBadge ph={entry.pred.ph} pd={entry.pred.pd} pa={entry.pred.pa} home={entry.home} away={entry.away} lang={lang} />
            </div>
            {entry.pred.top && entry.pred.top.length ? (
              <div className="mm-top">
                <div className="mm-top-lbl">{pt ? "Placares mais prováveis" : "Most likely scorelines"}</div>
                <div className="mm-top-row">
                  {entry.pred.top.map((t, i) => (
                    <span key={i} className="mm-top-chip"><b>{t[0]}–{t[1]}</b> {Math.round(t[2] * 100)}%</span>
                  ))}
                </div>
              </div>
            ) : null}
            <div className="md-note">{pt ? "O modelo primeiro aponta o resultado favorito (acima) e depois o placar mais provável dentro dele — por isso o placar nunca contradiz o favorito."
                                         : "The model first picks the favored result (above), then the most likely scoreline within it — so the score never contradicts the favorite."}</div>
          </div>
        )}

        {/* link de melhores momentos */}
        {entry.played && entry.video && (
          <a className="mm-video" href={entry.video} target="_blank" rel="noopener noreferrer">
            ▶ {pt ? "Ver melhores momentos" : "Watch highlights"}
          </a>
        )}
      </div>
    </Modal>
  );
}

Object.assign(window, { CalendarView, MatchModal, WDLBar, fmtDate });
