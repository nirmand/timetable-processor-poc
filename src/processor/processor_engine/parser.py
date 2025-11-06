"""Parser to extract structured timetable data from OCR and table results."""

import re
from datetime import time, datetime
from typing import List, Dict, Optional, Tuple
from .models import TimetableEntry, TimetableDocument, Weekday, TimeSlot
from .utils import normalize_activity_name


class TimetableParser:
    """Parses extracted text and tables to create structured timetable entries."""
    
    def __init__(self):
        """Initialize the parser with regex patterns."""
        # Flexible time detection (hours with optional minutes and optional am/pm)
        # Examples matched: '9', '9:00', '09.30', '1pm', '1:15 pm'
        self._time_re = re.compile(r'(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|AM|PM)?')
        
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
            # Try a smarter OCR-only fallback that infers column time slots from
            # header time tokens and maps OCR boxes into those columns. If that
            # fails, fall back to the older row-based OCR parser.
            entries = self._parse_ocr_with_inferred_columns(ocr_data)
            if not entries:
                entries = self._parse_ocr_data(ocr_data)

            for entry in entries:
                doc.add_entry(entry)
        
        # Set extraction timestamp
        doc.extraction_timestamp = datetime.now().isoformat()

        # Post-process entries: try to assign missing times using OCR header time tokens
        try:
            self._postprocess_entries(doc, ocr_data)
        except Exception:
            # non-fatal
            pass

        # Normalize activities and fill in simple, known default blocks
        try:
            self._normalize_and_fill_defaults(doc)
        except Exception:
            # best-effort only
            pass

        return doc

    def _postprocess_entries(self, doc: TimetableDocument, ocr_data: List[Dict[str, any]]) -> None:
        """
        Post-process parsed entries to assign missing times where possible.

        Strategy (heuristic):
        - Collect time tokens from OCR that appear near the top of the page (header row)
        - Sort them left-to-right to form the column time slots
        - For each weekday, assign missing times to entries in reading order using these header slots
        This is a best-effort heuristic for cases where table structure wasn't detected.
        """
        if not ocr_data or not doc.entries:
            return

        # Collect header-like time tokens (located near top of page)
        header_candidates = []
        for item in ocr_data:
            txt = item.get('text', '')
            if not txt or not isinstance(txt, str):
                continue
            if self._contains_time(txt):
                # prefer items near the top (norm y small)
                pos = item.get('position', (0.5, 0.5))
                y = pos[1]
                x = pos[0]
                header_candidates.append((y, x, txt))

        if not header_candidates:
            return

        # Choose candidates in top portion (y < 0.3) if available, else top half
        top_candidates = [c for c in header_candidates if c[0] < 0.30]
        if not top_candidates:
            top_candidates = [c for c in header_candidates if c[0] < 0.50]

        # Parse times and sort left-to-right
        parsed = []
        for y, x, txt in top_candidates:
            ts = self.parse_timeslot(txt)
            if ts:
                parsed.append((x, ts))

        if not parsed:
            return

        parsed.sort(key=lambda p: p[0])
        header_slots = [p[1] for p in parsed]

        # For each weekday, assign missing times in order using header_slots
        from collections import defaultdict
        by_day = defaultdict(list)
        for entry in doc.entries:
            by_day[entry.weekday].append(entry)

        for day, entries in by_day.items():
            # Build an index over header slots
            idx = 0
            for entry in entries:
                # Skip entries that look like metadata or are very short
                text_l = (entry.activity or '').lower()
                if any(k in text_l for k in ('class:', 'teacher', 'term', 'school', 'file')):
                    continue
                if len(text_l.strip()) < 3:
                    continue

                if entry.timeslot is None:
                    if header_slots:
                        entry.timeslot = header_slots[idx % len(header_slots)]
                        idx += 1
        # Further post-processing: ensure end_time exists and merge overlapping
        # activities per weekday. This is best-effort: we use other entries' start
        # times, header_slots and a +60 minute fallback when necessary.
        from datetime import datetime, timedelta

        def _time_to_minutes(t: time) -> int:
            return t.hour * 60 + t.minute

        def _minutes_to_time(m: int) -> time:
            h = (m // 60) % 24
            mm = m % 60
            return time(h, mm)

        # Normalize times from raw_text where possible
        for day, entries in list(by_day.items()):
            # try to ensure start_time exists where raw_text contains a parsable time
            for e in entries:
                ts = e.timeslot
                if ts and (not ts.start_time) and getattr(ts, 'raw_text', None):
                    parsed = self.parse_timeslot(ts.raw_text)
                    if parsed and parsed.start_time:
                        # copy parsed into existing timeslot preserving raw_text
                        e.timeslot.start_time = parsed.start_time
                        if parsed.end_time:
                            e.timeslot.end_time = parsed.end_time

            # Build sorted list of entries that have a start_time
            with_start = [e for e in entries if e.timeslot and e.timeslot.start_time]
            # sort by start_time minutes
            with_start.sort(key=lambda x: _time_to_minutes(x.timeslot.start_time))

            # assign missing end_time using next entry start, header_slots or +60min
            for i, e in enumerate(with_start):
                ts = e.timeslot
                if not ts.end_time and ts.start_time:
                    # try next entry
                    end_assigned = False
                    for j in range(i+1, len(with_start)):
                        other = with_start[j]
                        if other.timeslot and other.timeslot.start_time:
                            e.timeslot.end_time = other.timeslot.start_time
                            end_assigned = True
                            break

                    if not end_assigned and header_slots:
                        # try to match against header slots
                        for hs_i, hs in enumerate(header_slots):
                            if hs and hs.start_time and _time_to_minutes(hs.start_time) == _time_to_minutes(ts.start_time):
                                # use next header start if exists
                                if hs_i + 1 < len(header_slots) and header_slots[hs_i + 1].start_time:
                                    e.timeslot.end_time = header_slots[hs_i + 1].start_time
                                    end_assigned = True
                                break

                    if not end_assigned:
                        # fallback +60 minutes
                        st_min = _time_to_minutes(ts.start_time)
                        e.timeslot.end_time = _minutes_to_time(st_min + 60)

            # after ensuring end_times, merge overlapping entries for the day
            merged: List[TimetableEntry] = []
            for e in sorted(with_start, key=lambda x: _time_to_minutes(x.timeslot.start_time)):
                if not merged:
                    merged.append(e)
                    continue
                cur = merged[-1]
                # if either has None end_time we conservatively skip merging
                if not cur.timeslot or not cur.timeslot.end_time or not e.timeslot or not e.timeslot.start_time:
                    merged.append(e)
                    continue

                cur_end = _time_to_minutes(cur.timeslot.end_time)
                e_start = _time_to_minutes(e.timeslot.start_time)
                e_end = _time_to_minutes(e.timeslot.end_time) if e.timeslot.end_time else e_start + 60

                if e_start <= cur_end:
                    # overlap -> merge
                    new_start_min = min(_time_to_minutes(cur.timeslot.start_time), e_start)
                    new_end_min = max(cur_end, e_end)
                    # combine activity texts if different
                    if cur.activity and e.activity and cur.activity.strip().lower() != e.activity.strip().lower():
                        combined_activity = f"{cur.activity} / {e.activity}"
                    else:
                        combined_activity = cur.activity or e.activity

                    cur.timeslot.start_time = _minutes_to_time(new_start_min)
                    cur.timeslot.end_time = _minutes_to_time(new_end_min)
                    cur.activity = combined_activity
                    cur.confidence_score = max(cur.confidence_score, e.confidence_score)
                else:
                    merged.append(e)

            # replace day's entries in doc with merged ones + any entries without start_time
            no_start = [e for e in entries if not (e.timeslot and e.timeslot.start_time)]
            final_list = merged + no_start
            # update doc.entries: remove old ones for this weekday and add final_list
            # We'll rebuild doc.entries after finishing all days
            by_day[day] = final_list

        # Rebuild doc.entries preserving order by weekday and within-day order
        new_entries: List[TimetableEntry] = []
        # Try to preserve Monday..Sunday order if Weekday enum supports ordering via name
        weekday_order = list(Weekday)
        for wd in weekday_order:
            if wd in by_day:
                new_entries.extend(by_day[wd])
        # append any days not represented in Weekday enum iteration
        for day, lst in by_day.items():
            if day not in weekday_order:
                new_entries.extend(lst)

        doc.entries = new_entries

    def _normalize_and_fill_defaults(self, doc: TimetableDocument) -> None:
        """Best-effort normalization and minimal default block insertion.

        Goals (lightweight, not over-engineered):
        - Normalize activity strings (fix OCR artifacts, unify naming)
        - If a day is present, ensure these standard blocks exist once with
          canonical times when missing:
            * Registration and Early Morning work 08:35–08:50
            * Break 10:20–10:35
            * Lunch 12:00–13:00
            * Storytime 15:00–15:15
        """
        if not doc.entries:
            return

        from collections import defaultdict
        from datetime import time as dtime

        # 1) Normalize activity text
        for e in doc.entries:
            if e.activity:
                e.activity = normalize_activity_name(str(e.activity))
                # If activity string contains multiple items separated by '/',
                # prefer the leading activity as the primary label while keeping
                # the rest in notes when notes are empty.
                if ' / ' in e.activity and not e.notes:
                    parts = [p.strip() for p in e.activity.split(' / ') if p.strip()]
                    if parts:
                        e.notes = ' / '.join(parts[1:]) if len(parts) > 1 else None
                        e.activity = parts[0]

        # 2) Build per-day index and detect which days appear
        by_day = defaultdict(list)
        present_days = set()
        for e in doc.entries:
            if e.weekday:
                present_days.add(e.weekday)
                by_day[e.weekday].append(e)

        if not present_days:
            return

        def _minutes(t: dtime) -> int:
            return t.hour * 60 + t.minute

        def _overlaps(a_start: dtime, a_end: dtime, b_start: dtime, b_end: dtime) -> bool:
            return _minutes(a_start) < _minutes(b_end) and _minutes(b_start) < _minutes(a_end)

        # Canonical default blocks
        defaults = [
            ("Registration and Early Morning work", dtime(8, 35), dtime(8, 50)),
            ("Break", dtime(10, 20), dtime(10, 35)),
            ("Lunch", dtime(12, 0), dtime(13, 0)),
            ("Storytime", dtime(15, 0), dtime(15, 15)),
        ]

        # Helper to check if block exists for a given day
        def _has_block(day_entries: list[TimetableEntry], label: str, st: dtime, et: dtime) -> bool:
            for e in day_entries:
                if not e.timeslot or not e.timeslot.start_time or not e.timeslot.end_time:
                    # try to match by name only if times missing; consider it present
                    if e.activity and label.lower() in e.activity.lower():
                        return True
                    continue
                if e.activity and label.lower() in e.activity.lower():
                    if _overlaps(e.timeslot.start_time, e.timeslot.end_time, st, et):
                        return True
            return False

        # 3) Insert missing default blocks for days that appear
        new_entries: list[TimetableEntry] = []
        for day in present_days:
            day_entries = by_day.get(day, [])
            for label, st, et in defaults:
                if not _has_block(day_entries, label, st, et):
                    new_entries.append(
                        TimetableEntry(
                            weekday=day,
                            timeslot=TimeSlot(start_time=st, end_time=et, raw_text=f"{label}"),
                            activity=label,
                            confidence_score=0.7,
                        )
                    )

        # 4) Add the new defaults and sort entries within each day by start time where possible
        doc.entries.extend(new_entries)

        # Sort to improve readability/output order
        def _sort_key(e: TimetableEntry):
            if e.weekday and e.timeslot and e.timeslot.start_time:
                return (list(Weekday).index(e.weekday), _minutes(e.timeslot.start_time))
            if e.weekday:
                return (list(Weekday).index(e.weekday), 10_000)
            return (10_000, 10_000)

        doc.entries.sort(key=_sort_key)
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

    def _parse_ocr_with_inferred_columns(self, ocr_data: List[Dict[str, any]]) -> List[TimetableEntry]:
        """
        Attempt to infer column time slots from header time tokens (top of page)
        and map OCR items into those columns. This helps handle tables where
        img2table failed (no ximgproc available) and where cells span multiple
        time slots.
        """
        entries: List[TimetableEntry] = []

        if not ocr_data:
            return entries

        # Infer image width from OCR bbox coordinates if available
        img_w = self._compute_image_width(ocr_data)

        # Find header time tokens near top of page
        header_slots = self._infer_header_slots_from_ocr(ocr_data, img_w)
        if not header_slots or len(header_slots) < 2:
            # not enough header info to form columns
            return entries

        # Build column boundaries (x ranges) from header center positions
        centers = [s['x'] for s in header_slots]
        centers_px = [s['x_px'] for s in header_slots]
        centers_sorted = sorted(list(zip(centers_px, header_slots)), key=lambda x: x[0])
        centers_px_sorted = [c for c, s in centers_sorted]
        slots_sorted = [s for c, s in centers_sorted]

        # boundaries are midpoints between consecutive centers
        boundaries = []
        for i in range(len(centers_px_sorted) - 1):
            mid = (centers_px_sorted[i] + centers_px_sorted[i+1]) / 2.0
            boundaries.append(mid)

        # Build column ranges as (left, right) in pixels
        col_ranges: List[Tuple[float, float]] = []
        left = 0.0
        for b in boundaries:
            col_ranges.append((left, b))
            left = b
        # last column to image width
        col_ranges.append((left, img_w))

        # Group OCR items by detected weekday (rows)
        rows = self._group_by_rows(ocr_data)

        current_day: Optional[Weekday] = None

        for row in rows:
            # detect if this row contains a weekday
            weekday = None
            for item in row:
                wd = Weekday.from_string(item.get('text', ''))
                if wd:
                    weekday = wd
                    current_day = wd
                    break

            if not weekday:
                weekday = current_day

            if not weekday:
                # cannot assign entries without weekday context
                continue

            # For each text item in row, decide if it's a time token, metadata or activity
            for item in row:
                txt = item.get('text', '').strip()
                if not txt:
                    continue

                # skip header-like metadata rows
                if any(k in txt.lower() for k in ('class:', 'teacher', 'term', 'school')):
                    continue

                # if the cell explicitly contains a time range, prefer that
                explicit_ts = self.parse_timeslot(txt, reference_times=[s['slot'] for s in slots_sorted])
                if explicit_ts and not self._is_activity(txt):
                    # if it is a pure time cell, we don't create an activity
                    continue

                # Determine which columns this item's bbox spans
                bbox = item.get('bbox')
                if bbox and len(bbox) >= 4:
                    xs = [p[0] for p in bbox]
                    min_x = min(xs)
                    max_x = max(xs)
                else:
                    # fallback to center pixel
                    cx = item.get('center', (0, 0))[0]
                    min_x = cx - 1
                    max_x = cx + 1

                overlapping_cols = []
                for ci, (l, r) in enumerate(col_ranges):
                    # consider overlap if bbox intersects column range
                    if max_x >= l and min_x <= r:
                        overlapping_cols.append(ci)

                if not overlapping_cols:
                    # couldn't map to any column; skip
                    continue

                # compute timeslot for this item:
                final_ts = None
                if explicit_ts:
                    final_ts = explicit_ts
                else:
                    first_col = overlapping_cols[0]
                    last_col = overlapping_cols[-1]
                    # start from header slot start
                    start_slot = slots_sorted[first_col]['slot']
                    # end time: if the last_col has a next header, use its start as end
                    if last_col + 1 < len(slots_sorted):
                        end_slot = slots_sorted[last_col + 1]['slot']
                        # if that slot has a start_time, use it as end
                        if end_slot and end_slot.start_time:
                            final_ts = TimeSlot(start_time=start_slot.start_time, end_time=end_slot.start_time, raw_text=txt)
                        else:
                            # fallback: if header slots have end_time, use last's end_time or estimate 60 minutes
                            if slots_sorted[last_col]['slot'] and slots_sorted[last_col]['slot'].end_time:
                                final_ts = TimeSlot(start_time=start_slot.start_time, end_time=slots_sorted[last_col]['slot'].end_time, raw_text=txt)
                            else:
                                # estimate one hour slot
                                sh = start_slot.start_time.hour
                                sm = start_slot.start_time.minute
                                est_end = (sh + 1) % 24
                                final_ts = TimeSlot(start_time=start_slot.start_time, end_time=time(est_end, sm), raw_text=txt)
                    else:
                        # last column — try to use its own end_time or estimate
                        last_header = slots_sorted[last_col]['slot']
                        if last_header and last_header.end_time:
                            final_ts = TimeSlot(start_time=start_slot.start_time, end_time=last_header.end_time, raw_text=txt)
                        else:
                            sh = start_slot.start_time.hour
                            sm = start_slot.start_time.minute
                            est_end = (sh + 1) % 24
                            final_ts = TimeSlot(start_time=start_slot.start_time, end_time=time(est_end, sm), raw_text=txt)

                # If still no timeslot, fallback to parse one from text
                if not explicit_ts and not final_ts:
                    final_ts = self.parse_timeslot(txt, reference_times=[s['slot'] for s in slots_sorted])

                # Normalize timeslot: ensure end_time > start_time, else estimate +1 hour
                if final_ts and final_ts.start_time and final_ts.end_time:
                    sh_m = final_ts.start_time.hour * 60 + final_ts.start_time.minute
                    eh_m = final_ts.end_time.hour * 60 + final_ts.end_time.minute
                    if eh_m <= sh_m:
                        # assume spanning next slot — set end = start + 60 minutes
                        new_end_hour = (final_ts.start_time.hour + 1) % 24
                        final_ts.end_time = time(new_end_hour, final_ts.start_time.minute)

                # If text appears to be an activity, create entry
                if self._is_activity(txt):
                    avg_confidence = item.get('confidence', 0.8)
                    entry = TimetableEntry(
                        weekday=weekday,
                        timeslot=final_ts,
                        activity=txt,
                        confidence_score=avg_confidence
                    )
                    entries.append(entry)

        return entries

    def _infer_header_slots_from_ocr(self, ocr_data: List[Dict[str, any]], img_w: float) -> List[Dict[str, any]]:
        """
        Find header time tokens near the top of the page and return a list of
        dicts: { 'x': normalized_x, 'x_px': center_x_pixels, 'slot': TimeSlot }
        """
        candidates = []
        for item in ocr_data:
            txt = item.get('text', '')
            if not txt or not isinstance(txt, str):
                continue
            # location near the top
            y = item.get('position', (0.5, 0.5))[1]
            if y > 0.35:
                continue
            if self._contains_time(txt):
                ts = self.parse_timeslot(txt)
                if ts:
                    candidates.append((item.get('center', (0, 0))[0], item.get('position', (0, 0))[0], ts))

        if not candidates:
            return []

        # candidates: (center_px, norm_x, slot)
        # sort by center_px
        candidates.sort(key=lambda x: x[0])

        header_slots = []
        seen = set()
        for center_px, norm_x, slot in candidates:
            key = (int(center_px), getattr(slot, 'raw_text', ''))
            if key in seen:
                continue
            seen.add(key)
            header_slots.append({'x': norm_x, 'x_px': center_px, 'slot': slot})

        return header_slots

    def _compute_image_width(self, ocr_data: List[Dict[str, any]]) -> float:
        """Estimate image width from OCR bbox coordinates (pixels)."""
        max_x = 0.0
        for it in ocr_data:
            bbox = it.get('bbox')
            if bbox and isinstance(bbox, list):
                try:
                    xs = [p[0] for p in bbox]
                    max_x = max(max_x, max(xs))
                except Exception:
                    continue
            else:
                cx = it.get('center', (0, 0))[0]
                if cx:
                    max_x = max(max_x, cx)

        return max_x if max_x > 0 else 1.0
    
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
        header_times: List[TimeSlot] = []
        if content and content[0]:
            for i, cell in enumerate(content[0]):
                if i > day_col:  # Skip day column
                    timeslot = self.parse_timeslot(cell)
                    time_slots.append((i, timeslot))
                    if timeslot:
                        header_times.append(timeslot)
        
        # Parse each row (each row is a day)
        for row in content[1:]:
            if not row or len(row) <= day_col:
                continue
            
            # Extract weekday
            day_text = row[day_col].strip()
            weekday = Weekday.from_string(day_text)
            
            if not weekday:
                continue
            
            # Extract activities for each time slot. If adjacent columns contain
            # the same activity text, treat as a span (colspan) and create a
            # single entry with an end_time that covers the spanned columns.
            ci = 0
            while ci < len(time_slots):
                col_idx, timeslot = time_slots[ci]
                if col_idx >= len(row):
                    ci += 1
                    continue

                activity_text = row[col_idx].strip()
                if not activity_text or activity_text.lower() in ['', 'nan', 'none']:
                    ci += 1
                    continue

                # If the cell explicitly contains a time range, prefer that
                explicit_ts = self.parse_timeslot(activity_text, reference_times=header_times)

                # Check for identical consecutive cells to detect colspan
                span_last_col = col_idx
                span_count = 1
                for look in range(ci + 1, len(time_slots)):
                    next_col_idx, _ = time_slots[look]
                    if next_col_idx < len(row):
                        next_text = row[next_col_idx].strip()
                        # consider equal if normalized texts match
                        if next_text and next_text.lower().strip() == activity_text.lower().strip():
                            span_last_col = next_col_idx
                            span_count += 1
                            continue
                    break

                # Build final timeslot: explicit > spanned header range > single header
                final_ts = explicit_ts
                if not final_ts:
                    start_slot = timeslot
                    # end time: if there is a header after the last spanned column, use its start
                    # otherwise use the end_time of the last header or estimate +1 hour
                    try:
                        last_index = None
                        # find index of span_last_col in time_slots to get following header
                        for idx_map, (tci, _) in enumerate(time_slots):
                            if tci == span_last_col:
                                last_index = idx_map
                                break

                        if last_index is not None and (last_index + 1) < len(time_slots):
                            next_header_ts = time_slots[last_index + 1][1]
                            if next_header_ts and next_header_ts.start_time:
                                final_ts = TimeSlot(start_time=start_slot.start_time, end_time=next_header_ts.start_time, raw_text=activity_text)
                            else:
                                # fall back to last header's end_time
                                last_header = time_slots[last_index][1]
                                if last_header and last_header.end_time:
                                    final_ts = TimeSlot(start_time=start_slot.start_time, end_time=last_header.end_time, raw_text=activity_text)
                                else:
                                    # estimate +1 hour
                                    est_end = (start_slot.start_time.hour + 1) % 24
                                    final_ts = TimeSlot(start_time=start_slot.start_time, end_time=time(est_end, start_slot.start_time.minute), raw_text=activity_text)
                        else:
                            # no following header; use last header end_time or estimate
                            last_header = timeslot
                            if last_header and last_header.end_time:
                                final_ts = TimeSlot(start_time=start_slot.start_time, end_time=last_header.end_time, raw_text=activity_text)
                            else:
                                est_end = (start_slot.start_time.hour + 1) % 24
                                final_ts = TimeSlot(start_time=start_slot.start_time, end_time=time(est_end, start_slot.start_time.minute), raw_text=activity_text)
                    except Exception:
                        # fallback to the original timeslot
                        final_ts = timeslot

                entry = TimetableEntry(
                    weekday=weekday,
                    timeslot=final_ts,
                    activity=activity_text,
                    confidence_score=0.85  # Table-based extraction is typically reliable
                )
                entries.append(entry)

                # advance by span_count
                ci += span_count
        
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
        # Build a list of reference times from the first column if possible
        reference_times: List[TimeSlot] = []
        for r in range(1, len(content)):
            if content[r] and len(content[r]) > 0:
                ts = self.parse_timeslot(content[r][0])
                if ts:
                    reference_times.append(ts)

        for row_idx in range(1, len(content)):
            row = content[row_idx]

            # Try to extract time from first column
            timeslot = None
            if row:
                timeslot = self.parse_timeslot(row[0], reference_times=reference_times)

            # Extract activities for each day
            for col_idx, weekday in weekdays:
                if col_idx < len(row):
                    activity_text = row[col_idx].strip()

                    if not activity_text or activity_text.lower() in ['', 'nan', 'none']:
                        continue

                    explicit_ts = self.parse_timeslot(activity_text, reference_times=reference_times)
                    final_ts = explicit_ts or timeslot

                    entry = TimetableEntry(
                        weekday=weekday,
                        timeslot=final_ts,
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
    
    def parse_timeslot(self, text: str, reference_times: Optional[List[TimeSlot]] = None) -> Optional[TimeSlot]:
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
        
        # Pre-normalize text to reduce OCR noise and support a wider range of separators
        # - normalize various dash characters to '-' so ranges are caught
        # - convert dots between hour/min to ':' (OCR commonly uses '.' for ':')
        # - collapse multiple spaces
        norm = text.replace('\u2013', '-').replace('\u2014', '-').replace('\u2012', '-')
        norm = re.sub(r'[–—−]', '-', norm)
        # replace lone dot used as separator (e.g., '9.30') with ':' but avoid replacing decimal dots in numbers
        norm = re.sub(r'(?<=\d)\.(?=\d{2}\b)', ':', norm)
        # common OCR mistakes: letter O for zero in minute positions
        # Python's `re` requires fixed-width lookbehind. The original
        # pattern used a variable-width lookbehind `(?<=:\s?)` which fails
        # for some Python versions. Replace using a captured prefix and a
        # lambda replacement to avoid lookbehind altogether.
        norm = re.sub(r'(:\s?)[Oo](?=\b)', lambda m: m.group(1) + '0', norm, flags=re.IGNORECASE)
        norm = re.sub(r'\s+', ' ', norm).strip()

        # First attempt: look for explicit ranges like '1:15 - 2:15', '9.30 to 10:15', '1 - 2pm'
        range_re = re.compile(r"(\d{1,2}(?::|\.)?\d{0,2})\s*(?:-|–|—|to)\s*(\d{1,2}(?::|\.)?\d{0,2})(?:\s*(am|pm|AM|PM))?")
        mrange = range_re.search(norm)
        if mrange:
            left = mrange.group(1)
            right = mrange.group(2)
            trailing_ampm = mrange.group(3)

            # normalize separators to ':' for consistent parsing
            left = left.replace('.', ':')
            right = right.replace('.', ':')

            def _split_time_token(tok: str):
                if ':' in tok:
                    h, mm = tok.split(':', 1)
                    mm = mm[:2] if mm else '00'
                else:
                    h = tok
                    mm = '00'
                return int(re.sub(r'\D', '', h)), int(re.sub(r'\D', '', mm))

            try:
                lh, lm = _split_time_token(left)
                rh, rm = _split_time_token(right)

                # prepare am/pm propagation
                left_ampm = None
                right_ampm = trailing_ampm
                # If explicit AM/PM present inside tokens (rare), try to extract
                inner_left = re.search(r'(am|pm|AM|PM)$', left)
                inner_right = re.search(r'(am|pm|AM|PM)$', right)
                if inner_left:
                    left_ampm = inner_left.group(1)
                if inner_right:
                    right_ampm = inner_right.group(1)

                # propagate if only one side has am/pm
                if left_ampm and not right_ampm:
                    right_ampm = left_ampm
                if right_ampm and not left_ampm:
                    left_ampm = right_ampm

                def _map_hour_local(h: int, ampm: Optional[str]) -> int:
                    if ampm:
                        return _map_hour(h, ampm)
                    return h

                sh = _map_hour_local(lh, left_ampm)
                eh = _map_hour_local(rh, right_ampm)

                # If still ambiguous (no am/pm), and reference_times exist, choose mapping (h or h+12)
                if not left_ampm and reference_times:
                    # pick mapping (h or h+12) that minimizes minute difference to any ref start
                    def _best_map(h0):
                        cand1 = h0 % 24
                        cand2 = (h0 + 12) % 24
                        best_cand = cand1
                        best_diff = None
                        for ref in reference_times:
                            if not ref or not ref.start_time:
                                continue
                            for cand in (cand1, cand2):
                                diff = abs((cand * 60 + lm) - (ref.start_time.hour * 60 + ref.start_time.minute))
                                if best_diff is None or diff < best_diff:
                                    best_diff = diff
                                    best_cand = cand
                        return best_cand

                    sh = _best_map(lh)

                if not right_ampm and reference_times:
                    def _best_map_r(h0):
                        cand1 = h0 % 24
                        cand2 = (h0 + 12) % 24
                        best_cand = cand1
                        best_diff = None
                        for ref in reference_times:
                            if not ref or not ref.start_time:
                                continue
                            for cand in (cand1, cand2):
                                diff = abs((cand * 60 + rm) - (ref.start_time.hour * 60 + ref.start_time.minute))
                                if best_diff is None or diff < best_diff:
                                    best_diff = diff
                                    best_cand = cand
                        return best_cand
                    eh = _best_map_r(rh)

                start_time = time(int(sh), int(lm))
                end_time = time(int(eh), int(rm))
                # ensure end > start, otherwise if end <= start assume +1 hour
                if (end_time.hour * 60 + end_time.minute) <= (start_time.hour * 60 + start_time.minute):
                    end_time = time((start_time.hour + 1) % 24, start_time.minute)

                return TimeSlot(start_time=start_time, end_time=end_time, raw_text=text.strip())
            except Exception:
                # fall through to token-based parsing
                pass

        # Find all time-like tokens in the (normalized) text
        matches = list(self._time_re.finditer(norm))

        def _map_hour(h: int, ampm: Optional[str]) -> int:
            # Map 12-hour hour and am/pm to 24-hour
            if ampm:
                am = ampm.lower() == 'am'
                pm = ampm.lower() == 'pm'
                if am and h == 12:
                    return 0
                if pm and h < 12:
                    return h + 12
                return h % 24
            # No am/pm provided — we'll infer later
            return h

        times = []
        for m in matches:
            h = int(m.group(1))
            mm = int(m.group(2)) if m.group(2) else 0
            ampm = m.group(3)
            times.append({'hour': h, 'minute': mm, 'ampm': ampm})

        if len(times) >= 2:
            # Treat first two as a range
            s = times[0]
            e = times[1]

            # If either has am/pm, propagate to the other if missing
            if s['ampm'] and not e['ampm']:
                e['ampm'] = s['ampm']
            if e['ampm'] and not s['ampm']:
                s['ampm'] = e['ampm']

            # If still missing am/pm and reference times provided, try to infer
            def _resolve(t, refs):
                if t['ampm']:
                    return _map_hour(t['hour'], t['ampm']), t['minute']
                # Try to infer using reference_times (compare nearest minute)
                if refs:
                    best_choice = None
                    best_diff = None
                    for add12 in (0, 12):
                        cand = (t['hour'] % 12) + add12
                        cand_minutes = cand * 60 + t['minute']
                        for ref in refs:
                            if ref and ref.start_time:
                                ref_minutes = ref.start_time.hour * 60 + ref.start_time.minute
                                diff = abs(cand_minutes - ref_minutes)
                                if best_diff is None or diff < best_diff:
                                    best_diff = diff
                                    best_choice = (cand, t['minute'])
                    if best_choice:
                        return best_choice
                # Fallback heuristic: morning hours 7-11 -> AM, else PM (12->12)
                if 7 <= t['hour'] <= 11:
                    return t['hour'] % 24, t['minute']
                if t['hour'] == 12:
                    return 12, t['minute']
                return (t['hour'] + 12) % 24, t['minute']

            try:
                sh, sm = _resolve(s, reference_times)
                eh, em = _resolve(e, reference_times)
                start_time = time(int(sh), int(sm))
                end_time = time(int(eh), int(em))
                return TimeSlot(start_time=start_time, end_time=end_time, raw_text=text.strip())
            except Exception:
                pass

        if len(times) == 1:
            t = times[0]
            # resolve hour
            if t['ampm']:
                h24 = _map_hour(t['hour'], t['ampm'])
            else:
                # infer from reference_times or heuristics
                if reference_times:
                    # pick closest reference hour
                    best = None
                    best_diff = None
                    for ref in reference_times:
                        if ref and ref.start_time:
                            diff = abs(t['hour'] - (ref.start_time.hour % 12))
                            if best_diff is None or diff < best_diff:
                                best_diff = diff
                                best = ref.start_time.hour
                    if best is not None:
                        # choose mapping closest to best (either h or h+12)
                        if abs(t['hour'] - (best % 12)) <= abs((t['hour'] + 12) - best):
                            h24 = t['hour'] % 24
                        else:
                            h24 = (t['hour'] + 12) % 24
                    else:
                        # fallback heuristic
                        if 7 <= t['hour'] <= 11:
                            h24 = t['hour'] % 24
                        elif t['hour'] == 12:
                            h24 = 12
                        else:
                            h24 = (t['hour'] + 12) % 24
                else:
                    if 7 <= t['hour'] <= 11:
                        h24 = t['hour'] % 24
                    elif t['hour'] == 12:
                        h24 = 12
                    else:
                        h24 = (t['hour'] + 12) % 24

            try:
                start_time = time(int(h24), int(t['minute']))
                return TimeSlot(start_time=start_time, raw_text=text.strip())
            except Exception:
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
        return bool(self._time_re.search(text) or 'am' in text.lower() or 'pm' in text.lower())
    
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
