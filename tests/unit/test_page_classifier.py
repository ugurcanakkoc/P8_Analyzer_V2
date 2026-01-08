"""
Unit tests for Page Classifier (Schematic Filter) feature.

Tests the YOLO-based page classification that distinguishes
schematic pages from non-schematic pages (cover sheets, parts lists, etc.)
"""

import os
import sys
import pytest
import tempfile
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestPageClassifierModel:
    """Tests for the page classifier model loading and inference."""

    @pytest.fixture
    def model_path(self):
        """Path to the production page classifier model."""
        return PROJECT_ROOT / "p8_analyzer" / "models" / "page_classifier.pt"

    @pytest.fixture
    def sample_pdf_path(self):
        """Path to sample PDF for testing."""
        return PROJECT_ROOT / "data" / "ornek.pdf"

    def test_model_file_exists(self, model_path):
        """Model file should exist in production location."""
        assert model_path.exists(), f"Model not found at {model_path}"

    def test_model_file_size_reasonable(self, model_path):
        """Model file should be reasonable size (not empty, not huge)."""
        if not model_path.exists():
            pytest.skip("Model file not found")
        size_mb = model_path.stat().st_size / (1024 * 1024)
        assert 0.5 < size_mb < 50, f"Model size {size_mb:.1f} MB seems wrong"

    @pytest.mark.skipif(
        not (PROJECT_ROOT / "p8_analyzer" / "models" / "page_classifier.pt").exists(),
        reason="Model file not found"
    )
    def test_model_loads_successfully(self, model_path):
        """Model should load without errors."""
        try:
            from ultralytics import YOLO
        except ImportError:
            pytest.skip("ultralytics not installed")

        model = YOLO(str(model_path))
        assert model is not None
        assert hasattr(model, 'names')

    @pytest.mark.skipif(
        not (PROJECT_ROOT / "p8_analyzer" / "models" / "page_classifier.pt").exists(),
        reason="Model file not found"
    )
    def test_model_has_correct_classes(self, model_path):
        """Model should have schematic and non_schematic classes."""
        try:
            from ultralytics import YOLO
        except ImportError:
            pytest.skip("ultralytics not installed")

        model = YOLO(str(model_path))
        class_names = set(model.names.values())

        assert "schematic" in class_names, "Model missing 'schematic' class"
        assert "non_schematic" in class_names, "Model missing 'non_schematic' class"
        assert len(class_names) == 2, f"Expected 2 classes, got {len(class_names)}"

    @pytest.mark.skipif(
        not (PROJECT_ROOT / "p8_analyzer" / "models" / "page_classifier.pt").exists()
        or not (PROJECT_ROOT / "data" / "ornek.pdf").exists(),
        reason="Model or sample PDF not found"
    )
    def test_model_classifies_pdf_page(self, model_path, sample_pdf_path):
        """Model should classify a rendered PDF page."""
        try:
            from ultralytics import YOLO
            import pymupdf
        except ImportError as e:
            pytest.skip(f"Required package not installed: {e}")

        model = YOLO(str(model_path))
        doc = pymupdf.open(str(sample_pdf_path))

        try:
            page = doc.load_page(0)
            mat = pymupdf.Matrix(150/72, 150/72)  # 150 DPI
            pix = page.get_pixmap(matrix=mat)

            # Use fixed temp path (Windows-safe)
            temp_dir = tempfile.gettempdir()
            tmp_path = os.path.join(temp_dir, "test_classifier_temp.png")
            pix.save(tmp_path)

            results = model.predict(tmp_path, verbose=False)

            assert results is not None
            assert len(results) > 0
            assert results[0].probs is not None

            probs = results[0].probs
            top_class = probs.top1
            class_name = results[0].names[top_class]
            confidence = float(probs.top1conf)

            assert class_name in ["schematic", "non_schematic"]
            assert 0.0 <= confidence <= 1.0

            # Clean up
            os.unlink(tmp_path)
        finally:
            doc.close()


class TestTempFileHandling:
    """Tests for temp file handling on Windows."""

    def test_temp_file_overwrite_works(self):
        """Temp file can be overwritten multiple times."""
        temp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(temp_dir, "test_overwrite.txt")

        try:
            # Write multiple times
            for i in range(3):
                with open(tmp_path, 'w') as f:
                    f.write(f"test content {i}")

                with open(tmp_path, 'r') as f:
                    content = f.read()
                assert content == f"test content {i}"
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_png_overwrite_with_pymupdf(self):
        """PNG temp file can be overwritten by pymupdf."""
        try:
            import pymupdf
        except ImportError:
            pytest.skip("pymupdf not installed")

        temp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(temp_dir, "test_pymupdf_temp.png")

        try:
            # Create a simple pixmap and save multiple times
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 1)
            pix.clear_with(255)  # White background

            for i in range(3):
                pix.save(tmp_path)
                assert os.path.exists(tmp_path)
                size = os.path.getsize(tmp_path)
                assert size > 0
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestSchematicFilterLogic:
    """Tests for the schematic filter navigation logic."""

    def test_find_next_schematic_page(self):
        """Find next schematic page from current position."""
        schematic_pages = [5, 10, 15, 20]
        current_page = 7

        # Find next schematic page after current
        next_pages = [p for p in schematic_pages if p > current_page]
        next_schematic = next_pages[0] if next_pages else None

        assert next_schematic == 10

    def test_find_prev_schematic_page(self):
        """Find previous schematic page from current position."""
        schematic_pages = [5, 10, 15, 20]
        current_page = 12

        # Find previous schematic page before current
        prev_pages = [p for p in schematic_pages if p < current_page]
        prev_schematic = prev_pages[-1] if prev_pages else None

        assert prev_schematic == 10

    def test_wrap_to_first_schematic(self):
        """Wrap to first schematic when at end."""
        schematic_pages = [5, 10, 15, 20]
        current_page = 20

        next_pages = [p for p in schematic_pages if p > current_page]
        next_schematic = next_pages[0] if next_pages else schematic_pages[0]

        assert next_schematic == 5  # Wraps to first

    def test_wrap_to_last_schematic(self):
        """Wrap to last schematic when at beginning."""
        schematic_pages = [5, 10, 15, 20]
        current_page = 5

        prev_pages = [p for p in schematic_pages if p < current_page]
        prev_schematic = prev_pages[-1] if prev_pages else schematic_pages[-1]

        assert prev_schematic == 20  # Wraps to last

    def test_empty_schematic_list(self):
        """Handle empty schematic page list gracefully."""
        schematic_pages = []
        current_page = 5

        next_pages = [p for p in schematic_pages if p > current_page]
        next_schematic = next_pages[0] if next_pages else (
            schematic_pages[0] if schematic_pages else None
        )

        assert next_schematic is None
