"""
File Manager Module

Handles file operations including data saving and screenshot capture.
Separated from main window for better maintainability.
"""

import os
import csv
import datetime
from PySide6 import QtCore, QtWidgets
from pyqtgraph.exporters import ImageExporter
from niDAQ import NIDAQSettings


class FileManager(QtCore.QObject):
    """Manages file operations for data saving and screenshots."""
    
    # Signals
    file_saved = QtCore.Signal(str)  # File path
    file_error = QtCore.Signal(str)  # Error message
    directory_selected = QtCore.Signal(str)  # Directory path
    
    def __init__(self):
        super().__init__()
        self.save_directory = None
    
    def set_save_directory(self, directory):
        """Set the directory for saving files."""
        if directory and os.path.isdir(directory):
            self.save_directory = directory
            self.directory_selected.emit(directory)
            return True
        return False
    
    def get_save_directory(self):
        """Get the current save directory."""
        return self.save_directory
    
    def browse_directory(self, parent_widget=None, current_directory=None):
        """Open directory selection dialog."""
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            parent_widget,
            "Select Directory for Saving Files",
            current_directory or self.save_directory or ""
        )
        
        if directory:
            self.set_save_directory(directory)
            return directory
        return None
    
    def save_data_csv(self, filename, history_t, history_y, settings_dict):
        """Save data to CSV file."""
        if not self.save_directory:
            self.file_error.emit("No save directory selected")
            return False
        
        if not filename.strip():
            self.file_error.emit("No filename provided")
            return False
        
        # Add .csv extension if not provided
        if not filename.lower().endswith('.csv'):
            filename += '.csv'
        
        full_path = os.path.join(self.save_directory, filename)
        
        try:
            # Check if we have data to save
            if not history_t or not history_y:
                self.file_error.emit("No data to save")
                return False
            
            # Create settings object for channel info
            settings = NIDAQSettings(
                device_name=settings_dict.get('device_name', ''),
                channels=settings_dict.get('channels', []),
                sampling_rate_hz=settings_dict.get('sampling_rate', 1000),
                terminal_config=settings_dict.get('terminal_config', 'RSE'),
                v_min=settings_dict.get('v_min', -1.0),
                v_max=settings_dict.get('v_max', 1.0),
                channel_ranges=settings_dict.get('channel_ranges')
            )
            
            # Save as CSV
            with open(full_path, "w", newline="") as f:
                writer = csv.writer(f)
                
                # Write header
                header = ["sample_index", "timestamp_ms"] + settings.channels
                writer.writerow(header)
                
                # Write data
                for i, (t, y_row) in enumerate(zip(history_t, history_y)):
                    if isinstance(y_row, (list, tuple)):
                        data_row = [i, t] + list(y_row)
                    else:
                        data_row = [i, t, y_row]
                    writer.writerow(data_row)
            
            self.file_saved.emit(full_path)
            return True
            
        except Exception as e:
            self.file_error.emit(f"Error saving CSV: {e}")
            return False
    
    def capture_screenshot(self, plot_widget, graph_type, active_channels):
        """Capture screenshot of plot widget and save as PNG."""
        if not self.save_directory:
            self.file_error.emit("No save directory selected")
            return False
        
        try:
            # Get current time for filename
            now = datetime.datetime.now()
            time_str = now.strftime("%m.%d.%y-%H%M")
            
            # Create channel string for filename
            if active_channels:
                # Convert channel names (e.g., "ai0" -> "a0")
                channel_codes = []
                for channel in active_channels:
                    if channel.startswith("ai"):
                        channel_codes.append("a" + channel[2:])
                    else:
                        channel_codes.append(channel)
                channels_str = "".join(channel_codes)
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
            
            self.file_saved.emit(filename)
            return True
            
        except Exception as e:
            self.file_error.emit(f"Error capturing screenshot: {e}")
            return False
    
    def get_display_path(self, path, max_length=50):
        """Get a shortened path for display purposes."""
        if not path:
            return "No directory selected"
        
        if len(path) > max_length:
            return "..." + path[-(max_length-3):]
        return path
    
    def validate_filename(self, filename):
        """Validate filename for file system compatibility."""
        if not filename.strip():
            return False, "Filename cannot be empty"
        
        # Check for invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            if char in filename:
                return False, f"Filename cannot contain '{char}'"
        
        # Check length
        if len(filename) > 255:
            return False, "Filename too long (max 255 characters)"
        
        return True, ""
    
    def get_unique_filename(self, base_filename):
        """Get a unique filename by adding numbers if file exists."""
        if not self.save_directory:
            return base_filename
        
        full_path = os.path.join(self.save_directory, base_filename)
        
        if not os.path.exists(full_path):
            return base_filename
        
        # Split filename and extension
        name, ext = os.path.splitext(base_filename)
        
        counter = 1
        while True:
            new_filename = f"{name}_{counter}{ext}"
            new_path = os.path.join(self.save_directory, new_filename)
            if not os.path.exists(new_path):
                return new_filename
            counter += 1
    
    def create_data_backup(self, history_t, history_y, settings_dict):
        """Create an automatic backup of current data."""
        if not self.save_directory or not history_t or not history_y:
            return False
        
        try:
            # Create backup filename with timestamp
            now = datetime.datetime.now()
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_data_{timestamp}.csv"
            
            return self.save_data_csv(backup_filename, history_t, history_y, settings_dict)
            
        except Exception as e:
            self.file_error.emit(f"Error creating backup: {e}")
            return False
    
    def export_settings(self, settings_dict):
        """Export current settings to a JSON file."""
        if not self.save_directory:
            self.file_error.emit("No save directory selected")
            return False
        
        try:
            import json
            
            # Create settings filename with timestamp
            now = datetime.datetime.now()
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            settings_filename = f"daq_settings_export_{timestamp}.json"
            full_path = os.path.join(self.save_directory, settings_filename)
            
            with open(full_path, 'w') as f:
                json.dump(settings_dict, f, indent=2)
            
            self.file_saved.emit(full_path)
            return True
            
        except Exception as e:
            self.file_error.emit(f"Error exporting settings: {e}")
            return False
    
    def get_file_info(self, filename):
        """Get information about a file in the save directory."""
        if not self.save_directory or not filename:
            return None
        
        full_path = os.path.join(self.save_directory, filename)
        
        try:
            if os.path.exists(full_path):
                stat = os.stat(full_path)
                return {
                    'size': stat.st_size,
                    'modified': datetime.datetime.fromtimestamp(stat.st_mtime),
                    'created': datetime.datetime.fromtimestamp(stat.st_ctime),
                    'exists': True
                }
            else:
                return {'exists': False}
        except Exception:
            return None
    
    def cleanup_old_backups(self, max_backups=10):
        """Clean up old backup files, keeping only the most recent ones."""
        if not self.save_directory:
            return 0
        
        try:
            # Find all backup files
            backup_files = []
            for filename in os.listdir(self.save_directory):
                if filename.startswith('backup_data_') and filename.endswith('.csv'):
                    full_path = os.path.join(self.save_directory, filename)
                    mtime = os.path.getmtime(full_path)
                    backup_files.append((mtime, full_path))
            
            # Sort by modification time (newest first)
            backup_files.sort(reverse=True)
            
            # Remove old backups
            removed_count = 0
            for i, (mtime, filepath) in enumerate(backup_files):
                if i >= max_backups:
                    try:
                        os.remove(filepath)
                        removed_count += 1
                    except Exception:
                        pass
            
            return removed_count
            
        except Exception:
            return 0
