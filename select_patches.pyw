"""Double-click on Windows with Python and Tcl/Tk installed."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

if __name__ == "__main__":
    from patch_selector import main
    main(["--gui"])
