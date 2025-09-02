"""
Dialogs Module

Custom dialog classes for configuration and user interaction.
Separated from main window for better maintainability.
"""

from PySide6 import QtWidgets, QtCore


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


class AboutDialog(QtWidgets.QDialog):
    """About dialog with application information."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About DAQ Reader")
        self.setModal(True)
        self.resize(400, 300)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Application title
        title = QtWidgets.QLabel("NI DAQ Reader")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Version and description
        info_text = """
        <p><b>Version:</b> 2.0.0</p>
        <p><b>Description:</b> Multi-channel data acquisition application for National Instruments USB-6211 and compatible devices.</p>
        
        <p><b>Features:</b></p>
        <ul>
        <li>Real-time data acquisition and visualization</li>
        <li>Time domain and spectrum analysis</li>
        <li>Digital filtering capabilities</li>
        <li>Data export and screenshot capture</li>
        <li>Inter-channel delay control</li>
        <li>Configurable channel gains</li>
        </ul>
        
        <p><b>Dependencies:</b></p>
        <ul>
        <li>PySide6 (Qt6 GUI framework)</li>
        <li>PyQtGraph (plotting)</li>
        <li>NumPy (numerical operations)</li>
        <li>NI-DAQmx (hardware interface)</li>
        <li>SciPy (optional, for filtering)</li>
        </ul>
        """
        
        info_label = QtWidgets.QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        layout.addWidget(info_label)
        
        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class SettingsExportDialog(QtWidgets.QDialog):
    """Dialog for exporting/importing settings."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export/Import Settings")
        self.setModal(True)
        self.resize(450, 200)
        self.result_action = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Description
        desc = QtWidgets.QLabel("Export current settings to a file or import settings from a file.")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Export section
        export_group = QtWidgets.QGroupBox("Export Settings")
        export_layout = QtWidgets.QVBoxLayout(export_group)
        
        export_desc = QtWidgets.QLabel("Save current application settings to a JSON file.")
        export_layout.addWidget(export_desc)
        
        self.export_btn = QtWidgets.QPushButton("Export Settings...")
        self.export_btn.clicked.connect(self.export_settings)
        export_layout.addWidget(self.export_btn)
        
        layout.addWidget(export_group)
        
        # Import section
        import_group = QtWidgets.QGroupBox("Import Settings")
        import_layout = QtWidgets.QVBoxLayout(import_group)
        
        import_desc = QtWidgets.QLabel("Load settings from a previously exported JSON file.")
        import_layout.addWidget(import_desc)
        
        self.import_btn = QtWidgets.QPushButton("Import Settings...")
        self.import_btn.clicked.connect(self.import_settings)
        import_layout.addWidget(self.import_btn)
        
        layout.addWidget(import_group)
        
        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)
    
    def export_settings(self):
        """Handle export settings action."""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Settings",
            "daq_settings_export.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            self.result_action = ("export", filename)
            self.accept()
    
    def import_settings(self):
        """Handle import settings action."""
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import Settings",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            self.result_action = ("import", filename)
            self.accept()
    
    def get_result(self):
        """Get the result action and filename."""
        return self.result_action


