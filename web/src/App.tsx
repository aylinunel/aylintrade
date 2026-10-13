import { useEffect, useMemo, useState } from "react";

import { MultiLineChart, Sparkline } from "./components/Charts";
import { date, number, pct, signed, title } from "./lib/format";
import type { AppData, MacroSeries, Stat } from "./types";

const colours = ["#2a78d6", "#7799a8", "#d59b4a", "#b66662"];
const chartNames = ["Aylin trend portfolio", "S&P 500 (SPY) buy & hold", "Equal-weight buy & hold", "Risk parity, always invested"];

function Badge({ children, tone = "neutral" }: { children: string; tone?: "good" | "warn" | "neutral" | "quiet" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>;
}

function statusTone(status: string): "good" | "warn" | "neutral" | "quiet" {
  if (status.includes("approved") || status === "baseline") return "good";
  if (status.includes("quarantine") || status.includes("unavailable") || status.includes("unverified")) return "warn";
  if (status.includes("shadow") || status.includes("context")) return "neutral";
  return "quiet";
}

function Ribbon({ asOf, status, children }: { asOf?: string; status: string; children: React.ReactNode }) {
  return <div className="evidence-ribbon"><Badge tone={statusTone(status)}>{title(status)}</Badge><span>As of {date(asOf)}</span><span>{children}</span></div>;
}

function App() {
  const [data, setData] = useState<AppData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [selected, setSelected] = useState<string[]>(["Aylin trend portfolio", "S&P 500 (SPY) buy & hold"]);
  const [objective, setObjective] = useState<"risk" | "return" | "drawdown">("risk");
  const [macroId, setMacroId] = useState<string>("");
  const [showSources, setShowSources] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data.json`)
      .then((response) => {
        if (!response.ok) throw new Error(`Dashboard data returned ${response.status}`);
        return response.json() as Promise<AppData>;
      })
      .then((payload) => {
        setData(payload);
        setMacroId(payload.macro.series[0]?.id ?? "");
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  const study = data?.study;
  const baseline = study?.stats["Aylin trend portfolio"];
  const selectedMacro = data?.macro.series.find((item) => item.id === macroId) ?? data?.macro.series[0];
  const orderedStats = useMemo(() => {
    if (!study) return [] as Array<[string, Stat]>;
    const field = objective === "risk" ? "sharpe" : objective === "return" ? "cagr" : "max_drawdown";
    return Object.entries(study.stats).sort(([, a], [, b]) => b[field] - a[field]);
  }, [study, objective]);

  const toggleSeries = (name: string) => setSelected((current) => (
    current.includes(name) ? current.filter((item) => item !== name) : [...current, name]
  ));

  if (error) return <main className="boot-state"><div><span className="eyebrow">AylinTrade</span><h1>Data contract unavailable.</h1><p>{error}</p><p>Run <code>aylintrade site</code> after the research build, then refresh.</p></div></main>;
  if (!data) return <main className="boot-state"><div className="loading-mark">A/T</div><p>Loading the evidence bundle…</p></main>;

  const visibleSeries = chartNames
    .filter((name) => selected.includes(name))
    .map((name, index) => ({ name, values: (study?.curves[name] as number[] | undefined) ?? [], color: colours[index] }));

  return (
    <main className="app-shell">
      <a className="skip-link" href="#main">Skip to research dashboard</a>
      <aside className="rail" aria-label="Research status">
        <div className="brand"><div className="mark" aria-hidden="true"><i /><b /></div><span>Aylin<span>Trade</span></span></div>
        <p className="rail-kicker">Evidence-led market research</p>
        <div className="posture">
          <span className="eyebrow">Current posture</span>
          <strong>{data.paper?.latest ? "Paper account active" : "Baseline study ready"}</strong>
          <p>{data.paper?.latest ? `Last paper record: ${date(data.paper.latest.date)}` : "No paper-account record has been generated in this static bundle."}</p>
        </div>
        <nav className="nav" aria-label="Sections">
          <a href="#overview">Overview</a><a href="#evidence">Evidence</a><a href="#macro">Macro</a><a href="#hourly">Hourly</a><a href="#research">Research</a>
        </nav>
        <div className="rail-foot">
          <Badge tone="warn">Paper-only</Badge>
          <p>No orders, brokerage links, leverage, short sales or personalised recommendations.</p>
        </div>
      </aside>

      <section className="workspace" id="main">
        <header className="topbar">
          <div><span className="eyebrow">Research run / {study?.as_of ?? "pending"}</span><p>Static evidence bundle · public inputs are treated conservatively</p></div>
          <button className="theme-toggle" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle colour theme">{theme === "dark" ? "Light canvas" : "Dark canvas"}</button>
        </header>

        <section id="overview" className="hero section-reveal">
          <div className="hero-copy">
            <span className="eyebrow">Daily baseline · long only</span>
            <h1>Read the evidence<br /><em>before the model.</em></h1>
            <p>The allocator is a paper-only, multi-asset daily trend/risk-parity baseline. Macro, hourly and agent layers are surfaced as governed research—not as hidden signals.</p>
            <Ribbon asOf={study?.as_of} status="baseline">{study?.settings ?? "Awaiting baseline settings"}</Ribbon>
          </div>
          <div className="metrics-strip" aria-label="Baseline summary metrics">
            <Metric label="Annualised return" value={pct(baseline?.cagr)} note="Historical simulation" />
            <Metric label="Volatility" value={pct(baseline?.volatility)} note="Annualised" />
            <Metric label="Worst drawdown" value={pct(baseline?.max_drawdown)} note="Peak to trough" />
            <Metric label="Sharpe ratio" value={number(baseline?.sharpe)} note="Risk-adjusted" />
          </div>
        </section>

        <section id="evidence" className="section block-section">
          <div className="section-heading"><div><span className="eyebrow">01 / Baseline evidence</span><h2>Four objective views.<br />One unhidden trade-off.</h2></div><p>Risk-adjusted return, raw return and drawdown remain separate lenses. The system does not automatically crown the strongest historical row.</p></div>
          <div className="series-controls" role="group" aria-label="Cumulative return chart series">
            {chartNames.map((name, index) => <button key={name} className={selected.includes(name) ? "series-active" : "series-off"} onClick={() => toggleSeries(name)} aria-pressed={selected.includes(name)}><i style={{ background: colours[index] }} />{name.replace(" (SPY) buy & hold", "")}</button>)}
          </div>
          {study && (study.curves.dates as string[]).length && visibleSeries.length ? <MultiLineChart dates={study.curves.dates as string[]} series={visibleSeries} /> : <div className="empty-state">Study curves are unavailable in this evidence bundle. Select a source-backed study to inspect normalized history.</div>}
          <div className="compare-table" role="region" aria-label="Objective comparison table" tabIndex={0}>
            <div className="table-head"><span>Experiment</span><span>Return</span><span>Vol</span><span>Sharpe</span><span>Drawdown</span><span>Turnover</span></div>
            {orderedStats.map(([name, stat]) => <div className="table-row" key={name}><strong>{name}</strong><span>{pct(stat.cagr)}</span><span>{pct(stat.volatility)}</span><span>{number(stat.sharpe)}</span><span className="negative">{pct(stat.max_drawdown)}</span><span>{pct(stat.turnover, 0)}</span></div>)}
          </div>
          <Ribbon asOf={study?.as_of} status={data.meta.data_vintage}>Historical outputs are author-reported simulations with disclosed fixed costs; they are not forecasts or independently reproduced results.</Ribbon>
        </section>

        <section id="macro" className="section macro-section">
          <div className="section-heading"><div><span className="eyebrow">02 / Macro context</span><h2>Release-aware by design.<br />Current data, not hindsight.</h2></div><p>Current official-series context is visible here. It is deliberately excluded from historical strategy tests until a vintage and release-time evidence bundle exists.</p></div>
          <div className="regime-line"><Badge tone={statusTone(data.macro.status)}>{title(data.macro.status)}</Badge>{data.macro.regimes.map((regime) => <span key={regime.name} title={regime.rule}>{title(regime.name)}: <strong>{title(regime.state)}</strong></span>)}</div>
          <div className="macro-layout">
            <div className="macro-selector" role="listbox" aria-label="Select a macro series">
              {data.macro.series.map((series) => <button key={series.id} className={selectedMacro?.id === series.id ? "macro-active" : ""} onClick={() => setMacroId(series.id)} role="option" aria-selected={selectedMacro?.id === series.id}><span>{series.family}</span><strong>{series.label}</strong><em>{number(series.latest, 2)}</em></button>)}
            </div>
            <MacroDetail series={selectedMacro} />
          </div>
          <div className="source-callout"><strong>Release calendar boundary</strong><span>BLS CPI and Employment releases publish scheduled date/time; the New York Fed calendar provides additional economic-release timing. A value enters a historical backtest only after its recorded availability time.</span><a href="https://www.newyorkfed.org/research/calendars/nationalecon_cal" target="_blank" rel="noreferrer">Open official calendar ↗</a></div>
          <Ribbon asOf={data.macro.generated_at} status={data.macro.status}>{data.macro.source?.vintage_policy ?? data.macro.limitations[0]}</Ribbon>
        </section>

        <section id="hourly" className="section hourly-section">
          <div className="section-heading"><div><span className="eyebrow">03 / Hourly research</span><h2>A separate clock.<br />No accidental blend.</h2></div><p>ETF sessions, continuous futures and 24/7 crypto do not share a synthetic hourly calendar. This layer is a shadow-only research overlay.</p></div>
          <div className="hourly-rule"><div><span>Trend horizons</span><strong>{data.intraday.feature_definition.trend_horizons_hours.map((value) => `${value}h`).join(" · ")}</strong></div><div><span>Realised volatility</span><strong>{data.intraday.feature_definition.volatility_windows_hours.map((value) => `${value}h`).join(" · ")}</strong></div><div><span>Execution convention</span><strong>{data.intraday.feature_definition.execution}</strong></div></div>
          <div className="hourly-ledger">
            {data.intraday.markets.map((market) => <article key={market.market}><div><Badge tone={statusTone(market.status)}>{title(market.status)}</Badge><h3>{market.market}</h3><span>{market.asset_class}</span></div><p>{market.reason}</p><small>{market.session_rule}</small></article>)}
          </div>
          <Ribbon status={data.intraday.status}>No hourly source has cleared rights, coverage, session and point-in-time gates. No record can change daily paper weights.</Ribbon>
        </section>

        <section id="research" className="section research-section">
          <div className="section-heading"><div><span className="eyebrow">04 / Research register</span><h2>Registered variants,<br />not an optimisation trophy.</h2></div><p>Experiments are classified before they are shown. Holdout and failure evidence belong beside performance numbers, not after them.</p></div>
          <div className="objective-tabs" role="group" aria-label="Sort objective comparison"><span>Rank comparator by</span>{(["risk", "return", "drawdown"] as const).map((item) => <button key={item} onClick={() => setObjective(item)} className={objective === item ? "selected" : ""} aria-pressed={objective === item}>{item === "risk" ? "Risk-adjusted return" : title(item)}</button>)}</div>
          <div className="experiment-list">{data.validation.experiments.map((experiment, index) => <div className="experiment" key={experiment.id}><span>0{index + 1}</span><div><strong>{title(experiment.id)}</strong><p>{experiment.description}</p></div><Badge tone={statusTone(experiment.state)}>{title(experiment.state)}</Badge></div>)}</div>
          <div className="method-grid">{Object.entries(data.validation.method).map(([key, value]) => <div key={key}><span>{title(key)}</span><p>{value}</p></div>)}</div>
          <section className="agent-note"><div><Badge tone="neutral">{title(data.settings.agent_mode)}</Badge><h3>Agents may explain; deterministic controls decide.</h3><p>Committee output is citation-led commentary and a hypothetical shadow ledger. Its raw-return impact is settled separately after a predeclared horizon and it has no effect on current paper weights.</p></div><div className="agent-stats"><Metric label="Settled shadow decisions" value={String(data.paper?.agents.settled ?? 0)} /><Metric label="Shadow cuts" value={String(data.paper?.agents.shadow_cuts ?? 0)} /><Metric label="Current paper influence" value="0%" note="By design" /></div></section>
          <AgentLedger review={data.paper?.latest?.review} />
          <button className="source-toggle" onClick={() => setShowSources(!showSources)} aria-expanded={showSources}>{showSources ? "Hide" : "Show"} source register <span>({data.provenance.records.length})</span></button>
          {showSources && <div className="source-register"><p>{data.provenance.policy}</p>{data.provenance.records.map((record) => <details key={record.id}><summary><span>{record.id}</span><Badge tone={statusTone(record.status)}>{title(record.status)}</Badge></summary><dl><dt>Purpose</dt><dd>{title(record.purpose)}</dd><dt>Provider</dt><dd>{record.provider}</dd><dt>Point-in-time status</dt><dd>{title(record.point_in_time_status)}</dd><dt>Rights status</dt><dd>{title(record.rights_status)}</dd><dt>Notes</dt><dd>{record.notes}</dd></dl></details>)}</div>}
        </section>

        <footer className="footer"><div className="brand footer-brand"><div className="mark" aria-hidden="true"><i /><b /></div><span>Aylin<span>Trade</span></span></div><p>Paper-only research. Historical outputs can be wrong, incomplete, revised or unavailable. Inspect the source, vintage and limitation before relying on any chart.</p><a href="https://alfred.stlouisfed.org/" target="_blank" rel="noreferrer">ALFRED vintage data ↗</a></footer>
      </section>
    </main>
  );
}

function MacroDetail({ series }: { series?: MacroSeries }) {
  if (!series) return <div className="macro-detail empty-state">No current macro series were available in the last build.</div>;
  return <div className="macro-detail"><div className="macro-detail-top"><div><span className="eyebrow">{series.family} / {series.id}</span><h3>{series.label}</h3><p>Observed {date(series.observation_date)} · {series.eligibility.replaceAll("_", " ")}</p></div><strong>{number(series.latest, 2)}<small>{series.units}</small></strong></div><Sparkline values={series.values.map((point) => point.value)} /><div className="macro-change"><span>Previous <strong>{number(series.previous, 2)}</strong></span><span>Change <strong className={(series.change ?? 0) >= 0 ? "positive" : "negative"}>{signed(series.change, 2)}</strong></span><span>History <strong>{series.values.length} observations</strong></span></div></div>;
}

function AgentLedger({ review }: { review?: NonNullable<NonNullable<AppData["paper"]>["latest"]>["review"] }) {
  if (!review) return <div className="agent-ledger empty-state">No commentary run is included in this evidence bundle. When present, reports, citations, model metadata and errors are shown here separately from paper weights.</div>;
  return <div className="agent-ledger"><div className="agent-ledger-head"><Badge tone={review.status?.startsWith("ok") ? "good" : "warn"}>{review.status ?? "unknown"}</Badge><span>{review.provider ?? "provider not recorded"} · {review.run_at ? date(review.run_at) : "run time not recorded"}</span></div>{review.summary && <p className="agent-summary">{review.summary}</p>}{review.errors?.length ? <p className="agent-error">{review.errors.join(" · ")}</p> : null}{review.sources?.length ? <div className="citation-list"><span>Citations</span>{review.sources.map((source) => <a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a>)}</div> : <p className="agent-muted">No validated external citations were retained for this run.</p>}<details><summary>Audit metadata and reports</summary><dl><dt>Models</dt><dd>{Object.values(review.models ?? {}).join(" · ") || "not recorded"}</dd><dt>Input hash</dt><dd>{review.input_hash ?? "not recorded"}</dd></dl>{Object.entries(review.reports ?? {}).map(([role, report]) => <div className="agent-report" key={role}><strong>{title(role)}</strong><p>{report}</p></div>)}</details></div>;
}

export default App;
