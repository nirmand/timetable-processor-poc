"""Command-line entry point for processor engine."""

import sys
from pathlib import Path

# Add parent directory to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from processor_engine import (
    process_timetable,
    save_to_json,
    validate_document,
    is_supported_file
)
from processor_engine.utils import format_confidence_report
from processor_engine.database import get_db_engine, create_tables, TimetableSource, ExtractedActivities
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json


def main():
    """Main entry point for command-line execution."""
    
    if len(sys.argv) < 2:
        print("="*70)
        print("TIMETABLE PROCESSOR - Command Line Interface")
        print("="*70)
        print("\nUsage: python scripts/run.py <file_path> [options]")
        print("\nArguments:")
        print("  file_path    Path to timetable file (required)")
        print("\nOptions:")
        print("  --gpu        Use GPU acceleration for OCR")
        print("  --output     Specify output JSON file path")
        print("\nSupported formats: PDF, DOCX, PNG, JPG, JPEG, BMP, TIFF")
        print("\nExamples:")
        print("  python scripts/run.py timetable.pdf")
        print("  python scripts/run.py schedule.png --output results.json")
        print("  python scripts/run.py timetable.pdf --gpu")
        sys.exit(1)
    
    file_path = sys.argv[1]
    use_gpu = '--gpu' in sys.argv
    
    # Determine output path
    output_path = None
    if '--output' in sys.argv:
        try:
            output_idx = sys.argv.index('--output')
            if output_idx + 1 < len(sys.argv):
                output_path = sys.argv[output_idx + 1]
        except (ValueError, IndexError):
            pass
    
    if not output_path:
        output_path = Path(file_path).stem + "_extracted.json"
    
    # Validate file
    if not is_supported_file(file_path):
        print(f"\n✗ Error: Unsupported file format")
        print("  Supported formats: PDF, DOCX, PNG, JPG, JPEG, BMP, TIFF")
        sys.exit(1)
    
    try:
        # Process the timetable
        document = process_timetable(file_path, use_gpu=use_gpu)
        
        # Validate results
        warnings = validate_document(document)
        if warnings:
            print("\n" + "="*70)
            print("VALIDATION WARNINGS")
            print("="*70)
            for warning in warnings:
                print(f"⚠ {warning}")
        
        # Display confidence report
        print("\n" + "="*70)
        print("CONFIDENCE ANALYSIS")
        print("="*70)
        print(format_confidence_report(document))
        
        # Save to JSON
        print("\n" + "="*70)
        print("SAVING RESULTS")
        print("="*70)
        save_to_json(document, output_path)

        # Persist results to SQLite database and return the timetable source id
        try:
            # Use repo-level db directory (../../db/timetable.sqlite relative to src/processor)
            engine = get_db_engine(db_path="../../db/timetable.sqlite")
            create_tables(engine)

            with Session(engine) as session:
                # Insert TimetableSource
                ts = TimetableSource(file_path=str(document.file_path), processed_at=datetime.now(timezone.utc))
                session.add(ts)
                session.commit()

                source_id = ts.id

                # Insert extracted activities
                for entry in document.entries:
                    day = entry.weekday.value if entry.weekday else "Unknown"
                    # Prefer datetime.time isoformat if available, otherwise fall back to raw_text or empty string
                    start_time = ""
                    end_time = ""
                    if entry.timeslot:
                        try:
                            if getattr(entry.timeslot, "start_time", None):
                                start_time = entry.timeslot.start_time.isoformat()
                        except Exception:
                            start_time = str(getattr(entry.timeslot, "raw_text", ""))
                        try:
                            if getattr(entry.timeslot, "end_time", None):
                                end_time = entry.timeslot.end_time.isoformat()
                        except Exception:
                            end_time = ""

                    notes = entry.notes if getattr(entry, "notes", None) else None

                    ea = ExtractedActivities(
                        source_id=source_id,
                        activity_id=None,
                        day=day,
                        start_time=str(start_time),
                        end_time=str(end_time),
                        notes=notes,
                    )
                    session.add(ea)

                session.commit()

            # Print result JSON so callers (Node) can parse the source id
            print(json.dumps({"timetable_source_id": source_id}))
        except Exception as e:
            print(f"\n✗ Database Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        
        print("\n✓ Processing completed successfully!")
        print(f"\nNext step: Use the extracted data from '{output_path}' for database integration")
        
    except FileNotFoundError as e:
        print(f"\n✗ File Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"\n✗ Validation Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Processing Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
