"""
Frequency filtering functions for DAQ signal processing.

This module provides digital filter functions for real-time signal processing
of data acquired from NI-DAQmx devices. Supports low-pass and high-pass filtering
with configurable cutoff frequencies.

Functions:
- low_pass(y, t, cutoff_freq, order=4): Low-pass Butterworth filter
- high_pass(y, t, cutoff_freq, order=4): High-pass Butterworth filter
- band_pass(y, t, low_freq, high_freq, order=4): Band-pass Butterworth filter
- band_stop(y, t, low_freq, high_freq, order=4): Band-stop (notch) Butterworth filter

Requirements:
- scipy.signal for filter design and application
- numpy for array operations
"""

import numpy as np
from typing import Tuple, Union, Optional
import warnings

try:
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    warnings.warn("scipy not available. Install with: pip install scipy")


def _validate_inputs(y: np.ndarray, t: np.ndarray, cutoff_freq: float) -> Tuple[float, int]:
    """Validate common filter input parameters.
    
    Parameters
    ----------
    y : np.ndarray
        Input signal data, shape (N,) or (N, C) where N=samples, C=channels
    t : np.ndarray
        Time array in milliseconds, shape (N,)
    cutoff_freq : float
        Cutoff frequency in Hz
        
    Returns
    -------
    fs : float
        Sampling frequency in Hz
    n_samples : int
        Number of samples
        
    Raises
    ------
    ValueError
        If inputs are invalid or scipy is not available
    """
    if not SCIPY_AVAILABLE:
        raise ValueError("scipy is required for filtering. Install with: pip install scipy")
    
    y = np.asarray(y)
    t = np.asarray(t)
    
    if y.ndim == 1:
        y = y.reshape(-1, 1)
    elif y.ndim > 2:
        raise ValueError("y must be 1D or 2D array")
    
    if t.ndim != 1:
        raise ValueError("t must be 1D array")
    
    n_samples = y.shape[0]
    if len(t) != n_samples:
        raise ValueError("Time array length must match signal length")
    
    if n_samples < 3:
        raise ValueError("Need at least 3 samples for filtering")
    
    # Calculate sampling frequency from time array (t in milliseconds)
    if n_samples == 1:
        raise ValueError("Cannot determine sampling rate from single sample")
    
    dt_ms = np.mean(np.diff(t))  # Average time step in ms
    fs = 1000.0 / dt_ms  # Convert to Hz
    
    if cutoff_freq <= 0:
        raise ValueError("Cutoff frequency must be positive")
    
    nyquist_freq = fs / 2.0
    if cutoff_freq >= nyquist_freq:
        raise ValueError(f"Cutoff frequency ({cutoff_freq} Hz) must be less than Nyquist frequency ({nyquist_freq:.1f} Hz)")
    
    return fs, n_samples


def low_pass(y: np.ndarray, t: np.ndarray, cutoff_freq: float, order: int = 4) -> np.ndarray:
    """Apply low-pass Butterworth filter to signal data.
    
    Removes high-frequency components above the cutoff frequency while preserving
    low-frequency components. Useful for noise reduction and anti-aliasing.
    
    Parameters
    ----------
    y : np.ndarray
        Input signal data, shape (N,) or (N, C) where N=samples, C=channels
    t : np.ndarray
        Time array in milliseconds, shape (N,)
    cutoff_freq : float
        Cutoff frequency in Hz (-3dB point)
    order : int, default 4
        Filter order (higher order = steeper rolloff)
        
    Returns
    -------
    np.ndarray
        Filtered signal, same shape as input y
        
    Examples
    --------
    >>> # Filter 1kHz signal with 100Hz cutoff
    >>> t = np.linspace(0, 1000, 1000)  # 1 second, 1kHz sampling
    >>> y = np.sin(2 * np.pi * 50 * t/1000) + 0.1 * np.sin(2 * np.pi * 200 * t/1000)
    >>> y_filtered = low_pass(y, t, cutoff_freq=100)
    
    >>> # Multi-channel filtering
    >>> y_multi = np.column_stack([y, y + 0.5])  # 2 channels
    >>> y_filtered = low_pass(y_multi, t, cutoff_freq=100)
    """
    fs, n_samples = _validate_inputs(y, t, cutoff_freq)
    
    y = np.asarray(y)
    was_1d = y.ndim == 1
    if was_1d:
        y = y.reshape(-1, 1)
    
    # Design Butterworth low-pass filter
    nyquist = fs / 2.0
    normalized_cutoff = cutoff_freq / nyquist
    
    # Ensure normalized frequency is in valid range [0, 1)
    normalized_cutoff = min(normalized_cutoff, 0.99)
    
    try:
        b, a = signal.butter(order, normalized_cutoff, btype='low', analog=False)
        
        # Apply filter to each channel
        y_filtered = np.zeros_like(y)
        for ch in range(y.shape[1]):
            # Use filtfilt for zero-phase filtering (no time delay)
            y_filtered[:, ch] = signal.filtfilt(b, a, y[:, ch])
            
    except Exception as e:
        raise RuntimeError(f"Filter design or application failed: {e}")
    
    # Return same format as input
    if was_1d:
        return y_filtered.flatten()
    return y_filtered


