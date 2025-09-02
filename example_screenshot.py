#!/usr/bin/env python3
"""
Example demonstrating the graph screenshot functionality.
This shows how the automatic filename generation works.
"""

import datetime

def demonstrate_screenshot_feature():
    """Show examples of the screenshot filename generation."""
    
    print("DAQ Application - Graph Screenshot Feature")
    print("=" * 50)
    
    # Current time example
    now = datetime.datetime.now()
    time_str = now.strftime("%m.%d.%y-%H%M")
    
    print(f"Current time: {now.strftime('%I:%M %p on %B %d, %Y')}")
    print(f"Filename timestamp: {time_str}")
    print()
    
    # Example scenarios
    scenarios = [
        {
            "description": "Time domain analysis with two channels",
            "graph_type": "time",
            "active_channels": ["ai1", "ai5"],
            "context": "Monitoring voltage levels on analog inputs 1 and 5"
        },
        {
            "description": "Spectrum analysis of a single channel",
            "graph_type": "spectrum", 
            "active_channels": ["ai0"],
            "context": "Frequency analysis of signal on analog input 0"
        },
        {
            "description": "Time domain with multiple channels",
            "graph_type": "time",
            "active_channels": ["ai0", "ai2", "ai3"],
            "context": "Multi-channel sensor monitoring"
        },
        {
            "description": "Spectrum analysis with no visible data",
            "graph_type": "spectrum",
            "active_channels": [],
            "context": "Graph tab open but no channels selected"
        }
    ]
    
    print("Screenshot Filename Examples:")
    print("-" * 30)
    
    for i, scenario in enumerate(scenarios, 1):
        # Convert channel names for filename
        if scenario["active_channels"]:
            channel_names = [ch.replace("ai", "a") for ch in scenario["active_channels"]]
            channels_str = "".join(channel_names)
        else:
            channels_str = "nodata"
        
        filename = f"graph-{scenario['graph_type']}-{time_str}-{channels_str}.png"
        
        print(f"{i}. {scenario['description']}")
        print(f"   Context: {scenario['context']}")
        print(f"   Filename: {filename}")
        print()
    
    print("How to Use:")
    print("1. Start the DAQ application")
    print("2. Select a save directory using 'Browse Directory' button")
    print("3. Configure and start data acquisition")
    print("4. Switch to desired graph tab (Time or Spectrum)")
    print("5. Click '📷 Capture Graph' button")
    print("6. High-resolution PNG saved with automatic naming")
    print()
    
    print("File Details:")
    print(f"- Resolution: 1920×1080 pixels")
    print(f"- Format: PNG with anti-aliasing")
    print(f"- Location: User-selected save directory")
    print(f"- Automatic naming prevents file overwrites")

if __name__ == "__main__":
    demonstrate_screenshot_feature()
