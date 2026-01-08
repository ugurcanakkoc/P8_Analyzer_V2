"""
Unit tests for YOLO auto-detect feature in annotator.

Tests the YOLO model loading and inference on PDF pages.
"""
import os
import sys
import pytest
from pathlib import Path
from PIL import Image

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Check if ultralytics is available
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

# Check if pymupdf is available
try:
    import pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def yolo_dir():
    """Path to YOLO directory."""
    return Path(PROJECT_ROOT) / "YOLO"


@pytest.fixture
def model_paths(yolo_dir):
    """List of possible model paths."""
    return [
        yolo_dir / "best.pt",
        yolo_dir / "runs" / "role_detection" / "weights" / "best.pt",
        yolo_dir / "customers" / "troester" / "models" / "plc_model.pt",
    ]


@pytest.fixture
def sample_pdf_path():
    """Path to sample PDF."""
    return Path(PROJECT_ROOT) / "data" / "ornek.pdf"


@pytest.fixture
def page_11_image(sample_pdf_path):
    """Extract page 11 from PDF as PIL Image."""
    if not PYMUPDF_AVAILABLE:
        pytest.skip("pymupdf not installed")

    if not sample_pdf_path.exists():
        pytest.skip(f"Sample PDF not found: {sample_pdf_path}")

    doc = pymupdf.open(str(sample_pdf_path))
    if len(doc) < 11:
        pytest.skip(f"PDF has only {len(doc)} pages, need at least 11")

    # Page index is 0-based, so page 11 is index 10
    page = doc[10]

    # Render at high DPI for better detection
    mat = pymupdf.Matrix(2.0, 2.0)  # 2x zoom = ~144 DPI
    pix = page.get_pixmap(matrix=mat)

    # Convert to PIL Image
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    doc.close()
    return img


@pytest.fixture
def loaded_yolo_model(model_paths):
    """Load YOLO model from available paths."""
    if not YOLO_AVAILABLE:
        pytest.skip("ultralytics not installed")

    for path in model_paths:
        if path.exists():
            print(f"Loading model from: {path}")
            model = YOLO(str(path))
            return model

    pytest.skip("No YOLO model found")


# =============================================================================
# Tests: Model Loading
# =============================================================================

class TestModelLoading:
    """Tests for YOLO model loading."""

    def test_model_exists(self, model_paths):
        """At least one model file should exist."""
        existing = [p for p in model_paths if p.exists()]
        print(f"Found {len(existing)} model(s):")
        for p in existing:
            print(f"  - {p}")
        assert len(existing) > 0, f"No YOLO model found. Checked: {model_paths}"

    @pytest.mark.skipif(not YOLO_AVAILABLE, reason="ultralytics not installed")
    def test_model_loads_successfully(self, loaded_yolo_model):
        """Model should load without errors."""
        assert loaded_yolo_model is not None
        print(f"Model loaded: {type(loaded_yolo_model)}")

    @pytest.mark.skipif(not YOLO_AVAILABLE, reason="ultralytics not installed")
    def test_model_has_class_names(self, loaded_yolo_model):
        """Model should have class names defined."""
        assert hasattr(loaded_yolo_model, 'names')
        names = loaded_yolo_model.names
        print(f"Model classes ({len(names)}): {names}")
        assert len(names) > 0, "Model has no class names"

    @pytest.mark.skipif(not YOLO_AVAILABLE, reason="ultralytics not installed")
    def test_model_task_type(self, loaded_yolo_model):
        """Check the model task type (detect, obb, segment, etc.)."""
        task = getattr(loaded_yolo_model, 'task', None)
        print(f"Model task type: {task}")
        # Model should be either standard detection or OBB
        # If task is 'obb', we need OBB-specific handling


# =============================================================================
# Tests: PDF Page Extraction
# =============================================================================

