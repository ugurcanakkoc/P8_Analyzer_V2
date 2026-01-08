"""
P8 Component Label Detector.

Extracts component labels (like -X1, -1G35, -1F45) from PDF text layer
using regex pattern matching. Returns labels with bounding boxes.
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import pymupdf


@dataclass
class DetectedLabel:
    """A detected component label with its location."""
    text: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    font: str = ""
    font_size: float = 0.0
    confidence: float = 1.0

    @property
    def center(self) -> Tuple[float, float]:
        """Get center point of label."""
        return (
            (self.bbox[0] + self.bbox[2]) / 2,
            (self.bbox[1] + self.bbox[3]) / 2
        )

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]

    def to_yolo_format(self, page_width: float, page_height: float) -> str:
        """Convert to YOLO format: class_id x_center y_center width height (normalized)."""
        cx = (self.bbox[0] + self.bbox[2]) / 2 / page_width
        cy = (self.bbox[1] + self.bbox[3]) / 2 / page_height
        w = self.width / page_width
        h = self.height / page_height
        return f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


class LabelDetector:
    """Detects P8 component labels in PDF pages using regex."""

    # P8 label patterns - components typically start with minus sign
    # Examples: -X1, -1G35, -1F45, -1X11, -X4, -PE, -1Q21
    DEFAULT_PATTERNS = [
        r'^-\d*[A-Z]+\d*[A-Z]*\d*$',       # -X1, -1G35, -1F45, -PE
        r'^-\d*[A-Z]+\d*[A-Z]*\d*:\S+$',   # -X1:U, -X4:PE, -13D21:8
    ]

    def __init__(self, patterns: Optional[List[str]] = None):
        """
        Initialize label detector.

        Args:
            patterns: List of regex patterns to match labels.
                     If None, uses DEFAULT_PATTERNS.
        """
        self.patterns = patterns or self.DEFAULT_PATTERNS
        self._compiled_patterns = [re.compile(p) for p in self.patterns]

    def _matches_pattern(self, text: str) -> bool:
        """Check if text matches any label pattern."""
        for pattern in self._compiled_patterns:
            if pattern.match(text):
                return True
        return False

    def detect_labels(self, page: pymupdf.Page) -> List[DetectedLabel]:
        """
        Detect component labels on a PDF page.

        Args:
            page: PyMuPDF page object

        Returns:
            List of DetectedLabel objects
        """
        labels = []

        # Extract text with detailed structure
        text_dict = page.get_text("dict")

        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue  # Skip image blocks

            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue

                    if self._matches_pattern(text):
                        label = DetectedLabel(
                            text=text,
                            bbox=tuple(span["bbox"]),
                            font=span.get("font", ""),
                            font_size=span.get("size", 0.0),
                            confidence=1.0  # Regex match = high confidence
                        )
                        labels.append(label)

        return labels

    def detect_from_pdf(self, pdf_path: str, page_num: int) -> List[DetectedLabel]:
        """
        Detect labels from a specific PDF page.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-indexed)

        Returns:
            List of DetectedLabel objects
        """
        doc = pymupdf.open(pdf_path)
        try:
            page = doc.load_page(page_num - 1)
            return self.detect_labels(page)
        finally:
            doc.close()

    def detect_all_pages(self, pdf_path: str,
                         page_numbers: Optional[List[int]] = None) -> Dict[int, List[DetectedLabel]]:
        """
        Detect labels on multiple pages.

        Args:
            pdf_path: Path to PDF file
            page_numbers: List of page numbers (1-indexed). If None, all pages.

        Returns:
            Dict mapping page number to list of labels
        """
        results = {}
        doc = pymupdf.open(pdf_path)

        try:
            if page_numbers is None:
                page_numbers = list(range(1, doc.page_count + 1))

            for page_num in page_numbers:
                page = doc.load_page(page_num - 1)
                labels = self.detect_labels(page)
                results[page_num] = labels

        finally:
            doc.close()

        return results


def export_labels_to_yolo(labels: List[DetectedLabel],
                          page_width: float,
                          page_height: float,
                          output_path: str):
    """
    Export detected labels to YOLO format label file.

    Args:
        labels: List of DetectedLabel objects
        page_width: Page width in PDF units
        page_height: Page height in PDF units
        output_path: Path to output .txt file
    """
    with open(output_path, 'w') as f:
        for label in labels:
            yolo_line = label.to_yolo_format(page_width, page_height)
            f.write(yolo_line + '\n')


def visualize_labels(page: pymupdf.Page,
                     labels: List[DetectedLabel],
                     output_path: str,
                     scale: float = 2.0):
    """
    Visualize detected labels on a page and save as image.

    Args:
        page: PyMuPDF page object
        labels: List of DetectedLabel objects
        output_path: Path to output PNG file
        scale: Scale factor for output image
    """
    from PIL import Image, ImageDraw, ImageFont

    # Render page
    mat = pymupdf.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    draw = ImageDraw.Draw(img, 'RGBA')

    # Draw labels
    for label in labels:
        x0, y0, x1, y1 = [c * scale for c in label.bbox]

        # Draw rectangle
        draw.rectangle([x0, y0, x1, y1],
                      fill=(255, 200, 0, 100),  # Yellow fill
                      outline=(255, 150, 0),     # Orange outline
                      width=2)

        # Draw text above
        draw.text((x0, y0 - 12), label.text, fill=(255, 100, 0))

    img.save(output_path)
    return output_path
