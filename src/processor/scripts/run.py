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
