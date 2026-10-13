"use strict";
const $ = id => document.getElementById(id);
const agents = [
    ["data", "Data steward", "01", 70, 195, "Checks completed candles, gaps, candle geometry and source identity."],
    ["deviser", "Strategy deviser", "02", 213, 195, "Enumerates nine registered parameter templates. It does not invent executable code."],
    ["validation", "Validation", "03", 370, 195, "Checks causal signals, ranks validation windows, then measures one untouched test interval."],
    ["quant", "Quant reviewer", "04A", 535, 52, "Assesses measured held-out evidence, sample size and stressed costs."],
    ["market", "Market reviewer", "04B", 535, 146, "Assesses the current signal and observed volatility."],
    ["news", "Event reviewer", "04C", 535, 244, "Checks dated event context; abstains when the news archive is missing."],
    ["risk", "Risk reviewer", "04D", 535, 338, "Assesses proposed size and drawdown. It cannot override the numerical policy."],
    ["portfolio", "Portfolio gate", "05", 695, 195, "Requires three approvals including quant and risk, plus every hard check."],
    ["paper", "Paper ledger", "06", 857, 195, "Reconciles historical spot fills, costs and PnL. It sends no exchange orders."],
];
const links = [
    ["data", "deviser"],
    ["deviser", "validation"], ...agents.slice(3, 7).flatMap(a => [
        ["validation", a[0]],
        [a[0], "portfolio"]
    ]), ["portfolio", "paper"]
];
const state = {
    run: null,
    selected: "data",
    events: [],
    after: 0,
    nodes: {},
    result: null,
    token: null,
    polling: false
};

function element(tag, text, className) {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (className) e.className = className;
    return e;
}

function money(n) {
    return Number(n).toLocaleString(undefined, {
        maximumFractionDigits: 2
    });
}

function percent(n) {
    return Number.isFinite(n) ? `${(n*100).toFixed(2)}%` : "—";
}

function label(id) {
    return agents.find(a => a[0] === id)?.[1] || id;
}

function notice(text, error = false) {
    $("notice").textContent = text;
    $("notice").classList.toggle("error", error);
}

function buildGraph() {
    for (const [id, name, number, x, y] of agents) {
        const button = element("button", undefined, "agent");
        button.type = "button";
        button.id = `node-${id}`;
        button.style.left = `${x/920*100}%`;
        button.style.top = `${y/390*100}%`;
        button.append(element("b", number), element("span", name), element("span", "WAITING", "node-status"));
        button.setAttribute("aria-label", `${name}: waiting. Inspect agent`);
        button.onclick = () => {
            state.selected = id;
            inspect();
        };
        $("nodes").append(button);
    }
    for (const [from, to] of links) {
        const a = agents.find(x => x[0] === from),
            b = agents.find(x => x[0] === to);
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const x1 = a[3] + 63,
            x2 = b[3] - 63,
            y1 = a[4],
            y2 = b[4],
            mid = (x1 + x2) / 2;
        path.setAttribute("d", `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`);
        path.setAttribute("class", "edge");
        path.dataset.to = to;
        $("edges").append(path);
    }
    inspect();
    renderReviews([]);
}

function inspect() {
    const agent = agents.find(a => a[0] === state.selected),
        event = state.nodes[state.selected];
    $("agent-name").textContent = agent[1];
    $("agent-description").textContent = agent[5];
    $("agent-status").textContent = event?.status || "WAITING";
    $("agent-summary").textContent = event?.detail.message || event?.detail.reason || (event ? "Recorded evidence is available below." : "Select a run to inspect the saved evidence.");
    $("agent-detail").textContent = event ? JSON.stringify(event.detail, null, 2) : "No events yet.";
    for (const a of agents) $("node-" + a[0]).classList.toggle("selected", a[0] === state.selected);
}

