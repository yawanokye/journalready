(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  const REGISTRY_KEY = 'articleready_review_workspace_registry_v1';
  const WRITER_PAYLOAD_KEY = 'articleready_review_workspace_payload_v1';
  const PAGE_SIZE = 100;

  let registry = [];
  let active = null;
  let project = null;
  let records = [];
  let offset = 0;
  let total = 0;
  let selected = new Set();
  let currentRecord = null;

  function errorMessage(value, fallback = 'The request could not be completed.') {
    if (value instanceof Error) return value.message || fallback;
    if (Array.isArray(value)) return value.map((item) => errorMessage(item, '')).filter(Boolean).join('; ') || fallback;
    if (value && typeof value === 'object') {
      for (const key of ['detail', 'message', 'error', 'reason', 'description']) {
        if (value[key] != null) {
          const message = errorMessage(value[key], '');
          if (message) return message;
        }
      }
      try { const text = JSON.stringify(value); if (text !== '{}') return text; } catch (_) {}
    }
    const text = String(value || '').trim();
    return text && text !== '[object Object]' ? text : fallback;
  }

  async function readResponse(response) {
    const text = await response.text();
    if (!text) return {};
    try { return JSON.parse(text); } catch (_) { return {detail: text}; }
  }

  function headers(json = false) {
    const output = {'X-Review-Workspace-Token': active?.token || ''};
    if (json) output['Content-Type'] = 'application/json';
    return output;
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {...options, headers: {...headers(Boolean(options.body && !(options.body instanceof FormData))), ...(options.headers || {})}});
    const data = await readResponse(response);
    if (!response.ok) throw new Error(errorMessage(data, `Request failed (${response.status})`));
    return data;
  }

  function saveRegistry() {
    localStorage.setItem(REGISTRY_KEY, JSON.stringify(registry));
  }

  function loadRegistry() {
    try {
      const value = JSON.parse(localStorage.getItem(REGISTRY_KEY) || '[]');
      registry = Array.isArray(value) ? value.filter((item) => item?.id && item?.token) : [];
    } catch (_) { registry = []; }
  }

  function renderProjectSelector() {
    const selector = $('projectSelector');
    selector.innerHTML = '<option value="">Create or select a workspace</option>';
    for (const item of registry) {
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = item.title || 'Untitled review workspace';
      if (active?.id === item.id) option.selected = true;
      selector.appendChild(option);
    }
    $('exportAccessBtn').disabled = !active;
  }

  function setStatus(message, isError = false) {
    $('globalStatus').textContent = message || '';
    $('globalStatus').classList.toggle('error', isError);
  }

  function projectPayload() {
    return {
      title: $('projectTitle').value.trim(),
      article_type: $('projectArticleType').value,
      review_question: $('projectQuestion').value.trim(),
      protocol_positioning: $('projectPositioning').value,
      eligibility_criteria: $('projectEligibility').value.trim(),
      screening_process: $('projectScreening').value.trim(),
      quality_appraisal: $('projectQuality').value.trim(),
      synthesis_method: $('projectSynthesis').value.trim(),
      software: $('projectSoftware').value.trim(),
      notes: $('projectNotes').value.trim()
    };
  }

  function populateProject(data) {
    $('projectTitle').value = data.title || '';
    $('projectArticleType').value = data.article_type || 'Systematic review';
    $('projectQuestion').value = data.review_question || '';
    $('projectPositioning').value = data.protocol_positioning || 'Auto';
    $('projectEligibility').value = data.eligibility_criteria || '';
    $('projectScreening').value = data.screening_process || '';
    $('projectQuality').value = data.quality_appraisal || '';
    $('projectSynthesis').value = data.synthesis_method || '';
    $('projectSoftware').value = data.software || '';
    $('projectNotes').value = data.notes || '';
  }

  function renderSummary(summary = {}) {
    const unresolved = Number(summary.possible_duplicates || 0) + Number(summary.awaiting_title_abstract || 0) + Number(summary.awaiting_full_text || 0);
    $('sumIdentified').textContent = summary.records_identified || 0;
    $('sumDuplicates').textContent = summary.duplicates_removed || 0;
    $('sumScreened').textContent = summary.records_screened || 0;
    $('sumFullText').textContent = summary.full_text_assessed || 0;
    $('sumIncluded').textContent = summary.final_corpus || 0;
    $('sumUnresolved').textContent = unresolved;
    $('flowDatabase').textContent = summary.database_records_identified || 0;
    $('flowOther').textContent = summary.other_records_identified || 0;
    $('flowDuplicates').textContent = summary.duplicates_removed || 0;
    $('flowScreened').textContent = summary.records_screened || 0;
    $('flowTAExcluded').textContent = summary.records_excluded || 0;
    $('flowFullText').textContent = summary.full_text_assessed || 0;
    $('flowFTExcluded').textContent = summary.full_text_excluded || 0;
    $('flowNotRetrieved').textContent = summary.reports_not_retrieved || 0;
    $('flowIncluded').textContent = summary.final_corpus || 0;
    const warnings = summary.warnings || [];
    $('summaryWarnings').innerHTML = warnings.length
      ? warnings.map((item) => `<p class="warning">${esc(item)}</p>`).join('')
      : '<p class="attached-summary">No unresolved duplicate or screening-stage warnings.</p>';
  }

  function renderSearchRuns(runs = []) {
    $('searchRunList').innerHTML = runs.length ? runs.map((run) => `
      <article class="search-run-card">
        <div class="source-title-line"><strong>${esc(run.database_name)}</strong><span class="source-origin">${esc(String(run.source_route || '').replaceAll('_', ' '))}</span></div>
        <p><strong>Search date:</strong> ${esc(run.search_date || 'Not recorded')} · <strong>Imported:</strong> ${esc(run.imported_record_count || 0)}${run.reported_result_count == null ? '' : ` · <strong>Reported by source:</strong> ${esc(run.reported_result_count)}`}</p>
        ${run.search_string ? `<details><summary>Search string</summary><pre class="search-string-preview">${esc(run.search_string)}</pre></details>` : ''}
        <p class="muted">${esc([run.date_limits, run.language_limits, run.document_types].filter(Boolean).join(' · ') || 'No limits recorded.')}</p>
      </article>`).join('') : '<p class="muted">No search run has been registered.</p>';
  }

  function decisionLabel(value) {
    return ({not_screened:'Not screened', not_assessed:'Not assessed', include:'Include', exclude:'Exclude', uncertain:'Uncertain', not_retrieved:'Not retrieved'})[value] || value || 'Not recorded';
  }

  function duplicateLabel(record) {
    if (record.duplicate_of) return '<span class="decision-badge duplicate">Confirmed duplicate</span>';
    if (record.duplicate_candidate_of) return `<span class="decision-badge possible">Possible duplicate ${record.duplicate_confidence ? `(${Math.round(Number(record.duplicate_confidence) * 100)}%)` : ''}</span>`;
    return '<span class="decision-badge unique">Unique</span>';
  }

  function renderRecords() {
    const body = $('recordTableBody');
    if (!records.length) {
      body.innerHTML = '<tr><td colspan="7" class="muted">No records match the selected filter.</td></tr>';
    } else {
      body.innerHTML = records.map((record) => `
        <tr class="${record.duplicate_of ? 'duplicate-row' : ''}">
          <td><input class="record-select" type="checkbox" data-record-id="${esc(record.id)}" ${selected.has(record.id) ? 'checked' : ''} ${record.duplicate_of ? 'disabled' : ''}></td>
          <td><button type="button" class="record-title-button" data-review-id="${esc(record.id)}">${esc(record.title)}</button><div class="record-meta">${esc(record.authors || 'Authors not supplied')} ${record.publication_year ? `(${esc(record.publication_year)})` : ''}${record.doi ? ` · DOI ${esc(record.doi)}` : ''}</div></td>
          <td>${esc(record.source_database || '')}<div class="record-meta">${esc(String(record.source_route || '').replaceAll('_', ' '))}</div></td>
          <td>${duplicateLabel(record)}</td>
          <td><span class="decision-badge ${esc(record.title_abstract_decision)}">${esc(decisionLabel(record.title_abstract_decision))}</span>${record.title_abstract_reason ? `<div class="record-meta">${esc(record.title_abstract_reason)}</div>` : ''}</td>
          <td><span class="decision-badge ${esc(record.full_text_decision)}">${esc(decisionLabel(record.full_text_decision))}</span>${record.has_full_text ? '<div class="record-meta">Full text attached</div>' : ''}${record.full_text_reason ? `<div class="record-meta">${esc(record.full_text_reason)}</div>` : ''}</td>
          <td><button type="button" class="secondary compact-row-button" data-review-id="${esc(record.id)}">Review</button></td>
        </tr>`).join('');
    }
    document.querySelectorAll('.record-select').forEach((input) => input.addEventListener('change', () => {
      if (input.checked) selected.add(input.dataset.recordId); else selected.delete(input.dataset.recordId);
    }));
    document.querySelectorAll('[data-review-id]').forEach((button) => button.addEventListener('click', () => openRecord(button.dataset.reviewId)));
    const start = total ? offset + 1 : 0;
    const end = Math.min(offset + PAGE_SIZE, total);
    $('recordPageInfo').textContent = `${start}-${end} of ${total} record(s)`;
    $('previousPageBtn').disabled = offset === 0;
    $('nextPageBtn').disabled = offset + PAGE_SIZE >= total;
  }

  async function loadProject() {
    if (!active) return;
    setStatus('Loading review workspace...');
    try {
      project = await api(`/api/review-workspace/projects/${active.id}`);
      active.title = project.title;
      const item = registry.find((entry) => entry.id === active.id);
      if (item) item.title = project.title;
      saveRegistry();
      renderProjectSelector();
      populateProject(project);
      renderSummary(project.summary);
      renderSearchRuns(project.search_runs);
      $('createProjectPanel').hidden = true;
      $('workspacePanel').hidden = false;
      offset = 0;
      await loadRecords();
      setStatus('Review workspace ready.');
    } catch (error) {
      setStatus(errorMessage(error), true);
      $('workspacePanel').hidden = true;
      $('createProjectPanel').hidden = false;
    }
  }

  async function loadRecords() {
    if (!active) return;
    const params = new URLSearchParams({
      stage: $('recordStage').value,
      search: $('recordSearch').value.trim(),
      limit: String(PAGE_SIZE),
      offset: String(offset)
    });
    const data = await api(`/api/review-workspace/projects/${active.id}/records?${params}`);
    records = data.records || [];
    total = Number(data.total || 0);
    renderRecords();
  }

  async function refreshSummary() {
    if (!active) return;
    const summary = await api(`/api/review-workspace/projects/${active.id}/summary`);
    renderSummary(summary);
    if (project) project.summary = summary;
  }

  async function openRecord(recordId) {
    try {
      currentRecord = await api(`/api/review-workspace/projects/${active.id}/records/${recordId}`);
      $('recordDetailCard').hidden = false;
      $('detailTitle').textContent = currentRecord.title || '';
      $('detailAuthors').textContent = [currentRecord.authors, currentRecord.publication_year, currentRecord.doi].filter(Boolean).join(' · ');
      $('detailSource').textContent = [currentRecord.source_database, String(currentRecord.source_route || '').replaceAll('_', ' ')].filter(Boolean).join(' · ');
      $('detailAbstract').textContent = currentRecord.abstract || 'No abstract was supplied in the imported record.';
      $('detailTADecision').value = currentRecord.title_abstract_decision || 'not_screened';
      $('detailTAReason').value = currentRecord.title_abstract_reason || '';
      $('detailFTDecision').value = currentRecord.full_text_decision || 'not_assessed';
      $('detailFTReason').value = currentRecord.full_text_reason || '';
      $('detailNotes').value = currentRecord.reviewer_notes || '';
      $('detailFullTextStatus').textContent = currentRecord.full_text_filename ? `Attached: ${currentRecord.full_text_filename}` : 'No full text attached.';
      const excerpt = currentRecord.full_text_excerpt || '';
      $('fullTextPreviewPanel').hidden = !excerpt;
      $('fullTextPreview').textContent = excerpt;
      $('duplicateDecisionPanel').hidden = !currentRecord.duplicate_candidate_of;
      $('duplicateMessage').textContent = currentRecord.duplicate_candidate_of
        ? `This record is a ${Math.round(Number(currentRecord.duplicate_confidence || 0) * 100)}% title match to an existing record. Confirm it as a duplicate or keep it as unique.`
        : '';
      $('detailStatus').textContent = '';
      $('recordDetailCard').scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (error) { setStatus(errorMessage(error), true); }
  }

  async function download(path, fallbackName) {
    const response = await fetch(path, {headers: headers(false)});
    if (!response.ok) {
      const data = await readResponse(response);
      throw new Error(errorMessage(data));
    }
    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^";]+)"?/i);
    const name = match?.[1] || fallbackName;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = name; document.body.appendChild(anchor); anchor.click(); anchor.remove();
    URL.revokeObjectURL(url);
  }

  $('createProjectForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    setStatus('Creating review workspace...');
    try {
      const data = await api('/api/review-workspace/projects', {
        method: 'POST',
        body: JSON.stringify({
          title: $('newProjectTitle').value.trim(),
          article_type: $('newProjectType').value,
          review_question: $('newProjectQuestion').value.trim()
        })
      });
      active = {id: data.id, token: data.access_token, title: data.title};
      registry = registry.filter((item) => item.id !== active.id);
      registry.unshift(active);
      saveRegistry();
      renderProjectSelector();
      $('createProjectForm').reset();
      await loadProject();
    } catch (error) { setStatus(errorMessage(error), true); }
  });

  $('projectForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    setStatus('Saving review design...');
    try {
      project = await api(`/api/review-workspace/projects/${active.id}`, {method: 'PATCH', body: JSON.stringify(projectPayload())});
      populateProject(project);
      renderSummary(project.summary);
      renderSearchRuns(project.search_runs);
      active.title = project.title;
      const item = registry.find((entry) => entry.id === active.id); if (item) item.title = project.title;
      saveRegistry(); renderProjectSelector();
      setStatus('Review design saved.');
    } catch (error) { setStatus(errorMessage(error), true); }
  });

  $('importForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const file = $('importFile').files[0];
    if (!file) { $('importStatus').textContent = 'Select a database export file.'; return; }
    $('importBtn').disabled = true;
    $('importStatus').textContent = 'Importing records and checking exact and possible duplicates...';
    const form = new FormData();
    form.append('file', file);
    form.append('database_name', $('importDatabase').value.trim());
    form.append('platform', $('importPlatform').value.trim());
    form.append('source_route', $('importRoute').value);
    form.append('search_string', $('importSearchString').value.trim());
    form.append('search_date', $('importSearchDate').value);
    form.append('date_limits', $('importDateLimits').value.trim());
    form.append('language_limits', $('importLanguageLimits').value.trim());
    form.append('document_types', $('importDocumentTypes').value.trim());
    form.append('reported_result_count', $('importReportedCount').value);
    form.append('notes', $('importNotes').value.trim());
    try {
      const response = await fetch(`/api/review-workspace/projects/${active.id}/imports`, {method: 'POST', headers: headers(false), body: form});
      const data = await readResponse(response);
      if (!response.ok) throw new Error(errorMessage(data));
      $('importStatus').textContent = `${data.records_imported} record(s) imported. ${data.exact_duplicates} exact duplicate(s) and ${data.possible_duplicates} possible duplicate(s) identified.`;
      $('importFile').value = '';
      project = await api(`/api/review-workspace/projects/${active.id}`);
      renderSummary(project.summary); renderSearchRuns(project.search_runs);
      offset = 0; selected.clear(); await loadRecords();
    } catch (error) { $('importStatus').textContent = `Import error: ${errorMessage(error)}`; }
    finally { $('importBtn').disabled = false; }
  });

  $('recordReviewForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!currentRecord) return;
    $('detailStatus').textContent = 'Saving screening decision...';
    try {
      currentRecord = await api(`/api/review-workspace/projects/${active.id}/records/${currentRecord.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          title_abstract_decision: $('detailTADecision').value,
          title_abstract_reason: $('detailTAReason').value.trim(),
          full_text_decision: $('detailFTDecision').value,
          full_text_reason: $('detailFTReason').value.trim(),
          reviewer_notes: $('detailNotes').value.trim()
        })
      });
      $('detailStatus').textContent = 'Screening decision saved.';
      await refreshSummary(); await loadRecords();
    } catch (error) { $('detailStatus').textContent = `Error: ${errorMessage(error)}`; }
  });

  $('uploadFullTextBtn').addEventListener('click', async () => {
    if (!currentRecord) return;
    const file = $('detailFullTextFile').files[0];
    if (!file) { $('detailStatus').textContent = 'Select a full-text file.'; return; }
    $('uploadFullTextBtn').disabled = true;
    $('detailStatus').textContent = 'Extracting and attaching full text...';
    const form = new FormData(); form.append('file', file);
    try {
      const response = await fetch(`/api/review-workspace/projects/${active.id}/records/${currentRecord.id}/full-text`, {method: 'POST', headers: headers(false), body: form});
      const data = await readResponse(response);
      if (!response.ok) throw new Error(errorMessage(data));
      currentRecord = data;
      $('detailFullTextStatus').textContent = `Attached: ${data.full_text_filename}`;
      $('fullTextPreviewPanel').hidden = !data.full_text_excerpt;
      $('fullTextPreview').textContent = data.full_text_excerpt || '';
      $('detailFullTextFile').value = '';
      $('detailStatus').textContent = 'Full text attached.';
      await loadRecords();
    } catch (error) { $('detailStatus').textContent = `Upload error: ${errorMessage(error)}`; }
    finally { $('uploadFullTextBtn').disabled = false; }
  });

  $('confirmDuplicateBtn').addEventListener('click', async () => {
    if (!currentRecord?.duplicate_candidate_of) return;
    try {
      await api(`/api/review-workspace/projects/${active.id}/records/${currentRecord.id}/duplicate`, {method: 'POST', body: JSON.stringify({action: 'confirm', duplicate_of: currentRecord.duplicate_candidate_of})});
      $('recordDetailCard').hidden = true; currentRecord = null;
      await refreshSummary(); await loadRecords();
    } catch (error) { $('detailStatus').textContent = `Error: ${errorMessage(error)}`; }
  });

  $('keepUniqueBtn').addEventListener('click', async () => {
    if (!currentRecord) return;
    try {
      currentRecord = await api(`/api/review-workspace/projects/${active.id}/records/${currentRecord.id}/duplicate`, {method: 'POST', body: JSON.stringify({action: 'keep_unique'})});
      $('duplicateDecisionPanel').hidden = true;
      await refreshSummary(); await loadRecords();
    } catch (error) { $('detailStatus').textContent = `Error: ${errorMessage(error)}`; }
  });

  $('bulkApplyBtn').addEventListener('click', async () => {
    if (!selected.size) { setStatus('Select at least one record.', true); return; }
    try {
      const result = await api(`/api/review-workspace/projects/${active.id}/records/bulk-decision`, {
        method: 'POST',
        body: JSON.stringify({record_ids: Array.from(selected), stage: $('bulkStage').value, decision: $('bulkDecision').value, reason: $('bulkReason').value.trim()})
      });
      selected.clear();
      renderSummary(result.summary);
      await loadRecords();
      setStatus(`${result.updated} record(s) updated.`);
    } catch (error) { setStatus(errorMessage(error), true); }
  });

  $('loadRecordsBtn').addEventListener('click', async () => { offset = 0; selected.clear(); await loadRecords(); });
  $('previousPageBtn').addEventListener('click', async () => { offset = Math.max(0, offset - PAGE_SIZE); await loadRecords(); });
  $('nextPageBtn').addEventListener('click', async () => { offset += PAGE_SIZE; await loadRecords(); });
  $('selectPageBtn').addEventListener('click', () => { records.filter((record) => !record.duplicate_of).forEach((record) => selected.add(record.id)); renderRecords(); });
  $('clearSelectionBtn').addEventListener('click', () => { selected.clear(); renderRecords(); });
  $('selectAllRecords').addEventListener('change', (event) => { records.filter((record) => !record.duplicate_of).forEach((record) => event.target.checked ? selected.add(record.id) : selected.delete(record.id)); renderRecords(); });
  $('closeDetailBtn').addEventListener('click', () => { $('recordDetailCard').hidden = true; currentRecord = null; });

  $('sendToWriterBtn').addEventListener('click', async () => {
    try {
      const payload = await api(`/api/review-workspace/projects/${active.id}/writer-payload`);
      localStorage.setItem(WRITER_PAYLOAD_KEY, JSON.stringify(payload));
      window.location.href = '/article-writer?review_workspace=1';
    } catch (error) { setStatus(errorMessage(error), true); }
  });

  $('exportProtocolBtn').addEventListener('click', async () => { try { await download(`/api/review-workspace/projects/${active.id}/export/protocol.docx`, 'review_protocol_and_evidence_audit.docx'); } catch (error) { setStatus(errorMessage(error), true); } });
  $('exportIncludedBtn').addEventListener('click', async () => { try { await download(`/api/review-workspace/projects/${active.id}/export/records.csv?scope=included`, 'included_corpus.csv'); } catch (error) { setStatus(errorMessage(error), true); } });
  $('exportAllBtn').addEventListener('click', async () => { try { await download(`/api/review-workspace/projects/${active.id}/export/records.csv?scope=all`, 'review_evidence_ledger.csv'); } catch (error) { setStatus(errorMessage(error), true); } });
  $('exportAuditBtn').addEventListener('click', async () => { try { await download(`/api/review-workspace/projects/${active.id}/export/audit.json`, 'review_evidence_audit.json'); } catch (error) { setStatus(errorMessage(error), true); } });

  $('deleteProjectBtn').addEventListener('click', async () => {
    if (!active || !window.confirm('Delete this review workspace and all imported records? This cannot be undone.')) return;
    try {
      await api(`/api/review-workspace/projects/${active.id}`, {method: 'DELETE'});
      registry = registry.filter((item) => item.id !== active.id); saveRegistry(); active = null; project = null;
      renderProjectSelector(); $('workspacePanel').hidden = true; $('createProjectPanel').hidden = false; setStatus('Review workspace deleted.');
    } catch (error) { setStatus(errorMessage(error), true); }
  });

  $('exportAccessBtn').addEventListener('click', () => {
    if (!active) return;
    const payload = {version: 1, project_id: active.id, access_token: active.token, title: active.title || 'Review workspace'};
    const blob = new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = 'articleready_review_workspace_access.json'; document.body.appendChild(anchor); anchor.click(); anchor.remove();
    URL.revokeObjectURL(url);
    setStatus('Workspace access key saved. Keep it private.');
  });

  $('restoreAccessBtn').addEventListener('click', () => $('restoreAccessFile').click());
  $('restoreAccessFile').addEventListener('change', async () => {
    const file = $('restoreAccessFile').files[0];
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      if (!data.project_id || !data.access_token) throw new Error('This is not a valid ArticleReady workspace access file.');
      active = {id: String(data.project_id), token: String(data.access_token), title: String(data.title || 'Restored review workspace')};
      registry = registry.filter((item) => item.id !== active.id);
      registry.unshift(active); saveRegistry(); renderProjectSelector();
      await loadProject();
      setStatus('Workspace access restored on this browser.');
    } catch (error) { setStatus(errorMessage(error, 'Workspace access could not be restored.'), true); }
    finally { $('restoreAccessFile').value = ''; }
  });

  $('projectSelector').addEventListener('change', async () => {
    const item = registry.find((entry) => entry.id === $('projectSelector').value);
    if (!item) { active = null; $('workspacePanel').hidden = true; $('createProjectPanel').hidden = false; return; }
    active = item; selected.clear(); currentRecord = null; await loadProject();
  });

  $('newProjectBtn').addEventListener('click', () => {
    active = null; $('projectSelector').value = ''; $('workspacePanel').hidden = true; $('createProjectPanel').hidden = false; setStatus('Create a new workspace.');
  });

  window.addEventListener('DOMContentLoaded', async () => {
    loadRegistry(); renderProjectSelector();
    const last = registry[0];
    if (last) { active = last; renderProjectSelector(); await loadProject(); }
    else { $('createProjectPanel').hidden = false; $('workspacePanel').hidden = true; }
  });
})();
