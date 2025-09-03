"""
High-performance circular buffer for real-time data acquisition.
Optimized for minimal memory allocation and fast append/read operations.
"""

import numpy as np
from typing import Tuple, Optional
import threading


class CircularBuffer:
    """
    Thread-safe circular buffer optimized for real-time data acquisition.
    
    Features:
    - Pre-allocated memory to avoid allocation overhead
    - Thread-safe operations using locks
    - Efficient modular arithmetic for indexing
    - Configurable buffer size based on memory constraints
    """
    
    def __init__(self, max_samples: int, n_channels: int, dtype=np.float64):
        """
        Initialize circular buffer.
        
        Args:
            max_samples: Maximum number of samples to store per channel
            n_channels: Number of data channels
            dtype: Data type for storage
        """
        self.max_samples = max_samples
        self.n_channels = n_channels
        self.dtype = dtype
        
        # Pre-allocate buffers
        self.data_buffer = np.zeros((max_samples, n_channels), dtype=dtype)
        self.time_buffer = np.zeros(max_samples, dtype=np.float64)
        
        # State variables
        self.write_index = 0
        self.total_written = 0
        self.lock = threading.RLock()
        
    def append(self, timestamps: np.ndarray, data: np.ndarray) -> None:
        """
        Append new data to the circular buffer.
        
        Args:
            timestamps: Time array (N,)
            data: Data array (N, C) where C is number of channels
        """
        if len(timestamps) == 0:
            return
            
        n_new = len(timestamps)
        
        with self.lock:
            # Handle wraparound
            if self.write_index + n_new <= self.max_samples:
                # Simple case: no wraparound
                end_idx = self.write_index + n_new
                self.time_buffer[self.write_index:end_idx] = timestamps
                self.data_buffer[self.write_index:end_idx] = data
            else:
                # Wraparound case: split the write
                first_chunk = self.max_samples - self.write_index
                second_chunk = n_new - first_chunk
                
                # Write first chunk to end of buffer
                self.time_buffer[self.write_index:] = timestamps[:first_chunk]
                self.data_buffer[self.write_index:] = data[:first_chunk]
                
                # Write second chunk to beginning of buffer
                self.time_buffer[:second_chunk] = timestamps[first_chunk:]
                self.data_buffer[:second_chunk] = data[first_chunk:]
            
            # Update indices
            self.write_index = (self.write_index + n_new) % self.max_samples
            self.total_written += n_new
    
    def get_recent_data(self, n_samples: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get the most recent N samples.
        
        Args:
            n_samples: Number of recent samples to retrieve. If None, returns all available.
            
        Returns:
            (timestamps, data) tuple
        """
        with self.lock:
            available = min(self.total_written, self.max_samples)
            if available == 0:
                return np.array([]), np.empty((0, self.n_channels))
            
            if n_samples is None:
                n_samples = available
            else:
                n_samples = min(n_samples, available)
            
            if n_samples == 0:
                return np.array([]), np.empty((0, self.n_channels))
            
            # Calculate start index for recent data
            if self.total_written <= self.max_samples:
                # Buffer not full yet
                start_idx = max(0, self.write_index - n_samples)
                end_idx = self.write_index
                timestamps = self.time_buffer[start_idx:end_idx].copy()
                data = self.data_buffer[start_idx:end_idx].copy()
            else:
                # Buffer is full, data wraps around
                start_idx = (self.write_index - n_samples) % self.max_samples
                
                if start_idx < self.write_index:
                    # No wraparound in read
                    timestamps = self.time_buffer[start_idx:self.write_index].copy()
                    data = self.data_buffer[start_idx:self.write_index].copy()
                else:
                    # Wraparound in read
                    first_part_t = self.time_buffer[start_idx:]
                    second_part_t = self.time_buffer[:self.write_index]
                    timestamps = np.concatenate([first_part_t, second_part_t])
                    
                    first_part_d = self.data_buffer[start_idx:]
                    second_part_d = self.data_buffer[:self.write_index]
                    data = np.concatenate([first_part_d, second_part_d])
            
            return timestamps, data
    
    def get_statistics(self) -> dict:
        """Get buffer statistics."""
        with self.lock:
            available = min(self.total_written, self.max_samples)
            if available == 0:
                return {
                    'total_written': self.total_written,
                    'available_samples': 0,
                    'buffer_usage': 0.0,
                    'memory_mb': 0.0
                }
            
            # Calculate memory usage
            memory_bytes = (self.data_buffer.nbytes + self.time_buffer.nbytes)
            memory_mb = memory_bytes / (1024 * 1024)
            
            return {
                'total_written': self.total_written,
                'available_samples': available,
                'buffer_usage': available / self.max_samples,
                'memory_mb': memory_mb,
                'write_index': self.write_index
            }
    
    def clear(self):
        """Clear the buffer."""
        with self.lock:
            self.write_index = 0
            self.total_written = 0


class HighPerformanceDataProcessor:
    """
    High-performance data processor using circular buffers and background processing.
    """
    
    def __init__(self, buffer_seconds: float = 30.0, max_channels: int = 16):
        """
        Initialize high-performance data processor.
        
        Args:
            buffer_seconds: Number of seconds of data to keep in memory
            max_channels: Maximum number of channels to support
        """
        self.buffer_seconds = buffer_seconds
        self.max_channels = max_channels
        self.sampling_rate = 1000.0  # Will be updated when data arrives
        
        # Calculate buffer size (assume 50kHz max)
        max_samples = int(buffer_seconds * 50000)  # Conservative estimate
        
        # Create circular buffer
        self.circular_buffer = CircularBuffer(max_samples, max_channels)
        
        # Processing state
        self.last_processing_time = 0.0
        self.processing_lock = threading.Lock()
        
        # Pre-allocate arrays for processing
        self._temp_arrays = {}
        self._initialize_temp_arrays(max_samples, max_channels)
    
    def _initialize_temp_arrays(self, max_samples: int, max_channels: int):
        """Pre-allocate temporary arrays to avoid allocation during processing."""
        fft_sizes = [256, 512, 1024, 2048, 4096, 8192]
        
        for fft_size in fft_sizes:
            self._temp_arrays[f'window_{fft_size}'] = np.hanning(fft_size)
            self._temp_arrays[f'fft_input_{fft_size}'] = np.zeros(fft_size, dtype=np.complex128)
    
    def add_data(self, timestamps: np.ndarray, data: np.ndarray, sampling_rate: float):
        """
        Add new data to the high-performance buffer.
        
        Args:
            timestamps: Time array in milliseconds
            data: Data array (N, C)
            sampling_rate: Current sampling rate in Hz
        """
        self.sampling_rate = sampling_rate
        self.circular_buffer.append(timestamps, data)
    
    def get_recent_data_for_plot(self, window_ms: float = 1000.0, 
                                max_plot_points: int = 2000) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get recent data optimized for plotting.
        
        Args:
            window_ms: Time window in milliseconds
            max_plot_points: Maximum points for smooth plotting
            
        Returns:
            (timestamps, data) downsampled for plotting
        """
        # Calculate samples needed
        window_samples = int(window_ms * self.sampling_rate / 1000.0)
        
        # Get data from circular buffer
        timestamps, data = self.circular_buffer.get_recent_data(window_samples)
        
        if len(timestamps) == 0:
            return timestamps, data
        
        # Downsample for plotting if needed
        if len(timestamps) > max_plot_points:
            step = len(timestamps) // max_plot_points
            timestamps = timestamps[::step]
            data = data[::step]
        
        return timestamps, data
    
    def compute_spectrum_fast(self, channel_idx: int = 0, fft_size: int = 8192,
                             window_type: str = "hanning") -> Tuple[np.ndarray, np.ndarray]:
        """
        Fast spectrum computation using pre-allocated buffers.
        
        Args:
            channel_idx: Channel index to process
            fft_size: FFT size (must be pre-allocated)
            window_type: Window function type
            
        Returns:
            (frequencies, power_spectrum)
        """
        # Get recent data
        timestamps, data = self.circular_buffer.get_recent_data(fft_size * 2)  # Get extra for windowing
        
        if len(timestamps) < fft_size or data.shape[1] <= channel_idx:
            freq = np.fft.rfftfreq(fft_size, 1.0 / self.sampling_rate)
            return freq, np.zeros(len(freq))
        
        # Use the most recent fft_size samples
        signal = data[-fft_size:, channel_idx]
        
        # Apply window (use pre-allocated)
        window_key = f'window_{fft_size}'
        if window_key in self._temp_arrays:
            window = self._temp_arrays[window_key]
        else:
            window = np.hanning(fft_size)  # Fallback
        
        windowed_signal = signal * window
        
        # Compute FFT
        fft_result = np.fft.rfft(windowed_signal)
        
        # Compute power spectrum
        power_spectrum = np.abs(fft_result) ** 2
        
        # Normalize
        power_spectrum = power_spectrum / (self.sampling_rate * np.sum(window**2))
        
        # Frequency array
        frequencies = np.fft.rfftfreq(fft_size, 1.0 / self.sampling_rate)
        
        return frequencies, power_spectrum
    
    def get_statistics_fast(self, channels: list) -> dict:
        """
        Fast statistics computation for specified channels.
        
        Args:
            channels: List of channel indices
            
        Returns:
            Dictionary with statistics for each channel
        """
        # Get all recent data once
        timestamps, data = self.circular_buffer.get_recent_data()
        
        if len(timestamps) == 0:
            return {}
        
        stats = {}
        for ch_idx in channels:
            if ch_idx < data.shape[1]:
                channel_data = data[:, ch_idx]
                stats[ch_idx] = {
                    'mean': float(np.mean(channel_data)),
                    'std': float(np.std(channel_data)),
                    'min': float(np.min(channel_data)),
                    'max': float(np.max(channel_data)),
                    'samples': len(channel_data)
                }
        
        return stats
    
    def get_buffer_info(self) -> dict:
        """Get information about buffer usage and performance."""
        return self.circular_buffer.get_statistics()
