"""
Test script to analyze XYZ coordinate distances and validate threshold settings.
This checks if there are cases where two different corners are close in 3D space
but far in lap distance, which could cause incorrect KD-tree matching.
"""

import numpy as np
import pandas as pd
import fastf1
from scipy.spatial.distance import cdist
from config import Config

def analyze_xyz_distances(season=2023, event="Monaco Grand Prix", session="Q", driver="VER"):
    """
    Analyze XYZ coordinate distances to identify potential threshold issues.
    """
    print(f"Loading session: {season} {event} {session}")
    session_obj = fastf1.get_session(season, event, session)
    session_obj.load(telemetry=True, weather=False, messages=False)
    
    # Get driver's fastest lap
    laps = session_obj.laps.pick_drivers(driver)
    lap = laps.pick_fastest()
    
    # Get car data and position data
    car_data = lap.get_car_data()
    pos_data = lap.get_pos_data()
    
    # Resample to config frequency
    if Config.GLOBAL_SAMPLING_FREQUENCY != 'original':
        car_data = car_data.resample_channels(Config.GLOBAL_SAMPLING_FREQUENCY)
        pos_data = pos_data.resample_channels(Config.GLOBAL_SAMPLING_FREQUENCY)
        merged_data = car_data.merge_channels(pos_data)
    else:
        car_data = car_data.add_distance()
        car_data_reset = car_data.reset_index(drop=True)
        pos_data_reset = pos_data.reset_index(drop=True)
        merged_data = pd.merge_asof(car_data_reset, pos_data_reset, on='Time', direction='nearest')
    
    if 'Distance' not in merged_data.columns:
        merged_data = merged_data.add_distance()
    
    # Extract XYZ and Distance
    merged_data = merged_data[['X', 'Y', 'Z', 'Distance']].copy()
    merged_data = merged_data.dropna()
    
    xyz = merged_data[['X', 'Y', 'Z']].values
    distances = merged_data['Distance'].values
    
    print(f"\nData points: {len(xyz)}")
    print(f"Distance range: {distances.min():.1f}m to {distances.max():.1f}m")
    print(f"Total lap distance: {distances.max() - distances.min():.1f}m")
    
    # Calculate pairwise XYZ distances
    print("\nCalculating pairwise XYZ distances...")
    xyz_distances = cdist(xyz, xyz)
    
    # Set diagonal to infinity to avoid self-comparison
    np.fill_diagonal(xyz_distances, np.inf)
    
    # Find minimum XYZ distance for each point
    min_xyz_distances = np.min(xyz_distances, axis=1)
    
    print(f"\nXYZ Distance Statistics:")
    print(f"  Minimum: {min_xyz_distances.min():.3f}m")
    print(f"  25th percentile: {np.percentile(min_xyz_distances, 25):.3f}m")
    print(f"  50th percentile (median): {np.percentile(min_xyz_distances, 50):.3f}m")
    print(f"  75th percentile: {np.percentile(min_xyz_distances, 75):.3f}m")
    print(f"  95th percentile: {np.percentile(min_xyz_distances, 95):.3f}m")
    print(f"  Maximum: {min_xyz_distances.max():.3f}m")
    
    # Check for cases where XYZ distance is small but lap distance is large
    print("\nChecking for potential threshold issues...")
    print("(Cases where XYZ distance is small but lap distance is large)")
    
    thresholds = [5, 10, 15, 20, 30]
    
    for threshold in thresholds:
        # Find pairs with XYZ distance < threshold
        close_xyz_pairs = np.where(xyz_distances < threshold)
        
        if len(close_xyz_pairs[0]) > 0:
            # Calculate lap distance differences for these pairs
            lap_dist_diffs = np.abs(distances[close_xyz_pairs[0]] - distances[close_xyz_pairs[1]])
            
            # Find pairs with large lap distance difference (> 20m for more sensitive detection)
            large_lap_diff_mask = lap_dist_diffs > 20
            problematic_pairs = np.sum(large_lap_diff_mask)
            large_lap_diff_mask_50 = lap_dist_diffs > 50
            problematic_pairs_50 = np.sum(large_lap_diff_mask_50)

            if problematic_pairs > 0:
                max_lap_diff = np.max(lap_dist_diffs[large_lap_diff_mask])
                print(f"\n  Threshold {threshold}m:")
                print(f"    Total close XYZ pairs: {len(close_xyz_pairs[0])}")
                print(f"    Pairs with >20m lap distance: {problematic_pairs}")
                print(f"    Pairs with >50m lap distance: {problematic_pairs_50}")
                print(f"    Maximum lap distance difference: {max_lap_diff:.1f}m")
            else:
                print(f"\n  Threshold {threshold}m: No problematic pairs found")
    
    # Analyze point density
    print("\nPoint Density Analysis:")
    avg_distance_between_points = (distances.max() - distances.min()) / len(distances)
    print(f"  Average distance between consecutive points: {avg_distance_between_points:.3f}m")
    print(f"  Config threshold: {Config.DEFAULT_MAX_DISTANCE_THRESHOLD}m")
    print(f"  Threshold covers approximately: {Config.DEFAULT_MAX_DISTANCE_THRESHOLD / avg_distance_between_points:.1f} points")
    
    # Find specific examples of close XYZ but far lap distance
    print("\nFinding specific examples of potential threshold issues...")
    threshold = Config.DEFAULT_MAX_DISTANCE_THRESHOLD
    close_xyz_pairs = np.where(xyz_distances < threshold)
    
    if len(close_xyz_pairs[0]) > 0:
        lap_dist_diffs = np.abs(distances[close_xyz_pairs[0]] - distances[close_xyz_pairs[1]])
        large_lap_diff_mask = lap_dist_diffs > 100  # > 100m lap distance
        
        if np.any(large_lap_diff_mask):
            indices = np.where(large_lap_diff_mask)[0]
            print(f"  Found {len(indices)} examples where XYZ < {threshold}m but lap distance > 100m")
            print("\n  Top 5 examples:")
            
            # Sort by lap distance difference
            sorted_indices = indices[np.argsort(lap_dist_diffs[indices])[::-1]][:5]
            
            for i, idx in enumerate(sorted_indices):
                i1, i2 = close_xyz_pairs[0][idx], close_xyz_pairs[1][idx]
                xyz_dist = xyz_distances[i1, i2]
                lap_dist = lap_dist_diffs[idx]
                print(f"    {i+1}. Point {i1} (dist={distances[i1]:.1f}m) vs Point {i2} (dist={distances[i2]:.1f}m)")
                print(f"       XYZ distance: {xyz_dist:.3f}m, Lap distance: {lap_dist:.1f}m")
        else:
            print(f"  No examples found with threshold {threshold}m")
    
    return {
        'min_xyz_distances': min_xyz_distances,
        'distances': distances,
        'xyz_distances': xyz_distances
    }


if __name__ == "__main__":
    try:
        result = analyze_xyz_distances()
        print("\nAnalysis complete.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
