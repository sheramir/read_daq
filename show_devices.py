# Show available DAQ devices
import nidaqmx
from nidaqmx.system import System
print([d.name for d in System.local().devices])  # e.g. ['Dev1']
