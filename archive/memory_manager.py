"""
Memory manager for high-performance data acquisition.
Handles memory allocation, monitoring, and optimization for large datasets.
"""

import time
import numpy as np
import psutil
import os
import mmap
import tempfile
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
import weakref
import gc
import threading


@dataclass
class MemoryInfo:
    """Memory usage information."""
    total_mb: float
    available_mb: float
    used_mb: float
    used_percent: float
    process_mb: float
    
    def __str__(self):
        return (f"Memory: {self.used_mb:.1f}/{self.total_mb:.1f} MB "
                f"({self.used_percent:.1f}%) - Process: {self.process_mb:.1f} MB")


class MemoryMappedArray:
    """
    Memory-mapped array for large datasets.
    
    Uses memory mapping to handle datasets larger than available RAM.
    Automatically manages disk-based storage for large arrays.
    """
    
    def __init__(self, shape: Tuple[int, ...], dtype: np.dtype, 
                 temp_dir: Optional[str] = None):
        self.shape = shape
        self.dtype = dtype
        self.size = np.prod(shape) * np.dtype(dtype).itemsize
        
        # Create temporary file for memory mapping
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.temp_file = tempfile.NamedTemporaryFile(
            dir=self.temp_dir, 
            delete=False,
            prefix='daq_mmap_',
            suffix='.dat'
        )
        
        # Resize file to needed size
        self.temp_file.seek(self.size - 1)
        self.temp_file.write(b'\0')
        self.temp_file.flush()
        
        # Create memory map
        self.mmap = mmap.mmap(
            self.temp_file.fileno(),
            self.size,
            access=mmap.ACCESS_WRITE
        )
        
        # Create numpy array view
        self.array = np.frombuffer(self.mmap, dtype=dtype).reshape(shape)
        
        # Track for cleanup
        self._cleanup_registered = False
        self._register_cleanup()
    
    def _register_cleanup(self):
        """Register cleanup function."""
        if not self._cleanup_registered:
            weakref.finalize(self, self._cleanup, 
                           self.mmap, self.temp_file.name)
            self._cleanup_registered = True
    
    @staticmethod
    def _cleanup(mmap_obj, temp_filename):
        """Cleanup memory map and temporary file."""
        try:
            if mmap_obj:
                mmap_obj.close()
        except:
            pass
        
        try:
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)
        except:
            pass
    
    def close(self):
        """Explicitly close and cleanup."""
        if hasattr(self, 'mmap') and self.mmap:
            self.mmap.close()
            self.mmap = None
        
        if hasattr(self, 'temp_file') and self.temp_file:
            temp_filename = self.temp_file.name
            self.temp_file.close()
            
            try:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
            except:
                pass
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()


