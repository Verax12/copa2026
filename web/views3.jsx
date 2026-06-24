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

/* ---------- CALENDÁRIO (grade de cards por dia) ---------- */
function CalendarView({ lang, openMatch }) {
  const pt = lang === "pt";
  const days = useMemo(() => {
    const by = {};
    (D.calendar || []).forEach(c => { (by[c.date] = by[c.date] || []).push(c); });
    return Object.keys(by).sort().map(date => ({
      date,
      games: by[date].slice().sort((a, b) => (a.kickoff.local || "").localeCompare(b.kickoff.local || "")),
    }));
  }, []);

  const [filter, setFilter] = useState("all");   // all | played | upcoming
  if (!days.length) return <div className="datanote">Sem calendário disponível.</div>;

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
    if (days.some(d => d.date === todayIso)) return todayIso;
    const next = days.find(d => d.date >= todayIso);
    return next ? next.date : days[days.length - 1].date;
  }, [days, todayIso]);
  const exactToday = targetDate === todayIso;
  const targetFmt = fmtDate(targetDate, lang);

  function scrollToCurrentDay(behavior) {
    const el = document.querySelector(`[data-cal-date="${targetDate}"]`);
    if (el) el.scrollIntoView({ behavior: behavior || "smooth", block: "start" });
  }

  useEffect(() => {
    const timer = setTimeout(() => scrollToCurrentDay("auto"), 120);
    return () => clearTimeout(timer);
  }, [targetDate]);

  const total = (D.calendar || []).length;
  const playedN = (D.calendar || []).filter(g => g.played).length;

  const filtered = days
    .map(day => ({ ...day, games: day.games.filter(g => filter === "all" ? true : filter === "played" ? g.played : !g.played) }))
    .filter(day => day.games.length);

  return (
    <div className="fade-in">
      <div className="section-head">
        <div>
          <div className="eyebrow">{pt ? "Fase de grupos" : "Group stage"}</div>
          <h2>{pt ? "Calendário" : "Calendar"}</h2>
          <p>{pt ? "Clique em qualquer jogo para abrir os detalhes (escalação de gols, estatísticas e previsão) sem sair desta página."
                 : "Click any game to open its details (goals, stats and prediction) without leaving this page."}</p>
          <button className="btn cal-today-btn" onClick={() => scrollToCurrentDay("smooth")}>
            📍 {exactToday ? (pt ? "Hoje" : "Today") : (pt ? "Próximo dia" : "Next matchday")}: {targetFmt.dd} {targetFmt.moLong}
          </button>
        </div>
        <div className="cal-filter">
          <button className={"chip" + (filter === "all" ? " on" : "")} onClick={() => setFilter("all")}>{pt ? "Todos" : "All"} <b>{total}</b></button>
          <button className={"chip" + (filter === "played" ? " on" : "")} onClick={() => setFilter("played")}>{pt ? "Realizados" : "Played"} <b>{playedN}</b></button>
          <button className={"chip" + (filter === "upcoming" ? " on" : "")} onClick={() => setFilter("upcoming")}>{pt ? "A jogar" : "Upcoming"} <b>{total - playedN}</b></button>
        </div>
      </div>

      <div className="cal-days">
        {filtered.map(day => {
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
        })}
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
  return (
    <button className={"mtile" + (g.played ? " played" : "")} onClick={onClick}
            title={pt ? "Ver detalhes do jogo" : "See match details"}>
      <div className="mtile-top">
        <span className="mtile-grp">{pt ? "Grupo" : "Grp"} {g.group}</span>
        <span className={"mtile-status" + (g.played ? " ft" : "")}>{g.played ? (pt ? "Encerrado" : "Full-time") : `${time}${g.kickoff.br ? " BR" : ""}`}</span>
      </div>
      <div className="mtile-row">
        <span className={"mtile-team" + (homeWin ? " win" : "")}><Flag id={g.home} w={26} /><span className="nm">{WC.name(g.home, lang)}</span></span>
        <span className="mtile-sc">{g.played ? g.actual[0] : ""}</span>
      </div>
      <div className="mtile-row">
        <span className={"mtile-team" + (awayWin ? " win" : "")}><Flag id={g.away} w={26} /><span className="nm">{WC.name(g.away, lang)}</span></span>
        <span className="mtile-sc">{g.played ? g.actual[1] : ""}</span>
      </div>
      <div className="mtile-foot">
        <span className="mtile-stad">🏟️ {g.stadium}</span>
        {!g.played && <span className="mtile-pred">{pt ? "Prev." : "Pred."} {g.pred.score[0]}–{g.pred.score[1]}</span>}
      </div>
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

/* ---------- MODAL DE DETALHE / PREVISÃO DE UM JOGO ---------- */
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
    hit = oc(entry.actual[0], entry.actual[1]) === oc(entry.pre.score[0], entry.pre.score[1]);
    exact = entry.actual[0] === entry.pre.score[0] && entry.actual[1] === entry.pre.score[1];
  }

  return (
    <Modal open={open} onClose={onClose} labelledBy="mm-title">
      <div className="mm-bar">
        <span className="mm-comp">{pt ? "Copa do Mundo 2026" : "World Cup 2026"} · {pt ? "Grupo" : "Group"} {entry.group}</span>
        <button className="mm-close" onClick={onClose} aria-label={pt ? "Fechar" : "Close"}>✕</button>
      </div>

      <div className="mm-body">
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

        {/* gols marcados */}
        {entry.played && goals && (goals.home.length || goals.away.length) ? (
          <div className="mm-goals">
            <GoalsList goals={goals.home} align="left" />
            <span className="mm-goals-ic">⚽</span>
            <GoalsList goals={goals.away} align="right" />
          </div>
        ) : null}

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
                pt ? (exact ? "cravou o placar!" : hit ? "acertou o resultado" : "errou o resultado")
                   : (exact ? "exact score!" : hit ? "right result" : "wrong result")
              }</span></div>
              <div><div className="lb">{pt ? "Previsto" : "Predicted"}</div><div className="v" style={{ color: "var(--text-muted)" }}>{entry.pre.score[0]}–{entry.pre.score[1]}</div></div>
            </div>
            <div style={{ marginTop: "12px" }}><WDLBar ph={entry.pre.ph} pd={entry.pre.pd} pa={entry.pre.pa} lang={lang} /></div>
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
            <div className="md-note">{pt ? "Placar mais provável segundo o modelo (ensemble). Empate alto é comum — veja as probabilidades acima."
                                         : "Most likely scoreline per the (ensemble) model. Draws are common — see probabilities above."}</div>
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
