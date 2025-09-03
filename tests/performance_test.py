#!/usr/bin/env python3
"""
Performance testing script for high sampling rates.
Tests the DAQ application at various sampling rates to identify bottlenecks.
"""

import time
import sys
import os
import numpy as np
from contextlib import contextmanager

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from niDAQ import NIDAQReader, NIDAQSettings

@contextmanager
def timer(description):
    """Context manager to time operations."""
    start = time.perf_counter()
    print(f"{description}... ", end="", flush=True)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"{elapsed:.3f}s")

def test_data_processing_performance():
    """Test data processing performance at various data sizes."""
    print("Data Processing Performance Test")
    print("=" * 50)
    
    # Test different data sizes (simulating different sampling rates)
    test_cases = [
        (100, "Low rate (100 Hz)"),
        (1000, "Medium rate (1 kHz)"),
        (10000, "High rate (10 kHz)"),
        (50000, "Very high rate (50 kHz)"),
        (100000, "Extreme rate (100 kHz)")
    ]
    
    n_channels = 4
    duration_seconds = 1.0
    
    for samples_per_sec, description in test_cases:
        total_samples = int(samples_per_sec * duration_seconds)
        
        print(f"\n{description} - {total_samples} samples/channel:")
        
        # Generate test data
        with timer("  Data generation"):
            t = np.linspace(0, duration_seconds * 1000, total_samples)  # ms
            y = np.random.randn(total_samples, n_channels) * 0.1
            
        # Test FFT computation
        with timer("  FFT computation"):
            fft_size = min(8192, total_samples)
            for ch in range(n_channels):
                data = y[-fft_size:, ch]
                window = np.hanning(fft_size)
                windowed = data * window
                fft_result = np.fft.rfft(windowed)
                psd = np.abs(fft_result) ** 2
        
        # Test array operations
        with timer("  Statistics calculation"):
            means = np.mean(y, axis=0)
            stds = np.std(y, axis=0)
            mins = np.min(y, axis=0)
            maxs = np.max(y, axis=0)
        
        # Test filtering (if scipy available)
        try:
            from scipy import signal
            with timer("  Digital filtering"):
                fs = samples_per_sec
                nyquist = fs / 2
                low_cutoff = min(100, nyquist * 0.8)
                b, a = signal.butter(4, low_cutoff / nyquist, btype='low')
                for ch in range(n_channels):
                    filtered = signal.filtfilt(b, a, y[:, ch])
        except ImportError:
            print("  Digital filtering... SKIPPED (scipy not available)")
        
        # Memory usage estimate
        memory_mb = (t.nbytes + y.nbytes) / (1024 * 1024)
        print(f"  Memory usage: {memory_mb:.1f} MB")

def test_daq_reader_performance():
    """Test actual DAQ reader performance (if hardware available)."""
    print("\nNIDAQReader Performance Test")
    print("=" * 50)
    
    # Try to create a DAQ reader
    try:
        devices = NIDAQReader.list_devices()
        if not devices:
            print("No NI devices found. Skipping hardware test.")
            return
        
        print(f"Found devices: {devices}")
        
        # Test different sampling rates
        test_rates = [100, 500, 1000, 5000, 10000]
        
        for rate_hz in test_rates:
            print(f"\nTesting {rate_hz} Hz sampling rate:")
            
            settings = NIDAQSettings(
                device_name=devices[0],
                channels=["ai0", "ai1"],
                sampling_rate_hz=rate_hz,
                v_min=-1.0,
                v_max=1.0
            )
            
            try:
                with timer(f"  Initialize DAQ"):
                    reader = NIDAQReader(settings)
                    reader.start()
                
                # Read data for short duration
                with timer(f"  Read 1 second of data"):
                    samples_per_read = max(10, rate_hz // 10)  # 100ms chunks
                    total_samples = 0
                    start_time = time.perf_counter()
                    
                    while total_samples < rate_hz:  # 1 second worth
                        t, y = reader.read_data(
                            number_of_samples_per_channel=samples_per_read,
                            accumulate=False
                        )
                        total_samples += len(t)
                        
                        if time.perf_counter() - start_time > 2.0:  # Safety timeout
                            break
                
                print(f"  Actual samples collected: {total_samples}")
                
                reader.close()
                
            except Exception as e:
                print(f"  ERROR: {e}")
                
    except Exception as e:
        print(f"Hardware test failed: {e}")

def analyze_bottlenecks():
    """Analyze common performance bottlenecks."""
    print("\nBottleneck Analysis")
    print("=" * 50)
    
    # Test different operations
    n_samples = 10000
    n_channels = 4
    
    print(f"Testing with {n_samples} samples, {n_channels} channels:")
    
    # Generate test data
    t = np.linspace(0, 1000, n_samples)
    y = np.random.randn(n_samples, n_channels)
    
    # Memory allocation test
    with timer("Memory allocation (large arrays)"):
        for i in range(100):
            temp = np.zeros((n_samples, n_channels))
            del temp
    
    # Array copying test
    with timer("Array copying"):
        for i in range(100):
            temp = y.copy()
            del temp
    
    # NumPy operations test
    with timer("NumPy operations"):
        for i in range(1000):
            result = np.mean(y, axis=0)
            result = np.std(y, axis=0)
    
    # FFT test
    with timer("FFT operations"):
        for i in range(100):
            for ch in range(n_channels):
                fft_result = np.fft.rfft(y[:, ch])
    
    print("\nRecommendations:")
    print("- Use pre-allocated arrays when possible")
    print("- Limit FFT size to reasonable values (<=8192)")
    print("- Process data in chunks rather than all at once")
    print("- Use circular buffers for continuous data")
    print("- Separate data acquisition from GUI updates")

def main():
    """Run all performance tests."""
    print("DAQ Application Performance Analysis")
    print("=" * 60)
    print("This script analyzes performance bottlenecks and provides")
    print("recommendations for handling high sampling rates.")
    print("=" * 60)
    
    # Run tests
    test_data_processing_performance()
    test_daq_reader_performance()
    analyze_bottlenecks()
    
    print("\n" + "=" * 60)
    print("SUMMARY RECOMMENDATIONS:")
    print("=" * 60)
    print("1. For sampling rates up to 10 kHz:")
    print("   - Use the optimized Python version")
    print("   - Implement rate-limited GUI updates (30-60 Hz)")
    print("   - Use circular buffers and data downsampling")
    
    print("\n2. For sampling rates 10-50 kHz:")
    print("   - Consider C++ extensions for data processing")
    print("   - Keep GUI in Python, move DSP to compiled code")
    print("   - Use producer-consumer pattern with queues")
    
    print("\n3. For sampling rates >50 kHz:")
    print("   - Consider full C++/Rust implementation")
    print("   - Use real-time operating system considerations")
    print("   - Implement hardware buffering strategies")
    
    print("\n4. Language Performance Comparison:")
    print("   - Python: Good for prototyping, adequate for <10 kHz")
    print("   - C++: 5-10x faster, better for >10 kHz")
    print("   - Rust: Similar to C++, better memory safety")
    print("   - Hybrid: 80% performance gain with 20% effort")

if __name__ == "__main__":
    main()
