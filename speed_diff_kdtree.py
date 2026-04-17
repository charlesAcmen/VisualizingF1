import numpy as np
import pandas as pd
from scipy.spatial import KDTree
from scipy.interpolate import interp1d
import fastf1
from typing import Dict, List, Tuple, Optional
import time

class SpeedDifferenceCalculator:
    """
    Calculate speed differences between drivers using KD-tree for XYZ coordinate matching.
    
    Algorithm:
    1. Use the driver with most points as reference
    2. Upscale other drivers to match reference point count using interpolation
    3. Build KD-tree with reference driver's XYZ coordinates
    4. For each point in other drivers, find k nearest neighbors in reference
    5. Use weighted average of k nearest speeds for comparison
    """
    
    def __init__(self, k_neighbors: int = 5, max_distance_threshold: float = 30.0, sample_frequency: str = '0.1S'):
        """
        Initialize the calculator.
        
        Args:
            k_neighbors: Number of nearest neighbors to consider (default: 5)
            max_distance_threshold: Max distance in meters for valid matches (default: 30m)
            sample_frequency: Resampling frequency (default: '0.1S' for 10Hz)
        """
        self.k = k_neighbors
        self.max_distance = max_distance_threshold
        self.sample_frequency = sample_frequency
        
    def prepare_driver_data(self, session, driver: str, lap_selector: str = "fastest") -> Optional[pd.DataFrame]:
        """
        Prepare driver data with XYZ coordinates and speed.
        
        Args:
            session: FastF1 session object
            driver: Driver identifier
            lap_selector: "fastest" or lap number
            
        Returns:
            DataFrame with columns: ['X', 'Y', 'Z', 'Speed', 'Distance'] or None
        """
        try:
            # Get lap data
            laps = session.laps.pick_drivers(driver)
            if laps.empty:
                print(f"No laps found for driver {driver}")
                return None
                
            if lap_selector.lower() == "fastest":
                lap = laps.pick_fastest()
                if lap is None or getattr(lap, "empty", False):
                    print(f"Fastest lap not found for driver {driver}")
                    return None
            else:
                try:
                    lap_number = int(lap_selector)
                except ValueError:
                    print(f"Invalid lap selector: {lap_selector}")
                    return None
                    
                lap_matches = laps.pick_lap(lap_number)
                if lap_matches.empty:
                    print(f"Lap {lap_number} not found for driver {driver}")
                    return None
                lap = lap_matches.iloc[0]
            
            # Get car data and position data with resampling
            car_data = lap.get_car_data()
            pos_data = lap.get_pos_data()
            
            if car_data.empty or pos_data.empty:
                print(f"No data available for driver {driver}")
                return None
            
            # Resample to higher frequency for better data density
            if self.sample_frequency != 'original':
                car_data = car_data.resample_channels(self.sample_frequency)
                pos_data = pos_data.resample_channels(self.sample_frequency)
                merged_data = car_data.merge_channels(pos_data)
            else:
                # Original data processing
                car_data = car_data.add_distance()
                car_data_reset = car_data.reset_index(drop=True)
                pos_data_reset = pos_data.reset_index(drop=True)
                merged_data = pd.merge_asof(car_data_reset, pos_data_reset, on='Time', direction='nearest')
            
            # Ensure distance column exists
            if 'Distance' not in merged_data.columns:
                merged_data = merged_data.add_distance()
            
            # Select relevant columns
            result = merged_data[['X', 'Y', 'Z', 'Speed', 'Distance']].copy()
            
            # Remove rows with NaN values
            result = result.dropna()
            
            if result.empty:
                print(f"No valid data after merging for driver {driver}")
                return None
                
            print(f"Driver {driver}: {len(result)} points prepared")
            return result
            
        except Exception as e:
            print(f"Error preparing data for driver {driver}: {e}")
            return None
    
    def interpolate_to_reference_count(self, data: pd.DataFrame, target_count: int) -> pd.DataFrame:
        """
        Interpolate driver data to match reference point count.
        
        Args:
            data: Driver data with Distance, X, Y, Z, Speed
            target_count: Target number of points
            
        Returns:
            Interpolated DataFrame with target_count points
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
    
    def calculate_speed_differences(self, reference_driver_data: pd.DataFrame, 
                                 comparison_driver_data: pd.DataFrame) -> Dict:
        """
        Calculate speed differences between reference and comparison driver.
        
        Args:
            reference_driver_data: Reference driver data (most points)
            comparison_driver_data: Other driver data
            
        Returns:
            Dictionary with speed differences and statistics
        """
        start_time = time.time()
        
        # Ensure both datasets have same number of points
        ref_count = len(reference_driver_data)
        comp_count = len(comparison_driver_data)
        
        if ref_count != comp_count:
            print(f"Point count mismatch: ref={ref_count}, comp={comp_count}")
            # Interpolate comparison driver to match reference
            comparison_driver_data = self.interpolate_to_reference_count(comparison_driver_data, ref_count)
            print(f"Interpolated comparison driver to {len(comparison_driver_data)} points")
        
        # Build KD-tree with reference driver XYZ coordinates
        ref_coords = reference_driver_data[['X', 'Y', 'Z']].values
        comp_coords = comparison_driver_data[['X', 'Y', 'Z']].values
        ref_speeds = reference_driver_data['Speed'].values
        comp_speeds = comparison_driver_data['Speed'].values
        
        kdtree = KDTree(ref_coords)
        
        # Find k nearest neighbors for each comparison point
        distances, indices = kdtree.query(comp_coords, k=self.k)
        
        # Handle case where k=1 (distances and indices are 1D)
        if self.k == 1:
            distances = distances.reshape(-1, 1)
            indices = indices.reshape(-1, 1)
        
        # Calculate weighted average speeds using inverse distance weighting
        ref_speeds_matched = np.zeros(len(comp_coords))
        weights_sum = np.zeros(len(comp_coords))
        valid_matches = np.ones(len(comp_coords), dtype=bool)
        
        for i in range(len(comp_coords)):
            # Filter neighbors by distance threshold
            valid_neighbors = distances[i] <= self.max_distance
            
            if not np.any(valid_neighbors):
                valid_matches[i] = False
                continue
            
            # Use inverse distance weighting
            neighbor_distances = distances[i][valid_neighbors]
            neighbor_indices = indices[i][valid_neighbors]
            neighbor_speeds = ref_speeds[neighbor_indices]
            
            # Calculate weights (inverse distance, avoid division by zero)
            weights = 1.0 / (neighbor_distances + 1e-6)
            weights = weights / weights.sum()  # Normalize weights
            
            # Weighted average of neighbor speeds
            ref_speeds_matched[i] = np.sum(weights * neighbor_speeds)
            weights_sum[i] = weights.sum()
        
        # Calculate speed differences
        speed_diffs = np.full(len(comp_coords), np.nan)
        speed_diffs[valid_matches] = comp_speeds[valid_matches] - ref_speeds_matched[valid_matches]
        
        # Calculate statistics
        valid_diffs = speed_diffs[~np.isnan(speed_diffs)]
        
        elapsed_time = time.time() - start_time
        
        result = {
            'speed_differences': speed_diffs,
            'reference_speeds': ref_speeds_matched,
            'comparison_speeds': comp_speeds,
            'valid_matches': valid_matches,
            'match_statistics': {
                'total_points': len(comp_coords),
                'valid_matches': np.sum(valid_matches),
                'match_rate': np.sum(valid_matches) / len(comp_coords),
                'mean_speed_diff': np.mean(valid_diffs) if len(valid_diffs) > 0 else np.nan,
                'std_speed_diff': np.std(valid_diffs) if len(valid_diffs) > 0 else np.nan,
                'max_speed_diff': np.max(np.abs(valid_diffs)) if len(valid_diffs) > 0 else np.nan,
                'processing_time': elapsed_time
            }
        }
        
        return result
    
    def compare_multiple_drivers(self, session, drivers: List[str], 
                               lap_selector: Dict[str, str] = None) -> Dict:
        """
        Compare speed differences among multiple drivers.
        
        Args:
            session: FastF1 session object
            drivers: List of driver identifiers
            lap_selector: Dict mapping driver to lap selector ("fastest" or lap number)
            
        Returns:
            Dictionary with comparison results for all driver pairs
        """
        if lap_selector is None:
            lap_selector = {driver: "fastest" for driver in drivers}
        
        # Prepare data for all drivers
        driver_data = {}
        for driver in drivers:
            data = self.prepare_driver_data(session, driver, lap_selector.get(driver, "fastest"))
            if data is not None:
                driver_data[driver] = data
        
        if len(driver_data) < 2:
            return {"error": "Need at least 2 drivers with valid data"}
        
        # Find driver with most points as reference
        reference_driver = max(driver_data.keys(), key=lambda d: len(driver_data[d]))
        reference_data = driver_data[reference_driver]
        
        print(f"Using {reference_driver} as reference ({len(reference_data)} points)")
        
        # Compare each driver with reference
        results = {
            'reference_driver': reference_driver,
            'reference_data': reference_data,
            'comparisons': {}
        }
        
        for driver in drivers:
            if driver == reference_driver:
                continue
                
            if driver not in driver_data:
                results['comparisons'][driver] = {"error": "No valid data"}
                continue
            
            print(f"Comparing {driver} vs {reference_driver}...")
            comparison_result = self.calculate_speed_differences(reference_data, driver_data[driver])
            results['comparisons'][driver] = comparison_result
            
            # Print summary
            stats = comparison_result['match_statistics']
            print(f"  Match rate: {stats['match_rate']:.2%}")
            print(f"  Mean speed diff: {stats['mean_speed_diff']:.2f} km/h")
            print(f"  Std speed diff: {stats['std_speed_diff']:.2f} km/h")
            print(f"  Processing time: {stats['processing_time']:.3f}s")
        
        return results


def test_speed_difference_calculator():
    """Test the speed difference calculator with sample data."""
    try:
        # Load session
        session = fastf1.get_session(2023, 'Spanish Grand Prix', 'Q')
        session.load(telemetry=True, weather=False, messages=False)
        
        # Initialize calculator with optimized parameters
        calculator = SpeedDifferenceCalculator(k_neighbors=5, max_distance_threshold=30.0, sample_frequency='0.1S')
        
        # Test with sample drivers
        drivers = ['VER', 'LEC', 'HAM']
        lap_selectors = {'VER': 'fastest', 'LEC': 'fastest', 'HAM': 'fastest'}
        
        print("Testing Speed Difference Calculator...")
        results = calculator.compare_multiple_drivers(session, drivers, lap_selectors)
        
        return results
        
    except Exception as e:
        print(f"Error in test: {e}")
        return None


if __name__ == "__main__":
    test_speed_difference_calculator()
