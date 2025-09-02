"""
Data Processor Module

Handles data processing, filtering, FFT analysis, and statistics calculations.
Separated from main GUI for better maintainability.
"""

import numpy as np
from PySide6 import QtCore

# Try to import filtering functions
try:
    from freq_filters import low_pass, high_pass, band_pass, band_stop, notch_50hz, notch_60hz
    FILTERS_AVAILABLE = True
except ImportError:
    FILTERS_AVAILABLE = False


class DataProcessor(QtCore.QObject):
    """Handles data processing, filtering, and analysis operations."""
    
    # Signals
    statistics_updated = QtCore.Signal(dict)  # Channel statistics
    
    def __init__(self):
        super().__init__()
        self.history_t = []
        self.history_y = []
        
        # Filter settings
        self.filter_enabled = False
        self.filter_type = "low_pass"
        self.filter_cutoff1 = 100.0
        self.filter_cutoff2 = 200.0
        self.filter_order = 4
    
    def add_data(self, t, y, max_buffer_seconds=5, sampling_rate=1000):
        """Add new data to the history buffer."""
        if t.size == 0 or y.size == 0:
            return
        
        self.history_t.extend(t.tolist())
        
        # Handle both 1D and 2D arrays for y
        if y.ndim == 1:
            # Single channel - reshape to 2D
            y_list = [[val] for val in y.tolist()]
        else:
            # Multiple channels
            y_list = y.tolist()
        
        self.history_y.extend(y_list)
        
        # Keep buffer to specified duration
        max_samples = int(max(max_buffer_seconds * sampling_rate, 
                             2 * sampling_rate * 0.1))  # Minimum buffer
        if len(self.history_t) > max_samples:
            self.history_t = self.history_t[-max_samples:]
            self.history_y = self.history_y[-max_samples:]
    
    def get_current_data(self):
        """Get current data as numpy arrays."""
        if not self.history_t or not self.history_y:
            return np.array([]), np.array([])
        
        arr_t = np.array(self.history_t)
        arr_y = np.array(self.history_y)
        return arr_t, arr_y
    
    def get_filtered_data(self):
        """Get current data with filtering applied if enabled."""
        arr_t, arr_y = self.get_current_data()
        
        if arr_t.size == 0 or arr_y.size == 0:
            return arr_t, arr_y
        
        # Apply filtering if enabled and available
        if FILTERS_AVAILABLE and self.filter_enabled:
            try:
                arr_y = self.apply_filter(arr_t, arr_y)
            except Exception as e:
                # If filtering fails, use original data
                print(f"Filter error: {e}")
        
        return arr_t, arr_y
    
    def apply_filter(self, t, y):
        """Apply the selected filter to the data."""
        if not FILTERS_AVAILABLE or not self.filter_enabled or len(t) < 10:
            return y
        
        try:
            if self.filter_type == "low_pass":
                return low_pass(y, t, self.filter_cutoff1, order=self.filter_order)
            elif self.filter_type == "high_pass":
                return high_pass(y, t, self.filter_cutoff1, order=self.filter_order)
            elif self.filter_type == "band_pass":
                return band_pass(y, t, self.filter_cutoff1, self.filter_cutoff2, order=self.filter_order)
            elif self.filter_type == "band_stop":
                return band_stop(y, t, self.filter_cutoff1, self.filter_cutoff2, order=self.filter_order)
            elif self.filter_type == "50hz_notch":
                return notch_50hz(y, t, order=self.filter_order)
            elif self.filter_type == "60hz_notch":
                return notch_60hz(y, t, order=self.filter_order)
            else:
                return y
        except Exception as e:
            raise Exception(f"Filter processing failed: {e}")
    
    def set_filter_settings(self, enabled, filter_type, cutoff1, cutoff2, order):
        """Update filter settings."""
        self.filter_enabled = enabled and FILTERS_AVAILABLE
        self.filter_type = filter_type.lower().replace(" ", "_")
        self.filter_cutoff1 = cutoff1
        self.filter_cutoff2 = cutoff2
        self.filter_order = order
    
    def calculate_statistics(self, channels):
        """Calculate statistics for current data and emit signal."""
        arr_t, arr_y = self.get_filtered_data()
        
        if arr_y.size == 0 or len(channels) == 0:
            return
        
        stats = {}
        
        # Calculate statistics for each channel that has data
        for i, channel in enumerate(channels):
            if i < arr_y.shape[1] and len(arr_y[:, i]) > 0:
                channel_data = arr_y[:, i]
                stats[channel] = {
                    'min': float(np.min(channel_data)),
                    'max': float(np.max(channel_data)),
                    'mean': float(np.mean(channel_data)),
                    'std': float(np.std(channel_data)),
                    'rms': float(np.sqrt(np.mean(channel_data**2)))
                }
        
        self.statistics_updated.emit(stats)
    
    def compute_spectrum(self, sampling_rate, window_type="hanning", fft_size="auto", max_freq=100):
        """Compute power spectral density for current data."""
        arr_t, arr_y = self.get_filtered_data()
        
        if len(arr_t) < 2 or arr_y.size == 0:
            return None, None, None
        
        # Calculate sampling frequency
        dt_ms = np.mean(np.diff(arr_t))  # Average time step in ms
        fs = 1000.0 / dt_ms  # Convert to Hz
        
        # Determine FFT size
        if str(fft_size).lower() == "auto":
            available_samples = len(arr_y)
            if available_samples > 1:
                fft_size_val = min(available_samples, 2**int(np.log2(available_samples)))
            else:
                fft_size_val = available_samples
            fft_size_val = max(fft_size_val, 32)  # Minimum size
        else:
            try:
                fft_size_val = int(fft_size)
                fft_size_val = min(fft_size_val, len(arr_y))
            except (ValueError, TypeError):
                # Fallback to auto mode if conversion fails
                available_samples = len(arr_y)
                if available_samples > 1:
                    fft_size_val = min(available_samples, 2**int(np.log2(available_samples)))
                else:
                    fft_size_val = available_samples
                fft_size_val = max(fft_size_val, 32)  # Minimum size
        
        if fft_size_val < 32:
            return None, None, None
        
        # Use the most recent data for FFT
        recent_data = arr_y[-fft_size_val:]
        
        # Select window function
        window_type_lower = window_type.lower()
        if window_type_lower == "hanning":
            window = np.hanning(fft_size_val)
        elif window_type_lower == "hamming":
            window = np.hamming(fft_size_val)
        elif window_type_lower == "blackman":
            window = np.blackman(fft_size_val)
        else:  # Rectangle
            window = np.ones(fft_size_val)
        
        # Compute spectrum for each channel
        spectra = []
        freqs = np.fft.rfftfreq(fft_size_val, d=dt_ms/1000.0)
        
        for i in range(recent_data.shape[1]):
            # Apply window to the signal
            windowed_signal = recent_data[:, i] * window
            
            # Compute FFT
            fft_result = np.fft.rfft(windowed_signal)
            
            # Compute power spectral density
            psd = np.abs(fft_result) ** 2
            
            # Normalize by window power and sampling frequency
            window_power = np.sum(window**2)
            psd = psd / (fs * window_power)
            
            # Convert to dB (avoid log of zero)
            psd_db = 10 * np.log10(np.maximum(psd, 1e-12))
            
            spectra.append(psd_db)
        
        # Limit frequency range
        freq_mask = freqs <= max_freq
        freqs_limited = freqs[freq_mask]
        spectra_limited = [spectrum[freq_mask] for spectrum in spectra]
        
        return freqs_limited, spectra_limited, fs
    
    def clear_data(self):
        """Clear all stored data."""
        self.history_t = []
        self.history_y = []
    
    def get_data_length(self):
        """Get the current number of data points."""
        return len(self.history_t)
    
    def is_filters_available(self):
        """Check if filtering capabilities are available."""
        return FILTERS_AVAILABLE