function renderEvents() {
    for (const a of agents) {
        const ev = state.nodes[a[0]],
            status = ev?.status === "PROGRESS" ? "RUNNING" : ev?.status || "WAITING",
            node = $("node-" + a[0]);
        node.classList.remove("RUNNING", "COMPLETED", "FAILED");
        if (status !== "WAITING") node.classList.add(status);
        node.querySelector(".node-status").textContent = status;
        node.setAttribute("aria-label", `${a[1]}: ${status}. Inspect agent`);
    }
    for (const edge of $("edges").children) edge.classList.toggle("active", state.nodes[edge.dataset.to]?.status === "RUNNING");
    $("timeline").replaceChildren();
    for (const ev of state.events.slice(-60)) {
        const row = element("li");
        row.append(element("time", new Date(ev.time).toLocaleTimeString()), element("span", label(ev.agent)), element("span", ev.status, ev.status === "FAILED" ? "fail" : ev.status === "COMPLETED" ? "pass" : "muted"), element("span", ev.detail.message || ev.detail.reason || (ev.detail.trial ? `Trial ${ev.detail.trial.strategy} measured` : "Evidence saved"), "event-message"));
        $("timeline").prepend(row);
    }
    const manifest = state.nodes.data?.detail;
    if (manifest?.rows) {
        $("dataset").textContent = manifest.rows.toLocaleString() + " bars";
        $("dataset-sub").textContent = `${manifest.market} · ${manifest.interval} · ${manifest.synthetic?"synthetic":"market cache"}`;
    }
    $("trial-count").replaceChildren(document.createTextNode(String(state.events.filter(e => e.agent === "deviser" && e.status === "PROGRESS").length)), element("span", "/ 9"));
    const reviews = Object.values(state.nodes).filter(e => ["quant", "market", "news", "risk"].includes(e.agent) && e.detail.verdict).map(e => e.detail);
    renderReviews(reviews);
    inspect();
}

function renderReviews(reviews) {
    $("reviews").replaceChildren();
    for (const role of ["quant", "market", "news", "risk"]) {
        const review = reviews.find(r => r.role === role),
            card = element("article", undefined, "review-card");
        card.append(element("h3", label(role)), element("span", review?.verdict || "WAITING", "verdict " + (review?.verdict === "APPROVE" ? "pass" : review?.verdict === "REJECT" ? "fail" : "muted")), element("p", review?.reason || "Independent review will appear here."));
        if (review) {
            const details = element("details");
            details.append(element("summary", "Counterargument and sources"), element("p", review.counterargument || "No counterargument supplied"), element("small", `Evidence: ${(review.evidence||[]).join(" · ")} | Reviewer: ${review.provider}`));
            card.append(details);
        }
        $("reviews").append(card);
    }
    $("approval-count").replaceChildren(document.createTextNode(String(reviews.filter(r => r.verdict === "APPROVE").length)), element("span", "/ 4"));
}

