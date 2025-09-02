"""
DAQ Controller Module

Handles DAQ operations, worker thread, device detection and management.
Separated from main GUI for better maintainability.
"""

from PySide6 import QtCore
import numpy as np
from niDAQ import NIDAQReader, NIDAQSettings


class DAQWorker(QtCore.QThread):
    """Worker thread for DAQ data acquisition."""
    
    data_ready = QtCore.Signal(np.ndarray, np.ndarray)  # t, y
    error = QtCore.Signal(str)

    def __init__(self, settings, samples_per_read, avg_ms):
        super().__init__()
        self.settings = settings
        self.samples_per_read = samples_per_read
        self.avg_ms = avg_ms
        self.running = False

    def run(self):
        try:
            reader = NIDAQReader(self.settings)
            reader.start()
            self.running = True
            while self.running:
                t, y = reader.read_data(
                    number_of_samples_per_channel=self.samples_per_read,
                    average_ms=self.avg_ms if self.avg_ms > 0 else None,
                    accumulate=True,
                    timeout=1.0,
                )
                self.data_ready.emit(t, y)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            try:
                reader.stop()
            except Exception:
                pass

    def stop(self):
        self.running = False


class DAQController(QtCore.QObject):
    """Controller for managing DAQ operations and device detection."""
    
    # Signals
    acquisition_started = QtCore.Signal()
    acquisition_stopped = QtCore.Signal()
    devices_updated = QtCore.Signal(list)  # List of available devices
    status_message = QtCore.Signal(str)
    error_occurred = QtCore.Signal(str)
    data_ready = QtCore.Signal(np.ndarray, np.ndarray)  # Forward from worker
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self._last_devices = tuple()
        self._device_timer = None
        self.setup_device_polling()
    
    def setup_device_polling(self):
        """Begin periodic polling for newly connected / removed NI devices."""
        self._device_timer = QtCore.QTimer(self)
        self._device_timer.setInterval(2000)  # 2 second poll
        self._device_timer.timeout.connect(self.poll_devices)
        self._device_timer.start()
    
    def detect_devices(self):
        """Detect available DAQ devices and emit devices_updated signal."""
        try:
            devices = NIDAQReader.list_devices()
            self._last_devices = tuple(devices)
            self.devices_updated.emit(devices)
            
            if devices:
                self.status_message.emit(f"Device detected: {devices[0]}")
            else:
                self.status_message.emit("No device found (waiting for connection)...")
                
        except Exception as e:
            self.error_occurred.emit(f"Error detecting devices: {e}")
            self.devices_updated.emit([])
    
    def poll_devices(self):
        """Poll system for NI devices and emit update if list changed."""
        try:
            devices = NIDAQReader.list_devices()
        except Exception:
            devices = []
            
        devices_tuple = tuple(devices)
        if devices_tuple == self._last_devices:
            return  # No change
        
        self._last_devices = devices_tuple
        self.devices_updated.emit(devices)
        
        if devices:
            self.status_message.emit(f"Device list updated. Available: {', '.join(devices)}")
        else:
            self.status_message.emit("Device disconnected. Waiting for connection...")
    
    def start_acquisition(self, settings_dict, samples_per_read, avg_ms):
        """Start DAQ data acquisition with given settings."""
        if self.worker and self.worker.isRunning():
            self.error_occurred.emit("Acquisition already running")
            return False
        
        try:
            # Create NIDAQSettings object from dictionary
            settings = NIDAQSettings(
                device_name=settings_dict['device_name'],
                channels=settings_dict['channels'],
                sampling_rate_hz=settings_dict['sampling_rate'],
                terminal_config=settings_dict['terminal_config'],
                v_min=settings_dict['v_min'],
                v_max=settings_dict['v_max'],
                inter_channel_delay_us=settings_dict.get('inter_channel_delay_us', 0.0),
                channel_ranges=settings_dict.get('channel_ranges')
            )
            
            # Create and start worker
            self.worker = DAQWorker(settings, samples_per_read, avg_ms)
            self.worker.data_ready.connect(self.data_ready.emit)
            self.worker.error.connect(self._on_worker_error)
            self.worker.start()
            
            self.acquisition_started.emit()
            self.status_message.emit("Acquisition started.")
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to start acquisition: {e}")
            return False
    
    def stop_acquisition(self):
        """Stop DAQ data acquisition."""
        if self.worker:
            self.worker.stop()
            self.worker.wait()
            self.worker = None
        
        self.acquisition_stopped.emit()
        self.status_message.emit("Acquisition stopped.")
    
    def is_acquiring(self):
        """Check if acquisition is currently running."""
        return self.worker is not None and self.worker.isRunning()
    
    def validate_delay_setting(self, device_name, channels, delay_us):
        """Validate inter-channel delay setting and return warning message if needed."""
        if delay_us <= 0:
            return None  # No validation needed for auto mode
        
        try:
            # Create temporary settings to check max conversion rate
            temp_settings = NIDAQSettings(
                device_name=device_name,
                channels=channels or ["ai0"],
                inter_channel_delay_us=delay_us
            )
            
            # Create temporary reader to check max rate
            temp_reader = NIDAQReader(temp_settings)
            try:
                temp_reader.start()
                max_conv_rate = temp_reader.get_max_conversion_rate()
                temp_reader.close()
                
                if max_conv_rate is not None:
                    # Convert delay to required rate
                    required_rate = 1.0 / (delay_us * 1e-6)
                    if required_rate > max_conv_rate:
                        max_delay_us = 1.0 / max_conv_rate * 1e6
                        return f"Warning: Delay {delay_us:.2f} µs too small. Maximum delay: {max_delay_us:.2f} µs"
                    else:
                        return f"Inter-channel delay: {delay_us:.2f} µs"
                        
            except Exception:
                temp_reader.close()
                
        except Exception:
            pass  # Don't show errors for delay validation failures
        
        return None
    
    def _on_worker_error(self, msg):
        """Handle worker thread errors."""
        self.error_occurred.emit(f"DAQ error: {msg}")
        self.stop_acquisition()
