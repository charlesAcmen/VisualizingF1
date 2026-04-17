import fastf1
import pandas as pd

def test_direct_frequency():
    """Test frequency setting directly without API"""
    
    try:
        # Load session
        session = fastf1.get_session(2023, 'Spanish Grand Prix', 'Q')
        session.load(telemetry=True, weather=False, messages=False)
        
        # Get driver data
        laps = session.laps.pick_drivers('VER')
        fastest_lap = laps.pick_fastest()
        
        print("Testing frequency settings directly:")
        print("=" * 40)
        
        # Test original
        car_data_orig = fastest_lap.get_car_data()
        print(f"Original data points: {len(car_data_orig)}")
        
        # Test 10Hz
        car_data_10hz = fastest_lap.get_car_data().resample_channels('0.1S')
        print(f"10Hz (0.1S) data points: {len(car_data_10hz)}")
        
        # Test 20Hz
        car_data_20hz = fastest_lap.get_car_data().resample_channels('0.05S')
        print(f"20Hz (0.05S) data points: {len(car_data_20hz)}")
        
        # Check if resampling is working
        if len(car_data_10hz) > len(car_data_orig):
            print("✓ 10Hz resampling is working")
        else:
            print("✗ 10Hz resampling not working")
            
        if len(car_data_20hz) > len(car_data_10hz):
            print("✓ 20Hz resampling is working")
        else:
            print("✗ 20Hz resampling not working")
            
        # Show sample data
        print(f"\nOriginal sample distances: {car_data_orig['Distance'].head(3).tolist()}")
        print(f"10Hz sample distances: {car_data_10hz['Distance'].head(3).tolist()}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_direct_frequency()
