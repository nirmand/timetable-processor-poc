"""Validation and utility functions for timetable processing."""

import re
from pathlib import Path
from typing import Optional, List
from .models import TimetableDocument, TimetableEntry


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_file_path(file_path: str, supported_extensions: set) -> Path:
    """
    Validate file path and extension.
    
    Args:
        file_path: Path to validate
        supported_extensions: Set of supported file extensions
    
    Returns:
        Validated Path object
    
    Raises:
        ValidationError: If validation fails
    """
    try:
        path = Path(file_path)
    except Exception as e:
        raise ValidationError(f"Invalid file path: {e}")
    
    if not path.exists():
        raise ValidationError(f"File not found: {path}")
    
    if not path.is_file():
        raise ValidationError(f"Path is not a file: {path}")
    
    if path.suffix.lower() not in supported_extensions:
        raise ValidationError(
            f"Unsupported file format: {path.suffix}. "
            f"Supported formats: {', '.join(sorted(supported_extensions))}"
        )
    
    return path


def validate_document(document: TimetableDocument) -> List[str]:
    """
    Validate extracted timetable document and return warnings.
    
    Args:
        document: TimetableDocument to validate
    
    Returns:
        List of validation warning messages
    """
    warnings = []
    
    # Check if any entries were extracted
    if not document.entries:
        warnings.append("No timetable entries were extracted")
        return warnings
    
    # Check for entries without weekday
    missing_weekday = sum(1 for e in document.entries if not e.weekday)
    if missing_weekday > 0:
        warnings.append(f"{missing_weekday} entries missing weekday information")
    
    # Check for entries without timeslot
    missing_timeslot = sum(1 for e in document.entries if not e.timeslot)
    if missing_timeslot > 0:
        warnings.append(f"{missing_timeslot} entries missing timeslot information")
    
    # Check for entries with low confidence
    low_confidence = sum(1 for e in document.entries if e.confidence_score < 0.5)
    if low_confidence > 0:
        warnings.append(f"{low_confidence} entries have low confidence (< 50%)")
    
    # Check for suspiciously short activities
    short_activities = sum(1 for e in document.entries if len(e.activity.strip()) < 2)
    if short_activities > 0:
        warnings.append(f"{short_activities} entries have very short activity text")
    
    # Check metadata presence
    if not document.class_name:
        warnings.append("Class name not detected")
    if not document.teacher_name:
        warnings.append("Teacher name not detected")
    
    return warnings


def sanitize_text(text: str) -> str:
    """
    Sanitize extracted text by removing unwanted characters.
    
    Args:
        text: Text to sanitize
    
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters that might cause issues
    text = text.replace('\x00', '')
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def normalize_activity_name(activity: str) -> str:
    """
    Normalize activity names for consistency.
    
    Args:
        activity: Activity name to normalize
    
    Returns:
        Normalized activity name
    """
    activity = sanitize_text(activity)
    
    # Common substitutions
    replacements = {
        'math': 'Maths',
        'pe': 'PE',
        'phys ed': 'PE',
        'physical education': 'PE',
        'comp': 'Computing',
        're': 'RE',
        'religious education': 'RE',
    }
    
    activity_lower = activity.lower()
    for old, new in replacements.items():
        if old in activity_lower:
            activity = re.sub(old, new, activity, flags=re.IGNORECASE)
    
    return activity.strip()


def merge_duplicate_entries(entries: List[TimetableEntry]) -> List[TimetableEntry]:
    """
    Merge duplicate entries (same day, time, activity).
    
    Args:
        entries: List of entries to deduplicate
    
    Returns:
        Deduplicated list of entries
    """
    if not entries:
        return []
    
    unique_entries = []
    seen = set()
    
    for entry in entries:
        # Create a key for deduplication
        key = (
            entry.weekday.value if entry.weekday else None,
            str(entry.timeslot) if entry.timeslot else None,
            entry.activity.lower().strip()
        )
        
        if key not in seen:
            seen.add(key)
            unique_entries.append(entry)
    
    return unique_entries


def format_confidence_report(document: TimetableDocument) -> str:
    """
    Generate a confidence report for the extracted document.
    
    Args:
        document: TimetableDocument to analyze
    
    Returns:
        Formatted report string
    """
    if not document.entries:
        return "No entries to analyze"
    
    scores = [e.confidence_score for e in document.entries if e.confidence_score > 0]
    
    if not scores:
        return "No confidence scores available"
    
    avg_score = sum(scores) / len(scores)
    min_score = min(scores)
    max_score = max(scores)
    
    high_confidence = sum(1 for s in scores if s >= 0.8)
    medium_confidence = sum(1 for s in scores if 0.5 <= s < 0.8)
    low_confidence = sum(1 for s in scores if s < 0.5)
    
    report = f"""
Confidence Report:
  Average: {avg_score:.2%}
  Range: {min_score:.2%} - {max_score:.2%}
  
  Distribution:
    High (≥80%): {high_confidence} entries
    Medium (50-80%): {medium_confidence} entries
    Low (<50%): {low_confidence} entries
"""
    
    return report.strip()


def estimate_processing_time(file_path: Path) -> str:
    """
    Estimate processing time based on file size.
    
    Args:
        file_path: Path to file
    
    Returns:
        Estimated time description
    """
    try:
        size_mb = file_path.stat().st_size / (1024 * 1024)
        
        if size_mb < 1:
            return "< 30 seconds"
        elif size_mb < 5:
            return "30-60 seconds"
        elif size_mb < 10:
            return "1-2 minutes"
        else:
            return "2-5 minutes"
    except Exception:
        return "Unknown"


def is_supported_file(file_path: str) -> bool:
    """
    Quick check if file is supported.
    
    Args:
        file_path: Path to check
    
    Returns:
        True if file extension is supported
    """
    supported = {'.png', '.jpg', '.jpeg', '.pdf', '.docx', '.bmp', '.tiff', '.tif'}
    try:
        path = Path(file_path)
        return path.suffix.lower() in supported
    except Exception:
        return False
