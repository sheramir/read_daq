#!/usr/bin/env python3
"""
Simple test to verify the ImageExporter import works correctly.
"""

try:
    import pyqtgraph as pg
    from pyqtgraph.exporters import ImageExporter
    print("✓ Successfully imported ImageExporter from pyqtgraph.exporters")
    
    # Test creating a simple plot and exporter
    import numpy as np
    
    # Create a simple plot widget
    plot_widget = pg.PlotWidget()
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    plot_widget.plot(x, y, pen='r')
    
    # Test creating an exporter
    exporter = ImageExporter(plot_widget.plotItem)
    print("✓ Successfully created ImageExporter instance")
    
    # Test getting parameters
    params = exporter.parameters()
    print(f"✓ Exporter parameters available: {list(params.keys())}")
    
    print("\nScreenshot functionality should now work correctly!")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    print("PyQtGraph exporters module not available")
    
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    
# Show the format for screenshot filenames
import datetime
now = datetime.datetime.now()
time_str = now.strftime("%m.%d.%y-%H%M")

print(f"\nExample screenshot filename for current time:")
print(f"  graph-time-{time_str}-a1a5.png")
print(f"  (Captured at {now.strftime('%I:%M %p on %B %d, %Y')})")
