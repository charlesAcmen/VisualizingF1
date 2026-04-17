"""
Telemetry service for processing and formatting driver lap data.
"""
import pandas as pd
from config import Config
from services.session_service import SessionService, get_display_session_name
from utils.helpers import format_lap_time, resolve_event_name


class TelemetryService:
    """
    Service for processing driver telemetry data.
    """
    
    @staticmethod
    def build_payload(season, event_name, session_code, driver, lap_selector):
        """
        Build telemetry payload for a single driver lap.
        
        Args:
            season: Season year
            event_name: Grand Prix name
            session_code: Session code (e.g., 'Q', 'R', 'FP1')
            driver: Driver code
            lap_selector: Lap selector ('fastest' or lap number)
            
        Returns:
            Dictionary containing meta, channels, channel_units, data, and corners
        """
        session = SessionService.load_session(season, event_name, session_code)

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

        # Get car data with global sampling frequency for unified data density
        car_data = lap_row.get_car_data()
        
        # Use global sampling frequency configuration
        if Config.GLOBAL_SAMPLING_FREQUENCY != 'original':
            car_data = car_data.resample_channels(Config.GLOBAL_SAMPLING_FREQUENCY)
        
        car_data = car_data.add_distance()
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

        # Get display session name to match Query section
        display_session_name = get_display_session_name(season, event_name, session.name, session_code)

        meta = {
            "season": season,
            "event": resolve_event_name(session.event),
            "session": display_session_name,
            "driver": driver,
            "lap_number": lap_number_value,
            "lap_time": lap_time,
        }

        return {
            "meta": meta,
            "channels": list(channel_units.keys()),
            "channel_units": channel_units,
            "data": data,
            "corners": SessionService.build_corners(session),
        }