class TestPageExtraction:
    """Tests for PDF page extraction."""

    @pytest.mark.skipif(not PYMUPDF_AVAILABLE, reason="pymupdf not installed")
    def test_sample_pdf_exists(self, sample_pdf_path):
        """Sample PDF should exist."""
        assert sample_pdf_path.exists(), f"Sample PDF not found: {sample_pdf_path}"

    @pytest.mark.skipif(not PYMUPDF_AVAILABLE, reason="pymupdf not installed")
    def test_pdf_has_page_11(self, sample_pdf_path):
        """PDF should have at least 11 pages."""
        doc = pymupdf.open(str(sample_pdf_path))
        page_count = len(doc)
        doc.close()
        print(f"PDF has {page_count} pages")
        assert page_count >= 11, f"PDF has only {page_count} pages"

    @pytest.mark.skipif(not PYMUPDF_AVAILABLE, reason="pymupdf not installed")
    def test_page_11_extraction(self, page_11_image):
        """Page 11 should extract as a valid image."""
        assert page_11_image is not None
        assert isinstance(page_11_image, Image.Image)
        print(f"Page 11 image size: {page_11_image.size}")
        assert page_11_image.size[0] > 0
        assert page_11_image.size[1] > 0


# =============================================================================
# Tests: YOLO Inference
# =============================================================================

class TestYoloInference:
    """Tests for YOLO inference on PDF pages."""

    @pytest.mark.skipif(not YOLO_AVAILABLE or not PYMUPDF_AVAILABLE,
                        reason="ultralytics or pymupdf not installed")
    def test_inference_runs_without_error(self, loaded_yolo_model, page_11_image):
        """Inference should run without throwing exceptions."""
        # Run inference with low confidence to catch any detections
        results = loaded_yolo_model(page_11_image, verbose=True, conf=0.1)
        assert results is not None
        print(f"Inference returned {len(results)} result object(s)")

    @pytest.mark.skipif(not YOLO_AVAILABLE or not PYMUPDF_AVAILABLE,
                        reason="ultralytics or pymupdf not installed")
    def test_inference_result_structure(self, loaded_yolo_model, page_11_image):
        """Inference results should have expected structure."""
        results = loaded_yolo_model(page_11_image, verbose=False, conf=0.1)

        assert len(results) > 0, "Should have at least one result"
        result = results[0]

        # Check result attributes
        print(f"Result attributes: {dir(result)}")

        # Check if it's OBB or standard detection
        has_obb = hasattr(result, 'obb') and result.obb is not None
        has_boxes = hasattr(result, 'boxes') and result.boxes is not None

        print(f"Has OBB: {has_obb}")
        print(f"Has boxes: {has_boxes}")

        if has_obb:
            obb = result.obb
            print(f"OBB data shape: {obb.data.shape if hasattr(obb, 'data') else 'N/A'}")
            print(f"OBB count: {len(obb) if obb is not None else 0}")

        if has_boxes:
            boxes = result.boxes
            print(f"Boxes count: {len(boxes) if boxes is not None else 0}")
            if boxes is not None and len(boxes) > 0:
                print(f"First box conf: {boxes.conf[0]:.3f}")
                print(f"First box cls: {int(boxes.cls[0])}")

    @pytest.mark.skipif(not YOLO_AVAILABLE or not PYMUPDF_AVAILABLE,
                        reason="ultralytics or pymupdf not installed")
    def test_detection_count_on_page_11(self, loaded_yolo_model, page_11_image):
        """Count detections on page 11 at various confidence levels."""
        conf_levels = [0.1, 0.25, 0.5, 0.75]

        for conf in conf_levels:
            results = loaded_yolo_model(page_11_image, verbose=False, conf=conf)
            result = results[0]

            # Check both boxes and obb
            box_count = len(result.boxes) if result.boxes is not None else 0
            obb_count = len(result.obb) if hasattr(result, 'obb') and result.obb is not None else 0

            total_count = max(box_count, obb_count)  # Use whichever is populated
            print(f"conf={conf}: boxes={box_count}, obb={obb_count}, total={total_count}")

    @pytest.mark.skipif(not YOLO_AVAILABLE or not PYMUPDF_AVAILABLE,
                        reason="ultralytics or pymupdf not installed")
    def test_detection_classes_on_page_11(self, loaded_yolo_model, page_11_image):
        """Check which classes are detected on page 11."""
        results = loaded_yolo_model(page_11_image, verbose=False, conf=0.1)
        result = results[0]

        class_names = loaded_yolo_model.names
        detected_classes = {}

        # Handle both OBB and standard boxes
        if hasattr(result, 'obb') and result.obb is not None and len(result.obb) > 0:
            for i in range(len(result.obb)):
                cls_id = int(result.obb.cls[i])
                conf = float(result.obb.conf[i])
                cls_name = class_names.get(cls_id, f"class_{cls_id}")
                if cls_name not in detected_classes:
                    detected_classes[cls_name] = []
                detected_classes[cls_name].append(conf)

        elif result.boxes is not None and len(result.boxes) > 0:
            for i in range(len(result.boxes)):
                cls_id = int(result.boxes.cls[i])
                conf = float(result.boxes.conf[i])
                cls_name = class_names.get(cls_id, f"class_{cls_id}")
                if cls_name not in detected_classes:
                    detected_classes[cls_name] = []
                detected_classes[cls_name].append(conf)

        print("\nDetected classes on page 11:")
        for cls_name, confs in detected_classes.items():
            print(f"  {cls_name}: {len(confs)} detections, max_conf={max(confs):.3f}")

        # This test is informational - we want to understand what the model sees


