# Show available DAQ devices
import nidaqmx
from nidaqmx.system import System

try:
	devices = list(System.local().devices)
	for device in devices:
		print(f"Device Name: {device.name}, Product Type: {device.product_type}")
	device_names = [d.name for d in devices]
	print(device_names)  # e.g. ['Dev1']
	if not devices:
		print("No DAQ devices found.")
except Exception as e:
	print(f"Error accessing DAQ devices: {e}")