class MemoryPool:
    """
    Memory pool for reusing arrays.
    
    Reduces allocation/deallocation overhead by reusing arrays
    of common sizes and types.
    """
    
    def __init__(self, max_size_mb: float = 100):
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.pools = {}  # (shape, dtype) -> list of arrays
        self.current_size = 0
        self.lock = threading.RLock()
        
        # Track allocations
        self.allocated_arrays = weakref.WeakSet()
        self.total_allocations = 0
        self.pool_hits = 0
    
    def get_array(self, shape: Tuple[int, ...], dtype: np.dtype) -> np.ndarray:
        """
        Get an array from the pool or allocate a new one.
        
        Args:
            shape: Array shape
            dtype: Array data type
            
        Returns:
            Numpy array
        """
        with self.lock:
            # Use string representation for key to avoid hashing issues
            key = (str(shape), str(dtype))
            
            if key in self.pools and self.pools[key]:
                # Reuse from pool
                array = self.pools[key].pop()
                array.fill(0)  # Clear data
                self.pool_hits += 1
                return array
            
            # Allocate new array
            try:
                array = np.zeros(shape, dtype=dtype)
                # Don't add to WeakSet as numpy arrays are not hashable
                # self.allocated_arrays.add(array)  # Removed this line
                self.total_allocations += 1
                return array
            except MemoryError:
                # Try to free some memory and retry
                self._cleanup_pools()
                gc.collect()
                array = np.zeros(shape, dtype=dtype)
                # self.allocated_arrays.add(array)  # Removed this line
                self.total_allocations += 1
                return array
    
    def return_array(self, array: np.ndarray):
        """
        Return an array to the pool for reuse.
        
        Args:
            array: Array to return to pool
        """
        with self.lock:
            shape = array.shape
            dtype = array.dtype
            array_size = array.nbytes
            
            # Check if we have room in the pool
            if self.current_size + array_size > self.max_size_bytes:
                self._cleanup_pools()
            
            if self.current_size + array_size <= self.max_size_bytes:
                # Use string representation for key
                key = (str(shape), str(dtype))
                if key not in self.pools:
                    self.pools[key] = []
                
                self.pools[key].append(array)
                self.current_size += array_size
    
    def _cleanup_pools(self):
        """Clean up pools to free memory."""
        # Remove half of the cached arrays
        with self.lock:
            for key in list(self.pools.keys()):
                arrays = self.pools[key]
                remove_count = len(arrays) // 2
                
                for _ in range(remove_count):
                    if arrays:
                        array = arrays.pop()
                        self.current_size -= array.nbytes
                
                if not arrays:
                    del self.pools[key]
    
    def clear(self):
        """Clear all pools."""
        with self.lock:
            self.pools.clear()
            self.current_size = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self.lock:
            total_arrays = sum(len(arrays) for arrays in self.pools.values())
            hit_rate = self.pool_hits / max(1, self.total_allocations) * 100
            
            return {
                'total_arrays_pooled': total_arrays,
                'pool_size_mb': self.current_size / (1024 * 1024),
                'max_size_mb': self.max_size_bytes / (1024 * 1024),
                'total_allocations': self.total_allocations,
                'pool_hits': self.pool_hits,
                'hit_rate_percent': hit_rate,
                'active_arrays': 0  # Cannot track due to numpy array hashing issues
            }


