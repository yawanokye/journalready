const $ = (id) => document.getElementById(id);
const val = (id) => ($(id)?.value || "").trim();
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
const SOURCE_STORAGE_KEY = "articleready_attached_source_bank_v1";
const SEARCH_STORAGE_KEY = "articleready_latest_source_search_v1";

let lastText = "";
let lastInstrumentText = "";
let attachedSourceBank = [];
let latestSourceSearchResult = null;
let latestResearchResources = null;

function safeUrl(value) {
  try {
    const url = new URL(String(value || ""), window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch (_) { return ""; }
}

function sourceKey(src) {
  const doi = String(src?.doi || "").trim().toLowerCase().replace(/^https?:\/\/(?:dx\.)?doi\.org\//, "");
  if (doi) return `doi:${doi}`;
  return `title:${String(src?.title || "").toLowerCase().replace(/[^a-z0-9]+/g, "").slice(0, 120)}`;
}

function mergeSourceBank(existing, incoming, limit = 120) {
  const merged = [];
  const seen = new Set();
  for (const src of [...(existing || []), ...(incoming || [])]) {
    if (!src || typeof src !== "object") continue;
    const key = sourceKey(src);
    if (!key || key === "title:" || seen.has(key)) continue;
    seen.add(key);
    merged.push(src);
    if (merged.length >= limit) break;
  }
  return merged;
}

function persistSources() {
  try {
    localStorage.setItem(SOURCE_STORAGE_KEY, JSON.stringify(attachedSourceBank));
    if (latestSourceSearchResult) localStorage.setItem(SEARCH_STORAGE_KEY, JSON.stringify(latestSourceSearchResult));
    else localStorage.removeItem(SEARCH_STORAGE_KEY);
  } catch (_) {}
}

function restoreSources() {
  try {
    const stored = JSON.parse(localStorage.getItem(SOURCE_STORAGE_KEY) || "[]");
    attachedSourceBank = Array.isArray(stored) ? mergeSourceBank([], stored) : [];
    const latest = JSON.parse(localStorage.getItem(SEARCH_STORAGE_KEY) || "null");
    latestSourceSearchResult = latest && typeof latest === "object" ? latest : null;
  } catch (_) {
    attachedSourceBank = [];
    latestSourceSearchResult = null;
  }
}

function isIndependent() {
  return val("sourceMode") === "Develop as a new independent article";
}

function setGroupDisabled(groupId, disabled) {
  const group = $(groupId);
  if (!group) return;
  group.classList.toggle("disabled-section", disabled);
  group.querySelectorAll("input, textarea, select, button").forEach(control => { control.disabled = disabled; });
}

function applyWorkflowState(sourceChanged = false) {
  const independent = isIndependent();
  const fullOption = $("draftStage").querySelector('option[value="full_article"]');
  fullOption.disabled = independent;

  if (independent) {
    if (val("draftStage") === "full_article") $("draftStage").value = "initial_to_methods";
    if (sourceChanged) $("academicLevel").value = "PhD";
    $("sourceThesisTitle").value = "";
    $("thesisSourceMaterial").value = "";
  } else if (sourceChanged && val("academicLevel") === "PhD") {
    $("academicLevel").value = "Research Masters (e.g. MPhil)";
  }

  setGroupDisabled("sourceStudyFields", independent);
  $("independentNotice").hidden = !independent;

  const stage = val("draftStage") || "full_article";
  const initial = stage === "initial_to_methods";
  const continuation = stage === "continuation_after_results";
  $("continuationPanel").hidden = !continuation;
  $("completedEvidenceFields").hidden = initial;
  setGroupDisabled("completedEvidenceFields", initial);

  const messages = {
    full_article: "A complete study is available. The app may draft the full manuscript from supplied evidence.",
    initial_to_methods: "Stage 1 drafts the article body from Title through Methods only. Results, Discussion and Conclusion are intentionally withheld.",
    continuation_after_results: "Stage 2 requires the previous sections and completed results or analysis. It integrates them into a full article."
  };
  $("stageMessage").textContent = messages[stage];
  $("draftBtn").textContent = initial ? "Draft article up to Methods" : continuation ? "Complete article from results" : "Draft full journal article";
  $("outputHelp").textContent = initial ? "This output should stop at Methods, followed only by readiness, resource and reference notes." : continuation ? "The earlier sections and uploaded results will be integrated into one completed article." : "Review all claims, citations, results and journal requirements before submission.";
}

function sourceSearchPayload() {
  return {
    query: val("sourceSearchQuery"), article_title: val("articleTitle"), research_area: val("researchArea"),
    source_thesis_title: isIndependent() ? "" : val("sourceThesisTitle"), extraction_focus: val("extractionFocus"),
    context: val("context"), objectives: val("objectives"), theory_or_framework: val("theoryFramework"),
    variables_constructs: val("variablesConstructs"), key_findings: val("keyFindings"), methodology: val("methodology"),
    article_type: val("articleType"), academic_level: val("academicLevel"), max_results: Number($("sourceMaxResults")?.value || 12),
    include_older_foundational: Boolean($("includeOlderFoundational")?.checked)
  };
}

function researchResourcePayload() {
  return {
    article_title: val("articleTitle"), research_area: val("researchArea"), source_mode: val("sourceMode"),
    article_type: val("articleType"), research_route: val("researchRoute"), context: val("context"),
    objectives: val("objectives"), variables_constructs: val("variablesConstructs"), methodology: val("methodology"),
    data_available: [val("dataResults"), val("continuationMaterial")].join(" ").trim(), extraction_focus: val("extractionFocus"),
    instrument_requirements: val("instrumentRequirements"), max_results: Number($("resourceMaxResults")?.value || 6),
    include_live_search: Boolean($("includeSourceSearch")?.checked)
  };
}

function payload() {
  return {
    article_title: val("articleTitle"), research_area: val("researchArea"), source_mode: val("sourceMode"),
    draft_stage: val("draftStage"), source_thesis_title: isIndependent() ? "" : val("sourceThesisTitle"),
    thesis_source_material: isIndependent() ? "" : val("thesisSourceMaterial"), previous_sections: val("previousSections"),
    continuation_material: val("continuationMaterial"), extraction_focus: val("extractionFocus"), target_journal: val("targetJournal"),
    author_guidelines: val("authorGuidelines"), article_type: val("articleType"), academic_level: val("academicLevel"),
    research_route: val("researchRoute"), methodology: val("methodology"), context: val("context"),
    research_problem: val("researchProblem"), objectives: val("objectives"), theory_or_framework: val("theoryFramework"),
    variables_constructs: val("variablesConstructs"), data_and_results: val("dataResults"), key_findings: val("keyFindings"),
    contribution: val("contribution"), references_notes: val("referencesNotes"), instrument_requirements: val("instrumentRequirements"),
    include_instrument_draft: Boolean($("includeInstrumentDraft")?.checked), word_limit: val("wordLimit"), citation_style: val("citationStyle"),
    include_source_search: Boolean($("includeSourceSearch")?.checked), include_older_foundational: Boolean($("includeOlderFoundational")?.checked),
    include_research_resource_search: Boolean($("includeResourceSearch")?.checked), source_search_terms: latestSourceSearchResult?.query || val("sourceSearchQuery"),
    source_bank: attachedSourceBank, research_resources: latestResearchResources || {},
    retrieved_sources: latestSourceSearchResult ? {...latestSourceSearchResult, sources: latestSourceSearchResult.sources || [], source_bank_count: attachedSourceBank.length, frontend_attached: true} : {}
  };
}

function sourceCard(src, index, compact = false) {
  const authors = Array.isArray(src.authors) ? src.authors.join(", ") : (src.authors || "");
  const url = safeUrl(src.url || (src.doi ? `https://doi.org/${String(src.doi).replace(/^https?:\/\/(?:dx\.)?doi\.org\//, "")}` : ""));
  const abstract = String(src.abstract || "").trim();
  const origin = src.attachment_origin || "";
  const originLabel = origin === "attached_before_drafting" || origin === "manual_source_search" ? "Attached before drafting" : origin === "automatic_draft_search" ? "Found during drafting" : "Source record";
  return `<article class="source${compact ? " source-compact" : ""}"><div class="source-title-line"><strong>${esc(src.key ? `${src.key}: ` : `${index + 1}. `)}${esc(src.title || "Untitled")}</strong><span class="source-origin">${esc(originLabel)}</span></div><div class="muted">${esc(authors)} ${src.year ? `(${esc(src.year)})` : ""}</div><div class="muted">${esc(src.source || src.database || "")}${src.doi ? ` · DOI ${esc(src.doi)}` : ""}</div>${!compact && abstract ? `<p class="source-abstract">${esc(abstract)}</p>` : ""}${src.apa_hint || src.reference_entry_hint ? `<div class="source-hint"><strong>Citation hint:</strong> ${esc(src.apa_hint || src.reference_entry_hint)}</div>` : ""}${url ? `<a href="${esc(url)}" target="_blank" rel="noopener">Open source record</a>` : ""}</article>`;
}

function resourceCards(items, type) {
  if (!Array.isArray(items) || !items.length) return `<p class="muted">No ${type} candidates were identified.</p>`;
  return items.map(item => {
    const url = safeUrl(item.url);
    const detail = item.coverage || item.purpose || "";
    const check = item.access_note || item.permission_note || "";
    return `<article class="resource-card"><div class="resource-card-head"><strong>${esc(item.name || "Unnamed resource")}</strong><span class="resource-type">${esc(item.provider || "Source")}</span></div>${detail ? `<p>${esc(detail)}</p>` : ""}${item.suitability ? `<p class="muted"><strong>Possible fit:</strong> ${esc(item.suitability)}</p>` : ""}${check ? `<p class="muted"><strong>Check:</strong> ${esc(check)}</p>` : ""}${url ? `<a href="${esc(url)}" target="_blank" rel="noopener">Open resource</a>` : ""}</article>`;
  }).join("");
}

function renderAttachedSummary() {
  const count = attachedSourceBank.length;
  $("attachedSourceBadge").textContent = `${count} attached`;
  $("attachedSourceSummary").innerHTML = count ? `<strong>${count} deduplicated source record${count === 1 ? "" : "s"} attached.</strong> These records will be sent with the article draft and filtered for relevance.` : "No literature records are attached yet.";
}

function renderLatestSearch(result) {
  const sources = result?.sources || [];
  $("sourceSearchResults").innerHTML = sources.length ? sources.map((src, index) => sourceCard(src, index, true)).join("") : latestSourceSearchResult ? `<p class="muted">No usable source records were returned. Refine the search terms.</p>` : "";
}

function renderResearchResources(resources) {
  latestResearchResources = resources || null;
  const route = resources?.research_route_label || resources?.research_route || "Auto";
  $("resourceRouteBadge").textContent = route;
  $("resourceSummary").innerHTML = resources ? `<strong>${esc(route)}</strong>. ${esc(resources.search_note || "Verify all candidates before use.")}` : "No research-resource guidance has been generated yet.";
  $("writerDataSources").innerHTML = resourceCards(resources?.data_sources || [], "data source");
  $("writerInstrumentSources").innerHTML = resourceCards(resources?.instrument_sources || [], "instrument");
}


function markResourcesStale() {
  if (!latestResearchResources) return;
  latestResearchResources = null;
  renderResearchResources(null);
  $("resourceStatus").textContent = "Article inputs changed. Run the research-resource search again before drafting.";
}

function renderDraftSources(result) {
  $("filters").innerHTML = (result.quality_filters || []).map(x => `<span class="pill">${esc(x)}</span>`).join("");
  const sources = result.source_records_used || [];
  const attachedCount = Number(result.attached_source_count || 0);
  const automaticCount = Number(result.automatic_source_count || 0);
  $("draftSourceSummary").innerHTML = sources.length ? `<strong>${sources.length} source records supplied to the drafting model.</strong> ${attachedCount} came from the pre-draft attached bank and ${automaticCount} were found automatically. This doesn’t mean every record was cited.` : "No source records were supplied to this draft.";
  $("sources").innerHTML = sources.length ? sources.map((src, index) => sourceCard(src, index, false)).join("") : `<p class="muted">No source records were available.</p>`;
}

async function findSources() {
  const searchContext = [val("sourceSearchQuery"), val("articleTitle"), val("researchArea"), val("extractionFocus")].join(" ").trim();
  if (!searchContext) { $("sourceStatus").textContent = "Enter an article title, research area, development focus or search terms first."; return; }
  $("findSourcesBtn").disabled = true;
  $("sourceStatus").textContent = "Searching scholarly metadata and attaching relevant records...";
  try {
    const response = await fetch("/api/articles/find-sources", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(sourceSearchPayload())});
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || response.statusText);
    latestSourceSearchResult = body;
    attachedSourceBank = mergeSourceBank(attachedSourceBank, body.source_bank || body.sources || []);
    persistSources(); renderAttachedSummary(); renderLatestSearch(body);
    const warnings = (body.provider_errors || []).length;
    const excluded = Number(body.excluded_retracted_count || 0);
    $("sourceStatus").textContent = `Attached ${body.source_bank_count || body.count || 0} record(s). The bank now contains ${attachedSourceBank.length}. ${excluded ? `${excluded} unsafe record(s) were excluded. ` : ""}${warnings ? `${warnings} provider(s) could not be reached.` : ""}`;
  } catch (error) { $("sourceStatus").textContent = `Source search error: ${error.message}`; }
  finally { $("findSourcesBtn").disabled = false; }
}

async function findResources() {
  if (!val("articleTitle") && !val("researchArea")) { $("resourceStatus").textContent = "Enter the article title or research area first."; return; }
  $("findResourcesBtn").disabled = true;
  $("resourceStatus").textContent = "Searching for possible data sources and instrument records...";
  try {
    const response = await fetch("/api/articles/research-resources", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(researchResourcePayload())});
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || response.statusText);
    renderResearchResources(body);
    const warnings = (body.provider_errors || []).length;
    $("resourceStatus").textContent = `Resource guidance generated for ${body.research_route_label || body.research_route}. ${warnings ? `${warnings} scholarly provider warning(s) occurred.` : "Verify access, permission and fit before use."}`;
  } catch (error) { $("resourceStatus").textContent = `Resource search error: ${error.message}`; }
  finally { $("findResourcesBtn").disabled = false; }
}

