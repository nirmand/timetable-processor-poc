"""OCR extraction using PaddleOCR."""

from typing import List, Dict, Tuple, Optional
import numpy as np
from paddleocr import PaddleOCR


class OCRExtractor:
    """Handles OCR extraction from images using PaddleOCR."""
    
    def __init__(self, use_gpu: bool = False, lang: str = 'en'):
        """
        Initialize OCR extractor.
        
        Args:
            use_gpu: Whether to use GPU acceleration (note: gpu support requires paddlepaddle-gpu)
            lang: Language code for OCR (default: 'en')
        """
        self.ocr = PaddleOCR(
            use_angle_cls=True,  # Enable angle classification for rotated text
            lang=lang,
            det_db_box_thresh=0.3,  # Lower threshold for better detection of faint text
            det_db_unclip_ratio=2.0,  # Expand detected boxes slightly
        )
    
    def extract_text(self, image: np.ndarray) -> List[Dict[str, any]]:
        """
        Extract text from image using PaddleOCR.
        
        Args:
            image: Input image as numpy array (BGR format from OpenCV)
        
        Returns:
            List of dictionaries containing:
                - text: Extracted text
                - bbox: Bounding box coordinates [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                - confidence: Confidence score (0-1)
                - position: Normalized center position (x, y)
        """
        try:
            # Debug: Check image properties
            if image is None:
                print("    Warning: Received None image")
                return []
            
            if not isinstance(image, np.ndarray):
                print(f"    Warning: Image is not numpy array, got {type(image)}")
                return []
            
            if image.size == 0:
                print("    Warning: Empty image array")
                return []
            
            # Run OCR (expects BGR format from OpenCV)
            result = self.ocr.ocr(image)
            
            if not result or not result[0]:
                print("    Warning: PaddleOCR returned no results")
                return []
            
            # Parse results
            extracted_data = []
            for line in result[0]:
                try:
                    # Validate line structure
                    if not line or len(line) < 2:
                        continue
                    
                    bbox = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                    text_info = line[1]  # (text, confidence)
                    
                    # Validate text_info structure
                    if not text_info or len(text_info) < 2:
                        continue
                    
                    # Safely extract text and confidence
                    text = str(text_info[0]).strip() if text_info[0] else ""
                    
                    # Skip empty text
                    if not text:
                        continue
                    
                    confidence = float(text_info[1])
                    
                    # Validate bbox structure
                    if not bbox or len(bbox) < 4:
                        continue
                    
                    # Calculate center position for spatial analysis
                    center_x = sum(point[0] for point in bbox) / 4
                    center_y = sum(point[1] for point in bbox) / 4
                    
                    # Normalize position (0-1 range)
                    h, w = image.shape[:2]
                    norm_x = center_x / w
                    norm_y = center_y / h
                    
                    extracted_data.append({
                        'text': text,
                        'bbox': bbox,
                        'confidence': confidence,
                        'position': (norm_x, norm_y),
                        'center': (center_x, center_y),
                    })
                    
                except (IndexError, ValueError, TypeError) as line_error:
                    # Skip malformed lines but continue processing others
                    print(f"    Warning: Skipping malformed OCR result: {line_error}")
                    continue
            
            # Sort by vertical position (top to bottom), then horizontal (left to right)
            extracted_data.sort(key=lambda x: (x['center'][1], x['center'][0]))
            
            return extracted_data
        
        except Exception as e:
            print(f"Error during OCR extraction: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def extract_text_by_regions(
        self, 
        image: np.ndarray, 
        regions: List[Tuple[int, int, int, int]]
    ) -> List[str]:
        """
        Extract text from specific regions of the image.
        
        Args:
            image: Input image
            regions: List of regions as (x, y, width, height)
        
        Returns:
            List of extracted text for each region
        """
        results = []
        
        for x, y, w, h in regions:
            # Crop region
            roi = image[y:y+h, x:x+w]
            
            # Extract text from region
            text_data = self.extract_text(roi)
            
            # Concatenate all text in region
            text = ' '.join([item['text'] for item in text_data])
            results.append(text.strip())
        
        return results
    
    def group_text_by_rows(
        self, 
        text_data: List[Dict[str, any]], 
        row_threshold: float = 0.02
    ) -> List[List[Dict[str, any]]]:
        """
        Group text elements into rows based on vertical position.
        
        Args:
            text_data: Extracted text data from extract_text()
            row_threshold: Maximum normalized vertical distance to be in same row
        
        Returns:
            List of rows, each containing text elements
        """
        if not text_data:
            return []
        
        rows = []
        current_row = [text_data[0]]
        current_y = text_data[0]['position'][1]
        
        for item in text_data[1:]:
            y = item['position'][1]
            
            # If within threshold of current row, add to it
            if abs(y - current_y) <= row_threshold:
                current_row.append(item)
            else:
                # Sort current row by x position
                current_row.sort(key=lambda x: x['position'][0])
                rows.append(current_row)
                
                # Start new row
                current_row = [item]
                current_y = y
        
        # Add last row
        if current_row:
            current_row.sort(key=lambda x: x['position'][0])
            rows.append(current_row)
        
        return rows
    
    def get_text_in_row(self, row: List[Dict[str, any]]) -> str:
        """
        Concatenate text from a row.
        
        Args:
            row: List of text elements in a row
        
        Returns:
            Concatenated text
        """
        return ' '.join([item['text'] for item in row])
    
    @staticmethod
    def calculate_confidence_score(text_data: List[Dict[str, any]]) -> float:
        """
        Calculate average confidence score for extracted text.
        
        Args:
            text_data: Extracted text data
        
        Returns:
            Average confidence score (0-1)
        """
        if not text_data:
            return 0.0
        
        total = sum(item['confidence'] for item in text_data)
        return total / len(text_data)
