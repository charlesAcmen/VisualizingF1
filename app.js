const DATA_PATH = "./data/lap_telemetry.json";

const METRIC_COLORS = {
  Speed: "#7aa2ff",
  Throttle: "#3ddc97",
  Brake: "#ff6b6b",
  RPM: "#ffb454",
  nGear: "#c792ea",
};

const state = {
  dataset: null,
  metric: null,
  distanceKm: [],
};

const metricSelect = document.getElementById("metricSelect");
const reloadBtn = document.getElementById("reloadBtn");
const statusEl = document.getElementById("status");
const metricUnitEl = document.getElementById("metricUnit");

const metaFields = {
  season: document.getElementById("metaSeason"),
  event: document.getElementById("metaEvent"),
  session: document.getElementById("metaSession"),
  driver: document.getElementById("metaDriver"),
  lap: document.getElementById("metaLap"),
  lapTime: document.getElementById("metaLapTime"),
  generated: document.getElementById("metaGenerated"),
};

function setStatus(message, tone = "ready") {
  statusEl.textContent = message;
  statusEl.dataset.tone = tone;
}

function updateMeta(meta) {
  metaFields.season.textContent = meta?.season ?? "-";
  metaFields.event.textContent = meta?.event ?? "-";
  metaFields.session.textContent = meta?.session ?? "-";
  metaFields.driver.textContent = meta?.driver ?? "-";
  metaFields.lap.textContent = meta?.lap_number ?? "-";
  metaFields.lapTime.textContent = meta?.lap_time ?? "-";
  metaFields.generated.textContent = meta?.generated_utc ?? "-";
}

function populateMetricOptions(channels, units) {
  metricSelect.innerHTML = "";
  channels.forEach((channel) => {
    const option = document.createElement("option");
    option.value = channel;
    option.textContent = channel;
    metricSelect.appendChild(option);
  });
  if (!channels.includes(state.metric)) {
    state.metric = channels[0] || null;
  }
  if (state.metric) {
    metricSelect.value = state.metric;
    metricUnitEl.textContent = `Unit: ${units[state.metric] || "-"}`;
  }
}

function buildLayout(metric, unit, isBoolean, isGear) {
  const yaxis = {
    title: `${metric}${unit ? ` (${unit})` : ""}`,
    gridcolor: "rgba(255,255,255,0.08)",
    tickfont: { color: "#b8becb" },
    titlefont: { color: "#b8becb" },
  };

  if (isBoolean) {
    yaxis.range = [-0.1, 1.1];
    yaxis.tickmode = "array";
    yaxis.tickvals = [0, 1];
    yaxis.ticktext = ["Off", "On"];
  }

  if (isGear) {
    yaxis.range = [0, 9];
    yaxis.dtick = 1;
  }

  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: { l: 60, r: 22, t: 36, b: 50 },
    xaxis: {
      title: "Distance Along Lap (km)",
      gridcolor: "rgba(255,255,255,0.08)",
      tickfont: { color: "#b8becb" },
      titlefont: { color: "#b8becb" },
    },
    yaxis,
    hovermode: "x unified",
  };
}

function renderChart() {
  if (!state.dataset || !state.metric) {
    return;
  }
  const data = state.dataset.data;
  const units = state.dataset.channel_units || {};
  const metric = state.metric;
  const unit = units[metric] || "";
  const isBoolean = metric === "Brake";
  const isGear = metric === "nGear";
  const lineShape = isBoolean ? "hv" : "linear";

  const trace = {
    x: state.distanceKm,
    y: data[metric],
    mode: "lines",
    name: metric,
    line: {
      color: METRIC_COLORS[metric] || "#7aa2ff",
      width: 2,
      shape: lineShape,
    },
    hovertemplate: `Distance %{x:.3f} km<br>${metric} %{y:.3f}${unit ? ` ${unit}` : ""}<extra></extra>`,
  };

  const layout = buildLayout(metric, unit, isBoolean, isGear);
  const config = {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["toImage"],
  };

  Plotly.react("chart", [trace], layout, config);
}

async function loadDataset() {
  setStatus("Loading telemetry JSON…", "loading");
  try {
    const response = await fetch(DATA_PATH, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const dataset = await response.json();
    state.dataset = dataset;
    state.distanceKm = dataset.data.distance_m.map((val) => val / 1000);
    updateMeta(dataset.meta || {});
    populateMetricOptions(dataset.channels || [], dataset.channel_units || {});
    renderChart();
    setStatus("Telemetry loaded.", "ready");
  } catch (error) {
    console.error(error);
    setStatus("Failed to load telemetry JSON. Generate it first.", "error");
  }
}

function attachListeners() {
  metricSelect.addEventListener("change", (event) => {
    state.metric = event.target.value;
    if (state.dataset?.channel_units) {
      metricUnitEl.textContent = `Unit: ${state.dataset.channel_units[state.metric] || "-"}`;
    }
    renderChart();
  });

  reloadBtn.addEventListener("click", () => {
    loadDataset();
  });
}

function init() {
  attachListeners();
  loadDataset();
}

window.addEventListener("DOMContentLoaded", init);