function clearAttachedSources() {
  attachedSourceBank = []; latestSourceSearchResult = null; persistSources(); renderAttachedSummary(); renderLatestSearch(null); $("sourceStatus").textContent = "Attached source records cleared.";
}

async function extractFiles(inputId, targetId, label) {
  const files = Array.from($(inputId).files || []);
  if (!files.length) { $("uploadStatus").textContent = `Choose at least one ${label} file.`; return; }
  $("uploadStatus").textContent = `Extracting ${files.length} ${label} file(s)...`;
  const chunks = [];
  for (const file of files) {
    const form = new FormData(); form.append("file", file);
    const response = await fetch("/api/articles/extract-file", {method:"POST", body:form});
    const body = await response.json();
    if (!response.ok) throw new Error(`${file.name}: ${body.detail || response.statusText}`);
    chunks.push(`\n\n[Uploaded file: ${body.filename}]\n${body.text}`);
  }
  const existing = val(targetId);
  $(targetId).value = `${existing}${chunks.join("")}`.trim();
  $("uploadStatus").textContent = `Extracted ${files.length} ${label} file(s). Review the text before drafting.`;
}

async function draft(event) {
  event.preventDefault();
  if (!val("articleTitle")) { $("status").textContent = "Enter a working article title or topic."; return; }
  if (val("draftStage") === "continuation_after_results" && !val("previousSections") && !val("continuationMaterial") && !val("dataResults")) {
    $("status").textContent = "Stage 2 requires the previous sections and completed results or analysis."; return;
  }
  const attachedMessage = attachedSourceBank.length ? ` with ${attachedSourceBank.length} attached source record(s)` : "";
  $("status").textContent = `Preparing the selected article stage${attachedMessage}...`;
  $("draftBtn").disabled = true; $("copyBtn").disabled = true; $("downloadBtn").disabled = true;
  try {
    const response = await fetch("/api/articles/draft", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload())});
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || response.statusText);
    lastText = body.article_text || "";
    lastInstrumentText = body.instrument_text || "";
    $("articleOutput").value = lastText;
    $("instrumentOutput").value = lastInstrumentText;
    $("instrumentOutputPanel").hidden = !lastInstrumentText;
    if (body.research_resources) renderResearchResources(body.research_resources);
    renderDraftSources(body);
    const warnings = (body.provider_errors || []).length;
    $("status").textContent = `${body.draft_stage === "initial_to_methods" ? "Stage 1 draft completed through Methods" : body.draft_stage === "continuation_after_results" ? "Stage 2 article completion finished" : "Full article draft completed"} using ${body.model_used || "the configured workflow"}. ${warnings ? `Review ${warnings} warning(s).` : "Review all placeholders, resources, citations and evidence."}`;
    $("copyBtn").disabled = !lastText; $("downloadBtn").disabled = !lastText;
  } catch (error) { $("status").textContent = `Error: ${error.message}`; }
  finally { $("draftBtn").disabled = false; }
}

