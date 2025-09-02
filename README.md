# NI DAQ Reader

A Python application for real-time data acquisition from National Instruments (NI) USB-6211 and similar NI-DAQmx devices. This project provides both a high-level Python wrapper for NI-DAQmx hardware and a complete GUI application for data visualization, frequency analysis, and logging.

## Features

- **Real-time data acquisition** from multiple analog input channels
- **Per-channel programmable gain** for optimized signal resolution
- **Inter-channel delay control** for timing optimization and crosstalk reduction
- **Dual-domain visualization** with tabbed Time and Spectrum Analyzer views
- **Live frequency filtering** with multiple filter types (low-pass, high-pass, band-pass, band-stop, notch)
- **FFT spectrum analysis** with configurable windowing functions and frequency ranges
- **Device auto-detection** and hot-plug support
- **Statistics display** (min, max, mean for each channel)
- **Data export** to CSV with metadata
- **Graph screenshots** to high-resolution PNG images with timestamped filenames
- **Configurable sampling rates** and voltage ranges
- **Rolling average** and downsampling options
- **Professional GUI** built with PySide6 and pyqtgraph

## Prerequisites

### Required Software

1. **NI-DAQmx Driver**: Download and install from [NI Device Drivers](https://www.ni.com/en/support/downloads/drivers/download.ni-device-drivers.html)
   - This is essential for communicating with NI hardware
   - Choose the appropriate version for your operating system

2. **Python 3.8+** with required packages (see requirements.txt)

### Required Hardware

- National Instruments USB-6211 or compatible NI-DAQmx device
- Analog input signals to measure

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/sheramir/read_daq.git
   cd read_daq
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

   **Optional**: For frequency filtering functionality, install scipy:
   ```bash
   pip install scipy
   ```

3. Ensure your NI device is connected and recognized by the system

## Quick Start

### Running the GUI Application

```bash
python main.py
```

The application will automatically detect connected NI devices and allow you to:
- Select analog input channels (AI0-AI15)
- Configure sampling parameters
- Start real-time data acquisition
- View live plots with statistics
- Save data to CSV files

**Note**: The application now uses a modular architecture for better maintainability. The main entry point (`main.py`) launches the modular version which provides the same functionality as before with enhanced features like a menu system, help dialogs, and improved error handling.

### Using the NIDAQReader Class Programmatically

```python
from niDAQ import NIDAQReader, NIDAQSettings

# Configure acquisition settings
settings = NIDAQSettings(
    device_name="Dev1",
    channels=["ai0", "ai1"],
    sampling_rate_hz=200.0,
    v_min=-1.0,
    v_max=3.5,
    terminal_config="RSE"
)

# Configure per-channel gains for optimal resolution
settings.set_channel_range("ai0", -10.0, 10.0)  # ±10V for high-voltage signal
settings.set_channel_range("ai1", -0.1, 0.1)    # ±0.1V for low-voltage signal

# Create reader and start acquisition
reader = NIDAQReader(settings)
reader.start()

try:
    # Read 100 samples per channel
    timestamps_ms, voltages = reader.read_data(number_of_samples_per_channel=100)
    
    # Optional: apply 10ms rolling average
    timestamps_ms, voltages = reader.read_data(
        number_of_samples_per_channel=200, 
        average_ms=10
    )
    
    # Plot the data
    reader.plot_data()
    
    # Save to file
    reader.save_data("measurement.csv")
    
finally:
    reader.close()
```

## Per-Channel Programmable Gain

The NI USB-6211 supports programmable gain amplifiers (PGA) for each analog input channel, allowing you to optimize signal resolution by setting appropriate voltage ranges for different signal types.

### Available Voltage Ranges

The USB-6211 supports the following voltage ranges:
- **±10V, ±5V, ±2V, ±1V, ±0.5V, ±0.2V, ±0.1V** (bipolar)
- **0-10V, 0-5V, 0-2V, 0-1V** (unipolar)

### Resolution Benefits

Using appropriate ranges significantly improves measurement resolution:

| Range | Span | 16-bit Resolution |
|-------|------|-------------------|
| ±10V | 20V | 0.305 mV |
| ±1V | 2V | 0.031 mV |
| ±0.1V | 0.2V | 0.003 mV |

### Programmatic Configuration

```python
from niDAQ import NIDAQSettings

# Create settings with per-channel ranges
settings = NIDAQSettings(
    channels=["ai0", "ai1", "ai2", "ai3"],
    v_min=-10.0, v_max=10.0  # Default range for unconfigured channels
)

# Configure individual channel ranges
settings.set_channel_range("ai0", -10.0, 10.0)  # ±10V for high-voltage signal
settings.set_channel_range("ai1", -1.0, 1.0)    # ±1V for medium signal
settings.set_channel_range("ai2", -0.1, 0.1)    # ±0.1V for small signal
settings.set_channel_range("ai3", 0.0, 5.0)     # 0-5V for unipolar signal

# Get available preset ranges
common_ranges = NIDAQSettings.get_common_ranges()
print(common_ranges)  # Shows all available ranges

# Check configured range for a channel
v_min, v_max = settings.get_channel_range("ai0")
```

### GUI Configuration

The GUI application includes a **"Configure Channel Gains"** button that opens a dialog for setting individual channel ranges:

1. **Enable Custom Range**: Check the box for channels requiring different ranges
2. **Select Preset**: Choose from common ranges or select "Custom"
3. **Custom Values**: Set precise voltage limits for specialized applications
4. **Statistics Display**: The statistics table shows the configured range for each channel

### Best Practices

1. **Match signal amplitude**: Use the smallest range that accommodates your signal
2. **Leave headroom**: Allow 10-20% margin to prevent clipping
3. **Consider noise**: Smaller ranges may amplify noise along with signal
4. **Mixed signals**: Different channels can have completely different ranges

## Inter-Channel Delay Control

The application provides precise control over the timing between channel conversions, which is crucial for reducing crosstalk and optimizing signal quality in multi-channel acquisitions.

### What is Inter-Channel Delay?

When sampling multiple channels, the NI USB-6211 uses a multiplexer to rapidly switch between channels. The inter-channel delay controls how long the system waits between switching from one channel to the next, allowing for:

- **Signal settling time** after multiplexer switching
- **Crosstalk reduction** between adjacent channels  
- **External circuit compatibility** with specific timing requirements
- **Optimization for different signal conditioning**

### Configuration Options

**GUI Control**: The "Inter-channel delay" spinbox in the left panel allows setting delays from 0.0 to 10,000.0 microseconds.

**Settings**:
- **0.0 µs**: Automatic/fastest conversion rate (hardware optimized)
- **4.0+ µs**: Manual delay settings (hardware minimum ~4µs for USB-6211)
- **Higher values**: Slower conversion but better settling/isolation

### Programmatic Configuration

```python
from niDAQ import NIDAQSettings

# Create settings with inter-channel delay
settings = NIDAQSettings(
    channels=["ai0", "ai1", "ai2"],
    sampling_rate_hz=1000.0,
    inter_channel_delay_us=10.0  # 10 microsecond delay between channels
)

# Get maximum conversion rate information
reader = NIDAQReader(settings)
reader.start()
max_rate = reader.get_max_conversion_rate()  # Returns Hz
min_delay_us = 1.0 / max_rate * 1e6 if max_rate else None
print(f"Minimum possible delay: {min_delay_us:.2f} µs")
reader.close()
```

### Hardware Limitations

The NI USB-6211 has a maximum AI conversion rate of approximately **250 kHz**, which corresponds to a **minimum delay of ~4.0 µs**. The application automatically:

- **Validates delay settings** against hardware limits
- **Shows warnings** when requested delays are too small
- **Uses maximum rate** when delays exceed hardware capabilities
- **Provides feedback** on actual achievable timing

### Use Cases

| Application | Typical Delay | Benefit |
|------------|---------------|---------|
| High-speed digital signals | 0 µs (auto) | Maximum throughput |
| Mixed analog signals | 5-10 µs | Reduced crosstalk |
| Thermocouples/RTDs | 50-100 µs | Complete settling |
| External multiplexers | 100+ µs | Circuit compatibility |

## File Structure

### Core Files

- **`niDAQ.py`** - Main DAQ wrapper classes (see detailed documentation below)
- **`DAQMainWindow.py`** - Complete GUI application window with all UI components
- **`freq_filters.py`** - Digital signal processing library with frequency filtering functions
- **`settings_manager.py`** - Settings persistence and validation system
- **`main.py`** - Application entry point
- **`requirements.txt`** - Python package dependencies
- **`pyproject.toml`** - Project configuration

### Tests and Examples

All test scripts, examples, and utility programs are organized in the **`tests/`** folder:

- **Example Programs** - Demonstrations of key features (channel gains, delays, screenshots)
- **Test Scripts** - Unit tests and validation programs for core functionality
- **Utility Tools** - Device discovery and system checking tools
- **Documentation** - Working examples showing best practices

See **`tests/README.md`** for detailed descriptions of each file and how to run them.

## NIDAQReader Class Documentation

The `NIDAQReader` class in `niDAQ.py` is the core component for interfacing with NI-DAQmx hardware.

### Key Classes

#### `NIDAQSettings`
Configuration dataclass for DAQ parameters:

```python
@dataclass
class NIDAQSettings:
    device_name: str = "Dev1"           # NI device identifier
    sampling_rate_hz: float = 200.0     # Sampling frequency
    v_min: float = -1.0                 # Minimum input voltage
    v_max: float = 3.5                  # Maximum input voltage
    terminal_config: str = "RSE"        # Input configuration
    channels: List[str] = ["ai0"]       # Analog input channels
    adc_bits: int = 16                  # ADC resolution
```

**Terminal Configuration Options:**
- `"RSE"` - Referenced Single-Ended
- `"NRSE"` - Non-Referenced Single-Ended  
- `"DIFF"` - Differential
- `"PSEUDO-DIFF"` - Pseudo-Differential

#### `NIDAQReader`
Main class for data acquisition operations:

##### Core Methods

**Lifecycle Management:**
- `start()` - Initialize and start continuous acquisition
- `stop()` / `close()` - Stop acquisition and release hardware resources

**Data Acquisition:**
- `read_data(number_of_samples_per_channel, average_ms=None, *, rolling_avg=True, timeout=10.0, accumulate=True)`
  - Returns: `(timestamps_ms, voltages)` as numpy arrays
  - `timestamps_ms`: (N,) array of timestamps in milliseconds
  - `voltages`: (N, C) array where N=samples, C=channels
  - `average_ms`: Optional rolling average window in milliseconds
  - `rolling_avg`: True for moving average, False for downsampling

**Device Discovery:**
- `list_devices()` - Static method to enumerate available NI devices
- `list_ai_channels(device_name)` - List available analog input channels

**Data Management:**
- `save_data(filename, format="csv", include_json_sidecar=True)` - Export data with metadata
- `print_data(max_rows=None, time_decimals=3, value_decimals=6)` - Console output
- `plot_data(channels=None, separate=False, auto_ylim=False)` - Static plotting
- `plot_realtime(...)` - Live animated plotting

##### Dynamic Configuration
Settings can be changed during operation:
- `set_input(channels)` - Change active channels
- `set_terminal_config(terminal_config)` - Change input configuration
- `set_voltage_range(v_min, v_max)` - Adjust voltage range
- `set_sampling(rate_hz)` - Modify sampling rate

### Example Usage Patterns

#### Basic Single-Shot Measurement
```python
settings = NIDAQSettings(channels=["ai0", "ai1"], sampling_rate_hz=1000)
with NIDAQReader(settings) as reader:
    reader.start()
    t, y = reader.read_data(1000)  # 1 second of data
    print(f"Acquired {len(t)} samples from {y.shape[1]} channels")
```

#### Continuous Monitoring with Averaging
```python
reader = NIDAQReader(settings)
reader.start()
try:
    while monitoring:
        # Get 100ms worth of data, averaged over 10ms windows
        t, y = reader.read_data(
            number_of_samples_per_channel=100,
            average_ms=10,
            rolling_avg=False  # Downsample for efficiency
        )
        # Process data...
finally:
    reader.save_data("session.csv")
    reader.close()
```

#### Real-time Plotting
```python
reader = NIDAQReader(settings)
reader.start()
try:
    # Launch real-time plot (blocking)
    reader.plot_realtime(
        channels=["ai0", "ai1"],
        interval_ms=50,      # 50ms update rate
        window_ms=5000,      # 5 second window
        rolling_avg_ms=20,   # 20ms smoothing
        separate=True,       # Separate subplots
        auto_ylim=True       # Auto-scale Y axis
    )
finally:
    reader.close()
```

## Frequency Filtering and Signal Processing

The application includes a comprehensive digital signal processing library (`freq_filters.py`) for real-time frequency filtering:

### Available Filter Types

```python
from freq_filters import low_pass, high_pass, band_pass, band_stop, notch_50hz, notch_60hz

# Low-pass filter (remove high frequencies)
filtered_signal = low_pass(signal, time_ms, cutoff_hz=100, order=4)

# High-pass filter (remove low frequencies)  
filtered_signal = high_pass(signal, time_ms, cutoff_hz=10, order=4)

# Band-pass filter (keep frequencies in range)
filtered_signal = band_pass(signal, time_ms, low_cutoff=10, high_cutoff=100, order=4)

# Band-stop filter (remove frequencies in range)
filtered_signal = band_stop(signal, time_ms, low_cutoff=45, high_cutoff=55, order=4)

# Power line noise removal
filtered_signal = notch_50hz(signal, time_ms, order=4)  # For 50Hz power systems
filtered_signal = notch_60hz(signal, time_ms, order=4)  # For 60Hz power systems
```

### Filter Parameters

- **`signal`**: Input data as numpy array (N, C) where N=samples, C=channels
- **`time_ms`**: Time array in milliseconds for accurate frequency calculation
- **`cutoff_hz`**: Cutoff frequency in Hz
- **`order`**: Filter order (1-10), higher order = steeper rolloff
- **Returns**: Filtered signal with same shape as input

### GUI Integration

The frequency filtering is seamlessly integrated into the GUI:
- **Real-time filtering** applied to incoming data
- **Filter controls** in the right panel for easy adjustment
- **Visual feedback** showing current filter status and parameters
- **Statistics and spectrum** computed on filtered data when enabled

## Spectrum Analysis

The Spectrum Analyzer tab provides professional frequency domain analysis:

### FFT Analysis Features

- **Real-time FFT** computation with configurable parameters
- **Window functions** to reduce spectral leakage (Hanning, Hamming, Blackman, Rectangle)
- **Power spectral density** calculation with proper normalization
- **Frequency range limiting** for focused analysis
- **Logarithmic scaling** in dB for professional presentation

### Usage Tips

1. **Window Selection**: Use Hanning or Hamming for general signals, Blackman for high dynamic range
2. **FFT Size**: Larger sizes provide better frequency resolution but slower updates
3. **Frequency Range**: Set to focus on your signal's frequency content
4. **Filtering**: Apply filters to see their effect in both time and frequency domains

## GUI Application Features

The main GUI application (`DAQMainWindow.py`) provides:

### Left Panel - Acquisition Settings
- **Device Selection** - Automatic device detection with hot-plug support
- **Channel Configuration** - Enable/disable up to 16 analog inputs (AI0-AI15)
- **Per-Channel Gains** - Configure individual voltage ranges for optimal resolution
- **Input Settings** - Terminal configuration, voltage range, sampling rate
- **Statistics Table** - Real-time min/max/mean values and voltage ranges for each active channel

### Right Panel - Visualization and Data Management

#### Tabbed Plot Interface
- **Time Analyzer Tab** - Real-time amplitude vs time plotting
- **Spectrum Analyzer Tab** - Power spectral density vs frequency using FFT

#### Real-time Frequency Filtering
- **Filter Types**: Low-pass, High-pass, Band-pass, Band-stop, 50Hz/60Hz notch
- **Configurable Parameters**: Cutoff frequencies, filter order (1-10)
- **Real-time Application**: Filters apply to both time and frequency domain plots
- **Visual Status**: Real-time filter status indicator

#### Spectrum Analysis Controls
- **FFT Window Functions**: Hanning, Hamming, Blackman, Rectangle
- **FFT Size**: Auto or manual selection (256, 512, 1024, 2048, 4096 points)
- **Frequency Range**: Configurable maximum frequency display
- **Power Scale**: Logarithmic scale in dB for professional analysis

#### Plot Controls and Data Management
- **Auto-scaling** and manual range controls
- **Channel visibility** toggles with color-coded legends
- **File Management** - Directory selection and CSV export with metadata
- **Graph Screenshots** - Capture current graph as high-resolution PNG with automatic timestamped naming
- **Status Display** - Connection status and operation feedback

#### Graph Screenshot Feature
The application includes a professional graph capture feature accessible via the "📷 Capture Graph" button:

**Filename Format**: `graph-[type]-[date]-[time]-[channels].png`
- `[type]`: "time" for Time Analyzer or "spectrum" for Spectrum Analyzer
- `[date]`: MM.DD.YY format (e.g., "08.29.25")
- `[time]`: HHMM format in 24-hour time (e.g., "0900" for 9:00 AM)
- `[channels]`: Active channel names (e.g., "a1a5" for channels ai1 and ai5)

**Examples**:
- `graph-time-08.29.25-0900-a1a5.png` - Time domain at 9:00 AM with channels ai1 and ai5
- `graph-spectrum-08.29.25-1430-a0a2a3.png` - Spectrum at 2:30 PM with channels ai0, ai1, ai3
- `graph-time-08.29.25-2115-nodata.png` - Time domain at 9:15 PM with no visible channels

**Features**:
- High-resolution output (1920×1080 with anti-aliasing)
- Captures exactly what's displayed on screen
- Automatic file naming prevents overwrites
- Requires save directory to be selected first

### Key Features
- **Hot-plug Support** - Automatically detects when devices are connected/disconnected
- **Thread-safe Operation** - Non-blocking data acquisition using QThread workers
- **Data Persistence** - Automatic accumulation of all acquired samples
- **Professional UI** - Modern interface with proper error handling
- **Dual-domain Analysis** - Simultaneous time and frequency domain visualization

## Troubleshooting

### Common Issues

1. **"No device found"**
   - Ensure NI-DAQmx drivers are installed
   - Check device connection and power
   - Verify device appears in NI MAX (Measurement & Automation Explorer)

2. **Import errors for nidaqmx**
   - Install: `pip install nidaqmx`
   - Ensure NI-DAQmx runtime is installed

3. **Filtering unavailable message**
   - Install scipy for frequency filtering: `pip install scipy`
   - Restart the application after installation

4. **Permission errors**
   - Run as administrator (Windows) or with appropriate permissions
   - Check if another application is using the device

5. **Data acquisition errors**
   - Verify voltage range matches your signal levels
   - Check sampling rate is supported by your device
   - Ensure selected channels exist on your device

## Development

### Project Structure
- Uses modern Python practices with type hints and dataclasses
- PySide6 for cross-platform GUI development
- pyqtgraph for high-performance real-time plotting
- Modular design separating DAQ logic from GUI components

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes with appropriate tests
4. Submit a pull request

## License

This project is available under an open source license. See the repository for specific license terms.

## Support

For issues related to:
- **Hardware setup**: Consult NI documentation and support
- **Software bugs**: Open an issue on this repository
- **Feature requests**: Submit an issue with detailed requirements