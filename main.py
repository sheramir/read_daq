from PySide6 import QtWidgets
import sys
from DAQMainWindow import DAQMainWindow  # Import the DAQMainWindow class

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = DAQMainWindow()
    win.show()
    sys.exit(app.exec())
