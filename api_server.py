import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import OrderedDict
from pathlib import Path
from time import perf_counter
from threading import Event, Lock
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

SESSION_CACHE = OrderedDict()
SESSION_CACHE_LOCK = Lock()
SESSION_CACHE_MAX_SIZE = 4
SESSION_LOADING_EVENTS = {}


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


def is_testing_event(season, gp):
    """Check if an event is a testing event."""
    try:
        # Try to get event schedule and check if it's a testing event
        schedule = fastf1.get_event_schedule(season)
        for _, event in schedule.iterrows():
            if (event['EventName'] == gp or 
                (isinstance(gp, str) and gp.lower() in event['EventName'].lower())):
                # Check if it's a testing event (Round 0 or contains 'Testing')
                return (event['RoundNumber'] == 0 or 
                       'Testing' in str(event['EventName']))
        return False
    except Exception:
        # Fallback: check if gp name contains 'Testing'
        return 'Testing' in str(gp)


def load_session(season, gp, session_code):
    key = (int(season), str(gp), str(session_code))
    wait_event = None
    is_loader = False

    with SESSION_CACHE_LOCK:
        cached_session = SESSION_CACHE.get(key)
        if cached_session is not None:
            SESSION_CACHE.move_to_end(key)
            print(f"[CACHE] session hit {key}", flush=True)
            return cached_session
        if key in SESSION_LOADING_EVENTS:
            wait_event = SESSION_LOADING_EVENTS[key]
            print(f"[CACHE] session wait {key}", flush=True)
        else:
            wait_event = Event()
            SESSION_LOADING_EVENTS[key] = wait_event
            is_loader = True

    if not is_loader:
        wait_event.wait()
        with SESSION_CACHE_LOCK:
            cached_session = SESSION_CACHE.get(key)
            if cached_session is not None:
                SESSION_CACHE.move_to_end(key)
                print(f"[CACHE] session hit-after-wait {key}", flush=True)
                return cached_session
        raise RuntimeError(f"Session load failed for {key}.")

    try:
        print(f"[CACHE] session miss {key}, loading with telemetry", flush=True)
        
        # Check if this is a testing event
        if is_testing_event(season, gp):
            # For testing events, use get_testing_session
            # Convert session_code to session number for testing sessions
            session_number = None
            if session_code == 'FP1':
                session_number = 1
            elif session_code == 'FP2':
                session_number = 2
            elif session_code == 'FP3':
                session_number = 3
            else:
                # Default to first session for testing
                session_number = 1
            
            session = fastf1.get_testing_session(season, 1, session_number)
        else:
            # Regular race event
            session = fastf1.get_session(season, gp, session_code)
        
        session.load(telemetry=True, weather=False, messages=False)
        with SESSION_CACHE_LOCK:
            SESSION_CACHE[key] = session
            SESSION_CACHE.move_to_end(key)
            while len(SESSION_CACHE) > SESSION_CACHE_MAX_SIZE:
                evicted_key, _ = SESSION_CACHE.popitem(last=False)
                print(f"[CACHE] session evicted {evicted_key}", flush=True)
            return session
    finally:
        with SESSION_CACHE_LOCK:
            event = SESSION_LOADING_EVENTS.pop(key, None)
            if event is not None:
                event.set()


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
    session = load_session(season, gp, session_code)

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
        
        # Determine event type
        event_type = "race"
        if round_number == 0 or "Testing" in str(name):
            event_type = "testing"
        
        events.append({
            "name": str(name), 
            "round": int(round_number), 
            "date": date_iso,
            "type": event_type
        })
    events.sort(key=lambda item: item["round"])
    return events


SESSION_NAME_TO_CODE = {
    "Practice 1": "FP1",
    "Practice 2": "FP2",
    "Practice 3": "FP3",
    "Qualifying": "Q",
    "Sprint Qualifying": "SQ",
    "Sprint": "S",
    "Sprint Race": "S",
    "Sprint Shootout": "SS",
    "Race": "R",
}


def build_session_list(season, gp):
    # Check if this is a testing event
    if is_testing_event(season, gp):
        # For testing events, use get_testing_event
        try:
            event = fastf1.get_testing_event(season, 1)
        except Exception:
            # Fallback to regular event if testing event fails
            event = fastf1.get_event(season, gp)
    else:
        # Regular race event
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
        if not name or name == "None":
            continue

        # For testing events, modify session names to be more descriptive
        if is_testing_event(season, gp):
            if name == "Practice 1":
                name = "Testing Day 1 - Morning"
            elif name == "Practice 2":
                name = "Testing Day 1 - Afternoon"
            elif name == "Practice 3":
                name = "Testing Day 2 - Morning"
            # Add more descriptive names for testing sessions
            code = f"T{idx}"  # Use T1, T2, etc. for testing sessions
        else:
            code = SESSION_NAME_TO_CODE.get(name)
        
        if code is None:
            continue
        if code in seen_codes:
            continue
        seen_codes.add(code)
        sessions.append({"code": code, "name": name})

    return sessions


def build_driver_list(season, gp, session_code):
    session = load_session(season, gp, session_code)
    drivers = sorted(session.laps["Driver"].dropna().unique().tolist())
    driver_meta = {}

    try:
        results = session.results
    except Exception:
        results = None

    if results is not None and not results.empty:
        for _, row in results.iterrows():
            code = str(row.get("Abbreviation", "")).strip().upper()
            if not code:
                continue
            team_name = row.get("TeamName")
            team_color = row.get("TeamColor")
            if pd.isna(team_name):
                team_name = None
            if pd.isna(team_color):
                team_color = None
            color_value = None
            if team_color:
                color_value = f"#{str(team_color).strip().lstrip('#')}"
            driver_meta[code] = {"team_name": team_name, "team_color": color_value}

    for code in drivers:
        driver_meta.setdefault(code, {"team_name": None, "team_color": None})

    return drivers, driver_meta


def build_lap_list(season, gp, session_code, driver):
    session = load_session(season, gp, session_code)
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
                print(f"[API] /api/events error: {exc}", flush=True)
                traceback.print_exc()
                self._send_json(400, {"error": str(exc)})
            return

        if parsed.path == "/api/drivers":
            params = parse_qs(parsed.query)
            try:
                season = int(params.get("season", [2021])[0])
                gp = params.get("gp", ["Spanish Grand Prix"])[0]
                session_code = params.get("session", ["Q"])[0]
                drivers, driver_meta = build_driver_list(season, gp, session_code)
                self._send_json(
                    200,
                    {
                        "season": season,
                        "event": gp,
                        "session": session_code,
                        "drivers": drivers,
                        "driver_meta": driver_meta,
                    },
                )
            except Exception as exc:
                print(f"[API] /api/drivers error: {exc}", flush=True)
                traceback.print_exc()
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
                print(f"[API] /api/sessions error: {exc}", flush=True)
                traceback.print_exc()
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
                print(f"[API] /api/laps error: {exc}", flush=True)
                traceback.print_exc()
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