async function copyContent(text, label) {
  if (!text) return;
  await navigator.clipboard.writeText(text);
  $("status").textContent = `${label} copied.`;
}

async function downloadContent(text, title, filename) {
  if (!text) return;
  $("status").textContent = "Preparing the DOCX file...";
  try {
    const response = await fetch("/api/articles/export", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({article_title:title, article_text:text})});
    if (!response.ok) { let detail = response.statusText; try { detail = (await response.json()).detail || detail; } catch (_) {} throw new Error(detail); }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url); $("status").textContent = "DOCX downloaded.";
  } catch (error) { $("status").textContent = `Export error: ${error.message}`; }
}

function clearAll() {
  $("articleForm").reset(); $("wordLimit").value = "6000-8000"; $("draftStage").value = "full_article"; $("academicLevel").value = "Research Masters (e.g. MPhil)"; $("researchRoute").value = "Auto";
  $("articleOutput").value = ""; $("instrumentOutput").value = ""; $("instrumentOutputPanel").hidden = true; $("instrumentRequirementsLabel").hidden = true; $("filters").innerHTML = ""; $("sources").innerHTML = ""; $("draftSourceSummary").innerHTML = ""; $("status").textContent = "";
  $("copyBtn").disabled = true; $("downloadBtn").disabled = true; lastText = ""; lastInstrumentText = ""; latestResearchResources = null; renderResearchResources(null); clearAttachedSources(); applyWorkflowState(false);
}

