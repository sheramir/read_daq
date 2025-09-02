#!/usr/bin/env python3
"""
Test script for screenshot functionality.
Demonstrates the graph capture feature with filename format.
"""

import datetime

def test_screenshot_filename_generation():
    """Test the filename generation logic for screenshots."""
    
    print("Graph Screenshot Filename Generation Test")
    print("=" * 50)
    
    # Simulate current time
    now = datetime.datetime.now()
    time_str = now.strftime("%m.%d.%y-%H%M")
    
    # Test different scenarios
    test_cases = [
        {
            "graph_type": "time",
            "channels": ["ai0", "ai1"],
            "visible": [True, True],
            "expected_pattern": f"graph-time-{time_str}-a0a1.png"
        },
        {
            "graph_type": "spectrum", 
            "channels": ["ai1", "ai5"],
            "visible": [True, True],
            "expected_pattern": f"graph-spectrum-{time_str}-a1a5.png"
        },
        {
            "graph_type": "time",
            "channels": ["ai0", "ai1", "ai2"],
            "visible": [True, False, True],
            "expected_pattern": f"graph-time-{time_str}-a0a2.png"
        },
        {
            "graph_type": "spectrum",
            "channels": [],
            "visible": [],
            "expected_pattern": f"graph-spectrum-{time_str}-nodata.png"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"  Graph Type: {case['graph_type']}")
        print(f"  Available Channels: {case['channels']}")
        print(f"  Visible Channels: {[ch for ch, vis in zip(case['channels'], case['visible']) if vis]}")
        
        # Simulate the filename generation logic
        active_channels = []
        for j, channel in enumerate(case['channels']):
            if j < len(case['visible']) and case['visible'][j]:
                if channel.startswith("ai"):
                    active_channels.append("a" + channel[2:])
                else:
                    active_channels.append(channel)
        
        if active_channels:
            channels_str = "".join(active_channels)
        else:
            channels_str = "nodata"
        
        filename = f"graph-{case['graph_type']}-{time_str}-{channels_str}.png"
        
        print(f"  Generated Filename: {filename}")
        print(f"  Expected Pattern: {case['expected_pattern']}")
        print(f"  ✓ Match: {filename == case['expected_pattern']}")
    
    print(f"\nExample filenames for current time ({now.strftime('%B %d, %Y at %H:%M')}):")
    print(f"  Time domain with channels ai1, ai5: graph-time-{time_str}-a1a5.png")
    print(f"  Spectrum with channels ai0, ai2: graph-spectrum-{time_str}-a0a2.png")
    print(f"  Time domain with no visible channels: graph-time-{time_str}-nodata.png")

def show_screenshot_usage():
    """Show how to use the screenshot feature."""
    
    print("\nHow to Use the Graph Screenshot Feature:")
    print("=" * 45)
    print("1. Start the DAQ application")
    print("2. Select a save directory using 'Browse Directory'")
    print("3. Configure your channels and start data acquisition")
    print("4. Switch to the desired graph tab (Time Analyzer or Spectrum Analyzer)")
    print("5. Click the '📷 Capture Graph' button")
    print("6. The graph will be saved as a high-resolution PNG file")
    print()
    print("Filename Format:")
    print("  graph-[type]-[date]-[time]-[channels].png")
    print("  Where:")
    print("    [type] = 'time' or 'spectrum'")
    print("    [date] = MM.DD.YY format")
    print("    [time] = HHMM format (24-hour)")
    print("    [channels] = visible channel names (e.g., 'a1a5' for ai1 and ai5)")
    print()
    print("Examples:")
    print("  graph-time-08.29.25-0900-a1a5.png")
    print("  graph-spectrum-08.29.25-1430-a0a2a3.png")
    print("  graph-time-08.29.25-2115-nodata.png")

if __name__ == "__main__":
    test_screenshot_filename_generation()
    show_screenshot_usage()
