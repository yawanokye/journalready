const $ = (id) => document.getElementById(id);
function apiErrorMessage(value, fallback = "The request could not be completed.") {
  if (value == null) return fallback;
  if (typeof value === "string") return value.trim() || fallback;
  if (value instanceof Error) return apiErrorMessage(value.message, fallback);
  if (Array.isArray(value)) {
    const messages = value.map(item => apiErrorMessage(item, "")).filter(Boolean);
    return messages.length ? messages.join("; ") : fallback;
  }
  if (typeof value === "object") {
    if (typeof value.msg === "string") {
      const location = Array.isArray(value.loc) ? value.loc.filter(x => x !== "body").join(" → ") : "";
      return `${location ? `${location}: ` : ""}${value.msg}`;
    }
    for (const key of ["message", "detail", "error", "reason", "description", "errors"]) {
      if (value[key] != null) {
        const message = apiErrorMessage(value[key], "");
        if (message) return message;
      }
    }
    try {
      const serialised = JSON.stringify(value);
      if (serialised && serialised !== "{}") return serialised;
    } catch (_) {}
  }
  const text = String(value || "").trim();
  return text && text !== "[object Object]" ? text : fallback;
}

async function readApiResponse(response) {
  const text = await response.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch (_) { return {detail: text}; }
}

const val = (id) => ($(id)?.value || "").trim();
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
const SOURCE_STORAGE_KEY = "articleready_attached_source_bank_v1";
const SEARCH_STORAGE_KEY = "articleready_latest_source_search_v1";
const REVIEW_WORKSPACE_PAYLOAD_KEY = "articleready_review_workspace_payload_v1";

let lastText = "";
let lastInstrumentText = "";
let lastReviewProtocolText = "";
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

function isFullSynthesisArticle() {
  const type = val("articleType").toLowerCase();
  return ["systematic", "scoping", "conceptual", "theory", "bibliometric", "scientometric"].some(term => type.includes(term));
}

function isReviewEvidenceArticle() {
  const type = val("articleType").toLowerCase();
  return ["systematic", "scoping", "review", "conceptual", "theory", "integrative", "bibliometric", "scientometric"].some(term => type.includes(term));
}

function numberOrNull(id) {
  const raw = val(id);
  if (raw === "") return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed >= 0 ? Math.floor(parsed) : null;
}


function importReviewWorkspacePayload() {
  let data = null;
  try {
    data = JSON.parse(localStorage.getItem(REVIEW_WORKSPACE_PAYLOAD_KEY) || "null");
  } catch (_) { data = null; }
  if (!data || typeof data !== "object") return false;

  const mapping = {
    review_protocol_positioning: "reviewProtocolPositioning",
    review_databases: "reviewDatabases",
    review_search_strings: "reviewSearchStrings",
    review_search_date: "reviewSearchDate",
    review_date_limits: "reviewDateLimits",
    review_language_limits: "reviewLanguageLimits",
    review_document_types: "reviewDocumentTypes",
    review_eligibility_criteria: "reviewEligibilityCriteria",
    review_screening_process: "reviewScreeningProcess",
    review_quality_appraisal: "reviewQualityAppraisal",
    review_citation_tracking: "reviewCitationTracking",
    review_duplicate_removal: "reviewDuplicateRemoval",
    review_synthesis_method: "reviewSynthesisMethod",
    review_software: "reviewSoftware",
    review_protocol_notes: "reviewProtocolNotes",
    review_records_identified: "reviewRecordsIdentified",
    review_duplicates_removed: "reviewDuplicatesRemoved",
    review_records_screened: "reviewRecordsScreened",
    review_records_excluded: "reviewRecordsExcluded",
    review_full_text_assessed: "reviewFullTextAssessed",
    review_full_text_excluded: "reviewFullTextExcluded",
    review_citation_tracking_additions: "reviewCitationTrackingAdditions",
    review_final_corpus_size: "reviewFinalCorpusSize",
  };
  if (data.article_type && $("articleType")) $("articleType").value = data.article_type;
  if ($("sourceMode")) $("sourceMode").value = "Develop as a new independent article";
  if (data.workspace_title && $("articleTitle") && !val("articleTitle")) $("articleTitle").value = data.workspace_title;
  if (data.research_problem && $("researchProblem") && !val("researchProblem")) $("researchProblem").value = data.research_problem;
  if (data.methodology && $("methodology") && !val("methodology")) $("methodology").value = data.methodology;
  for (const [key, id] of Object.entries(mapping)) {
    const element = $(id);
    if (!element || data[key] == null) continue;
    element.value = String(data[key]);
  }
  if ($("includeReviewProtocolPackage")) $("includeReviewProtocolPackage").checked = true;
  applyWorkflowState(true, true);
  const status = $("reviewWorkspaceImportStatus");
  if (status) {
    const summary = data.workspace_summary || {};
    status.hidden = false;
    status.textContent = `Imported from Review Evidence Workspace: ${summary.records_identified || 0} identified, ${summary.duplicates_removed || 0} duplicates removed, ${summary.records_screened || 0} screened and ${summary.final_corpus || 0} included.`;
  }
  localStorage.removeItem(REVIEW_WORKSPACE_PAYLOAD_KEY);
  return true;
}

