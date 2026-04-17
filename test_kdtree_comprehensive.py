"""
Comprehensive test suite for KD-tree implementation
Tests for correctness, performance, edge cases, and potential issues
"""
import numpy as np
import pandas as pd
import fastf1
import time
import matplotlib.pyplot as plt
from speed_diff_kdtree import SpeedDifferenceCalculator
from config import Config
from typing import Dict, List, Tuple, Any

class KDTreeTester:
    """Comprehensive test suite for KD-tree speed difference calculation"""
    
    def __init__(self):
        self.test_results = {}
        self.session = None
        
    def setup_session(self, season=2023, event='Spanish Grand Prix', session='Q'):
        """Setup test session"""
        print(f"Loading session: {season} {event} {session}")
        self.session = fastf1.get_session(season, event, session)
        self.session.load(telemetry=True, weather=False, messages=False)
        print("Session loaded successfully")
    
    def test_basic_functionality(self):
        """Test basic KD-tree functionality"""
        print("\n=== Testing Basic Functionality ===")
        
        calculator = SpeedDifferenceCalculator()
        drivers = ['VER', 'LEC']
        
        try:
            results = calculator.compare_multiple_drivers(self.session, drivers)
            
            # Basic checks
            assert 'reference_driver' in results
            assert 'comparisons' in results
            assert len(results['comparisons']) > 0
            
            # Check comparison structure
            for driver, comp in results['comparisons'].items():
                if 'error' not in comp:
                    assert 'speed_differences' in comp
                    assert 'match_statistics' in comp
                    stats = comp['match_statistics']
                    assert 'match_rate' in stats
                    assert 'processing_time' in stats
                    
                    print(f"  {driver}: {stats['match_rate']:.2%} match rate, "
                          f"{stats['processing_time']:.3f}s processing")
            
            self.test_results['basic_functionality'] = 'PASSED'
            print("  Basic functionality: PASSED")
            
        except Exception as e:
            self.test_results['basic_functionality'] = f'FAILED: {e}'
            print(f"  Basic functionality: FAILED - {e}")
    
    def test_sampling_frequency_consistency(self):
        """Test that different sampling frequencies produce consistent results"""
        print("\n=== Testing Sampling Frequency Consistency ===")
        
        frequencies = ['0.1S', '0.05S', '0.02S']  # 10Hz, 20Hz, 50Hz
        drivers = ['VER', 'LEC']
        results = {}
        
        for freq in frequencies:
            print(f"  Testing {freq}...")
            calculator = SpeedDifferenceCalculator(sample_frequency=freq)
            
            try:
                result = calculator.compare_multiple_drivers(self.session, drivers)
                if 'comparisons' in result and 'VER' in result['comparisons']:
                    comp = result['comparisons']['VER']
                    if 'error' not in comp:
                        stats = comp['match_statistics']
                        results[freq] = {
                            'match_rate': stats['match_rate'],
                            'mean_diff': stats['mean_speed_diff'],
                            'std_diff': stats['std_speed_diff'],
                            'points': stats['total_points']
                        }
                        print(f"    Match rate: {stats['match_rate']:.2%}, "
                              f"Points: {stats['total_points']}")
                    else:
                        results[freq] = {'error': comp['error']}
                else:
                    results[freq] = {'error': 'No valid comparison'}
                    
            except Exception as e:
                results[freq] = {'error': str(e)}
                print(f"    Error: {e}")
        
        # Analyze consistency
        valid_results = {k: v for k, v in results.items() if 'error' not in v}
        
        if len(valid_results) >= 2:
            match_rates = [v['match_rate'] for v in valid_results.values()]
            mean_diffs = [v['mean_diff'] for v in valid_results.values()]
            
            # Check if results are reasonably consistent (within 10% for match rates)
            match_rate_std = np.std(match_rates)
            mean_diff_std = np.std(mean_diffs)
            
            print(f"  Match rate std: {match_rate_std:.3f}")
            print(f"  Mean diff std: {mean_diff_std:.3f} km/h")
            
            if match_rate_std < 0.1 and mean_diff_std < 2.0:
                self.test_results['frequency_consistency'] = 'PASSED'
                print("  Frequency consistency: PASSED")
            else:
                self.test_results['frequency_consistency'] = 'FAILED: High variance'
                print("  Frequency consistency: FAILED - High variance across frequencies")
        else:
            self.test_results['frequency_consistency'] = 'FAILED: Insufficient valid results'
            print("  Frequency consistency: FAILED - Insufficient valid results")
    
    def test_edge_cases(self):
        """Test edge cases and potential error conditions"""
        print("\n=== Testing Edge Cases ===")
        
        # Test 1: Single driver (should fail gracefully)
        print("  Testing single driver...")
        calculator = SpeedDifferenceCalculator()
        try:
            result = calculator.compare_multiple_drivers(self.session, ['VER'])
            if 'error' in result:
                print("    Single driver: Correctly returned error")
            else:
                print("    Single driver: Should have failed but didn't")
                self.test_results['single_driver'] = 'FAILED: Should have failed'
        except Exception as e:
            print(f"    Single driver: Exception - {e}")
            self.test_results['single_driver'] = f'FAILED: {e}'
        
        # Test 2: Invalid driver
        print("  Testing invalid driver...")
        try:
            result = calculator.compare_multiple_drivers(self.session, ['VER', 'INVALID'])
            if 'comparisons' in result and 'INVALID' in result['comparisons']:
                comp = result['comparisons']['INVALID']
                if 'error' in comp:
                    print("    Invalid driver: Correctly handled")
                    self.test_results['invalid_driver'] = 'PASSED'
                else:
                    print("    Invalid driver: Should have error")
                    self.test_results['invalid_driver'] = 'FAILED: Should have error'
            else:
                print("    Invalid driver: Not found in results (expected)")
                self.test_results['invalid_driver'] = 'PASSED'
        except Exception as e:
            print(f"    Invalid driver: Exception - {e}")
            self.test_results['invalid_driver'] = f'FAILED: {e}'
        
        # Test 3: Very small distance threshold
        print("  Testing small distance threshold...")
        try:
            calculator = SpeedDifferenceCalculator(max_distance_threshold=1.0)  # 1 meter
            result = calculator.compare_multiple_drivers(self.session, ['VER', 'LEC'])
            if 'comparisons' in result:
                comp = result['comparisons'].get('VER', {})
                if 'match_statistics' in comp:
                    match_rate = comp['match_statistics']['match_rate']
                    print(f"    Small threshold: {match_rate:.2%} match rate")
                    if match_rate < 0.5:  # Should be very low
                        self.test_results['small_threshold'] = 'PASSED'
                    else:
                        self.test_results['small_threshold'] = 'FAILED: Match rate too high'
                else:
                    self.test_results['small_threshold'] = 'FAILED: No stats'
            else:
                self.test_results['small_threshold'] = 'FAILED: No comparisons'
        except Exception as e:
            print(f"    Small threshold: Exception - {e}")
            self.test_results['small_threshold'] = f'FAILED: {e}'
        
        # Test 4: k=1 (nearest neighbor only)
        print("  Testing k=1...")
        try:
            calculator = SpeedDifferenceCalculator(k_neighbors=1)
            result = calculator.compare_multiple_drivers(self.session, ['VER', 'LEC'])
            if 'comparisons' in result:
                comp = result['comparisons'].get('VER', {})
                if 'match_statistics' in comp:
                    print(f"    k=1: {comp['match_statistics']['match_rate']:.2%} match rate")
                    self.test_results['k_equals_1'] = 'PASSED'
                else:
                    self.test_results['k_equals_1'] = 'FAILED: No stats'
            else:
                self.test_results['k_equals_1'] = 'FAILED: No comparisons'
        except Exception as e:
            print(f"    k=1: Exception - {e}")
            self.test_results['k_equals_1'] = f'FAILED: {e}'
    
    def test_performance_scaling(self):
        """Test performance with different numbers of drivers"""
        print("\n=== Testing Performance Scaling ===")
        
        driver_sets = [
            (['VER', 'LEC'], '2 drivers'),
            (['VER', 'LEC', 'HAM'], '3 drivers'),
            (['VER', 'LEC', 'HAM', 'SAI'], '4 drivers')
        ]
        
        calculator = SpeedDifferenceCalculator()
        
        for drivers, description in driver_sets:
            print(f"  Testing {description}...")
            start_time = time.time()
            
            try:
                result = calculator.compare_multiple_drivers(self.session, drivers)
                total_time = time.time() - start_time
                
                if 'comparisons' in result:
                    num_comparisons = len(result['comparisons'])
                    print(f"    {description}: {total_time:.3f}s, {num_comparisons} comparisons")
                    
                    # Check if time scales reasonably (should be roughly linear)
                    if total_time < 10.0:  # Should complete within 10 seconds
                        self.test_results[f'performance_{len(drivers)}'] = 'PASSED'
                    else:
                        self.test_results[f'performance_{len(drivers)}'] = 'WARNING: Slow'
                else:
                    self.test_results[f'performance_{len(drivers)}'] = 'FAILED: No results'
                    
            except Exception as e:
                print(f"    {description}: Exception - {e}")
                self.test_results[f'performance_{len(drivers)}'] = f'FAILED: {e}'
    
    def test_data_quality(self):
        """Test data quality and potential issues"""
        print("\n=== Testing Data Quality ===")
        
        calculator = SpeedDifferenceCalculator()
        drivers = ['VER', 'LEC']
        
        try:
            # Get raw data for analysis
            driver_data = {}
            for driver in drivers:
                data = calculator.prepare_driver_data(self.session, driver)
                if data is not None:
                    driver_data[driver] = data
            
            if len(driver_data) >= 2:
                for driver, data in driver_data.items():
                    print(f"  {driver}:")
                    print(f"    Points: {len(data)}")
                    print(f"    Distance range: {data['Distance'].min():.1f} - {data['Distance'].max():.1f}m")
                    print(f"    Speed range: {data['Speed'].min():.1f} - {data['Speed'].max():.1f} km/h")
                    
                    # Check for data issues
                    nan_count = data.isnull().sum().sum()
                    if nan_count > 0:
                        print(f"    WARNING: {nan_count} NaN values")
                        self.test_results[f'data_quality_{driver}'] = 'WARNING: NaN values'
                    else:
                        self.test_results[f'data_quality_{driver}'] = 'PASSED'
                    
                    # Check for duplicate distances
                    dup_distances = data['Distance'].duplicated().sum()
                    if dup_distances > 0:
                        print(f"    WARNING: {dup_distances} duplicate distances")
                    
                    # Check spatial distribution
                    x_range = data['X'].max() - data['X'].min()
                    y_range = data['Y'].max() - data['Y'].min()
                    print(f"    Spatial range: {x_range:.1f} x {y_range:.1f}m")
                
                self.test_results['data_quality'] = 'PASSED'
            else:
                self.test_results['data_quality'] = 'FAILED: Insufficient data'
                
        except Exception as e:
            print(f"  Data quality test failed: {e}")
            self.test_results['data_quality'] = f'FAILED: {e}'
    
    def test_natural_matching_accuracy(self):
        """Test natural matching algorithm accuracy by comparing with actual data"""
        print("\n=== Testing Natural Matching Accuracy ===")
        
        try:
            calculator = SpeedDifferenceCalculator()
            drivers = ['VER', 'LEC']
            
            # Get speed differences using new algorithm
            result = calculator.compare_multiple_drivers(self.session, drivers)
            
            if 'comparisons' in result and 'VER' in result['comparisons']:
                comp = result['comparisons']['VER']
                
                if 'error' not in comp:
                    stats = comp['match_statistics']
                    print(f"  Match rate: {stats['match_rate']:.2%}")
                    print(f"  Mean speed diff: {stats['mean_speed_diff']:.2f} km/h")
                    print(f"  Std speed diff: {stats['std_speed_diff']:.2f} km/h")
                    print(f"  Max speed diff: {stats['max_speed_diff']:.2f} km/h")
                    print(f"  Total points: {stats['total_points']}")
                    print(f"  Valid matches: {stats['valid_matches']}")
                    
                    # Check if results are reasonable
                    # Match rate should be high (>80% with 30m threshold)
                    if stats['match_rate'] > 0.8:
                        self.test_results['natural_matching_accuracy'] = 'PASSED'
                        print("  Natural matching accuracy: PASSED")
                    else:
                        self.test_results['natural_matching_accuracy'] = 'WARNING: Low match rate'
                        print("  Natural matching accuracy: WARNING - Low match rate")
                else:
                    self.test_results['natural_matching_accuracy'] = f'FAILED: {comp["error"]}'
                    print(f"  Natural matching accuracy: FAILED - {comp['error']}")
            else:
                self.test_results['natural_matching_accuracy'] = 'FAILED: No comparison data'
                print("  Natural matching accuracy: FAILED - No comparison data")
                
        except Exception as e:
            print(f"  Natural matching test failed: {e}")
            self.test_results['natural_matching_accuracy'] = f'FAILED: {e}'
    
    def run_all_tests(self):
        """Run all tests and generate report"""
        print("Starting Comprehensive KD-Tree Testing")
        print("=" * 50)
        
        if not self.session:
            self.setup_session()
        
        # Run all test suites
        self.test_basic_functionality()
        self.test_sampling_frequency_consistency()
        self.test_edge_cases()
        self.test_performance_scaling()
        self.test_data_quality()
        self.test_natural_matching_accuracy()
        
        # Generate summary report
        self.generate_report()
    
    def generate_report(self):
        """Generate test report"""
        print("\n" + "=" * 50)
        print("TEST REPORT")
        print("=" * 50)
        
        passed = sum(1 for result in self.test_results.values() if result == 'PASSED')
        failed = sum(1 for result in self.test_results.values() if result.startswith('FAILED'))
        warnings = sum(1 for result in self.test_results.values() if result.startswith('WARNING'))
        total = len(self.test_results)
        
        print(f"Total tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Warnings: {warnings}")
        print(f"Success rate: {passed/total*100:.1f}%")
        
        print("\nDetailed Results:")
        for test_name, result in self.test_results.items():
            status = "PASS" if result == 'PASSED' else "FAIL" if result.startswith('FAILED') else "WARN"
            print(f"  {test_name}: {status}")
            if result != 'PASSED':
                print(f"    {result}")
        
        # Identify potential issues
        print("\nPotential Issues:")
        issues = []
        
        if self.test_results.get('frequency_consistency', '').startswith('FAILED'):
            issues.append("- Sampling frequency affects results significantly")
        
        if any('WARNING' in result for result in self.test_results.values()):
            issues.append("- Some tests show warnings that may indicate data quality issues")
        
        if self.test_results.get('natural_matching_accuracy', '').startswith('WARNING'):
            issues.append("- Natural matching may have low match rate")
        
        if not issues:
            print("  No major issues detected")
        else:
            for issue in issues:
                print(issue)

def main():
    """Main test runner"""
    tester = KDTreeTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()
