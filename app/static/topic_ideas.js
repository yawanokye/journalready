const $ = (id) => document.getElementById(id);
let lastResult = null;
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
const val = (id) => ($(id)?.value || "").trim();

function safeUrl(value) {
  try {
    const url = new URL(String(value || ""), window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch (_) { return ""; }
}

function payload() {
  return {
    research_area: val("researchArea"),
    source_mode: val("sourceMode"),
    thesis_title: val("thesisTitle"),
    thesis_material: val("thesisMaterial"),
    discipline: val("discipline"),
    context: val("context"),
    target_journal: val("targetJournal"),
    journal_scope: val("journalScope"),
    article_type: val("articleType"),
    methodology: val("methodology"),
    research_route: val("researchRoute"),
    data_available: val("dataAvailable"),
    variables_or_themes: val("variablesThemes"),
    preferred_contribution: val("preferredContribution"),
    keywords: val("keywords"),
    max_ideas: Number(val("maxIdeas") || 6),
    resource_result_limit: Number(val("resourceResultLimit") || 6),
    include_source_search: $("includeSourceSearch").checked,
    include_research_resource_search: $("includeResourceSearch").checked,
    include_older_foundational: $("includeOlderFoundational").checked
  };
}

function list(items) {
  if (!Array.isArray(items) || !items.length) return "";
  return `<ul>${items.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
}

function resourceItems(items, type) {
  if (!Array.isArray(items) || !items.length) return `<p class="muted">No ${type} candidates were identified for this route.</p>`;
  return items.map(item => {
    const url = safeUrl(item.url);
    const detail = item.coverage || item.purpose || "";
    const condition = item.access_note || item.permission_note || "";
    return `<article class="resource-card">
      <div class="resource-card-head"><strong>${esc(item.name || "Unnamed resource")}</strong><span class="resource-type">${esc(item.provider || "Source")}</span></div>
      ${detail ? `<p>${esc(detail)}</p>` : ""}
      ${item.suitability ? `<p class="muted"><strong>Why it may fit:</strong> ${esc(item.suitability)}</p>` : ""}
      ${condition ? `<p class="muted"><strong>Check before use:</strong> ${esc(condition)}</p>` : ""}
      ${url ? `<a href="${esc(url)}" target="_blank" rel="noopener">Open resource</a>` : ""}
    </article>`;
  }).join("");
}

function ideaResourceBlock(guidance) {
  if (!guidance) return "";
  const data = guidance.possible_data_sources || [];
  const instruments = guidance.possible_instruments || [];
  if (!data.length && !instruments.length) return `<div class="resource-inline"><strong>Research resource route:</strong> ${esc(guidance.research_route_label || guidance.research_route || "Not determined")}. No specific data or instrument resource is needed for this idea at this stage.</div>`;
  return `<div class="resource-inline">
    <strong>Research resource route:</strong> ${esc(guidance.research_route_label || guidance.research_route || "Not determined")}
    ${data.length ? `<details><summary>Possible secondary data sources (${data.length})</summary>${resourceItems(data, "data source")}</details>` : ""}
    ${instruments.length ? `<details><summary>Possible questionnaire or instrument sources (${instruments.length})</summary>${resourceItems(instruments, "instrument")}</details>` : ""}
    <p class="muted">${esc(guidance.guidance_note || "Verify every resource before use.")}</p>
  </div>`;
}

function renderIdeas(result) {
  const ideas = result.ideas || [];
  $("ideas").innerHTML = ideas.length ? ideas.map(item => `<article class="idea-card">
    <div class="idea-meta"><span class="pill">${esc(item.article_type)}</span><span class="pill route">${esc((item.research_route || "undetermined").replaceAll("_", " "))}</span><span class="pill score">Readiness ${esc(item.readiness_score)}%</span></div>
    <h3>${esc(item.idea_number)}. ${esc(item.title)}</h3>
    <div class="idea-section"><strong>Article angle:</strong> ${esc(item.angle)}</div>
    <div class="idea-section"><strong>Publishable gap:</strong> ${esc(item.gap)}</div>
    <div class="idea-section"><strong>Overall objective:</strong> ${esc(item.objective)}</div>
    <div class="idea-section"><strong>Questions or hypotheses:</strong>${list(item.questions_or_hypotheses)}</div>
    <div class="idea-section"><strong>Contribution:</strong> ${esc(item.contribution)}</div>
    <div class="idea-section"><strong>Method and data route:</strong> ${esc(item.method_and_data_route)}</div>
    <div class="idea-section"><strong>Journal fit:</strong> ${esc(item.journal_fit)}</div>
    <div class="idea-section"><strong>Suggested sections:</strong> ${esc((item.suggested_sections || []).join(" · "))}</div>
    <div class="idea-section"><strong>Keywords:</strong> ${esc((item.keywords || []).join(", "))}</div>
    <div class="idea-section"><strong>Evidence still needed:</strong>${list(item.evidence_needed)}</div>
    ${ideaResourceBlock(item.resource_guidance)}
    <div class="warning">${esc(item.scope_warning)}</div>
  </article>`).join("") : `<p class="muted">No suitable ideas were returned.</p>`;
  const note = result.portfolio_note || "";
  $("portfolioNote").hidden = !note;
  $("portfolioNote").textContent = note;
  $("copyBtn").disabled = !ideas.length;
}

function renderResources(result) {
  const resources = result.research_resources || {};
  const route = resources.research_route_label || resources.research_route || "Not determined";
  $("resourceSummary").innerHTML = `<strong>${esc(route)}</strong>. ${esc(resources.search_note || "Review candidate resources before use.")}`;
  $("dataSources").innerHTML = resourceItems(resources.data_sources || [], "data source");
  $("instrumentSources").innerHTML = resourceItems(resources.instrument_sources || [], "instrument");
}

function renderSources(result) {
  const sources = result.source_records_used || [];
  $("sources").innerHTML = sources.length ? sources.map(src => `<article class="source"><strong>${esc(src.key)}: ${esc(src.title || "Untitled")}</strong><div class="muted">${esc(Array.isArray(src.authors) ? src.authors.join(", ") : src.authors || "")} ${src.year ? `(${esc(src.year)})` : ""}</div><div class="muted">${esc(src.source || src.database || "")}</div>${safeUrl(src.url) ? `<a href="${esc(safeUrl(src.url))}" target="_blank" rel="noopener">Open record</a>` : ""}</article>`).join("") : `<p class="muted">No scholarly source records were available. The ideas may still be generated from the supplied study material and resource catalogues.</p>`;
}

async function generate(event) {
  event.preventDefault();
  if (!val("researchArea")) { $("status").textContent = "Enter the research area."; return; }
  $("status").textContent = "Developing focused article ideas and searching for feasible data or instrument resources...";
  $("generateBtn").disabled = true;
  try {
    const response = await fetch("/api/article-ideas", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload())});
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || response.statusText);
    lastResult = body;
    renderIdeas(body);
    renderResources(body);
    renderSources(body);
    const warnings = (body.provider_errors || []).length;
    $("status").textContent = warnings ? `Ideas generated with ${warnings} source, resource, or model warning(s). Review the evidence and access requirements.` : `Ideas and research-resource guidance generated using ${body.model_used || "the configured workflow"}.`;
  } catch (error) { $("status").textContent = `Error: ${error.message}`; }
  finally { $("generateBtn").disabled = false; }
}

function copyAll() {
  if (!lastResult) return;
  const text = (lastResult.ideas || []).map(i => {
    const g = i.resource_guidance || {};
    const data = (g.possible_data_sources || []).map(x => `${x.name} (${x.provider || ""})`).join(" | ");
    const instruments = (g.possible_instruments || []).map(x => `${x.name} (${x.provider || ""})`).join(" | ");
    return `${i.idea_number}. ${i.title}\nArticle angle: ${i.angle}\nGap: ${i.gap}\nObjective: ${i.objective}\nQuestions/Hypotheses: ${(i.questions_or_hypotheses || []).join(" | ")}\nContribution: ${i.contribution}\nMethod/Data: ${i.method_and_data_route}\nResearch route: ${i.research_route || "undetermined"}\nPossible data sources: ${data || "None identified"}\nPossible instruments: ${instruments || "None identified"}\nJournal fit: ${i.journal_fit}\nEvidence needed: ${(i.evidence_needed || []).join(" | ")}\n`;
  }).join("\n");
  navigator.clipboard.writeText(text);
  $("status").textContent = "Copied all article ideas and research-resource guidance.";
}

function clearAll() {
  $("ideaForm").reset();
  $("maxIdeas").value = "6";
  $("resourceResultLimit").value = "6";
  $("researchRoute").value = "Auto";
  $("ideas").innerHTML = `<p class="muted">Generated article ideas will appear here.</p>`;
  $("sources").innerHTML = "";
  $("dataSources").innerHTML = "";
  $("instrumentSources").innerHTML = "";
  $("resourceSummary").textContent = "Research resource guidance will appear here.";
  $("portfolioNote").hidden = true;
  $("status").textContent = "";
  $("copyBtn").disabled = true;
  lastResult = null;
}

window.addEventListener("DOMContentLoaded", () => {
  $("ideaForm").addEventListener("submit", generate);
  $("copyBtn").addEventListener("click", copyAll);
  $("clearBtn").addEventListener("click", clearAll);
});
