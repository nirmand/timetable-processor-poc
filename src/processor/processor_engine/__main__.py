"""Main module for running processor engine."""

import sys
from pathlib import Path

from processor_engine.main import process_timetable

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m processor_engine <file_path>")
        print("\nExample: python -m processor_engine /path/to/timetable.png")
        sys.exit(1)

    file_path = sys.argv[1]
    process_timetable(file_path)
