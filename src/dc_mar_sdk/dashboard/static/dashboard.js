const hoursEl = document.getElementById("hours");
const autoRefreshEl = document.getElementById("auto-refresh");
const refreshBtn = document.getElementById("refresh-btn");

const overviewEl = document.getElementById("overview");
const cacheEl = document.getElementById("cache");
const anomaliesEl = document.getElementById("anomalies");
const timeseriesEl = document.getElementById("timeseries");
const endpointRowsEl = document.getElementById("endpoint-rows");

let refreshTimer = null;

async function fetchJson(path) {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json();
}

function renderKeyValue(target, items) {
  const rows = Object.entries(items)
    .map(([key, value]) => `<dt>${key}</dt><dd>${value}</dd>`)
    .join("");
  target.innerHTML = `<dl>${rows}</dl>`;
}

function renderAnomalies(anomalies) {
  if (!anomalies.length) {
    anomaliesEl.innerHTML = "<li>No anomaly signals in this window.</li>";
    return;
  }
  anomaliesEl.innerHTML = anomalies
    .map((a) => `<li><strong>${a.kind}</strong>: ${a.message}</li>`)
    .join("");
}

function renderEndpoints(rows) {
  if (!rows.length) {
    endpointRowsEl.innerHTML = "<tr><td colspan='4'>No endpoint data yet.</td></tr>";
    return;
  }
  endpointRowsEl.innerHTML = rows
    .map(
      (row) =>
        `<tr><td>${row.endpoint}</td><td>${row.request_count}</td><td>${row.error_rate}%</td><td>${row.avg_response_time_ms.toFixed(1)}ms</td></tr>`,
    )
    .join("");
}

async function refreshAll() {
  const hours = Number(hoursEl.value);
  const [overview, timeseries, endpoints] = await Promise.all([
    fetchJson(`/api/insights/overview?hours=${hours}`),
    fetchJson(`/api/insights/timeseries?hours=${hours}&bucket=hour`),
    fetchJson(`/api/insights/endpoints?hours=${hours}&limit=20&sort_by=request_count`),
  ]);

  renderKeyValue(overviewEl, {
    requests: overview.api_stats.total_requests,
    errors: overview.api_stats.error_count,
    "avg latency (ms)": Number(overview.api_stats.avg_response_time_ms).toFixed(1),
    "cache hit rate (%)": Number(overview.api_stats.cache_hit_rate).toFixed(1),
    "data received (MB)": Number(overview.data_summary.total_data_received_mb).toFixed(2),
  });

  renderKeyValue(cacheEl, {
    backend: overview.cache_stats.backend,
    entries: overview.cache_stats.entries ?? 0,
    hits: overview.cache_stats.hits,
    misses: overview.cache_stats.misses,
    "hit rate (%)": Number(overview.cache_stats.hit_rate).toFixed(1),
  });

  renderAnomalies(overview.anomalies);
  timeseriesEl.textContent = JSON.stringify(timeseries.points, null, 2);
  renderEndpoints(endpoints.rows);
}

function installAutoRefresh() {
  if (refreshTimer) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
  if (autoRefreshEl.checked) {
    refreshTimer = window.setInterval(refreshAll, 30000);
  }
}

refreshBtn.addEventListener("click", refreshAll);
hoursEl.addEventListener("change", refreshAll);
autoRefreshEl.addEventListener("change", installAutoRefresh);

refreshAll();
installAutoRefresh();