function currentTargetWords() {
  const explicit = Number(val("targetWordCount") || 0);
  if (explicit) return Math.max(1200, Math.min(explicit, 30000));
  const nums = (val("wordLimit") || "").replace(/,/g, "").match(/\d{3,5}/g) || [];
  if (nums.length >= 2) return Math.round((Number(nums[0]) + Number(nums[1])) / 2);
  if (nums.length === 1) return Number(nums[0]);
  return 8000;
}

function updateLengthPlanSummary() {
  const words = currentTargetWords();
  const mode = val("longWriteMode") || "auto";
  const sourceCount = attachedSourceBank.length;
  const outputTokens = Math.round(words * 1.35);
  const baseInput = 4500 + Math.round(sourceCount * 250);
  const autoThreshold = isFullSynthesisArticle() ? 9500 : 6500;
  const batch = mode === "batch" || (mode === "auto" && words >= autoThreshold);
  const estimatedTotal = batch ? Math.round((baseInput * 3.5) + outputTokens) : baseInput + outputTokens;
  const modeText = batch ? "Batch drafting expected" : "Single-pass drafting expected";
  $("tokenEstimateBadge").textContent = `${Math.round(estimatedTotal / 1000)}k token estimate`;
  $("lengthPlanSummary").innerHTML = `<strong>${esc(words.toLocaleString())} target words.</strong> ${modeText}. Actual usage changes with uploaded material, source records, tables, figures and references.`;
}

function setGroupDisabled(groupId, disabled) {
  const group = $(groupId);
  if (!group) return;
  group.classList.toggle("disabled-section", disabled);
  group.querySelectorAll("input, textarea, select, button").forEach(control => { control.disabled = disabled; });
}