class DeviceInfoDialog(QtWidgets.QDialog):
    """Dialog showing detailed device information."""
    
    def __init__(self, device_name, parent=None):
        super().__init__(parent)
        self.device_name = device_name
        self.setWindowTitle(f"Device Information - {device_name}")
        self.setModal(True)
        self.resize(500, 400)
        self.setup_ui()
        self.load_device_info()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Device name
        name_label = QtWidgets.QLabel(f"Device: {self.device_name}")
        name_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(name_label)
        
        # Information text area
        self.info_text = QtWidgets.QTextEdit()
        self.info_text.setReadOnly(True)
        layout.addWidget(self.info_text)
        
        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def load_device_info(self):
        """Load and display device information."""
        try:
            from niDAQ import NIDAQReader
            
            # Try to get device capabilities
            info_lines = [
                f"Device Name: {self.device_name}",
                "",
                "Device Capabilities:",
                "==================="
            ]
            
            try:
                # Create a temporary reader to get device info
                from niDAQ import NIDAQSettings
                temp_settings = NIDAQSettings(device_name=self.device_name)
                temp_reader = NIDAQReader(temp_settings)
                
                # Get basic info
                info_lines.extend([
                    f"• Available analog input channels: ai0-ai15 (typical)",
                    f"• Supported sampling rates: 1 Hz to 250 kHz",
                    f"• Input voltage ranges: ±10V, ±5V, ±1V, ±0.2V",
                    f"• Resolution: 16-bit",
                    f"• Terminal configurations: RSE, NRSE, DIFF, PSEUDO-DIFF",
                    "",
                    "Current Status:",
                    "==============="
                ])
                
                # Try to get max conversion rate
                try:
                    temp_reader.start()
                    max_rate = temp_reader.get_max_conversion_rate()
                    if max_rate:
                        info_lines.append(f"• Maximum conversion rate: {max_rate:,.0f} Hz")
                    temp_reader.close()
                except Exception:
                    info_lines.append("• Device status: Available")
                    
            except Exception as e:
                info_lines.extend([
                    "• Status: Error accessing device",
                    f"• Error details: {str(e)}"
                ])
            
            info_lines.extend([
                "",
                "Supported Features:",
                "==================",
                "• Real-time data acquisition",
                "• Multi-channel synchronous sampling",
                "• Hardware-timed operations",
                "• Inter-channel delay control",
                "• Individual channel gain settings",
                "• Built-in calibration"
            ])
            
            self.info_text.setPlainText("\n".join(info_lines))
            
        except Exception as e:
            self.info_text.setPlainText(f"Error loading device information:\n{str(e)}")


class FilterHelpDialog(QtWidgets.QDialog):
    """Dialog with information about digital filters."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Digital Filters Help")
        self.setModal(True)
        self.resize(600, 500)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title = QtWidgets.QLabel("Digital Filters Guide")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Help content
        help_text = """
        <h3>Filter Types</h3>
        
        <p><b>Low Pass Filter:</b><br>
        Allows low-frequency signals to pass through while attenuating high-frequency components.
        Use to remove high-frequency noise.</p>
        
        <p><b>High Pass Filter:</b><br>
        Allows high-frequency signals to pass through while attenuating low-frequency components.
        Use to remove DC offset and low-frequency drift.</p>
        
        <p><b>Band Pass Filter:</b><br>
        Allows signals within a specific frequency range to pass through.
        Requires both low and high cutoff frequencies.</p>
        
        <p><b>Band Stop Filter:</b><br>
        Attenuates signals within a specific frequency range while passing others.
        Useful for removing specific frequency bands (e.g., power line interference).</p>
        
        <p><b>50Hz/60Hz Notch Filters:</b><br>
        Specialized filters to remove power line interference at 50Hz or 60Hz.
        These are pre-configured and don't require frequency settings.</p>
        
        <h3>Filter Parameters</h3>
        
        <p><b>Cutoff Frequency:</b><br>
        The frequency at which the filter begins to attenuate the signal (-3dB point).
        Should be chosen based on your signal characteristics and noise.</p>
        
        <p><b>Filter Order:</b><br>
        Higher order filters provide steeper roll-off (sharper transition) but may introduce
        more phase distortion. Typical values: 2-8.</p>
        
        <h3>Guidelines</h3>
        
        <ul>
        <li>Choose cutoff frequencies based on your signal bandwidth</li>
        <li>Higher order filters have steeper transitions but more delay</li>
        <li>Test filters with known signals to verify performance</li>
        <li>Consider the Nyquist frequency (half your sampling rate) as the maximum</li>
        <li>Filters work best when cutoff is well below the Nyquist frequency</li>
        </ul>
        """
        
        help_content = QtWidgets.QLabel(help_text)
        help_content.setWordWrap(True)
        help_content.setTextFormat(QtCore.Qt.TextFormat.RichText)
        
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(help_content)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        
        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
