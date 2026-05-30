const API = '/api';
let currentJobPage = 0;
let pendingJobId = null;
let pendingAppId = null;
let jobSort = { by: 'discovered_at', dir: 'desc' };
let careerSites = {};  // company name (lowercase) → career homepage URL

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  // Load career sites before rendering jobs so company links are ready
  const sites = await apiFetch('/jobs/career-sites');
  if (sites) careerSites = sites;

  setupTabs();
  markPondViewed(); // opening the app on The Pond counts as viewing it
  loadStats();
  loadJobs();
  loadConfig();
  loadScraperStatus();
  setInterval(loadStats, 30_000);
  setInterval(() => { if (activeTab() === 'board') loadJobs(false); else checkNewJobs(); }, 60_000);
  setInterval(loadScraperStatus, 60_000);
});

function activeTab() {
  return document.querySelector('.tab.active')?.dataset.tab;
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

// ── New-jobs duck badge ───────────────────────────────────────────────────────

function markPondViewed() {
  localStorage.setItem('pondLastViewed', new Date().toISOString());
  document.getElementById('pond-badge').classList.remove('visible');
}

async function checkNewJobs() {
  const badge = document.getElementById('pond-badge');
  if (!badge) return;
  // Don't show badge while user is already on The Pond
  if (activeTab() === 'board') { markPondViewed(); return; }
  const lastViewed = localStorage.getItem('pondLastViewed');
  const data = await apiFetch('/jobs?status=new&limit=1&sort_by=discovered_at&sort_dir=desc');
  if (!data?.jobs?.length) return;
  const newestAt = data.jobs[0].discovered_at;
  if (!newestAt) return;
  if (!lastViewed || newestAt > lastViewed) {
    badge.classList.add('visible');
  }
}

function setupTabs() {
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(s => s.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
      if (btn.dataset.tab === 'board') markPondViewed();
      if (btn.dataset.tab === 'tracker') loadApplications();
      if (btn.dataset.tab === 'resumes') loadResumes();
      if (btn.dataset.tab === 'config') loadConfig();
      if (btn.dataset.tab === 'companies') loadCompanies();
      if (btn.dataset.tab === 'mailbox') loadMailbox();
      if (btn.dataset.tab === 'messages') loadLinkedInMessages();
      if (btn.dataset.tab === 'analysis') loadAnalysis();
    });
  });

  document.getElementById('btn-add-job').addEventListener('click', openAddJobModal);
  document.getElementById('aj-cancel').addEventListener('click', closeAddJobModal);
  document.getElementById('aj-confirm').addEventListener('click', confirmAddJob);
  document.getElementById('btn-refresh').addEventListener('click', () => loadJobs());
  document.getElementById('btn-scrape').addEventListener('click', triggerScrape);
  document.getElementById('search-q').addEventListener('input', debounce(() => loadJobs(), 400));
  document.getElementById('search-loc').addEventListener('input', debounce(() => loadJobs(), 400));
  document.getElementById('filter-status').addEventListener('change', loadApplications);
  document.getElementById('btn-save-config').addEventListener('click', saveConfig);
  setupResumeModal();
  document.getElementById('modal-cancel').addEventListener('click', closeModal);
  document.getElementById('modal-confirm').addEventListener('click', confirmApply);
  document.getElementById('status-modal-cancel').addEventListener('click', closeStatusModal);
  document.getElementById('status-modal-confirm').addEventListener('click', confirmStatusUpdate);
  setupCompanyModal();
  setupFeedbackModal();
  setupPortal();
}

// ── Stats ─────────────────────────────────────────────────────────────────────

async function loadStats() {
  const s = await apiFetch('/stats?period=all_time');
  if (!s) return;
  document.getElementById('stat-discovered').textContent = s.jobs_discovered ?? '—';
  document.getElementById('stat-applied').textContent = s.applications?.applied ?? '—';
  document.getElementById('stat-screening').textContent = s.applications?.phone_screen ?? '—';
  document.getElementById('stat-interview').textContent = s.applications?.interview ?? '—';
  document.getElementById('stat-offer').textContent = s.applications?.offer ?? '—';
  document.getElementById('stat-daily').textContent = (s.daily_average_applications ?? 0).toFixed(1);

  const days = s.days_remaining ?? 60;
  document.getElementById('countdown').innerHTML =
    `Day <strong>${s.days_since_start ?? 1}</strong> &nbsp;·&nbsp; <strong>${days}</strong> days remaining`;
}

// ── Job Board ─────────────────────────────────────────────────────────────────

function sortBy(col) {
  if (jobSort.by === col) {
    jobSort.dir = jobSort.dir === 'asc' ? 'desc' : 'asc';
  } else {
    jobSort.by = col;
    jobSort.dir = col === 'posted_at' || col === 'discovered_at' ? 'desc' : 'asc';
  }
  currentJobPage = 0;
  loadJobs();
}

function renderSortHeaders() {
  const cols = [
    { key: 'job_title',    label: 'Job Title' },
    { key: 'company_name', label: 'Company' },
    { key: 'location',     label: 'Location' },
    { key: 'level',        label: 'Level' },
    { key: 'source',       label: 'Source' },
    { key: 'posted_at',    label: 'Posted' },
    { key: 'discovered_at', label: 'Found' },
    { key: null,           label: 'Actions' },
  ];
  const thead = document.querySelector('#jobs-table thead tr');
  thead.innerHTML = cols.map(c => {
    if (!c.key) return `<th>${c.label}</th>`;
    const active = jobSort.by === c.key;
    const arrow = active ? (jobSort.dir === 'asc' ? ' ▲' : ' ▼') : ' ⇅';
    return `<th class="sortable${active ? ' sort-active' : ''}" onclick="sortBy('${c.key}')">${c.label}<span class="sort-arrow">${arrow}</span></th>`;
  }).join('');
}

