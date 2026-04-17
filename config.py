"""
Global configuration for F1 telemetry visualization
"""
from typing import Dict, Any

class Config:
    # Global sampling frequency - unified across all visualizations
    # Options: 'original', '0.2S' (5Hz), '0.1S' (10Hz), '0.05S' (20Hz), '0.02S' (50Hz)
    GLOBAL_SAMPLING_FREQUENCY = '0.05S'  # 20Hz for high precision
    
    # KD-tree default parameters
    DEFAULT_K_NEIGHBORS = 3
    DEFAULT_MAX_DISTANCE_THRESHOLD = 15.0  # meters
    
    # Data processing settings
    ENABLE_DISTANCE_BASED_PROCESSING = True
    MIN_POINTS_FOR_VALID_ANALYSIS = 50
    
    # Visualization settings
    PLOT_DPI = 100
    MAX_DRIVERS_IN_COMPARISON = 10
    
    @classmethod
    def get_frequency_settings(cls) -> Dict[str, Any]:
        """Get current frequency configuration"""
        freq_map = {
            'original': {'hz': None, 'description': 'Original frequency'},
            '0.2S': {'hz': 5, 'description': '5Hz'},
            '0.1S': {'hz': 10, 'description': '10Hz'},
            '0.05S': {'hz': 20, 'description': '20Hz'},
            '0.02S': {'hz': 50, 'description': '50Hz'}
        }
        return freq_map.get(cls.GLOBAL_SAMPLING_FREQUENCY, freq_map['0.05S'])
    
    @classmethod
    def validate_frequency(cls, frequency: str) -> str:
        """Validate and return a supported frequency"""
        valid_frequencies = ['original', '0.2S', '0.1S', '0.05S', '0.02S']
        if frequency not in valid_frequencies:
            print(f"Invalid frequency {frequency}, defaulting to {cls.GLOBAL_SAMPLING_FREQUENCY}")
            return cls.GLOBAL_SAMPLING_FREQUENCY
        return frequency
