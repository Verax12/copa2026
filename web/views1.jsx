/* ===== views1.jsx — Overview + Etapas (light, FIFA brand) ===== */

/* Cores da paleta FIFA 2026 para o termômetro */
const THERMO_COLORS = [
  "#D41515","#E8571A","#E8A000","#7B35B0",
  "#009B8C","#A8D400","#D41515","#7B35B0",
  "#E8571A","#009B8C","#3D1466","#004D42"
];

/* ---------- VISÃO GERAL ---------- */
function Thermometer({ lang, onPick }) {
  const T = I18N[lang];
  const ranked = useMemo(() =>
    D.teams.map(t => ({ id: t.id, p: D.titleProb[t.id] }))
      .sort((a, b) => b.p - a.p).slice(0, 12), []);
  const max = ranked[0].p || 1;

  return (
    <div className="thermo card card-accent">
      <div className="thermo-hd">
        <span className="t">{T.thermoTitle}</span>
        <span className="pill">{T.thermoSub}</span>
      </div>
      {ranked.map((r, i) => (
        <div className="thermo-row" key={r.id} onClick={() => onPick(r.id)}>
          <span className={"rk" + (i < 3 ? " top" : "")}>{i + 1}</span>
          <Flag id={r.id} w={40} />
          <div className="thermo-stack">
            <span className="nm">{WC.name(r.id, lang)}</span>
            <span className="thermo-bar">
              <i style={{ width: (r.p / max * 100) + "%", background: THERMO_COLORS[i] }} />
            </span>
          </div>
          <span className="pc" style={{ color: THERMO_COLORS[i] }}>
            {r.p.toFixed(1)}<span style={{ fontSize: "11px", color: "var(--text-muted)" }}>%</span>
          </span>
        </div>
      ))}
    </div>
  );
}

function HeroView({ lang, onPick }) {
  const T = I18N[lang];
  const champId = D.baseBracket.champion;

  return (
    <div className="fade-in">
      {/* color strip */}
      <div style={{
        display: "flex", height: "6px", borderRadius: "3px", overflow: "hidden",
        margin: "18px 0 20px", gap: "2px"
      }}>
        {["#D41515","#E8571A","#E8A000","#7B35B0","#009B8C","#A8D400",
          "#D41515","#7B35B0","#E8571A","#009B8C"].map((c, i) => (
          <div key={i} style={{ flex: 1, background: c, borderRadius: "2px" }} />
        ))}
      </div>

      <div className="hero-grid">
        <div className="hero-main card card-accent">
          <div className="eyebrow" style={{ marginBottom: "10px" }}>{T.sub}</div>
          <h1 className="hero-title">{T.heroTitle}</h1>
          <p className="hero-sub">{T.heroSub}</p>
          <div className="champ-hero" onClick={() => onPick(champId)}>
            <span className="trophy">🏆</span>
            <Flag id={champId} w={64} />
            <div className="meta">
              <div className="l">{T.favLabel}</div>
              <div className="n">{WC.name(champId, lang)}</div>
            </div>
            <div className="pct">
              <div className="v">{D.titleProb[champId].toFixed(1)}%</div>
              <div className="c">{T.titleChance}</div>
            </div>
          </div>
        </div>

        <Thermometer lang={lang} onPick={onPick} />
      </div>
    </div>
  );
}

/* ---------- GRUPOS ---------- */
const Q_CLASS = ["q1", "q2", "q3", "out"];

function GroupCard({ group, lang, onPick }) {
  const T = I18N[lang];
  const Q_LABEL = [T.first, T.second, T.third, T.out];

  return (
    <div className="group card">
      <div className="group-hd">
        <span className="g">{lang === "pt" ? "Grupo " : "Group "}<em>{group.label}</em></span>
        <span className="lab">{lang === "pt" ? "Classificação prevista" : "Predicted standing"}</span>
      </div>
      {group.table.map((row, i) => (
        <div key={row.id} className={"grow " + Q_CLASS[i]} onClick={() => onPick(row.id)}>
          <span className="pos">{i + 1}</span>
          <Flag id={row.id} w={32} />
          <span className="nm">{WC.name(row.id, lang)}</span>
          <span className="qbadge">{Q_LABEL[i]}</span>
          <span className="adv">{row.adv}<span>%</span></span>
        </div>
      ))}
    </div>
  );
}

function GroupsView({ lang, onTeamPick }) {
  const T = I18N[lang];
  return (
    <div className="fade-in">
      <div className="section-head">
        <div>
          <div className="eyebrow">{T.stagesTitle}</div>
          <h2>{T.groups}</h2>
          <p>{T.groupsSub}</p>
        </div>
        <div className="legend-bar">
          <span><i style={{ background: "var(--red)" }}></i>{T.first}/{T.second}</span>
          <span><i style={{ background: "var(--teal)" }}></i>{T.third}</span>
          <span><i style={{ background: "#ccc" }}></i>{T.out}</span>
        </div>
      </div>
      <div className="groups-grid">
        {D.groups.map(g => (
          <GroupCard key={g.id} group={g} lang={lang} onPick={onTeamPick} />
        ))}
      </div>
    </div>
  );
}

