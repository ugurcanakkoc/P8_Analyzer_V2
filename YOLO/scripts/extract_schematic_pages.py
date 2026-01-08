"""
Schematic Page Extractor & Classifier

This script:
1. Extracts pages from PDFs as images
2. Classifies pages as schematic/non-schematic using heuristics or trained model
3. Outputs filtered schematic pages for annotation

Usage:
    python extract_schematic_pages.py --pdf-dir ../data --output-dir ./extracted_schematics
    python extract_schematic_pages.py --pdf ../data/ornek.pdf --output-dir ./extracted_schematics
"""

import os
import sys
import argparse
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

import pymupdf
from PIL import Image
import numpy as np

# Optional: YOLO for trained classifier
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


@dataclass
class PageClassification:
    """Classification result for a single page."""
    pdf_name: str
    page_num: int
    is_schematic: bool
    confidence: float
    method: str  # 'heuristic' or 'model'
    features: Dict
    output_path: Optional[str] = None


class SchematicClassifier:
    """
    Classifies PDF pages as electrical schematics or not.

    Uses heuristics based on:
    - Vector line density (schematics have many lines)
    - Circle count (terminals are circles)
    - Text-to-drawing ratio
    - Color distribution (schematics are mostly black/white)
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        if model_path and YOLO_AVAILABLE and os.path.exists(model_path):
            try:
                self.model = YOLO(model_path)
                print(f"[INFO] Loaded classification model: {model_path}")
            except Exception as e:
                print(f"[WARNING] Could not load model: {e}")

    def classify_page(self, page: pymupdf.Page, page_image: Image.Image) -> PageClassification:
        """
        Classify a page as schematic or not.

        Returns PageClassification with confidence score.
        """
        # Extract features
        features = self._extract_features(page, page_image)

        # Use heuristic classification
        is_schematic, confidence = self._heuristic_classify(features)

        return PageClassification(
            pdf_name="",  # Will be set by caller
            page_num=0,   # Will be set by caller
            is_schematic=is_schematic,
            confidence=confidence,
            method="heuristic",
            features=features
        )

    def _extract_features(self, page: pymupdf.Page, image: Image.Image) -> Dict:
        """Extract classification features from page."""
        features = {}

        # 1. Vector analysis from PDF
        try:
            drawings = page.get_drawings()
            features['total_drawings'] = len(drawings)

            # Count drawing types
            lines = [d for d in drawings if d.get('items') and any(
                item[0] == 'l' for item in d['items']
            )]
            features['line_count'] = len(lines)

            # Circles (potential terminals)
            circles = [d for d in drawings if d.get('items') and any(
                item[0] == 'c' for item in d['items']
            )]
            features['circle_count'] = len(circles)

            # Rectangles
            rects = [d for d in drawings if d.get('items') and any(
                item[0] == 're' for item in d['items']
            )]
            features['rect_count'] = len(rects)

        except Exception as e:
            features['total_drawings'] = 0
            features['line_count'] = 0
            features['circle_count'] = 0
            features['rect_count'] = 0

        # 2. Text analysis
        try:
            text_blocks = page.get_text("blocks")
            features['text_block_count'] = len(text_blocks)
            total_text = page.get_text()
            features['text_char_count'] = len(total_text)
        except:
            features['text_block_count'] = 0
            features['text_char_count'] = 0

        # 3. Image analysis
        img_array = np.array(image.convert('L'))  # Grayscale

        # Color distribution (schematics are high contrast)
        features['mean_brightness'] = float(np.mean(img_array))
        features['std_brightness'] = float(np.std(img_array))

        # Edge density (schematics have many edges)
        # Simple edge detection using gradient
        gx = np.abs(np.diff(img_array.astype(float), axis=1))
        gy = np.abs(np.diff(img_array.astype(float), axis=0))
        features['edge_density'] = float((np.mean(gx) + np.mean(gy)) / 2)

        # White ratio (schematics are mostly white background)
        white_threshold = 240
        features['white_ratio'] = float(np.sum(img_array > white_threshold) / img_array.size)

        # Black ratio (lines are black)
        black_threshold = 50
        features['black_ratio'] = float(np.sum(img_array < black_threshold) / img_array.size)

        return features

    def _heuristic_classify(self, features: Dict) -> Tuple[bool, float]:
        """
        Heuristic classification based on extracted features.

        Returns (is_schematic, confidence)
        """
        score = 0.0
        max_score = 0.0

        # Rule 1: Line count (weight: 30%)
        # Schematics typically have 100-2000 lines
        line_count = features.get('line_count', 0)
        max_score += 30
        if line_count > 50:
            score += min(30, line_count / 50 * 15)  # Up to 30 points

        # Rule 2: Circle count (weight: 25%)
        # Terminals are circles - schematics have many
        circle_count = features.get('circle_count', 0)
        max_score += 25
        if circle_count > 5:
            score += min(25, circle_count / 10 * 12.5)

        # Rule 3: Drawing density (weight: 20%)
        total_drawings = features.get('total_drawings', 0)
        max_score += 20
        if total_drawings > 100:
            score += min(20, total_drawings / 200 * 20)

        # Rule 4: White background ratio (weight: 15%)
        # Schematics have 70-95% white background
        white_ratio = features.get('white_ratio', 0)
        max_score += 15
        if 0.6 < white_ratio < 0.98:
            score += 15
        elif 0.4 < white_ratio < 0.6 or white_ratio > 0.98:
            score += 7

        # Rule 5: Edge density (weight: 10%)
        # Schematics have moderate edge density
        edge_density = features.get('edge_density', 0)
        max_score += 10
        if 2 < edge_density < 20:
            score += 10
        elif 1 < edge_density < 30:
            score += 5

        # Calculate confidence
        confidence = score / max_score if max_score > 0 else 0

        # Threshold for classification
        is_schematic = confidence > 0.4

        return is_schematic, confidence


class PDFPageExtractor:
    """
    Extracts pages from PDFs and classifies them.
    """

    def __init__(self, output_dir: str, classifier: SchematicClassifier,
                 dpi: int = 150, min_confidence: float = 0.3):
        self.output_dir = Path(output_dir)
        self.classifier = classifier
        self.dpi = dpi
        self.min_confidence = min_confidence

        # Create output directories
        self.schematic_dir = self.output_dir / "schematics"
        self.non_schematic_dir = self.output_dir / "non_schematics"
        self.metadata_dir = self.output_dir / "metadata"

        for d in [self.schematic_dir, self.non_schematic_dir, self.metadata_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def extract_pdf(self, pdf_path: str,
                    page_range: Optional[Tuple[int, int]] = None,
                    save_non_schematics: bool = False) -> List[PageClassification]:
        """
        Extract and classify all pages from a PDF.

        Args:
            pdf_path: Path to PDF file
            page_range: Optional (start, end) page numbers (1-indexed)
            save_non_schematics: Whether to save non-schematic pages

        Returns:
            List of PageClassification results
        """
        pdf_path = Path(pdf_path)
        pdf_name = pdf_path.stem

        print(f"\n[INFO] Processing: {pdf_path.name}")

        try:
            doc = pymupdf.open(str(pdf_path))
        except Exception as e:
            print(f"[ERROR] Could not open PDF: {e}")
            return []

        total_pages = len(doc)
        print(f"[INFO] Total pages: {total_pages}")

        # Determine page range
        start_page = 0
        end_page = total_pages
        if page_range:
            start_page = max(0, page_range[0] - 1)
            end_page = min(total_pages, page_range[1])

        results = []
        schematic_count = 0

        for page_idx in range(start_page, end_page):
            page_num = page_idx + 1

            # Progress indicator
            if page_num % 10 == 0 or page_num == end_page:
                print(f"  Processing page {page_num}/{end_page}...", end='\r')

            try:
                page = doc.load_page(page_idx)

                # Render page to image
                mat = pymupdf.Matrix(self.dpi / 72, self.dpi / 72)
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # Classify
                classification = self.classifier.classify_page(page, img)
                classification.pdf_name = pdf_name
                classification.page_num = page_num

                # Save if schematic (or all if requested)
                if classification.is_schematic and classification.confidence >= self.min_confidence:
                    output_path = self.schematic_dir / f"{pdf_name}_page_{page_num:04d}.jpg"
                    img.save(str(output_path), "JPEG", quality=95)
                    classification.output_path = str(output_path)
                    schematic_count += 1
                elif save_non_schematics:
                    output_path = self.non_schematic_dir / f"{pdf_name}_page_{page_num:04d}.jpg"
                    img.save(str(output_path), "JPEG", quality=85)
                    classification.output_path = str(output_path)

                results.append(classification)

            except Exception as e:
                print(f"\n[WARNING] Error processing page {page_num}: {e}")
                continue

        doc.close()

        print(f"\n[INFO] Extracted {schematic_count} schematic pages from {pdf_name}")

        return results

    def save_metadata(self, results: List[PageClassification], pdf_name: str):
        """Save classification metadata to JSON."""
        metadata = {
            'pdf_name': pdf_name,
            'extraction_date': datetime.now().isoformat(),
            'total_pages': len(results),
            'schematic_pages': sum(1 for r in results if r.is_schematic),
            'min_confidence': self.min_confidence,
            'pages': [asdict(r) for r in results]
        }

        output_path = self.metadata_dir / f"{pdf_name}_metadata.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"[INFO] Saved metadata to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract and classify schematic pages from PDFs"
    )
    parser.add_argument('--pdf', type=str, help="Single PDF file to process")
    parser.add_argument('--pdf-dir', type=str, help="Directory containing PDFs")
    parser.add_argument('--output-dir', type=str, default='./extracted_schematics',
                        help="Output directory for extracted images")
    parser.add_argument('--dpi', type=int, default=150,
                        help="DPI for page rendering (default: 150)")
    parser.add_argument('--min-confidence', type=float, default=0.3,
                        help="Minimum confidence threshold (default: 0.3)")
    parser.add_argument('--model', type=str, default=None,
                        help="Path to trained classifier model (optional)")
    parser.add_argument('--page-range', type=str, default=None,
                        help="Page range to process, e.g., '1-100'")
    parser.add_argument('--save-all', action='store_true',
                        help="Save non-schematic pages too")
    parser.add_argument('--analyze-only', action='store_true',
                        help="Only analyze, don't save images")

    args = parser.parse_args()

    # Validate arguments
    if not args.pdf and not args.pdf_dir:
        parser.error("Either --pdf or --pdf-dir is required")

    # Parse page range
    page_range = None
    if args.page_range:
        try:
            start, end = map(int, args.page_range.split('-'))
            page_range = (start, end)
        except:
            parser.error("Invalid page range format. Use: start-end (e.g., 1-100)")

    # Initialize classifier
    classifier = SchematicClassifier(model_path=args.model)

    # Initialize extractor
    extractor = PDFPageExtractor(
        output_dir=args.output_dir,
        classifier=classifier,
        dpi=args.dpi,
        min_confidence=args.min_confidence
    )

    # Collect PDFs to process
    pdf_files = []
    if args.pdf:
        pdf_files.append(args.pdf)
    if args.pdf_dir:
        pdf_dir = Path(args.pdf_dir)
        pdf_files.extend([str(f) for f in pdf_dir.glob("*.pdf")])

    if not pdf_files:
        print("[ERROR] No PDF files found")
        sys.exit(1)

    print(f"[INFO] Found {len(pdf_files)} PDF file(s) to process")

    # Process each PDF
    all_results = []
    total_schematics = 0

    for pdf_path in pdf_files:
        results = extractor.extract_pdf(
            pdf_path,
            page_range=page_range,
            save_non_schematics=args.save_all
        )

        if results:
            pdf_name = Path(pdf_path).stem
            extractor.save_metadata(results, pdf_name)
            all_results.extend(results)
            total_schematics += sum(1 for r in results if r.is_schematic)

    # Summary
    print("\n" + "="*60)
    print("EXTRACTION SUMMARY")
    print("="*60)
    print(f"Total pages processed: {len(all_results)}")
    print(f"Schematic pages found: {total_schematics}")
    print(f"Output directory: {args.output_dir}")

    # Show confidence distribution
    if all_results:
        confidences = [r.confidence for r in all_results if r.is_schematic]
        if confidences:
            print(f"\nSchematic confidence distribution:")
            print(f"  Min: {min(confidences):.2f}")
            print(f"  Max: {max(confidences):.2f}")
            print(f"  Avg: {sum(confidences)/len(confidences):.2f}")


if __name__ == "__main__":
    main()
