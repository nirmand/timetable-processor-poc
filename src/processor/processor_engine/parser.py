"""Parser to extract structured timetable data from OCR and table results."""

import re
from datetime import time, datetime
from typing import List, Dict, Optional, Tuple
from .models import TimetableEntry, TimetableDocument, Weekday, TimeSlot


class TimetableParser:
    """Parses extracted text and tables to create structured timetable entries."""
    
    def __init__(self):
        """Initialize the parser with regex patterns."""
        # Time patterns (e.g., "9:00", "10.45", "9-9:30", "11.00 - 11.55")
        self.time_pattern = re.compile(
            r'(\d{1,2})[:.](\d{2})\s*(?:am|pm|AM|PM)?'
        )
        
        # Time range patterns
        self.time_range_pattern = re.compile(
            r'(\d{1,2})[:.](\d{2})\s*(?:am|pm|AM|PM)?\s*[-–—]\s*(\d{1,2})[:.](\d{2})\s*(?:am|pm|AM|PM)?'
        )
        
        # Activity indicators (common subjects/activities)
        self.activity_keywords = {
            'maths', 'math', 'mathematics', 'english', 'reading', 'writing',
            'science', 'history', 'geography', 'art', 'music', 'pe', 'physical education',
            'computing', 'assembly', 'break', 'lunch', 'recess', 'phonics',
            'register', 'handwriting', 'spelling', 'topic', 'lesson',
            'story', 'comprehension', 'grammar', 'vocabulary',
            'outdoor', 'indoor', 'swimming', 're', 'religious education',
            'drama', 'dance', 'spanish', 'french', 'pshe'
        }
    
    def parse_document(
        self, 
        file_path: str,
        ocr_data: List[Dict[str, any]],
        table_data: List[Dict[str, any]]
    ) -> TimetableDocument:
        """
        Parse OCR and table data to create structured timetable document.
        
        Args:
            file_path: Path to source file
            ocr_data: Extracted OCR data
            table_data: Detected table data
        
        Returns:
            TimetableDocument with parsed entries
        """
        doc = TimetableDocument(file_path=file_path)
        
        # Extract metadata from OCR data
        self._extract_metadata(doc, ocr_data)
        
        # Parse tables if available (preferred method)
        if table_data:
            entries = self._parse_tables(table_data)
            for entry in entries:
                doc.add_entry(entry)
        else:
            # Fallback: Parse raw OCR data
            entries = self._parse_ocr_data(ocr_data)
            for entry in entries:
                doc.add_entry(entry)
        
        # Set extraction timestamp
        doc.extraction_timestamp = datetime.now().isoformat()
        
        return doc
    
    def _extract_metadata(
        self, 
        doc: TimetableDocument, 
        ocr_data: List[Dict[str, any]]
    ) -> None:
        """
        Extract metadata like class name, teacher, term from OCR data.
        
        Args:
            doc: TimetableDocument to update
            ocr_data: OCR extracted data
        """
        if not ocr_data:
            return
        
        # Look for metadata in first few lines
        text_items = [item.get('text', '') for item in ocr_data[:10] if item.get('text')]
        
        if not text_items:
            return
        
        full_text = ' '.join(text_items).lower()
        
        # Class pattern (e.g., "Class: 2EJ", "2EJ", "4M")
        class_pattern = re.compile(r'class[:\s]+([a-z0-9]+)|^(\d[a-z]{1,3})\b', re.IGNORECASE)
        class_match = class_pattern.search(' '.join(text_items))
        if class_match:
            doc.class_name = class_match.group(1) or class_match.group(2)
        
        # Teacher pattern (e.g., "Teacher: Miss Joynes", "Miss Joynes", "Mr. Smith")
        teacher_pattern = re.compile(r'teacher[:\s]+((?:miss|mrs|mr|ms)\.?\s+\w+)', re.IGNORECASE)
        teacher_match = teacher_pattern.search(full_text)
        if teacher_match:
            doc.teacher_name = teacher_match.group(1).title()
        
        # Term pattern (e.g., "Autumn 2 2024", "Spring 2 Week: 2")
        term_pattern = re.compile(r'(autumn|spring|summer)\s*\d+\s*(?:week[:\s]+\d+)?\s*\d{4}', re.IGNORECASE)
        term_match = term_pattern.search(full_text)
        if term_match:
            doc.term = term_match.group(0).title()
        
        # School pattern
        school_pattern = re.compile(r'([a-z\s]+(?:primary|secondary|school))', re.IGNORECASE)
        school_match = school_pattern.search(' '.join(text_items))
        if school_match:
            doc.school_name = school_match.group(1).strip().title()
    
    def _parse_tables(
        self, 
        table_data: List[Dict[str, any]]
    ) -> List[TimetableEntry]:
        """
        Parse table structure to extract timetable entries.
        
        Args:
            table_data: Detected tables
        
        Returns:
            List of TimetableEntry objects
        """
        entries = []
        
        for table in table_data:
            content = table.get('content', [])
            
            if not content or len(content) < 2:
                continue
            
            # Identify table structure
            structure = self._identify_table_structure(content)
            
            if structure['type'] == 'weekday_rows':
                entries.extend(self._parse_weekday_rows(content, structure))
            elif structure['type'] == 'weekday_columns':
                entries.extend(self._parse_weekday_columns(content, structure))
            else:
                # Generic parsing
                entries.extend(self._parse_generic_table(content))
        
        return entries
    
    def _identify_table_structure(self, content: List[List[str]]) -> Dict[str, any]:
        """
        Identify table structure (days in rows vs columns).
        
        Args:
            content: 2D table content
        
        Returns:
            Dictionary with structure information
        """
        structure = {'type': 'unknown', 'day_index': -1, 'time_indices': []}
        
        # Check first column for weekdays
        if content and len(content) > 1:
            first_col = []
            for row in content[1:]:
                if row and len(row) > 0:
                    first_col.append(row[0].lower() if isinstance(row[0], str) else '')
                else:
                    first_col.append('')
            
            weekday_count = sum(1 for cell in first_col if self._contains_weekday(cell))
            
            if weekday_count >= 3:
                structure['type'] = 'weekday_rows'
                structure['day_index'] = 0
                
                # Time slots likely in first row
                if content[0]:
                    structure['time_indices'] = [
                        i for i, cell in enumerate(content[0]) 
                        if cell and isinstance(cell, str) and self._contains_time(cell)
                    ]
                return structure
        
        # Check first row for weekdays
        if content and len(content) > 0 and content[0]:
            first_row = [cell.lower() if isinstance(cell, str) else '' for cell in content[0]]
            weekday_count = sum(1 for cell in first_row if self._contains_weekday(cell))
            
            if weekday_count >= 3:
                structure['type'] = 'weekday_columns'
                structure['day_indices'] = [
                    i for i, cell in enumerate(first_row) 
                    if self._contains_weekday(cell)
                ]
                return structure
        
        return structure
    
    def _parse_weekday_rows(
        self, 
        content: List[List[str]], 
        structure: Dict[str, any]
    ) -> List[TimetableEntry]:
        """
        Parse table where weekdays are in rows.
        
        Args:
            content: 2D table content
            structure: Identified structure
        
        Returns:
            List of TimetableEntry objects
        """
        entries = []
        day_col = structure['day_index']
        
        # Get time slots from header row
        time_slots = []
        if content:
            for i, cell in enumerate(content[0]):
                if i > day_col:  # Skip day column
                    timeslot = self.parse_timeslot(cell)
                    time_slots.append((i, timeslot))
        
        # Parse each row (each row is a day)
        for row in content[1:]:
            if not row or len(row) <= day_col:
                continue
            
            # Extract weekday
            day_text = row[day_col].strip()
            weekday = Weekday.from_string(day_text)
            
            if not weekday:
                continue
            
            # Extract activities for each time slot
            for col_idx, timeslot in time_slots:
                if col_idx < len(row):
                    activity_text = row[col_idx].strip()
                    
                    if activity_text and activity_text.lower() not in ['', 'nan', 'none']:
                        entry = TimetableEntry(
                            weekday=weekday,
                            timeslot=timeslot,
                            activity=activity_text,
                            confidence_score=0.85  # Table-based extraction is typically reliable
                        )
                        entries.append(entry)
        
        return entries
    
    def _parse_weekday_columns(
        self, 
        content: List[List[str]], 
        structure: Dict[str, any]
    ) -> List[TimetableEntry]:
        """
        Parse table where weekdays are in columns.
        
        Args:
            content: 2D table content
            structure: Identified structure
        
        Returns:
            List of TimetableEntry objects
        """
        entries = []
        day_indices = structure.get('day_indices', [])
        
        if not day_indices:
            return entries
        
        # Extract weekdays from header
        weekdays = []
        for idx in day_indices:
            if idx < len(content[0]):
                day_text = content[0][idx]
                weekday = Weekday.from_string(day_text)
                if weekday:
                    weekdays.append((idx, weekday))
        
        # Parse each row (each row is a time slot or activity)
        for row_idx in range(1, len(content)):
            row = content[row_idx]
            
            # Try to extract time from first column
            timeslot = None
            if row:
                timeslot = self.parse_timeslot(row[0])
            
            # Extract activities for each day
            for col_idx, weekday in weekdays:
                if col_idx < len(row):
                    activity_text = row[col_idx].strip()
                    
                    if activity_text and activity_text.lower() not in ['', 'nan', 'none']:
                        entry = TimetableEntry(
                            weekday=weekday,
                            timeslot=timeslot,
                            activity=activity_text,
                            confidence_score=0.85
                        )
                        entries.append(entry)
        
        return entries
    
    def _parse_generic_table(self, content: List[List[str]]) -> List[TimetableEntry]:
        """
        Generic table parsing when structure is unclear.
        
        Args:
            content: 2D table content
        
        Returns:
            List of TimetableEntry objects
        """
        entries = []
        
        for row in content:
            weekday = None
            timeslot = None
            activity = None
            
            for cell in row:
                if not weekday and self._contains_weekday(cell):
                    weekday = Weekday.from_string(cell)
                
                if not timeslot and self._contains_time(cell):
                    timeslot = self.parse_timeslot(cell)
                
                if not activity and self._is_activity(cell):
                    activity = cell.strip()
            
            if weekday and activity:
                entry = TimetableEntry(
                    weekday=weekday,
                    timeslot=timeslot,
                    activity=activity,
                    confidence_score=0.7  # Lower confidence for generic parsing
                )
                entries.append(entry)
        
        return entries
    
    def _parse_ocr_data(self, ocr_data: List[Dict[str, any]]) -> List[TimetableEntry]:
        """
        Parse raw OCR data when no tables detected.
        
        Args:
            ocr_data: OCR extracted data
        
        Returns:
            List of TimetableEntry objects
        """
        entries = []
        
        # Group text by rows
        rows = self._group_by_rows(ocr_data)
        
        current_day = None
        
        for row in rows:
            row_text = ' '.join([item['text'] for item in row])
            
            # Check for weekday
            weekday = None
            for item in row:
                wd = Weekday.from_string(item['text'])
                if wd:
                    weekday = wd
                    current_day = wd
                    break
            
            if not weekday:
                weekday = current_day
            
            # Extract timeslot
            timeslot = self.parse_timeslot(row_text)
            
            # Extract activity
            activity_parts = []
            for item in row:
                if (not self._contains_weekday(item['text']) and 
                    not self._is_time_only(item['text'])):
                    activity_parts.append(item['text'])
            
            activity = ' '.join(activity_parts).strip()
            
            if weekday and activity:
                avg_confidence = sum(item['confidence'] for item in row) / len(row)
                
                entry = TimetableEntry(
                    weekday=weekday,
                    timeslot=timeslot,
                    activity=activity,
                    confidence_score=avg_confidence
                )
                entries.append(entry)
        
        return entries
    
    def parse_timeslot(self, text: str) -> Optional[TimeSlot]:
        """
        Parse timeslot from text.
        
        Args:
            text: Text containing time information
        
        Returns:
            TimeSlot object or None
        """
        if not text or not isinstance(text, str):
            return None
        
        text = text.strip()
        
        if not text:
            return None
        
        # Try range pattern first
        range_match = self.time_range_pattern.search(text)
        if range_match:
            start_h, start_m, end_h, end_m = range_match.groups()
            
            try:
                start_time = time(int(start_h), int(start_m))
                end_time = time(int(end_h), int(end_m))
                
                return TimeSlot(
                    start_time=start_time,
                    end_time=end_time,
                    raw_text=text.strip()
                )
            except (ValueError, TypeError):
                pass
        
        # Try single time pattern
        time_match = self.time_pattern.search(text)
        if time_match:
            hour, minute = time_match.groups()
            
            try:
                t = time(int(hour), int(minute))
                return TimeSlot(start_time=t, raw_text=text.strip())
            except (ValueError, TypeError):
                pass
        
        # Return raw text if parseable times not found but text looks time-related
        if self._contains_time(text):
            return TimeSlot(raw_text=text.strip())
        
        return None
    
    def _contains_weekday(self, text: str) -> bool:
        """Check if text contains a weekday."""
        if not text or not isinstance(text, str):
            return False
        return Weekday.from_string(text) is not None
    
    def _contains_time(self, text: str) -> bool:
        """Check if text contains time information."""
        if not text or not isinstance(text, str):
            return False
        return bool(self.time_pattern.search(text) or 
                   self.time_range_pattern.search(text) or
                   'am' in text.lower() or 'pm' in text.lower())
    
    def _is_time_only(self, text: str) -> bool:
        """Check if text is only time (no other content)."""
        if not text or not isinstance(text, str):
            return False
        cleaned = re.sub(r'[\d:.\-–—\s]+(?:am|pm)?', '', text, flags=re.IGNORECASE)
        return len(cleaned.strip()) < 2
    
    def _is_activity(self, text: str) -> bool:
        """Check if text appears to be an activity."""
        if not text or not isinstance(text, str):
            return False
        
        text_lower = text.lower().strip()
        
        if len(text_lower) < 2:
            return False
        
        # Check against known activity keywords
        if any(keyword in text_lower for keyword in self.activity_keywords):
            return True
        
        # If it's not a weekday or time, and has reasonable length, consider it an activity
        if (not self._contains_weekday(text) and 
            not self._is_time_only(text) and 
            len(text_lower) >= 3):
            return True
        
        return False
    
    def _group_by_rows(
        self, 
        ocr_data: List[Dict[str, any]], 
        threshold: float = 0.02
    ) -> List[List[Dict[str, any]]]:
        """Group OCR data into rows based on vertical position."""
        if not ocr_data:
            return []
        
        rows = []
        current_row = [ocr_data[0]]
        current_y = ocr_data[0]['position'][1]
        
        for item in ocr_data[1:]:
            y = item['position'][1]
            
            if abs(y - current_y) <= threshold:
                current_row.append(item)
            else:
                current_row.sort(key=lambda x: x['position'][0])
                rows.append(current_row)
                current_row = [item]
                current_y = y
        
        if current_row:
            current_row.sort(key=lambda x: x['position'][0])
            rows.append(current_row)
        
        return rows