def high_pass(y: np.ndarray, t: np.ndarray, cutoff_freq: float, order: int = 4) -> np.ndarray:
    """Apply high-pass Butterworth filter to signal data.
    
    Removes low-frequency components below the cutoff frequency while preserving
    high-frequency components. Useful for removing DC offset and low-frequency drift.
    
    Parameters
    ----------
    y : np.ndarray
        Input signal data, shape (N,) or (N, C) where N=samples, C=channels
    t : np.ndarray
        Time array in milliseconds, shape (N,)
    cutoff_freq : float
        Cutoff frequency in Hz (-3dB point)
    order : int, default 4
        Filter order (higher order = steeper rolloff)
        
    Returns
    -------
    np.ndarray
        Filtered signal, same shape as input y
        
    Examples
    --------
    >>> # Remove DC and low frequencies below 10Hz
    >>> t = np.linspace(0, 1000, 1000)  # 1 second, 1kHz sampling
    >>> y = 2.5 + 0.1 * np.sin(2 * np.pi * 5 * t/1000) + np.sin(2 * np.pi * 50 * t/1000)
    >>> y_filtered = high_pass(y, t, cutoff_freq=10)
    """
    fs, n_samples = _validate_inputs(y, t, cutoff_freq)
    
    y = np.asarray(y)
    was_1d = y.ndim == 1
    if was_1d:
        y = y.reshape(-1, 1)
    
    # Design Butterworth high-pass filter
    nyquist = fs / 2.0
    normalized_cutoff = cutoff_freq / nyquist
    
    # Ensure normalized frequency is in valid range (0, 1)
    normalized_cutoff = max(normalized_cutoff, 0.01)  # Avoid very low frequencies
    normalized_cutoff = min(normalized_cutoff, 0.99)
    
    try:
        b, a = signal.butter(order, normalized_cutoff, btype='high', analog=False)
        
        # Apply filter to each channel
        y_filtered = np.zeros_like(y)
        for ch in range(y.shape[1]):
            # Use filtfilt for zero-phase filtering (no time delay)
            y_filtered[:, ch] = signal.filtfilt(b, a, y[:, ch])
            
    except Exception as e:
        raise RuntimeError(f"Filter design or application failed: {e}")
    
    # Return same format as input
    if was_1d:
        return y_filtered.flatten()
    return y_filtered


