"""
Helper functions for data formatting and event resolution.
"""
import pandas as pd


def format_lap_time(value):
    """
    Format lap time as MM:SS.mmm.
    
    Args:
        value: Timedelta object or None
        
    Returns:
        Formatted string or None
    """
    if value is None or pd.isna(value):
        return None
    total_seconds = value.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = total_seconds - minutes * 60
    return f"{minutes}:{seconds:06.3f}"


def resolve_event_name(event):
    """
    Extract event name from event object.
    
    Args:
        event: FastF1 event object or dict
        
    Returns:
        Event name string
    """
    if event is None:
        return None
    try:
        return event.get("EventName")
    except AttributeError:
        try:
            return event["EventName"]
        except Exception:
            return str(event)


# Constants for testing event patterns
TESTING_PATTERNS = [
    "PRE-SEASON TESTING",
    "PRE-SEASON TEST",
    "PRE-SEASON TRACK SESSION",
    "Testing",
    "Test"
]


def is_testing_event(season, gp):
    """
    Check if an event is a testing event.
    
    Args:
        season: Season year
        gp: Grand Prix name or event object
        
    Returns:
        True if testing event, False otherwise
    """
    import fastf1
    
    try:
        # First check if gp name contains any testing patterns
        if isinstance(gp, str):
            gp_lower = gp.lower()
            for pattern in TESTING_PATTERNS:
                if pattern.lower() in gp_lower:
                    return True
        
        # Then check schedule for exact matches
        schedule = fastf1.get_event_schedule(season)
        for _, event in schedule.iterrows():
            if (event['EventName'] == gp or 
                (isinstance(gp, str) and gp.lower() in event['EventName'].lower())):
                return (event['RoundNumber'] == 0 or 
                       'Testing' in str(event['EventName']))
        
        # Check official names in schedule
        for _, event in schedule.iterrows():
            if ('OfficialEventName' in event and 
                isinstance(gp, str) and 
                gp.lower() in str(event['OfficialEventName']).lower()):
                return (event['RoundNumber'] == 0 or 
                       'Testing' in str(event['EventName']))
        
        return False
    except Exception:
        return 'Testing' in str(gp)


def get_testing_event_number(season, gp):
    """
    Get testing event number (1, 2, or 3) for a given testing event.
    
    Args:
        season: Season year
        gp: Grand Prix name
        
    Returns:
        Testing event number (1-3) or 1 if cannot determine
    """
    import fastf1
    
    try:
        if not is_testing_event(season, gp):
            return None
        
        schedule = fastf1.get_event_schedule(season)
        testing_events = []
        
        for _, event in schedule.iterrows():
            if event['RoundNumber'] == 0 or 'Testing' in str(event['EventName']):
                testing_events.append(event)
        
        # Match by exact name first
        for i, event in enumerate(testing_events, 1):
            if event['EventName'] == gp:
                return i
            if 'OfficialEventName' in event and event['OfficialEventName'] == gp:
                return i
        
        # Match by official name patterns
        if isinstance(gp, str):
            gp_lower = gp.lower()
            for i, event in enumerate(testing_events, 1):
                if 'OfficialEventName' in event:
                    official_name = str(event['OfficialEventName']).lower()
                    if gp_lower in official_name:
                        return i
        
        # Match by partial name
        for i, event in enumerate(testing_events, 1):
            if (isinstance(gp, str) and 
                gp.lower() in str(event['OfficialEventName']).lower()):
                return i
        
        return 1
    except Exception:
        return 1
