#!/usr/bin/env python3
"""
Diagnostic script to test 50kHz DAQ performance limitations.
"""

import time
import numpy as np
import threading
from collections import deque

def test_data_processing_overhead():
    """Test the computational overhead of processing 50kHz data."""
    print("Testing 50kHz Data Processing Overhead")
    print("=" * 45)
    
    # Simulate 50kHz data for 1 second
    sampling_rate = 50000
    channels = 2
    duration = 1.0  # 1 second test
    
    total_samples = int(sampling_rate * duration)
    data = np.random.randn(total_samples, channels).astype(np.float64)
    
    print(f"Test data: {total_samples:,} samples x {channels} channels")
    print(f"Data size: {data.nbytes / (1024*1024):.1f} MB")
    
    # Test 1: Raw data copying
    start_time = time.perf_counter()
    data_copy = data.copy()
    copy_time = time.perf_counter() - start_time
    print(f"Data copy time: {copy_time*1000:.1f} ms")
    
    # Test 2: GUI-style data downsampling
    start_time = time.perf_counter()
    downsample_factor = max(1, len(data) // 2000)  # Downsample to 2000 points
    downsampled = data[::downsample_factor]
    downsample_time = time.perf_counter() - start_time
    print(f"Downsample time: {downsample_time*1000:.1f} ms")
    
    # Test 3: Statistics calculation
    start_time = time.perf_counter()
    stats = {
        'mean': np.mean(data, axis=0),
        'std': np.std(data, axis=0),
        'min': np.min(data, axis=0),
        'max': np.max(data, axis=0)
    }
    stats_time = time.perf_counter() - start_time
    print(f"Statistics time: {stats_time*1000:.1f} ms")
    
    # Test 4: FFT computation (spectrum analysis)
    start_time = time.perf_counter()
    fft_size = min(8192, len(data))
    fft_data = data[:fft_size, 0]  # First channel only
    fft_result = np.fft.rfft(fft_data)
    fft_spectrum = np.abs(fft_result)
    fft_time = time.perf_counter() - start_time
    print(f"FFT time ({fft_size} points): {fft_time*1000:.1f} ms")
    
    total_processing_time = copy_time + downsample_time + stats_time + fft_time
    print(f"\nTotal processing time: {total_processing_time*1000:.1f} ms")
    print(f"Processing overhead: {total_processing_time*100:.1f}% of 1 second")
    
    # Test 5: Simulate GUI update rate
    gui_update_interval = 33  # 33ms = 30 Hz
    data_per_update = int(sampling_rate * gui_update_interval / 1000)
    
    print(f"\nGUI Update Analysis:")
    print(f"Update interval: {gui_update_interval} ms (30 Hz)")
    print(f"Data per update: {data_per_update:,} samples")
    print(f"Processing budget: {gui_update_interval} ms")
    
    if total_processing_time * 1000 > gui_update_interval:
        print("⚠️  WARNING: Processing time exceeds GUI update interval!")
        print("   This will cause GUI lag and potential buffer overruns.")
    else:
        print("✅ Processing time within acceptable limits.")

def recommend_optimizations():
    """Recommend optimizations for 50kHz operation."""
    print("\n" + "=" * 45)
    print("RECOMMENDATIONS FOR 50kHz OPERATION")
    print("=" * 45)
    
    print("\n1. GUI UPDATE RATE REDUCTION:")
    print("   - Reduce from 30 Hz to 10-15 Hz (67-100ms intervals)")
    print("   - Less frequent updates = more time for processing")
    
    print("\n2. PLOT DOWNSAMPLING:")
    print("   - Limit plot points to 1000-1500 for smooth rendering")
    print("   - Use every Nth sample for display (decimation)")
    
    print("\n3. BACKGROUND PROCESSING:")
    print("   - Move FFT/statistics to background thread")
    print("   - Use circular buffers for data storage")
    
    print("\n4. MEMORY OPTIMIZATION:")
    print("   - Pre-allocate buffers to avoid garbage collection")
    print("   - Use dtype=float32 instead of float64 if precision allows")
    
    print("\n5. DAQ CONFIGURATION:")
    print("   - Increase DAQ buffer size")
    print("   - Read larger chunks less frequently")
    print("   - Consider using DAQ callbacks instead of polling")
    
    print("\n6. ALTERNATIVE APPROACHES:")
    print("   - Consider using compiled extensions (Cython/numba)")
    print("   - Use dedicated DAQ software for 50kHz+ rates")
    print("   - Implement data logging without real-time GUI")

if __name__ == "__main__":
    test_data_processing_overhead()
    recommend_optimizations()
