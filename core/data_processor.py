"""
Data processing utilities for preparing telemetry data.
"""
import pandas as pd


def prepare_driver_speed_data(session, driver, lap_selector, sample_frequency='0.1S'):
    """
    Prepare driver data with XYZ coordinates and speed for speed difference calculation.
    
    Args:
        session: FastF1 session object
        driver: Driver code
        lap_selector: Lap selector ('fastest' or lap number)
        sample_frequency: Sampling frequency for resampling
        
    Returns:
        DataFrame with columns ['X', 'Y', 'Z', 'Speed', 'Distance']
        
    Raises:
        ValueError: If data preparation fails
    """
    try:
        # Get lap data
        laps = session.laps.pick_drivers(driver)
        if laps.empty:
            raise ValueError(f"No laps found for driver '{driver}'.")
            
        if str(lap_selector).lower() == "fastest":
            lap = laps.pick_fastest()
            if lap is None or getattr(lap, "empty", False):
                raise ValueError(f"Fastest lap not found for driver '{driver}'.")
        else:
            try:
                lap_number = int(lap_selector)
            except ValueError as exc:
                raise ValueError("Lap must be 'fastest' or an integer.") from exc
            lap_matches = laps.pick_lap(lap_number)
            if lap_matches.empty:
                raise ValueError(f"Lap {lap_number} not found for driver '{driver}'.")
            lap = lap_matches.iloc[0]
        
        # Get car data and position data with resampling
        car_data = lap.get_car_data()
        pos_data = lap.get_pos_data()
        
        if car_data.empty or pos_data.empty:
            raise ValueError(f"No telemetry data available for driver '{driver}'.")
        
        # Resample to higher frequency for better data density
        if sample_frequency != 'original':
            car_data = car_data.resample_channels(sample_frequency)
            pos_data = pos_data.resample_channels(sample_frequency)
            merged_data = car_data.merge_channels(pos_data)
        else:
            # Original data processing
            car_data_reset = car_data.reset_index(drop=True)
            pos_data_reset = pos_data.reset_index(drop=True)
            merged_data = pd.merge_asof(car_data_reset, pos_data_reset, on='Time', direction='nearest')
            merged_data = merged_data.add_distance()
        
        # Ensure distance column exists
        if 'Distance' not in merged_data.columns:
            merged_data = merged_data.add_distance()
        
        # Select relevant columns
        result = merged_data[['X', 'Y', 'Z', 'Speed', 'Distance']].copy()
        
        # Remove rows with NaN values
        result = result.dropna()
        
        if result.empty:
            raise ValueError(f"No valid data after merging for driver '{driver}'.")
        
        return result
        
    except Exception as e:
        raise ValueError(f"Error preparing data for driver '{driver}': {str(e)}")
