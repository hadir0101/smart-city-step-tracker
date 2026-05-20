async function loadStats() {
  const d = await fetch('/api/stats').then(r => r.json());
  document.getElementById('avg').textContent   = d.avg_daily.toLocaleString();
  document.getElementById('best').textContent  = d.best_day.toLocaleString();
  document.getElementById('days').textContent  = d.days_tracked;
  document.getElementById('goals').textContent = d.goal_days;
}

async function loadToday() {
  const d = await fetch('/api/today').then(r => r.json());
  document.getElementById('today-steps').textContent = d.steps.toLocaleString();
  document.getElementById('today-pct').textContent   = d.pct + '%';
  document.getElementById('today-date').textContent  = d.date;

  const fill = document.getElementById('progress-fill');
  fill.style.width      = d.pct + '%';
  fill.style.background = d.steps >= 10000 ? 'var(--green)'
                        : d.steps >= 5000  ? 'var(--accent)'
                        :                    'var(--orange)';
}

async function loadDailyChart() {
  const d = await fetch('/api/daily').then(r => r.json());

  const colors = d.values.map(v =>
    v >= 10000 ? 'rgba(104,211,145,0.8)' :
    v >= 5000  ? 'rgba(99,179,237,0.8)'  :
                 'rgba(246,173,85,0.8)'
  );

  new Chart(document.getElementById('dailyChart'), {
    type: 'bar',
    data: {
      labels: d.labels,
      datasets: [{ data: d.values, backgroundColor: colors, borderRadius: 4, borderSkipped: false }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.parsed.y.toLocaleString()} steps` } },
      },
      scales: {
        x: {
          ticks: { color: '#718096', font: { size: 10 }, maxRotation: 45 },
          grid:  { color: 'rgba(255,255,255,0.05)' },
        },
        y: {
          ticks: {
            color: '#718096',
            callback: v => v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v,
          },
          grid: { color: 'rgba(255,255,255,0.05)' },
        },
      },
    },
  });
}

loadStats();
loadToday();
loadDailyChart();

// ── Step Detection ────────────────────────────────────────────────────────────

function switchTab(tab) {
  document.getElementById('tab-csv').style.display  = tab === 'csv'  ? '' : 'none';
  document.getElementById('tab-live').style.display = tab === 'live' ? '' : 'none';
  document.querySelectorAll('.tab-btn').forEach((b, i) => {
    b.classList.toggle('active', (tab === 'csv' && i === 0) || (tab === 'live' && i === 1));
  });
  hideResults();
}

function showResults(data) {
  document.getElementById('detection-error').style.display = 'none';
  document.getElementById('detection-results').style.display = '';

  document.getElementById('det-steps').textContent    = data.steps.toLocaleString();
  document.getElementById('det-cadence').textContent  = data.cadence;
  document.getElementById('det-duration').textContent = data.duration_s;
  document.getElementById('det-fs').textContent       = data.fs;

  const cmp = document.getElementById('det-comparison');
  const val = data.validation;
  if (val) {
    const verdictEl = document.getElementById('det-verdict');
    document.getElementById('det-apple').textContent =
      data.apple_health
        ? data.apple_health.steps.toLocaleString() + ' steps (day total)'
        : '—';
    document.getElementById('det-diff').textContent =
      val.cadence + ' steps/min  (normal: ' + val.normal_range + ')';
    verdictEl.textContent = val.verdict;
    verdictEl.className   = 'verdict-badge verdict-' +
      val.verdict.toLowerCase().split(' ').join('-');
    cmp.style.display = '';
  } else {
    cmp.style.display = 'none';
  }
}

function showError(msg) {
  document.getElementById('detection-results').style.display = 'none';
  const el = document.getElementById('detection-error');
  el.textContent = msg;
  el.style.display = '';
}

function hideResults() {
  document.getElementById('detection-results').style.display = 'none';
  document.getElementById('detection-error').style.display   = 'none';
}

async function runCsv() {
  hideResults();
  const file = document.getElementById('csv-file').value.trim() || 'phyphox_data.csv';
  const date = document.getElementById('csv-date').value.trim();
  let url    = `/api/ingest/csv?file=${encodeURIComponent(file)}`;
  if (date) url += `&date=${date}`;

  const btn = document.querySelector('#tab-csv .run-btn');
  btn.textContent = 'Running...';
  btn.disabled    = true;

  try {
    const resp = await fetch(url);
    const data = await resp.json();
    if (!resp.ok) { showError(data.error || 'Detection failed.'); return; }
    showResults(data);
  } catch (e) {
    showError('Could not reach the server.');
  } finally {
    btn.textContent = 'Run Detection';
    btn.disabled    = false;
  }
}

async function runLive() {
  hideResults();
  const ip       = document.getElementById('live-ip').value.trim();
  const duration = parseInt(document.getElementById('live-dur').value) || 30;
  const date     = document.getElementById('live-date').value.trim();

  if (!ip) { showError('Enter the phone IP address (or 127.0.0.1 for mock server).'); return; }

  const btn       = document.querySelector('#tab-live .run-btn');
  const countdown = document.getElementById('live-countdown');
  const bar       = document.getElementById('live-bar');
  const status    = document.getElementById('live-status');

  btn.disabled    = true;
  btn.textContent = 'Collecting...';
  countdown.style.display = '';

  // Animate progress bar while fetch is in flight
  const start    = Date.now();
  const timer    = setInterval(() => {
    const elapsed = (Date.now() - start) / 1000;
    const pct     = Math.min(elapsed / duration * 100, 95);
    bar.style.width    = pct + '%';
    status.textContent = `Collecting... ${Math.floor(elapsed)}s / ${duration}s`;
  }, 300);

  try {
    const body = { ip, duration };
    if (date) body.date = date;

    const resp = await fetch('/api/ingest/live', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    clearInterval(timer);
    bar.style.width    = '100%';
    status.textContent = 'Done.';

    if (!resp.ok) { showError(data.error || 'Live detection failed.'); return; }
    showResults(data);
  } catch (e) {
    clearInterval(timer);
    showError('Could not reach the server or the phone.');
  } finally {
    btn.textContent = 'Start Live';
    btn.disabled    = false;
    setTimeout(() => { countdown.style.display = 'none'; bar.style.width = '0%'; }, 2000);
  }
}