# =============================================================================
# Tests: OBB vs Standard Detection
# =============================================================================

class TestObbVsStandard:
    """Tests to understand if model uses OBB or standard detection."""

    @pytest.mark.skipif(not YOLO_AVAILABLE, reason="ultralytics not installed")
    def test_model_type_detection(self, loaded_yolo_model, yolo_dir):
        """Determine model type from file and inference."""
        # Check model file size and structure
        model_path = None
        for path in [yolo_dir / "best.pt",
                     yolo_dir / "runs" / "role_detection" / "weights" / "best.pt"]:
            if path.exists():
                model_path = path
                break

        if model_path:
            file_size = model_path.stat().st_size / (1024 * 1024)  # MB
            print(f"Model file: {model_path.name}, size: {file_size:.2f} MB")

        # Check model properties
        print(f"Model task: {getattr(loaded_yolo_model, 'task', 'unknown')}")
        print(f"Model type: {type(loaded_yolo_model).__name__}")

        # Check model names format
        names = loaded_yolo_model.names
        print(f"Class names: {names}")

    @pytest.mark.skipif(not YOLO_AVAILABLE or not PYMUPDF_AVAILABLE,
                        reason="ultralytics or pymupdf not installed")
    def test_obb_inference_if_needed(self, loaded_yolo_model, page_11_image):
        """Test if model returns OBB results and how to handle them."""
        results = loaded_yolo_model(page_11_image, verbose=False, conf=0.1)
        result = results[0]

        # Comprehensive result inspection
        print("\n=== Result Inspection ===")
        print(f"Result type: {type(result)}")

        if hasattr(result, 'obb'):
            obb = result.obb
            print(f"\nOBB attribute exists: {obb is not None}")
            if obb is not None and len(obb) > 0:
                print(f"OBB detection count: {len(obb)}")
                print(f"OBB data shape: {obb.data.shape}")
                print(f"First OBB data: {obb.data[0].tolist()}")

                # Extract OBB info
                for i in range(min(3, len(obb))):
                    cls_id = int(obb.cls[i])
                    conf = float(obb.conf[i])
                    xywhr = obb.xywhr[i].tolist() if hasattr(obb, 'xywhr') else None
                    xyxyxyxy = obb.xyxyxyxy[i].tolist() if hasattr(obb, 'xyxyxyxy') else None
                    print(f"  OBB {i}: cls={cls_id}, conf={conf:.3f}")
                    if xywhr:
                        print(f"    xywhr (center, w, h, rotation): {xywhr}")
                    if xyxyxyxy:
                        print(f"    corners: {xyxyxyxy}")

        if hasattr(result, 'boxes'):
            boxes = result.boxes
            print(f"\nBoxes attribute exists: {boxes is not None}")
            if boxes is not None and len(boxes) > 0:
                print(f"Box detection count: {len(boxes)}")
                for i in range(min(3, len(boxes))):
                    cls_id = int(boxes.cls[i])
                    conf = float(boxes.conf[i])
                    xyxy = boxes.xyxy[i].tolist()
                    print(f"  Box {i}: cls={cls_id}, conf={conf:.3f}, xyxy={xyxy}")


