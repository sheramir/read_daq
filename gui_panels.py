"""
GUI Panels Module

Creates and manages GUI components and layouts.
Separated from main window for better maintainability.
"""

from PySide6 import QtWidgets
import pyqtgraph as pg


class LeftPanel(QtWidgets.QWidget):
    """Left panel containing DAQ acquisition settings."""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Device selection
        self.deviceSelector = QtWidgets.QComboBox()
        layout.addWidget(QtWidgets.QLabel("Device:"))
        layout.addWidget(self.deviceSelector)
        
        # Input configuration
        self.inputConfigCombo = QtWidgets.QComboBox()
        self.inputConfigCombo.addItems(["RSE", "NRSE", "DIFF", "PSEUDO-DIFF"])
        layout.addWidget(QtWidgets.QLabel("Input Configuration:"))
        layout.addWidget(self.inputConfigCombo)
        
        # Voltage range
        self.maxVoltSpin = QtWidgets.QDoubleSpinBox()
        self.maxVoltSpin.setRange(-10, 10)
        self.maxVoltSpin.setValue(3.5)
        self.minVoltSpin = QtWidgets.QDoubleSpinBox()
        self.minVoltSpin.setRange(-10, 10)
        self.minVoltSpin.setValue(-1.0)
        layout.addWidget(QtWidgets.QLabel("Max Input Limit (V):"))
        layout.addWidget(self.maxVoltSpin)
        layout.addWidget(QtWidgets.QLabel("Min Input Limit (V):"))
        layout.addWidget(self.minVoltSpin)
        
        # Sampling settings
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
        self.delaySpin.setRange(0.0, 10000.0)
        self.delaySpin.setValue(0.0)
        self.delaySpin.setSuffix(" µs")
        self.delaySpin.setDecimals(2)
        self.delaySpin.setToolTip("Inter-channel conversion delay (0 = automatic/fastest)")
        
        layout.addWidget(QtWidgets.QLabel("Rate (Hz):"))
        layout.addWidget(self.rateSpin)
        layout.addWidget(QtWidgets.QLabel("Samples to Read:"))
        layout.addWidget(self.samplesSpin)
        layout.addWidget(QtWidgets.QLabel("Average time span [ms]:"))
        layout.addWidget(self.avgMsSpin)
        layout.addWidget(QtWidgets.QLabel("Inter-channel delay:"))
        layout.addWidget(self.delaySpin)
        
        # Channel selection
        layout.addWidget(QtWidgets.QLabel("Channels:"))
        self.aiChecks = []
        grid = QtWidgets.QGridLayout()
        for i in range(16):
            cb = QtWidgets.QCheckBox(f"AI{i}")
            cb.setChecked(i < 2)
            self.aiChecks.append(cb)
            grid.addWidget(cb, i // 4, i % 4)
        layout.addLayout(grid)
        
        # Per-channel gain configuration
        self.configGainBtn = QtWidgets.QPushButton("Configure Channel Gains")
        self.configGainBtn.setToolTip("Set individual voltage ranges for each channel")
        layout.addWidget(self.configGainBtn)
        
        # Control buttons
        self.startBtn = QtWidgets.QPushButton("Start")
        self.stopBtn = QtWidgets.QPushButton("Stop")
        self.stopBtn.setEnabled(False)
        layout.addWidget(self.startBtn)
        layout.addWidget(self.stopBtn)
        
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
        layout.addWidget(stats_group)
        
        layout.addStretch()


class RightPanel(QtWidgets.QWidget):
    """Right panel containing plots and analysis controls."""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Create tabbed plot widget
        self.plot_tabs = QtWidgets.QTabWidget()
        
        # Time Analyzer Tab
        time_tab = QtWidgets.QWidget()
        time_layout = QtWidgets.QVBoxLayout(time_tab)
        self.time_plot = pg.PlotWidget(title="Amplitude vs Time (ms)")
        self.time_plot.setBackground("k")
        time_layout.addWidget(self.time_plot)
        self.plot_tabs.addTab(time_tab, "Time Analyzer")
        
        # Spectrum Analyzer Tab
        spectrum_tab = QtWidgets.QWidget()
        spectrum_layout = QtWidgets.QVBoxLayout(spectrum_tab)
        self.spectrum_plot = pg.PlotWidget(title="Power Spectral Density")
        self.spectrum_plot.setBackground("k")
        self.spectrum_plot.setLabel("left", "Power", units="dB")
        self.spectrum_plot.setLabel("bottom", "Frequency", units="Hz")
        spectrum_layout.addWidget(self.spectrum_plot)
        self.plot_tabs.addTab(spectrum_tab, "Spectrum Analyzer")
        
        # Plot tabs take most space
        layout.addWidget(self.plot_tabs, 4)
        
        # Auto-scale checkbox
        self.autoScaleCheck = QtWidgets.QCheckBox("Auto-scale")
        self.autoScaleCheck.setChecked(True)
        layout.addWidget(self.autoScaleCheck)
        
        # Spectrum Analyzer Controls
        self.spectrum_controls = self.create_spectrum_controls()
        layout.addWidget(self.spectrum_controls)
        
        # Frequency Filtering Controls
        self.filter_controls = self.create_filter_controls()
        layout.addWidget(self.filter_controls)
        
        # Channel visibility controls
        self.visibility_controls = self.create_visibility_controls()
        layout.addLayout(self.visibility_controls)
        
        # Save controls
        self.save_controls = self.create_save_controls()
        layout.addWidget(self.save_controls, 1)
        
        # Status bar
        self.statusBar = QtWidgets.QLabel("")
        layout.addWidget(self.statusBar)
    
    def create_spectrum_controls(self):
        """Create spectrum analyzer control group."""
        group = QtWidgets.QGroupBox("Spectrum Analyzer Settings")
        layout = QtWidgets.QHBoxLayout(group)
        
        # FFT Window Type
        layout.addWidget(QtWidgets.QLabel("Window:"))
        self.fftWindowCombo = QtWidgets.QComboBox()
        self.fftWindowCombo.addItems(["Hanning", "Hamming", "Blackman", "Rectangle"])
        self.fftWindowCombo.setCurrentText("Hanning")
        layout.addWidget(self.fftWindowCombo)
        
        # FFT Size
        layout.addWidget(QtWidgets.QLabel("FFT Size:"))
        self.fftSizeCombo = QtWidgets.QComboBox()
        self.fftSizeCombo.addItems(["Auto", "256", "512", "1024", "2048", "4096"])
        self.fftSizeCombo.setCurrentText("Auto")
        layout.addWidget(self.fftSizeCombo)
        
        # Frequency range
        layout.addWidget(QtWidgets.QLabel("Max Freq (Hz):"))
        self.maxFreqSpin = QtWidgets.QSpinBox()
        self.maxFreqSpin.setRange(1, 50000)
        self.maxFreqSpin.setValue(100)
        layout.addWidget(self.maxFreqSpin)
        
        return group
    
    def create_filter_controls(self):
        """Create frequency filtering control group."""
        group = QtWidgets.QGroupBox("Frequency Filtering")
        layout = QtWidgets.QVBoxLayout(group)
        
        # Check if filters are available
        try:
            from freq_filters import low_pass
            filters_available = True
        except ImportError:
            filters_available = False
        
        if not filters_available:
            # Show message if filtering not available
            no_filter_label = QtWidgets.QLabel("Filtering unavailable\n(Install scipy package)")
            no_filter_label.setStyleSheet("color: orange; font-style: italic;")
            layout.addWidget(no_filter_label)
        else:
            # Enable/Disable filtering
            self.filterEnableCheck = QtWidgets.QCheckBox("Enable Filtering")
            self.filterEnableCheck.setChecked(False)
            layout.addWidget(self.filterEnableCheck)
            
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
            layout.addLayout(filter_type_layout)
            
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
            
            layout.addLayout(cutoff_layout)
            
            # Filter status
            self.filterStatusLabel = QtWidgets.QLabel("Filter: Disabled")
            self.filterStatusLabel.setStyleSheet("color: gray; font-style: italic;")
            layout.addWidget(self.filterStatusLabel)
        
        return group
    
    def create_visibility_controls(self):
        """Create channel visibility control grid."""
        self.plotVisibilityChecks = []
        grid = QtWidgets.QGridLayout()
        for i in range(16):
            cb = QtWidgets.QCheckBox(f"AI{i}")
            cb.setChecked(i < 2)
            self.plotVisibilityChecks.append(cb)
            grid.addWidget(cb, i // 4, i % 4)
        return grid
    
    def create_save_controls(self):
        """Create save data control group."""
        group = QtWidgets.QGroupBox("Save Data")
        layout = QtWidgets.QVBoxLayout(group)
        
        # Directory selection
        dir_layout = QtWidgets.QHBoxLayout()
        self.saveDirLabel = QtWidgets.QLabel("No directory selected")
        self.browseDirBtn = QtWidgets.QPushButton("Browse Directory")
        dir_layout.addWidget(QtWidgets.QLabel("Save to:"))
        dir_layout.addWidget(self.saveDirLabel, 1)
        dir_layout.addWidget(self.browseDirBtn)
        layout.addLayout(dir_layout)
        
        # Filename input
        file_layout = QtWidgets.QHBoxLayout()
        self.saveNameEdit = QtWidgets.QLineEdit()
        self.saveNameEdit.setPlaceholderText("Enter filename (e.g., data.csv)")
        self.saveBtn = QtWidgets.QPushButton("Save")
        file_layout.addWidget(QtWidgets.QLabel("Filename:"))
        file_layout.addWidget(self.saveNameEdit, 1)
        file_layout.addWidget(self.saveBtn)
        layout.addLayout(file_layout)
        
        # Screenshot button
        screenshot_layout = QtWidgets.QHBoxLayout()
        self.screenshotBtn = QtWidgets.QPushButton("📷 Capture Graph")
        self.screenshotBtn.setToolTip("Save current graph as PNG image")
        screenshot_layout.addWidget(self.screenshotBtn)
        layout.addLayout(screenshot_layout)
        
        return group


class MainLayout(QtWidgets.QWidget):
    """Main layout combining left and right panels."""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        # Create panels
        self.left_panel = LeftPanel()
        self.right_panel = RightPanel()
        
        # Main layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.left_panel, 1)   # Left panel takes 1 part
        layout.addWidget(self.right_panel, 4)  # Right panel takes 4 parts (80% width)
        
        # Expose key widgets for external access
        self.setup_widget_access()
    
    def setup_widget_access(self):
        """Expose widgets for easy access from main window."""
        # Left panel widgets
        self.deviceSelector = self.left_panel.deviceSelector
        self.inputConfigCombo = self.left_panel.inputConfigCombo
        self.maxVoltSpin = self.left_panel.maxVoltSpin
        self.minVoltSpin = self.left_panel.minVoltSpin
        self.rateSpin = self.left_panel.rateSpin
        self.samplesSpin = self.left_panel.samplesSpin
        self.avgMsSpin = self.left_panel.avgMsSpin
        self.delaySpin = self.left_panel.delaySpin
        self.aiChecks = self.left_panel.aiChecks
        self.configGainBtn = self.left_panel.configGainBtn
        self.startBtn = self.left_panel.startBtn
        self.stopBtn = self.left_panel.stopBtn
        self.stats_table = self.left_panel.stats_table
        
        # Right panel widgets
        self.plot_tabs = self.right_panel.plot_tabs
        self.time_plot = self.right_panel.time_plot
        self.spectrum_plot = self.right_panel.spectrum_plot
        self.autoScaleCheck = self.right_panel.autoScaleCheck
        self.fftWindowCombo = self.right_panel.fftWindowCombo
        self.fftSizeCombo = self.right_panel.fftSizeCombo
        self.maxFreqSpin = self.right_panel.maxFreqSpin
        self.plotVisibilityChecks = self.right_panel.plotVisibilityChecks
        self.saveDirLabel = self.right_panel.saveDirLabel
        self.browseDirBtn = self.right_panel.browseDirBtn
        self.saveNameEdit = self.right_panel.saveNameEdit
        self.saveBtn = self.right_panel.saveBtn
        self.screenshotBtn = self.right_panel.screenshotBtn
        self.statusBar = self.right_panel.statusBar
        
        # Filter controls (if available)
        if hasattr(self.right_panel, 'filterEnableCheck'):
            self.filterEnableCheck = self.right_panel.filterEnableCheck
            self.filterTypeCombo = self.right_panel.filterTypeCombo
            self.filterCutoff1Spin = self.right_panel.filterCutoff1Spin
            self.filterCutoff2Spin = self.right_panel.filterCutoff2Spin
            self.filterCutoff2Label = self.right_panel.filterCutoff2Label
            self.filterOrderSpin = self.right_panel.filterOrderSpin
            self.filterStatusLabel = self.right_panel.filterStatusLabel
