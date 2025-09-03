"""
Plot Manager Module

Handles plotting operations for both time domain and spectrum analysis.
Separated from main GUI for better maintainability.
"""

import pyqtgraph as pg
import numpy as np
from PySide6 import QtCore


class PlotManager(QtCore.QObject):
    """Manages plotting operations for time and spectrum analysis."""
    
    def __init__(self, time_plot_widget, spectrum_plot_widget):
        super().__init__()
        self.time_plot = time_plot_widget
        self.spectrum_plot = spectrum_plot_widget
        
        # Plot curves
        self.time_curves = []
        self.spectrum_curves = []
        
        # Legends
        self.time_legend = None
        self.spectrum_legend = None
        
        # Channel colors
        self.channel_colors = [
            (255, 0, 0), (0, 128, 255), (0, 200, 0), (255, 128, 0),
            (128, 0, 255), (0, 200, 200), (200, 200, 0), (128, 128, 128),
            (255, 0, 128), (0, 255, 128), (128, 255, 0), (128, 0, 0),
            (0, 128, 0), (0, 0, 128), (128, 128, 0), (128, 0, 128)
        ]
        
        # Visibility tracking
        self.channel_visibility = []
        
        self.setup_plots()
    
    def setup_plots(self):
        """Initialize plot widgets with proper styling."""
        # Time plot setup
        self.time_plot.setBackground("k")
        self.time_plot.setLabel("bottom", "Time", units="ms")
        self.time_plot.setLabel("left", "Voltage", units="V")
        
        # Spectrum plot setup
        self.spectrum_plot.setBackground("k")
        self.spectrum_plot.setLabel("left", "Power", units="dB")
        self.spectrum_plot.setLabel("bottom", "Frequency", units="Hz")
    
    def setup_curves(self, channels):
        """Setup plot curves for the given channels."""
        # Clear existing curves
        self.clear_plots()
        
        # Create new curves
        self.time_curves = []
        self.spectrum_curves = []
        self.channel_visibility = []
        
        # Add legends
        self.time_legend = self.time_plot.addLegend()
        self.spectrum_legend = self.spectrum_plot.addLegend()
        
        for i, channel in enumerate(channels):
            color = self.channel_colors[i % len(self.channel_colors)]
            pen = pg.mkPen(color=color, width=3)
            
            # Time domain curve
            time_curve = self.time_plot.plot([], [], pen=pen, name=channel.upper())
            self.time_curves.append(time_curve)
            
            # Frequency domain curve
            spectrum_curve = self.spectrum_plot.plot([], [], pen=pen, name=channel.upper())
            self.spectrum_curves.append(spectrum_curve)
            
            # Visibility tracking
            self.channel_visibility.append(True)
    
    def update_time_plot(self, t_data, y_data, auto_scale=True, y_range=None):
        """Update the time domain plot with new data."""
        if len(self.time_curves) == 0 or t_data.size == 0 or y_data.size == 0:
            return
        
        # Performance optimization: Aggressive downsampling for high-rate data
        # Estimate sampling rate from data
        if len(t_data) > 1:
            dt = t_data[1] - t_data[0]
            estimated_rate = 1.0 / dt if dt > 0 else 1000
        else:
            estimated_rate = 1000
        
        # Adaptive max plot points based on estimated sampling rate
        if estimated_rate >= 50000:
            max_plot_points = 1000  # Very aggressive for 50kHz+
        elif estimated_rate >= 25000:
            max_plot_points = 1500  # Moderate for 25kHz+
        else:
            max_plot_points = 2000  # Standard for lower rates
        
        if len(t_data) > max_plot_points:
            # Downsample by taking every nth point
            step = len(t_data) // max_plot_points
            t_display = t_data[::step]
            y_display = y_data[::step] if y_data.ndim == 1 else y_data[::step, :]
        else:
            t_display = t_data
            y_display = y_data
        
        # Update each curve
        for i, curve in enumerate(self.time_curves):
            if i < len(self.channel_visibility) and self.channel_visibility[i]:
                if i < y_display.shape[1]:
                    curve.setData(t_display, y_display[:, i])
                    curve.show()
                else:
                    curve.hide()
            else:
                curve.hide()
        
        # Set axis ranges
        if auto_scale:
            self.time_plot.enableAutoRange()
        elif y_range:
            self.time_plot.setYRange(y_range[0], y_range[1])
    
    def update_spectrum_plot(self, freqs, spectra, auto_scale=True):
        """Update the spectrum plot with new FFT data."""
        if len(self.spectrum_curves) == 0 or freqs is None or spectra is None:
            return
        
        # Update each spectrum curve
        for i, curve in enumerate(self.spectrum_curves):
            if i < len(self.channel_visibility) and self.channel_visibility[i]:
                if i < len(spectra) and len(freqs) > 0 and len(spectra[i]) > 0:
                    curve.setData(freqs, spectra[i])
                    curve.show()
                else:
                    curve.hide()
            else:
                curve.hide()
        
        # Auto-scale if requested
        if auto_scale:
            self.spectrum_plot.enableAutoRange()
    
    def set_channel_visibility(self, channel_index, visible):
        """Set visibility for a specific channel."""
        if 0 <= channel_index < len(self.channel_visibility):
            self.channel_visibility[channel_index] = visible
            
            # Update curve visibility immediately
            if channel_index < len(self.time_curves):
                if visible:
                    self.time_curves[channel_index].show()
                else:
                    self.time_curves[channel_index].hide()
            
            if channel_index < len(self.spectrum_curves):
                if visible:
                    self.spectrum_curves[channel_index].show()
                else:
                    self.spectrum_curves[channel_index].hide()
    
    def get_channel_visibility(self):
        """Get current channel visibility states."""
        return self.channel_visibility.copy()
    
    def set_all_visibility(self, visibility_list):
        """Set visibility for all channels from a list."""
        for i, visible in enumerate(visibility_list):
            if i < len(self.channel_visibility):
                self.set_channel_visibility(i, visible)
    
    def clear_plots(self):
        """Clear both plots and remove legends."""
        self.time_plot.clear()
        self.spectrum_plot.clear()
        
        # Clear curves lists
        self.time_curves = []
        self.spectrum_curves = []
        
        # Reset legends
        self.time_legend = None
        self.spectrum_legend = None
    
    def get_time_plot_widget(self):
        """Get the time plot widget for external operations (e.g., screenshots)."""
        return self.time_plot
    
    def get_spectrum_plot_widget(self):
        """Get the spectrum plot widget for external operations (e.g., screenshots)."""
        return self.spectrum_plot
    
    def set_time_plot_title(self, title):
        """Set the title for the time plot."""
        self.time_plot.setTitle(title)
    
    def set_spectrum_plot_title(self, title):
        """Set the title for the spectrum plot."""
        self.spectrum_plot.setTitle(title)
    
    def enable_time_plot_grid(self, enable=True):
        """Enable or disable grid on time plot."""
        self.time_plot.showGrid(x=enable, y=enable)
    
    def enable_spectrum_plot_grid(self, enable=True):
        """Enable or disable grid on spectrum plot."""
        self.spectrum_plot.showGrid(x=enable, y=enable)
    
    def set_time_plot_range(self, x_range=None, y_range=None):
        """Set specific ranges for time plot axes."""
        if x_range:
            self.time_plot.setXRange(x_range[0], x_range[1])
        if y_range:
            self.time_plot.setYRange(y_range[0], y_range[1])
    
    def set_spectrum_plot_range(self, x_range=None, y_range=None):
        """Set specific ranges for spectrum plot axes."""
        if x_range:
            self.spectrum_plot.setXRange(x_range[0], x_range[1])
        if y_range:
            self.spectrum_plot.setYRange(y_range[0], y_range[1])
    
    def get_plot_count(self):
        """Get the number of active plot curves."""
        return len(self.time_curves)
    
    def has_data(self):
        """Check if plots have any data."""
        return len(self.time_curves) > 0
