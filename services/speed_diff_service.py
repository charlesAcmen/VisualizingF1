"""
Speed difference service for comparing driver telemetry using spatial matching.
"""
from config import Config
from services.session_service import SessionService, get_display_session_name
from utils.helpers import resolve_event_name
from core.data_processor import prepare_driver_speed_data
from core.kdtree_matcher import calculate_speed_differences


class SpeedDiffService:
    """
    Service for calculating speed differences between drivers.
    """
    
    @staticmethod
    def build_payload(season, event_name, session_code, drivers, lap_selectors, 
                     reference_driver=None, sample_frequency=None, k_neighbors=None, 
                     max_distance_threshold=None):
        """
        Build payload for speed difference comparison.
        
        Args:
            season: Season year
            event_name: Grand Prix name
            session_code: Session code
            drivers: List of driver codes
            lap_selectors: Dictionary mapping driver codes to lap selectors
            reference_driver: Optional reference driver code
            sample_frequency: Sampling frequency (uses config default if None)
            k_neighbors: Number of neighbors for KD-tree (uses config default if None)
            max_distance_threshold: Max distance for valid matches (uses config default if None)
            
        Returns:
            Dictionary containing meta, comparisons, and reference_data
        """
        # Use config defaults if not specified
        if sample_frequency is None:
            sample_frequency = Config.GLOBAL_SAMPLING_FREQUENCY
        if k_neighbors is None:
            k_neighbors = Config.DEFAULT_K_NEIGHBORS
        if max_distance_threshold is None:
            max_distance_threshold = Config.DEFAULT_MAX_DISTANCE_THRESHOLD
        
        session = SessionService.load_session(season, event_name, session_code)
        
        # Prepare data for all drivers
        driver_data = {}
        for driver in drivers:
            lap_selector = lap_selectors.get(driver, "fastest")
            data = prepare_driver_speed_data(session, driver, lap_selector, sample_frequency)
            driver_data[driver] = data
        
        if len(driver_data) < 2:
            raise ValueError("Need at least 2 drivers with valid data")
        
        # Find driver with most points as reference (or use specified reference)
        if reference_driver and reference_driver in driver_data:
            ref_driver = reference_driver
        else:
            ref_driver = max(driver_data.keys(), key=lambda d: len(driver_data[d]))
        
        reference_data = driver_data[ref_driver]
        
        # Compare each driver with reference
        comparisons = {}
        
        for driver in drivers:
            if driver == ref_driver:
                continue
            
            if driver not in driver_data:
                continue
            
            comparison_result = calculate_speed_differences(
                reference_data, 
                driver_data[driver], 
                k_neighbors, 
                max_distance_threshold
            )
            comparisons[driver] = comparison_result
        
        # Get display session name
        display_session_name = get_display_session_name(season, event_name, session.name, session_code)
        
        return {
            'meta': {
                'season': season,
                'event': resolve_event_name(session.event),
                'session': display_session_name,
                'reference_driver': ref_driver,
                'drivers': drivers,
                'lap_selectors': lap_selectors,
                'sample_frequency': sample_frequency,
                'k_neighbors': k_neighbors,
                'max_distance_threshold': max_distance_threshold
            },
            'comparisons': comparisons,
            'reference_data': {
                'distance': [float(x) for x in reference_data['Distance'].values],
                'speed': [float(x) for x in reference_data['Speed'].values],
                'x': [float(x) for x in reference_data['X'].values],
                'y': [float(x) for x in reference_data['Y'].values],
                'z': [float(x) for x in reference_data['Z'].values],
            }
        }