function renderResult(result) {
    state.result = result;
    $("export").disabled = false;
    const p = result.proposal,
        m = result.evidence.metrics;
    $("decision").textContent = p.status;
    $("decision-sub").textContent = p.status === "ELIGIBLE" ? "Conditional proposal · reprice before any fill" : "No actionable suggestion";
    $("proposal-status").textContent = p.status;
    $("proposal-description").textContent = p.reasons.length ? "Blocked by: " + p.reasons.map(x => x.replaceAll("_", " ")).join(", ") + "." : "Three independent approvals and all hard checks passed. This remains an experimental paper proposal.";
    $("checks").replaceChildren();
    for (const [name, pass] of Object.entries(p.checks)) {
        const row = element("div", undefined, "check");
        row.append(element("span", name.replaceAll("_", " ")), element("span", pass ? "PASS" : "BLOCK", pass ? "pass" : "fail"));
        $("checks").append(row);
    }
    $("levels").replaceChildren();
    for (const [title, value] of [
            ["Entry reference", p.entry_reference],
            ["Stop reference", p.stop_reference],
            ["Illustrative 2R target", p.target_reference],
            ["Eligible notional", p.notional]
        ]) {
        const d = element("div", title);
        d.append(element("b", money(value)));
        $("levels").append(d);
    }
    $("proposal-note").textContent = p.target_note + ". Sizes are indicative; no exchange order is created. Expires " + new Date(p.expires_at).toLocaleString() + ".";
    $("trials").replaceChildren();
    for (const t of [...result.trials].sort((a, b) => b.score - a.score)) {
        const row = element("tr", undefined, t.id === result.evidence.selected.id ? "selected" : "");
        for (const v of [t.strategy, JSON.stringify(t.params), t.score.toFixed(3), String(t.validation_trades), t.selection_eligible === undefined ? "Legacy snapshot" : t.selection_eligible ? "Enough observations" : "Insufficient observations"]) row.append(element("td", v));
        $("trials").append(row);
    }
    $("trades").replaceChildren();
    for (const t of [...result.trades].reverse()) {
        const row = element("tr");
        for (const v of [t.entry.toFixed(2), t.exit.toFixed(2), t.pnl.toFixed(2), t.reason]) row.append(element("td", v));
        row.children[2].className = t.pnl >= 0 ? "pass" : "fail";
        $("trades").append(row);
    }
    if (!result.trades.length) {
        const row = element("tr");
        const cell = element("td", "No completed trades in this test window.", "empty");
        cell.colSpan = 4;
        row.append(cell);
        $("trades").append(row);
    }
    $("ledger-status").textContent = result.ledger.reconciled ? "RECONCILED" : "FAILED";
    $("equity-metrics").replaceChildren();
    for (const [name, value] of [
            ["Net return", percent(m.return)],
            ["Maximum drawdown", percent(m.drawdown)],
            ["Trading fees", money(m.fees) + " USDT"]
        ]) {
        const e = element("span", name);
        e.append(element("b", value));
        $("equity-metrics").append(e);
    }
    renderReviews(result.reviews);
    drawEquity();
    notice(result.manifest.synthetic ? "Synthetic demo complete · these are measured outcomes on generated prices, not evidence of market profitability." : `Market-cache research complete · last completed candle ${result.manifest.end} UTC · ${result.manifest.fresh?"within freshness limit":"STALE; suggestions blocked"}.`);
}

function drawEquity() {
    const canvas = $("equity"),
        ratio = window.devicePixelRatio || 1,
        width = canvas.clientWidth,
        height = 220;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    const c = canvas.getContext("2d");
    c.scale(ratio, ratio);
    c.clearRect(0, 0, width, height);
    const values = state.result?.equity.map(x => x.value) || [];
    c.font = "10px system-ui";
    c.strokeStyle = "#273340";
    c.fillStyle = "#74879c";
    if (!values.length) {
        c.fillText("Run a study to see actual paper equity.", 22, 110);
        return;
    }
    let min = Math.min(...values),
        max = Math.max(...values);
    if (max === min) {
        min -= 1;
        max += 1;
    }
    const left = 62,
        right = width - 15,
        top = 16,
        bottom = 195;
    for (let i = 0; i < 4; i++) {
        const y = top + (bottom - top) * i / 3;
        c.beginPath();
        c.moveTo(left, y);
        c.lineTo(right, y);
        c.stroke();
        c.fillText(money(max - (max - min) * i / 3), 3, y + 3);
    }
    c.strokeStyle = "#c0e89b";
    c.lineWidth = 2;
    c.beginPath();
    values.forEach((v, i) => {
        const x = left + (right - left) * i / Math.max(1, values.length - 1),
            y = bottom - (v - min) / (max - min) * (bottom - top);
        i ? c.lineTo(x, y) : c.moveTo(x, y);
    });
    c.stroke();
    const pts = state.result.equity;
    c.fillText(pts[0].time.slice(0, 10), left, 215);
    c.fillText(pts.at(-1).time.slice(0, 10), Math.max(left, right - 68), 215);
}
async function api(path, options) {
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) throw Error(data.error || "Request failed");
    return data;
}
async function history() {
    const runs = await api("/api/runs");
    const placeholder = element("option", "Saved runs");
    placeholder.value = "";
    $("history").replaceChildren(placeholder);
    for (const r of runs) {
        const o = element("option", `${r.status} · ${new Date(r.created).toLocaleTimeString()}`);
        o.value = r.id;
        $("history").append(o);
    }
    if (state.run) $("history").value = state.run;
    return runs;
}

