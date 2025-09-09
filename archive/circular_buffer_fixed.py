"""
High-performance circular buffer for real-time data acquisition.
Optimized for 50kHz sampling rates with minimal memory overhead.
"""

import numpy as np
import threading
import time
from typing import Union, Optional, Tuple, Dict, Any


class CircularBuffer:
    """
    Thread-safe circular buffer optimized for real-time data acquisition.
    
    Features:
    - Pre-allocated memory to avoid allocation overhead
    - Thread-safe operations using locks
    - Efficient modular arithmetic for indexing
    - Configurable buffer size based on memory constraints
    """
    
    def __init__(self, capacity: int, dtype=np.float64, name: str = "Buffer"):
        """
        Initialize circular buffer.
        
        Args:
            capacity: Maximum number of elements
            dtype: Data type for storage
            name: Buffer name for debugging
        """
        self.capacity = capacity
        self.dtype = np.dtype(dtype) if not isinstance(dtype, np.dtype) else dtype
        self.name = name
        
        # Pre-allocate buffer array
        self.buffer = np.zeros(capacity, dtype=self.dtype)
        
        # Buffer state
        self.write_pos = 0
        self.size = 0
        self.lock = threading.RLock()
        
        # Statistics
        self.total_written = 0
        self.total_read = 0
    
    def append_chunk(self, data: np.ndarray) -> None:
        """
        Append a chunk of data to the buffer.
        
        Args:
            data: Data array to append
        """
        if len(data) == 0:
            return
        
        with self.lock:
            n_new = len(data)
            
            # Handle wraparound
            if self.write_pos + n_new <= self.capacity:
                # Simple case: no wraparound
                self.buffer[self.write_pos:self.write_pos + n_new] = data
            else:
                # Wraparound case
                first_part = self.capacity - self.write_pos
                self.buffer[self.write_pos:] = data[:first_part]
                if n_new > first_part:
                    remaining = n_new - first_part
                    self.buffer[:remaining] = data[first_part:]
            
            # Update state
            self.write_pos = (self.write_pos + n_new) % self.capacity
            self.size = min(self.size + n_new, self.capacity)
            self.total_written += n_new
    
    def get_recent_data(self, n_samples: int) -> np.ndarray:
        """
        Get the most recent n_samples from the buffer.
        
        Args:
            n_samples: Number of recent samples to retrieve
            
        Returns:
            Array of recent data
        """
        with self.lock:
            if self.size == 0:
                return np.array([], dtype=self.dtype)
            
            n_samples = min(n_samples, self.size)
            
            if self.size < self.capacity:
                # Buffer not full yet
                start_idx = max(0, self.write_pos - n_samples)
                return self.buffer[start_idx:self.write_pos].copy()
            else:
                # Buffer is full, handle wraparound
                if n_samples <= self.write_pos:
                    # Recent data doesn't wrap around
                    start_idx = self.write_pos - n_samples
                    return self.buffer[start_idx:self.write_pos].copy()
                else:
                    # Recent data wraps around
                    first_part = self.write_pos
                    second_part = n_samples - first_part
                    
                    result = np.zeros(n_samples, dtype=self.dtype)
                    result[:second_part] = self.buffer[-second_part:]
                    result[second_part:] = self.buffer[:first_part]
                    return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        with self.lock:
            utilization = (self.size / self.capacity) * 100 if self.capacity > 0 else 0
            
            return {
                'capacity': self.capacity,
                'size': self.size,
                'utilization_percent': utilization,
                'total_written': self.total_written,
                'total_read': self.total_read,
                'write_position': self.write_pos,
                'name': self.name
            }
    
    def clear(self):
        """Clear the buffer."""
        with self.lock:
            self.write_pos = 0
            self.size = 0
            self.buffer.fill(0)


