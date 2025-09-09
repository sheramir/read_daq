"""
Debug script to diagnose high-performance mode issues.
Run this to see what's happening when high-performance mode fails.
"""

import sys
import traceback
from PySide6 import QtWidgets, QtCore

def test_nidaqmx_availability():
    """Test if NI-DAQmx is available and can be imported."""
    print("1. Testing NI-DAQmx availability...")
    try:
        import nidaqmx
        print("   ✓ NI-DAQmx imported successfully")
        
        # Try to list devices
        try:
            system = nidaqmx.system.System.local()
            devices = system.devices
            print(f"   ✓ Found {len(devices)} DAQ devices:")
            for device in devices:
                print(f"     - {device.name}: {device.product_type}")
            return True, list(devices)
        except Exception as e:
            print(f"   ✗ Could not enumerate devices: {e}")
            return True, []
            
    except ImportError as e:
        print(f"   ✗ NI-DAQmx not available: {e}")
        return False, []
    except Exception as e:
        print(f"   ✗ NI-DAQmx error: {e}")
        return False, []

def test_high_performance_components():
    """Test if high-performance components can be imported."""
    print("\n2. Testing high-performance component imports...")
    
    components = [
        ("circular_buffer_fixed", "CircularBuffer"),
        ("background_processor", "BackgroundProcessor"),
        ("memory_manager", "MemoryManager"),
        ("high_performance_streamer", "HighPerformanceStreamer"),
        ("performance_monitor", "PerformanceMonitor")
    ]
    
    success_count = 0
    for module_name, class_name in components:
        try:
            module = __import__(module_name)
            cls = getattr(module, class_name)
            print(f"   ✓ {module_name}.{class_name}")
            success_count += 1
        except Exception as e:
            print(f"   ✗ {module_name}.{class_name}: {e}")
    
    return success_count == len(components)

def test_simple_daq_task():
    """Test creating a simple DAQ task."""
    print("\n3. Testing simple DAQ task creation...")
    
    try:
        import nidaqmx
        from nidaqmx.constants import TerminalConfiguration
        
        # Try to create a simple task
        task = nidaqmx.Task()
        
        # Try to add a channel (this will fail if no device is available)
        try:
            task.ai_channels.add_ai_voltage_chan(
                "Dev1/ai0",  # Common default device/channel
                terminal_config=TerminalConfiguration.RSE,
                min_val=-10.0,
                max_val=10.0
            )
            print("   ✓ Successfully added channel Dev1/ai0")
            
            # Try to configure timing
            task.timing.cfg_samp_clk_timing(
                rate=1000.0,
                samps_per_chan=1000
            )
            print("   ✓ Successfully configured timing")
            
            task.close()
            return True
            
        except Exception as e:
            print(f"   ✗ Could not configure task: {e}")
            print(f"      This usually means no DAQ device is available")
            task.close()
            return False
            
    except Exception as e:
        print(f"   ✗ Could not create task: {e}")
        return False

def test_fallback_simulation():
    """Test if we can simulate high-performance mode without hardware."""
    print("\n4. Testing simulation mode...")
    
    try:
        from circular_buffer_fixed import CircularBuffer, HighPerformanceDataProcessor
        import numpy as np
        
        # Test circular buffer
        buffer = CircularBuffer(10000, np.float64, "TestBuffer")
        test_data = np.random.randn(100)
        buffer.append_chunk(test_data)
        print("   ✓ Circular buffer works")
        
        # Test high-performance processor
        processor = HighPerformanceDataProcessor(10000, 4, 10000)
        test_chunk = np.random.randn(100, 4)
        processor.process_chunk(test_chunk, 0.0)
        print("   ✓ High-performance processor works")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Simulation failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run diagnostic tests."""
    print("=" * 60)
    print("High-Performance DAQ Diagnostic Tool")
    print("=" * 60)
    
    # Create minimal Qt app
    app = QtWidgets.QApplication(sys.argv)
    
    # Run tests
    nidaqmx_available, devices = test_nidaqmx_availability()
    components_ok = test_high_performance_components()
    hardware_ok = test_simple_daq_task() if nidaqmx_available else False
    simulation_ok = test_fallback_simulation()
    
    # Summary
    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    print(f"NI-DAQmx Available: {'✓' if nidaqmx_available else '✗'}")
    print(f"DAQ Hardware Available: {'✓' if hardware_ok else '✗'}")
    print(f"High-Performance Components: {'✓' if components_ok else '✗'}")
    print(f"Simulation Mode: {'✓' if simulation_ok else '✗'}")
    
    print("\nRECOMMENDATIONS:")
    
    if not nidaqmx_available:
        print("- Install NI-DAQmx drivers from National Instruments")
        print("- Ensure nidaqmx Python package is installed")
    
    if nidaqmx_available and not hardware_ok:
        print("- Connect a National Instruments DAQ device")
        print("- Verify device is recognized by NI MAX (Measurement & Automation Explorer)")
        print("- Check that channel names match your device (e.g., Dev1/ai0)")
    
    if not components_ok:
        print("- Check that all high-performance component files are present")
        print("- Verify Python environment has all required packages")
    
    if hardware_ok:
        print("✓ Hardware available - high-performance mode should work")
    elif simulation_ok:
        print("⚠ No hardware detected, but simulation mode available")
        print("  High-performance mode will fall back to standard mode")
    else:
        print("✗ Issues detected - high-performance mode may not work")
    
    print(f"\nDevices found: {len(devices)}")
    for device in devices:
        print(f"  - {device}")

if __name__ == "__main__":
    main()
