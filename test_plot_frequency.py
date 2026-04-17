import requests
import json

def test_plot_api_frequency():
    """Test if plot API is using 10Hz sampling"""
    
    # Test the plot API endpoint
    url = "http://localhost:8000/api/lap?season=2023&event=Spanish%20Grand%20Prix&session=Q&driver=VER&lap=fastest"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check data point count
            distance_points = len(data.get('data', {}).get('distance_m', []))
            speed_points = len(data.get('data', {}).get('Speed', []))
            
            print(f"Plot API Test Results:")
            print(f"Status: {response.status_code}")
            print(f"Distance points: {distance_points}")
            print(f"Speed points: {speed_points}")
            
            # Expected points for different frequencies:
            if distance_points > 700:
                print("✓ Plot API is using 10Hz sampling (~700+ points)")
            elif distance_points > 200:
                print("⚠ Plot API may be using original sampling (~200-300 points)")
            else:
                print("✗ Very low data count - possible error")
            
            # Show some sample data
            if distance_points > 0:
                distances = data['data']['distance_m'][:5]
                speeds = data['data']['Speed'][:5]
                print(f"\nSample data (first 5 points):")
                for i, (dist, speed) in enumerate(zip(distances, speeds)):
                    print(f"  Point {i+1}: Distance={dist}m, Speed={speed}km/h")
            
            # Check lap info
            lap_time = data.get('lap_time', 'N/A')
            lap_number = data.get('lap_number', 'N/A')
            print(f"\nLap info: {lap_number}, Time: {lap_time}")
                
        else:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"Connection error: {e}")
        print("Make sure API server is running on localhost:8000")

if __name__ == "__main__":
    test_plot_api_frequency()
