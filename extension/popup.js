const DEFAULT_SERVER = 'http://143.198.134.85';
let currentUrl = '';
let lastAnalysis = null;

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  const { serverUrl } = await chrome.storage.local.get('serverUrl');
  document.getElementById('server-url').value = serverUrl || DEFAULT_SERVER;

  // Get current tab URL
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentUrl = tab?.url || '';
  document.getElementById('current-url').textContent = currentUrl || 'No URL';

  document.getElementById('btn-analyze').addEventListener('click', analyze);
  document.getElementById('btn-settings').addEventListener('click', toggleSettings);
  document.getElementById('btn-save-settings').addEventListener('click', saveSettings);
  document.getElementById('btn-save-board').addEventListener('click', saveToBoard);
  document.getElementById('btn-apply-now').addEventListener('click', () => chrome.tabs.create({ url: currentUrl }));
});

// ── Settings ──────────────────────────────────────────────────────────────────

function toggleSettings() {
  document.getElementById('settings-panel').classList.toggle('hidden');
}

async function saveSettings() {
  const url = document.getElementById('server-url').value.trim().replace(/\/$/, '');
  await chrome.storage.local.set({ serverUrl: url });
  document.getElementById('settings-panel').classList.add('hidden');
}

async function getServer() {
  const { serverUrl } = await chrome.storage.local.get('serverUrl');
  return (serverUrl || DEFAULT_SERVER).replace(/\/$/, '');
}

// ── Analyze ───────────────────────────────────────────────────────────────────

async function analyze() {
  if (!currentUrl || currentUrl.startsWith('chrome://')) {
    showError('Navigate to a job posting page first.');
    return;
  }

  setLoading(true, 'Fetching job page…');
  hideResults();
  hideError();

  const server = await getServer();

  try {
    setLoading(true, 'Analyzing with Claude…');
    const resp = await fetch(`${server}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: currentUrl }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${resp.status}`);
    }

    lastAnalysis = await resp.json();
    renderResults(lastAnalysis);
  } catch (e) {
    showError(e.message.includes('Failed to fetch')
      ? `Can't reach server at ${server}. Check your server URL in settings.`
      : e.message);
  } finally {
    setLoading(false);
  }
}

// ── Render ────────────────────────────────────────────────────────────────────

function renderResults(data) {
  document.getElementById('res-title').textContent = data.job_title || 'Unknown Role';
  document.getElementById('res-company').textContent = data.company_name || '';
  document.getElementById('res-summary').textContent = data.summary || '';

  // Fit score
  const score = data.fit_score ?? 0;
  const badge = document.getElementById('fit-score');
  badge.textContent = `${score}%`;
  badge.className = 'fit-badge ' + (score >= 70 ? 'fit-high' : score >= 45 ? 'fit-mid' : 'fit-low');

  // Strengths
  const strengthsEl = document.getElementById('res-strengths');
  strengthsEl.innerHTML = (data.strengths || []).map(s => `<li>${esc(s)}</li>`).join('');

  // Gaps
  const gapsEl = document.getElementById('res-gaps');
  const gaps = data.gaps || [];
  gapsEl.innerHTML = gaps.map(g => `<li>${esc(g)}</li>`).join('');
  document.getElementById('gaps-section').style.display = gaps.length ? '' : 'none';

  // Cover letter bullets — click to copy
  const bulletsEl = document.getElementById('res-bullets');
  bulletsEl.innerHTML = (data.cover_letter_bullets || []).map(b => `
    <li onclick="copyText(this, '${b.replace(/'/g, "\\'")}')">
      ${esc(b)}
      <span class="copy-hint">click to copy</span>
    </li>
  `).join('');

  document.getElementById('results').classList.remove('hidden');
}

function copyText(el, text) {
  navigator.clipboard.writeText(text).then(() => {
    const hint = el.querySelector('.copy-hint');
    hint.textContent = '✓ copied!';
    setTimeout(() => { hint.textContent = 'click to copy'; }, 1500);
  });
}

// ── Save to Board ─────────────────────────────────────────────────────────────

async function saveToBoard() {
  if (!lastAnalysis) return;
  const server = await getServer();
  const btn = document.getElementById('btn-save-board');
  const msg = document.getElementById('save-msg');
  btn.disabled = true;

  try {
    const resp = await fetch(`${server}/api/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_title: lastAnalysis.job_title,
        company_name: lastAnalysis.company_name,
        url: currentUrl,
        location: lastAnalysis.location || null,
        level: lastAnalysis.level || null,
        description: lastAnalysis.description || null,
      }),
    });

    if (resp.status === 409) {
      msg.textContent = 'Already on your board';
    } else if (resp.ok) {
      msg.textContent = '✓ Saved to board!';
      btn.textContent = 'Saved ✓';
    } else {
      msg.textContent = 'Save failed';
      btn.disabled = false;
    }
  } catch {
    msg.textContent = 'Could not reach server';
    btn.disabled = false;
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function setLoading(on, msg = '') {
  document.getElementById('loading').classList.toggle('hidden', !on);
  document.getElementById('loading-msg').textContent = msg;
  document.getElementById('btn-analyze').disabled = on;
}

function hideResults() { document.getElementById('results').classList.add('hidden'); }
function hideError()   { document.getElementById('error-box').classList.add('hidden'); }

function showError(msg) {
  document.getElementById('error-msg').textContent = msg;
  document.getElementById('error-box').classList.remove('hidden');
}

function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