# =============================================================================
# Tests: Annotator Integration
# =============================================================================

class TestAnnotatorIntegration:
    """Tests for annotator's YOLO integration."""

    @pytest.mark.skipif(not YOLO_AVAILABLE or not PYMUPDF_AVAILABLE,
                        reason="ultralytics or pymupdf not installed")
    def test_convert_detections_to_normalized_format(self, loaded_yolo_model, page_11_image):
        """Test converting YOLO detections to normalized YOLO label format."""
        results = loaded_yolo_model(page_11_image, verbose=False, conf=0.1)
        result = results[0]

        img_w, img_h = page_11_image.size
        suggestions = []

        # Handle OBB results
        if hasattr(result, 'obb') and result.obb is not None and len(result.obb) > 0:
            obb = result.obb
            for i in range(len(obb)):
                conf = float(obb.conf[i])
                cls_id = int(obb.cls[i])

                # For OBB, get the bounding box that contains the rotated box
                if hasattr(obb, 'xyxy'):
                    x1, y1, x2, y2 = obb.xyxy[i].tolist()
                elif hasattr(obb, 'xyxyxyxy'):
                    # Get corners and compute bounding box
                    corners = obb.xyxyxyxy[i].tolist()
                    xs = [c[0] for c in corners]
                    ys = [c[1] for c in corners]
                    x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                else:
                    continue

                # Convert to normalized center format
                cx = ((x1 + x2) / 2) / img_w
                cy = ((y1 + y2) / 2) / img_h
                w = (x2 - x1) / img_w
                h = (y2 - y1) / img_h

                suggestions.append((cls_id, cx, cy, w, h, conf))

        # Handle standard box results
        elif result.boxes is not None and len(result.boxes) > 0:
            boxes = result.boxes
            for i in range(len(boxes)):
                conf = float(boxes.conf[i])
                cls_id = int(boxes.cls[i])
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()

                cx = ((x1 + x2) / 2) / img_w
                cy = ((y1 + y2) / 2) / img_h
                w = (x2 - x1) / img_w
                h = (y2 - y1) / img_h

                suggestions.append((cls_id, cx, cy, w, h, conf))

        print(f"\nConverted {len(suggestions)} detections to normalized format:")
        for i, (cls_id, cx, cy, w, h, conf) in enumerate(suggestions[:5]):
            print(f"  {i}: cls={cls_id}, center=({cx:.4f}, {cy:.4f}), size=({w:.4f}, {h:.4f}), conf={conf:.3f}")

        # Verify normalization is correct (values between 0 and 1)
        for cls_id, cx, cy, w, h, conf in suggestions:
            assert 0 <= cx <= 1, f"cx={cx} out of range"
            assert 0 <= cy <= 1, f"cy={cy} out of range"
            assert 0 <= w <= 1, f"w={w} out of range"
            assert 0 <= h <= 1, f"h={h} out of range"


# =============================================================================
# Run tests directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
