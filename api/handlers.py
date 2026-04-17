"""
HTTP request handlers for the FastF1 telemetry API.
"""
import json
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from time import perf_counter

import logging

from services.session_service import (
    SessionService,
    get_display_session_name,
    build_event_list,
    build_session_list,
    build_driver_list,
    build_lap_list
)
from services.telemetry_service import TelemetryService
from services.speed_diff_service import SpeedDiffService
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s", force=True)


class TelemetryHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for telemetry API endpoints.
    """
    
    def log_message(self, format, *args):
        """
        Override log_message to use custom format.
        """
        print(f"[HTTP] {self.address_string()} - {format % args}", flush=True)

    def _send_json(self, status, payload):
        """
        Send JSON response with CORS headers.
        
        Args:
            status: HTTP status code
            payload: Dictionary to serialize as JSON
        """
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
        """
        Handle OPTIONS request for CORS preflight.
        """
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        """
        Handle GET requests.
        """
        parsed = urlparse(self.path)
        
        # /api/events - Get event list for a season
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

        # /api/drivers - Get driver list for a session
        if parsed.path == "/api/drivers":
            params = parse_qs(parsed.query)
            try:
                season = int(params.get("season", [2021])[0])
                event_name = params.get("event", ["Spanish Grand Prix"])[0]
                session_code = params.get("session", ["Q"])[0]
                drivers, driver_meta = build_driver_list(season, event_name, session_code)
                self._send_json(
                    200,
                    {
                        "season": season,
                        "event": event_name,
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

        # /api/sessions - Get session list for an event
        if parsed.path == "/api/sessions":
            params = parse_qs(parsed.query)
            try:
                season = int(params.get("season", [2021])[0])
                event_name = params.get("event", ["Spanish Grand Prix"])[0]
                sessions = build_session_list(season, event_name)
                self._send_json(
                    200,
                    {"season": season, "event": event_name, "sessions": sessions},
                )
            except Exception as exc:
                print(f"[API] /api/sessions error: {exc}", flush=True)
                traceback.print_exc()
                self._send_json(400, {"error": str(exc)})
            return

        # /api/laps - Get lap list for a driver
        if parsed.path == "/api/laps":
            params = parse_qs(parsed.query)
            try:
                season = int(params.get("season", [2021])[0])
                event_name = params.get("event", ["Spanish Grand Prix"])[0]
                session_code = params.get("session", ["Q"])[0]
                driver = params.get("driver", ["VER"])[0].upper()
                laps = build_lap_list(season, event_name, session_code, driver)
                self._send_json(
                    200,
                    {
                        "season": season,
                        "event": event_name,
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

        # /api/lap - Get telemetry data for a single lap
        if parsed.path == "/api/lap":
            params = parse_qs(parsed.query)
            try:
                season = int(params.get("season", [2021])[0])
                event_name = params.get("event", ["Spanish Grand Prix"])[0]
                session_code = params.get("session", ["Q"])[0]
                driver = params.get("driver", ["VER"])[0].upper()
                lap_selector = params.get("lap", ["fastest"])[0]
                started = perf_counter()
                print(
                    f"[API] /api/lap season={season} event={event_name} session={session_code} driver={driver} lap={lap_selector}",
                    flush=True,
                )

                payload = TelemetryService.build_payload(
                    season=season,
                    event_name=event_name,
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

        # /api/speed-diff - Get speed difference comparison
        if parsed.path == "/api/speed-diff":
            params = parse_qs(parsed.query)
            try:
                season = int(params.get("season", [2023])[0])
                event_name = params.get("event", ["Spanish Grand Prix"])[0]
                session_code = params.get("session", ["Q"])[0]
                
                # Parse drivers list
                drivers_param = params.get("drivers", ["VER,LEC"])
                drivers = [d.strip().upper() for d in drivers_param[0].split(",") if d.strip()]
                
                # Parse lap selectors (format: "VER:fastest,LEC:12" or just "fastest" for all)
                lap_selectors_param = params.get("lap_selectors", ["fastest"])
                lap_selectors_str = lap_selectors_param[0]
                
                lap_selectors = {}
                if ":" in lap_selectors_str:
                    # Individual lap selectors per driver
                    for selector in lap_selectors_str.split(","):
                        if ":" in selector:
                            driver, lap = selector.strip().split(":", 1)
                            lap_selectors[driver.strip().upper()] = lap.strip()
                else:
                    # Same lap selector for all drivers
                    for driver in drivers:
                        lap_selectors[driver] = lap_selectors_str.strip()
                
                # Optional reference driver
                reference_driver = params.get("reference_driver", [None])[0]
                if reference_driver:
                    reference_driver = reference_driver.strip().upper()

                # Optional sampling frequency (use config default if not specified)
                sample_frequency = params.get("sample_frequency", [None])[0]
                if sample_frequency:
                    sample_frequency = Config.validate_frequency(sample_frequency)
                else:
                    sample_frequency = Config.GLOBAL_SAMPLING_FREQUENCY
                
                # Optional k-neighbors and distance threshold (use config defaults if not specified)
                k_neighbors_param = params.get("k_neighbors", [None])[0]
                k_neighbors = int(k_neighbors_param) if k_neighbors_param else Config.DEFAULT_K_NEIGHBORS

                max_distance_threshold_param = params.get("max_distance_threshold", [None])[0]
                max_distance_threshold = float(max_distance_threshold_param) if max_distance_threshold_param else Config.DEFAULT_MAX_DISTANCE_THRESHOLD
                
                started = perf_counter()
                print(
                    f"[API] /api/speed-diff season={season} event={event_name} session={session_code} drivers={drivers} lap_selectors={lap_selectors} freq={sample_frequency} k={k_neighbors} threshold={max_distance_threshold}",
                    flush=True,
                )

                payload = SpeedDiffService.build_payload(
                    season=season,
                    event_name=event_name,
                    session_code=session_code,
                    drivers=drivers,
                    lap_selectors=lap_selectors,
                    reference_driver=reference_driver,
                    sample_frequency=sample_frequency,
                    k_neighbors=k_neighbors,
                    max_distance_threshold=max_distance_threshold
                )
                
                elapsed_ms = (perf_counter() - started) * 1000
                total_comparisons = len(payload.get("comparisons", {}))
                print(f"[API] /api/speed-diff success comparisons={total_comparisons} elapsed_ms={elapsed_ms:.1f}", flush=True)
                self._send_json(200, payload)
                
            except Exception as exc:
                print(f"[API] /api/speed-diff error: {exc}", flush=True)
                traceback.print_exc()
                self._send_json(400, {"error": str(exc)})
            return

        # /api/health - Health check endpoint
        if parsed.path == "/api/health":
            self._send_json(200, {"status": "ok"})
            return

        # 404 for unknown paths
        self.send_response(404)
        self.end_headers()
