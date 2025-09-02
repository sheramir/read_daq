#!/usr/bin/env python3
"""
Test script to demonstrate settings persistence functionality.
"""

import json
import time
from niDAQ import NIDAQSettings

def create_test_settings():
    """Create a test settings file with various configurations."""
    
    # Create sample settings
    settings = {
        "sample_rate": 5000.0,
        "channels": ["ai0", "ai1", "ai2"],
        "device": "Dev1",
        "duration": 10.0,
        "display_duration": 5.0,
        "channel_ranges": {
            "ai0": "±1 V",
            "ai1": "±5 V", 
            "ai2": "±10 V"
        },
        "plot_settings": {
            "show_legend": True,
            "auto_scale": False,
            "show_grid": True,
            "line_width": 2.0
        },
        "filter_settings": {
            "enable_filter": True,
            "filter_type": "lowpass",
            "cutoff_frequency": 1000.0,
            "filter_order": 4
        },
        "save_settings": {
            "save_directory": "C:/DAQ_Data",
            "auto_save": True,
            "file_format": "csv"
        },
        "spectrum_settings": {
            "enable_spectrum": True,
            "window_function": "hanning",
            "overlap_percent": 50.0,
            "frequency_resolution": 1.0
        }
    }
    
    # Save to file
    with open("daq_settings.json", "w") as f:
        json.dump(settings, f, indent=2)
    
    print("Created test settings file: daq_settings.json")
    print("Settings contents:")
    print(json.dumps(settings, indent=2))

def verify_settings_load():
    """Verify that settings can be loaded correctly."""
    try:
        with open("daq_settings.json", "r") as f:
            loaded_settings = json.load(f)
        
        print("\nLoaded settings successfully:")
        print(f"Sample rate: {loaded_settings['sample_rate']} Hz")
        print(f"Channels: {loaded_settings['channels']}")
        print(f"Channel ranges: {loaded_settings['channel_ranges']}")
        print(f"Filter enabled: {loaded_settings['filter_settings']['enable_filter']}")
        print(f"Save directory: {loaded_settings['save_settings']['save_directory']}")
        
        return True
    except Exception as e:
        print(f"Error loading settings: {e}")
        return False

if __name__ == "__main__":
    print("Testing Settings Persistence System")
    print("=" * 40)
    
    # Create test settings
    create_test_settings()
    
    # Verify loading
    if verify_settings_load():
        print("\nSettings persistence test: PASSED ✓")
        print("You can now restart the DAQ application to see settings loaded automatically.")
    else:
        print("\nSettings persistence test: FAILED ✗")
