const $ = (id) => document.getElementById(id);
const val = (id) => ($(id)?.value || "").trim();
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
let lastText = "";

function payload() {
  return {
    article_title: val("articleTitle"), research_area: val("researchArea"), source_mode: val("sourceMode"),
    source_thesis_title: val("sourceThesisTitle"), thesis_source_material: val("thesisSourceMaterial"), extraction_focus: val("extractionFocus"),
    target_journal: val("targetJournal"), author_guidelines: val("authorGuidelines"), article_type: val("articleType"), academic_level: val("academicLevel"),
    methodology: val("methodology"), context: val("context"), research_problem: val("researchProblem"), objectives: val("objectives"),
    theory_or_framework: val("theoryFramework"), variables_constructs: val("variablesConstructs"), data_and_results: val("dataResults"),
    key_findings: val("keyFindings"), contribution: val("contribution"), references_notes: val("referencesNotes"), word_limit: val("wordLimit"),
    citation_style: val("citationStyle"), include_source_search: $("includeSourceSearch").checked, include_older_foundational: $("includeOlderFoundational").checked
  };
}

function renderSources(result) {
  const filters = result.quality_filters || [];
  $("filters").innerHTML = filters.map(x => `<span class="pill">${esc(x)}</span>`).join("");
  const sources = result.source_records_used || [];
  $("sources").innerHTML = sources.length ? sources.map(src => `<article class="source"><strong>${esc(src.key)}: ${esc(src.title || "Untitled")}</strong><div class="muted">${esc(Array.isArray(src.authors) ? src.authors.join(", ") : src.authors || "")} ${src.year ? `(${esc(src.year)})` : ""}</div><div class="muted">${esc(src.source || src.database || "")}</div>${src.url ? `<a href="${esc(src.url)}" target="_blank" rel="noopener">Open record</a>` : ""}</article>`).join("") : `<p class="muted">No source records were available. Add verified references or enable source search.</p>`;
}

async function draft(event) {
  event.preventDefault();
  if (!val("articleTitle")) { $("status").textContent = "Enter a working article title or topic."; return; }
  $("status").textContent = "Checking sources and drafting the focused journal article...";
  $("draftBtn").disabled = true; $("copyBtn").disabled = true; $("downloadBtn").disabled = true;
  try {
    const response = await fetch("/api/articles/draft", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload())});
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || response.statusText);
    lastText = body.article_text || ""; $("articleOutput").value = lastText; renderSources(body);
    const warnings = (body.provider_errors || []).length;
    $("status").textContent = warnings ? `Draft completed with ${warnings} source or model warning(s). Review placeholders and evidence.` : `Draft completed using ${body.model_used || "the configured workflow"}.`;
    $("copyBtn").disabled = !lastText; $("downloadBtn").disabled = !lastText;
  } catch (error) { $("status").textContent = `Error: ${error.message}`; }
  finally { $("draftBtn").disabled = false; }
}

async function copyText() { const text = $("articleOutput").value || lastText; if (!text) return; await navigator.clipboard.writeText(text); $("status").textContent = "Copied the article draft."; }
async function downloadDocx() {
  const text = $("articleOutput").value || lastText; if (!text) return;
  $("status").textContent = "Preparing the DOCX file...";
  try {
    const response = await fetch("/api/articles/export", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({article_title: val("articleTitle") || "Journal Article Draft", article_text:text})});
    if (!response.ok) { let detail = response.statusText; try { detail = (await response.json()).detail || detail; } catch (_) {} throw new Error(detail); }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = "journal_article_draft.docx"; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url); $("status").textContent = "DOCX downloaded.";
  } catch (error) { $("status").textContent = `Export error: ${error.message}`; }
}
function clearAll() { $("articleForm").reset(); $("wordLimit").value = "6000-8000"; $("articleOutput").value = ""; $("filters").innerHTML = ""; $("sources").innerHTML = ""; $("status").textContent = ""; $("copyBtn").disabled = true; $("downloadBtn").disabled = true; lastText = ""; }
window.addEventListener("DOMContentLoaded", () => { $("articleForm").addEventListener("submit", draft); $("copyBtn").addEventListener("click", copyText); $("downloadBtn").addEventListener("click", downloadDocx); $("clearBtn").addEventListener("click", clearAll); });
