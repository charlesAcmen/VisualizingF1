import { useEffect, useRef, useState } from "react";
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

type DriverResult = {
  driver: string;
  payload: TelemetryResponse | null;
  error: string | null;
};

type EventOption = {
  name: string;
  round: number;
  date: string | null;
};

type SessionOption = {
  code: string;
  name: string;
};

type FormState = {
  season: string;
  gp: string;
  session: string;
};

const CURRENT_YEAR = new Date().getFullYear();
const SEASON_OPTIONS = Array.from({ length: CURRENT_YEAR - 2018 + 1 }, (_, idx) => String(CURRENT_YEAR - idx));

const defaultForm: FormState = {
  season: String(CURRENT_YEAR),
  gp: "",
  session: "",
};

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body?.error) {
        detail = `${detail}: ${body.error}`;
      }
    } catch {
      // Keep default detail when response body is not JSON.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

function summarizeDriverError(driver: string, error: string | null): string {
  if (!error) {
    return `${driver} load failed`;
  }
  if (error.includes("Fastest lap not found")) {
    return `${driver} has no fastest lap`;
  }
  if (error.includes("No laps found")) {
    return `${driver} has no laps`;
  }
  return `${driver} failed`;
}

export default function App() {
  const [form, setForm] = useState<FormState>(defaultForm);
  const [events, setEvents] = useState<EventOption[]>([]);
  const [sessions, setSessions] = useState<SessionOption[]>([]);
  const [drivers, setDrivers] = useState<string[]>([]);
  const [selectedDrivers, setSelectedDrivers] = useState<string[]>([]);
  const [lapOptions, setLapOptions] = useState<Record<string, number[]>>({});
  const [lapSelection, setLapSelection] = useState<Record<string, string>>({});
  const [bulkLapMode, setBulkLapMode] = useState<"fastest" | "number">("fastest");
  const [bulkLapNumber, setBulkLapNumber] = useState<string>("");
  const [driverResults, setDriverResults] = useState<DriverResult[]>([]);
  const [metric, setMetric] = useState<string>("Speed");
  const [status, setStatus] = useState<string>("Idle");
  const [tone, setTone] = useState<"ready" | "loading" | "error">("ready");
  const chartRef = useRef<HTMLDivElement | null>(null);
  const eventsRequestIdRef = useRef(0);
  const sessionsRequestIdRef = useRef(0);
  const driversRequestIdRef = useRef(0);

  const validResults = driverResults.filter((item) => item.payload !== null);
  const primaryDataset = validResults[0]?.payload ?? null;
  const availableChannels = primaryDataset?.channels ?? [];
  const unit = primaryDataset?.channel_units?.[metric] ?? "";
  const isBoolean = metric === "Brake";
  const isGear = metric === "nGear";
  const driversDisabled = drivers.length === 0;

  useEffect(() => {
    const seasonValue = Number(form.season);
    if (!Number.isFinite(seasonValue)) {
      return;
    }

    const requestId = ++eventsRequestIdRef.current;
    setEvents([]);
    setSessions([]);
    setDrivers([]);
    setSelectedDrivers([]);
    setLapOptions({});
    setLapSelection({});

    (async () => {
      try {
        const url = new URL("/api/events", API_BASE);
        url.searchParams.set("season", String(seasonValue));
        const payload = await fetchJson<{ events: EventOption[] }>(url.toString());
        if (requestId !== eventsRequestIdRef.current) {
          return;
        }
        const eventList = payload.events ?? [];
        setEvents(eventList);
        setForm((prev) => {
          const nextGp =
            eventList.some((event) => event.name === prev.gp)
              ? prev.gp
              : (eventList[0]?.name ?? "");
          return { ...prev, gp: nextGp, session: "" };
        });
      } catch (error) {
        console.error(error);
        if (requestId !== eventsRequestIdRef.current) {
          return;
        }
        setEvents([]);
        setSessions([]);
        setDrivers([]);
        setSelectedDrivers([]);
      }
    })();
  }, [form.season]);

  useEffect(() => {
    const seasonValue = Number(form.season);
    if (!Number.isFinite(seasonValue) || !form.gp) {
      setSessions([]);
      setDrivers([]);
      setSelectedDrivers([]);
      return;
    }

    const requestId = ++sessionsRequestIdRef.current;
    setSessions([]);
    setDrivers([]);
    setSelectedDrivers([]);
    setLapOptions({});
    setLapSelection({});

    (async () => {
      try {
        const url = new URL("/api/sessions", API_BASE);
        url.searchParams.set("season", String(seasonValue));
        url.searchParams.set("gp", form.gp);
        const payload = await fetchJson<{ sessions: SessionOption[] }>(url.toString());
        if (requestId !== sessionsRequestIdRef.current) {
          return;
        }
        const sessionList = payload.sessions ?? [];
        setSessions(sessionList);
        setForm((prev) => {
          const nextSession =
            sessionList.some((session) => session.code === prev.session)
              ? prev.session
              : (sessionList[0]?.code ?? "");
          return { ...prev, session: nextSession };
        });
      } catch (error) {
        console.error(error);
        if (requestId !== sessionsRequestIdRef.current) {
          return;
        }
        setSessions([]);
        setDrivers([]);
        setSelectedDrivers([]);
      }
    })();
  }, [form.season, form.gp]);

  useEffect(() => {
    const seasonValue = Number(form.season);
    if (!Number.isFinite(seasonValue) || !form.gp || !form.session) {
      setDrivers([]);
      setSelectedDrivers([]);
      return;
    }

    const requestId = ++driversRequestIdRef.current;
    setDrivers([]);
    setSelectedDrivers([]);
    setLapOptions({});
    setLapSelection({});

    (async () => {
      try {
        const url = new URL("/api/drivers", API_BASE);
        url.searchParams.set("season", String(seasonValue));
        url.searchParams.set("gp", form.gp);
        url.searchParams.set("session", form.session);
        const payload = await fetchJson<{ drivers: string[] }>(url.toString());
        if (requestId !== driversRequestIdRef.current) {
          return;
        }
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
        if (requestId !== driversRequestIdRef.current) {
          return;
        }
        setDrivers([]);
        setSelectedDrivers([]);
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
      const results = await Promise.all(
        selectedDrivers.map(async (driver) => {
          const url = new URL("/api/lap", API_BASE);
          url.searchParams.set("season", String(seasonValue));
          url.searchParams.set("gp", form.gp);
          url.searchParams.set("session", form.session);
          url.searchParams.set("driver", driver);
          url.searchParams.set("lap", lapSelection[driver] ?? "fastest");
          try {
            const payload = await fetchJson<TelemetryResponse>(url.toString());
            return { driver, payload, error: null } as DriverResult;
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            return { driver, payload: null, error: message } as DriverResult;
          }
        })
      );

      setDriverResults(results);

      const successful = results.filter((item) => item.payload !== null);
      if (!successful.length) {
        setTone("error");
        const firstError = results[0]?.error ?? "No telemetry returned.";
        setStatus(`Failed to load telemetry: ${firstError}`);
        return;
      }

      const firstPayload = successful[0].payload!;
      setMetric((prev) => (firstPayload.channels.includes(prev) ? prev : firstPayload.channels[0] ?? ""));
      if (successful.length === results.length) {
        setTone("ready");
        setStatus("Telemetry loaded.");
      } else {
        const failed = results.filter((item) => item.payload === null);
        setTone("error");
        setStatus(`Loaded ${successful.length}/${results.length} drivers. ${failed.map((item) => summarizeDriverError(item.driver, item.error)).join("; ")}`);
      }
    } catch (error) {
      console.error(error);
      setTone("error");
      const message = error instanceof Error ? error.message : String(error);
      setStatus(`Failed to load telemetry: ${message}`);
    }
  }

  useEffect(() => {
    loadTelemetry();
  }, []);

  useEffect(() => {
    if (!driverResults.length || !chartRef.current || !metric) {
      return;
    }

    const traces = driverResults.map((result, index) => {
      const color = DRIVER_COLORS[index % DRIVER_COLORS.length];
      if (!result.payload) {
        return {
          x: [null],
          y: [null],
          mode: "lines",
          name: `${result.driver} (failed)`,
          line: {
            color,
            width: 2,
            dash: "dot",
          },
          hovertemplate: `Driver ${result.driver}<br>Error: ${result.error}<extra></extra>`,
          visible: "legendonly",
        };
      }

      const data = result.payload.data;
      const distance = data.distance_m ?? [];
      const y = data[metric] ?? [];
      const driver = result.payload.meta?.driver ?? result.driver;

      return {
        x: distance,
        y,
        mode: "lines",
        name: driver,
        line: {
          color,
          width: 2,
          shape: isBoolean ? "hv" : "linear",
        },
        hovertemplate: `Driver ${driver}<br>Distance %{x:.1f} m<br>${metric} %{y:.2f}${unit ? ` ${unit}` : ""}<extra></extra>`,
      };
    });

    let yMin = Infinity;
    let yMax = -Infinity;
    validResults.forEach((item) => {
      const series = item.payload!.data[metric] ?? [];
      series.forEach((value) => {
        if (value < yMin) {
          yMin = value;
        }
        if (value > yMax) {
          yMax = value;
        }
      });
    });

    if (!Number.isFinite(yMin) || !Number.isFinite(yMax)) {
      yMin = 0;
      yMax = 1;
    }

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
  }, [driverResults, validResults, metric, unit, isBoolean, isGear, primaryDataset]);

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
              <select
                value={form.season}
                onChange={(event) => setForm({ ...form, season: event.target.value })}
              >
                {SEASON_OPTIONS.map((season) => (
                  <option key={season} value={season}>
                    {season}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <span className="label">Grand Prix</span>
              <select
                value={form.gp}
                onChange={(event) => setForm({ ...form, gp: event.target.value })}
                disabled={events.length === 0}
              >
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
                disabled={sessions.length === 0}
              >
                {sessions.map((session) => (
                  <option key={session.code} value={session.code}>
                    {session.name} ({session.code})
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <span className="label">Drivers</span>
              {driversDisabled ? (
                <div className="note">No drivers loaded yet (check season/event/session).</div>
              ) : (
                <div className="driver-select-wrap">
                  <div className="driver-actions">
                    <button type="button" className="driver-action-btn" onClick={() => setSelectedDrivers(drivers)}>
                      Select All
                    </button>
                    <button type="button" className="driver-action-btn" onClick={() => setSelectedDrivers([])}>
                      Clear
                    </button>
                  </div>
                  <div className="driver-grid">
                    {drivers.map((driver) => {
                      const active = selectedDrivers.includes(driver);
                      return (
                        <button
                          key={driver}
                          type="button"
                          className={active ? "driver-btn active" : "driver-btn"}
                          onClick={() => {
                            setSelectedDrivers((prev) => {
                              if (prev.includes(driver)) {
                                return prev.filter((item) => item !== driver);
                              }
                              return [...prev, driver];
                            });
                          }}
                        >
                          {driver}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
              {!driversDisabled ? (
                <div className="note">
                  Selected: {selectedDrivers.length ? selectedDrivers.join(", ") : "none"}
                </div>
              ) : null}
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
                <div className="bulk-lap">
                  <span className="bulk-label">Apply to all selected drivers</span>
                  <div className="bulk-controls">
                    <select value={bulkLapMode} onChange={(event) => setBulkLapMode(event.target.value as "fastest" | "number")}>
                      <option value="fastest">Fastest</option>
                      <option value="number">Lap number</option>
                    </select>
                    {bulkLapMode === "number" ? (
                      <input
                        value={bulkLapNumber}
                        onChange={(event) => setBulkLapNumber(event.target.value)}
                        placeholder="e.g. 12"
                        inputMode="numeric"
                      />
                    ) : null}
                    <button
                      type="button"
                      onClick={() => {
                        setLapSelection((prev) => {
                          const next = { ...prev };
                          if (bulkLapMode === "fastest") {
                            selectedDrivers.forEach((driver) => {
                              next[driver] = "fastest";
                            });
                            return next;
                          }

                          const targetLap = Number(bulkLapNumber);
                          if (!Number.isFinite(targetLap) || targetLap <= 0) {
                            selectedDrivers.forEach((driver) => {
                              next[driver] = "fastest";
                            });
                            return next;
                          }

                          selectedDrivers.forEach((driver) => {
                            const options = lapOptions[driver] ?? [];
                            next[driver] = options.includes(targetLap) ? String(targetLap) : "fastest";
                          });
                          return next;
                        });
                      }}
                    >
                      Apply
                    </button>
                  </div>
                  <div className="note">If a lap number doesn't exist for a driver, it falls back to Fastest.</div>
                </div>
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
            </div>
            <div className="meta-drivers">
              {driverResults.map((result) => (
                <div className="meta-driver" key={result.driver}>
                  <div className="meta-driver-title">{result.driver}</div>
                  {result.payload ? (
                    <>
                      <div className="meta-row">
                        <span>Lap</span>
                        <span>{result.payload.meta.lap_number ?? "-"}</span>
                      </div>
                      <div className="meta-row">
                        <span>Lap Time</span>
                        <span>{result.payload.meta.lap_time ?? "-"}</span>
                      </div>
                    </>
                  ) : (
                    <div className="note">{summarizeDriverError(result.driver, result.error)}</div>
                  )}
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