async function loadJobs(showLoading = true) {
  renderSortHeaders();
  const tbody = document.getElementById('jobs-body');
  if (showLoading) tbody.innerHTML = '<tr><td colspan="8" class="loading">Loading…</td></tr>';

  const q = document.getElementById('search-q').value;
  const loc = document.getElementById('search-loc').value;
  const params = new URLSearchParams({
    status: 'new', limit: 50, offset: currentJobPage * 50,
    sort_by: jobSort.by, sort_dir: jobSort.dir,
  });
  if (q) params.set('q', q);
  if (loc) params.set('location', loc);

  const data = await apiFetch(`/jobs?${params}`);
  if (!data) return;

  if (!data.jobs.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="loading">No new openings found. Configure search or run scraper.</td></tr>';
    return;
  }

  tbody.innerHTML = data.jobs.map(j => `
    <tr>
      <td>
        ${j.original_url
          ? `<a href="${j.original_url}" target="_blank" title="Open on company career site">${esc(j.job_title)}</a>
             <a href="${j.url}" target="_blank" title="Open source (${esc(j.source.split(':')[0])})" style="color:var(--text-dim);font-size:10px;margin-left:4px">↗src</a>`
          : `<a href="${j.url}" target="_blank">${esc(j.job_title)}</a>`
        }
      </td>
      <td>${companyLink(j.company_name)}</td>
      <td>${j.location ? esc(j.location) : '<span style="color:var(--text-dim)">—</span>'}</td>
      <td>${j.level ? `<span class="badge badge-new">${esc(j.level)}</span>` : '—'}</td>
      <td><span class="source-chip">${esc(j.source.split(':')[0])}</span></td>
      <td style="color:var(--text-dim);font-size:12px">${j.posted_at ? `<span title="${fmtExact(j.posted_at)}">${timeAgo(j.posted_at)}</span>` : '<span style="color:var(--border)">—</span>'}</td>
      <td style="color:var(--text-dim);font-size:12px"><span title="${fmtExact(j.discovered_at)}">${timeAgo(j.discovered_at)}</span></td>
      <td>
        <button class="btn-primary btn-sm" onclick="openApplyModal(${j.id})">Apply</button>
        <button class="btn-secondary btn-sm" style="margin-left:4px" onclick="saveJob(${j.id})">Save</button>
        <button class="btn-feedback btn-sm" style="margin-left:4px" onclick="openFeedbackModal(${j.id})" data-label="${esc(j.job_title)} @ ${esc(j.company_name)}">✕</button>
      </td>
    </tr>
  `).join('');

  renderPagination(data.total, 50, currentJobPage);
}

