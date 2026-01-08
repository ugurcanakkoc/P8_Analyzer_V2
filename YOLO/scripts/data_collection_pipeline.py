"""
Data Collection Pipeline

Orchestrates the complete data collection workflow:
1. Extract schematic pages from PDFs
2. Generate LLM annotation suggestions
3. Prepare data for human review in annotator

Usage:
    # Full pipeline
    python data_collection_pipeline.py --pdf-dir ../../data --output-dir ./pipeline_output

    # Step by step
    python data_collection_pipeline.py --step extract --pdf-dir ../../data
    python data_collection_pipeline.py --step annotate --image-dir ./extracted/schematics
    python data_collection_pipeline.py --step prepare --suggestions-dir ./suggestions
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add script directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from extract_schematic_pages import SchematicClassifier, PDFPageExtractor
from llm_annotation_helper import LLMAnnotationHelper, AnnotationSuggestions


class DataCollectionPipeline:
    """
    End-to-end data collection pipeline for YOLO training.
    """

    def __init__(self, output_dir: str, provider: str = "anthropic"):
        self.output_dir = Path(output_dir)
        self.provider = provider

        # Pipeline directories
        self.extracted_dir = self.output_dir / "1_extracted"
        self.suggestions_dir = self.output_dir / "2_suggestions"
        self.review_dir = self.output_dir / "3_for_review"
        self.approved_dir = self.output_dir / "4_approved"

        # Create directories
        for d in [self.extracted_dir, self.suggestions_dir,
                  self.review_dir, self.approved_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # State tracking
        self.state_file = self.output_dir / "pipeline_state.json"
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load pipeline state from file."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            'extracted_pages': [],
            'annotated_pages': [],
            'reviewed_pages': [],
            'last_run': None
        }

    def _save_state(self):
        """Save pipeline state to file."""
        self.state['last_run'] = datetime.now().isoformat()
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def step1_extract_schematics(self, pdf_dir: str,
                                  min_confidence: float = 0.3,
                                  dpi: int = 150) -> int:
        """
        Step 1: Extract schematic pages from PDFs.

        Returns number of schematic pages extracted.
        """
        print("\n" + "="*60)
        print("STEP 1: Extracting Schematic Pages")
        print("="*60)

        classifier = SchematicClassifier()
        extractor = PDFPageExtractor(
            output_dir=str(self.extracted_dir),
            classifier=classifier,
            dpi=dpi,
            min_confidence=min_confidence
        )

        pdf_dir = Path(pdf_dir)
        pdf_files = list(pdf_dir.glob("*.pdf"))

        if not pdf_files:
            print(f"[WARNING] No PDF files found in {pdf_dir}")
            return 0

        print(f"[INFO] Found {len(pdf_files)} PDF files")

        total_extracted = 0
        for pdf_path in pdf_files:
            results = extractor.extract_pdf(str(pdf_path))
            schematic_count = sum(1 for r in results if r.is_schematic)
            total_extracted += schematic_count

            # Track in state
            for r in results:
                if r.is_schematic and r.output_path:
                    self.state['extracted_pages'].append({
                        'path': r.output_path,
                        'pdf': r.pdf_name,
                        'page': r.page_num,
                        'confidence': r.confidence
                    })

            extractor.save_metadata(results, pdf_path.stem)

        self._save_state()
        print(f"\n[STEP 1 COMPLETE] Extracted {total_extracted} schematic pages")
        return total_extracted

    def step2_generate_suggestions(self, image_dir: Optional[str] = None,
                                    batch_size: int = 10) -> int:
        """
        Step 2: Generate LLM annotation suggestions.

        Returns number of images annotated.
        """
        print("\n" + "="*60)
        print("STEP 2: Generating LLM Annotation Suggestions")
        print("="*60)

        # Use extracted schematics if no image_dir specified
        if image_dir:
            source_dir = Path(image_dir)
        else:
            source_dir = self.extracted_dir / "schematics"

        if not source_dir.exists():
            print(f"[ERROR] Source directory not found: {source_dir}")
            return 0

        # Find images not yet annotated
        image_extensions = {'.jpg', '.jpeg', '.png'}
        all_images = [f for f in source_dir.iterdir()
                      if f.suffix.lower() in image_extensions]

        annotated_stems = {Path(p['path']).stem
                          for p in self.state.get('annotated_pages', [])}
        pending_images = [img for img in all_images
                         if img.stem not in annotated_stems]

        if not pending_images:
            print("[INFO] All images already have suggestions")
            return 0

        print(f"[INFO] {len(pending_images)} images pending annotation")
        print(f"[INFO] Processing in batches of {batch_size}")

        # Initialize LLM helper
        try:
            helper = LLMAnnotationHelper(provider=self.provider)
        except Exception as e:
            print(f"[ERROR] Could not initialize LLM helper: {e}")
            print("[INFO] Please check your API keys in .env file")
            return 0

        # Process batch
        annotated_count = 0
        batch = pending_images[:batch_size]

        for i, img_path in enumerate(batch, 1):
            print(f"\n[{i}/{len(batch)}] Processing: {img_path.name}")

            try:
                suggestions = helper.analyze_image(str(img_path))

                # Save suggestions JSON
                json_path = self.suggestions_dir / f"{img_path.stem}_suggestions.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    from dataclasses import asdict
                    json.dump(asdict(suggestions), f, indent=2, ensure_ascii=False)

                # Save OBB labels
                labels = helper.suggestions_to_obb(suggestions)
                label_path = self.suggestions_dir / f"{img_path.stem}.txt"
                with open(label_path, 'w') as f:
                    f.write('\n'.join(labels))

                # Track state
                self.state.setdefault('annotated_pages', []).append({
                    'image_path': str(img_path),
                    'suggestions_path': str(json_path),
                    'label_path': str(label_path),
                    'component_count': len(suggestions.suggestions),
                    'timestamp': datetime.now().isoformat()
                })

                annotated_count += 1
                print(f"  Found {len(suggestions.suggestions)} components")

            except Exception as e:
                print(f"[ERROR] Failed: {e}")
                continue

        self._save_state()
        print(f"\n[STEP 2 COMPLETE] Generated suggestions for {annotated_count} images")

        remaining = len(pending_images) - batch_size
        if remaining > 0:
            print(f"[INFO] {remaining} images remaining. Run again to continue.")

        return annotated_count

    def step3_prepare_for_review(self) -> int:
        """
        Step 3: Copy images and suggestions to review directory
        for loading into annotator tool.

        Returns number of files prepared.
        """
        print("\n" + "="*60)
        print("STEP 3: Preparing Data for Review")
        print("="*60)

        # Create review subdirectories matching annotator expectations
        review_images = self.review_dir / "images"
        review_labels = self.review_dir / "labels"
        review_images.mkdir(exist_ok=True)
        review_labels.mkdir(exist_ok=True)

        prepared_count = 0
        annotated_pages = self.state.get('annotated_pages', [])

        for entry in annotated_pages:
            img_path = Path(entry['image_path'])
            label_path = Path(entry.get('label_path', ''))

            if not img_path.exists():
                continue

            # Copy image
            dest_img = review_images / img_path.name
            if not dest_img.exists():
                shutil.copy(img_path, dest_img)

            # Copy label if exists
            if label_path.exists():
                dest_label = review_labels / label_path.name
                if not dest_label.exists():
                    shutil.copy(label_path, dest_label)

            prepared_count += 1

        self._save_state()
        print(f"\n[STEP 3 COMPLETE] Prepared {prepared_count} files for review")
        print(f"[INFO] Review directory: {self.review_dir}")
        print(f"[INFO] Open smart_annotator.py and load images from: {review_images}")

        return prepared_count

    def get_status(self) -> dict:
        """Get pipeline status summary."""
        extracted = len(self.state.get('extracted_pages', []))
        annotated = len(self.state.get('annotated_pages', []))
        reviewed = len(self.state.get('reviewed_pages', []))

        return {
            'extracted_pages': extracted,
            'annotated_pages': annotated,
            'reviewed_pages': reviewed,
            'last_run': self.state.get('last_run'),
            'output_dir': str(self.output_dir)
        }


def main():
    parser = argparse.ArgumentParser(
        description="Data Collection Pipeline for YOLO Training"
    )
    parser.add_argument('--step', type=str,
                        choices=['extract', 'annotate', 'prepare', 'all', 'status'],
                        default='status',
                        help="Pipeline step to run")
    parser.add_argument('--pdf-dir', type=str,
                        help="Directory containing PDFs (for extract step)")
    parser.add_argument('--image-dir', type=str,
                        help="Directory containing images (for annotate step)")
    parser.add_argument('--output-dir', type=str, default='./pipeline_output',
                        help="Output directory for pipeline")
    parser.add_argument('--provider', type=str, default='anthropic',
                        choices=['anthropic', 'openai'],
                        help="LLM provider for annotation")
    parser.add_argument('--batch-size', type=int, default=10,
                        help="Number of images to annotate per run")
    parser.add_argument('--min-confidence', type=float, default=0.3,
                        help="Minimum confidence for schematic classification")
    parser.add_argument('--dpi', type=int, default=150,
                        help="DPI for PDF rendering")

    args = parser.parse_args()

    # Initialize pipeline
    pipeline = DataCollectionPipeline(
        output_dir=args.output_dir,
        provider=args.provider
    )

    # Run requested step
    if args.step == 'status':
        status = pipeline.get_status()
        print("\n" + "="*60)
        print("PIPELINE STATUS")
        print("="*60)
        print(f"Output directory: {status['output_dir']}")
        print(f"Last run: {status['last_run'] or 'Never'}")
        print(f"\nProgress:")
        print(f"  Extracted schematic pages: {status['extracted_pages']}")
        print(f"  LLM annotated pages: {status['annotated_pages']}")
        print(f"  Human reviewed pages: {status['reviewed_pages']}")

    elif args.step == 'extract':
        if not args.pdf_dir:
            parser.error("--pdf-dir required for extract step")
        pipeline.step1_extract_schematics(
            pdf_dir=args.pdf_dir,
            min_confidence=args.min_confidence,
            dpi=args.dpi
        )

    elif args.step == 'annotate':
        pipeline.step2_generate_suggestions(
            image_dir=args.image_dir,
            batch_size=args.batch_size
        )

    elif args.step == 'prepare':
        pipeline.step3_prepare_for_review()

    elif args.step == 'all':
        if not args.pdf_dir:
            parser.error("--pdf-dir required for full pipeline")

        # Run all steps
        extracted = pipeline.step1_extract_schematics(
            pdf_dir=args.pdf_dir,
            min_confidence=args.min_confidence,
            dpi=args.dpi
        )

        if extracted > 0:
            pipeline.step2_generate_suggestions(batch_size=args.batch_size)
            pipeline.step3_prepare_for_review()

        # Final status
        status = pipeline.get_status()
        print("\n" + "="*60)
        print("PIPELINE COMPLETE")
        print("="*60)
        print(f"Extracted: {status['extracted_pages']} schematic pages")
        print(f"Annotated: {status['annotated_pages']} pages with LLM")
        print(f"Ready for review: {status['annotated_pages']} pages")
        print(f"\nNext steps:")
        print(f"1. Open smart_annotator.py")
        print(f"2. Load images from: {pipeline.review_dir}/images")
        print(f"3. Review and correct LLM suggestions")
        print(f"4. Save approved annotations to training directory")


if __name__ == "__main__":
    main()
