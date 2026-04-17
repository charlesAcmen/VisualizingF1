from speed_diff_kdtree import SpeedDifferenceCalculator
import fastf1

def test_different_parameters():
    """Test different KD-tree parameters to find optimal settings."""
    
    # Load session
    session = fastf1.get_session(2023, 'Spanish Grand Prix', 'Q')
    session.load(telemetry=True, weather=False, messages=False)
    
    # Test different parameter combinations
    test_params = [
        (1, 100.0),   # k=1, 100m threshold
        (3, 50.0),    # k=3, 50m threshold  
        (3, 100.0),   # k=3, 100m threshold
        (5, 50.0),    # k=5, 50m threshold
        (5, 100.0),   # k=5, 100m threshold
    ]
    
    drivers = ['VER', 'LEC']
    
    print("Testing different KD-tree parameters...")
    print("k_neighbors, max_distance_threshold, match_rate, mean_speed_diff")
    
    for k, threshold in test_params:
        calculator = SpeedDifferenceCalculator(k_neighbors=k, max_distance_threshold=threshold)
        
        try:
            results = calculator.compare_multiple_drivers(session, drivers)
            
            if 'comparisons' in results and 'VER' in results['comparisons']:
                stats = results['comparisons']['VER']['match_statistics']
                print(f"{k}, {threshold}, {stats['match_rate']:.2%}, {stats['mean_speed_diff']:.2f}")
            else:
                print(f"{k}, {threshold}, ERROR, ERROR")
                
        except Exception as e:
            print(f"{k}, {threshold}, ERROR, ERROR - {e}")

if __name__ == "__main__":
    test_different_parameters()
