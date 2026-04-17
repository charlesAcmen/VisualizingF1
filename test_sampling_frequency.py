import fastf1
import pandas as pd
import numpy as np
import time
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt

def test_sampling_frequencies():
    """测试不同采样频率对数据密度和质量的影响"""
    
    # 加载会话数据
    session = fastf1.get_session(2023, 'Spanish Grand Prix', 'Q')
    session.load(telemetry=True, weather=False, messages=False)
    
    # 测试不同的采样频率
    frequencies = ['original', '0.2S', '0.1S', '0.05S', '0.02S']  # 原始, 5Hz, 10Hz, 20Hz, 50Hz
    driver = 'VER'
    
    results = {}
    
    print("Testing different sampling frequencies...")
    print("=" * 60)
    
    for freq in frequencies:
        print(f"\nTesting frequency: {freq} Hz")
        print("-" * 30)
        
        try:
            # 获取最快圈速
            laps = session.laps.pick_drivers(driver)
            fastest_lap = laps.pick_fastest()
            
            start_time = time.time()
            
            # 获取不同频率的数据
            if freq == 'original':
                car_data = fastest_lap.get_car_data()
                pos_data = fastest_lap.get_pos_data()
                # 合并数据
                car_data_reset = car_data.reset_index(drop=True)
                pos_data_reset = pos_data.reset_index(drop=True)
                merged_data = pd.merge_asof(car_data_reset, pos_data_reset, on='Time', direction='nearest')
            else:
                # 对于高频数据，先获取原始数据然后重采样
                car_data = fastest_lap.get_car_data()
                pos_data = fastest_lap.get_pos_data()
                car_data = car_data.resample_channels(freq)
                pos_data = pos_data.resample_channels(freq)
                merged_data = car_data.merge_channels(pos_data)
            
            load_time = time.time() - start_time
            
            # 确保有Distance列
            if 'Distance' not in merged_data.columns:
                merged_data = merged_data.add_distance()
            
            # 分析数据
            merged_data = merged_data[['X', 'Y', 'Z', 'Speed', 'Distance']].dropna()
            
            # 计算统计信息
            num_points = len(merged_data)
            distance_range = merged_data['Distance'].max() - merged_data['Distance'].min()
            
            # 计算距离间隔
            distances = merged_data['Distance'].values
            if len(distances) > 1:
                intervals = np.diff(distances)
                mean_interval = np.mean(intervals)
                std_interval = np.std(intervals)
                min_interval = np.min(intervals)
                max_interval = np.max(intervals)
                
                # 计算空间距离间隔
                x_coords = merged_data['X'].values
                y_coords = merged_data['Y'].values
                if len(x_coords) > 1:
                    spatial_intervals = np.sqrt((x_coords[1:] - x_coords[:-1])**2 + 
                                               (y_coords[1:] - y_coords[:-1])**2)
                    mean_spatial_interval = np.mean(spatial_intervals)
                    std_spatial_interval = np.std(spatial_intervals)
                else:
                    mean_spatial_interval = 0
                    std_spatial_interval = 0
            else:
                mean_interval = std_interval = min_interval = max_interval = 0
                mean_spatial_interval = std_spatial_interval = 0
            
            # 计算速度变化
            speeds = merged_data['Speed'].values
            if len(speeds) > 1:
                speed_changes = np.diff(speeds)
                mean_speed_change = np.mean(np.abs(speed_changes))
                max_speed_change = np.max(np.abs(speed_changes))
            else:
                mean_speed_change = max_speed_change = 0
            
            results[freq] = {
                'num_points': num_points,
                'load_time': load_time,
                'mean_interval': mean_interval,
                'std_interval': std_interval,
                'min_interval': min_interval,
                'max_interval': max_interval,
                'mean_spatial_interval': mean_spatial_interval,
                'std_spatial_interval': std_spatial_interval,
                'mean_speed_change': mean_speed_change,
                'max_speed_change': max_speed_change,
                'points_per_meter': num_points / distance_range if distance_range > 0 else 0,
                'data': merged_data
            }
            
            print(f"  Points: {num_points}")
            print(f"  Load time: {load_time:.3f}s")
            print(f"  Mean distance interval: {mean_interval:.3f}m")
            print(f"  Mean spatial interval: {mean_spatial_interval:.3f}m")
            print(f"  Points per meter: {num_points / distance_range:.3f}")
            print(f"  Mean speed change: {mean_speed_change:.2f} km/h")
            
        except Exception as e:
            print(f"  Error: {e}")
            results[freq] = None
    
    return results, driver

