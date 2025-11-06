"""Data models for timetable extraction."""

from dataclasses import dataclass, field
from datetime import time
from typing import Optional
from enum import Enum


class Weekday(Enum):
    """Enumeration for days of the week."""
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"
    SUNDAY = "Sunday"

    @classmethod
    def from_string(cls, day_str: str) -> Optional['Weekday']:
        """
        Parse weekday from various string formats.
        
        Args:
            day_str: String representation of weekday (e.g., "Mon", "Monday", "M")
        
        Returns:
            Weekday enum or None if not matched
        """
        if not day_str or not isinstance(day_str, str):
            return None
        
        day_str = day_str.strip().upper()
        
        if not day_str:
            return None
        
        day_mapping = {
            'M': cls.MONDAY, 'MON': cls.MONDAY, 'MONDAY': cls.MONDAY,
            'TU': cls.TUESDAY, 'TUE': cls.TUESDAY, 'TUES': cls.TUESDAY, 'TUESDAY': cls.TUESDAY,
            'W': cls.WEDNESDAY, 'WED': cls.WEDNESDAY, 'WEDNESDAY': cls.WEDNESDAY,
            'TH': cls.THURSDAY, 'THU': cls.THURSDAY, 'THUR': cls.THURSDAY, 'THURS': cls.THURSDAY, 'THURSDAY': cls.THURSDAY,
            'F': cls.FRIDAY, 'FRI': cls.FRIDAY, 'FRIDAY': cls.FRIDAY,
            'SA': cls.SATURDAY, 'SAT': cls.SATURDAY, 'SATURDAY': cls.SATURDAY,
            'SU': cls.SUNDAY, 'SUN': cls.SUNDAY, 'SUNDAY': cls.SUNDAY,
        }
        
        return day_mapping.get(day_str)


@dataclass
class TimeSlot:
    """Represents a time slot in the timetable."""
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    raw_text: str = ""  # Original text (e.g., "9:00-9:30", "10.45 - 11.00")
    
    def __str__(self) -> str:
        if self.start_time and self.end_time:
            return f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        return self.raw_text


@dataclass
class TimetableEntry:
    """Represents a single timetable entry/activity."""
    weekday: Optional[Weekday] = None
    timeslot: Optional[TimeSlot] = None
    activity: str = ""
    notes: Optional[str] = None
    
    # Additional metadata
    subject: Optional[str] = None  # For subject-specific activities
    location: Optional[str] = None  # Classroom or location if specified
    confidence_score: float = 0.0  # OCR confidence
    
    def __str__(self) -> str:
        day = self.weekday.value if self.weekday else "Unknown"
        time = str(self.timeslot) if self.timeslot else "No time"
        return f"{day} {time}: {self.activity}"


@dataclass
class TimetableDocument:
    """Represents the complete extracted timetable."""
    file_path: str
    entries: list[TimetableEntry] = field(default_factory=list)
    
    # Metadata
    class_name: Optional[str] = None
    teacher_name: Optional[str] = None
    term: Optional[str] = None
    school_name: Optional[str] = None
    extraction_timestamp: Optional[str] = None
    
    def add_entry(self, entry: TimetableEntry) -> None:
        """Add a timetable entry to the document."""
        self.entries.append(entry)
    
    def get_entries_by_day(self, weekday: Weekday) -> list[TimetableEntry]:
        """Get all entries for a specific weekday."""
        return [entry for entry in self.entries if entry.weekday == weekday]
    
    def __len__(self) -> int:
        return len(self.entries)
