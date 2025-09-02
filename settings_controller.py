"""
Settings Controller Module

Handles settings management, validation, and GUI synchronization.
Separated from main window for better maintainability.
"""

from PySide6 import QtCore
from settings_manager import SettingsManager


class SettingsController(QtCore.QObject):
    """Controller for managing application settings."""
    
    # Signals
    settings_loaded = QtCore.Signal(dict)
    settings_saved = QtCore.Signal()
    settings_error = QtCore.Signal(str)
    
    def __init__(self):
        super().__init__()
        self.settings_manager = SettingsManager()
        self.current_settings = {}
        self.channel_ranges = {}
    
    def load_settings(self):
        """Load settings from file and emit loaded signal."""
        try:
            self.current_settings = self.settings_manager.load_settings()
            # Convert legacy channel ranges format if needed
            self.channel_ranges = self._convert_legacy_channel_ranges(
                self.current_settings.get("channel_ranges", {})
            )
            self.current_settings["channel_ranges"] = self.channel_ranges
            self.settings_loaded.emit(self.current_settings)
            return self.current_settings
        except Exception as e:
            self.settings_error.emit(f"Error loading settings: {e}")
            return self.get_default_settings()
    
    def _convert_legacy_channel_ranges(self, channel_ranges):
        """Convert legacy string format channel ranges to tuple format."""
        converted = {}
        for channel, range_data in channel_ranges.items():
            if isinstance(range_data, str):
                # Legacy format: "±1 V", "±5 V", etc.
                # Convert to tuple format for consistency
                try:
                    # Extract the number from strings like "±1 V"
                    import re
                    match = re.search(r'±(\d+(?:\.\d+)?)', range_data)
                    if match:
                        voltage = float(match.group(1))
                        converted[channel] = (-voltage, voltage)
                    else:
                        # If we can't parse, skip this channel range
                        continue
                except:
                    # If conversion fails, skip this channel range
                    continue
            elif isinstance(range_data, (tuple, list)) and len(range_data) == 2:
                # Already in correct format
                converted[channel] = tuple(range_data)
        return converted
    
    def save_settings(self, settings=None):
        """Save current settings to file."""
        try:
            if settings:
                self.current_settings = settings
            
            # Validate settings before saving
            validated_settings = self.settings_manager.validate_settings(self.current_settings)
            success = self.settings_manager.save_settings(validated_settings)
            
            if success:
                self.settings_saved.emit()
            else:
                self.settings_error.emit("Could not save settings to file")
                
        except Exception as e:
            self.settings_error.emit(f"Error saving settings: {e}")
    
    def collect_gui_settings(self, gui_widgets):
        """Collect settings from GUI widgets into a dictionary."""
        try:
            # Get selected channels
            selected_channels = [i for i, cb in enumerate(gui_widgets['aiChecks']) if cb.isChecked()]
            
            # Get channel visibility
            channel_visibility = [cb.isChecked() for cb in gui_widgets['plotVisibilityChecks']]
            # Pad to 16 channels if needed
            while len(channel_visibility) < 16:
                channel_visibility.append(False)
            
            settings = {
                # Device settings
                "device_name": gui_widgets['deviceSelector'].currentText() if gui_widgets['deviceSelector'].count() > 0 else "",
                "input_config": gui_widgets['inputConfigCombo'].currentText(),
                
                # Voltage range settings
                "max_voltage": gui_widgets['maxVoltSpin'].value(),
                "min_voltage": gui_widgets['minVoltSpin'].value(),
                
                # Sampling settings
                "sampling_rate": gui_widgets['rateSpin'].value(),
                "samples_to_read": gui_widgets['samplesSpin'].value(),
                "average_time_span": gui_widgets['avgMsSpin'].value(),
                "inter_channel_delay_us": gui_widgets['delaySpin'].value(),
                
                # Channel settings
                "selected_channels": selected_channels,
                "channel_visibility": channel_visibility,
                "channel_ranges": self.channel_ranges,
                
                # Plot settings
                "auto_scale": gui_widgets['autoScaleCheck'].isChecked(),
                "active_tab": gui_widgets['plot_tabs'].currentIndex(),
                
                # Spectrum analyzer settings
                "fft_window": gui_widgets['fftWindowCombo'].currentText(),
                "fft_size": gui_widgets['fftSizeCombo'].currentText(),
                "max_frequency": gui_widgets['maxFreqSpin'].value(),
                
                # File settings
                "save_directory": getattr(gui_widgets, 'save_directory', "") or "",
                "last_filename": gui_widgets['saveNameEdit'].text()
            }
            
            # Add filter settings if available
            if 'filterEnableCheck' in gui_widgets:
                settings.update({
                    "filter_enabled": gui_widgets['filterEnableCheck'].isChecked(),
                    "filter_type": gui_widgets['filterTypeCombo'].currentText(),
                    "filter_cutoff1": gui_widgets['filterCutoff1Spin'].value(),
                    "filter_cutoff2": gui_widgets['filterCutoff2Spin'].value(),
                    "filter_order": gui_widgets['filterOrderSpin'].value(),
                })
            else:
                # Keep previous filter settings if filters not available
                settings.update({
                    "filter_enabled": self.current_settings.get("filter_enabled", False),
                    "filter_type": self.current_settings.get("filter_type", "Low Pass"),
                    "filter_cutoff1": self.current_settings.get("filter_cutoff1", 100.0),
                    "filter_cutoff2": self.current_settings.get("filter_cutoff2", 200.0),
                    "filter_order": self.current_settings.get("filter_order", 4),
                })
            
            self.current_settings = settings
            return settings
            
        except Exception as e:
            self.settings_error.emit(f"Error collecting GUI settings: {e}")
            return self.current_settings
    
    def apply_settings_to_gui(self, gui_widgets, settings=None):
        """Apply settings to GUI widgets."""
        if settings is None:
            settings = self.current_settings
            
        try:
            # Apply device settings
            if settings["input_config"]:
                idx = gui_widgets['inputConfigCombo'].findText(settings["input_config"])
                if idx >= 0:
                    gui_widgets['inputConfigCombo'].setCurrentIndex(idx)
            
            # Apply voltage range settings
            gui_widgets['maxVoltSpin'].setValue(settings["max_voltage"])
            gui_widgets['minVoltSpin'].setValue(settings["min_voltage"])
            
            # Apply sampling settings
            gui_widgets['rateSpin'].setValue(settings["sampling_rate"])
            gui_widgets['samplesSpin'].setValue(settings["samples_to_read"])
            gui_widgets['avgMsSpin'].setValue(settings["average_time_span"])
            gui_widgets['delaySpin'].setValue(settings.get("inter_channel_delay_us", 0.0))
            
            # Apply channel selections
            for i, cb in enumerate(gui_widgets['aiChecks']):
                cb.setChecked(i in settings["selected_channels"])
            
            # Apply channel visibility
            for i, checked in enumerate(settings["channel_visibility"][:16]):
                if i < len(gui_widgets['plotVisibilityChecks']):
                    gui_widgets['plotVisibilityChecks'][i].setChecked(checked)
            
            # Apply plot settings
            gui_widgets['autoScaleCheck'].setChecked(settings["auto_scale"])
            gui_widgets['plot_tabs'].setCurrentIndex(settings["active_tab"])
            
            # Apply spectrum analyzer settings
            idx = gui_widgets['fftWindowCombo'].findText(settings["fft_window"])
            if idx >= 0:
                gui_widgets['fftWindowCombo'].setCurrentIndex(idx)
            
            idx = gui_widgets['fftSizeCombo'].findText(settings["fft_size"])
            if idx >= 0:
                gui_widgets['fftSizeCombo'].setCurrentIndex(idx)
            
            gui_widgets['maxFreqSpin'].setValue(settings["max_frequency"])
            
            # Apply filter settings (if available)
            if 'filterEnableCheck' in gui_widgets:
                gui_widgets['filterEnableCheck'].setChecked(settings["filter_enabled"])
                
                idx = gui_widgets['filterTypeCombo'].findText(settings["filter_type"])
                if idx >= 0:
                    gui_widgets['filterTypeCombo'].setCurrentIndex(idx)
                
                gui_widgets['filterCutoff1Spin'].setValue(settings["filter_cutoff1"])
                gui_widgets['filterCutoff2Spin'].setValue(settings["filter_cutoff2"])
                gui_widgets['filterOrderSpin'].setValue(settings["filter_order"])
            
            # Apply file settings
            if settings["save_directory"]:
                # This will be handled by the main window
                pass
            
            if settings["last_filename"]:
                gui_widgets['saveNameEdit'].setText(settings["last_filename"])
            
            return True
            
        except Exception as e:
            self.settings_error.emit(f"Error applying settings to GUI: {e}")
            return False
    
    def restore_device_selection(self, gui_widgets):
        """Restore device selection after device detection."""
        try:
            if self.current_settings["device_name"]:
                device_selector = gui_widgets['deviceSelector']
                idx = device_selector.findText(self.current_settings["device_name"])
                if idx >= 0:
                    device_selector.setCurrentIndex(idx)
                    return True
            return False
        except Exception as e:
            self.settings_error.emit(f"Error restoring device selection: {e}")
            return False
    
    def get_channel_ranges(self):
        """Get current channel ranges."""
        return self.channel_ranges.copy()
    
    def set_channel_ranges(self, channel_ranges):
        """Set channel ranges and update current settings."""
        self.channel_ranges = channel_ranges.copy()
        self.current_settings["channel_ranges"] = self.channel_ranges
    
    def get_save_directory(self):
        """Get current save directory from settings."""
        return self.current_settings.get("save_directory", "")
    
    def set_save_directory(self, directory):
        """Set save directory in current settings."""
        self.current_settings["save_directory"] = directory
    
    def get_daq_settings_dict(self, gui_widgets):
        """Get settings dictionary formatted for DAQ operations."""
        try:
            selected_channels = [f"ai{i}" for i, cb in enumerate(gui_widgets['aiChecks']) if cb.isChecked()]
            
            return {
                'device_name': gui_widgets['deviceSelector'].currentText(),
                'channels': selected_channels,
                'sampling_rate': gui_widgets['rateSpin'].value(),
                'terminal_config': gui_widgets['inputConfigCombo'].currentText(),
                'v_min': gui_widgets['minVoltSpin'].value(),
                'v_max': gui_widgets['maxVoltSpin'].value(),
                'inter_channel_delay_us': gui_widgets['delaySpin'].value(),
                'channel_ranges': self.channel_ranges if self.channel_ranges else None
            }
        except Exception as e:
            self.settings_error.emit(f"Error creating DAQ settings: {e}")
            return {}
    
    def get_filter_settings_dict(self, gui_widgets):
        """Get filter settings dictionary."""
        try:
            if 'filterEnableCheck' in gui_widgets:
                return {
                    'enabled': gui_widgets['filterEnableCheck'].isChecked(),
                    'filter_type': gui_widgets['filterTypeCombo'].currentText(),
                    'cutoff1': gui_widgets['filterCutoff1Spin'].value(),
                    'cutoff2': gui_widgets['filterCutoff2Spin'].value(),
                    'order': gui_widgets['filterOrderSpin'].value()
                }
            else:
                return {
                    'enabled': False,
                    'filter_type': "Low Pass",
                    'cutoff1': 100.0,
                    'cutoff2': 200.0,
                    'order': 4
                }
        except Exception as e:
            self.settings_error.emit(f"Error getting filter settings: {e}")
            return {'enabled': False}
    
    def get_spectrum_settings_dict(self, gui_widgets):
        """Get spectrum analyzer settings dictionary."""
        try:
            return {
                'window_type': gui_widgets['fftWindowCombo'].currentText(),
                'fft_size': gui_widgets['fftSizeCombo'].currentText(),
                'max_frequency': gui_widgets['maxFreqSpin'].value(),
                'sampling_rate': gui_widgets['rateSpin'].value()
            }
        except Exception as e:
            self.settings_error.emit(f"Error getting spectrum settings: {e}")
            return {}
    
    def get_default_settings(self):
        """Get default settings dictionary."""
        return {
            "device_name": "",
            "input_config": "RSE",
            "max_voltage": 3.5,
            "min_voltage": -1.0,
            "sampling_rate": 200,
            "samples_to_read": 100,
            "average_time_span": 0,
            "inter_channel_delay_us": 0.0,
            "selected_channels": [0, 1],
            "channel_visibility": [True, True] + [False] * 14,
            "channel_ranges": {},
            "auto_scale": True,
            "active_tab": 0,
            "fft_window": "Hanning",
            "fft_size": "Auto",
            "max_frequency": 100,
            "filter_enabled": False,
            "filter_type": "Low Pass",
            "filter_cutoff1": 100.0,
            "filter_cutoff2": 200.0,
            "filter_order": 4,
            "save_directory": "",
            "last_filename": ""
        }