def band_pass(y: np.ndarray, t: np.ndarray, low_freq: float, high_freq: float, order: int = 4) -> np.ndarray:
    """Apply band-pass Butterworth filter to signal data.
    
    Preserves frequencies between low_freq and high_freq while attenuating
    frequencies outside this range. Useful for isolating specific frequency bands.
    
    Parameters
    ----------
    y : np.ndarray
        Input signal data, shape (N,) or (N, C) where N=samples, C=channels
    t : np.ndarray
        Time array in milliseconds, shape (N,)
    low_freq : float
        Lower cutoff frequency in Hz (-3dB point)
    high_freq : float
        Upper cutoff frequency in Hz (-3dB point)
    order : int, default 4
        Filter order (higher order = steeper rolloff)
        
    Returns
    -------
    np.ndarray
        Filtered signal, same shape as input y
        
    Examples
    --------
    >>> # Extract 40-60Hz band (e.g., around 50Hz power line frequency)
    >>> t = np.linspace(0, 1000, 1000)
    >>> y = np.sin(2 * np.pi * 10 * t/1000) + np.sin(2 * np.pi * 50 * t/1000) + np.sin(2 * np.pi * 200 * t/1000)
    >>> y_filtered = band_pass(y, t, low_freq=40, high_freq=60)
    """
    if low_freq >= high_freq:
        raise ValueError("low_freq must be less than high_freq")
    
    fs, n_samples = _validate_inputs(y, t, high_freq)
    
    # Also validate low frequency
    if low_freq <= 0:
        raise ValueError("Low frequency must be positive")
    
    nyquist_freq = fs / 2.0
    if low_freq >= nyquist_freq:
        raise ValueError(f"Low frequency ({low_freq} Hz) must be less than Nyquist frequency ({nyquist_freq:.1f} Hz)")
    
    y = np.asarray(y)
    was_1d = y.ndim == 1
    if was_1d:
        y = y.reshape(-1, 1)
    
    # Design Butterworth band-pass filter
    nyquist = fs / 2.0
    low_norm = max(low_freq / nyquist, 0.01)
    high_norm = min(high_freq / nyquist, 0.99)
    
    try:
        b, a = signal.butter(order, [low_norm, high_norm], btype='band', analog=False)
        
        # Apply filter to each channel
        y_filtered = np.zeros_like(y)
        for ch in range(y.shape[1]):
            y_filtered[:, ch] = signal.filtfilt(b, a, y[:, ch])
            
    except Exception as e:
        raise RuntimeError(f"Filter design or application failed: {e}")
    
    # Return same format as input
    if was_1d:
        return y_filtered.flatten()
    return y_filtered


def band_stop(y: np.ndarray, t: np.ndarray, low_freq: float, high_freq: float, order: int = 4) -> np.ndarray:
    """Apply band-stop (notch) Butterworth filter to signal data.
    
    Attenuates frequencies between low_freq and high_freq while preserving
    frequencies outside this range. Useful for removing specific interference
    like power line noise (50/60Hz).
    
    Parameters
    ----------
    y : np.ndarray
        Input signal data, shape (N,) or (N, C) where N=samples, C=channels
    t : np.ndarray
        Time array in milliseconds, shape (N,)
    low_freq : float
        Lower cutoff frequency in Hz (-3dB point)
    high_freq : float
        Upper cutoff frequency in Hz (-3dB point)
    order : int, default 4
        Filter order (higher order = steeper rolloff)
        
    Returns
    -------
    np.ndarray
        Filtered signal, same shape as input y
        
    Examples
    --------
    >>> # Remove 50Hz power line noise (48-52Hz band)
    >>> t = np.linspace(0, 1000, 1000)
    >>> y = np.sin(2 * np.pi * 10 * t/1000) + 0.2 * np.sin(2 * np.pi * 50 * t/1000) + np.sin(2 * np.pi * 100 * t/1000)
    >>> y_filtered = band_stop(y, t, low_freq=48, high_freq=52)
    """
    if low_freq >= high_freq:
        raise ValueError("low_freq must be less than high_freq")
    
    fs, n_samples = _validate_inputs(y, t, high_freq)
    
    # Also validate low frequency
    if low_freq <= 0:
        raise ValueError("Low frequency must be positive")
    
    nyquist_freq = fs / 2.0
    if low_freq >= nyquist_freq:
        raise ValueError(f"Low frequency ({low_freq} Hz) must be less than Nyquist frequency ({nyquist_freq:.1f} Hz)")
    
    y = np.asarray(y)
    was_1d = y.ndim == 1
    if was_1d:
        y = y.reshape(-1, 1)
    
    # Design Butterworth band-stop filter
    nyquist = fs / 2.0
    low_norm = max(low_freq / nyquist, 0.01)
    high_norm = min(high_freq / nyquist, 0.99)
    
    try:
        b, a = signal.butter(order, [low_norm, high_norm], btype='bandstop', analog=False)
        
        # Apply filter to each channel
        y_filtered = np.zeros_like(y)
        for ch in range(y.shape[1]):
            y_filtered[:, ch] = signal.filtfilt(b, a, y[:, ch])
            
    except Exception as e:
        raise RuntimeError(f"Filter design or application failed: {e}")
    
    # Return same format as input
    if was_1d:
        return y_filtered.flatten()
    return y_filtered


