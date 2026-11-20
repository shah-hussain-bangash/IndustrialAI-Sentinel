"""Compatibility entry point: use the checked current-schema upgrader."""
import runpy
from pathlib import Path
if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("upgrade_database.py")),run_name="__main__")
