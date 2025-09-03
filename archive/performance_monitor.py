"""
Performance monitoring and analysis for DAQ operations.
Tracks system performance, identifies bottlenecks, and provides optimization recommendations.
"""

import time
import numpy as np
import psutil
from PySide6 import QtCore, QtWidgets
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import threading
import json
import os


@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot."""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_io_sent_mb: float
    network_io_recv_mb: float
    thread_count: int
    open_files: int
    
    # DAQ-specific metrics
    sampling_rate: float = 0.0
    actual_rate: float = 0.0
    dropped_samples: int = 0
    buffer_health: float = 0.0
    gui_update_rate: float = 0.0
    processing_latency_ms: float = 0.0


@dataclass
class PerformanceAlert:
    """Performance alert information."""
    severity: str  # 'info', 'warning', 'critical'
    category: str  # 'cpu', 'memory', 'disk', 'daq', 'gui'
    message: str
    timestamp: float
    value: float = 0.0
    threshold: float = 0.0


@dataclass 
class BenchmarkResult:
    """Benchmark test result."""
    test_name: str
    duration_seconds: float
    samples_processed: int
    throughput_samples_per_sec: float
    cpu_usage_percent: float
    memory_usage_mb: float
    success: bool
    error_message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class PerformanceProfiler:
    """
    Performance profiler for identifying bottlenecks.
    
    Tracks timing of key operations and identifies slow components.
    """
    
    def __init__(self):
        self.timings = {}  # {operation_name: [durations]}
        self.active_timers = {}  # {operation_name: start_time}
        self.call_counts = {}  # {operation_name: count}
        self.lock = threading.RLock()
    
    def start_timer(self, operation: str):
        """Start timing an operation."""
        with self.lock:
            self.active_timers[operation] = time.perf_counter()
    
    def end_timer(self, operation: str) -> float:
        """
        End timing an operation.
        
        Returns:
            Duration in seconds
        """
        with self.lock:
            if operation in self.active_timers:
                duration = time.perf_counter() - self.active_timers[operation]
                del self.active_timers[operation]
                
                # Store timing
                if operation not in self.timings:
                    self.timings[operation] = deque(maxlen=1000)
                    self.call_counts[operation] = 0
                
                self.timings[operation].append(duration)
                self.call_counts[operation] += 1
                
                return duration
            return 0.0
    
    def get_stats(self, operation: str) -> Dict[str, float]:
        """Get statistics for an operation."""
        with self.lock:
            if operation not in self.timings or not self.timings[operation]:
                return {}
            
            durations = list(self.timings[operation])
            return {
                'count': self.call_counts.get(operation, 0),
                'mean_ms': np.mean(durations) * 1000,
                'std_ms': np.std(durations) * 1000,
                'min_ms': np.min(durations) * 1000,
                'max_ms': np.max(durations) * 1000,
                'p95_ms': np.percentile(durations, 95) * 1000,
                'p99_ms': np.percentile(durations, 99) * 1000,
                'total_time_s': np.sum(durations)
            }
    
    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all operations."""
        with self.lock:
            return {op: self.get_stats(op) for op in self.timings.keys()}
    
    def clear(self):
        """Clear all profiling data."""
        with self.lock:
            self.timings.clear()
            self.active_timers.clear()
            self.call_counts.clear()


