const state = {
  activeView: "alerts",
  overview: null,
  alerts: [],
  runs: [],
  events: [],
  selectedAlertId: null,
};

const byId = (id) => document.getElementById(id);
const escapeHTML = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character];
  });

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? escapeHTML(value)
    : date.toLocaleString("pt-BR", { timeZone: "UTC", hour12: false });
}

function eventPayload(row) {
  try {
    return JSON.parse(row.payload_json);
  } catch {
    return {};
  }
}

function alertDetails(alert) {
  try {
    return JSON.parse(alert.details_json);
  } catch {
    return {};
  }
}

function setNotice(message = "") {
  const notice = byId("notice");
  notice.textContent = message;
  notice.hidden = !message;
}

async function requestJSON(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Falha HTTP ${response.status}`);
  }
  return response.json();
}

function selectedRunId() {
  return byId("run-filter").value;
}

async function loadData() {
  const params = new URLSearchParams();
  if (byId("status-filter").value) params.set("status", byId("status-filter").value);
  if (byId("severity-filter").value) params.set("severity", byId("severity-filter").value);
  if (selectedRunId()) params.set("run_id", selectedRunId());

  const query = params.size ? `?${params.toString()}` : "";
  const [overview, runs, alerts, events] = await Promise.all([
    requestJSON("/api/overview"),
    requestJSON("/api/runs?limit=200"),
    requestJSON(`/api/alerts${query}`),
    requestJSON("/api/events?limit=1000"),
  ]);

  state.overview = overview;
  state.runs = runs;
  state.alerts = alerts;
  state.events = events;

  byId("connection-dot").className = "connection-dot is-online";
  byId("connection-label").textContent = "API conectada";
  byId("last-updated").textContent = `Atualizado ${new Date().toLocaleTimeString("pt-BR")}`;
  render();
  setNotice();
}

function renderMetrics() {
  const metrics = state.overview || {};
  byId("metric-open").textContent = metrics.open_alerts ?? 0;
  byId("metric-high").textContent = metrics.alerts_by_severity?.high ?? 0;
  byId("metric-events").textContent = metrics.events ?? 0;
  byId("metric-runs").textContent = metrics.runs ?? 0;
  byId("alert-count").textContent = state.alerts.length;
}

function renderRunFilters() {
  const filters = [byId("run-filter"), byId("events-run-filter")];
  for (const filter of filters) {
    const previous = filter.value;
    filter.innerHTML = '<option value="">Todas</option>' + state.runs.map((run) =>
      `<option value="${escapeHTML(run.run_id)}">${escapeHTML(run.scenario)} · ${formatTime(run.created_at)}</option>`,
    ).join("");
    if (state.runs.some((run) => run.run_id === previous)) filter.value = previous;
  }
}

function renderAlerts() {
  const body = byId("alerts-table-body");
  const empty = byId("alerts-empty");
  const alerts = state.alerts;
  if (!alerts.some((alert) => alert.alert_id === state.selectedAlertId)) {
    state.selectedAlertId = alerts[0]?.alert_id ?? null;
  }

  empty.hidden = alerts.length > 0;
  body.innerHTML = alerts.map((alert) => {
    const details = alertDetails(alert);
    const timestamp = details.window_start || details.timestamp || alert.created_at;
    const severity = escapeHTML(alert.severity.toLowerCase());
    return `<tr data-alert-id="${escapeHTML(alert.alert_id)}" tabindex="0" aria-selected="${alert.alert_id === state.selectedAlertId}">
      <td class="cell-time">${formatTime(timestamp)}</td>
      <td><span class="severity-badge severity-${severity}">${escapeHTML(alert.severity)}</span></td>
      <td class="cell-rule" title="${escapeHTML(alert.rule)}">${escapeHTML(alert.rule)}</td>
      <td class="cell-source">${escapeHTML(alert.source_ip || alert.scenario || "-")}</td>
      <td><span class="status-badge status-${escapeHTML(alert.status)}">${escapeHTML(alert.status)}</span></td>
    </tr>`;
  }).join("");

  body.querySelectorAll("[data-alert-id]").forEach((row) => {
    const select = () => {
      state.selectedAlertId = row.dataset.alertId;
      renderAlerts();
      renderAlertDetail();
    };
    row.addEventListener("click", select);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        select();
      }
    });
  });
  renderAlertDetail();
}

function relatedEvents(alert, details) {
  return state.events
    .filter((row) => row.run_id === alert.run_id)
    .map((row) => ({ row, payload: eventPayload(row) }))
    .filter(({ payload }) => {
      if (alert.source_ip && payload.source_ip === alert.source_ip) return true;
      return Boolean(
        (alert.username && payload.username === alert.username) ||
        (details.hostname && payload.hostname === details.hostname),
      );
    })
    .sort((left, right) => left.row.timestamp.localeCompare(right.row.timestamp))
    .slice(0, 8);
}

function renderAlertDetail() {
  const alert = state.alerts.find((item) => item.alert_id === state.selectedAlertId);
  byId("detail-empty").hidden = Boolean(alert);
  byId("detail-content").hidden = !alert;
  if (!alert) return;

  const details = alertDetails(alert);
  const severity = alert.severity.toLowerCase();
  byId("detail-severity").className = `severity-badge severity-${escapeHTML(severity)}`;
  byId("detail-severity").textContent = alert.severity;
  byId("detail-rule-id").textContent = `${alert.scenario} / ${alert.rule}`;
  byId("detail-title").textContent = alert.rule.replaceAll("_", " ");
  byId("detail-summary").textContent = alert.summary;

  const facts = [
    ["IP de origem", alert.source_ip],
    ["Usuário", alert.username],
    ["Início da janela", details.window_start],
    ["Fim da janela", details.window_end || details.correlated_success_at],
  ].filter(([, value]) => value);
  byId("detail-facts").innerHTML = facts.map(([label, value]) =>
    `<div><dt>${escapeHTML(label)}</dt><dd>${escapeHTML(value)}</dd></div>`,
  ).join("");

  const related = relatedEvents(alert, details);
  const timeline = byId("event-timeline");
  timeline.innerHTML = related.length
    ? related.map(({ row, payload }) => {
      const description = [
        payload.outcome,
        payload.username,
        payload.source_ip,
        payload.destination_port ? `porta ${payload.destination_port}` : "",
        payload.process_name,
      ].filter(Boolean).join(" · ");
      return `<li><time>${formatTime(row.timestamp).split(" ").at(-1)}</time><span>${escapeHTML(description || row.event_type)}</span></li>`;
    }).join("")
    : '<li class="timeline-empty">Sem eventos relacionados nesta execução.</li>';

  byId("triage-status").value = alert.status;
  byId("triage-notes").value = alert.analyst_notes;
}

function renderEvents() {
  const runId = byId("events-run-filter").value;
  const events = runId ? state.events.filter((event) => event.run_id === runId) : state.events;
  byId("events-empty").hidden = events.length > 0;
  byId("events-table-body").innerHTML = events.map((row) => {
    const payload = eventPayload(row);
    const origin = payload.source_ip || payload.destination_ip || "-";
    return `<tr>
      <td class="cell-time">${formatTime(row.timestamp)}</td>
      <td>${escapeHTML(row.event_type)}</td>
      <td>${escapeHTML(origin)}</td>
      <td>${escapeHTML(payload.username || "-")}</td>
      <td>${escapeHTML(payload.outcome || "-")}</td>
      <td>${escapeHTML(payload.hostname || "-")}</td>
    </tr>`;
  }).join("");
}

function renderRuns() {
  byId("runs-empty").hidden = state.runs.length > 0;
  byId("runs-table-body").innerHTML = state.runs.map((run) => `
    <tr>
      <td class="cell-time">${formatTime(run.created_at)}</td>
      <td>${escapeHTML(run.scenario)}</td>
      <td>${run.event_count}</td>
      <td>${run.alert_count}</td>
      <td class="run-id">${escapeHTML(run.run_id.slice(0, 12))}</td>
    </tr>`).join("");
}

function render() {
  renderMetrics();
  renderRunFilters();
  renderAlerts();
  renderEvents();
  renderRuns();
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    state.activeView = button.dataset.view;
    document.querySelectorAll("[data-view]").forEach((tab) => {
      tab.classList.toggle("is-active", tab === button);
    });
    byId("alerts-view").hidden = state.activeView !== "alerts";
    byId("events-view").hidden = state.activeView !== "events";
    byId("runs-view").hidden = state.activeView !== "runs";
    byId("alert-filters").hidden = state.activeView !== "alerts";
  });
});

for (const id of ["status-filter", "severity-filter", "run-filter"]) {
  byId(id).addEventListener("change", () => {
    loadData().catch((error) => setNotice(error.message));
  });
}

byId("events-run-filter").addEventListener("change", renderEvents);
byId("refresh-button").addEventListener("click", () => {
  loadData().catch((error) => setNotice(error.message));
});

byId("triage-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedAlertId) return;
  try {
    await requestJSON(`/api/alerts/${encodeURIComponent(state.selectedAlertId)}/triage`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: byId("triage-status").value,
        analyst_notes: byId("triage-notes").value,
      }),
    });
    await loadData();
    setNotice("Triagem salva.");
  } catch (error) {
    setNotice(error.message);
  }
});

loadData().catch((error) => {
  byId("connection-dot").className = "connection-dot is-offline";
  byId("connection-label").textContent = "API indisponível";
  setNotice(error.message);
});