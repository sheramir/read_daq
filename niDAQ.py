"""
NIDAQReader: Python class for NI USB-6211 and similar NI-DAQmx devices.

Usage Example:
    settings = NIDAQSettings(device_name="Dev1", channels=["ai0", "ai1"], sampling_rate_hz=200.0)
    reader = NIDAQReader(settings)
    reader.start()
    t_ms, y = reader.read_data(number_of_samples_per_channel=100)
    reader.stop()

Parameters:
- device_name: NI device name (e.g., "Dev1")
- channels: List of analog input channels (e.g., ["ai0", "ai1"])
- sampling_rate_hz: Acquisition rate in Hz
- v_min, v_max: Input voltage range
- terminal_config: Input configuration ("RSE", "NRSE", "DIFF", "PSEUDO-DIFF")
- adc_bits: ADC resolution (default 16)

Main Functions:
- start(): Initializes and starts the DAQ task
- stop(): Stops and closes the DAQ task
- read_data(number_of_samples_per_channel, average_ms=None, rolling_avg=True, timeout=10.0, accumulate=True):
    Reads a block of samples, returns (timestamps_ms, voltages) ndarray.
    Supports optional rolling average or downsampled mean per channel.
- save_data(filename, format="csv", include_json_sidecar=True, quantize=True, round_mode="round"):
    Saves accumulated data to CSV (with metadata header) and optional JSON sidecar.
- list_devices(): Static method to list available NI-DAQmx devices
- list_ai_channels(device_name): Static method to list available AI channels for a device
- print_data(max_rows=None, time_decimals=3, value_decimals=6):
    Prints accumulated samples in tabular form.
- plot_data(channels=None, separate=False, auto_ylim=False, figsize=None, show=True, show_mean=False):
    Plots accumulated channel data vs timestamp using matplotlib.
- plot_realtime(...):
    Plots real-time streaming values for selected channels using matplotlib animation.

Important Notes:
- Requires NI-DAQmx Python package: `nidaqmx` and NI-DAQmx driver installed
- Designed for use in desktop apps (PySide6/PyQt6, pyqtgraph, etc.)
- Thread-safe for use in worker threads
- Validates device, channels, voltage range, and configuration before starting
- Accumulated data can be saved or printed for analysis
- Handles multi-channel acquisition and accurate timestamping
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple, Dict
import time
import json
import os
from datetime import datetime  # added for metadata timestamp
import math

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

try:
    import nidaqmx
    from nidaqmx.constants import TerminalConfiguration, AcquisitionType
    from nidaqmx.stream_readers import AnalogMultiChannelReader
    from nidaqmx.system import System
except Exception as e:  # pragma: no cover - allows importing without hardware
    nidaqmx = None  # type: ignore
    TerminalConfiguration = object  # type: ignore
    AcquisitionType = object  # type: ignore
    AnalogMultiChannelReader = object  # type: ignore
    System = object  # type: ignore


_TERMINAL_MAP: Dict[str, int] = {
    "RSE": getattr(TerminalConfiguration, "RSE", 0),
    "NRSE": getattr(TerminalConfiguration, "NRSE", 1),
    "DIFF": getattr(TerminalConfiguration, "DIFFERENTIAL", 2),
    "PSEUDO-DIFF": getattr(TerminalConfiguration, "PSEUDODIFFERENTIAL", 3),
}


@dataclass
class NIDAQSettings:
    device_name: str = "Dev1"
    sampling_rate_hz: float = 200.0
    v_min: float = -1.0
    v_max: float = 3.5
    terminal_config: str = "RSE"
    channels: List[str] = field(default_factory=lambda: ["ai0"])
    adc_bits: int = 16          # <-- add ADC resolution (nominal)
    # Per-channel voltage ranges (optional) - if provided, overrides v_min/v_max for specific channels
    channel_ranges: Optional[Dict[str, Tuple[float, float]]] = None
    
    def get_channel_range(self, channel: str) -> Tuple[float, float]:
        """Get the voltage range for a specific channel.
        
        Returns:
            Tuple of (v_min, v_max) for the channel
        """
        if self.channel_ranges and channel in self.channel_ranges:
            return self.channel_ranges[channel]
        return (self.v_min, self.v_max)
    
    def set_channel_range(self, channel: str, v_min: float, v_max: float) -> None:
        """Set the voltage range for a specific channel.
        
        Args:
            channel: Channel name (e.g., "ai0")
            v_min: Minimum voltage
            v_max: Maximum voltage
        """
        if self.channel_ranges is None:
            self.channel_ranges = {}
        self.channel_ranges[channel] = (v_min, v_max)
    
    @staticmethod
    def get_common_ranges() -> Dict[str, Tuple[float, float]]:
        """Get common voltage ranges for the NI USB-6211.
        
        Returns:
            Dictionary of range names to (v_min, v_max) tuples
        """
        return {
            "±10V": (-10.0, 10.0),
            "±5V": (-5.0, 5.0),
            "±2V": (-2.0, 2.0),
            "±1V": (-1.0, 1.0),
            "±0.5V": (-0.5, 0.5),
            "±0.2V": (-0.2, 0.2),
            "±0.1V": (-0.1, 0.1),
            "0-10V": (0.0, 10.0),
            "0-5V": (0.0, 5.0),
            "0-2V": (0.0, 2.0),
            "0-1V": (0.0, 1.0),
        }


class NIDAQReader:
    """High-level reader around nidaqmx for multi-channel AI acquisition.

    Usage:
        with NIDAQReader(NIDAQSettings(...)) as reader:
            reader.start()
            t_ms, y = reader.read_data(100)
            reader.stop()
    """

    def __init__(self, settings: Optional[NIDAQSettings] = None, *,
                 valid_ai_indices: Iterable[int] = range(16)) -> None:
        if settings is None:
            settings = NIDAQSettings()
        self.settings = settings
        self.valid_ai_indices = set(valid_ai_indices)

        # runtime state
        self._task: Optional[nidaqmx.Task] = None  # type: ignore
        self._reader: Optional[AnalogMultiChannelReader] = None  # type: ignore
        self._running: bool = False
        self._t0_perf: float = 0.0
        self._total_samples_read: int = 0  # per channel

        # averaging state (keeps continuity between blocks)
        self._avg_win: int = 1
        self._avg_tail: Optional[np.ndarray] = None  # shape (win-1, n_chan)
        self._downsample_tail: Optional[np.ndarray] = None  # raw leftover (< win, C)

        # accumulation for optional save
        self._acc_times: List[np.ndarray] = []
        self._acc_values: List[np.ndarray] = []  # list of (n, C)

    # -------------- Discovery helpers --------------
    @staticmethod
    def list_devices() -> List[str]:
        """List available NI-DAQmx device names.

        Returns
        -------
        List[str]
            List of device names (e.g., ['Dev1', 'Dev2']). Empty list if
            nidaqmx is not available or no devices detected.
        """
        if nidaqmx is None:
            return []
        return [d.name for d in System.local().devices]

    @staticmethod
    def list_ai_channels(device_name: str) -> List[str]:
        """List discoverable analog input channel names for a device.

        Parameters
        ----------
        device_name : str
            Target NI device name (e.g., 'Dev1').

        Returns
        -------
        List[str]
            Channel names (e.g., ['ai0', 'ai1', ...]). Falls back to ai0..ai15
            if explicit list cannot be queried, or [] if device not found.
        """
        if nidaqmx is None:
            return []
        dev = next((d for d in System.local().devices if d.name == device_name), None)
        if dev is None:
            return []
        # Prefer explicit aiX enumeration when available
        try:
            return [p.replace(f"{device_name}/", "") for p in dev.ai_physical_chans.channel_names]
        except Exception:
            return [f"ai{i}" for i in range(16)]

    # -------------- Lifecycle --------------
    def __enter__(self) -> NIDAQReader:
        """Context manager entry; starts acquisition.

        Returns
        -------
        NIDAQReader
            This instance (already started).
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Context manager exit; ensures task is closed.

        Parameters
        ----------
        exc_type :
            Exception type (if any).
        exc :
            Exception instance (if any).
        tb :
            Traceback (if any).
        """
        self.close()

    def start(self) -> None:
        """(Re)create and start the task in continuous sampling mode.

        Re-validates settings, rebuilds the task, configures channels, timing,
        resets internal counters, accumulation, and averaging state.

        Raises
        ------
        RuntimeError
            If nidaqmx is unavailable.
        ValueError
            If settings are invalid.
        """
        self._validate_settings()
        self.close()  # idempotent
        if nidaqmx is None:
            raise RuntimeError("nidaqmx is not available in this environment")

        self._task = nidaqmx.Task(new_task_name="NIDAQReaderTask")
        term_cfg = _TERMINAL_MAP[self.settings.terminal_config]

        for ch in self.settings.channels:
            physical = f"{self.settings.device_name}/{ch}"
            v_min, v_max = self.settings.get_channel_range(ch)
            self._task.ai_channels.add_ai_voltage_chan(
                physical_channel=physical,
                min_val=v_min,
                max_val=v_max,
                terminal_config=term_cfg,
            )

        # Configure timing for continuous sampling
        # DAQmx buffer at least 1 sec or samples_per_read, whichever greater
        samps_per_chan = int(max(self.settings.sampling_rate_hz, 100))
        self._task.timing.cfg_samp_clk_timing(
            rate=self.settings.sampling_rate_hz,
            sample_mode=AcquisitionType.CONTINUOUS,
            samps_per_chan=samps_per_chan,
        )

        self._reader = AnalogMultiChannelReader(self._task.in_stream)
        self._running = True
        self._t0_perf = time.perf_counter()
        self._total_samples_read = 0
        self._reset_averaging_state(len(self.settings.channels))
        self._acc_times.clear()
        self._acc_values.clear()

    def stop(self) -> None:
        """Stop acquisition (alias of close). Safe to call multiple times."""
        self.close()

    def close(self) -> None:
        """Stop and dispose of the underlying DAQmx task.

        Ensures hardware resources are released. Idempotent.
        """
        if getattr(self, "_task", None) is not None:
            try:
                if self._running:
                    self._task.stop()
            except Exception:
                pass
            try:
                self._task.close()
            except Exception:
                pass
        self._task = None
        self._reader = None
        self._running = False

    # -------------- Settings mutation --------------
    def set_input(self, channels: Iterable[str]) -> None:
        """Set active AI channels (restarts task if running).

        Parameters
        ----------
        channels : Iterable[str]
            Channel identifiers (e.g., ['ai0','ai1']).

        Raises
        ------
        ValueError
            On invalid channel syntax or index.
        """
        self.settings.channels = self._normalize_and_validate_channels(channels)
        # Recreate task if already running
        if self._running:
            self.start()

    def set_terminal_config(self, terminal_config: str) -> None:
        """Set terminal configuration (RSE / NRSE / DIFF / PSEUDO-DIFF).

        Parameters
        ----------
        terminal_config : str
            Key from _TERMINAL_MAP.

        Raises
        ------
        ValueError
            If unsupported mode provided.
        """
        if terminal_config not in _TERMINAL_MAP:
            raise ValueError(f"Invalid terminal configuration: {terminal_config}")
        self.settings.terminal_config = terminal_config
        if self._running:
            self.start()

    def set_voltage_range(self, v_min: float, v_max: float) -> None:
        """Set input voltage span (restarts task if active).

        Parameters
        ----------
        v_min : float
            Minimum expected voltage.
        v_max : float
            Maximum expected voltage (must be > v_min).

        Raises
        ------
        ValueError
            If v_min >= v_max.
        """
        if v_min >= v_max:
            raise ValueError("v_min must be < v_max")
        self.settings.v_min = v_min
        self.settings.v_max = v_max
        if self._running:
            self.start()

    def set_sampling(self, rate_hz: float) -> None:
        """Set sampling rate in Hz (restarts task if active).

        Parameters
        ----------
        rate_hz : float
            New sampling frequency (> 0).

        Raises
        ------
        ValueError
            If rate_hz <= 0.
        """
        if rate_hz <= 0:
            raise ValueError("sampling rate must be > 0")
        self.settings.sampling_rate_hz = rate_hz
        if self._running:
            self.start()

    # -------------- Reading --------------
    def read_data(
        self,
        number_of_samples_per_channel: int,
        average_ms: Optional[float] = None,
        *,
        rolling_avg: bool = True,
        timeout: float = 10.0,
        accumulate: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Read a block of samples.

        Parameters
        ----------
        number_of_samples_per_channel : int
            Raw samples to fetch per channel this call.
        average_ms : float | None
            If None: no averaging. If >0: apply averaging over a window of
            length round(average_ms * fs / 1000) samples.
        rolling_avg : bool
            Only used when average_ms is not None and > 0.
            True  -> causal rolling (moving) average (same length as input).
            False -> downsample (non‑overlapping means); produces fewer samples.
        timeout : float
            DAQmx read timeout (s).
        accumulate : bool
            If True, append returned (possibly averaged/downsampled) samples
            to internal accumulation buffers for save_data.

        Returns
        -------
        t_ms : (N,) ndarray
            Timestamps in ms. For rolling average: one per raw sample.
            For downsample: timestamp at end of each averaged window.
        y : (N, C) ndarray
            Voltages (averaged if requested). N can be 0 if no full window yet
            in downsample mode.
        """
        if not self._running or self._task is None or self._reader is None:
            raise RuntimeError("Task is not started. Call start() first.")
        if number_of_samples_per_channel <= 0:
            raise ValueError("number_of_samples_per_channel must be > 0")

        n_ch = len(self.settings.channels)
        raw_buf = np.empty((n_ch, number_of_samples_per_channel), dtype=np.float64)
        self._reader.read_many_sample(
            data=raw_buf,
            number_of_samples_per_channel=number_of_samples_per_channel,
            timeout=timeout,
        )
        y_raw = raw_buf.T  # (N_raw, C)
        N_raw = y_raw.shape[0]

        fs = float(self.settings.sampling_rate_hz)
        start_index_raw = self._total_samples_read  # index of first new raw sample

        # --- Averaging logic ---
        if average_ms is not None and average_ms > 0:
            win = max(1, int(round(average_ms * fs / 1000.0)))
            if win <= 1:
                y_proc = y_raw  # degenerates to no averaging
                rolling = False
            else:
                if rolling_avg:
                    # (Re)initialize rolling tail if needed
                    if win != self._avg_win or self._avg_tail is None or self._avg_tail.shape[1] != n_ch:
                        self._avg_win = win
                        self._avg_tail = np.zeros((win - 1, n_ch), dtype=np.float64)
                    y_proc = self._rolling_mean_with_tail(y_raw, self._avg_tail, win)
                    rolling = True
                else:
                    # Downsample (non-overlapping means)
                    if self._downsample_tail is None or self._downsample_tail.shape[1] != n_ch:
                        self._downsample_tail = np.zeros((0, n_ch), dtype=np.float64)
                    extended = np.vstack([self._downsample_tail, y_raw])  # (M, C)
                    M = extended.shape[0]
                    n_full = M // win
                    if n_full:
                        block = extended[: n_full * win].reshape(n_full, win, n_ch)
                        y_proc = block.mean(axis=1)  # (n_full, C)
                        # leftover tail
                        self._downsample_tail = extended[n_full * win :]
                    else:
                        # Not enough samples yet to form one window
                        self._downsample_tail = extended
                        y_proc = np.zeros((0, n_ch), dtype=np.float64)
                    rolling = False
            # Timestamp generation
            if average_ms is None or average_ms <= 0 or win <= 1:
                # treat as raw (no averaging)
                idx = np.arange(start_index_raw, start_index_raw + y_proc.shape[0], dtype=np.float64)
            else:
                if rolling:
                    # One timestamp per raw sample (aligned to raw sample index)
                    idx = np.arange(start_index_raw, start_index_raw + y_proc.shape[0], dtype=np.float64)
                else:
                    # Downsample: each mean represents window ending index
                    n_full = y_proc.shape[0]
                    if n_full:
                        end_indices = start_index_raw + (win - 1) + np.arange(n_full) * win
                        idx = end_indices.astype(np.float64)
                    else:
                        idx = np.zeros((0,), dtype=np.float64)
        else:
            # No averaging
            y_proc = y_raw
            idx = np.arange(start_index_raw, start_index_raw + N_raw, dtype=np.float64)

        # Update total raw samples read (always add raw count, not processed length)
        self._total_samples_read += N_raw

        t_ms = (idx / fs) * 1000.0

        if accumulate and y_proc.shape[0] > 0:
            self._acc_times.append(t_ms.copy())
            self._acc_values.append(y_proc.copy())
        return t_ms, y_proc

    # -------------- Save --------------
    def save_data(self, filename: str, *, format: str = "csv", include_json_sidecar: bool = True,
                  quantize: bool = True, round_mode: str = "round") -> str:
        """Persist accumulated data to disk.

        Parameters
        ----------
        filename : str
            Output base filename (e.g., 'run.csv').
        format : str, default 'csv'
            Currently only 'csv' supported.
        include_json_sidecar : bool
            If True, writes <filename>.json with structured data + metadata.
        quantize : bool
            If True, values are quantized/rounded to hardware LSB.
        round_mode : str
            'round' -> round to nearest code (default)
            'floor' -> toward -inf
            'ceil'  -> toward +inf

        Returns
        -------
        str
            Path to primary saved file.

        Raises
        ------
        RuntimeError
            If no accumulated data.
        ValueError
            If unsupported format requested.
        """
        if not self._acc_values:
            raise RuntimeError("No data accumulated to save.")

        t = np.concatenate(self._acc_times)          # float ms
        y = np.concatenate(self._acc_values)         # (N, C)
        channels = list(self.settings.channels)
        N, C = y.shape

        sample_index = np.arange(N, dtype=np.int64)

        # --- Precision handling ---
        span = self.settings.v_max - self.settings.v_min
        bits = max(1, int(self.settings.adc_bits))
        lsb = span / (2 ** bits)  # nominal LSB size in volts

        if quantize:
            # Shift to zero, quantize, shift back
            y_shift = y - self.settings.v_min
            codes = y_shift / lsb
            if round_mode == "floor":
                codes = np.floor(codes)
            elif round_mode == "ceil":
                codes = np.ceil(codes)
            else:
                codes = np.rint(codes)
            y = codes * lsb + self.settings.v_min
            # Clip to range
            np.clip(y, self.settings.v_min, self.settings.v_max, out=y)

        # Decide displayed decimal places so printed resolution <= LSB
        # decimals so that 10^{-decimals} <= lsb OR decimals = ceil(-log10(lsb))
        if lsb == 0:
            decimals = 6
        else:
            decimals = max(0, math.ceil(-math.log10(lsb))) + 1
            # Avoid overkill; cap
            decimals = min(decimals, 7)

        val_fmt = f"{{:.{decimals}f}}"

        meta_lines = [
            f"# device={self.settings.device_name}",
            f"# channels={','.join(channels)}",
            f"# config={self.settings.terminal_config} vmin={self.settings.v_min} vmax={self.settings.v_max}",
            f"# adc_bits={bits} lsb_volts={lsb:.6e} decimals={decimals}",
            f"# rate_hz={float(self.settings.sampling_rate_hz)} total_samples={int(N)}",
            f"# datetime={datetime.now().isoformat(timespec='seconds')}",
        ]

        if format.lower() == "csv":
            # Use enough precision for timestamps (up to microsecond in ms units -> 6 decimals)
            ts_fmt = "{:.6f}"
            with open(filename, "w", encoding="utf-8", newline="") as f:
                for line in meta_lines:
                    f.write(line + "\n")
                f.write("sample_index,timestamp_ms," + ",".join(channels) + "\n")
                for i in range(N):
                    row_vals = ",".join(val_fmt.format(y[i, c]) for c in range(C))
                    f.write(f"{sample_index[i]},{ts_fmt.format(t[i])},{row_vals}\n")
        else:
            raise ValueError("Only 'csv' format currently supported.")

        if include_json_sidecar:
            sidecar = {
                "device": self.settings.device_name,
                "channels": channels,
                "terminal_config": self.settings.terminal_config,
                "v_min": self.settings.v_min,
                "v_max": self.settings.v_max,
                "adc_bits": bits,
                "lsb_volts": lsb,
                "decimals": decimals,
                "rate_hz": float(self.settings.sampling_rate_hz),
                "total_samples": int(N),
                "datetime": datetime.now().isoformat(timespec="seconds"),
                "data": {
                    "sample_index": sample_index.tolist(),
                    "timestamp_ms": t.tolist(),  # keep full float precision
                    **{ch: [float(f"{v:.{decimals}f}") for v in y[:, idx]] for idx, ch in enumerate(channels)},
                },
            }
            import json
            with open(filename + ".json", "w", encoding="utf-8") as jf:
                json.dump(sidecar, jf, indent=2)

        return filename

    # -------------- Internals --------------
    def _validate_settings(self) -> None:
        """Validate current settings (device, channels, ranges, timing).

        Raises
        ------
        ValueError
            On invalid device, channels, voltage range, terminal config,
            or sampling rate.
        """
        # device present?
        if nidaqmx is None:
            return
        devices = {d.name for d in System.local().devices}
        if self.settings.device_name not in devices:
            # If no devices reported (e.g., sim/offline), allow proceed to help testing
            if devices:
                raise ValueError(f"Device '{self.settings.device_name}' not found. Available: {sorted(devices)}")
        # channels
        self.settings.channels = self._normalize_and_validate_channels(self.settings.channels)
        # voltage
        if not (self.settings.v_min < self.settings.v_max):
            raise ValueError("Invalid voltage range: v_min must be < v_max")
        # terminal
        if self.settings.terminal_config not in _TERMINAL_MAP:
            raise ValueError(f"Invalid terminal configuration: {self.settings.terminal_config}")
        # sampling
        if self.settings.sampling_rate_hz <= 0:
            raise ValueError("sampling_rate_hz must be > 0")

    def _normalize_and_validate_channels(self, channels: Iterable[str]) -> List[str]:
        """Normalize & validate channel identifiers.

        Parameters
        ----------
        channels : Iterable[str]
            Raw channel strings.

        Returns
        -------
        List[str]
            Canonical, unique ordered channel list (e.g., ['ai0','ai1']).

        Raises
        ------
        ValueError
            If any channel invalid or unsupported.
        """
        norm: List[str] = []
        for ch in channels:
            s = ch.strip().lower()
            if s.startswith("/"):
                s = s.split("/")[-1]
            if not s.startswith("ai"):
                raise ValueError(f"Only AI channels are supported, got '{ch}'")
            try:
                idx = int(s[2:])
            except ValueError:
                raise ValueError(f"Invalid AI channel '{ch}'")
            if idx not in self.valid_ai_indices:
                raise ValueError(f"Channel index out of range: ai{idx}")
            norm.append(f"ai{idx}")
        if not norm:
            raise ValueError("At least one AI channel must be specified")
        # unique & stable order
        uniq = []
        seen = set()
        for c in norm:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq

    def _reset_averaging_state(self, n_channels: int) -> None:
        """Reset internal averaging & downsampling state.

        Parameters
        ----------
        n_channels : int
            Current channel count.
        """
        self._avg_win = 1
        self._avg_tail = np.zeros((0, n_channels), dtype=np.float64)
        self._downsample_tail = np.zeros((0, n_channels), dtype=np.float64)

    @staticmethod
    def _rolling_mean_with_tail(y: np.ndarray, tail: Optional[np.ndarray], win: int) -> np.ndarray:
        """Causal rolling mean with continuity across blocks.

        Parameters
        ----------
        y : ndarray (N, C)
            New raw block.
        tail : ndarray | None ((win-1), C)
            Last raw samples from previous call (not averaged).
        win : int
            Window length (samples) > 1.

        Returns
        -------
        ndarray (N, C)
            Rolling average aligned with each input sample.
        """
        if win <= 1:
            return y
        n, c = y.shape
        if tail is None or tail.shape != (win - 1, c):
            # Initialize empty tail if shape mismatch
            tail = np.zeros((win - 1, c), dtype=y.dtype)

        # Concatenate previous tail + current block
        extended = np.vstack([tail, y])          # shape (win-1 + N, C)

        # Correct cumulative-sum based moving average (no off-by-one):
        # window ending at index k (0-based in extended) uses samples [k-win+1 .. k]
        csum = np.cumsum(extended, axis=0)       # shape (win-1 + N, C)
        # Build array of csum[k-win] with k spanning win-1 .. end
        # Prepend a zero row for k = win-1 (so k-win = -1 -> 0 vector)
        csum_padded = np.vstack([np.zeros((1, c), dtype=extended.dtype), csum])
        window_end = csum[win - 1:]              # shape (N, C)
        window_start = csum_padded[:-win][ : ]   # rows 0 .. N-1 correspond to csum[k-win]
        out = (window_end - window_start) / win  # shape (N, C)

        # Update tail with last win-1 raw samples for next call
        new_tail = extended[-(win - 1):] if win > 1 else extended[-0:]
        if tail.shape == new_tail.shape:
            tail[:] = new_tail
        else:
            # Should not happen, but guard
            tail = new_tail
        return out

    # -------------- Printing --------------
    def print_data(
        self,
        *,
        max_rows: Optional[int] = None,
        time_decimals: int = 3,
        value_decimals: int = 6,
    ) -> None:
        """Print accumulated samples in tabular form.

        Parameters
        ----------
        max_rows : int | None
            Limit number of displayed rows (head) if provided.
        time_decimals : int
            Decimal places for timestamp formatting.
        value_decimals : int
            Decimal places for channel value formatting.

        Notes
        -----
        Does nothing if no accumulated data present.
        """
        if not self._acc_values:
            print("No accumulated data (nothing has been read with accumulate=True).")
            return

        t = np.concatenate(self._acc_times)          # (N,)
        y = np.concatenate(self._acc_values)         # (N, C)
        channels = list(self.settings.channels)
        N, C = y.shape

        N_print = min(N, max_rows) if max_rows is not None else N

        time_fmt = f"{{:.{time_decimals}f}}"
        val_fmt = f"{{:.{value_decimals}f}}"

        headers = ["sample#", "timestamp_ms"] + channels
        col_widths = [len(h) for h in headers]

        # Determine column widths
        for i in range(N_print):
            col_widths[0] = max(col_widths[0], len(str(i + 1)))
            col_widths[1] = max(col_widths[1], len(time_fmt.format(t[i])))
            for c in range(C):
                col_widths[2 + c] = max(col_widths[2 + c], len(val_fmt.format(y[i, c])))

        def fmt(text: str, idx: int) -> str:
            return text.rjust(col_widths[idx])

        # Header
        print(" | ".join(fmt(h, i) for i, h in enumerate(headers)))
        print("-+-".join("-" * w for w in col_widths))

        # Rows
        for i in range(N_print):
            row = [
                fmt(str(i + 1), 0),
                fmt(time_fmt.format(t[i]), 1),
            ]
            for c in range(C):
                row.append(fmt(val_fmt.format(y[i, c]), 2 + c))
            print(" | ".join(row))

        if N_print < N:
            print(f"... ({N - N_print} more rows)")

    # -------------- Plotting --------------
    def plot_data(
        self,
        channels: Optional[Iterable[str]] = None,
        *,
        separate: bool = False,
        auto_ylim: bool = False,
        figsize: Optional[Tuple[int, int]] = None,
        show: bool = True,
        show_mean: bool = False,
    ):
        """Plot accumulated channel data vs timestamp.

        Parameters
        ----------
        channels : Iterable[str] | None
            Subset of channel names to plot. If None, uses all configured channels.
        separate : bool
            If True, each channel on its own subplot (shared x). If False, all on one axes.
        auto_ylim : bool
            If True, y-limits taken from data min/max of the selected channels.
            If False, uses configured v_min / v_max from settings.
        figsize : (int, int) | None
            Matplotlib figure size. If None a heuristic is used.
        show : bool
            If True, calls plt.show() before returning.
        show_mean : bool
            If True, draw horizontal mean line(s). Applied only when:
              - separate=True (each subplot gets its own mean), OR
              - a single channel is plotted on a combined axes.
            Ignored when multiple channels share one axes.

        Returns
        -------
        (fig, axes)
            Matplotlib Figure and list of Axes objects.

        Raises
        ------
        RuntimeError
            If no accumulated data is available.
        ValueError
            If any requested channel is not configured.
        """
        if not self._acc_values:
            raise RuntimeError("No accumulated data to plot (run read_data with accumulate=True).")

        # Determine channels to plot
        all_ch = list(self.settings.channels)
        if channels is None:
            sel = all_ch
        else:
            sel = list(channels)
            missing = [c for c in sel if c not in all_ch]
            if missing:
                raise ValueError(f"Requested channels not configured: {missing}")

        # Assemble data
        t = np.concatenate(self._acc_times)  # (N,)
        y = np.concatenate(self._acc_values)  # (N, C_total)
        ch_index = {c: i for i, c in enumerate(all_ch)}

        # Choose figure / axes
        if separate:
            n = len(sel)
            if figsize is None:
                figsize = (10, 2.2 * n)
            fig, axes = plt.subplots(n, 1, sharex=True, figsize=figsize)
            if n == 1:
                axes = [axes]
            for ax, ch in zip(axes, sel):
                data = y[:, ch_index[ch]]
                ax.plot(t, data, label=ch)
                ax.set_ylabel(ch)
                if auto_ylim:
                    dmin, dmax = float(np.nanmin(data)), float(np.nanmax(data))
                else:
                    dmin, dmax = self.settings.v_min, self.settings.v_max
                if dmax - dmin < 1e-9:
                    pad = 1e-3
                    dmin -= pad
                    dmax += pad
                ax.set_ylim(dmin, dmax)
                if show_mean:
                    m = float(np.nanmean(data))
                    ax.axhline(m, color="red", linestyle="--", linewidth=1.0, label="mean")
                ax.grid(True, alpha=0.3)
                ax.legend(loc="best")
            axes[-1].set_xlabel("Time (ms)")
        else:
            if figsize is None:
                figsize = (10, 4)
            fig, ax = plt.subplots(figsize=figsize)
            axes = [ax]
            mins, maxs = [], []
            for ch in sel:
                data = y[:, ch_index[ch]]
                ax.plot(t, data, label=ch)
                if auto_ylim:
                    mins.append(np.nanmin(data))
                    maxs.append(np.nanmax(data))
            if auto_ylim:
                dmin, dmax = float(np.nanmin(mins)), float(np.nanmax(maxs))
            else:
                dmin, dmax = self.settings.v_min, self.settings.v_max
            if dmax - dmin < 1e-9:
                pad = 1e-3
                dmin -= pad
                dmax += pad
            ax.set_ylim(dmin, dmax)
            ax.set_xlabel("Time (ms)")
            ax.set_ylabel("Voltage (V)")
            # Mean line only if a single channel in combined view
            if show_mean and len(sel) == 1:
                ch = sel[0]
                data = y[:, ch_index[ch]]
                m = float(np.nanmean(data))
                ax.axhline(m, color="red", linestyle="--", linewidth=1.0, label=f"{ch} mean")
            ax.legend()
            ax.grid(True, alpha=0.3)

        fig.tight_layout()
        if show:
            plt.show()
        return fig,

    def plot_realtime(
        self,
        channels: Optional[Iterable[str]] = None,
        *,
        interval_ms: Optional[float] = 50,
        window_ms: float = 4000.0,
        rolling_avg_ms: Optional[float] = None,
        rolling_avg: bool = False,
        separate: bool = False,
        auto_ylim: bool = False,
        show_mean: bool = False,
        max_points: int = 200,
    ):
        """Plot real-time streaming values for selected channels.

        Parameters
        ----------
        channels : Iterable[str] | None
            Channels to display (default all configured).
        interval_ms : float | None
            Target UI update interval. If None uses one sample period.
        window_ms : float
            Visible time span (scrolling) in milliseconds.
        rolling_avg_ms : float | None
            If set >0 apply same averaging (rolling or downsample) per update.
        rolling_avg : bool
            Meaningful only if rolling_avg_ms provided. True=rolling; False=downsample.
        separate : bool
            If True, one subplot per channel; else combined.
        auto_ylim : bool
            If True y-limits follow data in window; else use configured v_min/v_max.
        show_mean : bool
            Draw horizontal mean line (only if single channel combined or per-channel when separate).
        max_points : int
            Cap on stored points in ring buffer.

        Notes
        -----
        To minimize plotting latency, use sampling frequency around 20 Hz.
        Also keep interval_ms near (1000 / sampling_rate_hz) * small factor (e.g. 2–4).
        """
        if not self._running:
            raise RuntimeError("Call start() before plot_realtime().")

        all_ch = list(self.settings.channels)
        if channels is None:
            sel = all_ch
        else:
            sel = [c for c in channels]
            missing = [c for c in sel if c not in all_ch]
            if missing:
                raise ValueError(f"Requested channels not configured: {missing}")
        ch_index = {c: i for i, c in enumerate(all_ch)}
        n_sel = len(sel)

        fs = float(self.settings.sampling_rate_hz)
        if interval_ms is None:
            interval_ms = max(1.0, 1000.0 / fs)
        block_samples = max(1, int(round(interval_ms * fs / 1000.0)))

        # Buffers
        t_buf: List[float] = []
        y_buf: List[np.ndarray] = []  # each row (n_sel,)

        # Figure / axes
        if separate:
            fig, axes = plt.subplots(n_sel, 1, sharex=True, figsize=(10, 2.0 * n_sel))
            if n_sel == 1:
                axes = [axes]
            line_objs = []
            for ax, ch in zip(axes, sel):
                (ln,) = ax.plot([], [], label=ch)
                ln.set_antialiased(False)
                line_objs.append(ln)
                ax.set_ylabel(ch)
                ax.grid(True, alpha=0.3)
            axes[-1].set_xlabel("Time (ms)")
        else:
            fig, ax = plt.subplots(figsize=(10, 4))
            axes = [ax]
            line_objs = []
            for ch in sel:
                (ln,) = ax.plot([], [], label=ch)
                ln.set_antialiased(False)
                line_objs.append(ln)
            ax.set_xlabel("Time (ms)")
            ax.set_ylabel("Voltage (V)")
            ax.grid(True, alpha=0.3)
            ax.legend(loc="best")

        vmin_cfg, vmax_cfg = self.settings.v_min, self.settings.v_max
        window_ms = max(window_ms, interval_ms)

        def _trim():
            # Trim buffers to time window & max_points
            if not t_buf:
                return
            t_max = t_buf[-1]
            t_min_keep = t_max - window_ms
            # Find first index to keep
            k = 0
            while k < len(t_buf) and t_buf[k] < t_min_keep:
                k += 1
            if k > 0:
                del t_buf[:k]
                del y_buf[:k]
            # Cap total points
            if len(t_buf) > max_points:
                drop = len(t_buf) - max_points
                del t_buf[:drop]
                del y_buf[:drop]

        def _current_arrays():
            if not t_buf:
                return np.empty(0), np.empty((0, n_sel))
            t_arr = np.asarray(t_buf)
            y_arr = np.vstack(y_buf)
            return t_arr, y_arr

        def _set_ylim(ax_obj, data):
            if auto_ylim and data.size:
                dmin = float(np.nanmin(data))
                dmax = float(np.nanmax(data))
                if dmax - dmin < 1e-9:
                    pad = 1e-3
                    dmin -= pad
                    dmax += pad
            else:
                dmin, dmax = vmin_cfg, vmax_cfg
            ax_obj.set_ylim(dmin, dmax)

        mean_lines = []
        if show_mean and (separate or n_sel == 1):
            # Pre-create mean line objects
            if separate:
                for ax in axes:
                    (mline,) = ax.plot([], [], color="red", linestyle="--", linewidth=1.0, label="mean")
                    mean_lines.append(mline)
            else:
                (mline,) = axes[0].plot([], [], color="red", linestyle="--", linewidth=1.0, label="mean")
                mean_lines.append(mline)
                axes[0].legend(loc="best")

        def _update(_frame):
            # Acquire new block (not accumulated)
            t_new, y_new = self.read_data(
                number_of_samples_per_channel=block_samples,
                average_ms=rolling_avg_ms,
                rolling_avg=rolling_avg,
                accumulate=False,
            )
            if y_new.size == 0:
                return line_objs

            # Extract selected channels
            sel_block = y_new[:, [ch_index[c] for c in sel]]  # (B, n_sel)

            # Append to buffers
            t_buf.extend(t_new.tolist())
            for row in sel_block:
                y_buf.append(row.copy())

            _trim()
            t_arr, y_arr = _current_arrays()
            if t_arr.size == 0:
                return line_objs

            # Update lines
            if separate:
                for i, ax_ch in enumerate(axes):
                    line_objs[i].set_data(t_arr, y_arr[:, i])
                    _set_ylim(ax_ch, y_arr[:, i])
                    ax_ch.set_xlim(max(t_arr[0], t_arr[-1] - window_ms), t_arr[-1])
                    if show_mean:
                        m = float(np.nanmean(y_arr[:, i]))
                        mean_lines[i].set_data([t_arr[0], t_arr[-1]], [m, m])
                return line_objs + mean_lines
            else:
                ax = axes[0]
                for i, ln in enumerate(line_objs):
                    ln.set_data(t_arr, y_arr[:, i])
                _set_ylim(ax, y_arr)
                ax.set_xlim(max(t_arr[0], t_arr[-1] - window_ms), t_arr[-1])
                if show_mean and n_sel == 1:
                    m = float(np.nanmean(y_arr[:, 0]))
                    mean_lines[0].set_data([t_arr[0], t_arr[-1]], [m, m])
                    return line_objs + mean_lines
                return line_objs

        ani = animation.FuncAnimation(
            fig, _update, interval=interval_ms, blit=False
        )

        fig.tight_layout()
        plt.show()
        return