class MemoryManager:
    """
    Comprehensive memory manager for DAQ applications.
    
    Features:
    - Memory usage monitoring
    - Automatic memory cleanup
    - Memory-mapped arrays for large datasets
    - Array pooling for performance
    - Memory pressure detection
    """
    
    def __init__(self, max_memory_mb: float = 1000, 
                 pool_size_mb: float = 100):
        self.max_memory_bytes = int(max_memory_mb * 1024 * 1024)
        self.warning_threshold = 0.8  # Warn at 80% usage
        self.critical_threshold = 0.9  # Critical at 90% usage
        
        # Memory pool for array reuse
        self.pool = MemoryPool(pool_size_mb)
        
        # Memory-mapped arrays
        self.mmapped_arrays = []
        
        # Monitoring
        self.memory_samples = []
        self.last_cleanup = time.time()
        self.cleanup_interval = 30.0  # seconds
        
        # Callbacks for memory events
        self.warning_callback = None
        self.critical_callback = None
        
        # Lock for thread safety
        self.lock = threading.RLock()
    
    def get_memory_info(self) -> MemoryInfo:
        """Get current memory usage information."""
        # System memory
        memory = psutil.virtual_memory()
        
        # Process memory
        process = psutil.Process()
        process_memory = process.memory_info()
        
        return MemoryInfo(
            total_mb=memory.total / (1024 * 1024),
            available_mb=memory.available / (1024 * 1024),
            used_mb=memory.used / (1024 * 1024),
            used_percent=memory.percent,
            process_mb=process_memory.rss / (1024 * 1024)
        )
    
    def monitor_memory(self):
        """Monitor memory usage and trigger cleanup if needed."""
        info = self.get_memory_info()
        
        # Store sample for history
        self.memory_samples.append({
            'timestamp': time.time(),
            'info': info
        })
        
        # Keep only last 100 samples
        if len(self.memory_samples) > 100:
            self.memory_samples.pop(0)
        
        # Check thresholds
        if info.process_mb > self.max_memory_bytes / (1024 * 1024):
            if info.process_mb > self.max_memory_bytes * self.critical_threshold / (1024 * 1024):
                self._handle_critical_memory()
            elif info.process_mb > self.max_memory_bytes * self.warning_threshold / (1024 * 1024):
                self._handle_warning_memory()
        
        # Periodic cleanup
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            self.cleanup_memory()
            self.last_cleanup = current_time
    
    def _handle_warning_memory(self):
        """Handle memory warning condition."""
        if self.warning_callback:
            self.warning_callback(self.get_memory_info())
        
        # Light cleanup
        self.pool._cleanup_pools()
    
    def _handle_critical_memory(self):
        """Handle critical memory condition."""
        if self.critical_callback:
            self.critical_callback(self.get_memory_info())
        
        # Aggressive cleanup
        self.cleanup_memory()
        gc.collect()
    
    def allocate_array(self, shape: Tuple[int, ...], dtype: np.dtype,
                      use_mmap: bool = None) -> np.ndarray:
        """
        Allocate an array with automatic memory management.
        
        Args:
            shape: Array shape
            dtype: Array data type  
            use_mmap: Force memory mapping (None = auto-decide)
            
        Returns:
            Numpy array (regular or memory-mapped)
        """
        array_size = np.prod(shape) * np.dtype(dtype).itemsize
        
        # Auto-decide memory mapping for large arrays
        if use_mmap is None:
            use_mmap = array_size > 100 * 1024 * 1024  # > 100MB
        
        if use_mmap:
            # Use memory-mapped array
            mmap_array = MemoryMappedArray(shape, dtype)
            with self.lock:
                self.mmapped_arrays.append(mmap_array)
            return mmap_array.array
        else:
            # Use memory pool
            return self.pool.get_array(shape, dtype)
    
    def return_array(self, array: np.ndarray):
        """
        Return an array to the pool for reuse.
        
        Args:
            array: Array to return
        """
        # Check if it's a memory-mapped array
        is_mmapped = False
        with self.lock:
            for mmap_array in self.mmapped_arrays:
                if mmap_array.array is array:
                    is_mmapped = True
                    break
        
        if not is_mmapped:
            # Return to regular pool
            self.pool.return_array(array)
    
    def cleanup_memory(self):
        """Perform memory cleanup."""
        with self.lock:
            # Clean up memory pools
            self.pool._cleanup_pools()
            
            # Clean up unused memory-mapped arrays
            active_mmaped = []
            for mmap_array in self.mmapped_arrays:
                try:
                    # Check if array is still referenced
                    if mmap_array.array is not None:
                        active_mmaped.append(mmap_array)
                    else:
                        mmap_array.close()
                except:
                    mmap_array.close()
            
            self.mmapped_arrays = active_mmaped
        
        # Force garbage collection
        gc.collect()
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics."""
        info = self.get_memory_info()
        pool_stats = self.pool.get_stats()
        
        with self.lock:
            mmapped_count = len(self.mmapped_arrays)
            mmapped_size_mb = sum(
                mmap_array.size / (1024 * 1024) 
                for mmap_array in self.mmapped_arrays
            )
        
        return {
            'system_memory': {
                'total_mb': info.total_mb,
                'available_mb': info.available_mb,
                'used_mb': info.used_mb,
                'used_percent': info.used_percent
            },
            'process_memory': {
                'used_mb': info.process_mb,
                'max_allowed_mb': self.max_memory_bytes / (1024 * 1024),
                'usage_percent': info.process_mb / (self.max_memory_bytes / (1024 * 1024)) * 100
            },
            'memory_pool': pool_stats,
            'memory_mapped': {
                'array_count': mmapped_count,
                'total_size_mb': mmapped_size_mb
            },
            'samples_count': len(self.memory_samples)
        }
    
    def set_callbacks(self, warning_callback=None, critical_callback=None):
        """
        Set callbacks for memory events.
        
        Args:
            warning_callback: Called when memory usage reaches warning threshold
            critical_callback: Called when memory usage reaches critical threshold
        """
        self.warning_callback = warning_callback
        self.critical_callback = critical_callback
    
    def get_memory_history(self) -> List[Dict[str, Any]]:
        """Get memory usage history."""
        return self.memory_samples.copy()
    
    def optimize_for_high_rate(self):
        """Optimize memory settings for high-rate acquisition."""
        # Increase pool size for high-rate operations
        self.pool.max_size_bytes = int(200 * 1024 * 1024)  # 200MB
        
        # More aggressive cleanup
        self.cleanup_interval = 10.0  # seconds
        
        # Tighter thresholds
        self.warning_threshold = 0.7
        self.critical_threshold = 0.8
