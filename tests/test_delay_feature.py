#!/usr/bin/env python3
"""
Test script for inter-channel delay functionality.
This demonstrates the new delay control feature.
"""

import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from niDAQ import NIDAQSettings, NIDAQReader

def test_delay_functionality():
    """Test the inter-channel delay feature."""
    
    print("Inter-Channel Delay Feature Test")
    print("=" * 40)
    
    # Test different delay settings
    test_cases = [
        {"delay_us": 0.0, "description": "Automatic/fastest conversion"},
        {"delay_us": 1.0, "description": "1 microsecond delay"},
        {"delay_us": 10.0, "description": "10 microsecond delay"},
        {"delay_us": 100.0, "description": "100 microsecond delay"},
        {"delay_us": 1000.0, "description": "1 millisecond delay"},
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {case['description']}")
        print(f"  Delay setting: {case['delay_us']} µs")
        
        try:
            # Create settings with delay
            settings = NIDAQSettings(
                device_name="Dev1",
                channels=["ai0", "ai1"],
                sampling_rate_hz=1000.0,
                inter_channel_delay_us=case['delay_us']
            )
            
            print(f"  ✓ Settings created successfully")
            print(f"    Channels: {settings.channels}")
            print(f"    Sampling rate: {settings.sampling_rate_hz} Hz")
            print(f"    Inter-channel delay: {settings.inter_channel_delay_us} µs")
            
            # Test conversion rate calculation
            if case['delay_us'] > 0:
                conv_rate_hz = 1.0 / (case['delay_us'] * 1e-6)
                print(f"    Calculated conversion rate: {conv_rate_hz:.0f} Hz")
            else:
                print(f"    Using automatic conversion rate")
            
            # Try to create reader (will fail without hardware, but tests settings)
            try:
                reader = NIDAQReader(settings)
                print(f"  ✓ Reader created successfully")
                
                # Test if we can get max conversion rate info
                try:
                    reader.start()
                    max_rate = reader.get_max_conversion_rate()
                    if max_rate is not None:
                        print(f"    Maximum conversion rate: {max_rate:.0f} Hz")
                        max_delay_us = 1.0 / max_rate * 1e6
                        print(f"    Minimum delay possible: {max_delay_us:.2f} µs")
                        
                        if case['delay_us'] > 0:
                            required_rate = 1.0 / (case['delay_us'] * 1e-6)
                            if required_rate > max_rate:
                                print(f"    ⚠ Warning: Requested delay too small!")
                            else:
                                print(f"    ✓ Delay setting is valid")
                    reader.close()
                except Exception as e:
                    print(f"    ⚠ Cannot test with hardware: {e}")
                    reader.close()
                    
            except Exception as e:
                print(f"  ⚠ Reader creation failed: {e}")
                
        except Exception as e:
            print(f"  ✗ Settings creation failed: {e}")
    
    print(f"\nGUI Integration:")
    print(f"  - New 'Inter-channel delay' control added to left panel")
    print(f"  - Range: 0.0 to 10,000.0 microseconds")
    print(f"  - 0.0 = automatic/fastest conversion rate")
    print(f"  - Higher values slow down channel switching")
    print(f"  - Settings are saved and restored automatically")
    print(f"  - Validation warns if delay is too small for hardware")
    
    print(f"\nUse Cases:")
    print(f"  - Reduce crosstalk between channels")
    print(f"  - Allow settling time for multiplexed inputs")
    print(f"  - Match timing requirements of external circuitry")
    print(f"  - Optimize for specific signal conditioning")

if __name__ == "__main__":
    test_delay_functionality()
