import requests
import json

def test_simple():
    """Simple test to check if API is using higher frequency"""
    
    # Test with explicit 10Hz parameter
    url = "http://localhost:8000/api/speed-diff?season=2023&event=Spanish%20Grand%20Prix&session=Q&drivers=VER,LEC&sample_frequency=0.1S"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if we have more data points than original (should be ~700+ vs ~270)
            ref_points = len(data['reference_data']['distance'])
            
            print(f"API Response Status: {response.status_code}")
            print(f"Reference data points: {ref_points}")
            
            # Check if frequency is in meta
            if 'sample_frequency' in data['meta']:
                print(f"Sample frequency: {data['meta']['sample_frequency']}")
            else:
                print("Sample frequency not found in meta")
            
            # Check other parameters
            print(f"K-neighbors: {data['meta'].get('k_neighbors', 'not found')}")
            print(f"Distance threshold: {data['meta'].get('max_distance_threshold', 'not found')}")
            
            # Expected points for different frequencies:
            if ref_points > 300:
                print("✓ Data points suggest 10Hz or higher sampling is working")
            elif ref_points > 200:
                print("⚠ Data points suggest original sampling")
            else:
                print("✗ Very low data count - possible error")
                
        else:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"Connection error: {e}")
        print("Make sure API server is running on localhost:8000")

if __name__ == "__main__":
    test_simple()
