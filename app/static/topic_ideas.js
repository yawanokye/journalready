const $ = (id) => document.getElementById(id);
let lastResult = null;
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
const val = (id) => ($(id)?.value || "").trim();

function payload() {
  return {
    research_area: val("researchArea"), source_mode: val("sourceMode"), thesis_title: val("thesisTitle"), thesis_material: val("thesisMaterial"),
    discipline: val("discipline"), context: val("context"), target_journal: val("targetJournal"), journal_scope: val("journalScope"),
    article_type: val("articleType"), methodology: val("methodology"), data_available: val("dataAvailable"), variables_or_themes: val("variablesThemes"),
    preferred_contribution: val("preferredContribution"), keywords: val("keywords"), max_ideas: Number(val("maxIdeas") || 6),
    include_source_search: $("includeSourceSearch").checked, include_older_foundational: $("includeOlderFoundational").checked
  };
}

function list(items) {
  if (!Array.isArray(items) || !items.length) return "";
  return `<ul>${items.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
}

function renderIdeas(result) {
  const ideas = result.ideas || [];
  $("ideas").innerHTML = ideas.length ? ideas.map(item => `<article class="idea-card">
    <div class="idea-meta"><span class="pill">${esc(item.article_type)}</span><span class="pill score">Readiness ${esc(item.readiness_score)}%</span></div>
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
    <div class="warning">${esc(item.scope_warning)}</div>
  </article>`).join("") : `<p class="muted">No suitable ideas were returned.</p>`;
  const note = result.portfolio_note || "";
  $("portfolioNote").hidden = !note;
  $("portfolioNote").textContent = note;
  $("copyBtn").disabled = !ideas.length;
}

function renderSources(result) {
  const sources = result.source_records_used || [];
  $("sources").innerHTML = sources.length ? sources.map(src => `<article class="source"><strong>${esc(src.key)}: ${esc(src.title || "Untitled")}</strong><div class="muted">${esc(Array.isArray(src.authors) ? src.authors.join(", ") : src.authors || "")} ${src.year ? `(${esc(src.year)})` : ""}</div><div class="muted">${esc(src.source || src.database || "")}</div>${src.url ? `<a href="${esc(src.url)}" target="_blank" rel="noopener">Open record</a>` : ""}</article>`).join("") : `<p class="muted">No source records were available. The ideas may still be generated from the supplied study material.</p>`;
}

async function generate(event) {
  event.preventDefault();
  if (!val("researchArea")) { $("status").textContent = "Enter the research area."; return; }
  $("status").textContent = "Developing focused article ideas and checking literature signals...";
  $("generateBtn").disabled = true;
  try {
    const response = await fetch("/api/article-ideas", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload())});
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || response.statusText);
    lastResult = body;
    renderIdeas(body); renderSources(body);
    const warnings = (body.provider_errors || []).length;
    $("status").textContent = warnings ? `Ideas generated with ${warnings} source or model warning(s). Review the evidence requirements.` : `Ideas generated using ${body.model_used || "the configured workflow"}.`;
  } catch (error) { $("status").textContent = `Error: ${error.message}`; }
  finally { $("generateBtn").disabled = false; }
}

function copyAll() {
  if (!lastResult) return;
  const text = (lastResult.ideas || []).map(i => `${i.idea_number}. ${i.title}\nArticle angle: ${i.angle}\nGap: ${i.gap}\nObjective: ${i.objective}\nQuestions/Hypotheses: ${(i.questions_or_hypotheses || []).join(" | ")}\nContribution: ${i.contribution}\nMethod/Data: ${i.method_and_data_route}\nJournal fit: ${i.journal_fit}\nEvidence needed: ${(i.evidence_needed || []).join(" | ")}\n`).join("\n");
  navigator.clipboard.writeText(text);
  $("status").textContent = "Copied all article ideas.";
}

function clearAll() { $("ideaForm").reset(); $("maxIdeas").value = "6"; $("ideas").innerHTML = `<p class="muted">Generated article ideas will appear here.</p>`; $("sources").innerHTML = ""; $("portfolioNote").hidden = true; $("status").textContent = ""; $("copyBtn").disabled = true; lastResult = null; }
window.addEventListener("DOMContentLoaded", () => { $("ideaForm").addEventListener("submit", generate); $("copyBtn").addEventListener("click", copyAll); $("clearBtn").addEventListener("click", clearAll); });
