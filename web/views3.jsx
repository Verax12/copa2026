/* ===== views3.jsx — Calendário + Detalhe/Previsão de jogo ===== */

const MONTHS = { pt: ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"],
                 en: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"] };
const WEEKD = { pt: ["Dom","Seg","Ter","Qua","Qui","Sex","Sáb"],
                en: ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"] };

function fmtDate(iso, lang) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return { wd: WEEKD[lang][dt.getUTCDay()], dd: d, mo: MONTHS[lang][m - 1] };
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

/* ---------- CALENDÁRIO ---------- */
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
  const firstUpcoming = days.find(d => d.games.some(g => !g.played));
  const [open, setOpen] = useState(() => (firstUpcoming || days[0] || {}).date);

  if (!days.length) return <div className="datanote">Sem calendário disponível.</div>;

  return (
    <div className="fade-in">
      <div className="section-head">
        <div>
          <div className="eyebrow">{pt ? "Fase de grupos" : "Group stage"}</div>
          <h2>{pt ? "Calendário" : "Calendar"}</h2>
          <p>{pt ? "Clique num dia para ver os jogos; clique num jogo para a previsão (ou o resultado, se já aconteceu)."
                 : "Click a day to see its games; click a game for the prediction (or result, if already played)."}</p>
        </div>
      </div>

      <div className="cal-list">
        {days.map(day => {
          const isOpen = open === day.date;
          const f = fmtDate(day.date, lang);
          const allPlayed = day.games.every(g => g.played);
          return (
            <div key={day.date} className="cal-day card">
              <div className="cal-dhead" onClick={() => setOpen(isOpen ? null : day.date)}>
                <div className="cal-date"><span className="dd">{f.dd}</span><span className="mo">{f.mo}</span></div>
                <div className="cal-dinfo">
                  <b>{f.wd}</b>
                  <span>{day.games.length} {pt ? "jogos" : "games"}{allPlayed ? (pt ? " · realizados" : " · played") : ""}</span>
                </div>
                <span className="cal-chev">{isOpen ? "▾" : "▸"}</span>
              </div>
              {isOpen && (
                <div className="cal-games">
                  {day.games.map((g, i) => (
                    <div key={i} className="cal-game" onClick={() => openMatch(g)}
                         title={pt ? "Ver previsão / detalhe" : "See prediction / detail"}>
                      <span className="cg-time">
                        {g.kickoff.br || g.kickoff.local}<small>{g.kickoff.br ? " BR" : ""}</small>
                      </span>
                      <span className="cg-grp">{pt ? "Grupo" : "Grp"} {g.group}</span>
                      <div className="cg-teams">
                        <span className="cg-side"><Flag id={g.home} w={24} /><span className="cg-nm">{WC.name(g.home, lang)}</span></span>
                        <span className="cg-score">{g.played ? `${g.actual[0]}–${g.actual[1]}` : "×"}</span>
                        <span className="cg-side r"><span className="cg-nm">{WC.name(g.away, lang)}</span><Flag id={g.away} w={24} /></span>
                      </div>
                      <span className="cg-stad">{g.stadium}</span>
                      <span className={"cg-tag" + (g.played ? " real" : "")}>{g.played ? (pt ? "● Resultado" : "● Result") : (pt ? "Previsão" : "Predicted")}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------- DETALHE / PREVISÃO DE UM JOGO ---------- */
function MatchDetailView({ lang, entry, back }) {
  const pt = lang === "pt";
  if (!entry) return <CalendarView lang={lang} openMatch={() => {}} />;
  const f = fmtDate(entry.date, lang);
  const k = entry.kickoff;
  const stats = entry.played ? D.getMatchStats(entry.home, entry.away) : null;
  const brTxt = k.br ? `${k.br} ${pt ? "Brasília" : "BRT"}${k.brShift > 0 ? " (+1d)" : k.brShift < 0 ? " (-1d)" : ""}` : "";

  // ✓/✗ pelo RESULTADO (V/E/D) do placar previsto vs o real — coerente com o que é exibido
  let hit = null, exact = false;
  if (entry.played && entry.pre) {
    const oc = (a, b) => (a > b ? 0 : a === b ? 1 : 2);
    hit = oc(entry.actual[0], entry.actual[1]) === oc(entry.pre.score[0], entry.pre.score[1]);
    exact = entry.actual[0] === entry.pre.score[0] && entry.actual[1] === entry.pre.score[1];
  }

  return (
    <div className="fade-in">
      <button className="btn" onClick={back} style={{ marginBottom: "14px" }}>← {pt ? "Calendário" : "Calendar"}</button>

      <div className="md-head card card-accent">
        <div className="md-team"><Flag id={entry.home} w={72} /><div className="nm">{WC.name(entry.home, lang)}</div></div>
        <div className="md-center">
          {entry.played
            ? <div className="md-score">{entry.actual[0]}<span>–</span>{entry.actual[1]}</div>
            : <div className="md-vs">×</div>}
          <span className="pill">{pt ? "Grupo" : "Group"} {entry.group}</span>
        </div>
        <div className="md-team"><Flag id={entry.away} w={72} /><div className="nm">{WC.name(entry.away, lang)}</div></div>
      </div>

      <div className="md-info card">
        <span>📅 {f.wd}, {f.dd} {f.mo} 2026</span>
        <span>🕐 {k.local}{k.offset ? " " + k.offset : ""}{brTxt ? " · " + brTxt : ""}</span>
        <span>🏟️ {entry.stadium}{entry.city ? " · " + entry.city : ""}</span>
      </div>

      {entry.played ? (
        <React.Fragment>
          {entry.pre && (
            <div className="card card-accent-teal md-block">
              <div className="eyebrow" style={{ color: "var(--teal)" }}>{pt ? "Resultado real × previsão do projeto" : "Actual vs project prediction"}</div>
              <div className="md-cmp">
                <div><div className="lb">{pt ? "Resultado real" : "Actual"}</div><div className="v">{entry.actual[0]}–{entry.actual[1]}</div></div>
                <div className="md-cmp-mid">{hit ? "✅" : "❌"}<span>{
                  pt ? (exact ? "cravou o placar!" : hit ? "acertou o resultado" : "errou o resultado")
                     : (exact ? "exact score!" : hit ? "right result" : "wrong result")
                }</span></div>
                <div><div className="lb">{pt ? "Previsto (pré-jogo)" : "Predicted (pre-match)"}</div><div className="v" style={{ color: "var(--text-muted)" }}>{entry.pre.score[0]}–{entry.pre.score[1]}</div></div>
              </div>
              <div style={{ marginTop: "12px" }}><WDLBar ph={entry.pre.ph} pd={entry.pre.pd} pa={entry.pre.pa} lang={lang} /></div>
            </div>
          )}
          {stats ? (
            <div className="card md-block">
              <div className="eyebrow">{pt ? "Estatísticas do jogo" : "Match stats"} · {stats.source}</div>
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
            <div className="datanote"><span>ℹ️</span><span>{pt ? "Estatísticas detalhadas não disponíveis para este jogo (fonte gratuita só cobre alguns)." : "Detailed stats not available for this game."}</span></div>
          )}
        </React.Fragment>
      ) : (
        <div className="card card-accent md-block">
          <div className="eyebrow">{pt ? "Previsão do projeto" : "Project prediction"}</div>
          <div className="md-predrow">
            <div className="md-pred">{entry.pred.score[0]}<span>–</span>{entry.pred.score[1]}</div>
            <div className="md-xg"><div className="lb">{pt ? "gols esperados (xG)" : "expected goals (xG)"}</div><div className="v">{entry.pred.xg[0]} – {entry.pred.xg[1]}</div></div>
          </div>
          <WDLBar ph={entry.pred.ph} pd={entry.pred.pd} pa={entry.pred.pa} lang={lang} />
          <div className="md-note">{pt ? "Placar mais provável segundo o modelo (ensemble). Empate alto é comum — veja as probabilidades acima."
                                       : "Most likely scoreline per the (ensemble) model. Draws are common — see probabilities above."}</div>
        </div>
      )}
    </div>
  );
}

Object.assign(window, { CalendarView, MatchDetailView });
