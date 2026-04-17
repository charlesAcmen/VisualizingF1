import fastf1
import pandas as pd
import numpy as np

def analyze_sampling():
    """Analyze FastF1 data sampling characteristics"""
    try:
        # Load a sample session
        session = fastf1.get_session(2023, 'Spanish Grand Prix', 'Q')
        session.load(telemetry=True, weather=False, messages=False)
        
        # Get multiple drivers' data for comparison
        drivers = ['VER', 'LEC', 'HAM']
        driver_data = {}
        
        for driver in drivers:
            driver_laps = session.laps.pick_drivers(driver)
            if not driver_laps.empty:
                fastest_lap = driver_laps.pick_fastest()
                car_data = fastest_lap.get_car_data().add_distance()
                
                # Get position data for X,Y coordinates
                pos_data = fastest_lap.get_pos_data()
                
                # Interpolate position data to match car data timestamps
                if not pos_data.empty and not car_data.empty:
                    # Reset index to ensure proper merging
                    car_data_reset = car_data.reset_index(drop=True)
                    pos_data_reset = pos_data.reset_index(drop=True)
                    
                    # Use pandas merge_asof for time-based merging
                    merged_data = pd.merge_asof(car_data_reset, pos_data_reset, on='Time', direction='nearest')
                    driver_data[driver] = merged_data
                else:
                    driver_data[driver] = car_data  # Fallback to car data only
                
                print(f"\n{driver}:")
                current_data = driver_data[driver]
                print(f"  Total points: {len(current_data)}")
                print(f"  Distance range: {current_data['Distance'].min():.1f} - {current_data['Distance'].max():.1f} m")
                
                # Check sampling intervals
                distances = current_data['Distance'].values
                if len(distances) > 1:
                    intervals = distances[1:] - distances[:-1]
                    print(f"  Distance intervals - Min: {intervals.min():.3f} m, Max: {intervals.max():.3f} m, Mean: {intervals.mean():.3f} m")
                
                # Check available columns
                print(f"  Available columns: {list(current_data.columns)}")
        
        # Analyze point count differences
        point_counts = [len(data) for data in driver_data.values()]
        print(f"\nPoint count analysis:")
        print(f"  Counts: {dict(zip(drivers, point_counts))}")
        print(f"  Max: {max(point_counts)}, Min: {min(point_counts)}, Ratio: {max(point_counts)/min(point_counts):.2f}")
        
        # Check for X,Y coordinates
        sample_data = list(driver_data.values())[0]
        has_xy = 'X' in sample_data.columns and 'Y' in sample_data.columns
        print(f"\nHas X,Y coordinates: {has_xy}")
        
        if has_xy:
            print(f"  X range: {sample_data['X'].min():.1f} - {sample_data['X'].max():.1f}")
            print(f"  Y range: {sample_data['Y'].min():.1f} - {sample_data['Y'].max():.1f}")
            
            # Calculate spatial distances between consecutive points
            x_coords = sample_data['X'].values
            y_coords = sample_data['Y'].values
            if len(x_coords) > 1:
                spatial_distances = np.sqrt((x_coords[1:] - x_coords[:-1])**2 + (y_coords[1:] - y_coords[:-1])**2)
                print(f"  Spatial distances - Min: {spatial_distances.min():.3f} m, Max: {spatial_distances.max():.3f} m, Mean: {spatial_distances.mean():.3f} m")
        
        return driver_data
        
    except Exception as e:
        print(f"Error analyzing sampling: {e}")
        return {}

if __name__ == "__main__":
    analyze_sampling()
