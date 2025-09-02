#!/usr/bin/env python3
"""
Example: Using per-channel gain settings with the NI USB-6211

This example demonstrates how to configure different voltage ranges 
(gains) for different channels to optimize resolution for various signal types.
"""

import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from niDAQ import NIDAQReader, NIDAQSettings

def main():
    print("Per-Channel Gain Configuration Example")
    print("=" * 50)
    
    # Show available common ranges
    common_ranges = NIDAQSettings.get_common_ranges()
    print("\nAvailable voltage ranges:")
    for name, (v_min, v_max) in common_ranges.items():
        print(f"  {name}: {v_min}V to {v_max}V")
    
    print("\nExample configuration:")
    print("  AI0: ±10V range for high-voltage signal")
    print("  AI1: ±1V range for medium-voltage signal")  
    print("  AI2: ±0.1V range for low-voltage signal")
    print("  AI3: 0-5V range for unipolar signal")
    
    # Create settings with per-channel ranges
    settings = NIDAQSettings(
        device_name="Dev1",
        channels=["ai0", "ai1", "ai2", "ai3"],
        sampling_rate_hz=1000,
        v_min=-10.0,     # Default range for unconfigured channels
        v_max=10.0,
        terminal_config="RSE"
    )
    
    # Configure individual channel ranges
    settings.set_channel_range("ai0", -10.0, 10.0)  # ±10V for high-voltage signal
    settings.set_channel_range("ai1", -1.0, 1.0)    # ±1V for medium-voltage signal
    settings.set_channel_range("ai2", -0.1, 0.1)    # ±0.1V for low-voltage signal
    settings.set_channel_range("ai3", 0.0, 5.0)     # 0-5V for unipolar signal
    
    print(f"\nConfigured channel ranges:")
    for channel in settings.channels:
        v_min, v_max = settings.get_channel_range(channel)
        range_span = v_max - v_min
        resolution_16bit = range_span / (2**16)
        print(f"  {channel}: {v_min:+.1f}V to {v_max:+.1f}V (span: {range_span:.1f}V, "
              f"16-bit resolution: {resolution_16bit*1000:.3f}mV)")
    
    # Note: This example assumes you have an NI device connected
    # Uncomment the following lines to actually run the acquisition:
    
    # try:
    #     reader = NIDAQReader(settings)
    #     reader.start()
    #     
    #     print(f"\nAcquiring 1000 samples...")
    #     t_ms, voltages = reader.read_data(1000)
    #     
    #     print(f"Acquired {len(t_ms)} samples from {voltages.shape[1]} channels")
    #     print(f"Time range: {t_ms[0]:.1f} to {t_ms[-1]:.1f} ms")
    #     
    #     for i, channel in enumerate(settings.channels):
    #         channel_data = voltages[:, i]
    #         print(f"{channel}: min={channel_data.min():.4f}V, "
    #               f"max={channel_data.max():.4f}V, mean={channel_data.mean():.4f}V")
    #     
    # except Exception as e:
    #     print(f"Note: Could not connect to NI device: {e}")
    # finally:
    #     try:
    #         reader.stop()
    #     except:
    #         pass
    
    print("\nAdvantages of per-channel gains:")
    print("- Better resolution for small signals (uses full ADC range)")
    print("- Prevents clipping of large signals")  
    print("- Each channel optimized for its specific signal type")
    print("- Improves overall measurement accuracy")

if __name__ == "__main__":
    main()
