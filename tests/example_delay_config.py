#!/usr/bin/env python3
"""
Example demonstrating inter-channel delay configuration.
Shows how to set conversion delays for different applications.
"""

import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from niDAQ import NIDAQSettings, NIDAQReader

def demonstrate_delay_settings():
    """Show different delay configurations for various applications."""
    
    print("Inter-Channel Delay Configuration Examples")
    print("=" * 50)
    
    # Example configurations for different use cases
    examples = [
        {
            "name": "High-Speed Digital Signals",
            "delay_us": 0.0,
            "description": "Automatic timing for maximum throughput",
            "use_case": "Fast digital measurements, high-frequency signals"
        },
        {
            "name": "Mixed Analog Signals", 
            "delay_us": 10.0,
            "description": "Small delay to reduce channel crosstalk",
            "use_case": "Multiple analog sensors with different signal levels"
        },
        {
            "name": "Temperature Sensors",
            "delay_us": 100.0,
            "description": "Allow complete settling for precision measurements", 
            "use_case": "Thermocouples, RTDs, precision voltage references"
        },
        {
            "name": "External Multiplexer",
            "delay_us": 500.0,
            "description": "Match external circuit switching time",
            "use_case": "Custom signal conditioning with external multiplexing"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['name']}")
        print(f"   Delay: {example['delay_us']} µs")
        print(f"   Purpose: {example['description']}")
        print(f"   Use Case: {example['use_case']}")
        
        # Show the settings configuration
        settings = NIDAQSettings(
            device_name="Dev1",
            channels=["ai0", "ai1", "ai2"],
            sampling_rate_hz=1000.0,
            inter_channel_delay_us=example['delay_us']
        )
        
        if example['delay_us'] > 0:
            conv_rate = 1.0 / (example['delay_us'] * 1e-6)
            print(f"   Conversion Rate: {conv_rate:.0f} Hz")
        else:
            print(f"   Conversion Rate: Hardware maximum (~250 kHz)")
    
    print(f"\nGUI Usage:")
    print(f"1. Open the DAQ application")
    print(f"2. Find 'Inter-channel delay' control in left panel")
    print(f"3. Set delay value in microseconds (0.0 to 10,000.0)")
    print(f"4. 0.0 = automatic/fastest rate")
    print(f"5. Higher values = more settling time")
    print(f"6. Application warns if delay is too small for hardware")
    
    print(f"\nHardware Info:")
    print(f"- NI USB-6211 max conversion rate: ~250 kHz")
    print(f"- Minimum achievable delay: ~4.0 µs")
    print(f"- Setting controls ai_conv_rate property")
    print(f"- Automatic validation against hardware limits")

if __name__ == "__main__":
    demonstrate_delay_settings()
