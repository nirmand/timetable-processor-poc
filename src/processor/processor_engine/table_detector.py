"""Table detection and extraction using img2table."""

from typing import List, Dict, Optional, Tuple
import numpy as np
from PIL import Image
from img2table.document import Image as Img2TableImage
from img2table.ocr import PaddleOCR as Img2TableOCR


class TableDetector:
    """Detects and extracts tables from images using img2table."""
    
    def __init__(self, use_gpu: bool = False):
        """
        Initialize table detector.
        
        Args:
            use_gpu: Whether to use GPU acceleration (note: gpu support requires paddlepaddle-gpu)
        """
        # img2table's PaddleOCR wrapper - pass use_gpu if supported
        try:
            self.ocr = Img2TableOCR(lang='en', use_gpu=use_gpu)
        except TypeError:
            # Fallback if use_gpu is not supported in this version
            self.ocr = Img2TableOCR(lang='en')
    
    def detect_tables(self, image: np.ndarray) -> List[Dict[str, any]]:
        """
        Detect and extract tables from image.
        
        Args:
            image: Input image as numpy array
        
        Returns:
            List of dictionaries containing:
                - bbox: Table bounding box (x1, y1, x2, y2)
                - content: Extracted table content as list of rows
                - title: Table title if detected
        """
        try:
            # Convert numpy array to PIL Image for img2table
            # img2table expects PIL Image, not numpy array
            if isinstance(image, np.ndarray):
                # Handle BGR (OpenCV) to RGB (PIL) conversion if needed
                if len(image.shape) == 3 and image.shape[2] == 3:
                    # Assume BGR from OpenCV, convert to RGB
                    from cv2 import cvtColor, COLOR_BGR2RGB
                    image_rgb = cvtColor(image, COLOR_BGR2RGB)
                    pil_image = Image.fromarray(image_rgb)
                else:
                    pil_image = Image.fromarray(image)
            else:
                pil_image = image
            
            # Create img2table Image object
            doc = Img2TableImage(pil_image)
            
            # Extract tables
            tables = doc.extract_tables(
                ocr=self.ocr,
                implicit_rows=True,  # Detect implicit row separators
                borderless_tables=True,  # Detect tables without borders
                min_confidence=50  # Minimum confidence for table detection
            )
            
            if not tables:
                return []
            
            # Parse table results
            extracted_tables = []
            for table in tables:
                table_data = {
                    'bbox': table.bbox.to_dict() if hasattr(table, 'bbox') else None,
                    'content': self._extract_table_content(table),
                    'title': table.title if hasattr(table, 'title') else None,
                }
                extracted_tables.append(table_data)
            
            return extracted_tables
        
        except Exception as e:
            print(f"Error during table detection: {e}")
            return []
    
    def _extract_table_content(self, table) -> List[List[str]]:
        """
        Extract content from detected table.
        
        Args:
            table: img2table Table object
        
        Returns:
            2D list representing table rows and columns
        """
        try:
            # Get table dataframe
            df = table.df
            
            if df is None or df.empty:
                return []
            
            # Convert to list of lists
            # Include headers
            content = [df.columns.tolist()]
            content.extend(df.values.tolist())
            
            # Clean up None values and convert to strings
            cleaned_content = []
            for row in content:
                cleaned_row = [str(cell).strip() if cell is not None else '' for cell in row]
                cleaned_content.append(cleaned_row)
            
            return cleaned_content
        
        except Exception as e:
            print(f"Error extracting table content: {e}")
            return []
    
    def detect_table_structure(
        self, 
        image: np.ndarray
    ) -> Optional[Dict[str, any]]:
        """
        Analyze table structure (rows, columns, cells).
        
        Args:
            image: Input image
        
        Returns:
            Dictionary with table structure information:
                - num_rows: Number of rows
                - num_cols: Number of columns
                - cells: List of cell information
        """
        try:
            doc = Img2TableImage(image)
            tables = doc.extract_tables(
                ocr=self.ocr,
                implicit_rows=True,
                borderless_tables=True
            )
            
            if not tables:
                return None
            
            # Analyze first table (primary timetable)
            table = tables[0]
            df = table.df
            
            if df is None or df.empty:
                return None
            
            structure = {
                'num_rows': len(df),
                'num_cols': len(df.columns),
                'headers': df.columns.tolist(),
                'has_index': df.index.name is not None,
            }
            
            return structure
        
        except Exception as e:
            print(f"Error analyzing table structure: {e}")
            return None
    
    @staticmethod
    def is_timetable_like(table_content: List[List[str]]) -> bool:
        """
        Check if extracted table looks like a timetable.
        
        Args:
            table_content: 2D list of table content
        
        Returns:
            True if table appears to be a timetable
        """
        if not table_content or len(table_content) < 2:
            return False
        
        # Check for day names in first column or first row
        day_keywords = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 
                       'mon', 'tue', 'wed', 'thu', 'fri', 'm', 'tu', 'w', 'th', 'f']
        
        # Check first column
        first_col = [row[0].lower() for row in table_content if row]
        if any(any(day in cell for day in day_keywords) for cell in first_col):
            return True
        
        # Check first row
        if table_content[0]:
            first_row = [cell.lower() for cell in table_content[0]]
            if any(any(day in cell for day in day_keywords) for cell in first_row):
                return True
        
        # Check for time patterns
        time_keywords = ['am', 'pm', ':', '-']
        content_str = ' '.join([' '.join(row) for row in table_content]).lower()
        time_indicators = sum(1 for kw in time_keywords if kw in content_str)
        
        # If multiple time indicators present, likely a timetable
        if time_indicators >= 3:
            return True
        
        return False
    
    def extract_cells_by_position(
        self, 
        table_content: List[List[str]], 
        row_indices: List[int], 
        col_indices: List[int]
    ) -> List[str]:
        """
        Extract specific cells from table.
        
        Args:
            table_content: 2D list of table content
            row_indices: Row indices to extract
            col_indices: Column indices to extract
        
        Returns:
            List of cell values
        """
        cells = []
        
        for row_idx in row_indices:
            if row_idx < len(table_content):
                row = table_content[row_idx]
                for col_idx in col_indices:
                    if col_idx < len(row):
                        cells.append(row[col_idx])
        
        return cells