function renderPagination(total, limit, page) {
  const pages = Math.ceil(total / limit);
  const el = document.getElementById('jobs-pagination');
  if (pages <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `
    <button class="btn-secondary btn-sm" onclick="changePage(${page - 1})" ${page === 0 ? 'disabled' : ''}>← Prev</button>
    <span style="color:var(--text-dim);font-size:12px">Page ${page + 1} / ${pages} &nbsp; (${total} total)</span>
    <button class="btn-secondary btn-sm" onclick="changePage(${page + 1})" ${page >= pages - 1 ? 'disabled' : ''}>Next →</button>
  `;
}

function changePage(p) { currentJobPage = p; loadJobs(); }

// ── Add Job Modal ─────────────────────────────────────────────────────────────

function openAddJobModal() {
  ['aj-title','aj-company','aj-url','aj-location','aj-level','aj-description'].forEach(id => {
    document.getElementById(id).value = '';
  });
  document.getElementById('aj-error').textContent = '';
  document.getElementById('add-job-overlay').classList.remove('hidden');
  document.getElementById('aj-title').focus();
}

function closeAddJobModal() {
  document.getElementById('add-job-overlay').classList.add('hidden');
}

async function confirmAddJob() {
  const title = document.getElementById('aj-title').value.trim();
  const company = document.getElementById('aj-company').value.trim();
  const url = document.getElementById('aj-url').value.trim();
  const errEl = document.getElementById('aj-error');

  if (!title || !company || !url) {
    errEl.textContent = 'Job title, company, and URL are required.';
    return;
  }

  const body = {
    job_title: title,
    company_name: company,
    url,
    location: document.getElementById('aj-location').value.trim() || null,
    level: document.getElementById('aj-level').value.trim() || null,
    description: document.getElementById('aj-description').value.trim() || null,
  };

  const res = await fetch(API + '/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (res.status === 409) {
    errEl.textContent = 'This job is already in your board.';
    return;
  }
  if (!res.ok) {
    errEl.textContent = 'Something went wrong. Try again.';
    return;
  }

  closeAddJobModal();
  loadJobs();
  loadStats();
}

// ── Apply Modal ───────────────────────────────────────────────────────────────

async function openApplyModal(jobId) {
  pendingJobId = jobId;
  const resumes = await apiFetch('/resumes');
  const sel = document.getElementById('modal-resume');
  sel.innerHTML = '<option value="">— No resume —</option>' +
    (resumes?.resumes || []).map(r =>
      `<option value="${r.id}">${esc(r.name)}${r.version ? ` v${r.version}` : ''}${r.file_path ? ' 📄' : ''}</option>`
    ).join('');
  const lastResumeId = localStorage.getItem('lastResumeId');
  if (lastResumeId && sel.querySelector(`option[value="${lastResumeId}"]`)) {
    sel.value = lastResumeId;
  }
  document.getElementById('modal-notes').value = '';
  document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  pendingJobId = null;
}

async function confirmApply() {
  if (!pendingJobId) return;
  const resumeId = document.getElementById('modal-resume').value;
  if (resumeId) localStorage.setItem('lastResumeId', resumeId);
  const notes = document.getElementById('modal-notes').value;
  await apiFetch('/applications', {
    method: 'POST',
    body: JSON.stringify({ job_id: pendingJobId, resume_id: resumeId ? +resumeId : null, notes, status: 'applied' }),
  });
  closeModal();
  loadJobs();
  loadStats();
}

async function saveJob(jobId) {
  await apiFetch('/applications', {
    method: 'POST',
    body: JSON.stringify({ job_id: jobId, status: 'saved' }),
  });
  loadJobs();
}

// ── Application Tracker ───────────────────────────────────────────────────────

let _appsData = [];
let _appsSortState = { by: 'applied', dir: 'desc' };

const _STATUS_ORDER = { applied: 0, assessment: 1, interview: 2, offered: 3, rejected: 4 };

async function loadApplications() {
  const tbody = document.getElementById('apps-body');
  tbody.innerHTML = '<tr><td colspan="7" class="loading">Loading…</td></tr>';
  const status = document.getElementById('filter-status').value;
  const params = new URLSearchParams({ limit: 200 });
  if (status) params.set('status', status);
  const data = await apiFetch(`/applications?${params}`);
  if (!data?.applications.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="loading">No applications yet. Start applying from the Job Board.</td></tr>';
    return;
  }
  _appsData = data.applications;
  _renderAppsTable();
}

function appsSort(col) {
  if (_appsSortState.by === col) {
    _appsSortState.dir = _appsSortState.dir === 'asc' ? 'desc' : 'asc';
  } else {
    _appsSortState.by = col;
    _appsSortState.dir = col === 'applied' ? 'desc' : 'asc';
  }
  document.querySelectorAll('#apps-thead .sortable').forEach(th => {
    th.classList.remove('sort-active');
    th.querySelector('.sort-arrow').textContent = ' ⇅';
  });
  const colIdx = { title: 0, company: 1, applied: 2, status: 3 };
  const ths = document.querySelectorAll('#apps-thead th');
  const th = ths[colIdx[col]];
  if (th) {
    th.classList.add('sort-active');
    th.querySelector('.sort-arrow').textContent = _appsSortState.dir === 'asc' ? ' ▲' : ' ▼';
  }
  _renderAppsTable();
}

function _renderAppsTable() {
  const tbody = document.getElementById('apps-body');
  const { by, dir } = _appsSortState;
  const sorted = [..._appsData].sort((a, b) => {
    let av, bv;
    if (by === 'title')   { av = a.job.job_title.toLowerCase();   bv = b.job.job_title.toLowerCase(); }
    else if (by === 'company') { av = a.job.company_name.toLowerCase(); bv = b.job.company_name.toLowerCase(); }
    else if (by === 'applied') { av = a.applied_at || ''; bv = b.applied_at || ''; }
    else if (by === 'status')  { av = _STATUS_ORDER[a.status] ?? 99; bv = _STATUS_ORDER[b.status] ?? 99; }
    if (av < bv) return dir === 'asc' ? -1 : 1;
    if (av > bv) return dir === 'asc' ? 1 : -1;
    return 0;
  });
  tbody.innerHTML = sorted.map(a => `
    <tr>
      <td><a href="${a.job.url}" target="_blank">${esc(a.job.job_title)}</a></td>
      <td>${esc(a.job.company_name)}</td>
      <td style="font-size:12px;color:var(--text-dim)">${a.applied_at ? formatDate(a.applied_at) : '—'}</td>
      <td><span class="badge badge-${a.status}">${a.status.replace('_', ' ')}</span></td>
      <td style="font-size:12px;color:var(--text-dim)">${a.resume?.name ?? '—'}</td>
      <td class="notes-cell">${esc(a.notes || '')}</td>
      <td>
        <button class="btn-secondary btn-sm" onclick="openStatusModal(${a.id}, '${a.status}')">Update</button>
      </td>
    </tr>
  `).join('');
}

// ── Status Modal ──────────────────────────────────────────────────────────────

function openStatusModal(appId, currentStatus) {
  pendingAppId = appId;
  document.getElementById('status-modal-select').value = currentStatus;
  document.getElementById('status-modal-notes').value = '';
  document.getElementById('status-modal-overlay').classList.remove('hidden');
}

function closeStatusModal() {
  document.getElementById('status-modal-overlay').classList.add('hidden');
  pendingAppId = null;
}

async function confirmStatusUpdate() {
  if (!pendingAppId) return;
  const status = document.getElementById('status-modal-select').value;
  const notes = document.getElementById('status-modal-notes').value;
  await apiFetch(`/applications/${pendingAppId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status, notes }),
  });
  closeStatusModal();
  loadApplications();
  loadStats();
}

// ── Feedback ──────────────────────────────────────────────────────────────────

let feedbackJobId = null;
let feedbackSelectedTags = new Set();

function openFeedbackModal(jobId) {
  feedbackJobId = jobId;
  feedbackSelectedTags = new Set();
  const btn = document.querySelector(`button[onclick="openFeedbackModal(${jobId})"]`);
  document.getElementById('feedback-job-title').textContent = btn ? btn.dataset.label : '';
  document.getElementById('feedback-text').value = '';
  document.querySelectorAll('#feedback-chips .chip').forEach(c => c.classList.remove('chip-active'));
  document.getElementById('feedback-overlay').classList.remove('hidden');
}

function closeFeedbackModal() {
  feedbackJobId = null;
  document.getElementById('feedback-overlay').classList.add('hidden');
}

async function submitFeedback() {
  if (!feedbackJobId) return;
  const tags = [...feedbackSelectedTags].join(', ');
  const note = document.getElementById('feedback-text').value.trim();
  const feedback = [tags, note].filter(Boolean).join(' — ');
  if (!feedback) { closeFeedbackModal(); return; }

  await apiFetch(`/jobs/${feedbackJobId}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ feedback }),
  });
  const removedId = feedbackJobId;
  closeFeedbackModal();
  document.querySelector(`button[onclick="openFeedbackModal(${removedId})"]`)?.closest('tr')?.remove();
  loadStats();
}

