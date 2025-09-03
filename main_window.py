"""
Main Window Module

Coordinates all components and provides the main application interface.
This is the new modular main window that replaces the monolithic DAQMainWindow.
"""

from PySide6 import QtWidgets, QtCore
import numpy as np

# Import our modular components
from gui_panels import MainLayout
from daq_controller import DAQController
from data_processor import DataProcessor
from plot_manager import PlotManager
from settings_controller import SettingsController
from file_manager import FileManager
from dialogs import ChannelGainDialog, AboutDialog, DeviceInfoDialog, FilterHelpDialog


class DAQMainWindow(QtWidgets.QMainWindow):
    """Main application window that coordinates all components."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NI USB-6211 DAQ - Modular Version")
        self.resize(1400, 900)
        
        # Initialize components
        self.init_components()
        self.setup_ui()
        self.connect_signals()
        self.load_and_apply_settings()
        
        # Initialize device detection
        self.daq_controller.detect_devices()
    
    def init_components(self):
        """Initialize all modular components."""
        # Core components
        self.daq_controller = DAQController()
        self.data_processor = DataProcessor()
        self.settings_controller = SettingsController()
        self.file_manager = FileManager()
        
        # Performance optimization: Rate-limited GUI updates
        self.gui_update_timer = QtCore.QTimer()
        self.gui_update_timer.timeout.connect(self.update_gui_elements)
        self.gui_update_timer.start(33)  # 30 Hz updates instead of data rate
        
        # Data buffer for rate-limited updates
        self.latest_data = None
        self.data_pending = False
        
        # GUI will be created in setup_ui
        self.plot_manager = None
        self.main_layout = None
    
    def setup_ui(self):
        """Setup the user interface."""
        # Create main layout with all GUI components
        self.main_layout = MainLayout()
        self.setCentralWidget(self.main_layout)
        
        # Initialize plot manager with the plot widgets
        self.plot_manager = PlotManager(
            self.main_layout.time_plot,
            self.main_layout.spectrum_plot
        )
        
        # Setup menu bar
        self.setup_menu_bar()
        
        # Initial UI state
        self.main_layout.stopBtn.setEnabled(False)
    
    def setup_menu_bar(self):
        """Setup the application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        export_action = file_menu.addAction("Export Settings...")
        export_action.triggered.connect(self.export_settings)
        
        import_action = file_menu.addAction("Import Settings...")
        import_action.triggered.connect(self.import_settings)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        
        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        
        device_info_action = tools_menu.addAction("Device Information...")
        device_info_action.triggered.connect(self.show_device_info)
        
        filter_help_action = tools_menu.addAction("Filter Help...")
        filter_help_action.triggered.connect(self.show_filter_help)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = help_menu.addAction("About...")
        about_action.triggered.connect(self.show_about)
    
    def connect_signals(self):
        """Connect signals between components."""
        # DAQ Controller signals
        self.daq_controller.acquisition_started.connect(self.on_acquisition_started)
        self.daq_controller.acquisition_stopped.connect(self.on_acquisition_stopped)
        self.daq_controller.devices_updated.connect(self.on_devices_updated)
        self.daq_controller.status_message.connect(self.update_status)
        self.daq_controller.error_occurred.connect(self.show_error)
        self.daq_controller.data_ready.connect(self.on_data_ready)
        
        # Data Processor signals
        self.data_processor.statistics_updated.connect(self.update_statistics_table)
        
        # Settings Controller signals
        self.settings_controller.settings_loaded.connect(self.on_settings_loaded)
        self.settings_controller.settings_saved.connect(self.on_settings_saved)
        self.settings_controller.settings_error.connect(self.show_error)
        
        # File Manager signals
        self.file_manager.file_saved.connect(self.on_file_saved)
        self.file_manager.file_error.connect(self.show_error)
        self.file_manager.directory_selected.connect(self.on_directory_selected)
        
        # GUI Control signals
        self.main_layout.startBtn.clicked.connect(self.start_acquisition)
        self.main_layout.stopBtn.clicked.connect(self.stop_acquisition)
        self.main_layout.saveBtn.clicked.connect(self.save_data)
        self.main_layout.screenshotBtn.clicked.connect(self.capture_screenshot)
        self.main_layout.browseDirBtn.clicked.connect(self.browse_directory)
        self.main_layout.configGainBtn.clicked.connect(self.configure_channel_gains)
        
        # Plot visibility controls
        for cb in self.main_layout.plotVisibilityChecks:
            cb.stateChanged.connect(self.update_plot_visibility)
        
        # Filter controls (if available)
        if hasattr(self.main_layout, 'filterEnableCheck'):
            self.main_layout.filterEnableCheck.stateChanged.connect(self.on_filter_settings_changed)
            self.main_layout.filterTypeCombo.currentTextChanged.connect(self.on_filter_type_changed)
            self.main_layout.filterCutoff1Spin.valueChanged.connect(self.on_filter_settings_changed)
            self.main_layout.filterCutoff2Spin.valueChanged.connect(self.on_filter_settings_changed)
            self.main_layout.filterOrderSpin.valueChanged.connect(self.on_filter_settings_changed)
        
        # Spectrum analyzer controls
        self.main_layout.fftWindowCombo.currentTextChanged.connect(self.update_spectrum_plot)
        self.main_layout.fftSizeCombo.currentTextChanged.connect(self.update_spectrum_plot)
        self.main_layout.maxFreqSpin.valueChanged.connect(self.update_spectrum_plot)
        
        # Auto-save settings connections
        self.setup_auto_save_connections()
        
        # Delay validation
        self.main_layout.delaySpin.valueChanged.connect(self.validate_delay_setting)
    
    def setup_auto_save_connections(self):
        """Setup automatic saving when settings change."""
        # Device and sampling settings
        self.main_layout.deviceSelector.currentTextChanged.connect(self.auto_save_settings)
        self.main_layout.inputConfigCombo.currentTextChanged.connect(self.auto_save_settings)
        self.main_layout.maxVoltSpin.valueChanged.connect(self.auto_save_settings)
        self.main_layout.minVoltSpin.valueChanged.connect(self.auto_save_settings)
        self.main_layout.rateSpin.valueChanged.connect(self.auto_save_settings)
        self.main_layout.samplesSpin.valueChanged.connect(self.auto_save_settings)
        self.main_layout.avgMsSpin.valueChanged.connect(self.auto_save_settings)
        self.main_layout.delaySpin.valueChanged.connect(self.auto_save_settings)
        
        # Channel selections
        for cb in self.main_layout.aiChecks:
            cb.stateChanged.connect(self.auto_save_settings)
        
        # Plot settings
        self.main_layout.autoScaleCheck.stateChanged.connect(self.auto_save_settings)
        self.main_layout.plot_tabs.currentChanged.connect(self.auto_save_settings)
        
        # Spectrum settings
        self.main_layout.fftWindowCombo.currentTextChanged.connect(self.auto_save_settings)
        self.main_layout.fftSizeCombo.currentTextChanged.connect(self.auto_save_settings)
        self.main_layout.maxFreqSpin.valueChanged.connect(self.auto_save_settings)
        
        # Filter settings (if available)
        if hasattr(self.main_layout, 'filterEnableCheck'):
            self.main_layout.filterEnableCheck.stateChanged.connect(self.auto_save_settings)
            self.main_layout.filterTypeCombo.currentTextChanged.connect(self.auto_save_settings)
            self.main_layout.filterCutoff1Spin.valueChanged.connect(self.auto_save_settings)
            self.main_layout.filterCutoff2Spin.valueChanged.connect(self.auto_save_settings)
            self.main_layout.filterOrderSpin.valueChanged.connect(self.auto_save_settings)
        
        # File settings
        self.main_layout.saveNameEdit.textChanged.connect(self.auto_save_settings)
    
    def load_and_apply_settings(self):
        """Load settings and apply them to the GUI."""
        self.settings_controller.load_settings()
    
    def get_gui_widgets_dict(self):
        """Get dictionary of GUI widgets for settings operations."""
        widgets = {
            'deviceSelector': self.main_layout.deviceSelector,
            'inputConfigCombo': self.main_layout.inputConfigCombo,
            'maxVoltSpin': self.main_layout.maxVoltSpin,
            'minVoltSpin': self.main_layout.minVoltSpin,
            'rateSpin': self.main_layout.rateSpin,
            'samplesSpin': self.main_layout.samplesSpin,
            'avgMsSpin': self.main_layout.avgMsSpin,
            'delaySpin': self.main_layout.delaySpin,
            'aiChecks': self.main_layout.aiChecks,
            'plotVisibilityChecks': self.main_layout.plotVisibilityChecks,
            'autoScaleCheck': self.main_layout.autoScaleCheck,
            'plot_tabs': self.main_layout.plot_tabs,
            'fftWindowCombo': self.main_layout.fftWindowCombo,
            'fftSizeCombo': self.main_layout.fftSizeCombo,
            'maxFreqSpin': self.main_layout.maxFreqSpin,
            'saveNameEdit': self.main_layout.saveNameEdit,
            'save_directory': self.file_manager.get_save_directory()
        }
        
        # Add filter widgets if available
        if hasattr(self.main_layout, 'filterEnableCheck'):
            widgets.update({
                'filterEnableCheck': self.main_layout.filterEnableCheck,
                'filterTypeCombo': self.main_layout.filterTypeCombo,
                'filterCutoff1Spin': self.main_layout.filterCutoff1Spin,
                'filterCutoff2Spin': self.main_layout.filterCutoff2Spin,
                'filterOrderSpin': self.main_layout.filterOrderSpin,
            })
        
        return widgets
    
    # Signal handlers
    def on_settings_loaded(self, settings):
        """Handle settings loaded signal."""
        gui_widgets = self.get_gui_widgets_dict()
        success = self.settings_controller.apply_settings_to_gui(gui_widgets, settings)
        if success:
            # Apply specific settings
            if settings.get("save_directory"):
                self.file_manager.set_save_directory(settings["save_directory"])
            self.update_status("Settings loaded successfully.")
        else:
            self.show_error("Error applying some settings to GUI.")
    
    def on_settings_saved(self):
        """Handle settings saved signal."""
        self.update_status("Settings saved successfully.")
    
    def auto_save_settings(self):
        """Automatically save current settings."""
        gui_widgets = self.get_gui_widgets_dict()
        settings = self.settings_controller.collect_gui_settings(gui_widgets)
        self.settings_controller.save_settings(settings)
    
    def on_acquisition_started(self):
        """Handle acquisition started signal."""
        self.main_layout.startBtn.setEnabled(False)
        self.main_layout.stopBtn.setEnabled(True)
        
        # Disable controls during acquisition
        controls = [
            self.main_layout.deviceSelector, self.main_layout.inputConfigCombo,
            self.main_layout.maxVoltSpin, self.main_layout.minVoltSpin,
            self.main_layout.rateSpin, self.main_layout.samplesSpin,
            self.main_layout.avgMsSpin, self.main_layout.delaySpin
        ] + self.main_layout.aiChecks
        
        for control in controls:
            control.setEnabled(False)
        
        # Clear data and setup plots
        self.data_processor.clear_data()
        channels = self.get_selected_channels()
        self.plot_manager.setup_curves(channels)
        self.setup_statistics_table(channels)
        
        # Update spectrum analyzer frequency range
        nyquist_freq = self.main_layout.rateSpin.value() // 2
        self.main_layout.maxFreqSpin.setMaximum(nyquist_freq)
        self.main_layout.maxFreqSpin.setValue(min(100, nyquist_freq))
    
    def on_acquisition_stopped(self):
        """Handle acquisition stopped signal."""
        self.main_layout.startBtn.setEnabled(True)
        self.main_layout.stopBtn.setEnabled(False)
        
        # Re-enable controls
        controls = [
            self.main_layout.deviceSelector, self.main_layout.inputConfigCombo,
            self.main_layout.maxVoltSpin, self.main_layout.minVoltSpin,
            self.main_layout.rateSpin, self.main_layout.samplesSpin,
            self.main_layout.avgMsSpin, self.main_layout.delaySpin
        ] + self.main_layout.aiChecks
        
        for control in controls:
            control.setEnabled(True)
        
        # Clear statistics table
        self.main_layout.stats_table.setRowCount(0)
    
    def on_devices_updated(self, devices):
        """Handle devices updated signal."""
        # Update device selector (only if not acquiring)
        if not self.daq_controller.is_acquiring():
            current_selection = self.main_layout.deviceSelector.currentText()
            
            self.main_layout.deviceSelector.blockSignals(True)
            self.main_layout.deviceSelector.clear()
            
            if devices:
                self.main_layout.deviceSelector.addItems(devices)
                # Restore selection if possible
                if current_selection in devices:
                    idx = devices.index(current_selection)
                    self.main_layout.deviceSelector.setCurrentIndex(idx)
                self.main_layout.startBtn.setEnabled(True)
            else:
                self.main_layout.deviceSelector.addItem("No device found")
                self.main_layout.startBtn.setEnabled(False)
            
            self.main_layout.deviceSelector.blockSignals(False)
            
            # Try to restore device from settings
            gui_widgets = self.get_gui_widgets_dict()
            self.settings_controller.restore_device_selection(gui_widgets)
    
    def on_data_ready(self, t, y):
        """Handle new data from DAQ - store for rate-limited processing."""
        # Store latest data without immediate GUI updates
        self.latest_data = (t, y)
        self.data_pending = True
        
        # Add to data processor for accumulation (quick operation)
        sampling_rate = self.main_layout.rateSpin.value()
        avg_ms = self.main_layout.avgMsSpin.value()
        max_buffer_time = max(5, 2 * avg_ms / 1000) if avg_ms > 0 else 5
        
        self.data_processor.add_data(t, y, max_buffer_time, sampling_rate)
    
    def update_gui_elements(self):
        """Rate-limited GUI update method (called by timer at 30 Hz)."""
        if not self.data_pending or self.latest_data is None:
            return
        
        t, y = self.latest_data
        self.data_pending = False
        
        # Now do the expensive GUI operations at controlled rate
        self.update_time_plot()
        self.update_spectrum_plot()
        
        # Update statistics
        channels = self.get_selected_channels()
        self.data_processor.calculate_statistics(channels)
    
    def update_statistics_table(self, stats):
        """Update the statistics table with new data."""
        for channel, channel_stats in stats.items():
            # Find the row for this channel
            for row in range(self.main_layout.stats_table.rowCount()):
                if self.main_layout.stats_table.item(row, 0).text().lower() == channel:
                    # Update statistics with 3 decimal places
                    self.main_layout.stats_table.setItem(row, 2, 
                        QtWidgets.QTableWidgetItem(f"{channel_stats['min']:.3f}"))
                    self.main_layout.stats_table.setItem(row, 3, 
                        QtWidgets.QTableWidgetItem(f"{channel_stats['max']:.3f}"))
                    self.main_layout.stats_table.setItem(row, 4, 
                        QtWidgets.QTableWidgetItem(f"{channel_stats['mean']:.3f}"))
                    break
    
    def on_file_saved(self, file_path):
        """Handle file saved signal."""
        import os
        filename = os.path.basename(file_path)
        self.update_status(f"Saved: {filename}")
    
    def on_directory_selected(self, directory):
        """Handle directory selected signal."""
        display_path = self.file_manager.get_display_path(directory)
        self.main_layout.saveDirLabel.setText(display_path)
        self.main_layout.saveDirLabel.setToolTip(directory)
        self.update_status(f"Save directory: {directory}")
        
        # Update settings
        self.settings_controller.set_save_directory(directory)
        self.auto_save_settings()
    
    def update_status(self, message):
        """Update status bar with message."""
        self.main_layout.statusBar.setText(message)
    
    def show_error(self, error_message):
        """Show error message in status bar."""
        self.main_layout.statusBar.setText(f"Error: {error_message}")
    
    # Action handlers
    def start_acquisition(self):
        """Start data acquisition."""
        channels = self.get_selected_channels()
        if not channels:
            self.show_error("Select at least one channel.")
            return
        
        # Get settings for DAQ
        gui_widgets = self.get_gui_widgets_dict()
        daq_settings = self.settings_controller.get_daq_settings_dict(gui_widgets)
        
        # Update data processor filter settings
        filter_settings = self.settings_controller.get_filter_settings_dict(gui_widgets)
        self.data_processor.set_filter_settings(
            filter_settings['enabled'],
            filter_settings['filter_type'],
            filter_settings['cutoff1'],
            filter_settings['cutoff2'],
            filter_settings['order']
        )
        
        # Start acquisition
        samples_per_read = self.main_layout.samplesSpin.value()
        avg_ms = self.main_layout.avgMsSpin.value()
        
        success = self.daq_controller.start_acquisition(daq_settings, samples_per_read, avg_ms)
        if not success:
            self.show_error("Failed to start acquisition")
    
    def stop_acquisition(self):
        """Stop data acquisition."""
        self.daq_controller.stop_acquisition()
    
    def save_data(self):
        """Save current data to CSV file."""
        filename = self.main_layout.saveNameEdit.text().strip()
        
        # Get current data
        t_data, y_data = self.data_processor.get_current_data()
        if len(t_data) == 0:
            self.show_error("No data to save. Start acquisition first.")
            return
        
        # Convert numpy arrays to lists for saving
        history_t = t_data.tolist()
        history_y = y_data.tolist()
        
        # Get settings for file
        gui_widgets = self.get_gui_widgets_dict()
        settings_dict = self.settings_controller.get_daq_settings_dict(gui_widgets)
        
        # Save file
        self.file_manager.save_data_csv(filename, history_t, history_y, settings_dict)
    
    def capture_screenshot(self):
        """Capture screenshot of current plot."""
        # Determine which plot is active
        current_tab = self.main_layout.plot_tabs.currentIndex()
        if current_tab == 0:
            plot_widget = self.main_layout.time_plot
            graph_type = "time"
        else:
            plot_widget = self.main_layout.spectrum_plot
            graph_type = "spectrum"
        
        # Get active channels
        active_channels = []
        selected_channels = self.get_selected_channels()
        visibility = self.plot_manager.get_channel_visibility()
        
        for i, channel in enumerate(selected_channels):
            if i < len(visibility) and visibility[i]:
                active_channels.append(channel)
        
        # Capture screenshot
        self.file_manager.capture_screenshot(plot_widget, graph_type, active_channels)
    
    def browse_directory(self):
        """Browse for save directory."""
        self.file_manager.browse_directory(self, self.file_manager.get_save_directory())
    
    def configure_channel_gains(self):
        """Open channel gain configuration dialog."""
        current_ranges = self.settings_controller.get_channel_ranges()
        dialog = ChannelGainDialog(current_ranges, self)
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            new_ranges = dialog.get_channel_ranges()
            self.settings_controller.set_channel_ranges(new_ranges)
            self.update_status("Channel gain configuration updated.")
            self.auto_save_settings()
    
    def validate_delay_setting(self):
        """Validate inter-channel delay setting."""
        delay_us = self.main_layout.delaySpin.value()
        device_name = self.main_layout.deviceSelector.currentText()
        channels = self.get_selected_channels()
        
        warning = self.daq_controller.validate_delay_setting(device_name, channels, delay_us)
        if warning:
            self.update_status(warning)
        else:
            self.update_status("")
    
    # Plot and filter handlers
    def update_plot_visibility(self):
        """Update plot visibility based on checkboxes."""
        for i, cb in enumerate(self.main_layout.plotVisibilityChecks):
            self.plot_manager.set_channel_visibility(i, cb.isChecked())
        self.auto_save_settings()
    
    def on_filter_settings_changed(self):
        """Handle filter settings changes."""
        if hasattr(self.main_layout, 'filterEnableCheck'):
            gui_widgets = self.get_gui_widgets_dict()
            filter_settings = self.settings_controller.get_filter_settings_dict(gui_widgets)
            
            self.data_processor.set_filter_settings(
                filter_settings['enabled'],
                filter_settings['filter_type'],
                filter_settings['cutoff1'],
                filter_settings['cutoff2'],
                filter_settings['order']
            )
            
            # Update filter status label
            self.update_filter_status_label()
            
            # Update plots if we have data
            self.update_time_plot()
            self.update_spectrum_plot()
    
    def on_filter_type_changed(self):
        """Handle filter type change - show/hide appropriate controls."""
        if hasattr(self.main_layout, 'filterTypeCombo'):
            filter_type = self.main_layout.filterTypeCombo.currentText()
            
            # Show/hide secondary cutoff for band filters
            is_band_filter = filter_type in ["Band Pass", "Band Stop"]
            self.main_layout.filterCutoff2Label.setVisible(is_band_filter)
            self.main_layout.filterCutoff2Spin.setVisible(is_band_filter)
            
            # Disable controls for notch filters
            is_notch = filter_type in ["50Hz Notch", "60Hz Notch"]
            self.main_layout.filterCutoff1Spin.setEnabled(not is_notch)
            self.main_layout.filterCutoff2Spin.setEnabled(not is_notch)
            
            self.on_filter_settings_changed()
    
    def update_filter_status_label(self):
        """Update the filter status label."""
        if not hasattr(self.main_layout, 'filterStatusLabel'):
            return
        
        if not hasattr(self.main_layout, 'filterEnableCheck') or not self.main_layout.filterEnableCheck.isChecked():
            self.main_layout.filterStatusLabel.setText("Filter: Disabled")
            self.main_layout.filterStatusLabel.setStyleSheet("color: gray; font-style: italic;")
            return
        
        filter_type = self.main_layout.filterTypeCombo.currentText()
        cutoff1 = self.main_layout.filterCutoff1Spin.value()
        cutoff2 = self.main_layout.filterCutoff2Spin.value()
        order = self.main_layout.filterOrderSpin.value()
        
        if filter_type in ["50Hz Notch", "60Hz Notch"]:
            status_text = f"Filter: {filter_type} (Order {order})"
        elif filter_type in ["Band Pass", "Band Stop"]:
            status_text = f"Filter: {filter_type} {cutoff1:.1f}-{cutoff2:.1f}Hz (Order {order})"
        else:
            status_text = f"Filter: {filter_type} {cutoff1:.1f}Hz (Order {order})"
        
        self.main_layout.filterStatusLabel.setText(status_text)
        self.main_layout.filterStatusLabel.setStyleSheet("color: green; font-weight: bold;")
    
    def update_time_plot(self):
        """Update the time domain plot."""
        t_data, y_data = self.data_processor.get_filtered_data()
        
        if t_data.size == 0 or y_data.size == 0:
            return
        
        # Get plot settings
        auto_scale = self.main_layout.autoScaleCheck.isChecked()
        y_range = None if auto_scale else (
            self.main_layout.minVoltSpin.value(),
            self.main_layout.maxVoltSpin.value()
        )
        
        self.plot_manager.update_time_plot(t_data, y_data, auto_scale, y_range)
    
    def update_spectrum_plot(self):
        """Update the spectrum plot."""
        if not self.plot_manager.has_data():
            return
        
        # Get spectrum settings
        gui_widgets = self.get_gui_widgets_dict()
        spectrum_settings = self.settings_controller.get_spectrum_settings_dict(gui_widgets)
        
        # Compute spectrum
        freqs, spectra, fs = self.data_processor.compute_spectrum(
            spectrum_settings['sampling_rate'],
            spectrum_settings['window_type'],
            spectrum_settings['fft_size'],
            spectrum_settings['max_frequency']
        )
        
        # Update plot
        auto_scale = self.main_layout.autoScaleCheck.isChecked()
        self.plot_manager.update_spectrum_plot(freqs, spectra, auto_scale)
    
    # Utility methods
    def get_selected_channels(self):
        """Get list of selected channel names."""
        return [f"ai{i}" for i, cb in enumerate(self.main_layout.aiChecks) if cb.isChecked()]
    
    def setup_statistics_table(self, channels):
        """Setup the statistics table for given channels."""
        self.main_layout.stats_table.setRowCount(len(channels))
        
        for i, channel in enumerate(channels):
            # Channel name
            self.main_layout.stats_table.setItem(i, 0, QtWidgets.QTableWidgetItem(channel.upper()))
            
            # Voltage range
            channel_ranges = self.settings_controller.get_channel_ranges()
            if channel in channel_ranges:
                range_data = channel_ranges[channel]
                # Handle both tuple format (v_min, v_max) and string format "±X V"
                if isinstance(range_data, (tuple, list)) and len(range_data) == 2:
                    v_min, v_max = range_data
                    range_text = f"{v_min:.3f} to {v_max:.3f}V"
                elif isinstance(range_data, str):
                    # Use the string as-is (e.g., "±1 V")
                    range_text = range_data
                else:
                    # Fallback to default range
                    range_text = f"{self.main_layout.minVoltSpin.value():.3f} to {self.main_layout.maxVoltSpin.value():.3f}V"
            else:
                range_text = f"{self.main_layout.minVoltSpin.value():.3f} to {self.main_layout.maxVoltSpin.value():.3f}V"
            self.main_layout.stats_table.setItem(i, 1, QtWidgets.QTableWidgetItem(range_text))
            
            # Initialize statistics with placeholder values
            self.main_layout.stats_table.setItem(i, 2, QtWidgets.QTableWidgetItem("--"))
            self.main_layout.stats_table.setItem(i, 3, QtWidgets.QTableWidgetItem("--"))
            self.main_layout.stats_table.setItem(i, 4, QtWidgets.QTableWidgetItem("--"))
    
    # Menu actions
    def export_settings(self):
        """Export current settings to file."""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Settings", "daq_settings_export.json", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            gui_widgets = self.get_gui_widgets_dict()
            settings = self.settings_controller.collect_gui_settings(gui_widgets)
            
            success = self.file_manager.export_settings(settings)
            if success:
                self.update_status(f"Settings exported to {filename}")
    
    def import_settings(self):
        """Import settings from file."""
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Settings", "", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                import json
                with open(filename, 'r') as f:
                    imported_settings = json.load(f)
                
                # Apply imported settings
                gui_widgets = self.get_gui_widgets_dict()
                success = self.settings_controller.apply_settings_to_gui(gui_widgets, imported_settings)
                
                if success:
                    self.settings_controller.save_settings(imported_settings)
                    self.update_status(f"Settings imported from {filename}")
                else:
                    self.show_error("Error applying imported settings")
                    
            except Exception as e:
                self.show_error(f"Error importing settings: {e}")
    
    def show_device_info(self):
        """Show device information dialog."""
        device_name = self.main_layout.deviceSelector.currentText()
        if device_name and device_name != "No device found":
            dialog = DeviceInfoDialog(device_name, self)
            dialog.exec()
        else:
            self.show_error("No device selected")
    
    def show_filter_help(self):
        """Show filter help dialog."""
        dialog = FilterHelpDialog(self)
        dialog.exec()
    
    def show_about(self):
        """Show about dialog."""
        dialog = AboutDialog(self)
        dialog.exec()
    
    def closeEvent(self, event):
        """Handle application close event."""
        # Stop acquisition if running
        if self.daq_controller.is_acquiring():
            self.daq_controller.stop_acquisition()
        
        # Save current settings
        gui_widgets = self.get_gui_widgets_dict()
        settings = self.settings_controller.collect_gui_settings(gui_widgets)
        self.settings_controller.save_settings(settings)
        
        # Accept the close event
        event.accept()


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    win = DAQMainWindow()
    win.show()
    sys.exit(app.exec())
