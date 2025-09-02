# Check pyqt installation

import sys, os, pyqtgraph as pg, PySide6
print("Python:", sys.executable)
print("pyqtgraph:", pg.__version__, "->", pg.__file__)
print("PySide6:", PySide6.__file__)
# Examples availability
import importlib.util, pathlib
ex_dir = pathlib.Path(pg.__file__).parent / "examples"
print("examples dir exists on disk:", ex_dir.is_dir())
try:
    import pyqtgraph.examples as ex
    print("import pyqtgraph.examples: OK")
except Exception as e:
    print("import pyqtgraph.examples: FAIL ->", e)
