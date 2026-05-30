"""Launch the dev settings launcher: python run_dev.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

from dev_launcher import main

if __name__ == "__main__":
    main()