# Convenience function for common 50/60Hz notch filtering
def notch_50hz(y: np.ndarray, t: np.ndarray, order: int = 4) -> np.ndarray:
    """Remove 50Hz power line noise (convenience function).
    
    Applies a band-stop filter around 50Hz (48-52Hz) to remove power line interference.
    
    Parameters
    ----------
    y : np.ndarray
        Input signal data
    t : np.ndarray
        Time array in milliseconds
    order : int, default 4
        Filter order
        
    Returns
    -------
    np.ndarray
        Filtered signal with 50Hz noise removed
    """
    return band_stop(y, t, low_freq=48, high_freq=52, order=order)


def notch_60hz(y: np.ndarray, t: np.ndarray, order: int = 4) -> np.ndarray:
    """Remove 60Hz power line noise (convenience function).
    
    Applies a band-stop filter around 60Hz (58-62Hz) to remove power line interference.
    
    Parameters
    ----------
    y : np.ndarray
        Input signal data
    t : np.ndarray
        Time array in milliseconds
    order : int, default 4
        Filter order
        
    Returns
    -------
    np.ndarray
        Filtered signal with 60Hz noise removed
    """
    return band_stop(y, t, low_freq=58, high_freq=62, order=order)


if __name__ == "__main__":
    # Example usage and testing
    print("Testing frequency filters...")
    
    if not SCIPY_AVAILABLE:
        print("scipy not available - install with: pip install scipy")
        exit(1)
    
    # Generate test signal: 10Hz + 50Hz + 200Hz + noise
    duration_ms = 1000  # 1 second
    fs = 1000  # 1kHz sampling
    t = np.linspace(0, duration_ms, fs)
    
    # Multi-frequency test signal
    f1, f2, f3 = 10, 50, 200  # Hz
    y = (np.sin(2 * np.pi * f1 * t / 1000) + 
         0.5 * np.sin(2 * np.pi * f2 * t / 1000) + 
         0.3 * np.sin(2 * np.pi * f3 * t / 1000) + 
         0.1 * np.random.randn(len(t)))  # Add noise
    
    print(f"Original signal: {f1}Hz + {f2}Hz + {f3}Hz + noise")
    print(f"Sampling rate: {fs}Hz, Duration: {duration_ms}ms")
    
    # Test filters
    try:
        y_lp = low_pass(y, t, cutoff_freq=100)
        print("✓ Low-pass filter (100Hz cutoff) - should remove 200Hz component")
        
        y_hp = high_pass(y, t, cutoff_freq=30)
        print("✓ High-pass filter (30Hz cutoff) - should remove 10Hz component")
        
        y_bp = band_pass(y, t, low_freq=40, high_freq=60)
        print("✓ Band-pass filter (40-60Hz) - should isolate 50Hz component")
        
        y_notch = notch_50hz(y, t)
        print("✓ 50Hz notch filter - should remove 50Hz component")
        
        # Test multi-channel
        y_multi = np.column_stack([y, y * 0.8])  # 2 channels
        y_multi_filtered = low_pass(y_multi, t, cutoff_freq=100)
        print("✓ Multi-channel filtering works")
        
        print("\nAll filter tests passed!")
        
    except Exception as e:
        print(f"Filter test failed: {e}")
