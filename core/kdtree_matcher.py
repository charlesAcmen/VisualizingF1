"""
KD-tree based spatial matching for comparing driver telemetry.
"""
import numpy as np
from scipy.spatial import KDTree


def calculate_speed_differences(reference_data, comparison_data, k_neighbors=3, max_distance_threshold=10.0):
    """
    Calculate speed differences between reference and comparison driver using KD-tree.
    
    Algorithm:
    - Build KD-tree with comparison driver XYZ coordinates
    - For each point in reference driver, find k nearest neighbors in comparison driver
    - Use inverse distance weighting to estimate comparison driver speed at reference point
    - Speed difference = estimated_comparison_speed - reference_speed
    - X-axis uses reference driver's Distance
    
    Args:
        reference_data: DataFrame with columns ['X', 'Y', 'Z', 'Speed', 'Distance']
        comparison_data: DataFrame with columns ['X', 'Y', 'Z', 'Speed', 'Distance']
        k_neighbors: Number of nearest neighbors to use for interpolation
        max_distance_threshold: Maximum distance (meters) for valid matches
        
    Returns:
        Dictionary containing:
        - speed_differences: List of speed difference values
        - reference_speeds: List of reference driver speeds
        - comparison_speeds_estimated: List of estimated comparison speeds
        - distance_coordinates: List of distance coordinates
        - match_statistics: Dictionary with matching statistics
    """
    # Extract coordinates and speeds
    ref_coords = reference_data[['X', 'Y', 'Z']].values
    comp_coords = comparison_data[['X', 'Y', 'Z']].values
    ref_speeds = reference_data['Speed'].values
    comp_speeds = comparison_data['Speed'].values

    # Build KD-tree with comparison driver coordinates
    kdtree = KDTree(comp_coords)

    # Find k nearest neighbors in comparison data for each reference point
    distances, indices = kdtree.query(ref_coords, k=k_neighbors)

    # Handle case where k=1 (distances and indices are 1D)
    if k_neighbors == 1:
        distances = distances.reshape(-1, 1)
        indices = indices.reshape(-1, 1)

    # Calculate weighted average speeds for comparison driver at reference points
    comp_speeds_estimated = np.zeros(len(ref_coords))
    valid_matches = np.ones(len(ref_coords), dtype=bool)

    for i in range(len(ref_coords)):
        # Filter neighbors by distance threshold
        valid_neighbors = distances[i] <= max_distance_threshold

        if not np.any(valid_neighbors):
            valid_matches[i] = False
            continue

        # Use inverse distance weighting
        neighbor_distances = distances[i][valid_neighbors]
        neighbor_indices = indices[i][valid_neighbors]
        neighbor_speeds = comp_speeds[neighbor_indices]

        # Calculate weights (inverse distance, avoid division by zero)
        weights = 1.0 / (neighbor_distances + 1e-6)
        weights = weights / weights.sum()  # Normalize weights

        # Weighted average of neighbor speeds
        comp_speeds_estimated[i] = np.sum(weights * neighbor_speeds)

    # Calculate speed differences (estimated comparison speed - reference speed)
    speed_diffs = np.full(len(ref_coords), np.nan)
    speed_diffs[valid_matches] = comp_speeds_estimated[valid_matches] - ref_speeds[valid_matches]

    # Calculate statistics
    valid_diffs = speed_diffs[~np.isnan(speed_diffs)]

    # Filter out NaN values to avoid vertical jump lines in chart
    valid_indices = ~np.isnan(speed_diffs)
    filtered_distances = reference_data['Distance'].values[valid_indices]
    filtered_speed_diffs = speed_diffs[valid_indices]

    result = {
        'speed_differences': [float(x) for x in filtered_speed_diffs],
        'reference_speeds': [float(x) for x in ref_speeds[valid_indices]],
        'comparison_speeds_estimated': [float(x) for x in comp_speeds_estimated[valid_indices]],
        'distance_coordinates': [float(x) for x in filtered_distances],
        'match_statistics': {
            'total_points': len(ref_coords),
            'valid_matches': int(np.sum(valid_matches)),
            'match_rate': float(np.sum(valid_matches) / len(ref_coords)),
            'mean_speed_diff': float(np.mean(valid_diffs)) if len(valid_diffs) > 0 else None,
            'std_speed_diff': float(np.std(valid_diffs)) if len(valid_diffs) > 0 else None,
            'max_speed_diff': float(np.max(np.abs(valid_diffs))) if len(valid_diffs) > 0 else None,
        }
    }

    return result