function applyWorkflowState(sourceChanged = false, articleTypeChanged = false) {
  const independent = isIndependent();
  const synthesisFull = isFullSynthesisArticle();
  const reviewEvidence = isReviewEvidenceArticle();
  const draftStage = $("draftStage");
  const fullOption = draftStage.querySelector('option[value="full_article"]');
  const initialOption = draftStage.querySelector('option[value="initial_to_methods"]');

  fullOption.disabled = independent && !synthesisFull;
  fullOption.textContent = synthesisFull
    ? "Full synthesis article from literature or publication metadata"
    : "Full article from a completed study";
  initialOption.textContent = synthesisFull
    ? "Optional protocol or methods-only draft"
    : "Stage 1: Develop new article up to Methods";

  if (independent) {
    if (synthesisFull) {
      if (sourceChanged || articleTypeChanged) {
        draftStage.value = "full_article";
      }
    } else if (val("draftStage") === "full_article") {
      draftStage.value = "initial_to_methods";
    }
    if (sourceChanged) $("academicLevel").value = "PhD";
    $("sourceThesisTitle").value = "";
    $("thesisSourceMaterial").value = "";
  } else if (sourceChanged && val("academicLevel") === "PhD") {
    $("academicLevel").value = "Research Masters (e.g. MPhil)";
  }

  setGroupDisabled("sourceStudyFields", independent);
  $("reviewProtocolInputPanel").hidden = !reviewEvidence;
  setGroupDisabled("reviewProtocolInputPanel", !reviewEvidence);
  $("independentNotice").hidden = !independent;
  if (independent) {
    $("independentNotice").innerHTML = synthesisFull
      ? "<strong>Independent synthesis article mode is active.</strong> Thesis and project inputs are disabled. A complete systematic, scoping, conceptual or bibliometric article can be drafted from verified literature, source records and supplied review outputs. Missing screening or bibliometric results remain red author-action items."
      : "<strong>Independent empirical article mode is active.</strong> Thesis, dissertation and project inputs are disabled. Research depth is PhD by default, and Stage 1 stops at Methods until results or analysis are supplied.";
  }

  const stage = val("draftStage") || "full_article";
  const initial = stage === "initial_to_methods";
  const continuation = stage === "continuation_after_results";
  $("continuationPanel").hidden = !continuation;
  $("completedEvidenceFields").hidden = initial;
  setGroupDisabled("completedEvidenceFields", initial);

  if (synthesisFull && stage === "full_article") {
    $("dataResults").placeholder = "Optional. Paste verified review-screening counts, included-study synthesis, bibliometric tables, network outputs, cluster results, thematic maps, or corpus statistics. Missing formal outputs are shown as red author-action items rather than invented.";
    $("keyFindings").placeholder = "Optional. State verified synthesis findings, conceptual propositions, bibliometric patterns, clusters, themes, or research fronts.";
  } else {
    $("dataResults").placeholder = "Paste actual coefficients, p-values, fit statistics, themes, quotations, robustness checks, tables, or a careful results summary.";
    $("keyFindings").placeholder = "State only findings supported by the study evidence";
  }

  let stageMessage = "";
  if (stage === "full_article" && synthesisFull) {
    stageMessage = "A complete synthesis article is produced from verified literature or publication metadata. Primary data collection is not required. Unsupplied screening, corpus or software-derived results remain red author-action items.";
  } else if (stage === "full_article") {
    stageMessage = "A complete study is available. The app may draft the full manuscript from supplied evidence.";
  } else if (stage === "initial_to_methods") {
    stageMessage = synthesisFull
      ? "This optional protocol route develops the review rationale and methods only. Select Full synthesis article to generate the complete paper."
      : "Stage 1 drafts the article body from Title through Methods only. Results, Discussion and Conclusion are intentionally withheld.";
  } else {
    stageMessage = "Stage 2 requires the previous sections and completed results or analysis. It integrates them into a full article.";
  }
  $("stageMessage").textContent = stageMessage;
  $("draftBtn").textContent = initial ? "Draft article up to Methods" : continuation ? "Complete article from results" : synthesisFull ? "Draft full synthesis article" : "Draft full journal article";
  $("outputHelp").textContent = initial
    ? "This output stops at Methods, followed only by readiness, resource and reference notes."
    : continuation
      ? "The earlier sections and uploaded results are integrated into one completed article."
      : synthesisFull
        ? "The complete synthesis paper is drafted from verified evidence. Review all red author-action items before submission."
        : "Review all claims, citations, results and journal requirements before submission.";
  updateLengthPlanSummary();
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
    include_instrument_draft: Boolean($("includeInstrumentDraft")?.checked), word_limit: val("wordLimit"),
    target_word_count: Number(val("targetWordCount") || 0) || null, article_structure: val("articleStructure"), long_write_mode: val("longWriteMode") || "auto",
    citation_style: val("citationStyle"), humanizer_mode: val("humanizerMode") || "balanced",
    include_source_search: Boolean($("includeSourceSearch")?.checked), include_older_foundational: Boolean($("includeOlderFoundational")?.checked),
    include_research_resource_search: Boolean($("includeResourceSearch")?.checked), source_search_terms: latestSourceSearchResult?.query || val("sourceSearchQuery"),
    source_bank: attachedSourceBank, research_resources: latestResearchResources || {},
    include_review_protocol_package: Boolean($("includeReviewProtocolPackage")?.checked),
    review_protocol_positioning: val("reviewProtocolPositioning") || "Auto", review_databases: val("reviewDatabases"),
    review_search_strings: val("reviewSearchStrings"), review_search_date: val("reviewSearchDate"), review_date_limits: val("reviewDateLimits"),
    review_language_limits: val("reviewLanguageLimits"), review_document_types: val("reviewDocumentTypes"),
    review_eligibility_criteria: val("reviewEligibilityCriteria"), review_screening_process: val("reviewScreeningProcess"),
    review_quality_appraisal: val("reviewQualityAppraisal"), review_citation_tracking: val("reviewCitationTracking"),
    review_duplicate_removal: val("reviewDuplicateRemoval"), review_synthesis_method: val("reviewSynthesisMethod"),
    review_software: val("reviewSoftware"), review_protocol_notes: val("reviewProtocolNotes"),
    review_records_identified: numberOrNull("reviewRecordsIdentified"), review_duplicates_removed: numberOrNull("reviewDuplicatesRemoved"),
    review_records_screened: numberOrNull("reviewRecordsScreened"), review_records_excluded: numberOrNull("reviewRecordsExcluded"),
    review_full_text_assessed: numberOrNull("reviewFullTextAssessed"), review_full_text_excluded: numberOrNull("reviewFullTextExcluded"),
    review_citation_tracking_additions: numberOrNull("reviewCitationTrackingAdditions"), review_final_corpus_size: numberOrNull("reviewFinalCorpusSize"),
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
  updateLengthPlanSummary();
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
  const tokenEstimate = result.token_budget_estimate || {};
  const tokenNote = tokenEstimate.estimated_total_tokens ? ` Estimated drafting tokens: about ${Number(tokenEstimate.estimated_total_tokens).toLocaleString()} across ${tokenEstimate.drafting_passes || 1} pass(es).` : "";
  const batchNote = result.batch_drafting_applied ? " Batch drafting was applied for this long manuscript." : "";
  const density = result.citation_density_report || {};
  const densityValue = Number(density.citation_occurrences_per_1000_words || 0);
  const densityNote = density.word_count ? ` Citation density: ${densityValue.toFixed(1)} per 1,000 words, minimum ${Number(density.minimum_target || 0)}, preferred ${Number(density.preferred_target || 0)}.` : "";
  const humanizer = result.humanizer_report || {};
  const humanizerNote = humanizer.mode ? ` Humanizer: ${esc(humanizer.mode)}${humanizer.model_pass_applied ? " with preservation-gated model pass" : ""}.` : "";
  $("draftSourceSummary").innerHTML = sources.length ? `<strong>${sources.length} source records supplied to the drafting workflow.</strong> ${attachedCount} came from the pre-draft attached bank and ${automaticCount} were found automatically. This doesn’t mean every record was cited.${tokenNote}${batchNote}${densityNote}${humanizerNote}` : `No source records were supplied to this draft.${tokenNote}${batchNote}${densityNote}${humanizerNote}`;
  $("sources").innerHTML = sources.length ? sources.map((src, index) => sourceCard(src, index, false)).join("") : `<p class="muted">No source records were available.</p>`;
}