/* ---------- BRACKET ---------- */
const ROUND_COL_CLASS = { R32: "r32", R16: "r16", QF: "qf", SF: "sf", F: "final" };
/* rótulos corretos para a Copa de 48 (32 no mata-mata) */
const ROUND_NAMES = {
  pt: { R32: "32-avos de final", R16: "Oitavas de final", QF: "Quartas de final", SF: "Semifinais", F: "Final" },
  en: { R32: "Round of 32", R16: "Round of 16", QF: "Quarter-finals", SF: "Semi-finals", F: "Final" }
};
const ROUND_ORDER = ["R32", "R16", "QF", "SF"];

function MatchCardLang({ match, lang, overrides, onToggle }) {
  const { a, b, score, winner } = match;
  const isEdited = overrides[match.id] != null;

  function teamRow(id, side) {
    const isWin = id === winner;
    return (
      <div
        className={"mteam" + (isWin ? " win" : " lose") + (isEdited && overrides[match.id] === id ? " edited" : "")}
        onClick={() => onToggle(match.id, id, side === "a" ? b : a, match)}
        title={lang === "pt" ? "Clique para fazer essa seleção vencer" : "Click to make this team win"}
      >
        <Flag id={id} w={32} />
        <span className="nm">{WC.name(id, lang)}</span>
        <span className="sc">{side === "a" ? score[0] : score[1]}</span>
      </div>
    );
  }

  return (
    <div className="match">
      {teamRow(a, "a")}
      {teamRow(b, "b")}
    </div>
  );
}

function BracketView({ lang }) {
  const T = I18N[lang];
  const [overrides, setOverrides] = useState({});
  const bracket = useMemo(() => D.buildBracket(overrides), [overrides]);
  const hasEdits = Object.keys(overrides).length > 0;

  function handleToggle(matchId, clickedId, otherId, match) {
    const current = overrides[matchId] != null ? overrides[matchId] : match.def;
    if (current === clickedId) {
      const next = { ...overrides }; delete next[matchId]; setOverrides(next);
    } else {
      setOverrides(o => ({ ...o, [matchId]: clickedId }));
    }
  }

  const champId = bracket.champion;

  return (
    <div className="fade-in">
      <div className="section-head">
        <div>
          <div className="eyebrow">{T.stagesTitle}</div>
          <h2>{T.knockout}</h2>
          <p>{T.bracketSub}</p>
        </div>
      </div>

      <div className="sim-bar card">
        <span className="ic">⚡</span>
        <div className="tx">
          <b>{T.simTitle}: </b>{T.simBody}
        </div>
        <div style={{ marginLeft: "auto" }}>
          <button className="btn" onClick={() => setOverrides({})} disabled={!hasEdits}>{T.reset}</button>
        </div>
      </div>

      {hasEdits && (
        <div className="datanote" style={{ marginBottom: "14px" }}>
          <span>✏️</span>
          <span>{lang === "pt" ? "Chaveamento personalizado ativo — edições destacadas em laranja." : "Custom bracket active — edits highlighted in orange."}</span>
        </div>
      )}

      <div className="bracket-scroll">
        <div className="bracket">
          {ROUND_ORDER.map(rk => (
            <div key={rk} className="bcol">
              <div className={"bcol-hd " + ROUND_COL_CLASS[rk]}>
                {ROUND_NAMES[lang][rk]}
              </div>
              {bracket.rounds[rk].map(m => (
                <MatchCardLang key={m.id} match={m} lang={lang} overrides={overrides} onToggle={handleToggle} />
              ))}
            </div>
          ))}

          <div className="bcol">
            <div className="bcol-hd final">{ROUND_NAMES[lang]["F"]}</div>
            {bracket.rounds["F"].map(m => (
              <MatchCardLang key={m.id} match={m} lang={lang} overrides={overrides} onToggle={handleToggle} />
            ))}
          </div>

          <div className="bcol" style={{ justifyContent: "center" }}>
            <div className="bcol-hd champ">{T.champion}</div>
            <div className="champ-card">
              <div className="tp">🏆</div>
              <Flag id={champId} w={80} />
              <div className="nm">{WC.name(champId, lang)}</div>
              <div className="lb">{D.titleProb[champId].toFixed(1)}% {T.titleChance}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------- ETAPAS WRAPPER ---------- */
function StagesView({ lang, onTeamPick }) {
  const T = I18N[lang];
  const [sub, setSub] = useState("groups");
  return (
    <div className="fade-in">
      <div className="sub-tabs">
        <button className={"btn" + (sub === "groups" ? " primary" : "")} onClick={() => setSub("groups")}>
          ⚽ {T.groups}
        </button>
        <button className={"btn" + (sub === "bracket" ? " primary" : "")} onClick={() => setSub("bracket")}>
          🗂 {T.knockout}
        </button>
      </div>
      {sub === "groups"  && <GroupsView lang={lang} onTeamPick={onTeamPick} />}
      {sub === "bracket" && <BracketView lang={lang} />}
    </div>
  );
}

Object.assign(window, { HeroView, StagesView });
