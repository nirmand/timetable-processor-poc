"""Command-line entry point for processor engine."""

import sys
from pathlib import Path

# Add parent directory to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from processor_engine.main import process_timetable


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run.py <file_path>")
        print("\nExample: python scripts/run.py /path/to/timetable.png")
        sys.exit(1)

    file_path = sys.argv[1]
    process_timetable(file_path)
