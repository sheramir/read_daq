"""
Background processing worker for high-performance data acquisition.
Handles data processing in separate thread to avoid blocking GUI.
"""

import time
import numpy as np
from PySide6 import QtCore
from typing import Optional, Dict, Any
import threading
import queue
from dataclasses import dataclass


@dataclass
class ProcessingRequest:
    """Request for background processing."""
    request_type: str  # 'spectrum', 'statistics', 'filter'
    data: Any
    params: Dict[str, Any]
    timestamp: float


@dataclass 
class ProcessingResult:
    """Result from background processing."""
    request_type: str
    result: Any
    processing_time: float
    timestamp: float


class BackgroundProcessor(QtCore.QThread):
    """
    Background processing thread for computationally expensive operations.
    
    This thread handles:
    - FFT spectrum computation
    - Digital filtering
    - Statistical calculations
    - Data analysis
    
    All heavy processing is moved off the GUI thread for better responsiveness.
    """
    
    # Signals for results
    spectrum_ready = QtCore.Signal(object)  # (frequencies, spectrum, channel_idx)
    statistics_ready = QtCore.Signal(object)  # {channel: stats}
    filter_ready = QtCore.Signal(object)  # (filtered_data, channel_idx)
    processing_stats = QtCore.Signal(object)  # Performance statistics
    
    def __init__(self):
        super().__init__()
        
        # Processing queue
        self.request_queue = queue.Queue(maxsize=100)  # Limit queue size to prevent memory buildup
        
        # Control flags
        self.running = False
        self.processing_enabled = True
        
        # Performance tracking
        self.processing_times = []
        self.processed_requests = 0
        self.dropped_requests = 0
        
        # Pre-allocate common arrays
        self.fft_windows = {}
        self._initialize_windows()
    
    def _initialize_windows(self):
        """Pre-allocate window functions for different FFT sizes."""
        fft_sizes = [256, 512, 1024, 2048, 4096, 8192, 16384]
        
        for size in fft_sizes:
            self.fft_windows[size] = {
                'hanning': np.hanning(size),
                'hamming': np.hamming(size), 
                'blackman': np.blackman(size),
                'rectangle': np.ones(size)
            }
    
    def start_processing(self):
        """Start the background processing thread."""
        self.running = True
        self.start()
    
    def stop_processing(self):
        """Stop the background processing thread."""
        self.running = False
        
        # Clear the queue
        while not self.request_queue.empty():
            try:
                self.request_queue.get_nowait()
            except queue.Empty:
                break
        
        # Wait for thread to finish
        if self.isRunning():
            self.wait(1000)  # 1 second timeout (in milliseconds)
    
    def request_spectrum(self, data: np.ndarray, channel_idx: int, 
                        sampling_rate: float, fft_size: int = 8192,
                        window_type: str = "hanning", max_freq: float = None):
        """
        Request spectrum computation in background.
        
        Args:
            data: Signal data for the channel
            channel_idx: Channel index
            sampling_rate: Sampling rate in Hz
            fft_size: FFT size
            window_type: Window function type
            max_freq: Maximum frequency to include
        """
        request = ProcessingRequest(
            request_type='spectrum',
            data=data.copy(),  # Copy to avoid race conditions
            params={
                'channel_idx': channel_idx,
                'sampling_rate': sampling_rate,
                'fft_size': fft_size,
                'window_type': window_type,
                'max_freq': max_freq
            },
            timestamp=time.perf_counter()
        )
        
        self._submit_request(request)
    
    def request_statistics(self, data: np.ndarray, channels: list):
        """
        Request statistics computation in background.
        
        Args:
            data: Data array (N, C)
            channels: List of channel indices to process
        """
        request = ProcessingRequest(
            request_type='statistics',
            data=data.copy(),
            params={'channels': channels},
            timestamp=time.perf_counter()
        )
        
        self._submit_request(request)
    
    def request_filter(self, data: np.ndarray, channel_idx: int,
                      filter_type: str, params: dict):
        """
        Request digital filtering in background.
        
        Args:
            data: Signal data
            channel_idx: Channel index
            filter_type: Type of filter ('lowpass', 'highpass', etc.)
            params: Filter parameters
        """
        request = ProcessingRequest(
            request_type='filter',
            data=data.copy(),
            params={
                'channel_idx': channel_idx,
                'filter_type': filter_type,
                **params
            },
            timestamp=time.perf_counter()
        )
        
        self._submit_request(request)
    
    def _submit_request(self, request: ProcessingRequest):
        """Submit a processing request to the queue."""
        if not self.processing_enabled:
            return
        
        try:
            # Try to add request, drop oldest if queue is full
            self.request_queue.put_nowait(request)
        except queue.Full:
            # Queue is full, drop oldest request
            try:
                self.request_queue.get_nowait()
                self.dropped_requests += 1
                self.request_queue.put_nowait(request)
            except queue.Empty:
                pass
    
    def run(self):
        """Main processing loop."""
        while self.running:
            try:
                # Get request with timeout
                request = self.request_queue.get(timeout=0.1)
                
                # Process the request
                start_time = time.perf_counter()
                self._process_request(request)
                processing_time = time.perf_counter() - start_time
                
                # Track performance
                self.processing_times.append(processing_time)
                if len(self.processing_times) > 100:  # Keep last 100 times
                    self.processing_times.pop(0)
                
                self.processed_requests += 1
                
                # Emit performance stats periodically
                if self.processed_requests % 50 == 0:
                    self._emit_performance_stats()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Background processing error: {e}")
    
    def _process_request(self, request: ProcessingRequest):
        """Process a single request."""
        if request.request_type == 'spectrum':
            self._process_spectrum(request)
        elif request.request_type == 'statistics':
            self._process_statistics(request)
        elif request.request_type == 'filter':
            self._process_filter(request)
    
    def _process_spectrum(self, request: ProcessingRequest):
        """Process spectrum computation request."""
        data = request.data
        params = request.params
        
        channel_idx = params['channel_idx']
        sampling_rate = params['sampling_rate']
        fft_size = params.get('fft_size', 8192)
        window_type = params.get('window_type', 'hanning')
        max_freq = params.get('max_freq', None)
        
        if len(data) < fft_size:
            # Not enough data for FFT
            freq = np.fft.rfftfreq(fft_size, 1.0 / sampling_rate)
            spectrum = np.zeros(len(freq))
        else:
            # Use most recent data
            signal = data[-fft_size:]
            
            # Apply window
            if fft_size in self.fft_windows and window_type in self.fft_windows[fft_size]:
                window = self.fft_windows[fft_size][window_type]
            else:
                # Fallback to hanning
                window = np.hanning(fft_size)
            
            windowed_signal = signal * window
            
            # Compute FFT
            fft_result = np.fft.rfft(windowed_signal)
            
            # Compute power spectrum
            spectrum = np.abs(fft_result) ** 2
            
            # Normalize
            spectrum = spectrum / (sampling_rate * np.sum(window**2))
            
            # Convert to dB
            spectrum = 10 * np.log10(spectrum + 1e-12)  # Add small value to avoid log(0)
            
            # Frequency array
            freq = np.fft.rfftfreq(fft_size, 1.0 / sampling_rate)
            
            # Limit frequency range if requested
            if max_freq is not None:
                mask = freq <= max_freq
                freq = freq[mask]
                spectrum = spectrum[mask]
        
        # Emit result
        result = {
            'frequencies': freq,
            'spectrum': spectrum,
            'channel_idx': channel_idx,
            'fft_size': fft_size,
            'window_type': window_type
        }
        
        self.spectrum_ready.emit(result)
    
    def _process_statistics(self, request: ProcessingRequest):
        """Process statistics computation request."""
        data = request.data  # Shape: (N, C)
        channels = request.params['channels']
        
        if len(data) == 0:
            self.statistics_ready.emit({})
            return
        
        stats = {}
        for ch_idx in channels:
            if ch_idx < data.shape[1]:
                channel_data = data[:, ch_idx]
                stats[ch_idx] = {
                    'mean': float(np.mean(channel_data)),
                    'std': float(np.std(channel_data)),
                    'min': float(np.min(channel_data)),
                    'max': float(np.max(channel_data)),
                    'rms': float(np.sqrt(np.mean(channel_data**2))),
                    'samples': len(channel_data)
                }
        
        self.statistics_ready.emit(stats)
    
    def _process_filter(self, request: ProcessingRequest):
        """Process digital filtering request."""
        # This would implement various digital filters
        # For now, just pass through the data
        data = request.data
        channel_idx = request.params['channel_idx']
        
        # Placeholder for actual filtering
        filtered_data = data  # Would apply actual filter here
        
        result = {
            'data': filtered_data,
            'channel_idx': channel_idx
        }
        
        self.filter_ready.emit(result)
    
    def _emit_performance_stats(self):
        """Emit performance statistics."""
        if not self.processing_times:
            return
        
        avg_time = np.mean(self.processing_times)
        max_time = np.max(self.processing_times)
        
        stats = {
            'processed_requests': self.processed_requests,
            'dropped_requests': self.dropped_requests,
            'avg_processing_time_ms': avg_time * 1000,
            'max_processing_time_ms': max_time * 1000,
            'queue_size': self.request_queue.qsize(),
            'drop_rate': self.dropped_requests / max(1, self.processed_requests + self.dropped_requests)
        }
        
        self.processing_stats.emit(stats)
    
    def get_performance_info(self) -> dict:
        """Get current performance information."""
        if not self.processing_times:
            return {
                'processed_requests': self.processed_requests,
                'dropped_requests': self.dropped_requests,
                'queue_size': self.request_queue.qsize()
            }
        
        return {
            'processed_requests': self.processed_requests,
            'dropped_requests': self.dropped_requests,
            'avg_processing_time_ms': np.mean(self.processing_times) * 1000,
            'max_processing_time_ms': np.max(self.processing_times) * 1000,
            'queue_size': self.request_queue.qsize(),
            'drop_rate': self.dropped_requests / max(1, self.processed_requests + self.dropped_requests)
        }
    
    def clear_performance_stats(self):
        """Clear performance statistics."""
        self.processing_times.clear()
        self.processed_requests = 0
        self.dropped_requests = 0
