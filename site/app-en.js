const state = {
  config: null,
  participant: null,
  catalog: [],
  catalogFilter: "all",
  authMode: "login",
  activeItem: null,
  draftRevision: 0,
  activeSeconds: 0,
  activeTimer: null,
  saveTimer: null,
  saving: false,
  saveQueued: false,
  adminToken: "",
  adminSummary: null,
  adminTab: "items",
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const ROUTE_CANVAS = Object.freeze({
  width: 1280,
  height: 720,
  gridPixels: 496,
  gridY: 126,
  gridXs: [66, 704],
  agentColors: ["#D55E00", "#0072B2", "#CC79A7", "#009E73"],
});

class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers,
  });
  const contentType = response.headers.get("Content-Type") || "";
  const payload = contentType.includes("json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    throw new ApiError(
      payload?.message || `Request failed (${response.status})`,
      response.status,
      payload,
    );
  }
  return payload;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return "0:00";
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

function toast(message, type = "success") {
  const element = document.createElement("div");
  element.className = `toast ${type === "error" ? "error" : ""}`;
  element.textContent = message;
  $("#toast-region").append(element);
  window.setTimeout(() => element.remove(), 4200);
}

function showView(name) {
  $$(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `${name}-view`);
  });
  const signedIn = Boolean(state.participant);
  $("#directory-button").classList.toggle("hidden", !signedIn || name === "dashboard");
  $("#profile-button").classList.toggle("hidden", !signedIn);
  $("#profile-popover").classList.add("hidden");
  if (name !== "judge") {
    stopActiveTimer();
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function setIntegrity(config) {
  const chip = $("#integrity-chip");
  const complete = config.artifact_status === "complete_frozen_artifacts";
  chip.classList.toggle("verified", complete);
  chip.innerHTML = complete
    ? '<span class="status-dot"></span>Public artifacts frozen and verified'
    : '<span class="status-dot"></span>Interface preview · collection service unavailable';
  $("#manifest-footer").textContent =
    `Manifest ${config.public_manifest_sha256.slice(0, 12)}...`;
}

function renderConfig() {
  const config = state.config;
  const itemCount = Number(config.items_per_rater);
  const mapCount = Number(config.map_count);
  const itemsPerMap =
    Number(config.items_per_map) ||
    (Number.isInteger(itemCount) && Number.isInteger(mapCount)
      ? itemCount / mapCount
      : 0);
  $("#metric-maps").textContent = config.map_count;
  $("#metric-personal").textContent = config.items_per_rater;
  $("#metric-votes").textContent = config.judgments_per_item;
  const unlockLabel = $("#tutorial-unlock-label");
  if (unlockLabel) {
    unlockLabel.textContent = `Unlock my complete ${itemCount}-item catalog`;
  }
  const progressTotal = $("#progress-total");
  if (progressTotal) {
    progressTotal.textContent = `/ ${itemCount}`;
  }
  const catalogDescription = $("#catalog-description");
  if (catalogDescription) {
    catalogDescription.textContent =
      `The catalog contains ${itemCount} items. You may complete it over multiple sessions and revise submitted choices.`;
  }
  const catalogSizeLabel = $("#catalog-size-label");
  if (catalogSizeLabel) {
    catalogSizeLabel.textContent =
      `${itemCount} items · ${mapCount} maps · ${itemsPerMap} comparisons per map`;
  }
  const adminItemsTab = $("#admin-items-tab");
  if (adminItemsTab) {
    adminItemsTab.textContent = `${itemCount}-item coverage`;
  }
  $("#study-mode-label").textContent =
    ["formal", "formal_collection"].includes(config.study_mode)
      ? "INTERNAL EVALUATION"
      : "EVALUATION";
  $("#consent-copy").textContent = config.consent_text;
  $("#registration-note").classList.toggle("hidden", config.registration_open);
  $("#register-tab").disabled = !config.registration_open;
  $("#register-tab").title = config.registration_open
    ? ""
    : "New participant registration is not open";
  setIntegrity(config);
}

function updateProfile() {
  if (!state.participant) return;
  const name = state.participant.username;
  $("#avatar-initial").textContent = [...name][0]?.toUpperCase() || "R";
  $("#profile-username").textContent = name;
  $("#profile-rater-id").textContent = state.participant.rater_id;
}

function setAuthMode(mode) {
  if (mode === "register" && !state.config.registration_open) {
    toast("New participant registration is not open.", "error");
    return;
  }
  state.authMode = mode;
  $("#login-tab").classList.toggle("active", mode === "login");
  $("#register-tab").classList.toggle("active", mode === "register");
  $("#login-tab").setAttribute("aria-selected", mode === "login");
  $("#register-tab").setAttribute("aria-selected", mode === "register");
  $("#consent-box").classList.toggle("hidden", mode !== "register");
  $("#auth-submit").innerHTML =
    mode === "register"
      ? 'Create anonymous slot <span aria-hidden="true">→</span>'
      : 'Load existing progress <span aria-hidden="true">→</span>';
  $("#pin-input").autocomplete =
    mode === "register" ? "new-password" : "current-password";
  $("#auth-error").classList.add("hidden");
}

async function submitAuth(event) {
  event.preventDefault();
  const error = $("#auth-error");
  const submit = $("#auth-submit");
  error.classList.add("hidden");
  submit.disabled = true;
  const body = {
    username: $("#username-input").value.trim(),
    pin: $("#pin-input").value,
  };
  if (state.authMode === "register") {
    body.consented = $("#consent-checkbox").checked;
  }
  try {
    const result = await api(`/api/auth/${state.authMode}`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    state.participant = result.participant;
    updateProfile();
    toast(
      state.authMode === "register"
        ? `Assigned anonymous ID ${state.participant.rater_id}`
        : "restored progress from this browser.",
    );
    if (state.participant.tutorial_completed) {
      await loadDashboard();
    } else {
      showView("tutorial");
    }
  } catch (requestError) {
    error.textContent = requestError.message;
    error.classList.remove("hidden");
  } finally {
    submit.disabled = false;
  }
}

async function finishTutorial() {
  const button = $("#finish-tutorial");
  button.disabled = true;
  try {
    await api("/api/tutorial/complete", {
      method: "POST",
      body: JSON.stringify({ completed: true }),
    });
    state.participant.tutorial_completed = true;
    toast("Instructions completed; your catalog is unlocked.");
    await loadDashboard();
  } catch (error) {
    toast(error.message, "error");
    button.disabled = false;
  }
}

function statusLabel(status) {
  return {
    not_started: "Not started",
    in_progress: "In progress",
    draft: "Draft",
    submitted: "Submitted",
  }[status] || status;
}

function renderCatalog() {
  const list = $("#catalog-list");
  const filtered = state.catalog.filter((item) => {
    if (state.catalogFilter === "submitted") return item.status === "submitted";
    if (state.catalogFilter === "open") return item.status !== "submitted";
    return true;
  });
  list.innerHTML = filtered
    .map(
      (item) => `
        <button
          class="catalog-item ${escapeHtml(item.status)}"
          type="button"
          data-item-id="${escapeHtml(item.item_id)}"
        >
          <span class="catalog-number">${String(item.catalog_number).padStart(2, "0")}</span>
          <span class="catalog-copy">
            <strong>${escapeHtml(item.blind_map_id.replace("_", " ").toUpperCase())}</strong>
            <span>${escapeHtml(item.item_id)}</span>
          </span>
          <span class="status-label">${statusLabel(item.status)}</span>
        </button>
      `,
    )
    .join("");
  if (!filtered.length) {
    list.innerHTML =
      '<p class="empty-state">No items match this filter.</p>';
  }
  $$("[data-item-id]", list).forEach((button) => {
    button.addEventListener("click", () => openItem(button.dataset.itemId));
  });
}

function updateDashboardStats() {
  const completed = state.catalog.filter((item) => item.status === "submitted").length;
  const total = state.catalog.length || state.config.items_per_rater;
  const percent = Math.round((completed / total) * 100);
  state.participant.completed = completed;
  $("#progress-value").textContent = completed;
  $("#progress-ring").style.setProperty("--progress", percent);
  $("#progress-bar-fill").style.width = `${percent}%`;
  $("#welcome-name").textContent = `Welcome, ${state.participant.username}`;
  $("#rater-id-label").textContent =
    `${state.participant.rater_id} · ${
      ["formal", "formal_collection"].includes(state.config.study_mode)
        ? "Internal evaluation"
        : "Evaluation"
    }`;
  $("#catalog-summary").textContent =
    `Submitted ${completed} items; ${total - completed} remaining. Submitted choices may still be revised.`;
  const next = state.catalog.find((item) => item.status !== "submitted");
  const button = $("#resume-button");
  if (next) {
    button.disabled = false;
    button.innerHTML =
      `${next.status === "not_started" ? "Start" : "Continue"} item ${next.catalog_number} <span aria-hidden="true">→</span>`;
    button.onclick = () => openItem(next.item_id);
    $("#progress-message").textContent =
      completed === 0
        ? "You may split the catalog across sessions; use the same pseudonym and PIN to resume."
        : "Progress is saved in this browser; continue now or return later.";
  } else {
    button.disabled = true;
    button.textContent = `${total} items complete`;
    $("#progress-message").textContent =
      "Thank you for completing the catalog. You may still export your anonymous backup.";
  }
}

async function loadDashboard() {
  try {
    const [catalogResult, meResult] = await Promise.all([
      api("/api/catalog"),
      api("/api/me"),
    ]);
    state.catalog = catalogResult.items;
    if (meResult.authenticated) {
      state.participant = meResult.participant;
    }
    updateProfile();
    updateDashboardStats();
    renderCatalog();
    showView("dashboard");
  } catch (error) {
    if (error.status === 401) {
      state.participant = null;
      showView("auth");
    }
    toast(error.message, "error");
  }
}


function ratingSection() {
  return `
    <section class="rating-section" data-choice-section>
      <header class="rating-heading">
        <span class="endpoint-number">Choice</span>
        <div>
          <h2>Which route is better overall, Route A or Route B?</h2>
          <p>Using the task instruction and the two anonymous route maps, choose one route overall. Do not separately judge completion or assign dimension scores.</p>
        </div>
        <span class="endpoint-tag">A/B forced choice</span>
      </header>
      <div class="pairwise-choice-group" role="radiogroup" aria-label="Choose the better route overall">
        <label class="pairwise-choice-card">
          <input type="radio" name="pairwise-choice" value="A" data-rating-field>
          <span><strong>A</strong>Choose Route A</span>
        </label>
        <label class="pairwise-choice-card">
          <input type="radio" name="pairwise-choice" value="B" data-rating-field>
          <span><strong>B</strong>Choose Route B</span>
        </label>
      </div>
    </section>
  `;
}

function localDraftKey(itemId) {
  return [
    "tbam-draft",
    state.config.storage_namespace_id,
    state.participant.rater_id,
    itemId,
  ].join(":");
}


function applyDraft(draft) {
  const choice = draft?.payload?.choice;
  state.activeSeconds = Number(draft?.active_seconds || 0);
  state.draftRevision = Number(draft?.revision || 0);
  if (choice === "A" || choice === "B") {
    const input = document.querySelector(
      `input[name="pairwise-choice"][value="${choice}"]`,
    );
    if (input) input.checked = true;
  }
}

function draftPayload() {
  const selected = document.querySelector(
    'input[name="pairwise-choice"]:checked',
  );
  return { choice: selected?.value || null };
}

function finalChoice() {
  const choice = draftPayload().choice;
  if (choice !== "A" && choice !== "B") {
    document
      .querySelector("[data-choice-section]")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
    throw new Error("Please choose Route A or Route B.");
  }
  return choice;
}

function setSaveState(label, saved = false) {
  const element = $("#save-state");
  element.classList.toggle("saved", saved);
  element.innerHTML = `<span class="status-dot"></span>${escapeHtml(label)}`;
}

function saveLocalDraft() {
  if (!state.activeItem || !state.participant) return;
  try {
    localStorage.setItem(
      localDraftKey(state.activeItem.item_id),
      JSON.stringify({
        payload: draftPayload(),
        active_seconds: state.activeSeconds,
        saved_utc: new Date().toISOString(),
      }),
    );
  } catch {
    // Browser-local persistence remains authoritative.
  }
}

function scheduleDraftSave() {
  if (!state.activeItem) return;
  saveLocalDraft();
  setSaveState("Unsaved changes", false);
  window.clearTimeout(state.saveTimer);
  state.saveTimer = window.setTimeout(() => saveDraft(false), 900);
}

async function saveDraft(showConfirmation = false) {
  if (!state.activeItem) return;
  if (state.saving) {
    state.saveQueued = true;
    return;
  }
  state.saving = true;
  setSaveState("Saving draft...", false);
  try {
    const result = await api(`/api/item/${state.activeItem.item_id}/draft`, {
      method: "PUT",
      body: JSON.stringify({
        payload: draftPayload(),
        active_seconds: state.activeSeconds,
        expected_revision: state.draftRevision,
      }),
    });
    state.draftRevision = result.revision;
    setSaveState(`Draft saved · v${result.revision}`, true);
    if (showConfirmation) toast("draft saved in this browser.");
  } catch (error) {
    if (error.status === 409 && error.payload?.detail) {
      applyDraft(error.payload.detail);
      setSaveState("Loaded the version from another tab", true);
      toast("Another tab changed this item; its latest browser draft was loaded.", "error");
    } else {
      setSaveState("Browser save failed; the local draft was retained", false);
      if (showConfirmation) toast(error.message, "error");
    }
  } finally {
    state.saving = false;
    if (state.saveQueued) {
      state.saveQueued = false;
      window.setTimeout(() => saveDraft(false), 0);
    }
  }
}


function updateCharacterCounts() {}

function bindRatingEvents() {
  const form = document.querySelector("#rating-form");
  form.oninput = (event) => {
    if (event.target.matches("[data-rating-field]")) {
      scheduleDraftSave();
    }
  };
  form.onclick = null;
  form.onkeydown = null;
  form.onchange = null;
}

function startActiveTimer() {
  stopActiveTimer();
  state.activeTimer = window.setInterval(() => {
    if (
      state.activeItem &&
      $("#judge-view").classList.contains("active") &&
      !document.hidden
    ) {
      state.activeSeconds += 1;
      saveLocalDraft();
    }
  }, 1000);
}

function stopActiveTimer() {
  if (state.activeTimer) window.clearInterval(state.activeTimer);
  state.activeTimer = null;
}

function interpolateColor(palette, value) {
  const bounded = Math.max(0, Math.min(1, Number(value)));
  const scaled = bounded * (palette.length - 1);
  const lower = Math.min(palette.length - 2, Math.floor(scaled));
  const fraction = scaled - lower;
  const rgb = palette[lower].map((channel, index) =>
    Math.round(channel * (1 - fraction) + palette[lower + 1][index] * fraction),
  );
  return `rgb(${rgb.join(",")})`;
}

function matrixShape(values, label) {
  if (!Array.isArray(values) || values.length === 0) {
    throw new Error(`${label} data is empty.`);
  }
  const columns = Array.isArray(values[0]) ? values[0].length : 0;
  if (
    columns === 0 ||
    values.some(
      (row) =>
        !Array.isArray(row) ||
        row.length !== columns ||
        row.some((value) => !Number.isFinite(Number(value))),
    )
  ) {
    throw new Error(`${label} data dimensions are invalid.`);
  }
  return { rows: values.length, columns };
}

function routeGeometry(map) {
  const heightShape = matrixShape(map.height, "Elevation map");
  const coverShape = matrixShape(map.cover, "Cover map");
  if (
    heightShape.rows !== coverShape.rows ||
    heightShape.columns !== coverShape.columns ||
    heightShape.rows !== heightShape.columns ||
    ![8, 16, 24, 32].includes(heightShape.rows)
  ) {
    throw new Error("Route maps must be supported 8, 16, 24, or 32 square grids.");
  }
  return {
    rows: heightShape.rows,
    columns: heightShape.columns,
    cellWidth: ROUTE_CANVAS.gridPixels / heightShape.columns,
    cellHeight: ROUTE_CANVAS.gridPixels / heightShape.rows,
    gridWidth: ROUTE_CANVAS.gridPixels,
    gridHeight: ROUTE_CANVAS.gridPixels,
  };
}

function cellCenter(gridX, position, geometry) {
  return [
    gridX + (Number(position[1]) + 0.5) * geometry.cellWidth,
    ROUTE_CANVAS.gridY + (Number(position[0]) + 0.5) * geometry.cellHeight,
  ];
}

function routeHorizon(routeInput) {
  const mapSize = routeInput.map.height.length;
  const horizon = Number(routeInput.map.max_steps);
  if (horizon !== mapSize * 6 || ![48, 96, 144, 192].includes(horizon)) {
    throw new Error("The route horizon does not match the map size.");
  }
  return horizon;
}

function checkpointTimes(horizon) {
  return Array.from({ length: 6 }, (_, index) =>
    Math.round((horizon * index) / 5),
  );
}

function drawStar(context, centerX, centerY, outerRadius = 14, innerRadius = 6) {
  context.beginPath();
  for (let index = 0; index < 10; index += 1) {
    const angle = -Math.PI / 2 + index * Math.PI / 5;
    const radius = index % 2 === 0 ? outerRadius : innerRadius;
    const x = centerX + radius * Math.cos(angle);
    const y = centerY + radius * Math.sin(angle);
    if (index === 0) context.moveTo(x, y);
    else context.lineTo(x, y);
  }
  context.closePath();
  context.fillStyle = "#ffcd00";
  context.fill();
  context.strokeStyle = "#101010";
  context.lineWidth = 2;
  context.stroke();
}

function drawMapPanel(context, values, gridX, title, kind, geometry) {
  const palettes = {
    height: [[43, 73, 121], [72, 132, 86], [188, 173, 118], [245, 245, 238]],
    cover: [[255, 251, 230], [183, 220, 187], [67, 141, 111], [16, 71, 52]],
  };
  const palette = palettes[kind];
  context.fillStyle = "#141414";
  context.font = "700 24px system-ui, sans-serif";
  context.fillText(title, gridX, ROUTE_CANVAS.gridY - 22);
  for (let row = 0; row < geometry.rows; row += 1) {
    for (let column = 0; column < geometry.columns; column += 1) {
      const normalized =
        kind === "height" ? Number(values[row][column]) / 5 : Number(values[row][column]);
      context.fillStyle = interpolateColor(palette, normalized);
      context.fillRect(
        gridX + column * geometry.cellWidth,
        ROUTE_CANVAS.gridY + row * geometry.cellHeight,
        geometry.cellWidth,
        geometry.cellHeight,
      );
    }
  }
  context.strokeStyle = "rgba(35, 35, 35, 0.62)";
  context.lineWidth = geometry.rows >= 24 ? 0.6 : 1;
  for (let offset = 0; offset <= geometry.rows; offset += 1) {
    const y = ROUTE_CANVAS.gridY + offset * geometry.cellHeight;
    context.beginPath();
    context.moveTo(gridX, y);
    context.lineTo(gridX + geometry.gridWidth, y);
    context.stroke();
  }
  for (let offset = 0; offset <= geometry.columns; offset += 1) {
    const x = gridX + offset * geometry.cellWidth;
    context.beginPath();
    context.moveTo(x, ROUTE_CANVAS.gridY);
    context.lineTo(x, ROUTE_CANVAS.gridY + geometry.gridHeight);
    context.stroke();
  }
  context.strokeStyle = "#080808";
  context.lineWidth = 2;
  context.strokeRect(
    gridX,
    ROUTE_CANVAS.gridY,
    geometry.gridWidth,
    geometry.gridHeight,
  );

  const barY = ROUTE_CANVAS.gridY + geometry.gridHeight + 15;
  for (let pixel = 0; pixel < geometry.gridWidth; pixel += 1) {
    context.fillStyle = interpolateColor(palette, pixel / (geometry.gridWidth - 1));
    context.fillRect(gridX + pixel, barY, 1, 14);
  }
  context.strokeStyle = "#282828";
  context.lineWidth = 1;
  context.strokeRect(gridX, barY, geometry.gridWidth, 14);
  context.fillStyle = "#202020";
  context.font = "16px system-ui, sans-serif";
  context.fillText(kind === "height" ? "0 low" : "0 exposed", gridX, barY + 34);
  const highLabel = kind === "height" ? "5 high" : "1 concealed";
  context.textAlign = "right";
  context.fillText(highLabel, gridX + geometry.gridWidth, barY + 34);
  context.textAlign = "left";
}

function markerCenters(gridX, positions, geometry) {
  const groups = new Map();
  positions.forEach((position, agent) => {
    const key = `${position[0]},${position[1]}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(agent);
  });
  const centers = Array(positions.length);
  for (const agents of groups.values()) {
    const base = cellCenter(gridX, positions[agents[0]], geometry);
    agents.forEach((agent, index) => {
      if (agents.length === 1) {
        centers[agent] = base;
      } else {
        const angle = -Math.PI / 2 + 2 * Math.PI * index / agents.length;
        const offset = Math.max(
          3,
          Math.min(8, Math.min(geometry.cellWidth, geometry.cellHeight) * 0.25),
        );
        centers[agent] = [
          base[0] + offset * Math.cos(angle),
          base[1] + offset * Math.sin(angle),
        ];
      }
    });
  }
  return centers;
}

function drawRouteTrace(context, gridX, trajectory, geometry) {
  const agentCount = trajectory[0].positions.length;
  const colorWidth = Math.max(
    2,
    Math.min(5, Math.min(geometry.cellWidth, geometry.cellHeight) * 0.18),
  );
  for (let agent = 0; agent < agentCount; agent += 1) {
    const points = trajectory.map((stateFrame) =>
      cellCenter(gridX, stateFrame.positions[agent], geometry),
    );
    for (const [strokeStyle, lineWidth] of [["rgba(255,255,255,0.9)", colorWidth + 3], [
      ROUTE_CANVAS.agentColors[agent % ROUTE_CANVAS.agentColors.length],
      colorWidth,
    ]]) {
      context.beginPath();
      points.forEach(([x, y], index) => {
        if (index === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      });
      context.strokeStyle = strokeStyle;
      context.lineWidth = lineWidth;
      context.lineCap = "round";
      context.lineJoin = "round";
      context.stroke();
    }
  }
}

function drawCheckpointMarkers(
  context,
  gridX,
  trajectory,
  geometry,
  times,
) {
  const radius = Math.max(
    4,
    Math.min(8, Math.min(geometry.cellWidth, geometry.cellHeight) * 0.24),
  );
  times.forEach((time, checkpointIndex) => {
    const frame = trajectory[Math.min(time, trajectory.length - 1)];
    const centers = markerCenters(gridX, frame.positions, geometry);
    centers.forEach(([x, y], agent) => {
      context.beginPath();
      context.arc(x, y, radius, 0, Math.PI * 2);
      context.fillStyle =
        ROUTE_CANVAS.agentColors[agent % ROUTE_CANVAS.agentColors.length];
      context.fill();
      context.strokeStyle = "#ffffff";
      context.lineWidth = 2;
      context.stroke();
      context.fillStyle = "#ffffff";
      context.font = `700 ${Math.max(7, Math.round(radius * 1.1))}px system-ui, sans-serif`;
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.fillText(String(checkpointIndex), x, y + 0.5);
    });
  });
  context.textAlign = "left";
  context.textBaseline = "alphabetic";
}

function drawEndpoints(context, gridX, map, trajectory, geometry) {
  const [startX, startY] = cellCenter(gridX, map.start, geometry);
  const [goalX, goalY] = cellCenter(gridX, map.goal, geometry);
  const endpointRadius = Math.max(
    6,
    Math.min(12, Math.min(geometry.cellWidth, geometry.cellHeight) * 0.38),
  );
  context.fillStyle = "#ffffff";
  context.strokeStyle = "#000000";
  context.lineWidth = 2;
  context.fillRect(
    startX - endpointRadius,
    startY - endpointRadius,
    endpointRadius * 2,
    endpointRadius * 2,
  );
  context.strokeRect(
    startX - endpointRadius,
    startY - endpointRadius,
    endpointRadius * 2,
    endpointRadius * 2,
  );
  drawStar(
    context,
    goalX,
    goalY,
    endpointRadius * 1.15,
    endpointRadius * 0.5,
  );

  const finalFrame = trajectory[trajectory.length - 1];
  const centers = markerCenters(gridX, finalFrame.positions, geometry);
  centers.forEach(([x, y], agent) => {
    context.beginPath();
    context.arc(x, y, endpointRadius, 0, Math.PI * 2);
    context.fillStyle =
      ROUTE_CANVAS.agentColors[agent % ROUTE_CANVAS.agentColors.length];
    context.fill();
    context.strokeStyle = "#ffffff";
    context.lineWidth = 3;
    context.stroke();
    context.fillStyle = "#ffffff";
    context.font =
      `700 ${Math.max(9, Math.round(endpointRadius * 1.2))}px system-ui, sans-serif`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(String(agent + 1), x, y);
  });
  context.textAlign = "left";
  context.textBaseline = "alphabetic";
}

function drawRouteLegend(context, agentCount) {
  const legendX = 568;
  const legendY = 126;
  const agentStartY = 180;
  const rowStep = 29;
  const startY = agentStartY + agentCount * rowStep + 4;
  const goalY = startY + 37;
  const legendHeight = goalY - legendY + 22;
  context.fillStyle = "rgba(255,255,255,0.96)";
  context.strokeStyle = "#aaaaaa";
  context.lineWidth = 1;
  context.fillRect(legendX, legendY, 118, legendHeight);
  context.strokeRect(legendX, legendY, 118, legendHeight);
  context.fillStyle = "#141414";
  context.font = "700 18px system-ui, sans-serif";
  context.fillText("Legend", 580, 151);
  ROUTE_CANVAS.agentColors.slice(0, agentCount).forEach((color, index) => {
    context.beginPath();
    context.arc(587, agentStartY + index * rowStep, 8, 0, Math.PI * 2);
    context.fillStyle = color;
    context.fill();
    context.fillStyle = "#202020";
    context.font = "14px system-ui, sans-serif";
    context.fillText(`agent ${index + 1}`, 603, agentStartY + 5 + index * rowStep);
  });
  context.fillStyle = "#ffffff";
  context.strokeStyle = "#000000";
  context.lineWidth = 2;
  context.fillRect(579, startY - 8, 16, 16);
  context.strokeRect(579, startY - 8, 16, 16);
  context.fillStyle = "#202020";
  context.font = "15px system-ui, sans-serif";
  context.fillText("start", 605, startY + 5);
  drawStar(context, 587, goalY, 10, 4);
  context.fillStyle = "#202020";
  context.fillText("goal", 605, goalY + 5);
}

function validateRouteInput(payload) {
  if (
    payload?.schema_version !== "tbam.blind_judge_input.v1" ||
    !Array.isArray(payload?.map?.height) ||
    !Array.isArray(payload?.map?.cover) ||
    !Array.isArray(payload?.map?.start) ||
    payload.map.start.length !== 2 ||
    !Array.isArray(payload?.map?.goal) ||
    payload.map.goal.length !== 2
  ) {
    throw new Error("Invalid anonymous route data format.");
  }
  const geometry = routeGeometry(payload.map);
  const horizon = routeHorizon(payload);
  const declaredAgentCount = Number(payload.map.agent_count);
  if (![2, 3, 4].includes(declaredAgentCount)) {
    throw new Error("The route map declares an invalid agent count.");
  }
  let expectedAgentCount = null;
  for (const arm of ["A", "B"]) {
    const route = payload?.routes?.[arm];
    const trajectory = route?.trajectory;
    if (
      typeof route?.completed !== "boolean" ||
      !Object.hasOwn(route || {}, "completion_step") ||
      !Array.isArray(trajectory) ||
      trajectory.length === 0 ||
      !Array.isArray(trajectory[0]?.positions) ||
      trajectory[0].positions.length < 2 ||
      trajectory[0].positions.length > 4
    ) {
      throw new Error(`Route ${arm} trajectory data is incomplete.`);
    }
    const agentCount = trajectory[0].positions.length;
    if (agentCount !== declaredAgentCount) {
      throw new Error("The route agent count does not match the map declaration.");
    }
    if (expectedAgentCount !== null && agentCount !== expectedAgentCount) {
      throw new Error("Routes A and B have different agent counts.");
    }
    expectedAgentCount = agentCount;
    for (const frame of trajectory) {
      if (
        !Array.isArray(frame?.positions) ||
        frame.positions.length !== agentCount ||
        frame.positions.some(
          (position) =>
            !Array.isArray(position) ||
            position.length !== 2 ||
            !Number.isInteger(Number(position[0])) ||
            !Number.isInteger(Number(position[1])) ||
            Number(position[0]) < 0 ||
            Number(position[0]) >= geometry.rows ||
            Number(position[1]) < 0 ||
            Number(position[1]) >= geometry.columns,
        )
      ) {
        throw new Error(`Route ${arm} contains an out-of-bounds or invalid trajectory position.`);
      }
    }
    if (trajectory.length > horizon + 1) {
      throw new Error(`Route ${arm} trajectory length exceeds the declared horizon.`);
    }
  }
  return { geometry, horizon, agentCount: expectedAgentCount };
}

function renderRouteCanvas(canvas, routeInput, arm) {
  const context = canvas.getContext("2d");
  if (!context) throw new Error("This browser does not support the route-map canvas.");
  const trajectory = routeInput.routes[arm].trajectory;
  const geometry = routeGeometry(routeInput.map);
  const horizon = routeHorizon(routeInput);
  const times = checkpointTimes(horizon);
  const agentCount = trajectory[0].positions.length;
  canvas.width = ROUTE_CANVAS.width;
  canvas.height = ROUTE_CANVAS.height;
  context.fillStyle = "#f8f8f6";
  context.fillRect(0, 0, ROUTE_CANVAS.width, ROUTE_CANVAS.height);
  context.fillStyle = "#1e2b3b";
  context.fillRect(0, 0, ROUTE_CANVAS.width, 72);
  context.fillStyle = "#ffffff";
  context.font = "700 30px system-ui, sans-serif";
  context.fillText(`Route ${arm} · full trace`, 32, 46);
  context.textAlign = "right";
  context.font = "22px system-ui, sans-serif";
  context.fillText(`time marks 0–5 = t ${times.join(", ")}`, 1248, 45);
  context.textAlign = "left";

  drawMapPanel(
    context,
    routeInput.map.height,
    ROUTE_CANVAS.gridXs[0],
    "Elevation",
    "height",
    geometry,
  );
  drawMapPanel(
    context,
    routeInput.map.cover,
    ROUTE_CANVAS.gridXs[1],
    "Cover",
    "cover",
    geometry,
  );
  for (const gridX of ROUTE_CANVAS.gridXs) {
    drawRouteTrace(context, gridX, trajectory, geometry);
    drawEndpoints(context, gridX, routeInput.map, trajectory, geometry);
  }
  drawCheckpointMarkers(
    context,
    ROUTE_CANVAS.gridXs[1],
    trajectory,
    geometry,
    times,
  );
  drawRouteLegend(context, agentCount);
}

async function configureRouteMaps() {
  $$(".route-map-loading").forEach((element) => element.classList.remove("hidden"));
  for (const canvas of [$("#route-map-a"), $("#route-map-b")]) {
    const context = canvas.getContext("2d");
    context?.clearRect(0, 0, canvas.width, canvas.height);
  }
  const routeInput = await api(state.activeItem.media.judge_input);
  const routeMetadata = validateRouteInput(routeInput);
  if (routeInput.item_id !== state.activeItem.item_id) {
    throw new Error("Anonymous route data does not match the current item.");
  }
  const routeTimeNote = $("#route-time-note");
  if (routeTimeNote) {
    const times = checkpointTimes(routeMetadata.horizon);
    routeTimeNote.textContent =
      `Elevation is shown on the left and cover on the right. Labels 0–5 correspond to ` +
      `t=${times.join(", ")}. Matching labels indicate the same time step.`;
  }
  renderRouteCanvas($("#route-map-a"), routeInput, "A");
  renderRouteCanvas($("#route-map-b"), routeInput, "B");
  $$(".route-map-loading").forEach((element) => element.classList.add("hidden"));
}

async function openItem(itemId) {
  const catalogItem = state.catalog.find((item) => item.item_id === itemId);
  if (!catalogItem) return;
  $("#submit-rating").disabled = false;
  setSaveState("Loading the browser draft...", false);
  showView("judge");
  $("#endpoint-forms").innerHTML =
    '<div class="loading-inline">Loading anonymous route artifact...</div>';
  try {
    const [item] = await Promise.all([
      api(`/api/item/${itemId}`),
      api(`/api/item/${itemId}/start`, {
        method: "POST",
        body: JSON.stringify({ open: true }),
      }),
    ]);
    state.activeItem = { ...item, catalog_number: catalogItem.catalog_number };
    state.draftRevision = 0;
    state.activeSeconds = 0;
    $("#judge-map-label").textContent = item.blind_map_id.replace("_", " ");
    $("#judge-count-label").textContent =
      `Item ${catalogItem.catalog_number} / ${state.catalog.length}`;
    $("#judge-directive").textContent = item.directive;
    $("#endpoint-forms").innerHTML =
      ratingSection();
    bindRatingEvents();
    await configureRouteMaps();

    let draft = item.draft;
    let recoveredLocalDraft = false;
    try {
      const local = JSON.parse(localStorage.getItem(localDraftKey(itemId)));
      const localTime = Date.parse(local?.saved_utc || "") || 0;
      const storedTime = Date.parse(draft?.updated_utc || "") || 0;
      if (local?.payload && (!draft || localTime > storedTime)) {
        draft = {
          ...local,
          revision: Number(draft?.revision || 0),
        };
        recoveredLocalDraft = true;
        toast("Restored a newer unsaved draft from this browser.");
      }
    } catch {
      // Ignore malformed recovery data.
    }
    applyDraft(draft);
    if (recoveredLocalDraft) {
      setSaveState("Saving the restored browser draft...", false);
      window.setTimeout(() => saveDraft(false), 0);
    } else {
      setSaveState(
        draft?.revision ? `Draft saved · v${draft.revision}` : "No browser draft",
        Boolean(draft?.revision),
      );
    }
    startActiveTimer();
  } catch (error) {
    toast(error.message, "error");
    await loadDashboard();
  }
}



async function submitRating(event) {
  event.preventDefault();
  let choice;
  try {
    choice = finalChoice();
  } catch (error) {
    toast(error.message, "error");
    return;
  }
  const button = $("#submit-rating");
  button.disabled = true;
  window.clearTimeout(state.saveTimer);
  state.saveTimer = null;
  state.saveQueued = false;
  const activeItem = state.activeItem;
  try {
    const result = await api(`/api/item/${activeItem.item_id}/submit`, {
      method: "POST",
      body: JSON.stringify({
        choice,
        active_seconds: Math.max(0.001, state.activeSeconds),
      }),
    });
    localStorage.removeItem(localDraftKey(activeItem.item_id));
    toast(`Item ${activeItem.catalog_number} submitted; you may reopen it and change the choice.`);
    const currentId = activeItem.item_id;
    const currentIndex = state.catalog.findIndex(
      (row) => row.item_id === currentId,
    );
    state.activeItem = null;
    const item = state.catalog.find((row) => row.item_id === currentId);
    if (item) {
      item.status = "submitted";
      item.submitted_utc = result.record.completed_utc;
    }
    const nextCandidates =
      currentIndex >= 0
        ? [
            ...state.catalog.slice(currentIndex + 1),
            ...state.catalog.slice(0, currentIndex),
          ]
        : state.catalog;
    const nextItem = nextCandidates.find(
      (row) => row.status !== "submitted",
    );
    if (nextItem) {
      await openItem(nextItem.item_id);
    } else {
      await loadDashboard();
    }
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

function openAdmin() {
  showView("admin");
  if (state.adminToken) {
    loadAdminSummary();
  } else {
    $("#admin-login-card").classList.remove("hidden");
    $("#admin-dashboard").classList.add("hidden");
  }
}

async function loadAdminSummary() {
  const error = $("#admin-error");
  error.classList.add("hidden");
  try {
    const summary = await api("/api/admin/summary", {
      headers: { "X-Admin-Token": state.adminToken },
    });
    state.adminSummary = summary;
    sessionStorage.setItem("tbam-admin-token", state.adminToken);
    $("#admin-login-card").classList.add("hidden");
    $("#admin-dashboard").classList.remove("hidden");
    renderAdminSummary();
  } catch (requestError) {
    state.adminToken = "";
    sessionStorage.removeItem("tbam-admin-token");
    $("#admin-login-card").classList.remove("hidden");
    $("#admin-dashboard").classList.add("hidden");
    error.textContent = requestError.message;
    error.classList.remove("hidden");
  }
}

function renderAdminSummary() {
  const summary = state.adminSummary;
  $("#admin-judgments").textContent = summary.judgment_count.toLocaleString();
  $("#admin-judgments-target").textContent =
    `/ ${summary.target_judgment_count.toLocaleString()}`;
  $("#admin-raters").textContent = summary.participant_count;
  $("#admin-raters-target").textContent = `/ ${summary.max_raters}`;
  $("#admin-complete").textContent = summary.completed_participant_count;
  $("#admin-covered").textContent = summary.items.filter(
    (item) => item.target > 0 && item.submitted === item.target,
  ).length;
  $("#admin-covered-target").textContent = `/ ${summary.target_item_count}`;
  $("#admin-generated").textContent =
    `Local summary generated ${formatDate(summary.generated_utc)} · ${summary.study_id}`;
  renderAdminTable();
}

function renderAdminTable() {
  const query = $("#admin-search").value.trim().toLowerCase();
  const isItems = state.adminTab === "items";
  const rows = isItems
    ? state.adminSummary.items
    : state.adminSummary.participants;
  const filtered = rows.filter((row) =>
    Object.values(row).some((value) =>
      String(value ?? "").toLowerCase().includes(query),
    ),
  );
  $("#admin-table-count").textContent = `${filtered.length} rows`;
  if (isItems) {
    $("#admin-table-head").innerHTML = `
      <tr>
        <th>Map</th><th>Anonymous item</th><th>Coverage</th><th>Assigned</th>
        <th>Choice A</th><th>Choice B</th>
      </tr>`;
    $("#admin-table-body").innerHTML = filtered
      .map(
        (row) => `
          <tr>
            <td>${escapeHtml(row.blind_map_id)}</td>
            <td><code>${escapeHtml(row.item_id)}</code></td>
            <td class="coverage-cell">
              <span class="coverage-track"><span style="width:${row.target ? Math.min(100, (row.submitted / row.target) * 100) : 0}%"></span></span>
              ${row.submitted}/${row.target}
            </td>
            <td>${row.assigned}/${row.target}</td>
            <td>${row.choice_A ?? "sealed"}</td><td>${row.choice_B ?? "sealed"}</td>
          </tr>`,
      )
      .join("");
  } else {
    $("#admin-table-head").innerHTML = `
      <tr>
        <th>Anonymous ID</th><th>Operational pseudonym</th><th>Progress</th><th>Instructions</th>
        <th>Registered</th><th>Last sign-in</th>
      </tr>`;
    $("#admin-table-body").innerHTML = filtered
      .map(
        (row) => `
          <tr>
            <td><code>${escapeHtml(row.rater_id)}</code></td>
            <td>${escapeHtml(row.username)}</td>
            <td class="coverage-cell">
              <span class="coverage-track"><span style="width:${Math.min(100, (row.completed / row.total) * 100)}%"></span></span>
              ${row.completed}/${row.total}
            </td>
            <td>${row.tutorial_completed ? "Complete" : "Incomplete"}</td>
            <td>${formatDate(row.created_utc)}</td>
            <td>${formatDate(row.last_login_utc)}</td>
          </tr>`,
      )
      .join("");
  }
}

async function downloadAdminExport(name) {
  try {
    const response = await fetch(`/api/admin/export/${name}`, {
      headers: { "X-Admin-Token": state.adminToken },
      credentials: "same-origin",
    });
    if (!response.ok) {
      const payload = await response.json();
      throw new Error(payload.message || "Export failed");
    }
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = name;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  } catch (error) {
    toast(error.message, "error");
  }
}

async function logout() {
  try {
    await api("/api/auth/logout", {
      method: "POST",
      body: JSON.stringify({ logout: true }),
    });
  } catch {
    // Clear local state even if browser storage is temporarily unavailable.
  }
  state.participant = null;
  state.catalog = [];
  state.activeItem = null;
  $("#profile-popover").classList.add("hidden");
  showView("auth");
  toast("Signed out.");
}

function bindGlobalEvents() {
  $("#login-tab").addEventListener("click", () => setAuthMode("login"));
  $("#register-tab").addEventListener("click", () => setAuthMode("register"));
  $("#auth-form").addEventListener("submit", submitAuth);
  $$(".tutorial-check").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      $("#finish-tutorial").disabled = !$$(".tutorial-check").every(
        (item) => item.checked,
      );
    });
  });
  $("#finish-tutorial").addEventListener("click", finishTutorial);
  $(".filter-pills").addEventListener("click", (event) => {
    const button = event.target.closest("[data-filter]");
    if (!button) return;
    state.catalogFilter = button.dataset.filter;
    $$(".filter-pill").forEach((pill) =>
      pill.classList.toggle("active", pill === button),
    );
    renderCatalog();
  });
  $("#back-to-directory").addEventListener("click", async () => {
    await saveDraft(false);
    await loadDashboard();
  });
  $("#directory-button").addEventListener("click", loadDashboard);
  $("#brand-button").addEventListener("click", () => {
    if (state.participant?.tutorial_completed) loadDashboard();
    else if (state.participant) showView("tutorial");
    else showView("auth");
  });
  $("#profile-button").addEventListener("click", () => {
    $("#profile-popover").classList.toggle("hidden");
  });
  $("#logout-button").addEventListener("click", logout);
  $("#save-draft-button").addEventListener("click", () => saveDraft(true));
  $("#rating-form").addEventListener("submit", submitRating);
  $("#export-mine").addEventListener("click", () => {
    window.location.href = "/api/export/mine.json";
  });
  $("#open-admin-login").addEventListener("click", openAdmin);
  $("#leave-admin").addEventListener("click", () => {
    if (state.participant?.tutorial_completed) loadDashboard();
    else if (state.participant) showView("tutorial");
    else showView("auth");
  });
  $("#admin-token-form").addEventListener("submit", (event) => {
    event.preventDefault();
    state.adminToken = $("#admin-token-input").value;
    loadAdminSummary();
  });
  $$(".admin-download").forEach((button) => {
    button.addEventListener("click", () =>
      downloadAdminExport(button.dataset.export),
    );
  });
  $$(".admin-tabs button").forEach((button) => {
    button.addEventListener("click", () => {
      state.adminTab = button.dataset.adminTab;
      $$(".admin-tabs button").forEach((tab) =>
        tab.classList.toggle("active", tab === button),
      );
      renderAdminTable();
    });
  });
  $("#admin-search").addEventListener("input", renderAdminTable);
  window.addEventListener("beforeunload", saveLocalDraft);
  document.addEventListener("click", (event) => {
    if (
      !event.target.closest("#profile-popover") &&
      !event.target.closest("#profile-button")
    ) {
      $("#profile-popover").classList.add("hidden");
    }
  });
}

async function boot() {
  bindGlobalEvents();
  state.adminToken = sessionStorage.getItem("tbam-admin-token") || "";
  try {
    const [config, me] = await Promise.all([
      api("/api/config"),
      api("/api/me"),
    ]);
    state.config = config;
    renderConfig();
    if (me.authenticated) {
      state.participant = me.participant;
      updateProfile();
    }
    if (window.location.pathname === "/admin") {
      openAdmin();
    } else if (!state.participant) {
      showView("auth");
    } else if (!state.participant.tutorial_completed) {
      showView("tutorial");
    } else {
      await loadDashboard();
    }
  } catch (error) {
    $("#loading-view p").textContent =
      `The page could not connect to the evaluation service: ${error.message}`;
    toast(error.message, "error");
  }
}

boot();