async function findSources() {
  const searchContext = [val("sourceSearchQuery"), val("articleTitle"), val("researchArea"), val("extractionFocus")].join(" ").trim();
  if (!searchContext) { $("sourceStatus").textContent = "Enter an article title, research area, development focus or search terms first."; return; }
  $("findSourcesBtn").disabled = true;
  $("sourceStatus").textContent = "Searching scholarly metadata and attaching relevant records...";
  try {
    const searchOptions = {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(sourceSearchPayload())};
    const response = window.ArticleReadyPayments ? await ArticleReadyPayments.authorisedFetch("/api/articles/find-sources", searchOptions) : await fetch("/api/articles/find-sources", searchOptions);
    const body = await readApiResponse(response);
    if (!response.ok) throw new Error(apiErrorMessage(body.detail ?? body, response.statusText || `Request failed (${response.status})`));
    latestSourceSearchResult = body;
    attachedSourceBank = mergeSourceBank(attachedSourceBank, body.source_bank || body.sources || []);
    persistSources(); renderAttachedSummary(); renderLatestSearch(body);
    const warnings = (body.provider_errors || []).length;
    const excluded = Number(body.excluded_retracted_count || 0);
    $("sourceStatus").textContent = `Attached ${body.source_bank_count || body.count || 0} record(s). The bank now contains ${attachedSourceBank.length}. ${excluded ? `${excluded} unsafe record(s) were excluded. ` : ""}${warnings ? `${warnings} provider(s) could not be reached.` : ""}`;
  } catch (error) { $("sourceStatus").textContent = `Source search error: ${apiErrorMessage(error, "Source search failed.")}`; }
  finally { $("findSourcesBtn").disabled = false; }
}

