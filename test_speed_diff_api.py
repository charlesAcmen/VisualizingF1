import requests
import json

def test_speed_diff_api():
    """Test the speed difference API endpoint."""
    
    base_url = "http://localhost:8000"
    
    # Test cases
    test_cases = [
        {
            "name": "Basic two drivers fastest laps",
            "params": {
                "season": "2023",
                "event": "Spanish Grand Prix", 
                "session": "Q",
                "drivers": "VER,LEC",
                "lap_selectors": "fastest"
            }
        },
        {
            "name": "Three drivers with mixed laps",
            "params": {
                "season": "2023",
                "event": "Spanish Grand Prix",
                "session": "Q", 
                "drivers": "VER,LEC,HAM",
                "lap_selectors": "VER:fastest,LEC:12,HAM:fastest"
            }
        },
        {
            "name": "With specific reference driver",
            "params": {
                "season": "2023",
                "event": "Spanish Grand Prix",
                "session": "Q",
                "drivers": "VER,LEC,HAM", 
                "lap_selectors": "fastest",
                "reference_driver": "LEC"
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\nTesting: {test_case['name']}")
        print(f"URL: {base_url}/api/speed-diff")
        print(f"Params: {test_case['params']}")
        
        try:
            response = requests.get(f"{base_url}/api/speed-diff", params=test_case['params'], timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                meta = data.get('meta', {})
                comparisons = data.get('comparisons', {})
                
                print(f"✅ Success!")
                print(f"  Reference driver: {meta.get('reference_driver')}")
                print(f"  Drivers: {meta.get('drivers')}")
                print(f"  Comparisons: {len(comparisons)}")
                
                for driver, comp in comparisons.items():
                    stats = comp.get('match_statistics', {})
                    print(f"    {driver}: {stats.get('match_rate', 0):.1%} match rate, "
                          f"mean diff: {stats.get('mean_speed_diff', 0):.2f} km/h")
                
            else:
                print(f"❌ Failed: {response.status_code}")
                print(f"  Error: {response.text}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_speed_diff_api()
