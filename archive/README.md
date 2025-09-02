# Archive Folder

This folder contains archived files from the DAQ project that are no longer actively used but kept for reference.

## Contents

### `DAQMainWindow.py`
- **Original monolithic DAQ application** (1,087 lines)
- **Archived on**: September 2, 2025
- **Reason**: Replaced by modular architecture in `main_window.py` + 7 other modules
- **Status**: Fully functional but superseded by modular version
- **Total Lines**: 1,087 lines
- **Functionality**: Complete DAQ application with GUI, plotting, settings, etc.

### Why Archived
The monolithic `DAQMainWindow.py` was successfully refactored into a modular architecture:
- **8 focused modules** with single responsibilities
- **Better maintainability** and code organization  
- **Enhanced features** (menu system, help dialogs, error handling)
- **Same functionality** with improved architecture
- **Total modular lines**: 2,582 lines across 8 files

### Usage Notes
If you need to reference the original implementation:
```bash
# To run the archived version (if needed for comparison)
python archive/DAQMainWindow.py
```

However, the recommended approach is to use the modular version:
```bash
# Run the current modular version
python main.py
```

### Migration Complete
✅ All functionality from `DAQMainWindow.py` has been successfully migrated to the modular architecture  
✅ No active code dependencies on the archived file  
✅ `main.py` updated to use modular version  
✅ All testing passed successfully  
