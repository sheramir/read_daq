"""
Settings Manager for NI DAQ Application

Handles saving and loading of application settings to/from JSON file.
Includes all GUI parameters and per-channel gain configurations.
"""

import json
import os
from typing import Dict, Any, Optional
from dataclasses import asdict

class SettingsManager:
    """Manages application settings persistence."""
    
    def __init__(self, settings_file: str = "daq_settings.json"):
        self.settings_file = settings_file
        self.default_settings = self._get_default_settings()
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default application settings."""
        return {
            # Device settings
            "device_name": "",  # Will be auto-detected
            "input_config": "RSE",
            
            # Voltage range settings
            "max_voltage": 3.5,
            "min_voltage": -1.0,
            
            # Sampling settings
            "sampling_rate": 200,
            "samples_to_read": 100,
            "average_time_span": 0,
            
            # Channel settings
            "selected_channels": [0, 1],  # AI0, AI1 by default
            "channel_visibility": [True, True] + [False] * 14,  # First 2 visible
            "channel_ranges": {},  # Per-channel voltage ranges
            
            # Plot settings
            "auto_scale": True,
            "active_tab": 0,  # 0=Time Analyzer, 1=Spectrum Analyzer
            
            # Spectrum analyzer settings
            "fft_window": "Hanning",
            "fft_size": "Auto",
            "max_frequency": 100,
            
            # Filter settings
            "filter_enabled": False,
            "filter_type": "Low Pass",
            "filter_cutoff1": 100.0,
            "filter_cutoff2": 200.0,
            "filter_order": 4,
            
            # File settings
            "save_directory": "",
            "last_filename": ""
        }
    
    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file. Returns default settings if file doesn't exist."""
        if not os.path.exists(self.settings_file):
            print(f"Settings file '{self.settings_file}' not found. Using defaults.")
            return self.default_settings.copy()
        
        try:
            with open(self.settings_file, 'r') as f:
                loaded_settings = json.load(f)
            
            # Merge with defaults to handle missing keys in old settings files
            settings = self.default_settings.copy()
            settings.update(loaded_settings)
            
            print(f"Settings loaded from '{self.settings_file}'")
            return settings
            
        except Exception as e:
            print(f"Error loading settings: {e}. Using defaults.")
            return self.default_settings.copy()
    
    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """Save settings to file. Returns True if successful."""
        try:
            # Create backup of existing file
            if os.path.exists(self.settings_file):
                backup_file = self.settings_file + ".bak"
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                os.rename(self.settings_file, backup_file)
            
            # Save new settings
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2, sort_keys=True)
            
            print(f"Settings saved to '{self.settings_file}'")
            return True
            
        except Exception as e:
            print(f"Error saving settings: {e}")
            # Restore backup if save failed
            backup_file = self.settings_file + ".bak"
            if os.path.exists(backup_file):
                if os.path.exists(self.settings_file):
                    os.remove(self.settings_file)
                os.rename(backup_file, self.settings_file)
            return False
    
    def get_daq_settings_from_gui(self, settings: Dict[str, Any]):
        """Convert GUI settings to NIDAQSettings format."""
        from niDAQ import NIDAQSettings
        
        # Get selected channels
        channels = [f"ai{i}" for i in settings["selected_channels"]]
        
        # Create NIDAQSettings
        daq_settings = NIDAQSettings(
            device_name=settings["device_name"],
            channels=channels,
            sampling_rate_hz=settings["sampling_rate"],
            terminal_config=settings["input_config"],
            v_min=settings["min_voltage"],
            v_max=settings["max_voltage"],
            channel_ranges=settings["channel_ranges"] if settings["channel_ranges"] else None
        )
        
        return daq_settings
    
    def validate_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and correct settings values."""
        # Ensure required keys exist
        validated = self.default_settings.copy()
        validated.update(settings)
        
        # Validate ranges
        validated["sampling_rate"] = max(1, min(100000, validated["sampling_rate"]))
        validated["samples_to_read"] = max(1, min(100000, validated["samples_to_read"]))
        validated["average_time_span"] = max(0, min(10000, validated["average_time_span"]))
        validated["max_voltage"] = max(-10.0, min(10.0, validated["max_voltage"]))
        validated["min_voltage"] = max(-10.0, min(10.0, validated["min_voltage"]))
        validated["filter_cutoff1"] = max(0.1, min(10000.0, validated["filter_cutoff1"]))
        validated["filter_cutoff2"] = max(0.1, min(10000.0, validated["filter_cutoff2"]))
        validated["filter_order"] = max(1, min(10, validated["filter_order"]))
        validated["max_frequency"] = max(1, min(50000, validated["max_frequency"]))
        
        # Validate channel lists
        if len(validated["selected_channels"]) == 0:
            validated["selected_channels"] = [0, 1]
        
        if len(validated["channel_visibility"]) != 16:
            validated["channel_visibility"] = [True, True] + [False] * 14
        
        # Validate enum values
        valid_configs = ["RSE", "NRSE", "DIFF", "PSEUDO-DIFF"]
        if validated["input_config"] not in valid_configs:
            validated["input_config"] = "RSE"
        
        valid_windows = ["Hanning", "Hamming", "Blackman", "Rectangle"]
        if validated["fft_window"] not in valid_windows:
            validated["fft_window"] = "Hanning"
        
        valid_fft_sizes = ["Auto", "256", "512", "1024", "2048", "4096"]
        if validated["fft_size"] not in valid_fft_sizes:
            validated["fft_size"] = "Auto"
        
        valid_filters = ["Low Pass", "High Pass", "Band Pass", "Band Stop", "50Hz Notch", "60Hz Notch"]
        if validated["filter_type"] not in valid_filters:
            validated["filter_type"] = "Low Pass"
        
        return validated
