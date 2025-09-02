# Tests and Examples

This folder contains test scripts, example code, and utility programs for the DAQ application.

## Test Files

### Core Functionality Tests
- **`test_settings.py`** - Tests settings persistence system
- **`test_delay_feature.py`** - Tests inter-channel delay functionality  
- **`test_imageexporter.py`** - Tests PyQtGraph screenshot/export functionality
- **`test_screenshot.py`** - Tests graph capture feature

### Verification Scripts
- **`verify_settings.py`** - Verifies settings loading/saving works correctly
- **`verify_screenshot.py`** - Verifies screenshot implementation is complete

## Example Programs

### Feature Demonstrations
- **`example_channel_gains.py`** - Demonstrates per-channel gain configuration
- **`example_delay_config.py`** - Shows inter-channel delay configuration
- **`example_screenshot.py`** - Graph capture feature examples
- **`get_daq_examples.py`** - Basic NIDAQReader usage patterns

## Utility Scripts

### System Utilities
- **`show_devices.py`** - Lists available NI DAQ devices
- **`python_check.py`** - Checks Python environment and dependencies

## Test Data

### Configuration Files
- **`test_daq_settings.json`** - Sample settings file for testing

## Running Tests

### Individual Tests
```bash
# Run specific test
python tests/test_settings.py
python tests/example_channel_gains.py
python tests/show_devices.py
```

### Verification Suite
```bash
# Verify core functionality
python tests/verify_settings.py
python tests/verify_screenshot.py
```

### Example Programs
```bash
# Learn about features
python tests/example_channel_gains.py
python tests/example_delay_config.py
```

## Test Categories

### Unit Tests
- Settings management
- Hardware configuration
- GUI component validation

### Integration Tests  
- End-to-end screenshot workflow
- Settings persistence across restarts
- Hardware compatibility validation

### Examples
- Feature usage demonstrations
- Best practices
- Configuration patterns

## Development Notes

These files help with:
- **Testing** new features before integration
- **Validation** of existing functionality
- **Documentation** through working examples
- **Debugging** hardware and software issues
- **Learning** how to use the DAQ system effectively

All test files are designed to run independently and provide clear output about what they're testing and the results.
