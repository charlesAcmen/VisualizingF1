"""
Session service for managing FastF1 session loading and caching.
"""
import fastf1
import pandas as pd
from pathlib import Path
from utils.cache import SessionCache
from utils.helpers import is_testing_event, get_testing_event_number
from config import Config


# Global cache instance
SESSION_CACHE_MAX_SIZE = 4
SESSION_CACHE = SessionCache(max_size=SESSION_CACHE_MAX_SIZE)

# Setup FastF1 cache
CACHE_DIR = Path(__file__).resolve().parent.parent / ".fastf1_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))


class SessionService:
    """
    Service for loading and caching FastF1 sessions.
    """
    
    @staticmethod
    def load_session(season, gp, session_code):
        """
        Load session with caching support.
        
        Args:
            season: Season year
            gp: Grand Prix name
            session_code: Session code (e.g., 'Q', 'R', 'FP1')
            
        Returns:
            FastF1 session object
        """
        key = (int(season), str(gp), str(session_code))
        
        # Check cache
        cached_session = SESSION_CACHE.get(key)
        if cached_session is not None:
            SESSION_CACHE.hit(key)
            return cached_session
        
        # Check if already loading
        wait_event, is_loader = SESSION_CACHE.get_or_create_loading_event(key)
        
        if not is_loader:
            SESSION_CACHE.wait(key)
            wait_event.wait()
            cached_session = SESSION_CACHE.get(key)
            if cached_session is not None:
                SESSION_CACHE.hit(key)
                return cached_session
            raise RuntimeError(f"Session load failed for {key}.")
        
        # Load session
        try:
            SESSION_CACHE.miss(key)
            
            # Check if this is a testing event
            testing_event_num = None
            session_number = None
            
            if is_testing_event(season, gp):
                testing_event_num = get_testing_event_number(season, gp)
                
                # Parse session code for testing events (T11, T12, T13, T21, T22, T23)
                if session_code.startswith('T') and len(session_code) == 3:
                    try:
                        session_number = int(session_code[2])
                    except ValueError:
                        session_number = 1
                else:
                    session_number = 1
                
                session = fastf1.get_testing_session(season, testing_event_num, session_number)
            else:
                # Regular race event
                session = fastf1.get_session(season, gp, session_code)
            
            session.load(telemetry=True, weather=False, messages=False)
            SESSION_CACHE.set(key, session)
            return session
        finally:
            SESSION_CACHE.remove_loading_event(key)
    
    @staticmethod
    def build_corners(session):
        """
        Extract corner information from circuit info.
        
        Args:
            session: FastF1 session object
            
        Returns:
            List of corner dictionaries with distance, number, letter
        """
        import pandas as pd
        
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
            corners.append({
                "distance": float(corner["Distance"]),
                "number": str(corner["Number"]),
                "letter": str(letter),
            })
        return corners


def build_event_list(season):
    """
    Build list of events for a given season.
    
    Args:
        season: Season year
        
    Returns:
        List of event dictionaries with name, round, date, type
    """
    import pandas as pd
    
    schedule = fastf1.get_event_schedule(season)
    events = []
    
    for _, row in schedule.iterrows():
        name = row.get("EventName") if hasattr(row, "get") else row["EventName"]
        round_number = row.get("RoundNumber") if hasattr(row, "get") else row["RoundNumber"]
        date_value = row.get("EventDate") if hasattr(row, "get") else row.get("EventDate", None)
        official_name = row.get("OfficialEventName") if hasattr(row, "get") else row.get("OfficialEventName", "")
        
        if pd.isna(date_value):
            date_value = None
        date_iso = date_value.isoformat() if date_value is not None else None
        
        # Determine event type and proper name
        event_type = "testing" if round_number == 0 or "Testing" in str(name) else "race"
        
        # For testing events, prefer OfficialEventName if it contains "PRE-SEASON TESTING"
        # For race events, always use EventName for consistency
        if event_type == "testing" and official_name and "PRE-SEASON TESTING" in str(official_name):
            display_name = str(official_name)
        else:
            display_name = str(name)
        
        events.append({
            "name": display_name, 
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


def get_display_session_name(season, event_name, session_name, session_code):
    """
    Get the display session name that matches Query section format.
    
    Args:
        season: Season year
        event_name: Grand Prix name
        session_name: Session name from FastF1
        session_code: Session code
        
    Returns:
        Formatted session name string
    """
    if is_testing_event(season, event_name):
        testing_event_num = get_testing_event_number(season, event_name)
        
        # Match the same logic as build_session_list
        if session_name == "Practice 1":
            return f"Day 1 (T{testing_event_num}1)"
        elif session_name == "Practice 2":
            return f"Day 2 (T{testing_event_num}2)"
        elif session_name == "Practice 3":
            return f"Day 3 (T{testing_event_num}3)"
        else:
            return f"{session_name} (T{testing_event_num}{session_code[-1]})"
    else:
        # For race events, return the standard name with code
        return f"{session_name} ({session_code})"


def build_session_list(season, event_name):
    """
    Build list of available sessions for an event.
    
    Args:
        season: Season year
        event_name: Grand Prix name
        
    Returns:
        List of session dictionaries with code and name
    """
    # Check if this is a testing event
    if is_testing_event(season, event_name):
        # For testing events, always use get_testing_event with the correct event number
        testing_event_num = get_testing_event_number(season, event_name)
        event = fastf1.get_testing_event(season, testing_event_num)
    else:
        # Regular race event
        event = fastf1.get_event(season, event_name)
    
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
        if is_testing_event(season, event_name):
            testing_event_num = get_testing_event_number(season, event_name)
            
            # Create more descriptive names for testing sessions
            if name == "Practice 1":
                name = f"Day 1 (T{testing_event_num}1)"
            elif name == "Practice 2":
                name = f"Day 2 (T{testing_event_num}2)"
            elif name == "Practice 3":
                name = f"Day 3 (T{testing_event_num}3)"
            else:
                name = f"{name} (T{testing_event_num}{idx})"
            
            code = f"T{testing_event_num}{idx}"
        else:
            code = SESSION_NAME_TO_CODE.get(name)
        
        if code is None:
            continue
        if code in seen_codes:
            continue
        seen_codes.add(code)
        sessions.append({"code": code, "name": name})

    return sessions


def build_driver_list(season, event_name, session_code):
    """
    Build list of drivers for a session.
    
    Args:
        season: Season year
        event_name: Grand Prix name
        session_code: Session code
        
    Returns:
        Tuple of (driver_list, driver_metadata_dict)
    """
    import pandas as pd
    
    session = SessionService.load_session(season, event_name, session_code)
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


def build_lap_list(season, event_name, session_code, driver):
    """
    Build list of lap numbers for a driver in a session.
    
    Args:
        season: Season year
        event_name: Grand Prix name
        session_code: Session code
        driver: Driver code
        
    Returns:
        List of lap numbers
    """
    session = SessionService.load_session(season, event_name, session_code)
    laps = session.laps.pick_drivers(driver)
    if laps.empty:
        raise ValueError(f"No laps found for driver '{driver}'.")
    lap_numbers = (
        laps["LapNumber"].dropna().astype(int).sort_values().unique().tolist()
    )
    return lap_numbers
