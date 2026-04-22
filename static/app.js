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
