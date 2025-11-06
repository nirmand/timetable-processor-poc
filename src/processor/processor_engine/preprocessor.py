"""Document preprocessing for various file formats."""

import io
import tempfile
from pathlib import Path
from typing import List, Union
import numpy as np
from PIL import Image
import cv2


class DocumentPreprocessor:
    """Handles conversion and preprocessing of various document formats."""
    
    def __init__(self):
        """Initialize the document preprocessor."""
        self.supported_image_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif'}
        self.supported_doc_formats = {'.pdf', '.docx'}
    
    def process(self, file_path: Union[str, Path]) -> List[np.ndarray]:
        """
        Process document and return list of images as numpy arrays.
        
        Args:
            file_path: Path to the document file
        
        Returns:
            List of images as numpy arrays (one per page/image)
        
        Raises:
            ValueError: If file format is not supported
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        if extension in self.supported_image_formats:
            return self._process_image(file_path)
        elif extension == '.pdf':
            return self._process_pdf(file_path)
        elif extension == '.docx':
            return self._process_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {extension}")
    
    def _process_image(self, file_path: Path) -> List[np.ndarray]:
        """
        Load and preprocess image file.
        
        Args:
            file_path: Path to image file
        
        Returns:
            List containing single preprocessed image
        """
        try:
            # Load image directly with OpenCV (returns BGR format, which PaddleOCR expects)
            img_array = cv2.imread(str(file_path))
            
            if img_array is None:
                raise ValueError(f"Failed to load image: {file_path}")
            
            print(f"  → Loaded image: shape={img_array.shape}, dtype={img_array.dtype}")
            
            # Preprocess image (keeps BGR format for OCR)
            processed = self._preprocess_image(img_array)
            
            print(f"  → Preprocessed: shape={processed.shape}, dtype={processed.dtype}")
            
            return [processed]
        except Exception as e:
            raise ValueError(f"Error processing image {file_path}: {e}")
    
    def _process_pdf(self, file_path: Path) -> List[np.ndarray]:
        """
        Convert PDF to images.
        
        Args:
            file_path: Path to PDF file
        
        Returns:
            List of images (one per page)
        """
        try:
            from pdf2image import convert_from_path
            
            # Convert PDF to images (300 DPI for good OCR quality)
            images = convert_from_path(
                str(file_path),
                dpi=300,
                fmt='RGB'
            )
            
            # Convert PIL images to numpy arrays (BGR format for PaddleOCR) and preprocess
            processed_images = []
            for img in images:
                # Convert PIL Image (RGB) to numpy array then to BGR for OpenCV/PaddleOCR
                img_array = np.array(img)
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                processed = self._preprocess_image(img_bgr)
                processed_images.append(processed)
            
            return processed_images
        except ImportError:
            raise ImportError(
                "pdf2image is required for PDF processing. "
                "Install with: pip install pdf2image"
            )
        except Exception as e:
            raise ValueError(f"Error processing PDF {file_path}: {e}")
    
    def _process_docx(self, file_path: Path) -> List[np.ndarray]:
        """
        Convert DOCX to images.
        
        This is a simplified approach that converts DOCX pages to images.
        For production, consider using docx2pdf + pdf2image or direct rendering.
        
        Args:
            file_path: Path to DOCX file
        
        Returns:
            List of images
        """
        try:
            import docx
            from docx2pdf import convert
            
            # Create temporary PDF file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp_pdf_path = Path(tmp.name)
            
            try:
                # Convert DOCX to PDF
                convert(str(file_path), str(tmp_pdf_path))
                
                # Process the PDF
                images = self._process_pdf(tmp_pdf_path)
                
                return images
            finally:
                # Clean up temporary file
                if tmp_pdf_path.exists():
                    tmp_pdf_path.unlink()
        
        except ImportError:
            raise ImportError(
                "docx2pdf is required for DOCX processing. "
                "Install with: pip install docx2pdf"
            )
        except Exception as e:
            raise ValueError(f"Error processing DOCX {file_path}: {e}")
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Apply preprocessing to improve OCR accuracy.
        
        Args:
            image: Input image as numpy array (BGR format from OpenCV)
        
        Returns:
            Preprocessed image (BGR format)
        """
        # Denoise (works with BGR format)
        denoised = cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
        
        # Enhance contrast using CLAHE on LAB color space
        lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        
        return enhanced
    
    @staticmethod
    def resize_for_ocr(image: np.ndarray, max_dimension: int = 3000) -> np.ndarray:
        """
        Resize image if too large, maintaining aspect ratio.
        
        Args:
            image: Input image
            max_dimension: Maximum width or height
        
        Returns:
            Resized image
        """
        h, w = image.shape[:2]
        
        if max(h, w) > max_dimension:
            scale = max_dimension / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        
        return image