async function findResources() {
  if (!val("articleTitle") && !val("researchArea")) { $("resourceStatus").textContent = "Enter the article title or research area first."; return; }
  $("findResourcesBtn").disabled = true;
  $("resourceStatus").textContent = "Searching for possible data sources and instrument records...";
  try {
    const response = await fetch("/api/articles/research-resources", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(researchResourcePayload())});
    const body = await readApiResponse(response);
    if (!response.ok) throw new Error(apiErrorMessage(body.detail ?? body, response.statusText || `Request failed (${response.status})`));
    renderResearchResources(body);
    const warnings = (body.provider_errors || []).length;
    $("resourceStatus").textContent = `Resource guidance generated for ${body.research_route_label || body.research_route}. ${warnings ? `${warnings} scholarly provider warning(s) occurred.` : "Verify access, permission and fit before use."}`;
  } catch (error) { $("resourceStatus").textContent = `Resource search error: ${apiErrorMessage(error, "Research-resource search failed.")}`; }
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
    const body = await readApiResponse(response);
    if (!response.ok) throw new Error(`${file.name}: ${apiErrorMessage(body.detail ?? body, response.statusText || `Request failed (${response.status})`)}`);
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
  $("copyReviewProtocolBtn").disabled = true; $("downloadReviewProtocolBtn").disabled = true;
  try {
    const planKey = window.ArticleReadyPayments ? ArticleReadyPayments.selectedDraftPlan() : '';
    const headers = {"Content-Type":"application/json", ...(window.ArticleReadyPayments ? ArticleReadyPayments.paymentHeaders(planKey) : {})};
    const response = window.ArticleReadyPayments
      ? await ArticleReadyPayments.authorisedFetch("/api/articles/draft", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload())}, planKey)
      : await fetch("/api/articles/draft", {method:"POST", headers, body:JSON.stringify(payload())});
    const body = await readApiResponse(response);
    if (response.status === 402 && window.ArticleReadyPayments) { ArticleReadyPayments.openFromApi(body.detail || {}); return; }
    if (!response.ok) throw new Error(apiErrorMessage(body.detail ?? body, response.statusText || `Request failed (${response.status})`));
    lastText = body.article_text || "";
    lastInstrumentText = body.instrument_text || "";
    lastReviewProtocolText = body.review_protocol_text || "";
    $("articleOutput").value = lastText;
    $("instrumentOutput").value = lastInstrumentText;
    $("instrumentOutputPanel").hidden = !lastInstrumentText;
    $("reviewProtocolOutput").value = lastReviewProtocolText;
    $("reviewProtocolOutputPanel").hidden = !lastReviewProtocolText;
    $("copyReviewProtocolBtn").disabled = !lastReviewProtocolText;
    $("downloadReviewProtocolBtn").disabled = !lastReviewProtocolText;
    if (body.research_resources) renderResearchResources(body.research_resources);
    renderDraftSources(body);
    const warnings = (body.provider_errors || []).length;
    const completionMessage = body.draft_stage === "initial_to_methods"
      ? "Stage 1 completed. The article draft is prepared through the Methods section."
      : body.draft_stage === "continuation_after_results"
        ? "Stage 2 completed. The full article draft is ready."
        : "Article draft completed.";
    const protocolAudit = body.review_protocol_audit || {};
    const protocolNote = protocolAudit.enabled
      ? ` Review protocol audit: ${protocolAudit.complete ? "complete" : `${(protocolAudit.missing_items || []).length} missing item(s) and ${(protocolAudit.flow_warnings || []).length} count warning(s)`}.`
      : "";
    $("status").textContent = `${completionMessage} ${warnings ? `Review ${warnings} warning(s).` : "Review all red author-action items, citations and evidence."}${protocolNote}`;
    $("copyBtn").disabled = !lastText; $("downloadBtn").disabled = !lastText;
  } catch (error) { $("status").textContent = `Error: ${apiErrorMessage(error, "Article drafting failed.")}`; }
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
    const planKey = window.ArticleReadyPayments ? ArticleReadyPayments.selectedDraftPlan() : '';
    const headers = {"Content-Type":"application/json", ...(window.ArticleReadyPayments ? ArticleReadyPayments.paymentHeaders(planKey) : {})};
    const response = await fetch("/api/articles/export", {method:"POST", headers, body:JSON.stringify({article_title:title, article_text:text})});
    if (response.status === 402 && window.ArticleReadyPayments) { const data = await readApiResponse(response); ArticleReadyPayments.openFromApi(data.detail || {}); return; }
    if (!response.ok) { const data = await readApiResponse(response); throw new Error(apiErrorMessage(data.detail ?? data, response.statusText || `Request failed (${response.status})`)); }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url); $("status").textContent = "DOCX downloaded.";
  } catch (error) { $("status").textContent = `Export error: ${apiErrorMessage(error, "Article export failed.")}`; }
}

