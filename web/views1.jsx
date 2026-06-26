/* ===== views1.jsx — Overview + Etapas (light, FIFA brand) ===== */

/* Cores da paleta FIFA 2026 para o termômetro */
const THERMO_COLORS = [
  "#D41515","#E8571A","#E8A000","#7B35B0",
  "#009B8C","#A8D400","#D41515","#7B35B0",
  "#E8571A","#009B8C","#3D1466","#004D42"
];

/* ---------- VISÃO GERAL ---------- */

/* Pódio do topo: campeã prevista em destaque + vice e 3º */
function ChampionHero({ lang, onPick }) {
  const T = I18N[lang];
  const ranked = useMemo(() =>
    D.teams.map(t => ({ id: t.id, p: D.titleProb[t.id] }))
      .sort((a, b) => b.p - a.p).slice(0, 3), []);
  const champId = D.baseBracket.champion;
  const champP = D.titleProb[champId];

  return (
    <div className="champ-banner card card-accent">
      <div className="cb-strip">
        {["#D41515","#E8571A","#E8A000","#7B35B0","#009B8C","#A8D400","#D41515","#7B35B0","#E8571A","#009B8C"].map((c, i) => (
          <div key={i} style={{ flex: 1, background: c }} />
        ))}
      </div>
      <div className="cb-inner">
        <div className="cb-eyebrow">{T.sub}</div>
        <h1 className="cb-title">{T.heroTitle}</h1>
        <p className="cb-sub">{T.heroSub}</p>

        <div className="cb-champ" {...clickable(() => onPick(champId), WC.name(champId, lang))} title={lang === "pt" ? "Ver caminho da seleção" : "See team path"}>
          <span className="cb-trophy">🏆</span>
          <Flag id={champId} w={84} />
          <div className="cb-meta">
            <span className="l">{T.favLabel}</span>
            <span className="n">{WC.name(champId, lang)}</span>
          </div>
          <div className="cb-pct">
            <span className="v">{champP.toFixed(1)}%</span>
            <span className="c">{T.titleChance}</span>
          </div>
        </div>

        {/* vice + terceiro logo abaixo do campeão */}
        <div className="cb-runners">
          {ranked.slice(1).map((r, i) => (
            <div key={r.id} className="cb-runner" {...clickable(() => onPick(r.id), WC.name(r.id, lang))}>
              <span className="medal">{i === 0 ? "🥈" : "🥉"}</span>
              <Flag id={r.id} w={40} />
              <span className="nm">{WC.name(r.id, lang)}</span>
              <span className="pc">{r.p.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* Termômetro — agora abaixo do campeão, em largura total */
function Thermometer({ lang, onPick }) {
  const T = I18N[lang];
  const ranked = useMemo(() =>
    D.teams.map(t => ({ id: t.id, p: D.titleProb[t.id] }))
      .sort((a, b) => b.p - a.p).slice(0, 12), []);
  const max = ranked[0].p || 1;

  return (
    <div className="thermo card card-accent-black">
      <div className="thermo-hd">
        <span className="t">{T.thermoTitle}</span>
        <span className="pill">{T.thermoSub}</span>
      </div>
      <div className="thermo-grid">
        {ranked.map((r, i) => (
          <div className="thermo-row" key={r.id} {...clickable(() => onPick(r.id), WC.name(r.id, lang))}>
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
    </div>
  );
}

/* ---------- DESEMPENHO DO MODELO (backtest pré-Copa) ---------- */
function TrackRecord({ lang, openPair }) {
  const tr = D.trackRecord;
  const [open, setOpen] = useState(false);
  const [showWhy, setShowWhy] = useState(false);   // camada "por que confiar / onde erra"
  const [tab, setTab] = useState("all");   // all | hit | miss
  if (!tr || !tr.summary || !tr.summary.n) return null;
  const s = tr.summary;
  const pt = lang === "pt";
  // "acerto de resultado" = V/E/D pelo resultado MAIS PROVÁVEL (argmax das
  // probabilidades) — métrica honesta da força do modelo. É SEPARADO de "cravou
  // o placar" (placar exato), exibido como selo 🎯 à parte na linha do jogo e no
  // modal; os dois podem divergir (ex.: favorito não venceu, mas o placar-moda
  // bateu por coincidência).
  const resultCorrect = s.probCorrect ?? s.winnerCorrect;
  const resultAcc = s.probAcc ?? s.winnerAcc;
  const idByEn = (en) => { const t = D.teams.find(x => x.en === en); return t ? t.id : null; };
  const nm = (en) => { const t = D.teams.find(x => x.en === en); return t ? WC.name(t.id, lang) : en; };

  // taxa de acerto vs baselines, em barra comparativa
  const accPct = Math.round(resultAcc * 100);
  const eloPct = Math.round((s.baselineEloAcc || 0) * 100);
  const games = [...tr.games].sort((a, b) => (b.date || "").localeCompare(a.date || ""))
    .filter(g => {
      const ok = (g.probHit ?? g.winnerHit);
      return tab === "all" ? true : tab === "hit" ? ok : !ok;
    });

  // ----- explicabilidade ("por que confiar / onde erra") -----
  const conf = (g) => Math.max(g.ph, g.pd, g.pa);          // confiança = prob. do resultado mais provável
  const okOf = (g) => (g.probHit ?? g.winnerHit);
  const byConf = [...tr.games].sort((a, b) => conf(b) - conf(a));
  const confHits = byConf.filter(okOf).slice(0, 3);
  const confMiss = byConf.filter(g => !okOf(g)).slice(0, 3);
  const calBins = [[0, 0.4], [0.4, 0.55], [0.55, 0.7], [0.7, 1.0001]].map(([lo, hi]) => {
    const gs = tr.games.filter(g => { const c = conf(g); return c >= lo && c < hi; });
    const n = gs.length;
    return { lo, hi, n, hit: n ? gs.filter(okOf).length / n : 0, avg: n ? gs.reduce((x, g) => x + conf(g), 0) / n : 0 };
  });
  // barras comparativas (largura = "melhor = mais longa", para acerto e Brier)
  function cmpRows(rows, lowerBetter) {
    const vals = rows.map(r => r.v);
    const max = Math.max(...vals), min = Math.min(...vals);
    const bestV = lowerBetter ? min : max;
    return rows.map(r => {
      const w = max === min ? 100 : (lowerBetter ? (max - r.v) / (max - min) : (r.v - min) / (max - min)) * 78 + 22;
      return { ...r, w, best: r.v === bestV };
    });
  }
  const accRows = cmpRows([
    { k: pt ? "Modelo" : "Model", v: accPct, color: "var(--teal)" },
    { k: "Elo", v: eloPct, color: "var(--purple)" },
    { k: pt ? "Aleatório" : "Random", v: 33, color: "#bbb" },
  ], false);
  const brierRows = cmpRows([
    { k: pt ? "Modelo" : "Model", v: s.brier, color: "var(--teal)" },
    { k: "Elo", v: s.brierElo ?? s.brierUniform, color: "var(--purple)" },
    { k: pt ? "Chute" : "Guess", v: s.brierUniform, color: "#bbb" },
  ], true);
  function gameLine(g) {
    const hId = idByEn(g.home), aId = idByEn(g.away);
    const canOpen = hId != null && aId != null && D.calendarEntry(hId, aId);
    const props = canOpen ? clickable(() => openPair(hId, aId)) : {};
    return (
      <div key={g.home + g.away + g.date} className={"why-game" + (canOpen ? " clickable" : "")} {...props}>
        {hId != null && <Flag id={hId} w={18} />}
        <span className="wg-nm">{nm(g.home)} <b>{g.actual[0]}–{g.actual[1]}</b> {nm(g.away)}</span>
        <span className="wg-conf">{Math.round(conf(g) * 100)}%</span>
      </div>
    );
  }

  return (
    <div className="card card-accent-teal model-perf">
      <div className="mp-head">
        <div>
          <div className="eyebrow" style={{ color: "var(--teal)" }}>{pt ? "Desempenho do modelo" : "Model performance"}</div>
          <h2 className="mp-title">{pt ? "Como o modelo foi nos jogos já disputados" : "How the model did on played games"}</h2>
          <p className="mp-sub">{pt
            ? `Backtest honesto (sem vazamento): treinado só com dados de ANTES da Copa e testado nos ${s.n} jogos já realizados. Placar exato é loteria — o que importa é acertar o resultado e a calibração das probabilidades.`
            : `Honest backtest (leakage-free): trained only on pre-cup data and tested on the ${s.n} games played so far. Exact scores are luck — what matters is the result and probability calibration.`}</p>
        </div>
        <div className="mp-accuracy">
          <div className="mp-acc-big">{accPct}<small>%</small></div>
          <div className="mp-acc-lbl">{pt ? "acerto de resultado" : "result accuracy"}</div>
          <div className="mp-acc-base">{pt ? "Elo de referência" : "Elo baseline"}: {eloPct}%</div>
        </div>
      </div>

      <div className="mp-stats">
        <div className="mp-stat">
          <div className="l">{pt ? "Acertos V/E/D" : "W/D/L correct"}</div>
          <div className="v">{resultCorrect}<small>/{s.n}</small></div>
          <div className="bar"><i style={{ width: (resultCorrect / s.n * 100) + "%", background: "var(--teal)" }} /></div>
        </div>
        <div className="mp-stat">
          <div className="l">{pt ? "Placares exatos" : "Exact scores"}</div>
          <div className="v">{s.exactCorrect ?? "—"}<small>/{s.n}</small></div>
          <div className="bar"><i style={{ width: ((s.exactCorrect || 0) / s.n * 100) + "%", background: "var(--purple)" }} /></div>
        </div>
        <div className="mp-stat" title={pt ? "Quanto menor, melhor (chute aleatório seria " + s.brierUniform + ")" : "Lower is better"}>
          <div className="l">Brier <small className="muted">↓ {pt ? "chute" : "guess"} {s.brierUniform}</small></div>
          <div className="v">{s.brier.toFixed(2)}</div>
          <div className="bar"><i style={{ width: Math.max(4, (1 - s.brier / (s.brierUniform || 1)) * 100) + "%", background: "var(--red)" }} /></div>
        </div>
        <div className="mp-stat" title="Log-loss — ↓ melhor">
          <div className="l">Log-loss <small className="muted">↓</small></div>
          <div className="v">{s.logloss.toFixed(2)}</div>
          <div className="bar"><i style={{ width: Math.max(4, (1 - s.logloss / 1.6) * 100) + "%", background: "var(--lime)" }} /></div>
        </div>
      </div>

      <div className="mp-toolbar">
        <button className={"btn" + (showWhy ? " primary" : "")} onClick={() => setShowWhy(o => !o)}>
          {showWhy ? (pt ? "Ocultar análise" : "Hide analysis") : (pt ? "🔍 Por que confiar?" : "🔍 Why trust it?")}
        </button>
        <button className={"btn" + (open ? " primary" : "")} onClick={() => setOpen(o => !o)}>
          {open ? (pt ? "Ocultar jogo a jogo" : "Hide game by game") : (pt ? "Ver jogo a jogo" : "Show game by game")}
        </button>
        {open && (
          <div className="mp-filter">
            <button className={"chip" + (tab === "all" ? " on" : "")} onClick={() => setTab("all")}>{pt ? "Todos" : "All"}</button>
            <button className={"chip" + (tab === "hit" ? " on" : "")} onClick={() => setTab("hit")}>✅ {pt ? "Acertos" : "Hits"}</button>
            <button className={"chip" + (tab === "miss" ? " on" : "")} onClick={() => setTab("miss")}>❌ {pt ? "Erros" : "Misses"}</button>
          </div>
        )}
      </div>

      {showWhy && (
        <div className="mp-why">
          <div className="mp-why-grid">
            {/* A. comparativo Modelo × Elo × Aleatório */}
            <div className="mp-why-block">
              <div className="mp-why-h">{pt ? "Acerto do resultado" : "Result accuracy"} <small>↑ {pt ? "melhor" : "better"}</small></div>
              {accRows.map((r, i) => (
                <div key={i} className={"cmp-row" + (r.best ? " best" : "")}>
                  <span className="cmp-k">{r.k}</span>
                  <span className="cmp-bar"><i style={{ width: r.w + "%", background: r.color }} /></span>
                  <span className="cmp-v">{r.v}%</span>
                </div>
              ))}
            </div>
            <div className="mp-why-block">
              <div className="mp-why-h">Brier <small>↓ {pt ? "melhor" : "better"}</small></div>
              {brierRows.map((r, i) => (
                <div key={i} className={"cmp-row" + (r.best ? " best" : "")}>
                  <span className="cmp-k">{r.k}</span>
                  <span className="cmp-bar"><i style={{ width: r.w + "%", background: r.color }} /></span>
                  <span className="cmp-v">{r.v.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* C. calibração por faixa de confiança */}
          <div className="mp-why-block">
            <div className="mp-why-h">{pt ? "Calibração por confiança" : "Calibration by confidence"}
              <small>{pt ? "barra = acerto real; ◆ = confiança média" : "bar = real accuracy; ◆ = avg confidence"}</small></div>
            {calBins.map((b, i) => (
              <div key={i} className="cal-row" style={{ opacity: b.n ? 1 : 0.4 }}>
                <span className="cal-rng">{Math.round(b.lo * 100)}–{Math.round((b.hi > 1 ? 1 : b.hi) * 100)}%</span>
                <span className="cal-track">
                  <i style={{ width: (b.hit * 100) + "%" }} />
                  {b.n > 0 && <em className="cal-diamond" style={{ left: (b.avg * 100) + "%" }} title={pt ? "confiança média" : "avg confidence"}>◆</em>}
                </span>
                <span className="cal-n">{b.n ? Math.round(b.hit * 100) + "% · " + b.n + (pt ? " jogos" : " games") : "—"}</span>
              </div>
            ))}
          </div>

          {/* B. jogos de maior confiança */}
          <div className="mp-why-grid">
            <div className="mp-why-block">
              <div className="mp-why-h">✅ {pt ? "Mais confiante e acertou" : "Most confident & right"}</div>
              {confHits.length ? confHits.map(gameLine) : <div className="why-empty">—</div>}
            </div>
            <div className="mp-why-block">
              <div className="mp-why-h">❌ {pt ? "Mais confiante e errou" : "Most confident & wrong"}</div>
              {confMiss.length ? confMiss.map(gameLine) : <div className="why-empty">—</div>}
            </div>
          </div>

          {/* D. texto explicativo */}
          <div className="mp-why-note">
            {pt
              ? "Placar exato é ruído — o foco é acertar o resultado (V/E/D) e a calibração. O Brier mede a qualidade das probabilidades (quanto menor, melhor; o chute uniforme é a referência). Na calibração, o ideal é a barra de acerto real ficar perto do losango de confiança média."
              : "Exact scores are noise — the focus is the result (W/D/L) and calibration. Brier measures probability quality (lower is better; uniform guess is the reference). In calibration, the real-accuracy bar should sit close to the average-confidence diamond."}
          </div>
        </div>
      )}

      {open && (
        <div className="mp-games">
          {games.map((g, i) => {
            const ok = (g.probHit ?? g.winnerHit);
            const hId = idByEn(g.home), aId = idByEn(g.away);
            const canOpen = hId != null && aId != null && D.calendarEntry(hId, aId);
            const f = (g.date || "").split("-");
            const dateLbl = f.length === 3 ? `${f[2]}/${f[1]}` : g.date;
            return (
              <button key={i} className={"mp-game" + (ok ? " hit" : " miss") + (canOpen ? " clickable" : "")}
                      onClick={() => canOpen && openPair(hId, aId)}
                      title={canOpen ? (pt ? "Ver detalhes do jogo" : "See match details") : ""}>
                <span className="mpg-mark">{ok ? "✅" : "❌"}</span>
                <span className="mpg-date">{dateLbl}</span>
                <span className="mpg-match">
                  {hId != null && <Flag id={hId} w={20} />}
                  <b>{nm(g.home)}</b>
                  <span className="mpg-sc">{g.actual[0]}–{g.actual[1]}</span>
                  <b>{nm(g.away)}</b>
                  {aId != null && <Flag id={aId} w={20} />}
                </span>
                <span className="mpg-pred">{pt ? "prev" : "pred"} {g.predScore[0]}-{g.predScore[1]}
                  {g.exactHit && <em className="mpg-exact" title={pt ? "cravou o placar exato" : "exact score nailed"}>🎯</em>}
                </span>
                <span className="mpg-probs">
                  <em style={{ color: "var(--red)" }}>{Math.round(g.ph * 100)}</em>
                  <em>{Math.round(g.pd * 100)}</em>
                  <em style={{ color: "var(--purple)" }}>{Math.round(g.pa * 100)}</em>
                </span>
                {canOpen && <span className="mpg-chev">›</span>}
              </button>
            );
          })}
          <div className="mp-legend">{pt ? "Probabilidades pré-jogo: vitória mandante / empate / vitória visitante. Clique para ver os detalhes." : "Pre-match probabilities: home win / draw / away win. Click for details."}</div>
        </div>
      )}
    </div>
  );
}

function HeroView({ lang, onPick, openPair }) {
  return (
    <div className="fade-in">
      <ChampionHero lang={lang} onPick={onPick} />
      <Thermometer lang={lang} onPick={onPick} />
      <TrackRecord lang={lang} openPair={openPair} />
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
        <div key={row.id} className={"grow " + Q_CLASS[i]} {...clickable(() => onPick(row.id), WC.name(row.id, lang))}>
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

/* ---------- BRACKET (mata-mata) ---------- */
const ROUND_NAMES = {
  pt: { R32: "32-avos", R16: "Oitavas", QF: "Quartas", SF: "Semifinais", F: "Final" },
  en: { R32: "Round of 32", R16: "Round of 16", QF: "Quarter-finals", SF: "Semi-finals", F: "Final" }
};
const ROUND_ORDER = ["R32", "R16", "QF", "SF", "F"];

/* uma partida do bracket */
function BracketMatch({ match, lang, overrides, onToggle, openPair }) {
  const { a, b, score, winner } = match;
  const isEdited = overrides[match.id] != null;

  function row(id, side) {
    const isWin = id === winner;
    const sc = side === "a" ? score[0] : score[1];
    return (
      <div className={"bm-team" + (isWin ? " win" : " lose") + (isEdited && overrides[match.id] === id ? " edited" : "")}
           {...clickable(() => onToggle(match.id, id, side === "a" ? b : a, match), WC.name(id, lang))}
           title={lang === "pt" ? "Clique para fazer esta seleção vencer" : "Click to make this team win"}>
        <Flag id={id} w={26} />
        <span className="nm">{WC.name(id, lang)}</span>
        <span className="sc">{sc}</span>
      </div>
    );
  }

  return (
    <div className={"bm" + (isEdited ? " edited" : "")}>
      {row(a, "a")}
      <div className="bm-div" />
      {row(b, "b")}
    </div>
  );
}

function BracketView({ lang, openPair }) {
  const T = I18N[lang];
  const [overrides, setOverrides] = useState({});
  const bracket = useMemo(() => D.buildBracket(overrides), [overrides]);
  const hasEdits = Object.keys(overrides).length > 0;
  const pt = lang === "pt";

  function handleToggle(matchId, clickedId, otherId, match) {
    const current = overrides[matchId] != null ? overrides[matchId] : match.def;
    if (current === clickedId) {
      const next = { ...overrides }; delete next[matchId]; setOverrides(next);
    } else {
      setOverrides(o => ({ ...o, [matchId]: clickedId }));
    }
  }

  const champId = bracket.champion;
  const finalMatch = bracket.rounds["F"][0];
  const runnerUp = finalMatch.winner === finalMatch.a ? finalMatch.b : finalMatch.a;

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
        <div className="tx"><b>{T.simTitle}: </b>{T.simBody}</div>
        <button className="btn" onClick={() => setOverrides({})} disabled={!hasEdits} style={{ marginLeft: "auto" }}>{T.reset}</button>
      </div>

      {hasEdits && (
        <div className="datanote sim-active">
          <span>✏️</span>
          <span>{pt ? "Chaveamento personalizado ativo — suas edições estão destacadas em laranja." : "Custom bracket active — your edits are highlighted in orange."}</span>
        </div>
      )}

      {/* campeão previsto em destaque no topo */}
      <div className="ko-champion card">
        <div className="koc-final">
          <div className="koc-side">
            <span className="koc-lbl">{pt ? "Finalista" : "Finalist"}</span>
            <Flag id={finalMatch.a} w={34} /><span className="koc-nm">{WC.name(finalMatch.a, lang)}</span>
          </div>
          <span className="koc-score">{finalMatch.score[0]} – {finalMatch.score[1]}</span>
          <div className="koc-side r">
            <span className="koc-lbl">{pt ? "Finalista" : "Finalist"}</span>
            <Flag id={finalMatch.b} w={34} /><span className="koc-nm">{WC.name(finalMatch.b, lang)}</span>
          </div>
        </div>
        <div className="koc-winner">
          <span className="tp">🏆</span>
          <Flag id={champId} w={54} />
          <div className="koc-wmeta">
            <span className="l">{T.champion}</span>
            <span className="n">{WC.name(champId, lang)}</span>
          </div>
          <span className="koc-pct">{D.titleProb[champId].toFixed(1)}%</span>
        </div>
      </div>

      <div className="bracket-scroll">
        <div className="bracket2">
          {ROUND_ORDER.map(rk => (
            <div key={rk} className={"bcol2 col-" + rk.toLowerCase()}>
              <div className="bcol2-hd">{ROUND_NAMES[lang][rk]}<span>{bracket.rounds[rk].length} {pt ? "jogos" : "ties"}</span></div>
              <div className="bcol2-body">
                {bracket.rounds[rk].map(m => (
                  <BracketMatch key={m.id} match={m} lang={lang} overrides={overrides} onToggle={handleToggle} openPair={openPair} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ---------- ETAPAS WRAPPER ---------- */
function StagesView({ lang, onTeamPick, openPair }) {
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
      {sub === "bracket" && <BracketView lang={lang} openPair={openPair} />}
    </div>
  );
}

Object.assign(window, { HeroView, StagesView });
