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

const byId = (id) => document.getElementById(id);

const form = byId('revisionForm');
const articleText = byId('articleText');
const reviewComments = byId('reviewComments');
const revisedArticle = byId('revisedArticle');
const revisionReport = byId('revisionReport');
const reviewerMatrix = byId('reviewerMatrix');
const reviewerMatrixPanel = byId('reviewerMatrixPanel');
const statusBox = byId('status');
const uploadStatus = byId('uploadStatus');
const reviseBtn = byId('reviseBtn');
const copyArticleBtn = byId('copyArticleBtn');
const copyReportBtn = byId('copyReportBtn');
const copyMatrixBtn = byId('copyMatrixBtn');
const downloadRevisionBtn = byId('downloadRevisionBtn');
const revisionMeta = byId('revisionMeta');

let lastResult = null;

function message(text, kind = '') {
  statusBox.textContent = text || '';
  statusBox.className = `status ${kind}`.trim();
}

function setBusy(busy) {
  reviseBtn.disabled = busy;
  reviseBtn.textContent = busy ? 'Revising article…' : 'Revise and polish article';
}

async function extractFile(fileInput, target, label) {
  const file = fileInput.files && fileInput.files[0];
  if (!file) {
    uploadStatus.textContent = `Choose a ${label} file first.`;
    return;
  }
  const body = new FormData();
  body.append('file', file);
  uploadStatus.textContent = `Extracting ${file.name}…`;
  try {
    const response = await fetch('/api/articles/extract-file', { method: 'POST', body });
    const data = await readApiResponse(response);
    if (!response.ok) throw new Error(apiErrorMessage(data.detail ?? data, 'File extraction failed.'));
    target.value = target.value.trim() ? `${target.value.trim()}\n\n${data.text}` : data.text;
    uploadStatus.textContent = `${file.name} extracted, ${Number(data.character_count || 0).toLocaleString()} characters${data.truncated ? ', truncated to the extraction limit' : ''}.`;
  } catch (error) {
    uploadStatus.textContent = apiErrorMessage(error, 'File extraction failed.');
  }
}

byId('extractArticleBtn').addEventListener('click', () => extractFile(byId('articleFile'), articleText, 'manuscript'));
byId('extractCommentsBtn').addEventListener('click', () => extractFile(byId('commentsFile'), reviewComments, 'review-comment'));

function payloadFromForm() {
  return {
    article_title: byId('articleTitle').value.trim(),
    article_text: articleText.value.trim(),
    review_comments: reviewComments.value.trim(),
    target_journal: byId('targetJournal').value.trim(),
    journal_scope: byId('journalScope').value.trim(),
    author_guidelines: byId('authorGuidelines').value.trim(),
    article_type: byId('articleType').value,
    citation_style: byId('citationStyle').value,
    humanizer_mode: byId('humanizerMode').value || 'balanced',
    word_limit: byId('wordLimit').value.trim(),
    research_area: byId('researchArea').value.trim(),
    context: byId('context').value.trim(),
    methodology: byId('methodology').value.trim(),
    data_and_results: byId('dataResults').value.trim(),
    contribution_claim: byId('contributionClaim').value.trim(),
    revision_level: byId('revisionLevel').value,
    revision_goals: byId('revisionGoals').value.trim(),
    academic_level: 'PhD',
    strengthen_conceptualisation: byId('strengthenConceptualisation').checked,
    strengthen_contribution: byId('strengthenContribution').checked,
    assess_method_fit: byId('assessMethodFit').checked,
    assess_analysis: byId('assessAnalysis').checked,
    deepen_discussion: byId('deepenDiscussion').checked,
    strengthen_recommendations: byId('strengthenRecommendations').checked,
    include_reviewer_response_matrix: byId('includeResponseMatrix').checked,
    include_source_search: byId('includeSourceSearch').checked,
    include_older_foundational: byId('includeOlderFoundational').checked,
    source_search_terms: byId('sourceSearchTerms').value.trim(),
    source_bank: [],
  };
}

