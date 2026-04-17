import requests
import json

def test_api_frequencies():
    """Test different sampling frequencies via API"""
    
    base_url = "http://localhost:8000/api/speed-diff"
    base_params = "season=2023&event=Spanish%20Grand%20Prix&session=Q&drivers=VER,LEC"
    
    frequencies = [
        ("original", "Original frequency"),
        ("0.1S", "10Hz"),
        ("0.05S", "20Hz")
    ]
    
    print("Testing API with different sampling frequencies")
    print("=" * 50)
    
    for freq, desc in frequencies:
        print(f"\n{desc} ({freq}):")
        print("-" * 30)
        
        url = f"{base_url}?{base_params}&sample_frequency={freq}"
        
        try:
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                meta = data['meta']
                
                # Get first comparison
                comparison_key = None
                for key in data['comparisons'].keys():
                    comparison_key = key
                    break
                
                if comparison_key:
                    comp = data['comparisons'][comparison_key]
                    
                    print(f"  Frequency: {meta['sample_frequency']}")
                    print(f"  K-neighbors: {meta['k_neighbors']}")
                    print(f"  Distance threshold: {meta['max_distance_threshold']}m")
                    print(f"  Reference points: {len(data['reference_data']['distance'])}")
                    print(f"  Match rate: {comp['match_statistics']['match_rate']:.2%}")
                    
                    if comp['match_statistics']['mean_speed_diff']:
                        print(f"  Mean speed diff: {comp['match_statistics']['mean_speed_diff']:.2f} km/h")
                        print(f"  Std speed diff: {comp['match_statistics']['std_speed_diff']:.2f} km/h")
                    
                    print(f"  Valid matches: {comp['match_statistics']['valid_matches']}/{comp['match_statistics']['total_points']}")
                else:
                    print("  No comparison data found")
                    
            else:
                print(f"  Error: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"  Message: {error_data.get('error', 'Unknown error')}")
                except:
                    print(f"  Response: {response.text[:200]}")
                    
        except requests.exceptions.ConnectionError:
            print("  Connection error - make sure API server is running on localhost:8000")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    test_api_frequencies()