function setupFeedbackModal() {
  document.getElementById('feedback-cancel').addEventListener('click', closeFeedbackModal);
  document.getElementById('feedback-confirm').addEventListener('click', submitFeedback);
  document.querySelectorAll('#feedback-chips .chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const tag = chip.dataset.tag;
      if (feedbackSelectedTags.has(tag)) {
        feedbackSelectedTags.delete(tag);
        chip.classList.remove('chip-active');
      } else {
        feedbackSelectedTags.add(tag);
        chip.classList.add('chip-active');
      }
    });
  });
}

// ── Config ────────────────────────────────────────────────────────────────────

async function loadConfig() {
  const cfg = await apiFetch('/config');
  if (!cfg) return;
  document.getElementById('cfg-titles').value = cfg.titles.join(', ');
  document.getElementById('cfg-locations').value = cfg.locations.join(', ');
  document.getElementById('cfg-levels').value = cfg.levels.join(', ');
  document.getElementById('cfg-keywords').value = cfg.keywords.join(', ');
  document.getElementById('cfg-excluded').value = cfg.excluded_companies.join(', ');
}

async function saveConfig() {
  const parse = id => document.getElementById(id).value.split(',').map(s => s.trim()).filter(Boolean);
  const body = {
    titles: parse('cfg-titles'),
    locations: parse('cfg-locations'),
    levels: parse('cfg-levels'),
    keywords: parse('cfg-keywords'),
    excluded_companies: parse('cfg-excluded'),
  };
  const msg = document.getElementById('config-msg');
  msg.textContent = 'Saving…';
  await apiFetch('/config', { method: 'PUT', body: JSON.stringify(body) });
  msg.textContent = 'Saved! Scraper running…';
  setTimeout(() => { msg.textContent = ''; }, 3000);
}

// ── Resumes ───────────────────────────────────────────────────────────────────

async function loadResumes() {
  const tbody = document.getElementById('resumes-body');
  tbody.innerHTML = '<tr><td colspan="6" class="loading">Loading…</td></tr>';
  const data = await apiFetch('/resumes');
  if (!data?.resumes.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="loading">No resumes yet. Upload your first one.</td></tr>';
    return;
  }
  tbody.innerHTML = data.resumes.map(r => {
    const hasFile = !!r.file_path;
    const fileCell = hasFile
      ? `<a href="${API}/resumes/${r.id}/file" target="_blank" class="file-download-link" title="Download ${esc(r.name)}">⬇ Download</a>`
      : `<span style="color:var(--text-dim)">—</span>`;
    return `
    <tr>
      <td style="font-weight:500">${esc(r.name)}</td>
      <td>${r.version ? `<span class="source-chip">v${esc(r.version)}</span>` : '—'}</td>
      <td>${(r.tags || []).map(t => `<span class="source-chip">${esc(t)}</span>`).join(' ')}</td>
      <td>${fileCell}</td>
      <td style="font-size:12px;color:var(--text-dim)">${formatDate(r.created_at)}</td>
      <td>
        <button class="btn-secondary btn-sm" onclick="deleteResume(${r.id})">Delete</button>
      </td>
    </tr>`;
  }).join('');
}

// ── Add Resume Modal ──────────────────────────────────────────────────────────

let _rmFile = null;

function openResumeModal() {
  _rmFile = null;
  ['rm-name','rm-version','rm-tags'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('rm-drop-label').textContent = 'Drop file here or click to browse';
  document.getElementById('rm-error').textContent = '';
  document.getElementById('rm-confirm').disabled = false;
  document.getElementById('rm-confirm').textContent = 'Upload & Save';
  document.getElementById('resume-overlay').classList.remove('hidden');
  document.getElementById('rm-name').focus();
}

function closeResumeModal() {
  document.getElementById('resume-overlay').classList.add('hidden');
}

function setupResumeModal() {
  document.getElementById('btn-add-resume').addEventListener('click', openResumeModal);
  document.getElementById('rm-cancel').addEventListener('click', closeResumeModal);
  document.getElementById('rm-confirm').addEventListener('click', submitResume);

  const drop = document.getElementById('rm-drop');
  const fileInput = document.getElementById('rm-file');

  drop.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) setResumeFile(fileInput.files[0]);
  });
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('drag-over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('drag-over'));
  drop.addEventListener('drop', e => {
    e.preventDefault();
    drop.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) setResumeFile(e.dataTransfer.files[0]);
  });
}

function setResumeFile(file) {
  _rmFile = file;
  document.getElementById('rm-drop-label').textContent = `✓ ${file.name}`;
  document.getElementById('rm-drop').classList.add('file-selected');
  // Auto-fill name from filename if empty
  const nameEl = document.getElementById('rm-name');
  if (!nameEl.value) {
    nameEl.value = file.name.replace(/\.[^.]+$/, '').replace(/[-_]/g, ' ');
  }
}

async function submitResume() {
  const name = document.getElementById('rm-name').value.trim();
  const errEl = document.getElementById('rm-error');
  if (!name) { errEl.textContent = 'Name is required.'; return; }
  if (!_rmFile) { errEl.textContent = 'Please select a file.'; return; }

  const btn = document.getElementById('rm-confirm');
  btn.disabled = true;
  btn.textContent = 'Uploading…';

  const form = new FormData();
  form.append('file', _rmFile);
  form.append('name', name);
  const version = document.getElementById('rm-version').value.trim();
  if (version) form.append('version', version);
  form.append('tags', document.getElementById('rm-tags').value.trim());

  try {
    const resp = await fetch(`${API}/resumes/upload`, { method: 'POST', body: form });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      errEl.textContent = err.detail || `Upload failed (${resp.status})`;
      btn.disabled = false;
      btn.textContent = 'Upload & Save';
      return;
    }
    closeResumeModal();
    loadResumes();
  } catch (e) {
    errEl.textContent = 'Could not reach server.';
    btn.disabled = false;
    btn.textContent = 'Upload & Save';
  }
}