function enableOutputs(enabled) {
  copyArticleBtn.disabled = !enabled;
  copyReportBtn.disabled = !enabled;
  downloadRevisionBtn.disabled = !enabled;
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = payloadFromForm();
  if (!payload.article_title || payload.article_text.length < 100) {
    message('Provide an article title and paste or upload the existing article.', 'error');
    return;
  }
  setBusy(true);
  enableOutputs(false);
  copyMatrixBtn.disabled = true;
  message('Revising the manuscript and assessing publication readiness…');
  try {
    const planKey = window.ArticleReadyPayments ? ArticleReadyPayments.selectedRevisionPlan() : '';
    const requestOptions = {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)};
    const response = window.ArticleReadyPayments
      ? await ArticleReadyPayments.authorisedFetch('/api/articles/revise', requestOptions, planKey)
      : await fetch('/api/articles/revise', requestOptions);
    const data = await readApiResponse(response);
    if (response.status === 402 && window.ArticleReadyPayments) { ArticleReadyPayments.openFromApi(data.detail || {}); return; }
    if (!response.ok) throw new Error(apiErrorMessage(data.detail ?? data, 'Article revision failed.'));
    lastResult = data;
    revisedArticle.value = data.revised_article_text || '';
    revisionReport.value = data.revision_report || '';
    reviewerMatrix.value = data.reviewer_response_matrix || '';
    reviewerMatrixPanel.hidden = !reviewerMatrix.value.trim();
    copyMatrixBtn.disabled = reviewerMatrixPanel.hidden;
    const sourceCount = Number(data.source_bank_count || 0);
    const errors = Array.isArray(data.provider_errors) ? data.provider_errors.filter(Boolean) : [];
    const density = data.citation_density_report || {};
    const densityNote = density.word_count ? ` Citation density: ${Number(density.citation_occurrences_per_1000_words || 0).toFixed(1)} per 1,000 words, minimum ${Number(density.minimum_target || 0)}, preferred ${Number(density.preferred_target || 0)}.` : '';
    const humanizer = data.humanizer_report || {};
    const humanizerNote = humanizer.mode ? ` Humanizer: ${humanizer.mode}${humanizer.model_pass_applied ? ' with preservation-gated model pass' : ''}.` : '';
    revisionMeta.innerHTML = `<strong>${data.mode === 'ai_revision' ? 'Revision completed' : 'Fallback output returned'}.</strong> ${sourceCount} scholarly record(s) passed to the revision workflow.${densityNote}${humanizerNote} ${data.revision_colour_note || ''}`;
    enableOutputs(Boolean(revisedArticle.value.trim()));
    message(errors.length ? `Revision completed with ${errors.length} provider warning(s). Review the report before using the manuscript.` : 'Revision completed. Review the manuscript, report and any suggested analyses before downloading.');
  } catch (error) {
    message(apiErrorMessage(error, 'Article revision failed.'), 'error');
  } finally {
    setBusy(false);
  }
});

async function copyText(value, successMessage) {
  if (!value.trim()) return;
  try {
    await navigator.clipboard.writeText(value);
    message(successMessage);
  } catch (_error) {
    message('Copying was blocked by the browser. Select the text and copy it manually.', 'error');
  }
}

copyArticleBtn.addEventListener('click', () => copyText(revisedArticle.value, 'Revised article copied.'));
copyReportBtn.addEventListener('click', () => copyText(revisionReport.value, 'Revision report copied.'));
copyMatrixBtn.addEventListener('click', () => copyText(reviewerMatrix.value, 'Reviewer response matrix copied.'));

downloadRevisionBtn.addEventListener('click', async () => {
  if (!lastResult || !revisedArticle.value.trim()) return;
  message('Preparing the DOCX with revisions shown in blue…');
  downloadRevisionBtn.disabled = true;
  try {
    const planKey = window.ArticleReadyPayments ? ArticleReadyPayments.selectedRevisionPlan() : '';
    const response = await fetch('/api/articles/revision/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(window.ArticleReadyPayments ? ArticleReadyPayments.paymentHeaders(planKey) : {}) },
      body: JSON.stringify({
        article_title: byId('articleTitle').value.trim() || 'Revised Journal Article',
        original_article_text: articleText.value.trim(),
        revised_article_text: revisedArticle.value,
        revision_report: revisionReport.value,
        reviewer_response_matrix: reviewerMatrix.value,
        include_revision_report: true,
      }),
    });
    if (response.status === 402 && window.ArticleReadyPayments) {
      const data = await readApiResponse(response);
      ArticleReadyPayments.openFromApi(data.detail || {});
      return;
    }
    if (!response.ok) {
      const data = await readApiResponse(response);
      throw new Error(apiErrorMessage(data.detail ?? data, 'Revision export failed.')); 
    }
    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^";]+)"?/i);
    const filename = match ? match[1] : 'articleready_polished_revision_blue.docx';
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    message('DOCX downloaded. Added or changed wording is blue, while exact unchanged wording remains black.');
  } catch (error) {
    message(apiErrorMessage(error, 'Revision export failed.'), 'error');
  } finally {
    downloadRevisionBtn.disabled = false;
  }
});

byId('clearBtn').addEventListener('click', () => {
  form.reset();
  articleText.value = '';
  reviewComments.value = '';
  revisedArticle.value = '';
  revisionReport.value = '';
  reviewerMatrix.value = '';
  reviewerMatrixPanel.hidden = true;
  lastResult = null;
  revisionMeta.textContent = 'Revision details will appear here.';
  uploadStatus.textContent = '';
  message('');
  enableOutputs(false);
  copyMatrixBtn.disabled = true;
  byId('revisionLevel').value = 'Publication-readiness overhaul';
  byId('humanizerMode').value = 'balanced';
  ['strengthenConceptualisation', 'strengthenContribution', 'assessMethodFit', 'assessAnalysis', 'deepenDiscussion', 'strengthenRecommendations', 'includeResponseMatrix', 'includeSourceSearch', 'includeOlderFoundational'].forEach((id) => { byId(id).checked = true; });
});
