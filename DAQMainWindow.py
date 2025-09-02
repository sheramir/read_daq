from PySide6 import QtWidgets, QtCore
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
import numpy as np
import csv
import datetime
import os
from niDAQ import NIDAQReader, NIDAQSettings
from settings_manager import SettingsManager

# Try to import filtering functions
try:
    from freq_filters import low_pass, high_pass, band_pass, band_stop, notch_50hz, notch_60hz
    FILTERS_AVAILABLE = True
except ImportError:
    FILTERS_AVAILABLE = False
    import warnings
    warnings.warn("freq_filters not available. Install scipy for filtering functionality.")

class DAQWorker(QtCore.QThread):
    data_ready = QtCore.Signal(np.ndarray, np.ndarray)  # t, y
    error = QtCore.Signal(str)

    def __init__(self, settings, samples_per_read, avg_ms):
        super().__init__()
        self.settings = settings
        self.samples_per_read = samples_per_read
        self.avg_ms = avg_ms
        self.running = False

    def run(self):
        try:
            reader = NIDAQReader(self.settings)
            reader.start()
            self.running = True
            while self.running:
                t, y = reader.read_data(
                    number_of_samples_per_channel=self.samples_per_read,
                    average_ms=self.avg_ms if self.avg_ms > 0 else None,
                    accumulate=True,
                    timeout=1.0,
                )
                self.data_ready.emit(t, y)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            try:
                reader.stop()
            except Exception:
                pass

    def stop(self):
        self.running = False

class DAQMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NI USB-6211 DAQ")
        self.resize(1400, 900)
        self.worker = None
        self.history_t = []
        self.history_y = []
        self.channel_colors = [
            (255, 0, 0), (0, 128, 255), (0, 200, 0), (255, 128, 0),
            (128, 0, 255), (0, 200, 200), (200, 200, 0), (128, 128, 128),
            (255, 0, 128), (0, 255, 128), (128, 255, 0), (128, 0, 0),
            (0, 128, 0), (0, 0, 128), (128, 128, 0), (128, 0, 128)
        ]
        self._last_devices = tuple()  # track last seen device list
        self.save_directory = None  # Selected directory for saving files
        # Filter settings
        self.filter_enabled = False
        self.filter_type = "low_pass"
        self.filter_cutoff1 = 100.0  # Primary cutoff frequency
        self.filter_cutoff2 = 200.0  # Secondary cutoff (for band filters)
        self.filter_order = 4
        # Initialize plot curves lists
        self.curves = []
        self.spectrum_curves = []
        
        # Initialize settings manager and load settings
        self.settings_manager = SettingsManager()
        self.app_settings = self.settings_manager.load_settings()
        
        # Initialize per-channel ranges from loaded settings
        self.channel_ranges = self.app_settings.get("channel_ranges", {})
        
        self.setup_ui()
        
        # Apply loaded settings to GUI BEFORE connecting auto-save signals
        self.apply_settings_to_gui()
        
        # Now setup signals (including auto-save)
        self.setup_signals()
        
        # Initialize filter UI state (only if filters available)
        if FILTERS_AVAILABLE:
            self.on_filter_type_changed()
        self.detect_devices()
        
        # Restore device selection after device detection
        self.restore_device_selection()
        
        self.start_device_polling()

    def setup_ui(self):
        # Left: Acquisition Settings
        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        # Device
        self.deviceSelector = QtWidgets.QComboBox()
        left_layout.addWidget(QtWidgets.QLabel("Device:"))
        left_layout.addWidget(self.deviceSelector)
        # Input Config
        self.inputConfigCombo = QtWidgets.QComboBox()
        self.inputConfigCombo.addItems(["RSE", "NRSE", "DIFF", "PSEUDO-DIFF"])
        left_layout.addWidget(QtWidgets.QLabel("Input Configuration:"))
        left_layout.addWidget(self.inputConfigCombo)
        # Voltage Range
        self.maxVoltSpin = QtWidgets.QDoubleSpinBox()
        self.maxVoltSpin.setRange(-10, 10)
        self.maxVoltSpin.setValue(3.5)
        self.minVoltSpin = QtWidgets.QDoubleSpinBox()
        self.minVoltSpin.setRange(-10, 10)
        self.minVoltSpin.setValue(-1.0)
        left_layout.addWidget(QtWidgets.QLabel("Max Input Limit (V):"))
        left_layout.addWidget(self.maxVoltSpin)
        left_layout.addWidget(QtWidgets.QLabel("Min Input Limit (V):"))
        left_layout.addWidget(self.minVoltSpin)
        # Sampling
        self.rateSpin = QtWidgets.QSpinBox()
        self.rateSpin.setRange(1, 100000)
        self.rateSpin.setValue(200)
        self.samplesSpin = QtWidgets.QSpinBox()
        self.samplesSpin.setRange(1, 100000)
        self.samplesSpin.setValue(100)
        self.avgMsSpin = QtWidgets.QSpinBox()
        self.avgMsSpin.setRange(0, 10000)
        self.avgMsSpin.setValue(0)
        self.delaySpin = QtWidgets.QDoubleSpinBox()
        self.delaySpin.setRange(0.0, 10000.0)  # 0 to 10,000 microseconds
        self.delaySpin.setValue(0.0)
        self.delaySpin.setSuffix(" µs")
        self.delaySpin.setDecimals(2)
        self.delaySpin.setToolTip("Inter-channel conversion delay (0 = automatic/fastest)")
        left_layout.addWidget(QtWidgets.QLabel("Rate (Hz):"))
        left_layout.addWidget(self.rateSpin)
        left_layout.addWidget(QtWidgets.QLabel("Samples to Read:"))
        left_layout.addWidget(self.samplesSpin)
        left_layout.addWidget(QtWidgets.QLabel("Average time span [ms]:"))
        left_layout.addWidget(self.avgMsSpin)
        left_layout.addWidget(QtWidgets.QLabel("Inter-channel delay:"))
        left_layout.addWidget(self.delaySpin)
        # Channel Selection
        left_layout.addWidget(QtWidgets.QLabel("Channels:"))
        self.aiChecks = []
        grid = QtWidgets.QGridLayout()
        for i in range(16):
            cb = QtWidgets.QCheckBox(f"AI{i}")
            cb.setChecked(i < 2)
            self.aiChecks.append(cb)
            grid.addWidget(cb, i // 4, i % 4)
        left_layout.addLayout(grid)
        
        # Per-channel gain configuration button
        self.configGainBtn = QtWidgets.QPushButton("Configure Channel Gains")
        self.configGainBtn.setToolTip("Set individual voltage ranges for each channel")
        left_layout.addWidget(self.configGainBtn)
        
        # Initialize per-channel ranges storage
        self.channel_ranges = {}  # Will store {channel: (v_min, v_max)} for custom ranges
        
        # Control buttons
        self.startBtn = QtWidgets.QPushButton("Start")
        self.stopBtn = QtWidgets.QPushButton("Stop")
        self.stopBtn.setEnabled(False)
        left_layout.addWidget(self.startBtn)
        left_layout.addWidget(self.stopBtn)
        
        # Statistics table
        stats_group = QtWidgets.QGroupBox("Signal Statistics")
        stats_layout = QtWidgets.QVBoxLayout(stats_group)
        self.stats_table = QtWidgets.QTableWidget()
        self.stats_table.setColumnCount(5)
        self.stats_table.setHorizontalHeaderLabels(["Channel", "Range", "Min (V)", "Max (V)", "Mean (V)"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.setMaximumHeight(200)
        self.stats_table.setAlternatingRowColors(True)
        stats_layout.addWidget(self.stats_table)
        left_layout.addWidget(stats_group)
        
        left_layout.addStretch()

        # Right: Live Plot & Save
        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        
        # Create tabbed plot widget
        self.plot_tabs = QtWidgets.QTabWidget()
        
        # Time Analyzer Tab (existing plot)
        time_tab = QtWidgets.QWidget()
        time_layout = QtWidgets.QVBoxLayout(time_tab)
        self.plot = pg.PlotWidget(title="Amplitude vs Time (ms)")
        self.plot.setBackground("k")
        time_layout.addWidget(self.plot)
        self.plot_tabs.addTab(time_tab, "Time Analyzer")
        
        # Spectrum Analyzer Tab (FFT plot)
        spectrum_tab = QtWidgets.QWidget()
        spectrum_layout = QtWidgets.QVBoxLayout(spectrum_tab)
        self.spectrum_plot = pg.PlotWidget(title="Power Spectral Density")
        self.spectrum_plot.setBackground("k")
        self.spectrum_plot.setLabel("left", "Power", units="dB")
        self.spectrum_plot.setLabel("bottom", "Frequency", units="Hz")
        # Don't set log mode initially - we'll handle it manually
        spectrum_layout.addWidget(self.spectrum_plot)
        self.plot_tabs.addTab(spectrum_tab, "Spectrum Analyzer")
        
        # Make plot tabs take most of the vertical space (80%)
        right_layout.addWidget(self.plot_tabs, 4)  # Plot tabs get 4 parts
        
        self.autoScaleCheck = QtWidgets.QCheckBox("Auto-scale")
        self.autoScaleCheck.setChecked(True)
        right_layout.addWidget(self.autoScaleCheck)
        
        # Spectrum Analyzer Controls
        spectrum_group = QtWidgets.QGroupBox("Spectrum Analyzer Settings")
        spectrum_layout = QtWidgets.QHBoxLayout(spectrum_group)
        
        # FFT Window Type
        spectrum_layout.addWidget(QtWidgets.QLabel("Window:"))
        self.fftWindowCombo = QtWidgets.QComboBox()
        self.fftWindowCombo.addItems(["Hanning", "Hamming", "Blackman", "Rectangle"])
        self.fftWindowCombo.setCurrentText("Hanning")
        spectrum_layout.addWidget(self.fftWindowCombo)
        
        # FFT Size
        spectrum_layout.addWidget(QtWidgets.QLabel("FFT Size:"))
        self.fftSizeCombo = QtWidgets.QComboBox()
        self.fftSizeCombo.addItems(["Auto", "256", "512", "1024", "2048", "4096"])
        self.fftSizeCombo.setCurrentText("Auto")
        spectrum_layout.addWidget(self.fftSizeCombo)
        
        # Frequency range
        spectrum_layout.addWidget(QtWidgets.QLabel("Max Freq (Hz):"))
        self.maxFreqSpin = QtWidgets.QSpinBox()
        self.maxFreqSpin.setRange(1, 50000)
        self.maxFreqSpin.setValue(100)  # Default to 100 Hz
        spectrum_layout.addWidget(self.maxFreqSpin)
        
        right_layout.addWidget(spectrum_group)
        
        # Frequency Filtering Controls
        filter_group = QtWidgets.QGroupBox("Frequency Filtering")
        filter_layout = QtWidgets.QVBoxLayout(filter_group)
        
        if not FILTERS_AVAILABLE:
            # Show message if filtering not available
            no_filter_label = QtWidgets.QLabel("Filtering unavailable\n(Install scipy package)")
            no_filter_label.setStyleSheet("color: orange; font-style: italic;")
            filter_layout.addWidget(no_filter_label)
        else:
            # Enable/Disable filtering
            self.filterEnableCheck = QtWidgets.QCheckBox("Enable Filtering")
            self.filterEnableCheck.setChecked(False)
            filter_layout.addWidget(self.filterEnableCheck)
            
            # Filter type selection
            filter_type_layout = QtWidgets.QHBoxLayout()
            filter_type_layout.addWidget(QtWidgets.QLabel("Filter Type:"))
            self.filterTypeCombo = QtWidgets.QComboBox()
            self.filterTypeCombo.addItems([
                "Low Pass", "High Pass", "Band Pass", "Band Stop", 
                "50Hz Notch", "60Hz Notch"
            ])
            self.filterTypeCombo.setCurrentText("Low Pass")
            filter_type_layout.addWidget(self.filterTypeCombo)
            filter_layout.addLayout(filter_type_layout)
            
            # Cutoff frequency controls
            cutoff_layout = QtWidgets.QGridLayout()
            
            # Primary cutoff frequency
            cutoff_layout.addWidget(QtWidgets.QLabel("Cutoff Freq (Hz):"), 0, 0)
            self.filterCutoff1Spin = QtWidgets.QDoubleSpinBox()
            self.filterCutoff1Spin.setRange(0.1, 10000)
            self.filterCutoff1Spin.setValue(100.0)
            self.filterCutoff1Spin.setDecimals(1)
            cutoff_layout.addWidget(self.filterCutoff1Spin, 0, 1)
            
            # Secondary cutoff frequency (for band filters)
            self.filterCutoff2Label = QtWidgets.QLabel("High Freq (Hz):")
            self.filterCutoff2Label.setVisible(False)
            cutoff_layout.addWidget(self.filterCutoff2Label, 1, 0)
            self.filterCutoff2Spin = QtWidgets.QDoubleSpinBox()
            self.filterCutoff2Spin.setRange(0.1, 10000)
            self.filterCutoff2Spin.setValue(200.0)
            self.filterCutoff2Spin.setDecimals(1)
            self.filterCutoff2Spin.setVisible(False)
            cutoff_layout.addWidget(self.filterCutoff2Spin, 1, 1)
            
            # Filter order
            cutoff_layout.addWidget(QtWidgets.QLabel("Filter Order:"), 2, 0)
            self.filterOrderSpin = QtWidgets.QSpinBox()
            self.filterOrderSpin.setRange(1, 10)
            self.filterOrderSpin.setValue(4)
            cutoff_layout.addWidget(self.filterOrderSpin, 2, 1)
            
            filter_layout.addLayout(cutoff_layout)
            
            # Filter status
            self.filterStatusLabel = QtWidgets.QLabel("Filter: Disabled")
            self.filterStatusLabel.setStyleSheet("color: gray; font-style: italic;")
            filter_layout.addWidget(self.filterStatusLabel)
        
        right_layout.addWidget(filter_group)
        
        # Legend + visibility controls
        self.plotVisibilityChecks = []
        self.legend = self.plot.addLegend()
        self.spectrum_legend = self.spectrum_plot.addLegend()
        self.vis_grid = QtWidgets.QGridLayout()
        for i in range(16):
            cb = QtWidgets.QCheckBox(f"AI{i}")
            cb.setChecked(i < 2)
            self.plotVisibilityChecks.append(cb)
            self.vis_grid.addWidget(cb, i // 4, i % 4)
        right_layout.addLayout(self.vis_grid)
        # Save controls
        save_group = QtWidgets.QGroupBox("Save Data")
        save_layout = QtWidgets.QVBoxLayout(save_group)
        
        # Directory selection
        dir_layout = QtWidgets.QHBoxLayout()
        self.saveDirLabel = QtWidgets.QLabel("No directory selected")
        self.browseDirBtn = QtWidgets.QPushButton("Browse Directory")
        dir_layout.addWidget(QtWidgets.QLabel("Save to:"))
        dir_layout.addWidget(self.saveDirLabel, 1)
        dir_layout.addWidget(self.browseDirBtn)
        save_layout.addLayout(dir_layout)
        
        # Filename input
        file_layout = QtWidgets.QHBoxLayout()
        self.saveNameEdit = QtWidgets.QLineEdit()
        self.saveNameEdit.setPlaceholderText("Enter filename (e.g., data.csv)")
        self.saveBtn = QtWidgets.QPushButton("Save")
        file_layout.addWidget(QtWidgets.QLabel("Filename:"))
        file_layout.addWidget(self.saveNameEdit, 1)
        file_layout.addWidget(self.saveBtn)
        save_layout.addLayout(file_layout)
        
        # Screenshot button
        screenshot_layout = QtWidgets.QHBoxLayout()
        self.screenshotBtn = QtWidgets.QPushButton("📷 Capture Graph")
        self.screenshotBtn.setToolTip("Save current graph as PNG image")
        screenshot_layout.addWidget(self.screenshotBtn)
        save_layout.addLayout(screenshot_layout)
        
        right_layout.addWidget(save_group, 1)  # Save controls get 1 part
        # Status bar
        self.statusBar = QtWidgets.QLabel("")
        right_layout.addWidget(self.statusBar)

        # Main layout
        main_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QHBoxLayout(main_widget)
        main_layout.addWidget(left, 1)  # Left panel takes 1 part
        main_layout.addWidget(right, 4)  # Right panel takes 4 parts (80% of width)
        self.setCentralWidget(main_widget)

    def apply_settings_to_gui(self):
        """Apply loaded settings to GUI controls."""
        try:
            # Apply device settings
            if self.app_settings["input_config"]:
                idx = self.inputConfigCombo.findText(self.app_settings["input_config"])
                if idx >= 0:
                    self.inputConfigCombo.setCurrentIndex(idx)
            
            # Apply voltage range settings
            self.maxVoltSpin.setValue(self.app_settings["max_voltage"])
            self.minVoltSpin.setValue(self.app_settings["min_voltage"])
            
            # Apply sampling settings
            self.rateSpin.setValue(self.app_settings["sampling_rate"])
            self.samplesSpin.setValue(self.app_settings["samples_to_read"])
            self.avgMsSpin.setValue(self.app_settings["average_time_span"])
            self.delaySpin.setValue(self.app_settings.get("inter_channel_delay_us", 0.0))
            
            # Apply channel selections
            for i, cb in enumerate(self.aiChecks):
                cb.setChecked(i in self.app_settings["selected_channels"])
            
            # Apply channel visibility
            for i, checked in enumerate(self.app_settings["channel_visibility"][:16]):
                if i < len(self.plotVisibilityChecks):
                    self.plotVisibilityChecks[i].setChecked(checked)
            
            # Apply plot settings
            self.autoScaleCheck.setChecked(self.app_settings["auto_scale"])
            self.plot_tabs.setCurrentIndex(self.app_settings["active_tab"])
            
            # Apply spectrum analyzer settings
            idx = self.fftWindowCombo.findText(self.app_settings["fft_window"])
            if idx >= 0:
                self.fftWindowCombo.setCurrentIndex(idx)
            
            idx = self.fftSizeCombo.findText(self.app_settings["fft_size"])
            if idx >= 0:
                self.fftSizeCombo.setCurrentIndex(idx)
            
            self.maxFreqSpin.setValue(self.app_settings["max_frequency"])
            
            # Apply filter settings (if available)
            if FILTERS_AVAILABLE:
                self.filterEnableCheck.setChecked(self.app_settings["filter_enabled"])
                
                idx = self.filterTypeCombo.findText(self.app_settings["filter_type"])
                if idx >= 0:
                    self.filterTypeCombo.setCurrentIndex(idx)
                
                self.filterCutoff1Spin.setValue(self.app_settings["filter_cutoff1"])
                self.filterCutoff2Spin.setValue(self.app_settings["filter_cutoff2"])
                self.filterOrderSpin.setValue(self.app_settings["filter_order"])
            
            # Apply file settings
            if self.app_settings["save_directory"]:
                self.save_directory = self.app_settings["save_directory"]
                self.saveDirLabel.setText(self.app_settings["save_directory"])
            
            if self.app_settings["last_filename"]:
                self.saveNameEdit.setText(self.app_settings["last_filename"])
            
            self.statusBar.setText("Settings loaded successfully.")
            
        except Exception as e:
            print(f"Error applying settings to GUI: {e}")
            self.statusBar.setText("Error loading some settings.")

    def collect_settings_from_gui(self):
        """Collect current GUI settings into a dictionary."""
        # Get selected channels
        selected_channels = [i for i, cb in enumerate(self.aiChecks) if cb.isChecked()]
        
        # Get channel visibility
        channel_visibility = [cb.isChecked() for cb in self.plotVisibilityChecks]
        # Pad to 16 channels if needed
        while len(channel_visibility) < 16:
            channel_visibility.append(False)
        
        settings = {
            # Device settings
            "device_name": self.deviceSelector.currentText() if self.deviceSelector.count() > 0 else "",
            "input_config": self.inputConfigCombo.currentText(),
            
            # Voltage range settings
            "max_voltage": self.maxVoltSpin.value(),
            "min_voltage": self.minVoltSpin.value(),
            
            # Sampling settings
            "sampling_rate": self.rateSpin.value(),
            "samples_to_read": self.samplesSpin.value(),
            "average_time_span": self.avgMsSpin.value(),
            "inter_channel_delay_us": self.delaySpin.value(),
            
            # Channel settings
            "selected_channels": selected_channels,
            "channel_visibility": channel_visibility,
            "channel_ranges": self.channel_ranges,
            
            # Plot settings
            "auto_scale": self.autoScaleCheck.isChecked(),
            "active_tab": self.plot_tabs.currentIndex(),
            
            # Spectrum analyzer settings
            "fft_window": self.fftWindowCombo.currentText(),
            "fft_size": self.fftSizeCombo.currentText(),
            "max_frequency": self.maxFreqSpin.value(),
            
            # File settings
            "save_directory": self.save_directory or "",
            "last_filename": self.saveNameEdit.text()
        }
        
        # Add filter settings if available
        if FILTERS_AVAILABLE:
            settings.update({
                "filter_enabled": self.filterEnableCheck.isChecked(),
                "filter_type": self.filterTypeCombo.currentText(),
                "filter_cutoff1": self.filterCutoff1Spin.value(),
                "filter_cutoff2": self.filterCutoff2Spin.value(),
                "filter_order": self.filterOrderSpin.value(),
            })
        else:
            # Keep previous filter settings if filters not available
            settings.update({
                "filter_enabled": self.app_settings.get("filter_enabled", False),
                "filter_type": self.app_settings.get("filter_type", "Low Pass"),
                "filter_cutoff1": self.app_settings.get("filter_cutoff1", 100.0),
                "filter_cutoff2": self.app_settings.get("filter_cutoff2", 200.0),
                "filter_order": self.app_settings.get("filter_order", 4),
            })
        
        return settings

    def save_current_settings(self):
        """Save current GUI settings to file."""
        try:
            self.app_settings = self.collect_settings_from_gui()
            self.app_settings = self.settings_manager.validate_settings(self.app_settings)
            success = self.settings_manager.save_settings(self.app_settings)
            if not success:
                self.statusBar.setText("Warning: Could not save settings.")
        except Exception as e:
            print(f"Error saving settings: {e}")
            self.statusBar.setText("Error saving settings.")

    def validate_delay_setting(self):
        """Validate the inter-channel delay setting and show warnings if needed."""
        try:
            delay_us = self.delaySpin.value()
            if delay_us <= 0:
                return  # No validation needed for auto mode
            
            # Create a temporary settings object to check max conversion rate
            temp_settings = NIDAQSettings(
                device_name=self.deviceSelector.currentText(),
                channels=self.get_selected_channels() or ["ai0"],  # Use ai0 if none selected
                inter_channel_delay_us=delay_us
            )
            
            # Create temporary reader to check max rate
            from niDAQ import NIDAQReader
            temp_reader = NIDAQReader(temp_settings)
            try:
                temp_reader.start()
                max_conv_rate = temp_reader.get_max_conversion_rate()
                temp_reader.close()
                
                if max_conv_rate is not None:
                    # Convert delay to required rate
                    required_rate = 1.0 / (delay_us * 1e-6)
                    if required_rate > max_conv_rate:
                        max_delay_us = 1.0 / max_conv_rate * 1e6
                        self.statusBar.setText(
                            f"Warning: Delay {delay_us:.2f} µs too small. "
                            f"Maximum delay: {max_delay_us:.2f} µs"
                        )
                    else:
                        self.statusBar.setText(f"Inter-channel delay: {delay_us:.2f} µs")
                        
            except Exception:
                # If we can't validate (e.g., no device), just clear any warning
                temp_reader.close()
                
        except Exception as e:
            # Don't show errors for delay validation failures
            pass

    def closeEvent(self, event):
        """Handle application close event."""
        # Save settings before closing
        self.save_current_settings()
        
        # Stop acquisition if running
        if self.worker and self.worker.isRunning():
            self.stop_acquisition()
        
        # Accept the close event
        event.accept()

    def setup_signals(self):
        self.startBtn.clicked.connect(self.start_acquisition)
        self.stopBtn.clicked.connect(self.stop_acquisition)
        self.saveBtn.clicked.connect(self.save_data)
        self.screenshotBtn.clicked.connect(self.capture_graph)
        self.browseDirBtn.clicked.connect(self.browse_save_directory)
        self.configGainBtn.clicked.connect(self.configure_channel_gains)
        for cb in self.plotVisibilityChecks:
            cb.stateChanged.connect(self.update_plot_visibility)
        
        # Spectrum analyzer control signals
        self.fftWindowCombo.currentTextChanged.connect(self.update_plot)
        self.fftSizeCombo.currentTextChanged.connect(self.update_plot)
        self.maxFreqSpin.valueChanged.connect(self.update_plot)
        
        # Filter control signals (only if filters available)
        if FILTERS_AVAILABLE:
            self.filterEnableCheck.stateChanged.connect(self.on_filter_settings_changed)
            self.filterTypeCombo.currentTextChanged.connect(self.on_filter_type_changed)
            self.filterCutoff1Spin.valueChanged.connect(self.on_filter_settings_changed)
            self.filterCutoff2Spin.valueChanged.connect(self.on_filter_settings_changed)
            self.filterOrderSpin.valueChanged.connect(self.on_filter_settings_changed)
        
        # Connect settings auto-save signals
        self.setup_settings_autosave()

    def setup_settings_autosave(self):
        """Connect GUI controls to auto-save settings when changed."""
        # Device and sampling settings
        self.deviceSelector.currentTextChanged.connect(self.save_current_settings)
        self.inputConfigCombo.currentTextChanged.connect(self.save_current_settings)
        self.maxVoltSpin.valueChanged.connect(self.save_current_settings)
        self.minVoltSpin.valueChanged.connect(self.save_current_settings)
        self.rateSpin.valueChanged.connect(self.save_current_settings)
        self.samplesSpin.valueChanged.connect(self.save_current_settings)
        self.avgMsSpin.valueChanged.connect(self.save_current_settings)
        self.delaySpin.valueChanged.connect(self.save_current_settings)
        self.delaySpin.valueChanged.connect(self.validate_delay_setting)
        
        # Channel selection
        for cb in self.aiChecks:
            cb.stateChanged.connect(self.save_current_settings)
        
        # Plot settings
        self.autoScaleCheck.stateChanged.connect(self.save_current_settings)
        self.plot_tabs.currentChanged.connect(self.save_current_settings)
        
        # Spectrum analyzer settings
        self.fftWindowCombo.currentTextChanged.connect(self.save_current_settings)
        self.fftSizeCombo.currentTextChanged.connect(self.save_current_settings)
        self.maxFreqSpin.valueChanged.connect(self.save_current_settings)
        
        # Filter settings (if available)
        if FILTERS_AVAILABLE:
            self.filterEnableCheck.stateChanged.connect(self.save_current_settings)
            self.filterTypeCombo.currentTextChanged.connect(self.save_current_settings)
            self.filterCutoff1Spin.valueChanged.connect(self.save_current_settings)
            self.filterCutoff2Spin.valueChanged.connect(self.save_current_settings)
            self.filterOrderSpin.valueChanged.connect(self.save_current_settings)
        
        # File settings
        self.saveNameEdit.textChanged.connect(self.save_current_settings)

    def detect_devices(self):
        from niDAQ import NIDAQReader
        devices = NIDAQReader.list_devices()
        self.deviceSelector.clear()
        if devices:
            self.deviceSelector.addItems(devices)
            self.startBtn.setEnabled(True)
            self.statusBar.setText(f"Device detected: {devices[0]}")
        else:
            self.deviceSelector.addItem("No device found")
            self.startBtn.setEnabled(False)
            self.statusBar.setText("No device found (waiting for connection)...")
        # store snapshot
        self._last_devices = tuple(devices)

    def restore_device_selection(self):
        """Restore the selected device from settings after device detection."""
        if self.app_settings["device_name"]:
            idx = self.deviceSelector.findText(self.app_settings["device_name"])
            if idx >= 0:
                self.deviceSelector.setCurrentIndex(idx)
                self.statusBar.setText(f"Restored device: {self.app_settings['device_name']}")
            else:
                self.statusBar.setText(f"Previously used device '{self.app_settings['device_name']}' not found")

    def start_device_polling(self):
        """Begin periodic polling for newly connected / removed NI devices.

        This allows the UI to enable Start automatically once a device is
        plugged in after the application was launched.
        """
        self._device_timer = QtCore.QTimer(self)
        self._device_timer.setInterval(2000)  # 2 s poll
        self._device_timer.timeout.connect(self.poll_devices)
        self._device_timer.start()

    def poll_devices(self):
        """Poll system for NI devices and update UI if list changed."""
        from niDAQ import NIDAQReader
        try:
            devices = NIDAQReader.list_devices()
        except Exception:
            devices = []
        devices_tuple = tuple(devices)
        if devices_tuple == self._last_devices:
            return  # no change

        # Device list changed; update selector & start button state only if not acquiring
        running = self.worker is not None and self.worker.isRunning()
        current_selection = self.deviceSelector.currentText() if self.deviceSelector.count() else None
        self.deviceSelector.blockSignals(True)
        self.deviceSelector.clear()
        if devices:
            self.deviceSelector.addItems(devices)
            # preserve selection if still present
            if current_selection in devices:
                idx = devices.index(current_selection)
                self.deviceSelector.setCurrentIndex(idx)
            else:
                self.deviceSelector.setCurrentIndex(0)
            if not running:
                self.startBtn.setEnabled(True)
            self.statusBar.setText(f"Device list updated. Using: {self.deviceSelector.currentText()}")
        else:
            self.deviceSelector.addItem("No device found")
            if not running:
                self.startBtn.setEnabled(False)
            self.statusBar.setText("Device disconnected. Waiting for connection...")
        self.deviceSelector.blockSignals(False)
        self._last_devices = devices_tuple

    def on_filter_type_changed(self):
        """Handle filter type change - show/hide appropriate controls."""
        filter_type = self.filterTypeCombo.currentText()
        
        # Show/hide secondary cutoff for band filters
        is_band_filter = filter_type in ["Band Pass", "Band Stop"]
        self.filterCutoff2Label.setVisible(is_band_filter)
        self.filterCutoff2Spin.setVisible(is_band_filter)
        
        # Update labels
        if filter_type == "Low Pass":
            self.filterCutoff1Spin.setToolTip("Cutoff frequency - signals above this will be attenuated")
        elif filter_type == "High Pass":
            self.filterCutoff1Spin.setToolTip("Cutoff frequency - signals below this will be attenuated")
        elif filter_type == "Band Pass":
            self.filterCutoff1Spin.setToolTip("Lower cutoff frequency")
            self.filterCutoff2Spin.setToolTip("Upper cutoff frequency")
        elif filter_type == "Band Stop":
            self.filterCutoff1Spin.setToolTip("Lower cutoff frequency (start of stop band)")
            self.filterCutoff2Spin.setToolTip("Upper cutoff frequency (end of stop band)")
        
        # Disable controls for notch filters
        is_notch = filter_type in ["50Hz Notch", "60Hz Notch"]
        self.filterCutoff1Spin.setEnabled(not is_notch)
        self.filterCutoff2Spin.setEnabled(not is_notch)
        
        self.on_filter_settings_changed()

    def on_filter_settings_changed(self):
        """Handle changes to filter settings and update filter status."""
        self.filter_enabled = self.filterEnableCheck.isChecked()
        self.filter_type = self.filterTypeCombo.currentText().lower().replace(" ", "_")
        self.filter_cutoff1 = self.filterCutoff1Spin.value()
        self.filter_cutoff2 = self.filterCutoff2Spin.value()
        self.filter_order = self.filterOrderSpin.value()
        
        # Update status label
        if self.filter_enabled:
            if self.filter_type in ["50hz_notch", "60hz_notch"]:
                status_text = f"Filter: {self.filterTypeCombo.currentText()} (Order {self.filter_order})"
            elif self.filter_type in ["band_pass", "band_stop"]:
                status_text = f"Filter: {self.filterTypeCombo.currentText()} {self.filter_cutoff1:.1f}-{self.filter_cutoff2:.1f}Hz (Order {self.filter_order})"
            else:
                status_text = f"Filter: {self.filterTypeCombo.currentText()} {self.filter_cutoff1:.1f}Hz (Order {self.filter_order})"
            self.filterStatusLabel.setText(status_text)
            self.filterStatusLabel.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.filterStatusLabel.setText("Filter: Disabled")
            self.filterStatusLabel.setStyleSheet("color: gray; font-style: italic;")
        
        # Update plot if we have data
        self.update_plot()

    def apply_filter(self, t, y):
        """Apply the selected filter to the data.
        
        Parameters
        ----------
        t : np.ndarray
            Time array in milliseconds
        y : np.ndarray
            Signal data, shape (N, C) where N=samples, C=channels
            
        Returns
        -------
        np.ndarray
            Filtered signal data, same shape as input
        """
        if not FILTERS_AVAILABLE or not self.filter_enabled or len(t) < 10:  # Need minimum samples for filtering
            return y
        
        try:
            if self.filter_type == "low_pass":
                return low_pass(y, t, self.filter_cutoff1, order=self.filter_order)
            elif self.filter_type == "high_pass":
                return high_pass(y, t, self.filter_cutoff1, order=self.filter_order)
            elif self.filter_type == "band_pass":
                return band_pass(y, t, self.filter_cutoff1, self.filter_cutoff2, order=self.filter_order)
            elif self.filter_type == "band_stop":
                return band_stop(y, t, self.filter_cutoff1, self.filter_cutoff2, order=self.filter_order)
            elif self.filter_type == "50hz_notch":
                return notch_50hz(y, t, order=self.filter_order)
            elif self.filter_type == "60hz_notch":
                return notch_60hz(y, t, order=self.filter_order)
            else:
                return y
        except Exception as e:
            # If filtering fails, show error and disable filter
            if FILTERS_AVAILABLE:
                self.filterEnableCheck.setChecked(False)
            self.statusBar.setText(f"Filter error: {e}")
            return y

    def get_selected_channels(self):
        return [f"ai{i}" for i, cb in enumerate(self.aiChecks) if cb.isChecked()]

    def start_acquisition(self):
        channels = self.get_selected_channels()
        if not channels:
            self.statusBar.setText("Select at least one channel.")
            return
        try:
            settings = NIDAQSettings(
                device_name=self.deviceSelector.currentText(),
                channels=channels,
                sampling_rate_hz=self.rateSpin.value(),
                terminal_config=self.inputConfigCombo.currentText(),
                v_min=self.minVoltSpin.value(),
                v_max=self.maxVoltSpin.value(),
                inter_channel_delay_us=self.delaySpin.value(),
                channel_ranges=self.channel_ranges if self.channel_ranges else None
            )
            samples_per_read = self.samplesSpin.value()
            avg_ms = self.avgMsSpin.value()
            self.worker = DAQWorker(settings, samples_per_read, avg_ms)
            self.worker.data_ready.connect(self.on_data_ready)
            self.worker.error.connect(self.on_worker_error)
            self.worker.start()
            self.startBtn.setEnabled(False)
            self.stopBtn.setEnabled(True)
            for w in [self.deviceSelector, self.inputConfigCombo, self.maxVoltSpin, self.minVoltSpin,
                      self.rateSpin, self.samplesSpin, self.avgMsSpin, self.delaySpin] + self.aiChecks:
                w.setEnabled(False)
            self.statusBar.setText("Acquisition started.")
            self.history_t = []
            self.history_y = []
            self.setup_plot_curves(channels)
            self.setup_stats_table(channels)
            # Update spectrum analyzer frequency range based on sampling rate
            nyquist_freq = self.rateSpin.value() // 2
            self.maxFreqSpin.setMaximum(nyquist_freq)
            self.maxFreqSpin.setValue(min(100, nyquist_freq))
        except Exception as e:
            self.statusBar.setText(f"Error: {e}")

    def stop_acquisition(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait()
            self.worker = None
        self.startBtn.setEnabled(True)
        self.stopBtn.setEnabled(False)
        for w in [self.deviceSelector, self.inputConfigCombo, self.maxVoltSpin, self.minVoltSpin,
                  self.rateSpin, self.samplesSpin, self.avgMsSpin, self.delaySpin] + self.aiChecks:
            w.setEnabled(True)
        self.statusBar.setText("Acquisition stopped.")
        # Clear statistics table
        self.stats_table.setRowCount(0)

    def setup_plot_curves(self, channels):
        self.plot.clear()
        self.spectrum_plot.clear()
        self.legend = self.plot.addLegend()
        self.spectrum_legend = self.spectrum_plot.addLegend()
        self.curves = []
        self.spectrum_curves = []
        # Remove old visibility checkboxes
        for i in reversed(range(self.vis_grid.count())):
            widget = self.vis_grid.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.plotVisibilityChecks = []
        for i, ch in enumerate(channels):
            pen = pg.mkPen(color=self.channel_colors[i % len(self.channel_colors)], width=3)
            # Time domain curve
            curve = self.plot.plot([], [], pen=pen, name=ch)
            self.curves.append(curve)
            # Frequency domain curve
            spectrum_curve = self.spectrum_plot.plot([], [], pen=pen, name=ch)
            self.spectrum_curves.append(spectrum_curve)
            # Visibility checkbox
            cb = QtWidgets.QCheckBox(ch.upper())
            cb.setChecked(True)
            cb.stateChanged.connect(self.update_plot_visibility)
            self.plotVisibilityChecks.append(cb)
            self.vis_grid.addWidget(cb, i // 4, i % 4)

    def on_data_ready(self, t, y):
        if t.size == 0 or y.size == 0:
            return
        
        self.history_t.extend(t.tolist())
        
        # Handle both 1D and 2D arrays for y
        if y.ndim == 1:
            # Single channel - reshape to 2D
            y_list = [[val] for val in y.tolist()]
        else:
            # Multiple channels
            y_list = y.tolist()
        
        self.history_y.extend(y_list)
        
        # Keep buffer to last 5 seconds
        fs = self.rateSpin.value()
        max_samples = int(max(5 * fs, 2 * fs * self.avgMsSpin.value() / 1000))
        if len(self.history_t) > max_samples:
            self.history_t = self.history_t[-max_samples:]
            self.history_y = self.history_y[-max_samples:]
        
        self.update_plot()
        self.update_statistics()

    def update_plot(self):
        # Check if we have curves and data before proceeding
        if not hasattr(self, 'curves') or not self.curves or not self.history_t or not self.history_y:
            return
        arr_t = np.array(self.history_t)
        arr_y = np.array(self.history_y)
        
        # Apply filtering if enabled
        if FILTERS_AVAILABLE and self.filter_enabled:
            try:
                arr_y_filtered = self.apply_filter(arr_t, arr_y)
            except Exception as e:
                # If filtering fails, use original data and show error
                arr_y_filtered = arr_y
                self.statusBar.setText(f"Filter error: {e}")
        else:
            arr_y_filtered = arr_y
        
        # Update time domain plot
        self.update_time_plot(arr_t, arr_y_filtered)
        
        # Update frequency domain plot if spectrum curves exist
        if hasattr(self, 'spectrum_curves') and self.spectrum_curves:
            self.update_spectrum_plot(arr_t, arr_y_filtered)

    def update_time_plot(self, arr_t, arr_y):
        """Update the time domain plot."""
        # X axis is time in ms
        for i, curve in enumerate(self.curves):
            if self.plotVisibilityChecks[i].isChecked():
                curve.setData(arr_t, arr_y[:, i])
                curve.show()
            else:
                curve.hide()
        self.plot.setLabel("bottom", "Time", units="ms")
        if self.autoScaleCheck.isChecked():
            self.plot.enableAutoRange()
        else:
            self.plot.setYRange(self.minVoltSpin.value(), self.maxVoltSpin.value())

    def update_spectrum_plot(self, arr_t, arr_y):
        """Update the frequency domain plot using FFT."""
        if len(arr_t) < 2:
            return
            
        # Calculate sampling frequency
        dt_ms = np.mean(np.diff(arr_t))  # Average time step in ms
        fs = 1000.0 / dt_ms  # Convert to Hz
        
        # Determine FFT size
        fft_size_str = self.fftSizeCombo.currentText()
        if fft_size_str == "Auto":
            # Use next power of 2 for efficiency, but limit to available data
            available_samples = len(arr_y)
            if available_samples > 1:
                fft_size = min(available_samples, 2**int(np.log2(available_samples)))
            else:
                fft_size = available_samples
            fft_size = max(fft_size, 32)  # Minimum size
        else:
            fft_size = int(fft_size_str)
            fft_size = min(fft_size, len(arr_y))  # Can't be larger than available data
        
        if fft_size < 32:
            return  # Too few samples for meaningful FFT
            
        # Use the most recent data for FFT
        recent_data = arr_y[-fft_size:]
        
        # Select window function
        window_type = self.fftWindowCombo.currentText().lower()
        if window_type == "hanning":
            window = np.hanning(fft_size)
        elif window_type == "hamming":
            window = np.hamming(fft_size)
        elif window_type == "blackman":
            window = np.blackman(fft_size)
        else:  # Rectangle
            window = np.ones(fft_size)
        
        for i, spectrum_curve in enumerate(self.spectrum_curves):
            if i < len(self.plotVisibilityChecks) and self.plotVisibilityChecks[i].isChecked():
                # Apply window to the signal
                windowed_signal = recent_data[:, i] * window
                
                # Compute FFT
                fft_result = np.fft.rfft(windowed_signal)
                
                # Compute power spectral density
                psd = np.abs(fft_result) ** 2
                
                # Normalize by window power and sampling frequency
                window_power = np.sum(window**2)
                psd = psd / (fs * window_power)
                
                # Convert to dB (avoid log of zero)
                psd_db = 10 * np.log10(np.maximum(psd, 1e-12))
                
                # Frequency axis
                freqs = np.fft.rfftfreq(fft_size, d=dt_ms/1000.0)  # Convert dt to seconds
                
                # Limit frequency range based on user setting
                max_freq = self.maxFreqSpin.value()
                freq_mask = freqs <= max_freq
                
                # Set data
                freqs_plot = freqs[freq_mask]
                psd_plot = psd_db[freq_mask]
                
                if len(freqs_plot) > 0 and len(psd_plot) > 0:
                    spectrum_curve.setData(freqs_plot, psd_plot)
                    spectrum_curve.show()
                else:
                    spectrum_curve.hide()
            else:
                spectrum_curve.hide()
        
        # Auto-scale spectrum plot
        if self.autoScaleCheck.isChecked():
            self.spectrum_plot.enableAutoRange()

    def update_plot_visibility(self):
        self.update_plot()
        # Save settings when visibility changes
        self.save_current_settings()

    def setup_stats_table(self, channels):
        """Initialize the statistics table for the given channels."""
        self.stats_table.setRowCount(len(channels))
        for i, channel in enumerate(channels):
            # Channel name
            self.stats_table.setItem(i, 0, QtWidgets.QTableWidgetItem(channel.upper()))
            
            # Voltage range
            if channel in self.channel_ranges:
                v_min, v_max = self.channel_ranges[channel]
                range_text = f"{v_min:.3f} to {v_max:.3f}V"
            else:
                range_text = f"{self.minVoltSpin.value():.3f} to {self.maxVoltSpin.value():.3f}V"
            self.stats_table.setItem(i, 1, QtWidgets.QTableWidgetItem(range_text))
            
            # Initialize statistics with placeholder values
            self.stats_table.setItem(i, 2, QtWidgets.QTableWidgetItem("--"))
            self.stats_table.setItem(i, 3, QtWidgets.QTableWidgetItem("--"))
            self.stats_table.setItem(i, 4, QtWidgets.QTableWidgetItem("--"))

    def update_statistics(self):
        """Update the statistics table with current data."""
        if not self.history_y or not hasattr(self, 'curves'):
            return
            
        arr_t = np.array(self.history_t)
        arr_y = np.array(self.history_y)
        if arr_y.size == 0:
            return
        
        # Apply filtering to statistics if enabled
        if FILTERS_AVAILABLE and self.filter_enabled:
            try:
                arr_y = self.apply_filter(arr_t, arr_y)
            except Exception:
                pass  # Use original data if filtering fails
            
        # Update statistics for each channel that has data
        for i in range(min(arr_y.shape[1], self.stats_table.rowCount())):
            channel_data = arr_y[:, i]
            if len(channel_data) > 0:
                min_val = np.min(channel_data)
                max_val = np.max(channel_data)
                mean_val = np.mean(channel_data)
                
                # Update table items with 3 decimal places
                self.stats_table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{min_val:.3f}"))
                self.stats_table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{max_val:.3f}"))
                self.stats_table.setItem(i, 4, QtWidgets.QTableWidgetItem(f"{mean_val:.3f}"))

    def save_data(self):
        # Check if directory is selected
        if not self.save_directory:
            self.statusBar.setText("Please select a directory first.")
            return
            
        filename = self.saveNameEdit.text().strip()
        if not filename:
            self.statusBar.setText("Please enter a filename.")
            return
            
        # Add .csv extension if not provided
        if not filename.lower().endswith('.csv'):
            filename += '.csv'
            
        import os
        full_path = os.path.join(self.save_directory, filename)
        
        try:
            settings = NIDAQSettings(
                device_name=self.deviceSelector.currentText(),
                channels=self.get_selected_channels(),
                sampling_rate_hz=self.rateSpin.value(),
                terminal_config=self.inputConfigCombo.currentText(),
                v_min=self.minVoltSpin.value(),
                v_max=self.maxVoltSpin.value(),
                channel_ranges=self.channel_ranges if self.channel_ranges else None
            )
            
            # Check if we have data to save
            if not self.history_t or not self.history_y:
                self.statusBar.setText("No data to save. Start acquisition first.")
                return
                
            # Save as CSV
            with open(full_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["sample_index", "timestamp_ms"] + settings.channels)
                for i, (t, y_row) in enumerate(zip(self.history_t, self.history_y)):
                    writer.writerow([i, t] + list(y_row))
            self.statusBar.setText(f"Saved to {full_path}")
        except Exception as e:
            self.statusBar.setText(f"Save error: {e}")

    def capture_graph(self):
        """Capture the current graph and save it as a PNG image."""
        # Check if directory is selected
        if not self.save_directory:
            self.statusBar.setText("Please select a directory first.")
            return
        
        try:
            # Get current time for filename
            now = datetime.datetime.now()
            time_str = now.strftime("%m.%d.%y-%H%M")
            
            # Determine graph type and get active channels
            current_tab = self.plot_tabs.currentIndex()
            if current_tab == 0:
                graph_type = "time"
                plot_widget = self.plot
            else:
                graph_type = "spectrum"
                plot_widget = self.spectrum_plot
            
            # Get active channels for filename
            selected_channels = self.get_selected_channels()
            active_channels = []
            
            # Check which channels have visible curves
            for i, channel in enumerate(selected_channels):
                if i < len(self.plotVisibilityChecks) and self.plotVisibilityChecks[i].isChecked():
                    # Convert channel name (e.g., "ai0" -> "a0")
                    if channel.startswith("ai"):
                        active_channels.append("a" + channel[2:])
                    else:
                        active_channels.append(channel)
            
            # Create channel string for filename
            if active_channels:
                channels_str = "".join(active_channels)
            else:
                channels_str = "nodata"
            
            # Create filename: graph-time-8.29.25-0900-a1a5.png
            filename = f"graph-{graph_type}-{time_str}-{channels_str}.png"
            full_path = os.path.join(self.save_directory, filename)
            
            # Export the plot widget as PNG
            exporter = ImageExporter(plot_widget.plotItem)
            
            # Set high quality parameters
            exporter.parameters()['width'] = 1920  # High resolution
            exporter.parameters()['height'] = 1080
            exporter.parameters()['antialias'] = True
            
            # Export to file
            exporter.export(full_path)
            
            self.statusBar.setText(f"Graph saved to {filename}")
            
        except Exception as e:
            self.statusBar.setText(f"Screenshot error: {e}")
            print(f"Screenshot error details: {e}")

    def browse_save_directory(self):
        """Open directory selection dialog."""
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, 
            "Select Directory for Saving Files",
            self.save_directory or ""
        )
        
        if directory:
            self.save_directory = directory
            # Show shortened path in label
            import os
            if len(directory) > 50:
                display_path = "..." + directory[-47:]
            else:
                display_path = directory
            self.saveDirLabel.setText(display_path)
            self.saveDirLabel.setToolTip(directory)  # Show full path on hover
            self.statusBar.setText(f"Save directory set to: {directory}")
            
            # Save settings after directory change
            self.save_current_settings()

    def configure_channel_gains(self):
        """Open dialog to configure individual channel voltage ranges."""
        dialog = ChannelGainDialog(self.channel_ranges, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.channel_ranges = dialog.get_channel_ranges()
            self.statusBar.setText("Channel gain configuration updated.")
            
            # Save settings after channel gain changes
            self.save_current_settings()

    def on_worker_error(self, msg):
        self.statusBar.setText(f"DAQ error: {msg}")
        self.stop_acquisition()


class ChannelGainDialog(QtWidgets.QDialog):
    """Dialog for configuring individual channel voltage ranges."""
    
    def __init__(self, current_ranges, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Channel Voltage Ranges")
        self.setModal(True)
        self.resize(500, 600)
        
        # Store current ranges
        self.channel_ranges = current_ranges.copy() if current_ranges else {}
        
        # Get common ranges
        from niDAQ import NIDAQSettings
        self.common_ranges = NIDAQSettings.get_common_ranges()
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header
        header = QtWidgets.QLabel("Configure voltage ranges for each channel individually.\n"
                                "Smaller ranges provide better resolution for low-level signals.")
        header.setWordWrap(True)
        layout.addWidget(header)
        
        # Scroll area for channel configurations
        scroll = QtWidgets.QScrollArea()
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
        
        self.channel_widgets = {}
        
        # Create configuration for each channel
        for i in range(16):
            channel = f"ai{i}"
            group = QtWidgets.QGroupBox(f"Channel AI{i}")
            group_layout = QtWidgets.QHBoxLayout(group)
            
            # Enable checkbox
            enable_cb = QtWidgets.QCheckBox("Custom Range")
            enable_cb.setChecked(channel in self.channel_ranges)
            
            # Range selection combo
            range_combo = QtWidgets.QComboBox()
            range_combo.addItem("Select Range...", None)
            for name, (v_min, v_max) in self.common_ranges.items():
                range_combo.addItem(f"{name} ({v_min}V to {v_max}V)", (v_min, v_max))
            range_combo.addItem("Custom...", "custom")
            
            # Custom range inputs
            min_spin = QtWidgets.QDoubleSpinBox()
            min_spin.setRange(-10.0, 10.0)
            min_spin.setValue(-1.0)
            min_spin.setDecimals(3)
            min_spin.setSuffix(" V")
            
            max_spin = QtWidgets.QDoubleSpinBox()
            max_spin.setRange(-10.0, 10.0)
            max_spin.setValue(1.0)
            max_spin.setDecimals(3)
            max_spin.setSuffix(" V")
            
            # Set current values if configured
            if channel in self.channel_ranges:
                v_min, v_max = self.channel_ranges[channel]
                min_spin.setValue(v_min)
                max_spin.setValue(v_max)
                
                # Try to find matching preset
                found_preset = False
                for j in range(1, range_combo.count() - 1):  # Skip "Select Range..." and "Custom..."
                    preset_range = range_combo.itemData(j)
                    if preset_range and abs(preset_range[0] - v_min) < 0.001 and abs(preset_range[1] - v_max) < 0.001:
                        range_combo.setCurrentIndex(j)
                        found_preset = True
                        break
                
                if not found_preset:
                    range_combo.setCurrentIndex(range_combo.count() - 1)  # Custom
            
            # Connect signals
            def make_range_changed(ch, combo, min_s, max_s, enable):
                def on_range_changed():
                    if combo.currentData() == "custom":
                        min_s.setEnabled(True)
                        max_s.setEnabled(True)
                    elif combo.currentData() is not None:
                        v_min, v_max = combo.currentData()
                        min_s.setValue(v_min)
                        max_s.setValue(v_max)
                        min_s.setEnabled(False)
                        max_s.setEnabled(False)
                    else:
                        min_s.setEnabled(False)
                        max_s.setEnabled(False)
                return on_range_changed
            
            def make_enable_changed(ch, combo, min_s, max_s):
                def on_enable_changed(checked):
                    combo.setEnabled(checked)
                    if checked:
                        on_range_changed = make_range_changed(ch, combo, min_s, max_s, None)()
                    else:
                        min_s.setEnabled(False)
                        max_s.setEnabled(False)
                return on_enable_changed
            
            range_combo.currentIndexChanged.connect(make_range_changed(channel, range_combo, min_spin, max_spin, enable_cb))
            enable_cb.stateChanged.connect(make_enable_changed(channel, range_combo, min_spin, max_spin))
            
            # Initial state
            range_combo.setEnabled(enable_cb.isChecked())
            if enable_cb.isChecked():
                range_combo.currentIndexChanged.emit(range_combo.currentIndex())
            else:
                min_spin.setEnabled(False)
                max_spin.setEnabled(False)
            
            # Layout
            group_layout.addWidget(enable_cb)
            group_layout.addWidget(range_combo)
            group_layout.addWidget(QtWidgets.QLabel("Min:"))
            group_layout.addWidget(min_spin)
            group_layout.addWidget(QtWidgets.QLabel("Max:"))
            group_layout.addWidget(max_spin)
            
            scroll_layout.addWidget(group)
            
            # Store widgets for later access
            self.channel_widgets[channel] = {
                'enable': enable_cb,
                'combo': range_combo,
                'min': min_spin,
                'max': max_spin
            }
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | 
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Reset button
        reset_btn = QtWidgets.QPushButton("Reset All to Default")
        reset_btn.clicked.connect(self.reset_all)
        layout.insertWidget(-1, reset_btn)
    
    def reset_all(self):
        """Reset all channels to default (no custom range)."""
        for widgets in self.channel_widgets.values():
            widgets['enable'].setChecked(False)
            widgets['combo'].setCurrentIndex(0)
    
    def get_channel_ranges(self):
        """Get the configured channel ranges."""
        ranges = {}
        for channel, widgets in self.channel_widgets.items():
            if widgets['enable'].isChecked():
                v_min = widgets['min'].value()
                v_max = widgets['max'].value()
                if v_min < v_max:  # Sanity check
                    ranges[channel] = (v_min, v_max)
        return ranges

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    win = DAQMainWindow()
    win.show()
    sys.exit(app.exec())
