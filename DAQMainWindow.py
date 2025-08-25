from PySide6 import QtWidgets, QtCore
import pyqtgraph as pg
import numpy as np
import csv
from niDAQ import NIDAQReader, NIDAQSettings

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
        self.setup_ui()
        self.setup_signals()
        # Initialize filter UI state (only if filters available)
        if FILTERS_AVAILABLE:
            self.on_filter_type_changed()
        self.detect_devices()
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
        left_layout.addWidget(QtWidgets.QLabel("Rate (Hz):"))
        left_layout.addWidget(self.rateSpin)
        left_layout.addWidget(QtWidgets.QLabel("Samples to Read:"))
        left_layout.addWidget(self.samplesSpin)
        left_layout.addWidget(QtWidgets.QLabel("Average time span [ms]:"))
        left_layout.addWidget(self.avgMsSpin)
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
        self.stats_table.setColumnCount(4)
        self.stats_table.setHorizontalHeaderLabels(["Channel", "Min (V)", "Max (V)", "Mean (V)"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.setMaximumHeight(200)
        self.stats_table.setAlternatingRowColors(True)
        stats_layout.addWidget(self.stats_table)
        left_layout.addWidget(stats_group)
        
        left_layout.addStretch()

        # Right: Live Plot & Save
        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        self.plot = pg.PlotWidget(title="Amplitude vs Time (ms)")
        self.plot.setBackground("k")
        # Make plot take most of the vertical space (80%)
        right_layout.addWidget(self.plot, 4)  # Plot gets 4 parts
        self.autoScaleCheck = QtWidgets.QCheckBox("Auto-scale")
        self.autoScaleCheck.setChecked(True)
        right_layout.addWidget(self.autoScaleCheck)
        
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

    def setup_signals(self):
        self.startBtn.clicked.connect(self.start_acquisition)
        self.stopBtn.clicked.connect(self.stop_acquisition)
        self.saveBtn.clicked.connect(self.save_data)
        self.browseDirBtn.clicked.connect(self.browse_save_directory)
        for cb in self.plotVisibilityChecks:
            cb.stateChanged.connect(self.update_plot_visibility)
        
        # Filter control signals (only if filters available)
        if FILTERS_AVAILABLE:
            self.filterEnableCheck.stateChanged.connect(self.on_filter_settings_changed)
            self.filterTypeCombo.currentTextChanged.connect(self.on_filter_type_changed)
            self.filterCutoff1Spin.valueChanged.connect(self.on_filter_settings_changed)
            self.filterCutoff2Spin.valueChanged.connect(self.on_filter_settings_changed)
            self.filterOrderSpin.valueChanged.connect(self.on_filter_settings_changed)

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
                      self.rateSpin, self.samplesSpin, self.avgMsSpin] + self.aiChecks:
                w.setEnabled(False)
            self.statusBar.setText("Acquisition started.")
            self.history_t = []
            self.history_y = []
            self.setup_plot_curves(channels)
            self.setup_stats_table(channels)
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
                  self.rateSpin, self.samplesSpin, self.avgMsSpin] + self.aiChecks:
            w.setEnabled(True)
        self.statusBar.setText("Acquisition stopped.")
        # Clear statistics table
        self.stats_table.setRowCount(0)

    def setup_plot_curves(self, channels):
        self.plot.clear()
        self.legend = self.plot.addLegend()
        self.curves = []
        # Remove old visibility checkboxes
        for i in reversed(range(self.vis_grid.count())):
            widget = self.vis_grid.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.plotVisibilityChecks = []
        for i, ch in enumerate(channels):
            pen = pg.mkPen(color=self.channel_colors[i % len(self.channel_colors)], width=3)
            curve = self.plot.plot([], [], pen=pen, name=ch)
            self.curves.append(curve)
            cb = QtWidgets.QCheckBox(ch.upper())
            cb.setChecked(True)
            cb.stateChanged.connect(self.update_plot_visibility)
            self.plotVisibilityChecks.append(cb)
            self.vis_grid.addWidget(cb, i // 4, i % 4)

    def on_data_ready(self, t, y):
        if t.size == 0 or y.size == 0:
            return
        self.history_t.extend(t.tolist())
        self.history_y.extend(y.tolist())
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
        
        # X axis is time in ms
        for i, curve in enumerate(self.curves):
            if self.plotVisibilityChecks[i].isChecked():
                curve.setData(arr_t, arr_y_filtered[:, i])
                curve.show()
            else:
                curve.hide()
        self.plot.setLabel("bottom", "Time", units="ms")
        if self.autoScaleCheck.isChecked():
            self.plot.enableAutoRange()
        else:
            self.plot.setYRange(self.minVoltSpin.value(), self.maxVoltSpin.value())

    def update_plot_visibility(self):
        self.update_plot()

    def setup_stats_table(self, channels):
        """Initialize the statistics table for the given channels."""
        self.stats_table.setRowCount(len(channels))
        for i, channel in enumerate(channels):
            # Channel name
            self.stats_table.setItem(i, 0, QtWidgets.QTableWidgetItem(channel.upper()))
            # Initialize with placeholder values
            self.stats_table.setItem(i, 1, QtWidgets.QTableWidgetItem("--"))
            self.stats_table.setItem(i, 2, QtWidgets.QTableWidgetItem("--"))
            self.stats_table.setItem(i, 3, QtWidgets.QTableWidgetItem("--"))

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
                self.stats_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{min_val:.3f}"))
                self.stats_table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{max_val:.3f}"))
                self.stats_table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{mean_val:.3f}"))

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

    def on_worker_error(self, msg):
        self.statusBar.setText(f"DAQ error: {msg}")
        self.stop_acquisition()

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    win = DAQMainWindow()
    win.show()
    sys.exit(app.exec())
