"use strict";
(() => {
  const data = JSON.parse(document.getElementById("trace-data").textContent);
  const byId = id => document.getElementById(id);
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const statusClass = value => ({SUPPORTED:"supported",CONTRADICTED:"contradicted",MIXED:"mixed"}[value] || "unknown");
  const number = value => value == null ? "Unknown" : Number(value).toLocaleString(undefined, {maximumFractionDigits:9});
  const cap = value => value == null ? "Uncapped" : number(value);
  let selected = 0;
  let step = 0;
  byId("title").textContent = data.title;

  function renderList() {
    const query = byId("filter").value.toLowerCase();
    const list = byId("case-list");
    list.replaceChildren();
    let count = 0;
    data.cases.forEach((item, index) => {
      if (!(item.run + " " + item.id + " " + item.question).toLowerCase().includes(query)) return;
      count++;
      const button = element("button");
      button.type = "button";
      button.setAttribute("aria-current", String(index === selected));
      button.append(element("small", item.run), element("strong", item.question));
      button.addEventListener("click", () => select(index));
      list.append(button);
    });
    byId("case-count").textContent = `${count} of ${data.cases.length} saved cases`;
    if (!count) list.append(element("p", "No matching saved cases.", "empty"));
  }

  function drawGraph(view) {
    const container = byId("graph");
    container.replaceChildren();
    const graph = view.graph;
    if (!graph) {
      container.append(element("p", "No premise graph recorded at this step.", "empty"));
      return;
    }
    const nodes = new Map(graph.nodes.map(node => [node.id, node]));
    const claims = new Map(graph.claims.map(claim => [claim.id, claim.text]));
    const beliefs = new Map(view.beliefs.map(b => [b.claim_id, b.status]));
    const levels = new Map([[graph.conclusion_id, 0]]);
    let queue = [graph.conclusion_id];
    let rounds = 0;
    while (queue.length && rounds++ <= graph.nodes.length) {
      const next = [];
      for (const id of queue) for (const child of (nodes.get(id)?.children || [])) {
        const depth = levels.get(id) + 1;
        if (!levels.has(child) || depth > levels.get(child)) { levels.set(child, depth); next.push(child); }
      }
      queue = next;
    }
    const layers = [];
    for (const node of graph.nodes) {
      const depth = levels.get(node.id) || 0;
      (layers[depth] ||= []).push(node);
    }
    const width = Math.max(380, ...layers.filter(Boolean).map(layer => layer.length * 205));
    const height = layers.length * 102 + 20;
    const ns = "http://www.w3.org/2000/svg";
    const svgElement = (tag, attributes = {}, text) => {
      const node = document.createElementNS(ns, tag);
      Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
      if (text !== undefined) node.textContent = text;
      return node;
    };
    const svg = svgElement("svg", {width, height, viewBox:`0 0 ${width} ${height}`, role:"img", "aria-label":"Premise dependency graph; conclusion at top"});
    const defs = svgElement("defs");
    const marker = svgElement("marker", {id:"arrow", viewBox:"0 0 10 10", refX:9, refY:5, markerWidth:5, markerHeight:5, orient:"auto-start-reverse"});
    marker.append(svgElement("path", {d:"M 0 0 L 10 5 L 0 10 z", class:"arrow"})); defs.append(marker); svg.append(defs);
    const positions = new Map();
    layers.forEach((layer, depth) => layer.forEach((node, i) => positions.set(node.id, {x:(i + .5) * width / layer.length, y:depth * 102 + 12})));
    graph.nodes.forEach(node => (node.children || []).forEach(child => {
      const a = positions.get(node.id), b = positions.get(child);
      if (a && b) svg.append(svgElement("line", {x1:a.x, y1:a.y+64, x2:b.x, y2:b.y-3, "marker-end":"url(#arrow)"}));
    }));
    graph.nodes.forEach(node => {
      const position = positions.get(node.id);
      const status = beliefs.get(node.claim_id) || view.node_states[node.id] || "UNKNOWN";
      const group = svgElement("g", {transform:`translate(${position.x-91},${position.y})`, class:statusClass(status)});
      const label = claims.get(node.claim_id) || node.kind;
      group.append(svgElement("title", {}, `${label} — ${status}`));
      group.append(svgElement("rect", {width:182, height:64, rx:7}));
      group.append(svgElement("text", {x:10,y:17,class:"kind"}, node.kind));
      const short = label.length > 47 ? label.slice(0,44)+"…" : label;
      group.append(svgElement("text", {x:10,y:35}, short.slice(0,26)));
      group.append(svgElement("text", {x:10,y:51}, short.slice(26)));
      svg.append(group);
    });
    container.append(svg);
  }

  function render() {
    const item = data.cases[selected];
    const view = item.snapshots[step];
    byId("case-meta").textContent = `${item.run} · ${item.fixture_only ? "SCRIPTED FIXTURE" : "SAVED MODEL RUN"}`;
    byId("question").textContent = item.question;
    byId("model").textContent = `${item.model} · effort ${item.reasoning_effort || "not applicable"} · final wall time ${number(item.wall_seconds)}s · ${item.id}`;
    byId("step").max = item.snapshots.length - 1;
    byId("step").value = step;
    byId("step-label").textContent = `Event ${step+1} / ${item.snapshots.length}`;
    byId("event-label").textContent = `${view.event.type} / ${view.event.component}`;
    byId("previous").disabled = step === 0;
    byId("next").disabled = step === item.snapshots.length-1;
    const cards = byId("usage"); cards.replaceChildren();
    const metrics = [
      [number(view.usage.prompt_tokens), `Input tokens · cached ${number(view.usage.cached_input_tokens)} · local reuse ${number(view.usage.model_cache_hits)}`],
      [number(view.usage.completion_tokens), `Output tokens · reasoning ${number(view.usage.reasoning_tokens)}`],
      [`${number(view.usage.model_calls)} / ${cap(item.budget.max_llm_calls)}`, "Model calls / cap"],
      [`${number(view.usage.search_calls)} / ${cap(item.budget.max_search_calls)}`, "Search calls / cap"],
      [view.usage.cost_usd == null ? "Unknown" : "$"+number(view.usage.cost_usd), `Estimated physical cost · API calls ${number(view.usage.api_calls)}`],
    ];
    metrics.forEach(([value, label]) => {
      const card = element("div", undefined, "metric"); card.append(element("strong", value), element("span", label)); cards.append(card);
    });
    drawGraph(view);
    const claims = new Map((view.graph?.claims || []).map(c => [c.id, c.text]));
    const beliefBox = byId("beliefs"); beliefBox.replaceChildren();
    view.beliefs.forEach(b => {
      const line = element("div", undefined, "belief");
      const text = element("div", claims.get(b.claim_id) || b.claim_id);
      text.append(element("small", `Support ${number(b.support_score)} · contradiction ${number(b.contradiction_score)} · uncertainty ${number(b.uncertainty)}`));
      line.append(text, element("span", b.status, "badge "+statusClass(b.status))); beliefBox.append(line);
    });
    if (!view.beliefs.length) beliefBox.append(element("p", "No explicit belief update recorded yet.", "empty"));
    const decision = byId("decision"); decision.replaceChildren();
    decision.append(element("p", view.decision?.action || "Not yet recorded", "action"));
    decision.append(element("p", view.decision?.rationale || "Use the timeline to follow recorded decisions.", "rationale"));
    const blockers = byId("blockers"); blockers.replaceChildren();
    view.blockers.forEach(id => blockers.append(element("p", claims.get(id) || id)));
    if (!view.blockers.length) blockers.append(element("p", "No blockers recorded at this step.", "muted"));
    byId("query").textContent = view.next_query || "No pending generated query recorded.";
    const answer = byId("answer"); answer.replaceChildren();
    answer.append(element("span", item.status, "badge "+(item.status === "completed" ? "unknown" : "mixed")));
    answer.append(element("p", item.output?.answer ?? "No answer / abstention"));
    if (item.output?.citation_ids?.length) answer.append(element("small", "Citations: "+item.output.citation_ids.join(", "), "source"));
    if (item.error) answer.append(element("p", item.error, "rationale"));
    if (!item.usage_complete) answer.append(element("p", "Usage is incomplete; reported costs may omit unknown charges.", "muted"));
    const evidence = byId("evidence"); evidence.replaceChildren();
    const extracted = view.evidence.length > 0;
    const entries = extracted ? view.evidence : view.documents;
    if (!entries.length) evidence.append(element("p", "No evidence or retrieved documents recorded yet.", "empty"));
    if (!extracted && entries.length) evidence.append(element("p", "Retrieved context only; no extracted stance recorded.", "muted"));
    entries.forEach(e => {
      const card = element("article", undefined, "evidence-card");
      card.append(element("span", e.stance || "RETRIEVED", "badge "+({SUPPORT:"supported",CONTRADICT:"contradicted",NEUTRAL:"unknown"}[e.stance] || "unknown")));
      if (e.claim_id) card.append(element("p", claims.get(e.claim_id) || e.claim_id, "muted"));
      card.append(element("blockquote", e.span ?? e.text));
      card.append(element("div", `${e.source.id} · ${e.source.title} · ${e.source.uri}`, "source"));
      evidence.append(card);
    });
    byId("raw-event").textContent = JSON.stringify(item.events[step], null, 2);
  }
  function select(index) { selected = index; step = data.cases[index].snapshots.length-1; renderList(); render(); }
  byId("filter").addEventListener("input", renderList);
  byId("step").addEventListener("input", event => { step = Number(event.target.value); render(); });
  byId("previous").addEventListener("click", () => { if (step > 0) { step--; render(); } });
  byId("next").addEventListener("click", () => { if (step < data.cases[selected].snapshots.length-1) { step++; render(); } });
  select(0);
})();
