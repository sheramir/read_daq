"""
Simple test script to validate the high-performance components work correctly.
"""

import sys
import time
import numpy as np
from PySide6 import QtWidgets, QtCore

# Test the components individually
def test_circular_buffer():
    """Test circular buffer functionality."""
    print("Testing CircularBuffer...")
    
    try:
        from circular_buffer_fixed import CircularBuffer
        
        # Create buffer
        buffer = CircularBuffer(1000, np.float64, "TestBuffer")
        
        # Add some test data
        test_data = np.random.randn(100)
        buffer.append_chunk(test_data)
        
        # Retrieve data
        recent = buffer.get_recent_data(50)
        
        # Get stats
        stats = buffer.get_statistics()
        
        print(f"  ✓ Buffer created and tested successfully")
        print(f"  ✓ Added {len(test_data)} samples, retrieved {len(recent)}")
        print(f"  ✓ Buffer utilization: {stats['utilization_percent']:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"  ✗ CircularBuffer test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_manager():
    """Test memory manager functionality."""
    print("Testing MemoryManager...")
    
    try:
        from memory_manager import MemoryManager
        
        # Create memory manager
        manager = MemoryManager(max_memory_mb=100, pool_size_mb=20)
        
        # Test basic allocation
        array1 = manager.allocate_array((100, 4), np.float64, use_mmap=False)
        array1.fill(1.0)
        
        array2 = manager.allocate_array((200, 2), np.float32, use_mmap=False)
        array2.fill(2.0)
        
        # Return arrays to pool
        manager.return_array(array1)
        manager.return_array(array2)
        
        # Get stats
        stats = manager.get_memory_stats()
        
        print(f"  ✓ Memory manager created and tested successfully")
        print(f"  ✓ Process memory: {stats['process_memory']['used_mb']:.1f} MB")
        print(f"  ✓ Pool arrays: {stats['memory_pool']['total_arrays_pooled']}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ MemoryManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_background_processor():
    """Test background processor functionality."""
    print("Testing BackgroundProcessor...")
    
    try:
        from background_processor import BackgroundProcessor
        
        # Create processor
        processor = BackgroundProcessor()
        processor.start_processing()
        
        # Wait a moment for startup
        time.sleep(0.5)
        
        # Test simple operation
        test_signal = np.random.randn(1000)
        
        # Use a simple callback approach
        results = []
        
        def on_result(result):
            results.append(result)
        
        processor.spectrum_ready.connect(on_result)
        
        # Request processing
        processor.request_spectrum(test_signal, 0, 1000.0)
        
        # Wait for result
        wait_time = 0
        while len(results) == 0 and wait_time < 3.0:
            time.sleep(0.1)
            wait_time += 0.1
        
        processor.stop_processing()
        
        print(f"  ✓ Background processor created and tested successfully")
        print(f"  ✓ Processed {len(results)} results")
        
        return len(results) > 0
        
    except Exception as e:
        print(f"  ✗ BackgroundProcessor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run simple tests."""
    print("=" * 50)
    print("Simple High-Performance Component Tests")
    print("=" * 50)
    
    # Create minimal Qt app for signal/slot functionality
    app = QtWidgets.QApplication(sys.argv)
    
    tests = [
        ("CircularBuffer", test_circular_buffer),
        ("MemoryManager", test_memory_manager),
        ("BackgroundProcessor", test_background_processor),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            success = test_func()
            if success:
                passed += 1
                print(f"  Result: ✓ PASS")
            else:
                print(f"  Result: ✗ FAIL")
        except Exception as e:
            print(f"  Result: ✗ FAIL - {e}")
    
    print(f"\n" + "=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 50)
    
    if passed == total:
        print("🎉 All basic tests passed!")
    else:
        print("❌ Some tests failed. Check individual components.")


if __name__ == "__main__":
    main()