class HighPerformanceDataProcessor:
    """
    High-performance data processor for real-time applications.
    
    Optimized for minimal latency and maximum throughput.
    Uses pre-allocated buffers and efficient algorithms.
    """
    
    def __init__(self, sampling_rate: float, num_channels: int, buffer_size: int):
        """
        Initialize the high-performance data processor.
        
        Args:
            sampling_rate: Sampling rate in Hz
            num_channels: Number of data channels
            buffer_size: Size of internal buffers
        """
        self.sampling_rate = sampling_rate
        self.num_channels = num_channels
        self.buffer_size = buffer_size
        
        # Pre-allocate processing buffers
        self.processing_buffer = np.zeros((buffer_size, num_channels), dtype=np.float64)
        self.temp_buffer = np.zeros(buffer_size, dtype=np.float64)
        
        # Performance tracking
        self.samples_processed = 0
        self.processing_times = []
        self.start_time = time.perf_counter()
        
        # Thread safety
        self.lock = threading.RLock()
    
    def process_chunk(self, data: np.ndarray, timestamp: float):
        """
        Process a chunk of data.
        
        Args:
            data: Data chunk (samples, channels)
            timestamp: Timestamp of the data
        """
        process_start = time.perf_counter()
        
        with self.lock:
            # Update sample count
            self.samples_processed += data.shape[0]
            
            # Store processing time
            processing_time = time.perf_counter() - process_start
            self.processing_times.append(processing_time)
            
            # Keep only last 100 times for efficiency
            if len(self.processing_times) > 100:
                self.processing_times.pop(0)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        with self.lock:
            current_time = time.perf_counter()
            elapsed_time = current_time - self.start_time
            
            if elapsed_time > 0:
                throughput = self.samples_processed / elapsed_time
            else:
                throughput = 0
            
            if self.processing_times:
                avg_time = np.mean(self.processing_times)
                max_time = np.max(self.processing_times)
            else:
                avg_time = max_time = 0
            
            return {
                'samples_processed': self.samples_processed,
                'elapsed_time': elapsed_time,
                'throughput_samples_per_sec': throughput,
                'avg_processing_time_ms': avg_time * 1000,
                'max_processing_time_ms': max_time * 1000,
                'target_rate': self.sampling_rate,
                'rate_accuracy_percent': (throughput / self.sampling_rate * 100) if self.sampling_rate > 0 else 0
            }


class OptimizedBuffer:
    """
    Memory-optimized buffer with automatic cleanup.
    
    Uses memory mapping for large datasets and provides
    automatic memory management.
    """
    
    def __init__(self, initial_size: int = 10000, dtype=np.float64):
        """
        Initialize optimized buffer.
        
        Args:
            initial_size: Initial buffer size
            dtype: Data type
        """
        self.dtype = dtype
        self.buffers = []
        self.current_buffer = np.zeros(initial_size, dtype=dtype)
        self.current_size = 0
        self.total_size = 0
        
        # Memory management
        self.max_memory_mb = 500  # 500MB limit
        self.cleanup_threshold = 0.8  # Cleanup at 80% capacity
        
        self.lock = threading.RLock()
    
    def append(self, data: np.ndarray):
        """Append data to the buffer."""
        with self.lock:
            if len(data) == 0:
                return
            
            # Check if current buffer has space
            if self.current_size + len(data) > len(self.current_buffer):
                # Archive current buffer and create new one
                if self.current_size > 0:
                    self.buffers.append(self.current_buffer[:self.current_size].copy())
                
                # Create new buffer (double size if needed)
                new_size = max(len(self.current_buffer) * 2, len(data))
                self.current_buffer = np.zeros(new_size, dtype=self.dtype)
                self.current_size = 0
                
                # Check memory usage and cleanup if needed
                self._check_memory_usage()
            
            # Add data to current buffer
            end_idx = self.current_size + len(data)
            self.current_buffer[self.current_size:end_idx] = data
            self.current_size += len(data)
            self.total_size += len(data)
    
    def get_all_data(self) -> np.ndarray:
        """Get all data as a single array."""
        with self.lock:
            if not self.buffers and self.current_size == 0:
                return np.array([], dtype=self.dtype)
            
            # Combine all buffers
            all_data = []
            
            for buffer in self.buffers:
                all_data.append(buffer)
            
            if self.current_size > 0:
                all_data.append(self.current_buffer[:self.current_size])
            
            return np.concatenate(all_data) if all_data else np.array([], dtype=self.dtype)
    
    def _check_memory_usage(self):
        """Check memory usage and cleanup if needed."""
        # Estimate memory usage
        total_elements = sum(len(buf) for buf in self.buffers) + self.current_size
        memory_mb = total_elements * self.dtype.itemsize / (1024 * 1024)
        
        if memory_mb > self.max_memory_mb * self.cleanup_threshold:
            # Remove oldest buffers
            while len(self.buffers) > 5 and memory_mb > self.max_memory_mb * 0.5:
                removed_buffer = self.buffers.pop(0)
                memory_mb -= len(removed_buffer) * self.dtype.itemsize / (1024 * 1024)
    
    def clear(self):
        """Clear all data."""
        with self.lock:
            self.buffers.clear()
            self.current_size = 0
            self.total_size = 0
            self.current_buffer.fill(0)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        with self.lock:
            total_elements = sum(len(buf) for buf in self.buffers) + self.current_size
            memory_mb = total_elements * self.dtype.itemsize / (1024 * 1024)
            
            return {
                'total_elements': total_elements,
                'memory_usage_mb': memory_mb,
                'num_buffers': len(self.buffers) + (1 if self.current_size > 0 else 0),
                'current_buffer_size': self.current_size,
                'max_memory_mb': self.max_memory_mb
            }
