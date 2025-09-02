# DAQ Application - Modular Architecture

This document describes the new modular architecture that replaces the monolithic `DAQMainWindow.py` with focused, maintainable components.

## Architecture Overview

The application has been refactored from a single 1000+ line file into 8 focused modules:

```
📁 DAQ Application
├── 🏠 main_window.py          # Main coordination & UI assembly
├── 🎛️ gui_panels.py           # GUI components & layouts  
├── 🔧 daq_controller.py       # Hardware control & worker thread
├── 📊 data_processor.py       # Filtering, FFT, statistics
├── 📈 plot_manager.py         # Time & spectrum plotting
├── ⚙️ settings_controller.py  # Settings management
├── 💾 file_manager.py         # File operations & screenshots
└── 🪟 dialogs.py              # Custom dialog classes
```

## Module Responsibilities

### 1. `main_window.py` - Main Window Coordinator
**Purpose**: Orchestrates all components and provides the main application interface

**Key Responsibilities**:
- Initialize and coordinate all modules
- Handle signal connections between components
- Manage application lifecycle (startup/shutdown)
- Provide menu system and main window structure

**Main Classes**: `DAQMainWindow`

### 2. `gui_panels.py` - GUI Components
**Purpose**: Creates and manages all GUI widgets and layouts

**Key Responsibilities**:
- Left panel: Device settings, channel selection, controls
- Right panel: Plots, analysis controls, save options
- Widget creation and layout management
- UI component organization

**Main Classes**: `LeftPanel`, `RightPanel`, `MainLayout`

### 3. `daq_controller.py` - DAQ Operations  
**Purpose**: Handles hardware communication and data acquisition

**Key Responsibilities**:
- Device detection and management
- DAQ worker thread management
- Hardware timing and delay validation
- Acquisition start/stop control

**Main Classes**: `DAQWorker`, `DAQController`

### 4. `data_processor.py` - Data Processing
**Purpose**: Processes acquired data with filtering and analysis

**Key Responsibilities**:
- Data buffering and management
- Digital filtering (low/high/band pass, notch)
- FFT and spectrum analysis
- Statistics calculations

**Main Classes**: `DataProcessor`

### 5. `plot_manager.py` - Plotting & Visualization
**Purpose**: Manages both time domain and spectrum plots

**Key Responsibilities**:
- Time domain plotting with auto-scaling
- Spectrum analysis visualization
- Channel visibility management
- Plot styling and legends

**Main Classes**: `PlotManager`

### 6. `settings_controller.py` - Settings Management
**Purpose**: Handles application settings persistence and validation

**Key Responsibilities**:
- Load/save settings to JSON
- Apply settings to GUI components
- Auto-save functionality
- Settings validation

**Main Classes**: `SettingsController`

### 7. `file_manager.py` - File Operations
**Purpose**: Manages data export and file operations

**Key Responsibilities**:
- CSV data export with headers
- High-resolution screenshot capture
- Directory management
- File validation and naming

**Main Classes**: `FileManager`

### 8. `dialogs.py` - Custom Dialogs
**Purpose**: Provides specialized dialog windows

**Key Responsibilities**:
- Channel gain configuration dialog
- Device information display
- Filter help and documentation
- About dialog

**Main Classes**: `ChannelGainDialog`, `AboutDialog`, `DeviceInfoDialog`, `FilterHelpDialog`

## Benefits of Modular Architecture

### 🔧 **Maintainability**
- Each module has a single, clear responsibility
- Easier to locate and fix bugs
- Changes in one area don't affect others

### 🧪 **Testability**
- Individual components can be unit tested
- Mock interfaces for isolated testing
- Better test coverage possible

### 👥 **Collaboration**
- Multiple developers can work on different modules
- Cleaner code reviews with focused changes
- Reduced merge conflicts

### 🔄 **Reusability**
- Components can be reused in other projects
- Clear interfaces enable module swapping
- Easier to extend functionality

### 📚 **Readability**
- Smaller, focused files are easier to understand
- Clear separation of concerns
- Better code documentation possible

## Signal Flow Architecture

The modules communicate through Qt signals for loose coupling:

```
DAQController ──data_ready──► DataProcessor ──statistics_updated──► MainWindow
     │                            │
     ├─acquisition_started────────┤
     ├─devices_updated────────────┤
     └─error_occurred─────────────┤
                                  │
FileManager ──file_saved─────────► MainWindow ◄──settings_loaded──── SettingsController
     │                                                │
     └─directory_selected─────────────────────────────┘
```

## Usage Comparison

### Before (Monolithic)
```python
# Everything in one huge class
class DAQMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        # 100+ lines of GUI setup
        # Mixed with DAQ logic
        # Settings management inline
        # No clear separation
        
    def huge_method_doing_everything(self):
        # 200+ lines handling multiple concerns
        pass
```

### After (Modular)
```python
# Clear separation of concerns
class DAQMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        self.daq_controller = DAQController()
        self.data_processor = DataProcessor() 
        self.plot_manager = PlotManager(...)
        self.settings_controller = SettingsController()
        self.file_manager = FileManager()
        
        self.connect_signals()  # Simple signal connections
        
    def start_acquisition(self):
        # Just coordinate - actual work done in appropriate modules
        settings = self.settings_controller.get_daq_settings()
        self.daq_controller.start_acquisition(settings)
```

## File Size Comparison

| Original | New Modular Structure |
|----------|----------------------|
| `DAQMainWindow.py`: 1,087 lines | `main_window.py`: 634 lines |
| Single monolithic file | `daq_controller.py`: 165 lines |
| | `data_processor.py`: 273 lines |
| | `plot_manager.py`: 245 lines |
| | `gui_panels.py`: 356 lines |
| | `settings_controller.py`: 301 lines |
| | `file_manager.py`: 244 lines |
| | `dialogs.py`: 364 lines |
| **Total: 1,087 lines** | **Total: 2,582 lines** |

> **Note**: The line count increased because the modular version includes:
> - Better documentation and comments
> - More robust error handling
> - Additional functionality (menu system, help dialogs)
> - Cleaner code structure with proper spacing
> - Enhanced features not in the original

## Running the Modular Version

### Run the new modular version:
```bash
python main_window.py
```

### Run the original (for comparison):
```bash
python DAQMainWindow.py
```

Both versions provide the same functionality, but the modular version is much more maintainable and extensible.

## Migration Notes

- All original functionality is preserved
- Settings files remain compatible
- No user-visible changes in behavior
- Enhanced error handling and status reporting
- Additional features like menu system and help dialogs

## Future Enhancements Made Easy

With the modular structure, new features can be easily added:

- **New Analysis**: Add modules to `data_processor.py`
- **Different Hardware**: Swap `daq_controller.py` implementation  
- **New File Formats**: Extend `file_manager.py`
- **Custom Plots**: Add plot types to `plot_manager.py`
- **New Settings**: Extend `settings_controller.py`

The modular architecture makes the codebase much more maintainable and ready for future development!