window.addEventListener("DOMContentLoaded", () => {
  restoreSources(); renderAttachedSummary(); renderLatestSearch(latestSourceSearchResult); renderResearchResources(null); applyWorkflowState(false);
  $("sourceMode").addEventListener("change", () => applyWorkflowState(true));
  $("draftStage").addEventListener("change", () => applyWorkflowState(false));
  $("researchRoute").addEventListener("change", () => { $("resourceRouteBadge").textContent = val("researchRoute"); markResourcesStale(); });
  $("includeInstrumentDraft").addEventListener("change", () => { $("instrumentRequirementsLabel").hidden = !$("includeInstrumentDraft").checked; });
  ["articleTitle", "researchArea", "context", "objectives", "variablesConstructs", "methodology", "extractionFocus"].forEach(id => $(id).addEventListener("input", markResourcesStale));
  $("articleForm").addEventListener("submit", draft);
  $("findSourcesBtn").addEventListener("click", findSources);
  $("clearSourcesBtn").addEventListener("click", clearAttachedSources);
  $("findResourcesBtn").addEventListener("click", findResources);
  $("extractPreviousBtn").addEventListener("click", async () => { try { await extractFiles("previousSectionsFiles", "previousSections", "previous-section"); } catch (error) { $("uploadStatus").textContent = `Upload error: ${error.message}`; } });
  $("extractResultsBtn").addEventListener("click", async () => { try { await extractFiles("resultsFiles", "continuationMaterial", "results or analysis"); } catch (error) { $("uploadStatus").textContent = `Upload error: ${error.message}`; } });
  $("copyBtn").addEventListener("click", () => copyContent($("articleOutput").value || lastText, "Article draft"));
  $("downloadBtn").addEventListener("click", () => downloadContent($("articleOutput").value || lastText, val("articleTitle") || "Journal Article Draft", "journal_article_draft.docx"));
  $("copyInstrumentBtn").addEventListener("click", () => copyContent($("instrumentOutput").value || lastInstrumentText, "Instrument draft"));
  $("downloadInstrumentBtn").addEventListener("click", () => downloadContent($("instrumentOutput").value || lastInstrumentText, `${val("articleTitle") || "Article"} Instrument`, "article_instrument_draft.docx"));
  $("clearBtn").addEventListener("click", clearAll);
});
