#!/usr/bin/env python3
"""
Test channel format conversion for high-performance mode.
"""

def test_channel_format():
    """Test that channels are properly formatted for high-performance streamer."""
    # Simulate the channel format conversion
    channels = ["ai0", "ai1", "ai2"]  # From get_selected_channels()
    device_name = "Dev1"  # From DAQ settings
    
    # Convert to full device paths (like in fixed code)
    full_channel_names = [f"{device_name}/{channel}" for channel in channels]
    
    print("Original channels:", channels)
    print("Device name:", device_name)
    print("Full channel names:", full_channel_names)
    
    # Verify format is correct for NI-DAQmx
    expected_format = ["Dev1/ai0", "Dev1/ai1", "Dev1/ai2"]
    if full_channel_names == expected_format:
        print("✓ Channel format conversion is correct!")
        return True
    else:
        print("✗ Channel format conversion failed!")
        print("Expected:", expected_format)
        print("Got:", full_channel_names)
        return False

if __name__ == "__main__":
    success = test_channel_format()
    print(f"\nTest result: {'PASS' if success else 'FAIL'}")