def compare_interpolation_vs_sampling():
    """比较插值与高频采样的效果"""
    
    print("\n" + "=" * 60)
    print("Comparing Interpolation vs High-Frequency Sampling")
    print("=" * 60)
    
    # 加载数据
    session = fastf1.get_session(2023, 'Spanish Grand Prix', 'Q')
    session.load(telemetry=True, weather=False, messages=False)
    
    driver = 'VER'
    laps = session.laps.pick_drivers(driver)
    fastest_lap = laps.pick_fastest()
    
    # 原始数据
    original_car = fastest_lap.get_car_data()
    original_pos = fastest_lap.get_pos_data()
    original_car_reset = original_car.reset_index(drop=True)
    original_pos_reset = original_pos.reset_index(drop=True)
    original_merged = pd.merge_asof(original_car_reset, original_pos_reset, on='Time', direction='nearest')
    original_merged = original_merged.add_distance()
    original_data = original_merged[['X', 'Y', 'Z', 'Speed', 'Distance']].dropna()
    
    # 高频采样数据 (20Hz = 0.05S)
    hf_car = fastest_lap.get_car_data()
    hf_pos = fastest_lap.get_pos_data()
    hf_car = hf_car.resample_channels('0.05S')
    hf_pos = hf_pos.resample_channels('0.05S')
    hf_merged = hf_car.merge_channels(hf_pos)
    hf_merged = hf_merged.add_distance()
    hf_data = hf_merged[['X', 'Y', 'Z', 'Speed', 'Distance']].dropna()
    
    # 插值数据（从原始插值到高频点数）
    from scipy.interpolate import interp1d
    target_count = len(hf_data)
    
    interp_data = pd.DataFrame()
    interp_data['Distance'] = np.linspace(original_data['Distance'].min(), 
                                         original_data['Distance'].max(), 
                                         target_count)
    
    for col in ['X', 'Y', 'Z', 'Speed']:
        interp_func = interp1d(original_data['Distance'], original_data[col], 
                              kind='linear', bounds_error=False, fill_value='extrapolate')
        interp_data[col] = interp_func(interp_data['Distance'])
    
    # 比较分析
    print(f"\nOriginal data: {len(original_data)} points")
    print(f"High-frequency (20Hz): {len(hf_data)} points") 
    print(f"Interpolated: {len(interp_data)} points")
    
    # 计算与高频数据的差异
    if len(hf_data) == len(interp_data):
        speed_diff = np.abs(hf_data['Speed'].values - interp_data['Speed'].values)
        pos_diff = np.sqrt((hf_data['X'].values - interp_data['X'].values)**2 + 
                           (hf_data['Y'].values - interp_data['Y'].values)**2)
        
        print(f"\nInterpolation vs High-Frequency (20Hz):")
        print(f"  Mean speed difference: {np.mean(speed_diff):.2f} km/h")
        print(f"  Max speed difference: {np.max(speed_diff):.2f} km/h")
        print(f"  Mean position difference: {np.mean(pos_diff):.3f} m")
        print(f"  Max position difference: {np.max(pos_diff):.3f} m")
    
    return {
        'original': original_data,
        'high_frequency': hf_data,
        'interpolated': interp_data
    }

def analyze_computation_cost():
    """分析不同方法的计算成本"""
    
    print("\n" + "=" * 60)
    print("Computational Cost Analysis")
    print("=" * 60)
    
    session = fastf1.get_session(2023, 'Spanish Grand Prix', 'Q')
    session.load(telemetry=True, weather=False, messages=False)
    
    drivers = ['VER', 'LEC']
    frequencies = ['original', '0.1S', '0.05S']  # 原始, 10Hz, 20Hz
    
    for freq in frequencies:
        print(f"\nTesting {freq} Hz with {len(drivers)} drivers:")
        
        start_time = time.time()
        driver_data = {}
        
        for driver in drivers:
            laps = session.laps.pick_drivers(driver)
            fastest_lap = laps.pick_fastest()
            
            if freq == 'original':
                car_data = fastest_lap.get_car_data()
                pos_data = fastest_lap.get_pos_data()
                car_data_reset = car_data.reset_index(drop=True)
                pos_data_reset = pos_data.reset_index(drop=True)
                merged_data = pd.merge_asof(car_data_reset, pos_data_reset, on='Time', direction='nearest')
            else:
                car_data = fastest_lap.get_car_data()
                pos_data = fastest_lap.get_pos_data()
                car_data = car_data.resample_channels(freq)
                pos_data = pos_data.resample_channels(freq)
                merged_data = car_data.merge_channels(pos_data)
            
            merged_data = merged_data.add_distance()
            driver_data[driver] = merged_data[['X', 'Y', 'Z', 'Speed', 'Distance']].dropna()
        
        load_time = time.time() - start_time
        
        # 模拟k-d树计算
        from scipy.spatial import KDTree
        ref_driver = drivers[0]
        ref_data = driver_data[ref_driver]
        
        kdtree_start = time.time()
        kdtree = KDTree(ref_data[['X', 'Y', 'Z']].values)
        
        for driver in drivers[1:]:
            comp_data = driver_data[driver]
            distances, indices = kdtree.query(comp_data[['X', 'Y', 'Z']].values, k=3)
        
        kdtree_time = time.time() - kdtree_start
        total_time = time.time() - start_time
        
        print(f"  Data loading: {load_time:.3f}s")
        print(f"  KD-tree query: {kdtree_time:.3f}s")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Points per driver: {[len(data) for data in driver_data.values()]}")

def main():
    """主测试函数"""
    
    print("FastF1 Sampling Frequency Analysis")
    print("=" * 60)
    
    # 测试不同采样频率
    results, driver = test_sampling_frequencies()
    
    # 比较插值vs高频采样
    comparison_data = compare_interpolation_vs_sampling()
    
    # 分析计算成本
    analyze_computation_cost()
    
    # 总结建议
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    
    if results:
        print("\n1. Data Density vs Frequency:")
        for freq, data in results.items():
            if data:
                print(f"   {freq} Hz: {data['num_points']} points, {data['points_per_meter']:.3f} points/meter")
    
    print("\n2. Trade-offs:")
    print("   - Original: Most accurate but sparse (~16m intervals)")
    print("   - 10Hz: Good balance (~8m intervals, reasonable load time)")
    print("   - 20Hz: High density (~4m intervals, higher computational cost)")
    print("   - 50Hz: Very dense but may introduce interpolation artifacts")
    
    print("\n3. Recommended for KD-tree:")
    print("   - Use 10Hz or 20Hz for better spatial matching")
    print("   - Adjust distance threshold to 30-50m for higher density")
    print("   - Consider k=5 for smoother results with more data points")

if __name__ == "__main__":
    main()
