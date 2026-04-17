"""
Interpolation utilities for resampling telemetry data.
"""
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d


def interpolate_to_reference_count(data, target_count):
    """
    Interpolate driver data to match reference point count.
    
    This function creates a uniform distance grid and interpolates
    X, Y, Z coordinates and speed values to match the target count.
    
    Args:
        data: DataFrame with columns ['X', 'Y', 'Z', 'Speed', 'Distance']
        target_count: Target number of data points
        
    Returns:
        Interpolated DataFrame with target_count rows
    """
    if len(data) == target_count:
        return data.copy()
    
    # Create uniform distance grid
    min_dist, max_dist = data['Distance'].min(), data['Distance'].max()
    target_distances = np.linspace(min_dist, max_dist, target_count)
    
    # Interpolate each column
    interpolated_data = pd.DataFrame({'Distance': target_distances})
    
    for col in ['X', 'Y', 'Z', 'Speed']:
        # Create interpolation function
        interp_func = interp1d(data['Distance'], data[col], 
                               kind='linear', bounds_error=False, 
                               fill_value='extrapolate')
        interpolated_data[col] = interp_func(target_distances)
    
    return interpolated_data