async function deleteResume(id) {
  if (!confirm('Delete this resume version? The file will also be removed.')) return;
  await apiFetch(`/resumes/${id}`, { method: 'DELETE' });
  loadResumes();
}

// ── Scraper ───────────────────────────────────────────────────────────────────

async function loadScraperStatus() {
  const data = await apiFetch('/scraper/status');
  if (!data) return;
  const el = document.getElementById('last-searched');
  if (data.last_run) {
    const ago = timeAgo(data.last_run);
    const found = data.jobs_found_last_run;
    const runs = data.total_runs;
    el.textContent = `Last searched ${ago}  ·  ${found} new jobs  ·  ${runs} runs`;
    el.title = `Full timestamp: ${new Date(data.last_run + 'Z').toLocaleString()}`;
  } else {
    el.textContent = 'Scraper not yet run';
  }
}

async function triggerScrape() {
  const el = document.getElementById('scraper-status');
  el.textContent = 'Running…';
  await apiFetch('/scraper/run', { method: 'POST' });
  el.textContent = 'Scraper triggered. Results in ~30s.';
  setTimeout(() => { el.textContent = ''; loadJobs(); loadStats(); loadScraperStatus(); }, 35_000);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function apiFetch(path, opts = {}) {
  try {
    const res = await fetch(API + path, {
      headers: { 'Content-Type': 'application/json', ...opts.headers },
      ...opts,
    });
    if (res.status === 204) return null;
    return res.ok ? res.json() : null;
  } catch (e) {
    console.error('API error:', e);
    return null;
  }
}

function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function companyLink(name) {
  const url = careerSites[name.toLowerCase()];
  return url
    ? `<a href="${url}" target="_blank" title="Open ${esc(name)} careers page">${esc(name)}</a>`
    : esc(name);
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function timeAgo(iso) {
  if (!iso) return '—';
  // Ensure UTC parsing — server returns ISO strings without Z suffix
  const ts = iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function fmtExact(iso) {
  if (!iso) return '';
  const ts = iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z';
  return new Date(ts).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit', hour12: true,
  });
}

function debounce(fn, delay) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
}

// ── Companies ─────────────────────────────────────────────────────────────────

const ATS_BADGE = {
  greenhouse:      { label: 'Greenhouse',      cls: 'badge-green'  },
  lever:           { label: 'Lever',           cls: 'badge-blue'   },
  ashby:           { label: 'Ashby',           cls: 'badge-purple' },
  workday:         { label: 'Workday',         cls: 'badge-orange' },
  smartrecruiters: { label: 'SmartRecruiters', cls: 'badge-teal'   },
  amazon:          { label: 'Amazon',          cls: 'badge-yellow' },
  custom:          { label: 'Custom',          cls: 'badge-gray'   },
};

// ── Company Portal ────────────────────────────────────────────────────────────

