"""Processor Engine Package for Timetable Extraction."""

__version__ = "0.1.0"

from .main import process_timetable, save_to_json
from .models import TimetableDocument, TimetableEntry, Weekday, TimeSlot
from .preprocessor import DocumentPreprocessor
from .ocr_extractor import OCRExtractor
from .table_detector import TableDetector
from .parser import TimetableParser
from .utils import validate_document, is_supported_file

__all__ = [
    'process_timetable',
    'save_to_json',
    'TimetableDocument',
    'TimetableEntry',
    'Weekday',
    'TimeSlot',
    'DocumentPreprocessor',
    'OCRExtractor',
    'TableDetector',
    'TimetableParser',
    'validate_document',
    'is_supported_file',
]