function clearAll() {
  $("articleForm").reset(); $("wordLimit").value = "7000-9000"; $("targetWordCount").value = "8000"; $("longWriteMode").value = "auto"; $("humanizerMode").value = "balanced"; $("articleStructure").value = ""; $("draftStage").value = "full_article"; $("academicLevel").value = "Research Masters (e.g. MPhil)"; $("researchRoute").value = "Auto";
  $("articleOutput").value = ""; $("instrumentOutput").value = ""; $("instrumentOutputPanel").hidden = true; $("reviewProtocolOutput").value = ""; $("reviewProtocolOutputPanel").hidden = true; $("instrumentRequirementsLabel").hidden = true; $("filters").innerHTML = ""; $("sources").innerHTML = ""; $("draftSourceSummary").innerHTML = ""; $("status").textContent = "";
  $("copyBtn").disabled = true; $("downloadBtn").disabled = true; $("copyReviewProtocolBtn").disabled = true; $("downloadReviewProtocolBtn").disabled = true; lastText = ""; lastInstrumentText = ""; lastReviewProtocolText = ""; latestResearchResources = null; renderResearchResources(null); clearAttachedSources(); applyWorkflowState(false, false);
}

window.addEventListener("DOMContentLoaded", () => {
  restoreSources(); renderAttachedSummary(); renderLatestSearch(latestSourceSearchResult); renderResearchResources(null); applyWorkflowState(false, false); importReviewWorkspacePayload();
  $("sourceMode").addEventListener("change", () => applyWorkflowState(true, false));
  $("articleType").addEventListener("change", () => { applyWorkflowState(false, true); markResourcesStale(); });
  $("draftStage").addEventListener("change", () => applyWorkflowState(false, false));
  $("researchRoute").addEventListener("change", () => { $("resourceRouteBadge").textContent = val("researchRoute"); markResourcesStale(); });
  $("includeInstrumentDraft").addEventListener("change", () => { $("instrumentRequirementsLabel").hidden = !$("includeInstrumentDraft").checked; });
  ["articleTitle", "researchArea", "context", "objectives", "variablesConstructs", "methodology", "extractionFocus"].forEach(id => $(id).addEventListener("input", markResourcesStale));
  ["wordLimit", "targetWordCount", "longWriteMode", "articleStructure"].forEach(id => $(id)?.addEventListener("input", updateLengthPlanSummary));
  $("longWriteMode")?.addEventListener("change", updateLengthPlanSummary);
  $("articleForm").addEventListener("submit", draft);
  $("findSourcesBtn").addEventListener("click", findSources);
  $("clearSourcesBtn").addEventListener("click", clearAttachedSources);
  $("findResourcesBtn").addEventListener("click", findResources);
  $("extractPreviousBtn").addEventListener("click", async () => { try { await extractFiles("previousSectionsFiles", "previousSections", "previous-section"); } catch (error) { $("uploadStatus").textContent = `Upload error: ${apiErrorMessage(error, "File extraction failed.")}`; } });
  $("extractResultsBtn").addEventListener("click", async () => { try { await extractFiles("resultsFiles", "continuationMaterial", "results or analysis"); } catch (error) { $("uploadStatus").textContent = `Upload error: ${apiErrorMessage(error, "File extraction failed.")}`; } });
  $("copyBtn").addEventListener("click", () => copyContent($("articleOutput").value || lastText, "Article draft"));
  $("downloadBtn").addEventListener("click", () => downloadContent($("articleOutput").value || lastText, val("articleTitle") || "Journal Article Draft", "journal_article_draft.docx"));
  $("copyInstrumentBtn").addEventListener("click", () => copyContent($("instrumentOutput").value || lastInstrumentText, "Instrument draft"));
  $("downloadInstrumentBtn").addEventListener("click", () => downloadContent($("instrumentOutput").value || lastInstrumentText, `${val("articleTitle") || "Article"} Instrument`, "article_instrument_draft.docx"));
  $("copyReviewProtocolBtn").addEventListener("click", () => copyContent($("reviewProtocolOutput").value || lastReviewProtocolText, "Review protocol"));
  $("downloadReviewProtocolBtn").addEventListener("click", () => downloadContent($("reviewProtocolOutput").value || lastReviewProtocolText, `${val("articleTitle") || "Article"} Review Protocol and Evidence Audit`, "review_protocol_evidence_audit.docx"));
  $("clearBtn").addEventListener("click", clearAll);
});