function reset(run) {
    state.run = run;
    state.events = [];
    state.nodes = {};
    state.after = 0;
    state.result = null;
    $("export").disabled = true;
    $("dataset").textContent = "—";
    $("dataset-sub").textContent = "Waiting for data";
    $("decision").textContent = "RUNNING";
    $("decision-sub").textContent = "Evaluating evidence";
    $("proposal-status").textContent = "WAITING FOR EVIDENCE";
    $("proposal-description").textContent = "Reviews cannot override mandatory checks.";
    $("proposal-note").textContent = "Waiting for measured results.";
    $("equity-metrics").replaceChildren(element("span", "Waiting for paper results"));
    $("ledger-status").textContent = "NOT RUN";
    $("checks").replaceChildren();
    $("levels").replaceChildren();
    $("trials").replaceChildren();
    $("trades").replaceChildren();
    renderEvents();
    drawEquity();
}
async function poll() {
    if (state.polling) return;
    state.polling = true;
    const id = state.run;
    try {
        if (!id) return;
        const events = await api(`/api/runs/${id}/events?after=${state.after}`);
        if (id !== state.run) return;
        for (const e of events) {
            state.events.push(e);
            state.after = e.seq;
            state.nodes[e.agent] = e;
        }
        renderEvents();
        const run = await api(`/api/runs/${id}`);
        if (id !== state.run) return;
        $("run-status").textContent = `${run.status} · ${id.slice(0,8)}`;
        $("run").disabled = run.status === "RUNNING";
        if (run.result) {
            renderResult(run.result);
            $("elapsed").textContent = `${run.result.elapsed_seconds.toFixed(2)}s TOTAL`;
        }
        if (run.status === "FAILED") {
            notice(run.error || "Research failed", true);
            $("decision").textContent = "FAILED";
            $("proposal-status").textContent = "NO TRADE";
        }
        if (run.status === "RUNNING" || events.length === 500) setTimeout(poll, 700);
        else await history();
    } catch (e) {
        notice(e.message, true);
        $("run").disabled = false;
    } finally {
        state.polling = false;
        if (id !== state.run) setTimeout(poll, 0);
    }
}
$("settings").onsubmit = async event => {
    event.preventDefault();
    $("run").disabled = true;
    const values = Object.fromEntries(new FormData(event.target));
    for (const k of ["capital", "risk_fraction"]) values[k] = Number(values[k]);
    try {
        const result = await api("/api/runs", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Studio-Token": state.token
            },
            body: JSON.stringify(values)
        });
        reset(result.id);
        notice("Research running · numerical evidence comes before independent reviews.");
        await poll();
    } catch (e) {
        notice(e.message, true);
        $("run").disabled = false;
    }
};
$("history").onchange = () => {
    if ($("history").value) {
        reset($("history").value);
        poll();
    }
};
$("depth").onclick = () => {
    const on = $("depth").getAttribute("aria-pressed") !== "true";
    $("depth").setAttribute("aria-pressed", String(on));
    document.querySelector(".graph-viewport").classList.toggle("depth", on);
};
$("export").onclick = () => {
    if (!state.result) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(state.result, null, 2)], {
        type: "application/json"
    }));
    const a = element("a");
    a.href = url;
    a.download = `quant-evidence-${state.run.slice(0,8)}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
};
window.addEventListener("resize", drawEquity);
buildGraph();
drawEquity();
(async () => {
    try {
        const session = await api("/api/session");
        state.token = session.token;
        $("provider").textContent = session.reviewer === "rules" ? "RULE REVIEWERS" : "LLM REVIEWERS";
        const runs = await history();
        if (runs.length) {
            reset(runs[0].id);
            await poll();
        }
    } catch (e) {
        notice("Could not reach the local server: " + e.message, true);
    }
})();