class PerformanceMonitor(QtCore.QObject):
    """
    Comprehensive performance monitor for DAQ applications.
    
    Features:
    - Real-time system monitoring
    - Performance alerting
    - Benchmark testing
    - Optimization recommendations
    - Historical data tracking
    """
    
    # Signals
    metrics_updated = QtCore.Signal(object)  # PerformanceMetrics
    alert_raised = QtCore.Signal(object)     # PerformanceAlert
    benchmark_completed = QtCore.Signal(object)  # BenchmarkResult
    
    def __init__(self):
        super().__init__()
        
        # Monitoring
        self.monitoring = False
        self.monitor_thread = None
        self.stop_event = threading.Event()
        
        # Historical data
        self.metrics_history = deque(maxlen=1000)  # Last 1000 measurements
        self.alerts_history = deque(maxlen=100)    # Last 100 alerts
        
        # Profiler
        self.profiler = PerformanceProfiler()
        
        # Alert thresholds
        self.thresholds = {
            'cpu_warning': 70.0,
            'cpu_critical': 90.0,
            'memory_warning': 70.0,
            'memory_critical': 85.0,
            'disk_warning': 80.0,
            'disk_critical': 95.0,
            'rate_accuracy_warning': 95.0,  # Below 95% accuracy
            'rate_accuracy_critical': 90.0,  # Below 90% accuracy
            'latency_warning': 50.0,  # >50ms latency
            'latency_critical': 100.0,  # >100ms latency
        }
        
        # Performance baselines
        self.baselines = {}
        
        # DAQ performance tracking
        self.daq_metrics = {
            'sampling_rate': 0.0,
            'actual_rate': 0.0,
            'dropped_samples': 0,
            'buffer_health': 0.0,
            'gui_update_rate': 0.0,
            'processing_latency_ms': 0.0
        }
        
        # System baseline measurement
        self._measure_baseline()
    
    def _measure_baseline(self):
        """Measure system performance baseline."""
        try:
            # CPU baseline (idle)
            cpu_samples = []
            for _ in range(5):
                cpu_samples.append(psutil.cpu_percent(interval=0.1))
            
            self.baselines['cpu_idle'] = np.mean(cpu_samples)
            
            # Memory baseline
            memory = psutil.virtual_memory()
            self.baselines['memory_available'] = memory.available / (1024**3)  # GB
            
            # Disk baseline
            disk = psutil.disk_usage('/')
            self.baselines['disk_free'] = disk.free / (1024**3)  # GB
            
        except Exception as e:
            print(f"Failed to measure baseline: {e}")
    
    def start_monitoring(self, interval: float = 1.0):
        """
        Start performance monitoring.
        
        Args:
            interval: Monitoring interval in seconds
        """
        if self.monitoring:
            return
        
        self.monitoring = True
        self.stop_event.clear()
        
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        if not self.monitoring:
            return
        
        self.monitoring = False
        self.stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
    
    def _monitoring_loop(self, interval: float):
        """Main monitoring loop."""
        last_disk_io = psutil.disk_io_counters()
        last_network_io = psutil.net_io_counters()
        last_time = time.time()
        
        while not self.stop_event.wait(interval):
            try:
                current_time = time.time()
                dt = current_time - last_time
                
                # System metrics
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                
                # Process metrics
                process = psutil.Process()
                process_memory = process.memory_info()
                
                # Disk I/O
                current_disk_io = psutil.disk_io_counters()
                if last_disk_io and dt > 0:
                    disk_read_mb = (current_disk_io.read_bytes - last_disk_io.read_bytes) / (1024**2) / dt
                    disk_write_mb = (current_disk_io.write_bytes - last_disk_io.write_bytes) / (1024**2) / dt
                else:
                    disk_read_mb = disk_write_mb = 0.0
                
                # Network I/O
                current_network_io = psutil.net_io_counters()
                if last_network_io and dt > 0:
                    net_sent_mb = (current_network_io.bytes_sent - last_network_io.bytes_sent) / (1024**2) / dt
                    net_recv_mb = (current_network_io.bytes_recv - last_network_io.bytes_recv) / (1024**2) / dt
                else:
                    net_sent_mb = net_recv_mb = 0.0
                
                # Create metrics object
                metrics = PerformanceMetrics(
                    timestamp=current_time,
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    memory_mb=process_memory.rss / (1024**2),
                    disk_io_read_mb=disk_read_mb,
                    disk_io_write_mb=disk_write_mb,
                    network_io_sent_mb=net_sent_mb,
                    network_io_recv_mb=net_recv_mb,
                    thread_count=process.num_threads(),
                    open_files=len(process.open_files()),
                    **self.daq_metrics
                )
                
                # Store metrics
                self.metrics_history.append(metrics)
                
                # Check for alerts
                self._check_alerts(metrics)
                
                # Emit metrics
                self.metrics_updated.emit(metrics)
                
                # Update for next iteration
                last_disk_io = current_disk_io
                last_network_io = current_network_io
                last_time = current_time
                
            except Exception as e:
                print(f"Monitoring error: {e}")
    
    def _check_alerts(self, metrics: PerformanceMetrics):
        """Check metrics against thresholds and raise alerts."""
        alerts = []
        
        # CPU alerts
        if metrics.cpu_percent > self.thresholds['cpu_critical']:
            alerts.append(PerformanceAlert(
                severity='critical',
                category='cpu',
                message=f'Critical CPU usage: {metrics.cpu_percent:.1f}%',
                timestamp=metrics.timestamp,
                value=metrics.cpu_percent,
                threshold=self.thresholds['cpu_critical']
            ))
        elif metrics.cpu_percent > self.thresholds['cpu_warning']:
            alerts.append(PerformanceAlert(
                severity='warning',
                category='cpu',
                message=f'High CPU usage: {metrics.cpu_percent:.1f}%',
                timestamp=metrics.timestamp,
                value=metrics.cpu_percent,
                threshold=self.thresholds['cpu_warning']
            ))
        
        # Memory alerts
        if metrics.memory_percent > self.thresholds['memory_critical']:
            alerts.append(PerformanceAlert(
                severity='critical',
                category='memory',
                message=f'Critical memory usage: {metrics.memory_percent:.1f}%',
                timestamp=metrics.timestamp,
                value=metrics.memory_percent,
                threshold=self.thresholds['memory_critical']
            ))
        elif metrics.memory_percent > self.thresholds['memory_warning']:
            alerts.append(PerformanceAlert(
                severity='warning',
                category='memory',
                message=f'High memory usage: {metrics.memory_percent:.1f}%',
                timestamp=metrics.timestamp,
                value=metrics.memory_percent,
                threshold=self.thresholds['memory_warning']
            ))
        
        # DAQ rate accuracy alerts
        if metrics.sampling_rate > 0:
            rate_accuracy = (metrics.actual_rate / metrics.sampling_rate) * 100
            
            if rate_accuracy < self.thresholds['rate_accuracy_critical']:
                alerts.append(PerformanceAlert(
                    severity='critical',
                    category='daq',
                    message=f'Critical DAQ rate accuracy: {rate_accuracy:.1f}%',
                    timestamp=metrics.timestamp,
                    value=rate_accuracy,
                    threshold=self.thresholds['rate_accuracy_critical']
                ))
            elif rate_accuracy < self.thresholds['rate_accuracy_warning']:
                alerts.append(PerformanceAlert(
                    severity='warning',
                    category='daq',
                    message=f'Low DAQ rate accuracy: {rate_accuracy:.1f}%',
                    timestamp=metrics.timestamp,
                    value=rate_accuracy,
                    threshold=self.thresholds['rate_accuracy_warning']
                ))
        
        # Processing latency alerts
        if metrics.processing_latency_ms > self.thresholds['latency_critical']:
            alerts.append(PerformanceAlert(
                severity='critical',
                category='daq',
                message=f'Critical processing latency: {metrics.processing_latency_ms:.1f}ms',
                timestamp=metrics.timestamp,
                value=metrics.processing_latency_ms,
                threshold=self.thresholds['latency_critical']
            ))
        elif metrics.processing_latency_ms > self.thresholds['latency_warning']:
            alerts.append(PerformanceAlert(
                severity='warning',
                category='daq',
                message=f'High processing latency: {metrics.processing_latency_ms:.1f}ms',
                timestamp=metrics.timestamp,
                value=metrics.processing_latency_ms,
                threshold=self.thresholds['latency_warning']
            ))
        
        # Emit alerts
        for alert in alerts:
            self.alerts_history.append(alert)
            self.alert_raised.emit(alert)
    
    def update_daq_metrics(self, **kwargs):
        """Update DAQ-specific metrics."""
        self.daq_metrics.update(kwargs)
    
    def run_benchmark(self, test_name: str, duration_seconds: float = 10.0) -> BenchmarkResult:
        """
        Run a performance benchmark test.
        
        Args:
            test_name: Name of the benchmark test
            duration_seconds: Test duration
            
        Returns:
            Benchmark result
        """
        print(f"Running benchmark: {test_name}")
        
        start_time = time.perf_counter()
        start_metrics = self._get_current_metrics()
        
        try:
            if test_name == "memory_allocation":
                samples_processed = self._benchmark_memory_allocation(duration_seconds)
            elif test_name == "array_operations":
                samples_processed = self._benchmark_array_operations(duration_seconds)
            elif test_name == "gui_updates":
                samples_processed = self._benchmark_gui_updates(duration_seconds)
            elif test_name == "file_io":
                samples_processed = self._benchmark_file_io(duration_seconds)
            else:
                raise ValueError(f"Unknown benchmark: {test_name}")
            
            end_time = time.perf_counter()
            end_metrics = self._get_current_metrics()
            
            actual_duration = end_time - start_time
            throughput = samples_processed / actual_duration
            
            cpu_usage = end_metrics.cpu_percent
            memory_usage = end_metrics.memory_mb
            
            result = BenchmarkResult(
                test_name=test_name,
                duration_seconds=actual_duration,
                samples_processed=samples_processed,
                throughput_samples_per_sec=throughput,
                cpu_usage_percent=cpu_usage,
                memory_usage_mb=memory_usage,
                success=True
            )
            
        except Exception as e:
            result = BenchmarkResult(
                test_name=test_name,
                duration_seconds=time.perf_counter() - start_time,
                samples_processed=0,
                throughput_samples_per_sec=0,
                cpu_usage_percent=0,
                memory_usage_mb=0,
                success=False,
                error_message=str(e)
            )
        
        self.benchmark_completed.emit(result)
        return result
    
    def _get_current_metrics(self) -> PerformanceMetrics:
        """Get current system metrics."""
        memory = psutil.virtual_memory()
        process = psutil.Process()
        process_memory = process.memory_info()
        
        return PerformanceMetrics(
            timestamp=time.time(),
            cpu_percent=psutil.cpu_percent(),
            memory_percent=memory.percent,
            memory_mb=process_memory.rss / (1024**2),
            disk_io_read_mb=0,
            disk_io_write_mb=0,
            network_io_sent_mb=0,
            network_io_recv_mb=0,
            thread_count=process.num_threads(),
            open_files=len(process.open_files())
        )
    
    def _benchmark_memory_allocation(self, duration: float) -> int:
        """Benchmark memory allocation performance."""
        samples_processed = 0
        end_time = time.perf_counter() + duration
        
        arrays = []
        while time.perf_counter() < end_time:
            # Allocate arrays of different sizes
            for size in [1000, 5000, 10000]:
                arr = np.random.random((size, 8))
                arrays.append(arr)
                samples_processed += size
                
                # Clean up periodically
                if len(arrays) > 100:
                    arrays = arrays[-50:]  # Keep last 50
        
        return samples_processed
    
    def _benchmark_array_operations(self, duration: float) -> int:
        """Benchmark array processing performance."""
        samples_processed = 0
        end_time = time.perf_counter() + duration
        
        # Pre-allocate test data
        test_data = np.random.random((10000, 8))
        
        while time.perf_counter() < end_time:
            # Various array operations
            result = np.mean(test_data, axis=0)
            result = np.std(test_data, axis=0)
            result = np.fft.fft(test_data[:, 0])
            result = np.convolve(test_data[:, 0], test_data[:, 1], mode='same')
            
            samples_processed += test_data.shape[0]
        
        return samples_processed
    
    def _benchmark_gui_updates(self, duration: float) -> int:
        """Benchmark GUI update performance."""
        # This would require GUI access - placeholder implementation
        return int(duration * 1000)  # Simulate 1000 updates per second
    
    def _benchmark_file_io(self, duration: float) -> int:
        """Benchmark file I/O performance."""
        samples_processed = 0
        end_time = time.perf_counter() + duration
        
        # Test data
        test_data = np.random.random((1000, 8))
        
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_filename = f.name
        
        try:
            while time.perf_counter() < end_time:
                # Write data
                np.savetxt(temp_filename, test_data, delimiter=',')
                
                # Read data back
                loaded_data = np.loadtxt(temp_filename, delimiter=',')
                
                samples_processed += test_data.shape[0]
        finally:
            try:
                os.unlink(temp_filename)
            except:
                pass
        
        return samples_processed
    
    def get_optimization_recommendations(self) -> List[str]:
        """Get optimization recommendations based on current performance."""
        recommendations = []
        
        if not self.metrics_history:
            return ["Start monitoring to get recommendations"]
        
        # Analyze recent metrics
        recent_metrics = list(self.metrics_history)[-10:]  # Last 10 measurements
        
        # CPU analysis
        avg_cpu = np.mean([m.cpu_percent for m in recent_metrics])
        if avg_cpu > 80:
            recommendations.append("High CPU usage detected. Consider:")
            recommendations.append("- Reducing GUI update frequency")
            recommendations.append("- Moving processing to background threads")
            recommendations.append("- Optimizing data processing algorithms")
        
        # Memory analysis
        avg_memory = np.mean([m.memory_percent for m in recent_metrics])
        if avg_memory > 70:
            recommendations.append("High memory usage detected. Consider:")
            recommendations.append("- Implementing data streaming for large datasets")
            recommendations.append("- Using memory-mapped arrays")
            recommendations.append("- Reducing buffer sizes")
        
        # DAQ performance analysis
        if self.daq_metrics['sampling_rate'] > 0:
            rate_accuracy = self.daq_metrics['actual_rate'] / self.daq_metrics['sampling_rate'] * 100
            if rate_accuracy < 95:
                recommendations.append("Low DAQ rate accuracy detected. Consider:")
                recommendations.append("- Increasing buffer sizes")
                recommendations.append("- Using dedicated DAQ threads")
                recommendations.append("- Reducing concurrent operations")
        
        if not recommendations:
            recommendations.append("System performance is good!")
        
        return recommendations
    
    def save_performance_report(self, filename: str):
        """Save performance report to file."""
        report = {
            'timestamp': time.time(),
            'baselines': self.baselines,
            'thresholds': self.thresholds,
            'metrics_count': len(self.metrics_history),
            'alerts_count': len(self.alerts_history),
            'profiler_stats': self.profiler.get_all_stats(),
            'recommendations': self.get_optimization_recommendations()
        }
        
        # Add recent metrics
        if self.metrics_history:
            recent_metrics = list(self.metrics_history)[-100:]  # Last 100
            report['recent_metrics'] = [
                {
                    'timestamp': m.timestamp,
                    'cpu_percent': m.cpu_percent,
                    'memory_percent': m.memory_percent,
                    'memory_mb': m.memory_mb,
                    'sampling_rate': m.sampling_rate,
                    'actual_rate': m.actual_rate,
                    'processing_latency_ms': m.processing_latency_ms
                }
                for m in recent_metrics
            ]
        
        # Add recent alerts
        if self.alerts_history:
            recent_alerts = list(self.alerts_history)[-50:]  # Last 50
            report['recent_alerts'] = [
                {
                    'timestamp': a.timestamp,
                    'severity': a.severity,
                    'category': a.category,
                    'message': a.message,
                    'value': a.value,
                    'threshold': a.threshold
                }
                for a in recent_alerts
            ]
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
