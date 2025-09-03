"""
High-performance data streaming for real-time DAQ operations.
Handles continuous data streaming with minimal latency and maximum throughput.
"""

import time
import numpy as np
from PySide6 import QtCore
from typing import Optional, Callable, Dict, Any, List, Tuple
import threading
import queue
from dataclasses import dataclass
from collections import deque
import nidaqmx
from nidaqmx.constants import AcquisitionType, TerminalConfiguration


@dataclass
class StreamConfig:
    """Configuration for data streaming."""
    sampling_rate: float
    channels: List[str]
    samples_per_channel: int
    buffer_size: int = 10000
    timeout: float = 10.0
    terminal_config: TerminalConfiguration = TerminalConfiguration.RSE


@dataclass
class StreamData:
    """Data packet from streaming."""
    data: np.ndarray  # Shape: (samples, channels)
    timestamp: float
    sample_count: int
    channel_count: int
    sampling_rate: float
    buffer_health: float  # 0.0 to 1.0, buffer usage


class HighPerformanceStreamer(QtCore.QObject):
    """
    High-performance data streamer for continuous acquisition.
    
    Features:
    - Continuous streaming with minimal latency
    - Automatic buffer management
    - Real-time performance monitoring
    - Adaptive buffer sizing
    - Thread-safe operation
    """
    
    # Signals
    data_ready = QtCore.Signal(object)  # StreamData object
    error_occurred = QtCore.Signal(str)
    stream_started = QtCore.Signal()
    stream_stopped = QtCore.Signal()
    performance_update = QtCore.Signal(object)  # Performance stats
    
    def __init__(self):
        super().__init__()
        
        # DAQ task
        self.task = None
        self.is_streaming = False
        
        # Configuration
        self.config = None
        
        # Threading
        self.stream_thread = None
        self.stop_event = threading.Event()
        
        # Buffers and queues
        self.data_queue = queue.Queue(maxsize=50)  # Limit queue size
        self.read_buffer = None
        
        # Performance tracking
        self.samples_read = 0
        self.start_time = 0
        self.last_read_time = 0
        self.read_times = deque(maxlen=100)  # Last 100 read times
        self.dropped_packets = 0
        
        # Buffer management
        self.buffer_underruns = 0
        self.buffer_overruns = 0
        self.adaptive_buffer_size = 0
        
        # Callbacks
        self.data_callback = None
        
        # High-performance settings
        self.use_double_buffering = True
        self.pre_allocate_buffers = True
        self.optimize_for_speed = True
    
    def configure_stream(self, config: StreamConfig):
        """
        Configure the streaming parameters.
        
        Args:
            config: Stream configuration
        """
        self.config = config
        
        # Calculate optimal buffer sizes
        self._calculate_buffer_sizes()
        
        # Pre-allocate buffers if enabled
        if self.pre_allocate_buffers:
            self._allocate_buffers()
    
    def _calculate_buffer_sizes(self):
        """Calculate optimal buffer sizes for the stream."""
        if not self.config:
            return
        
        # More conservative buffer sizing for stability
        if self.config.sampling_rate >= 50000:
            # For 50kHz+, use 20ms buffers (was 50ms)
            buffer_samples = int(self.config.sampling_rate * 0.02)  # 20ms
        elif self.config.sampling_rate >= 25000:
            # For 25kHz+, use 15ms buffers
            buffer_samples = int(self.config.sampling_rate * 0.015)  # 15ms
        elif self.config.sampling_rate >= 10000:
            # For 10kHz+, use 10ms buffers (was 20ms)
            buffer_samples = int(self.config.sampling_rate * 0.01)  # 10ms
        else:
            # For lower rates, use 5ms buffers for responsiveness
            buffer_samples = int(self.config.sampling_rate * 0.005)  # 5ms
            buffer_samples = max(buffer_samples, 50)  # Minimum 50 samples
        
        # Ensure reasonable limits
        buffer_samples = max(buffer_samples, 50)    # Minimum
        buffer_samples = min(buffer_samples, 5000)  # Maximum for stability
        
        # Store calculated buffer size
        self.adaptive_buffer_size = buffer_samples
        
        # Update config
        self.config.samples_per_channel = buffer_samples
    
    def _allocate_buffers(self):
        """Pre-allocate buffers for high-performance operation."""
        if not self.config:
            return
        
        # Pre-allocate read buffer
        buffer_shape = (self.config.samples_per_channel, len(self.config.channels))
        self.read_buffer = np.zeros(buffer_shape, dtype=np.float64)
        
        # Pre-allocate additional buffers for double buffering
        if self.use_double_buffering:
            self.read_buffer_2 = np.zeros(buffer_shape, dtype=np.float64)
            self.current_buffer = 0
    
    def start_stream(self) -> bool:
        """
        Start the data stream.
        
        Returns:
            True if stream started successfully
        """
        if self.is_streaming:
            return False
        
        if not self.config:
            self.error_occurred.emit("Stream not configured")
            return False
        
        try:
            # Create DAQ task
            self.task = nidaqmx.Task()
            
            # Add analog input channels
            for channel in self.config.channels:
                self.task.ai_channels.add_ai_voltage_chan(
                    channel,
                    terminal_config=self.config.terminal_config,
                    min_val=-10.0,
                    max_val=10.0
                )
            
            # Configure timing
            self.task.timing.cfg_samp_clk_timing(
                rate=self.config.sampling_rate,
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=self.config.buffer_size
            )
            
            # Configure buffer size for high performance
            if self.optimize_for_speed:
                # Set buffer size to handle high rates
                buffer_size = max(self.config.buffer_size, self.adaptive_buffer_size * 4)
                self.task.in_stream.input_buf_size = buffer_size
            
            # Start the task
            self.task.start()
            
            # Reset performance counters
            self.samples_read = 0
            self.start_time = time.perf_counter()
            self.last_read_time = self.start_time
            self.read_times.clear()
            self.dropped_packets = 0
            self.buffer_underruns = 0
            self.buffer_overruns = 0
            
            # Start streaming thread
            self.stop_event.clear()
            self.is_streaming = True
            self.stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
            self.stream_thread.start()
            
            self.stream_started.emit()
            return True
            
        except ImportError as e:
            self.error_occurred.emit("NI-DAQmx not installed or not available")
            self._cleanup_task()
            return False
        except Exception as e:
            error_msg = str(e)
            if "device" in error_msg.lower():
                self.error_occurred.emit("DAQ device not found or not available")
            elif "channel" in error_msg.lower():
                self.error_occurred.emit("Invalid channel specification")
            elif "resource" in error_msg.lower():
                self.error_occurred.emit("DAQ resource not available")
            else:
                self.error_occurred.emit(f"High-performance streaming failed: {error_msg}")
            self._cleanup_task()
            return False
    
    def stop_stream(self):
        """Stop the data stream."""
        if not self.is_streaming:
            return
        
        # Signal stop
        self.stop_event.set()
        self.is_streaming = False
        
        # Wait for thread to finish
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=2.0)
        
        # Cleanup DAQ task
        self._cleanup_task()
        
        # Clear queue
        while not self.data_queue.empty():
            try:
                self.data_queue.get_nowait()
            except queue.Empty:
                break
        
        self.stream_stopped.emit()
    
    def _cleanup_task(self):
        """Clean up DAQ task."""
        if self.task:
            try:
                if self.task.is_task_done() is False:
                    self.task.stop()
                self.task.close()
            except:
                pass
            finally:
                self.task = None
    
    def _stream_loop(self):
        """Main streaming loop running in separate thread."""
        buffer_index = 0
        
        while not self.stop_event.is_set() and self.is_streaming:
            try:
                # Get current buffer for double buffering
                if self.use_double_buffering:
                    current_read_buffer = (self.read_buffer if buffer_index == 0 
                                         else self.read_buffer_2)
                    buffer_index = 1 - buffer_index
                else:
                    current_read_buffer = self.read_buffer
                
                # Read data from DAQ
                read_start = time.perf_counter()
                
                if current_read_buffer is not None:
                    # Read into pre-allocated buffer
                    samples_read = self.task.read(
                        number_of_samples_per_channel=self.config.samples_per_channel,
                        timeout=self.config.timeout
                    )
                    # Convert to numpy array if needed
                    if not isinstance(samples_read, np.ndarray):
                        data = np.array(samples_read).T  # Transpose to (samples, channels)
                    else:
                        data = samples_read.T
                else:
                    # Fallback without pre-allocated buffer
                    samples_read = self.task.read(
                        number_of_samples_per_channel=self.config.samples_per_channel,
                        timeout=self.config.timeout
                    )
                    data = np.array(samples_read).T
                
                read_end = time.perf_counter()
                read_time = read_end - read_start
                
                # Track performance
                self.read_times.append(read_time)
                self.samples_read += data.shape[0]
                
                # Calculate buffer health
                available_samples = self.task.in_stream.avail_samp_per_chan
                buffer_size = self.task.in_stream.input_buf_size
                buffer_health = 1.0 - (available_samples / max(buffer_size, 1))
                
                # Check for buffer issues
                if buffer_health > 0.9:
                    self.buffer_overruns += 1
                elif buffer_health < 0.1:
                    self.buffer_underruns += 1
                
                # Create stream data packet
                stream_data = StreamData(
                    data=data.copy(),  # Copy to avoid buffer reuse issues
                    timestamp=read_end,
                    sample_count=data.shape[0],
                    channel_count=data.shape[1],
                    sampling_rate=self.config.sampling_rate,
                    buffer_health=buffer_health
                )
                
                # Queue data for processing
                try:
                    self.data_queue.put_nowait(stream_data)
                except queue.Full:
                    # Queue is full, drop oldest data
                    try:
                        self.data_queue.get_nowait()
                        self.dropped_packets += 1
                        self.data_queue.put_nowait(stream_data)
                    except queue.Empty:
                        pass
                
                # Emit data signal
                self.data_ready.emit(stream_data)
                
                # Call callback if set
                if self.data_callback:
                    self.data_callback(stream_data)
                
                # Update performance stats periodically
                if self.samples_read % (self.config.sampling_rate * 2) == 0:  # Every 2 seconds
                    self._emit_performance_stats()
                
                self.last_read_time = read_end
                
                # Add small adaptive delay for system stability
                # Calculate target delay based on buffer health and sampling rate
                if buffer_health > 0.8:
                    # System is stressed, add more delay
                    delay = 0.001  # 1ms
                elif buffer_health < 0.2:
                    # System is keeping up well, minimal delay
                    delay = 0.0001  # 0.1ms
                else:
                    # Normal operation
                    delay = 0.0005  # 0.5ms
                
                time.sleep(delay)
                
            except Exception as e:
                if self.is_streaming:  # Only emit error if we're still supposed to be streaming
                    self.error_occurred.emit(f"Streaming error: {str(e)}")
                break
    
    def _emit_performance_stats(self):
        """Emit performance statistics."""
        current_time = time.perf_counter()
        elapsed_time = current_time - self.start_time
        
        if elapsed_time > 0:
            actual_rate = self.samples_read / elapsed_time
            rate_accuracy = actual_rate / self.config.sampling_rate * 100
        else:
            actual_rate = 0
            rate_accuracy = 0
        
        if self.read_times:
            avg_read_time = np.mean(list(self.read_times))
            max_read_time = np.max(list(self.read_times))
            read_frequency = 1.0 / avg_read_time if avg_read_time > 0 else 0
        else:
            avg_read_time = 0
            max_read_time = 0
            read_frequency = 0
        
        # Calculate buffer statistics
        if self.task and self.task.in_stream:
            try:
                available_samples = self.task.in_stream.avail_samp_per_chan
                buffer_size = self.task.in_stream.input_buf_size
                buffer_usage = available_samples / max(buffer_size, 1) * 100
            except:
                buffer_usage = 0
        else:
            buffer_usage = 0
        
        stats = {
            'elapsed_time': elapsed_time,
            'samples_read': self.samples_read,
            'actual_rate': actual_rate,
            'target_rate': self.config.sampling_rate,
            'rate_accuracy_percent': rate_accuracy,
            'avg_read_time_ms': avg_read_time * 1000,
            'max_read_time_ms': max_read_time * 1000,
            'read_frequency': read_frequency,
            'dropped_packets': self.dropped_packets,
            'buffer_underruns': self.buffer_underruns,
            'buffer_overruns': self.buffer_overruns,
            'buffer_usage_percent': buffer_usage,
            'queue_size': self.data_queue.qsize()
        }
        
        self.performance_update.emit(stats)
    
    def get_queued_data(self) -> Optional[StreamData]:
        """
        Get the next data packet from the queue.
        
        Returns:
            StreamData object or None if queue is empty
        """
        try:
            return self.data_queue.get_nowait()
        except queue.Empty:
            return None
    
    def get_all_queued_data(self) -> List[StreamData]:
        """
        Get all queued data packets.
        
        Returns:
            List of StreamData objects
        """
        data_packets = []
        while True:
            try:
                data_packets.append(self.data_queue.get_nowait())
            except queue.Empty:
                break
        return data_packets
    
    def set_data_callback(self, callback: Callable[[StreamData], None]):
        """
        Set a callback function for new data.
        
        Args:
            callback: Function to call with new StreamData
        """
        self.data_callback = callback
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        self._emit_performance_stats()
        
        current_time = time.perf_counter()
        elapsed_time = current_time - self.start_time
        
        if elapsed_time > 0:
            actual_rate = self.samples_read / elapsed_time
        else:
            actual_rate = 0
        
        return {
            'is_streaming': self.is_streaming,
            'elapsed_time': elapsed_time,
            'samples_read': self.samples_read,
            'actual_rate': actual_rate,
            'target_rate': self.config.sampling_rate if self.config else 0,
            'dropped_packets': self.dropped_packets,
            'buffer_underruns': self.buffer_underruns,
            'buffer_overruns': self.buffer_overruns,
            'queue_size': self.data_queue.qsize(),
            'adaptive_buffer_size': self.adaptive_buffer_size
        }
    
    def optimize_for_rate(self, target_rate: float):
        """
        Optimize streaming parameters for a specific sample rate.
        
        Args:
            target_rate: Target sampling rate in Hz
        """
        if target_rate >= 50000:
            # Ultra-high rate optimization
            self.use_double_buffering = True
            self.pre_allocate_buffers = True
            self.optimize_for_speed = True
            
            # Larger buffers for stability
            self.adaptive_buffer_size = int(target_rate * 0.1)  # 100ms
            
            # Increase queue size
            self.data_queue = queue.Queue(maxsize=100)
            
        elif target_rate >= 10000:
            # High rate optimization  
            self.use_double_buffering = True
            self.pre_allocate_buffers = True
            self.optimize_for_speed = True
            
            # Medium buffers
            self.adaptive_buffer_size = int(target_rate * 0.05)  # 50ms
            
        else:
            # Standard optimization
            self.use_double_buffering = False
            self.pre_allocate_buffers = True
            self.optimize_for_speed = False
            
            # Small buffers for low latency
            self.adaptive_buffer_size = int(target_rate * 0.01)  # 10ms
