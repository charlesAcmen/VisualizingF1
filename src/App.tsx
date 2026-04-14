import { useEffect, useMemo, useRef, useState } from "react";
import Plotly from "plotly.js-dist-min";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const DRIVER_COLORS = [
  "#7aa2ff",
  "#ff6b6b",
  "#ffb454",
  "#6be3b5",
  "#c792ea",
  "#4fd2d2",
  "#f38ba8",
  "#ffd166",
  "#a6e3a1",
  "#89b4fa",
];

type TelemetryMeta = {
  season: number;
  event: string;
  session: string;
  driver: string;
  lap_number: number | null;
  lap_time: string | null;
  generated_utc: string;
};

type CornerInfo = {
  distance: number;
  number: string;
  letter: string;
};

type TelemetryResponse = {
  meta: TelemetryMeta;
  channels: string[];
  channel_units: Record<string, string>;
  data: Record<string, number[]> & { distance_m: number[] };
  corners?: CornerInfo[];
};

type EventOption = {
  name: string;
  round: number;
  date: string | null;
};

type FormState = {
  season: string;
  gp: string;
  session: string;
  maxPoints: string;
};

const defaultForm: FormState = {
  season: "2021",
  gp: "Spanish Grand Prix",
  session: "Q",
  maxPoints: "0",
};

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export default function App() {
  const [form, setForm] = useState<FormState>(defaultForm);
  const [events, setEvents] = useState<EventOption[]>([]);
  const [drivers, setDrivers] = useState<string[]>([]);
  const [selectedDrivers, setSelectedDrivers] = useState<string[]>([]);
  const [lapOptions, setLapOptions] = useState<Record<string, number[]>>({});
  const [lapSelection, setLapSelection] = useState<Record<string, string>>({});
  const [datasets, setDatasets] = useState<TelemetryResponse[]>([]);
  const [metric, setMetric] = useState<string>("Speed");
  const [status, setStatus] = useState<string>("Idle");
  const [tone, setTone] = useState<"ready" | "loading" | "error">("ready");
  const chartRef = useRef<HTMLDivElement | null>(null);

  const primaryDataset = datasets[0] ?? null;
  const availableChannels = primaryDataset?.channels ?? [];
  const unit = primaryDataset?.channel_units?.[metric] ?? "";
  const isBoolean = metric === "Brake";
  const isGear = metric === "nGear";

  useEffect(() => {
    const seasonValue = Number(form.season);
    if (!Number.isFinite(seasonValue)) {
      return;
    }

    (async () => {
      try {
        const url = new URL("/api/events", API_BASE);
        url.searchParams.set("season", String(seasonValue));
        const payload = await fetchJson<{ events: EventOption[] }>(url.toString());
        const eventList = payload.events ?? [];
        setEvents(eventList);
        setForm((prev) => {
          if (!eventList.length) {
            return prev;
          }
          const current = prev.gp;
          if (eventList.some((event) => event.name === current)) {
            return prev;
          }
          return { ...prev, gp: eventList[0].name };
        });
      } catch (error) {
        console.error(error);
        setEvents([]);
      }
    })();
  }, [form.season]);

  useEffect(() => {
    const seasonValue = Number(form.season);
    if (!Number.isFinite(seasonValue) || !form.gp || !form.session) {
      setDrivers([]);
      return;
    }

    setLapOptions({});
    setLapSelection({});

    (async () => {
      try {
        const url = new URL("/api/drivers", API_BASE);
        url.searchParams.set("season", String(seasonValue));
        url.searchParams.set("gp", form.gp);
        url.searchParams.set("session", form.session);
        const payload = await fetchJson<{ drivers: string[] }>(url.toString());
        const driverList = payload.drivers ?? [];
        setDrivers(driverList);
        setSelectedDrivers((prev) => {
          const filtered = prev.filter((driver) => driverList.includes(driver));
          if (!filtered.length && driverList.length) {
            return [driverList[0]];
          }
          return filtered;
        });
      } catch (error) {
        console.error(error);
        setDrivers([]);
      }
    })();
  }, [form.season, form.gp, form.session]);

  useEffect(() => {
    setLapOptions((prev) => {
      const next: Record<string, number[]> = {};
      selectedDrivers.forEach((driver) => {
        if (prev[driver]) {
          next[driver] = prev[driver];
        }
      });
      return next;
    });
    setLapSelection((prev) => {
      const next: Record<string, string> = {};
      selectedDrivers.forEach((driver) => {
        if (prev[driver]) {
          next[driver] = prev[driver];
        }
      });
      return next;
    });
  }, [selectedDrivers]);

  useEffect(() => {
    const seasonValue = Number(form.season);
    if (!Number.isFinite(seasonValue) || !form.gp || !form.session) {
      return;
    }

    selectedDrivers.forEach((driver) => {
      if (lapOptions[driver]) {
        return;
      }
      (async () => {
        try {
          const url = new URL("/api/laps", API_BASE);
          url.searchParams.set("season", String(seasonValue));
          url.searchParams.set("gp", form.gp);
          url.searchParams.set("session", form.session);
          url.searchParams.set("driver", driver);
          const payload = await fetchJson<{ laps: number[] }>(url.toString());
          const laps = payload.laps ?? [];
          setLapOptions((prev) => ({ ...prev, [driver]: laps }));
          setLapSelection((prev) => {
            const current = prev[driver];
            if (current) {
              if (current === "fastest") {
                return prev;
              }
              const numeric = Number(current);
              if (Number.isFinite(numeric) && laps.includes(numeric)) {
                return prev;
              }
            }
            return { ...prev, [driver]: "fastest" };
          });
        } catch (error) {
          console.error(error);
          setLapOptions((prev) => ({ ...prev, [driver]: [] }));
        }
      })();
    });
  }, [selectedDrivers, form.season, form.gp, form.session, lapOptions]);

  async function loadTelemetry() {
    if (!selectedDrivers.length) {
      setTone("error");
      setStatus("Select at least one driver.");
      return;
    }

    const seasonValue = Number(form.season);
    if (!Number.isFinite(seasonValue)) {
      setTone("error");
      setStatus("Season must be a number.");
      return;
    }

    setTone("loading");
    setStatus(`Loading telemetry for ${selectedDrivers.length} driver${selectedDrivers.length > 1 ? "s" : ""}...`);

    try {
      const maxPointsValue = Number(form.maxPoints);
      const payloads = await Promise.all(
        selectedDrivers.map(async (driver) => {
          const url = new URL("/api/lap", API_BASE);
          url.searchParams.set("season", String(seasonValue));
          url.searchParams.set("gp", form.gp);
          url.searchParams.set("session", form.session);
          url.searchParams.set("driver", driver);
          url.searchParams.set("lap", lapSelection[driver] ?? "fastest");
          if (Number.isFinite(maxPointsValue) && maxPointsValue > 0) {
            url.searchParams.set("max_points", String(maxPointsValue));
          }
          return fetchJson<TelemetryResponse>(url.toString());
        })
      );

      setDatasets(payloads);
      setMetric((prev) => (payloads[0]?.channels.includes(prev) ? prev : payloads[0]?.channels[0] ?? ""));
      setTone("ready");
      setStatus("Telemetry loaded.");
    } catch (error) {
      console.error(error);
      setTone("error");
      setStatus("Failed to load telemetry. Check the API server.");
    }
  }

  useEffect(() => {
    loadTelemetry();
  }, []);

  useEffect(() => {
    if (!datasets.length || !chartRef.current || !metric) {
      return;
    }

    const traces = datasets.map((payload, index) => {
      const data = payload.data;
      const distance = data.distance_m ?? [];
      const y = data[metric] ?? [];
      const driver = payload.meta?.driver ?? `Driver ${index + 1}`;

      return {
        x: distance,
        y,
        mode: "lines",
        name: driver,
        line: {
          color: DRIVER_COLORS[index % DRIVER_COLORS.length],
          width: 2,
          shape: isBoolean ? "hv" : "linear",
        },
        hovertemplate: `Driver ${driver}<br>Distance %{x:.1f} m<br>${metric} %{y:.2f}${unit ? ` ${unit}` : ""}<extra></extra>`,
      };
    });

    let yMin = Infinity;
    let yMax = -Infinity;
    datasets.forEach((payload) => {
      const series = payload.data[metric] ?? [];
      series.forEach((value) => {
        if (value < yMin) {
          yMin = value;
        }
        if (value > yMax) {
          yMax = value;
        }
      });
    });

    const corners = primaryDataset?.corners ?? [];
    const shapes =
      metric === "Speed" && corners.length
        ? corners.map((corner) => ({
            type: "line",
            x0: corner.distance,
            x1: corner.distance,
            y0: yMin - 20,
            y1: yMax + 20,
            line: {
              color: "rgba(255,255,255,0.25)",
              dash: "dot",
              width: 1,
            },
          }))
        : [];

    const annotations =
      metric === "Speed" && corners.length
        ? corners.map((corner) => ({
            x: corner.distance,
            y: yMin - 30,
            text: `${corner.number}${corner.letter || ""}`,
            showarrow: false,
            font: { size: 10, color: "#cfd6e4" },
          }))
        : [];

    const layout = {
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      margin: { l: 62, r: 20, t: 36, b: 50 },
      xaxis: {
        title: "Distance Along Lap (m)",
        gridcolor: "rgba(255,255,255,0.08)",
        tickfont: { color: "#b8becb" },
        titlefont: { color: "#b8becb" },
      },
      yaxis: {
        title: `${metric}${unit ? ` (${unit})` : ""}`,
        gridcolor: "rgba(255,255,255,0.08)",
        tickfont: { color: "#b8becb" },
        titlefont: { color: "#b8becb" },
        range: isBoolean ? [-0.1, 1.1] : undefined,
        dtick: isGear ? 1 : undefined,
      },
      hovermode: "x unified",
      shapes,
      annotations,
    };

    const config = {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["toImage"],
    };

    Plotly.react(chartRef.current, traces, layout, config);
  }, [datasets, metric, unit, isBoolean, isGear, primaryDataset]);

  const driverSelectSize = Math.min(Math.max(drivers.length, 4), 10);

  return (
    <div className="app">
      <header>
        <h1>FastF1 Telemetry Explorer</h1>
        <div className="subtitle">Multi-driver lap telemetry with distance-based x-axis (FastF1 cache enabled).</div>
      </header>

      <main className="layout">
        <section className="panel">
          <div className="panel-block">
            <div className="block-title">Query</div>
            <div className="field">
              <span className="label">Season</span>
              <input
                value={form.season}
                onChange={(event) => setForm({ ...form, season: event.target.value })}
                placeholder="2021"
              />
            </div>
            <div className="field">
              <span className="label">Grand Prix</span>
              <select value={form.gp} onChange={(event) => setForm({ ...form, gp: event.target.value })}>
                {events.map((event) => (
                  <option key={event.name} value={event.name}>
                    {event.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <span className="label">Session</span>
              <select
                value={form.session}
                onChange={(event) => setForm({ ...form, session: event.target.value })}
              >
                <option value="R">Race (R)</option>
                <option value="Q">Qualifying (Q)</option>
                <option value="S">Sprint (S)</option>
                <option value="FP1">FP1</option>
                <option value="FP2">FP2</option>
                <option value="FP3">FP3</option>
              </select>
            </div>
            <div className="field">
              <span className="label">Drivers</span>
              <select
                multiple
                size={driverSelectSize}
                value={selectedDrivers}
                onChange={(event) => {
                  const values = Array.from(event.target.selectedOptions).map((option) => option.value);
                  setSelectedDrivers(values);
                }}
              >
                {drivers.map((driver) => (
                  <option key={driver} value={driver}>
                    {driver}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <span className="label">Max Points</span>
              <input
                value={form.maxPoints}
                onChange={(event) => setForm({ ...form, maxPoints: event.target.value })}
                placeholder="0 = no downsample"
              />
            </div>
            <button className="primary" type="button" onClick={loadTelemetry}>
              Load Telemetry
            </button>
            <div className="status" data-tone={tone}>
              {status}
            </div>
            <div className="note">API base: {API_BASE}</div>
          </div>

          <div className="panel-block">
            <div className="block-title">Driver Laps</div>
            {selectedDrivers.length === 0 ? (
              <div className="note">Select drivers above to choose laps.</div>
            ) : (
              <div className="driver-laps">
                {selectedDrivers.map((driver) => (
                  <div className="driver-lap-row" key={driver}>
                    <span className="driver-pill">{driver}</span>
                    <select
                      value={lapSelection[driver] ?? "fastest"}
                      onChange={(event) =>
                        setLapSelection((prev) => ({ ...prev, [driver]: event.target.value }))
                      }
                    >
                      <option value="fastest">Fastest</option>
                      {(lapOptions[driver] ?? []).map((lap) => (
                        <option key={lap} value={String(lap)}>
                          Lap {lap}
                        </option>
                      ))}
                    </select>
                    <span className="lap-count">
                      {(lapOptions[driver] ?? []).length
                        ? `${lapOptions[driver].length} laps`
                        : "Loading..."}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="panel-block">
            <div className="block-title">Metric</div>
            <div className="field">
              <span className="label">Channel</span>
              <select
                value={metric}
                onChange={(event) => setMetric(event.target.value)}
                disabled={!availableChannels.length}
              >
                {availableChannels.map((channel) => (
                  <option key={channel} value={channel}>
                    {channel}
                  </option>
                ))}
              </select>
            </div>
            <div className="note">Unit: {unit || "-"}</div>
          </div>

          <div className="panel-block">
            <div className="block-title">Meta</div>
            <div className="meta-grid">
              <div className="meta-row">
                <span>Season</span>
                <span>{primaryDataset?.meta?.season ?? "-"}</span>
              </div>
              <div className="meta-row">
                <span>Event</span>
                <span>{primaryDataset?.meta?.event ?? "-"}</span>
              </div>
              <div className="meta-row">
                <span>Session</span>
                <span>{primaryDataset?.meta?.session ?? "-"}</span>
              </div>
              <div className="meta-row">
                <span>Generated</span>
                <span>{primaryDataset?.meta?.generated_utc ?? "-"}</span>
              </div>
            </div>
            <div className="meta-drivers">
              {datasets.map((payload) => (
                <div className="meta-driver" key={payload.meta.driver}>
                  <div className="meta-driver-title">{payload.meta.driver}</div>
                  <div className="meta-row">
                    <span>Lap</span>
                    <span>{payload.meta.lap_number ?? "-"}</span>
                  </div>
                  <div className="meta-row">
                    <span>Lap Time</span>
                    <span>{payload.meta.lap_time ?? "-"}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="chart-panel">
          <div ref={chartRef} className="chart" />
        </section>
      </main>
    </div>
  );
}
