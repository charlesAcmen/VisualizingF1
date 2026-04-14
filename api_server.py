import json
import logging
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter
import traceback
from urllib.parse import parse_qs, urlparse

import fastf1
import pandas as pd


CACHE_DIR = Path(__file__).resolve().parent / ".fastf1_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))
# Keep FastF1 loading logs visible in server console.
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s", force=True)
fastf1.set_log_level("INFO")


def format_lap_time(value):
    if value is None or pd.isna(value):
        return None
    total_seconds = value.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = total_seconds - minutes * 60
    return f"{minutes}:{seconds:06.3f}"


def resolve_event_name(event):
    if event is None:
        return None
    try:
        return event.get("EventName")
    except AttributeError:
        try:
            return event["EventName"]
        except Exception:
            return str(event)


def load_session(season, gp, session_code, telemetry=False):
    session = fastf1.get_session(season, gp, session_code)
    session.load(telemetry=telemetry, weather=False, messages=False)
    return session


def build_corners(session):
    try:
        circuit_info = session.get_circuit_info()
    except Exception:
        return []
    if circuit_info is None or not hasattr(circuit_info, "corners"):
        return []

    corners = []
    for _, corner in circuit_info.corners.iterrows():
        letter = corner.get("Letter") if hasattr(corner, "get") else corner["Letter"]
        if pd.isna(letter):
            letter = ""
        corners.append(
            {
                "distance": float(corner["Distance"]),
                "number": str(corner["Number"]),
                "letter": str(letter),
            }
        )
    return corners


def build_payload(season, gp, session_code, driver, lap_selector):
    session = load_session(season, gp, session_code, telemetry=True)

    laps = session.laps.pick_drivers(driver)
    if laps.empty:
        raise ValueError(f"No laps found for driver '{driver}'.")

    if str(lap_selector).lower() == "fastest":
        lap_row = laps.pick_fastest()
        if lap_row is None or getattr(lap_row, "empty", False):
            raise ValueError(f"Fastest lap not found for driver '{driver}'.")
    else:
        try:
            lap_number = int(lap_selector)
        except ValueError as exc:
            raise ValueError("Lap must be 'fastest' or an integer.") from exc
        lap_matches = laps.pick_lap(lap_number)
        if lap_matches.empty:
            raise ValueError(f"Lap {lap_number} not found for driver '{driver}'.")
        lap_row = lap_matches.iloc[0]

    car_data = lap_row.get_car_data().add_distance()
    car_data = car_data[car_data["Distance"].notna()].copy()
    car_data = car_data.loc[~car_data["Distance"].duplicated()].reset_index(drop=True)

    channels = [
        ("Speed", "km/h"),
        ("Throttle", "%"),
        ("Brake", "bool"),
        ("RPM", "rpm"),
        ("nGear", "gear"),
    ]

    data = {"distance_m": [round(float(val), 3) for val in car_data["Distance"].to_numpy()]}
    channel_units = {}
    for channel, unit in channels:
        if channel not in car_data.columns:
            continue
        channel_units[channel] = unit
        series = car_data[channel]
        if channel in {"Brake", "nGear"}:
            data[channel] = [int(val) for val in series.fillna(0).astype(int).to_numpy()]
        else:
            data[channel] = [round(float(val), 3) for val in series.fillna(0).to_numpy()]

    lap_time = format_lap_time(lap_row.get("LapTime"))
    lap_number_raw = lap_row.get("LapNumber")
    lap_number_value = int(lap_number_raw) if not pd.isna(lap_number_raw) else None

    meta = {
        "season": season,
        "event": resolve_event_name(session.event),
        "session": session.name,
        "driver": driver,
        "lap_number": lap_number_value,
        "lap_time": lap_time,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "meta": meta,
        "channels": list(channel_units.keys()),
        "channel_units": channel_units,
        "data": data,
        "corners": build_corners(session),
    }


def build_event_list(season):
    schedule = fastf1.get_event_schedule(season)
    events = []
    for _, row in schedule.iterrows():
        name = row.get("EventName") if hasattr(row, "get") else row["EventName"]
        round_number = row.get("RoundNumber") if hasattr(row, "get") else row["RoundNumber"]
        date_value = row.get("EventDate") if hasattr(row, "get") else row.get("EventDate", None)
        if pd.isna(date_value):
            date_value = None
        date_iso = date_value.isoformat() if date_value is not None else None
        events.append({"name": str(name), "round": int(round_number), "date": date_iso})
    events.sort(key=lambda item: item["round"])
    return events