function _portalMsg(text, side, style = '') {
  const log = document.getElementById('portal-log');
  const avatar = side === 'user' ? '🧑' : '🦆';
  const div = document.createElement('div');
  div.className = `portal-msg ${side}${style ? ' ' + style : ''}`;
  div.innerHTML = `
    <div class="portal-avatar">${avatar}</div>
    <div class="portal-bubble">${text}</div>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

function setupPortal() {
  const input = document.getElementById('portal-input');
  const btn   = document.getElementById('portal-submit');

  async function submit() {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    input.focus();

    _portalMsg(esc(text), 'user');
    const spinner = _portalMsg('Looking up…', 'bot', 'spin');

    const result = await apiFetch('/companies/ingest', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });

    spinner.remove();

    if (!result) {
      _portalMsg('⚠️ Server error — could not process the request.', 'bot', 'error');
      return;
    }

    const styleMap = { added: 'ok', exists: 'warn', not_found: 'warn', error: 'error' };
    const icon     = { added: '✅', exists: 'ℹ️', not_found: '🔍', error: '❌' };
    const botStyle = styleMap[result.status] || '';
    _portalMsg(`${icon[result.status] || ''} ${esc(result.message)}`, 'bot', botStyle);

    if (result.status === 'added') {
      // Refresh the company list below
      await loadCompanies();
    }
  }

  btn.addEventListener('click', submit);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') submit(); });
}

let allCompanies = [];

async function loadCompanies() {
  const data = await apiFetch('/companies');
  if (!data) return;
  allCompanies = data;
  renderCompanies();

  document.getElementById('co-search').oninput = debounce(renderCompanies, 250);
  document.getElementById('co-filter-ats').onchange = renderCompanies;
  document.getElementById('co-filter-active').onchange = renderCompanies;
}

function renderCompanies() {
  const q = document.getElementById('co-search').value.toLowerCase();
  const atsFilter = document.getElementById('co-filter-ats').value;
  const activeFilter = document.getElementById('co-filter-active').value;

  const filtered = allCompanies.filter(c => {
    if (q && !c.company_name.toLowerCase().includes(q) && !c.ats_slug.toLowerCase().includes(q) && !c.ats_type.toLowerCase().includes(q)) return false;
    if (atsFilter && c.ats_type !== atsFilter) return false;
    if (activeFilter === 'true' && !c.is_active) return false;
    if (activeFilter === 'false' && c.is_active) return false;
    return true;
  });

  const tbody = document.getElementById('companies-body');
  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="loading">No companies match.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(c => {
    const badge = ATS_BADGE[c.ats_type] || { label: c.ats_type, cls: 'badge-gray' };
    const careerLink = c.career_url
      ? `<a href="${esc(c.career_url)}" target="_blank" title="Open career page">↗</a>`
      : '—';
    const activeToggle = c.is_active
      ? `<button class="btn-tiny btn-active" onclick="toggleCompany(${c.id}, false)" title="Deactivate">✓ Active</button>`
      : `<button class="btn-tiny btn-inactive" onclick="toggleCompany(${c.id}, true)" title="Activate">✗ Inactive</button>`;
    return `<tr class="${c.is_active ? '' : 'row-inactive'}">
      <td>${esc(c.company_name)}</td>
      <td><span class="badge ${badge.cls}">${badge.label}</span></td>
      <td><code>${esc(c.ats_slug)}</code></td>
      <td>${careerLink}</td>
      <td>${activeToggle}</td>
      <td><button class="btn-tiny btn-danger" onclick="deleteCompany(${c.id}, '${esc(c.company_name)}')">Delete</button></td>
    </tr>`;
  }).join('');
}

async function toggleCompany(id, active) {
  await apiFetch(`/companies/${id}`, { method: 'PATCH', body: JSON.stringify({ is_active: active }) });
  const c = allCompanies.find(x => x.id === id);
  if (c) c.is_active = active;
  renderCompanies();
}

async function deleteCompany(id, name) {
  if (!confirm(`Delete ${name}? This cannot be undone.`)) return;
  const res = await fetch(`${API}/companies/${id}`, { method: 'DELETE' });
  if (res.ok) {
    allCompanies = allCompanies.filter(c => c.id !== id);
    renderCompanies();
  }
}

function setupCompanyModal() {
  document.getElementById('btn-discover').addEventListener('click', async () => {
    const btn = document.getElementById('btn-discover');
    btn.disabled = true;
    btn.textContent = '🔍 Discovering…';
    const result = await apiFetch('/scraper/discover', { method: 'POST' });
    btn.disabled = false;
    btn.textContent = '🔍 Auto-Discover';
    if (result) alert('Discovery started! New companies will appear in the list within a few minutes.');
  });

  document.getElementById('btn-add-company').addEventListener('click', () => {
    document.getElementById('co-name').value = '';
    document.getElementById('co-slug').value = '';
    document.getElementById('co-board').value = '';
    document.getElementById('co-wd-ver').value = 'wd5';
    document.getElementById('co-url').value = '';
    document.getElementById('co-error').textContent = '';
    document.getElementById('co-overlay').classList.remove('hidden');
  });
  document.getElementById('co-cancel').addEventListener('click', () => {
    document.getElementById('co-overlay').classList.add('hidden');
  });
  document.getElementById('co-confirm').addEventListener('click', async () => {
    const body = {
      company_name: document.getElementById('co-name').value.trim(),
      ats_type: document.getElementById('co-ats-type').value,
      ats_slug: document.getElementById('co-slug').value.trim(),
      workday_board: document.getElementById('co-board').value.trim() || null,
      workday_wd_ver: document.getElementById('co-wd-ver').value.trim() || 'wd5',
      career_url: document.getElementById('co-url').value.trim() || null,
    };
    if (!body.company_name || !body.ats_slug) {
      document.getElementById('co-error').textContent = 'Name and slug are required.';
      return;
    }
    const result = await apiFetch('/companies', { method: 'POST', body: JSON.stringify(body) });
    if (result) {
      allCompanies.push(result);
      allCompanies.sort((a, b) => a.company_name.localeCompare(b.company_name));
      renderCompanies();
      document.getElementById('co-overlay').classList.add('hidden');
    } else {
      document.getElementById('co-error').textContent = 'Failed to add company. Check for duplicates.';
    }
  });
}

// ── Mailbox Tab ───────────────────────────────────────────────────────────────

let mailboxEvents = [];
let mailboxSortState = { by: 'received_at', dir: 'desc' };

const CATEGORY_LABEL = {
  interview:           'Interview',
  offer:               'Offer',
  assessment:          'Assessment',
  rejection:           'Rejection',
  application_confirm: 'Confirmation',
  linkedin_message:    'LinkedIn DM',
  other:               'Other',
};
const CATEGORY_CLASS = {
  interview:           'badge-green',
  offer:               'badge-purple',
  assessment:          'badge-blue',
  rejection:           'badge-orange',
  application_confirm: 'badge-teal',
  linkedin_message:    'badge-blue',
  other:               'badge-gray',
};

async function loadMailbox() {
  const data = await apiFetch('/mailbox/summary');
  if (!data) return;

  const cat = data.by_category || {};
  const week = data.this_week || {};

  document.getElementById('mc-total').textContent      = data.total_emails ?? 0;
  document.getElementById('mc-interview').textContent  = cat.interview ?? 0;
  document.getElementById('mc-assessment').textContent = cat.assessment ?? 0;
  document.getElementById('mc-rejection').textContent  = cat.rejection ?? 0;
  document.getElementById('mc-offer').textContent      = cat.offer ?? 0;
  document.getElementById('mc-confirm').textContent    = cat.application_confirm ?? 0;

  if (data.last_sync) {
    const d = new Date(data.last_sync + 'Z');
    document.getElementById('mailbox-last-sync').textContent =
      'Last sync: ' + d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  }

  const weekEl = document.getElementById('mailbox-week-cards');
  const weekOrder = ['interview','offer','assessment','rejection','application_confirm'];
  weekEl.innerHTML = weekOrder.map(k => `
    <div class="mcard-sm">
      <span class="mcard-sm-num">${week[k] ?? 0}</span>
      <span class="mcard-sm-label">${CATEGORY_LABEL[k]}</span>
    </div>
  `).join('');

  document.getElementById('mc-linkedin').textContent = data.linkedin_messages ?? 0;

  mailboxEvents = data.recent_events || [];
  renderMailboxTable();
}

function mailboxSort(col) {
  if (mailboxSortState.by === col) {
    mailboxSortState.dir = mailboxSortState.dir === 'asc' ? 'desc' : 'asc';
  } else {
    mailboxSortState.by = col;
    mailboxSortState.dir = col === 'received_at' ? 'desc' : 'asc';
  }
  // Update header arrows
  document.querySelectorAll('#mailbox-thead .sortable').forEach(th => {
    th.classList.remove('sort-active');
    th.querySelector('.sort-arrow').textContent = ' ⇅';
  });
  const colMap = { company: 1, category: 3, received_at: 4 };
  const idx = colMap[col];
  const ths = document.querySelectorAll('#mailbox-thead th');
  if (ths[idx]) {
    ths[idx].classList.add('sort-active');
    ths[idx].querySelector('.sort-arrow').textContent = mailboxSortState.dir === 'asc' ? ' ▲' : ' ▼';
  }
  renderMailboxTable();
}

function renderMailboxTable() {
  const tbody = document.getElementById('mailbox-events-body');
  if (!mailboxEvents.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="loading">No email events yet — click Sync Now.</td></tr>';
    return;
  }

  const { by, dir } = mailboxSortState;
  const sorted = [...mailboxEvents].sort((a, b) => {
    let av = by === 'company' ? (a.company_name || a.from_name || '') :
             by === 'category' ? (a.category || '') :
             (a.received_at || '');
    let bv = by === 'company' ? (b.company_name || b.from_name || '') :
             by === 'category' ? (b.category || '') :
             (b.received_at || '');
    av = av.toLowerCase(); bv = bv.toLowerCase();
    return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
  });

  tbody.innerHTML = sorted.map(e => {
    const recv = e.received_at ? new Date(e.received_at + 'Z').toLocaleDateString() : '—';
    const appLink = e.linked_application_id
      ? `<a href="#" onclick="switchToTracker(${e.linked_application_id})" style="color:var(--accent)">View</a>`
      : '<span style="color:var(--text-dim)">—</span>';
    return `<tr>
      <td style="font-size:18px;text-align:center">${e.icon}</td>
      <td><strong>${esc(e.company_name || e.from_name || '?')}</strong></td>
      <td style="font-size:12px;max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(e.subject)}">${esc(e.subject)}</td>
      <td><span class="ats-badge ${CATEGORY_CLASS[e.category] || 'badge-gray'}">${CATEGORY_LABEL[e.category] || e.category}</span></td>
      <td style="font-size:12px;color:var(--text-dim)">${recv}</td>
      <td>${appLink}</td>
    </tr>`;
  }).join('');
}

async function loadLinkedInMessages() {
  const data = await apiFetch('/mailbox/linkedin-messages?limit=30');
  if (!data) return;

  const badge = document.getElementById('linkedin-unread-badge');
  if (data.unread_3d > 0) {
    badge.textContent = data.unread_3d + ' new';
    badge.style.display = 'inline';
  } else {
    badge.style.display = 'none';
  }

  const list = document.getElementById('linkedin-messages-list');
  if (!data.messages || data.messages.length === 0) {
    list.innerHTML = '<div style="color:var(--text-dim);font-size:13px">No LinkedIn messages yet — they\'ll appear here once Gmail syncs them.</div>';
    return;
  }

  list.innerHTML = data.messages.map(m => {
    const sender = esc(m.sender_name || m.from_name || 'LinkedIn User');
    const preview = esc(m.preview || m.subject || '');
    const date = m.received_at
      ? new Date(m.received_at + 'Z').toLocaleDateString([], {month:'short', day:'numeric'})
      : '';
    return `<div style="background:var(--card-bg);border:1px solid var(--border);border-left:3px solid #0077b5;border-radius:6px;padding:12px 14px;display:flex;align-items:flex-start;gap:12px">
      <div style="width:36px;height:36px;border-radius:50%;background:#0077b5;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:14px;flex-shrink:0">${esc(sender[0] || '?')}</div>
      <div style="flex:1;min-width:0">
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px">
          <strong style="font-size:14px">${sender}</strong>
          <span style="font-size:11px;color:var(--text-dim);white-space:nowrap">${date}</span>
        </div>
        <div style="font-size:13px;color:var(--text-dim);margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${preview}">${preview}</div>
      </div>
      <a href="https://www.linkedin.com/messaging/" target="_blank" rel="noopener" style="color:#0077b5;font-size:12px;white-space:nowrap;align-self:center">Open →</a>
    </div>`;
  }).join('');
}

async function triggerEmailSync() {
  document.getElementById('mailbox-last-sync').textContent = 'Syncing…';
  const result = await apiFetch('/mailbox/sync', { method: 'POST' });
  if (result) {
    await loadMailbox();
    if (result.new_events > 0 || result.status_updates > 0) {
      alert(`Sync complete: ${result.new_events} new emails, ${result.status_updates} status updates.`);
    }
  }
}

function switchToTracker(appId) {
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(s => s.classList.remove('active'));
  document.querySelector('[data-tab="tracker"]').classList.add('active');
  document.getElementById('tab-tracker').classList.add('active');
  loadApplications();
}

// ── Analysis Tab ──────────────────────────────────────────────────────────────

const _anCharts = {};   // registry so we can destroy before redraw

function _destroyChart(id) {
  if (_anCharts[id]) { _anCharts[id].destroy(); delete _anCharts[id]; }
}

const _CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {},
};

const _GRID = {
  color: 'rgba(40,56,32,0.6)',
  borderColor: 'rgba(40,56,32,0.6)',
};

const _TICK = { color: '#7a9a6a', font: { size: 11 } };

async function loadAnalysis() {
  const d = await apiFetch('/stats/analysis');
  if (!d) return;

  _renderKPIs(d.kpi);
  _renderDaily(d);
  _renderCumulative(d);
  _renderFunnel(d.funnel);
  _renderSource(d.by_source);
  _renderCompanies(d.top_companies);
}

function _renderKPIs(k) {
  document.getElementById('an-kpis').innerHTML = [
    { val: k.total_applied,            label: 'Total Applied',      cls: 'accent'  },
    { val: k.avg_per_day + '/day',     label: 'Avg per Day',        cls: ''        },
    { val: k.response_rate + '%',      label: 'Response Rate',      cls: 'blue'    },
    { val: k.interview_rate + '%',     label: 'Interview Rate',     cls: 'yellow'  },
    { val: k.interviews,               label: 'Interviews',         cls: 'blue'    },
    { val: k.offers,                   label: 'Offers',             cls: 'purple'  },
    { val: k.rejections,               label: 'Rejections',         cls: 'red'     },
    { val: k.days_active + ' days',    label: 'Days Active',        cls: ''        },
  ].map(c => `
    <div class="an-kpi ${c.cls}">
      <div class="an-kpi-val">${c.val}</div>
      <div class="an-kpi-label">${c.label}</div>
    </div>`).join('');
}

function _renderDaily(d) {
  _destroyChart('daily');
  const ctx = document.getElementById('chart-daily').getContext('2d');
  _anCharts['daily'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: d.dates,
      datasets: [
        {
          label: 'Applications',
          data: d.applied_series,
          borderColor: '#6dba5e',
          backgroundColor: 'rgba(109,186,94,0.12)',
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 5,
          pointBackgroundColor: '#6dba5e',
          fill: true,
          tension: 0.35,
        },
        {
          label: '7-day avg',
          data: d.rolling_7d,
          borderColor: '#e8b84b',
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 0,
          borderDash: [4, 3],
          tension: 0.4,
        },
      ],
    },
    options: {
      ..._CHART_DEFAULTS,
      plugins: {
        legend: { display: false },
        tooltip: { mode: 'index', intersect: false },
      },
      scales: {
        x: { grid: _GRID, ticks: { ..._TICK, maxTicksLimit: 14 } },
        y: { grid: _GRID, ticks: _TICK, beginAtZero: true },
      },
    },
  });
}

function _renderCumulative(d) {
  _destroyChart('cumulative');
  const ctx = document.getElementById('chart-cumulative').getContext('2d');
  _anCharts['cumulative'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: d.dates,
      datasets: [{
        label: 'Total Applications',
        data: d.cumulative,
        borderColor: '#6dba5e',
        backgroundColor: 'rgba(109,186,94,0.08)',
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        tension: 0.3,
      }],
    },
    options: {
      ..._CHART_DEFAULTS,
      scales: {
        x: { grid: _GRID, ticks: { ..._TICK, maxTicksLimit: 10 } },
        y: { grid: _GRID, ticks: _TICK, beginAtZero: true },
      },
    },
  });
}

function _renderFunnel(funnel) {
  _destroyChart('funnel');
  const ctx = document.getElementById('chart-funnel').getContext('2d');
  const labels = funnel.map(f => f.stage.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()));
  const counts  = funnel.map(f => f.count);
  _anCharts['funnel'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Count',
        data: counts,
        backgroundColor: ['rgba(109,186,94,0.7)','rgba(116,192,252,0.7)','rgba(232,184,75,0.7)','rgba(192,132,252,0.7)'],
        borderRadius: 4,
        borderWidth: 0,
      }],
    },
    options: {
      ..._CHART_DEFAULTS,
      indexAxis: 'y',
      scales: {
        x: { grid: _GRID, ticks: _TICK, beginAtZero: true },
        y: { grid: { display: false }, ticks: { color: '#deebd4', font: { size: 12 } } },
      },
    },
  });
}

function _renderSource(sources) {
  _destroyChart('source');
  const ctx = document.getElementById('chart-source').getContext('2d');
  const colors = ['#6dba5e','#74c0fc','#e8b84b','#c084fc','#e85a6a','#2dd4bf','#f97316','#94a3b8'];
  _anCharts['source'] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: sources.map(s => s.source),
      datasets: [{
        data: sources.map(s => s.count),
        backgroundColor: colors,
        borderColor: '#121a0e',
        borderWidth: 2,
        hoverOffset: 6,
      }],
    },
    options: {
      ..._CHART_DEFAULTS,
      cutout: '60%',
      plugins: {
        legend: {
          display: true,
          position: 'right',
          labels: { color: '#7a9a6a', font: { size: 11 }, boxWidth: 10, padding: 8 },
        },
      },
    },
  });
}

function _renderCompanies(companies) {
  _destroyChart('companies');
  const ctx = document.getElementById('chart-companies').getContext('2d');
  const labels  = companies.map(c => c.company);
  const applied  = companies.map(c => c.total - c.interview - c.offer - c.rejected);
  const interviews = companies.map(c => c.interview);
  const offers   = companies.map(c => c.offer);
  const rejected = companies.map(c => c.rejected);
  _anCharts['companies'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Applied',    data: applied,    backgroundColor: 'rgba(109,186,94,0.65)', borderRadius: 3 },
        { label: 'Interview',  data: interviews, backgroundColor: 'rgba(116,192,252,0.75)', borderRadius: 3 },
        { label: 'Offer',      data: offers,     backgroundColor: 'rgba(192,132,252,0.75)', borderRadius: 3 },
        { label: 'Rejected',   data: rejected,   backgroundColor: 'rgba(232,90,106,0.55)', borderRadius: 3 },
      ],
    },
    options: {
      ..._CHART_DEFAULTS,
      indexAxis: 'y',
      plugins: {
        legend: {
          display: true,
          labels: { color: '#7a9a6a', font: { size: 11 }, boxWidth: 10 },
        },
        tooltip: { mode: 'index', intersect: false },
      },
      scales: {
        x: { stacked: true, grid: _GRID, ticks: _TICK, beginAtZero: true },
        y: { stacked: true, grid: { display: false }, ticks: { color: '#deebd4', font: { size: 11 } } },
      },
    },
  });
}
