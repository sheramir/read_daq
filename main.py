from PySide6 import QtWidgets
import sys
from main_window import DAQMainWindow  # Import the modular DAQMainWindow class

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = DAQMainWindow()
    win.show()
    sys.exit(app.exec())
