"""Core execution logic for processor engine."""

import json
from pathlib import Path
from typing import Optional

from .database import get_db_engine, create_tables
from .preprocessor import DocumentPreprocessor
from .ocr_extractor import OCRExtractor
from .table_detector import TableDetector
from .parser import TimetableParser
from .models import TimetableDocument

# Supported file extensions
SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.pdf', '.docx', '.bmp', '.tiff', '.tif'}


def process_timetable(file_path: str, use_gpu: bool = False) -> TimetableDocument:
    """
    Process a single timetable file and extract structured data.

    This function handles various file formats (PDF, DOCX, images) and layouts,
    extracting weekdays, timeslots, activities, and notes from timetables.

    Args:
        file_path: Absolute or relative path to the timetable file
        use_gpu: Whether to use GPU acceleration for OCR (default: False)

    Returns:
        TimetableDocument containing extracted entries

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the file format is not supported
        Exception: If processing fails
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

        # print(f"\n{'='*60}")
        print(f"▶ Processing Timetable: {file_path.name}")
        # print(f"{'='*60}")

        # Step 1: Preprocess document (convert to images)
        print("\n[1/5] Preprocessing document...")
        preprocessor = DocumentPreprocessor()
        images = preprocessor.process(file_path)
        print(f"✓ Converted to {len(images)} image(s)")

        # Step 2: Extract text using OCR
        print("\n[2/5] Extracting text with PaddleOCR...")
        ocr_extractor = OCRExtractor(use_gpu=use_gpu)
        
        all_ocr_data = []
        for idx, image in enumerate(images):
            print(f"  → Processing page {idx + 1}/{len(images)}...")
            ocr_data = ocr_extractor.extract_text(image)
            all_ocr_data.extend(ocr_data)
            print(f"    Extracted {len(ocr_data)} text elements")
        
        avg_confidence = ocr_extractor.calculate_confidence_score(all_ocr_data)
        print(f"✓ OCR completed (avg confidence: {avg_confidence:.2%})")

        # Step 3: Detect tables
        print("\n[3/5] Detecting tables with img2table...")
        table_detector = TableDetector(use_gpu=use_gpu)
        
        all_tables = []
        for idx, image in enumerate(images):
            print(f"  → Analyzing page {idx + 1}/{len(images)}...")
            tables = table_detector.detect_tables(image)
            all_tables.extend(tables)
            print(f"    Found {len(tables)} table(s)")
        
        print(f"✓ Detected {len(all_tables)} total table(s)")

        # Step 4: Parse extracted data
        print("\n[4/5] Parsing timetable data...")
        parser = TimetableParser()
        document = parser.parse_document(
            file_path=str(file_path.absolute()),
            ocr_data=all_ocr_data,
            table_data=all_tables
        )
        print(f"✓ Extracted {len(document.entries)} timetable entries")

        # Step 5: Display summary
        print("\n[5/5] Extraction Summary")
        print(f"{'─'*60}")
        _print_document_summary(document)

        print(f"\n{'='*60}")
        print("✓ Timetable processing completed successfully")
        print(f"{'='*60}\n")

        return document

    except (FileNotFoundError, ValueError) as e:
        print(f"\n✗ Validation error: {str(e)}")
        raise
    except Exception as e:
        print(f"\n✗ Error during timetable processing: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def save_to_json(document: TimetableDocument, output_path: str) -> None:
    """
    Save extracted timetable data to JSON file.

    Args:
        document: TimetableDocument to save
        output_path: Path to output JSON file
    """
    data = {
        'file_path': document.file_path,
        'metadata': {
            'class_name': document.class_name,
            'teacher_name': document.teacher_name,
            'term': document.term,
            'school_name': document.school_name,
            'extraction_timestamp': document.extraction_timestamp,
        },
        'entries': [
            {
                'weekday': entry.weekday.value if entry.weekday else None,
                'timeslot': {
                    'start_time': entry.timeslot.start_time.isoformat() if entry.timeslot and entry.timeslot.start_time else None,
                    'end_time': entry.timeslot.end_time.isoformat() if entry.timeslot and entry.timeslot.end_time else None,
                    'raw_text': entry.timeslot.raw_text if entry.timeslot else None,
                },
                'activity': entry.activity,
                'notes': entry.notes,
                'subject': entry.subject,
                'location': entry.location,
                'confidence_score': entry.confidence_score,
            }
            for entry in document.entries
        ]
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved to: {output_path}")


def _print_document_summary(document: TimetableDocument) -> None:
    """Print a summary of the extracted document."""
    
    # Metadata
    if document.class_name:
        print(f"  Class: {document.class_name}")
    if document.teacher_name:
        print(f"  Teacher: {document.teacher_name}")
    if document.term:
        print(f"  Term: {document.term}")
    if document.school_name:
        print(f"  School: {document.school_name}")
    
    print(f"\n  Total Entries: {len(document.entries)}")
    
    # Group by weekday
    from .models import Weekday
    for day in Weekday:
        entries = document.get_entries_by_day(day)
        if entries:
            print(f"    {day.value}: {len(entries)} entries")
    
    # Show first few entries as examples
    if document.entries:
        print("\n  Sample Entries:")
        for i, entry in enumerate(document.entries[:3], 1):
            day = entry.weekday.value if entry.weekday else "N/A"
            time = str(entry.timeslot) if entry.timeslot else "N/A"
            activity = entry.activity[:40] + "..." if len(entry.activity) > 40 else entry.activity
            print(f"    {i}. {day} | {time} | {activity}")
        
        if len(document.entries) > 3:
            print(f"    ... and {len(document.entries) - 3} more entries")