SESSION_NAME_TO_CODE = {
    "Practice 1": "FP1",
    "Practice 2": "FP2",
    "Practice 3": "FP3",
    "Qualifying": "Q",
    "Sprint Qualifying": "S",
    "Sprint": "S",
    "Sprint Shootout": "SS",
    "Race": "R",
}


def build_session_list(season, gp):
    event = fastf1.get_event(season, gp)
    sessions = []
    seen_codes = set()

    for idx in range(1, 6):
        key = f"Session{idx}"
        if key not in event.index:
            continue
        raw_name = event.get(key)
        if raw_name is None or pd.isna(raw_name):
            continue

        name = str(raw_name).strip()
        if not name:
            continue

        code = SESSION_NAME_TO_CODE.get(name)
        if code is None:
            continue
        if code in seen_codes:
            continue
        seen_codes.add(code)
        sessions.append({"code": code, "name": name})

    return sessions


def build_driver_list(season, gp, session_code):
    session = load_session(season, gp, session_code, telemetry=False)
    drivers = sorted(session.laps["Driver"].dropna().unique().tolist())
    return drivers


def build_lap_list(season, gp, session_code, driver):
    session = load_session(season, gp, session_code, telemetry=False)
    laps = session.laps.pick_drivers(driver)
    if laps.empty:
        raise ValueError(f"No laps found for driver '{driver}'.")
    lap_numbers = (
        laps["LapNumber"].dropna().astype(int).sort_values().unique().tolist()
    )
    return lap_numbers


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[HTTP] {self.address_string()} - {format % args}", flush=True)

    def _send_json(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/events":
            params = parse_qs(parsed.query)
            try:
                season = int(params.get("season", [2021])[0])
                events = build_event_list(season)
                self._send_json(200, {"season": season, "events": events})
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return

        if parsed.path == "/api/drivers":
            params = parse_qs(parsed.query)
            try:
                season = int(params.get("season", [2021])[0])
                gp = params.get("gp", ["Spanish Grand Prix"])[0]
                session_code = params.get("session", ["Q"])[0]
                drivers = build_driver_list(season, gp, session_code)
                self._send_json(
                    200,
                    {"season": season, "event": gp, "session": session_code, "drivers": drivers},
                )
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return

        if parsed.path == "/api/sessions":
            params = parse_qs(parsed.query)
            try:
                season = int(params.get("season", [2021])[0])
                gp = params.get("gp", ["Spanish Grand Prix"])[0]
                sessions = build_session_list(season, gp)
                self._send_json(
                    200,
                    {"season": season, "event": gp, "sessions": sessions},
                )
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return

        if parsed.path == "/api/laps":
            params = parse_qs(parsed.query)
            try:
                season = int(params.get("season", [2021])[0])
                gp = params.get("gp", ["Spanish Grand Prix"])[0]
                session_code = params.get("session", ["Q"])[0]
                driver = params.get("driver", ["VER"])[0].upper()
                laps = build_lap_list(season, gp, session_code, driver)
                self._send_json(
                    200,
                    {
                        "season": season,
                        "event": gp,
                        "session": session_code,
                        "driver": driver,
                        "laps": laps,
                    },
                )
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return

        if parsed.path == "/api/lap":
            params = parse_qs(parsed.query)
            try:
                season = int(params.get("season", [2021])[0])
                gp = params.get("gp", ["Spanish Grand Prix"])[0]
                session_code = params.get("session", ["Q"])[0]
                driver = params.get("driver", ["VER"])[0].upper()
                lap_selector = params.get("lap", ["fastest"])[0]
                started = perf_counter()
                print(
                    f"[API] /api/lap season={season} gp={gp} session={session_code} driver={driver} lap={lap_selector}",
                    flush=True,
                )

                payload = build_payload(
                    season=season,
                    gp=gp,
                    session_code=session_code,
                    driver=driver,
                    lap_selector=lap_selector,
                )
                elapsed_ms = (perf_counter() - started) * 1000
                point_count = len(payload.get("data", {}).get("distance_m", []))
                print(f"[API] /api/lap success points={point_count} elapsed_ms={elapsed_ms:.1f}", flush=True)
                self._send_json(200, payload)
            except Exception as exc:
                print(f"[API] /api/lap error: {exc}", flush=True)
                traceback.print_exc()
                self._send_json(400, {"error": str(exc)})
            return

        if parsed.path == "/api/health":
            self._send_json(200, {"status": "ok"})
            return

        self.send_response(404)
        self.end_headers()


def main():
    host = "0.0.0.0"
    port = 8000
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"FastF1 API server running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
