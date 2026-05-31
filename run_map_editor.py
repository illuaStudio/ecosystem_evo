"""Launch the map editor: python run_map_editor.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from map_editor.app import main

if __name__ == "__main__":
    main()