# Example usage (commented):
if __name__ == "__main__":
    settings = NIDAQSettings(device_name="Dev1", 
                             channels=["ai0", "ai1"], 
                             sampling_rate_hz=20.0,
                             terminal_config="RSE",)
    reader = NIDAQReader(settings)
    reader.start()
    try:
        # for _ in range(5):
        #     t, y = reader.read_data(number_of_samples_per_channel=200, average_ms=10)
        #     # t, y = reader.read_data(number_of_samples_per_channel=200, average_ms=10, rolling_avg=False)
        #     # t, y = reader.read_data(number_of_samples_per_channel=100)
        #     # print(t.shape, y.shape, y.mean(axis=0))
        
        # reader.read_data(number_of_samples_per_channel=1000)
        # reader.plot_data()  # all channels, shared y from v_min/v_max
        # reader.plot_data(auto_ylim=True)                 # all channels, auto y
        # reader.plot_data(channels=["ai0"], auto_ylim=True)
        # reader.plot_data(channels=["ai0","ai1"], separate=True, auto_ylim=True, show_mean=True)
        # reader.plot_realtime(interval_ms=50,
        #                  window_ms=500,
        #                  channels=["ai0", "ai1"],
        #                  separate=False,
        #                  auto_ylim=True,
        #                  rolling_avg=False,
        #                  show_mean=False)
        
        reader.plot_realtime(
            interval_ms=50,
            window_ms=4000,
            channels=["ai0","ai1"],
            separate=False,
            auto_ylim=True,
            rolling_avg_ms=None,
            rolling_avg=False,
            show_mean=False
        )
    finally:
        # reader.save_data("run.csv")
        # reader.print_data(max_rows=10)
        reader.close()
