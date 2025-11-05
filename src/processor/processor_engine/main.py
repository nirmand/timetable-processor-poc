"""Core execution logic for processor engine."""

import os
from pathlib import Path
from img2table.document import ImageTableExtractor
from paddleocr import PaddleOCR

from .database import get_db_engine, create_tables

# Supported image extensions
SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.pdf', '.docx'}


def process_timetable(file_path: str) -> None:
    """
    Process a single timetable image file and extract data.

    Args:
        file_path: Absolute or relative path to the timetable image file

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the file is not a supported image format
    """
    try:
        # Convert to Path object and validate
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format: {file_path.suffix}. "
                f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

        # Initialize database
        engine = get_db_engine()
        create_tables(engine)
        print("✓ Database initialized successfully")

        # Initialize PaddleOCR configuration
        ocr_config = PaddleOCR(use_gpu=False, lang=['en'])
        print("✓ PaddleOCR configuration initialized")

        print(f"\n▶ Starting extraction for: {file_path.name}")
        print(f"→ File path: {file_path.absolute()}")

        # Placeholder for extraction logic
        print(f"→ Attempting to process {file_path.name}")

        print("\n✓ Timetable processing completed")

    except (FileNotFoundError, ValueError) as e:
        print(f"✗ Validation error: {str(e)}")
        raise
    except Exception as e:
        print(f"✗ Error during timetable processing: {type(e).__name__}: {str(e)}")
        raise
