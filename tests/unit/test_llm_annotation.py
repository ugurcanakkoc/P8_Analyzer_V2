"""
Unit tests for LLM Annotation Helper.

Tests the LLM-based component detection for electrical schematics.
"""

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "YOLO" / "scripts"))


class TestLLMAnnotationHelper:
    """Tests for the LLM annotation helper module."""

    @pytest.fixture
    def sample_image_path(self):
        """Path to sample schematic image."""
        return PROJECT_ROOT / "YOLO" / "data" / "classification_output" / "ornek_20260107_163847" / "schematic" / "ornek_page0011.png"

    @pytest.fixture
    def mock_openai_response(self):
        """Mock OpenAI API response."""
        return """```json
[
  {"class_name": "Terminal", "x_center": 4.7, "y_center": 8.0, "width": 1.5, "height": 2.0, "confidence": 0.9, "label": "-X1:U", "reasoning": "Circle on terminal strip"},
  {"class_name": "Terminal", "x_center": 5.7, "y_center": 8.0, "width": 1.5, "height": 2.0, "confidence": 0.9, "label": "-X1:V", "reasoning": "Circle on terminal strip"},
  {"class_name": "PLC_Module", "x_center": 50.0, "y_center": 25.0, "width": 15.0, "height": 10.0, "confidence": 0.95, "label": "-1G35", "reasoning": "SITOP power supply"}
]
```"""

    def test_import_module(self):
        """Module should be importable."""
        from llm_annotation_helper import LLMAnnotationHelper, COMPONENT_CLASSES
        assert LLMAnnotationHelper is not None
        assert len(COMPONENT_CLASSES) == 3  # POC: PLC_Module, Terminal, Contactor

    def test_component_classes_defined(self):
        """Component classes should be properly defined."""
        from llm_annotation_helper import COMPONENT_CLASSES, CLASS_NAME_TO_ID

        assert "PLC_Module" in CLASS_NAME_TO_ID
        assert "Terminal" in CLASS_NAME_TO_ID
        assert "Contactor" in CLASS_NAME_TO_ID

        assert CLASS_NAME_TO_ID["PLC_Module"] == 0
        assert CLASS_NAME_TO_ID["Terminal"] == 1
        assert CLASS_NAME_TO_ID["Contactor"] == 2

    def test_parse_llm_response(self, mock_openai_response):
        """Response parser should extract valid components."""
        from llm_annotation_helper import LLMAnnotationHelper

        # Create helper without API (we'll test parsing only)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            helper = LLMAnnotationHelper(provider="openai")

        components = helper._parse_llm_response(mock_openai_response)

        assert len(components) == 3
        assert components[0]['class_name'] == "Terminal"
        assert components[0]['label'] == "-X1:U"
        assert components[2]['class_name'] == "PLC_Module"
        assert components[2]['label'] == "-1G35"

        # Check normalization (percentages to 0-1)
        assert 0 <= components[0]['x_center'] <= 1
        assert 0 <= components[0]['y_center'] <= 1

    def test_parse_invalid_class_ignored(self):
        """Parser should ignore unknown classes."""
        from llm_annotation_helper import LLMAnnotationHelper

        invalid_response = """[
          {"class_name": "InvalidClass", "x_center": 50.0, "y_center": 50.0, "width": 10.0, "height": 10.0, "confidence": 0.9},
          {"class_name": "Terminal", "x_center": 30.0, "y_center": 30.0, "width": 5.0, "height": 5.0, "confidence": 0.8}
        ]"""

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            helper = LLMAnnotationHelper(provider="openai")

        components = helper._parse_llm_response(invalid_response)

        assert len(components) == 1
        assert components[0]['class_name'] == "Terminal"

    def test_parse_out_of_bounds_ignored(self):
        """Parser should ignore components with invalid coordinates."""
        from llm_annotation_helper import LLMAnnotationHelper

        invalid_response = """[
          {"class_name": "Terminal", "x_center": 150.0, "y_center": 50.0, "width": 5.0, "height": 5.0, "confidence": 0.9},
          {"class_name": "Terminal", "x_center": 30.0, "y_center": 30.0, "width": 5.0, "height": 5.0, "confidence": 0.8}
        ]"""

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            helper = LLMAnnotationHelper(provider="openai")

        components = helper._parse_llm_response(invalid_response)

        assert len(components) == 1
        assert components[0]['x_center'] == 0.30

    def test_suggestions_to_yolo_format(self, mock_openai_response):
        """Conversion to YOLO format should work."""
        from llm_annotation_helper import LLMAnnotationHelper, AnnotationSuggestions

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            helper = LLMAnnotationHelper(provider="openai")

        components = helper._parse_llm_response(mock_openai_response)

        suggestions = AnnotationSuggestions(
            image_path="test.png",
            image_width=2337,
            image_height=1688,
            timestamp="2026-01-07",
            model_used="gpt-4o",
            suggestions=components,
            raw_response=mock_openai_response
        )

        yolo_labels = helper.suggestions_to_yolo(suggestions)

        assert len(yolo_labels) == 3
        # Format: class_id x_center y_center width height
        parts = yolo_labels[0].split()
        assert len(parts) == 5
        assert parts[0] == "1"  # Terminal class_id

    def test_suggestions_to_obb_format(self, mock_openai_response):
        """Conversion to OBB format should work."""
        from llm_annotation_helper import LLMAnnotationHelper, AnnotationSuggestions

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            helper = LLMAnnotationHelper(provider="openai")

        components = helper._parse_llm_response(mock_openai_response)

        suggestions = AnnotationSuggestions(
            image_path="test.png",
            image_width=2337,
            image_height=1688,
            timestamp="2026-01-07",
            model_used="gpt-4o",
            suggestions=components,
            raw_response=mock_openai_response
        )

        obb_labels = helper.suggestions_to_obb(suggestions)

        assert len(obb_labels) == 3
        # Format: class_id x1 y1 x2 y2 x3 y3 x4 y4
        parts = obb_labels[0].split()
        assert len(parts) == 9
        assert parts[0] == "1"  # Terminal class_id


class TestLLMAnnotationVisualization:
    """Tests for visualization functionality."""

    @pytest.fixture
    def sample_image_path(self):
        """Path to sample schematic image."""
        path = PROJECT_ROOT / "YOLO" / "data" / "classification_output" / "ornek_20260107_163847" / "schematic" / "ornek_page0011.png"
        if not path.exists():
            pytest.skip("Sample image not found")
        return path

    def test_visualization_creates_file(self, sample_image_path, tmp_path):
        """Visualization should create an annotated image file."""
        from llm_annotation_helper import LLMAnnotationHelper, AnnotationSuggestions

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            helper = LLMAnnotationHelper(provider="openai")

        # Create mock suggestions
        suggestions = AnnotationSuggestions(
            image_path=str(sample_image_path),
            image_width=2337,
            image_height=1688,
            timestamp="2026-01-07",
            model_used="gpt-4o",
            suggestions=[
                {
                    'class_id': 1,
                    'class_name': 'Terminal',
                    'x_center': 0.1,
                    'y_center': 0.1,
                    'width': 0.02,
                    'height': 0.02,
                    'confidence': 0.9,
                    'label': '-X1:1',
                    'reasoning': 'Test terminal'
                },
                {
                    'class_id': 0,
                    'class_name': 'PLC_Module',
                    'x_center': 0.5,
                    'y_center': 0.3,
                    'width': 0.15,
                    'height': 0.1,
                    'confidence': 0.95,
                    'label': '-1G35',
                    'reasoning': 'Test module'
                }
            ],
            raw_response=""
        )

        output_path = tmp_path / "annotated.png"
        result_path = helper.visualize_suggestions(suggestions, str(output_path))

        assert Path(result_path).exists()
        assert Path(result_path).stat().st_size > 0


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - skipping live API test"
)
class TestLLMAnnotationLive:
    """Live integration tests (require API key)."""

    @pytest.fixture
    def sample_image_path(self):
        """Path to sample schematic image."""
        path = PROJECT_ROOT / "YOLO" / "data" / "classification_output" / "ornek_20260107_163847" / "schematic" / "ornek_page0011.png"
        if not path.exists():
            pytest.skip("Sample image not found")
        return path

    def test_live_analysis(self, sample_image_path, tmp_path):
        """Live test: analyze sample image with real API call."""
        from llm_annotation_helper import LLMAnnotationHelper

        helper = LLMAnnotationHelper(provider="openai")
        suggestions = helper.analyze_image(str(sample_image_path))

        assert suggestions is not None
        assert len(suggestions.suggestions) > 0

        # Should find some components
        class_names = [s['class_name'] for s in suggestions.suggestions]
        assert any(name in class_names for name in ['Terminal', 'PLC_Module', 'Contactor'])

        # Save visualization
        output_path = tmp_path / "live_test_annotated.png"
        viz_path = helper.visualize_suggestions(suggestions, str(output_path))
        assert Path(viz_path).exists()

        print(f"\n[TEST] Found {len(suggestions.suggestions)} components:")
        for s in suggestions.suggestions:
            print(f"  - {s['class_name']} [{s.get('label', '')}]: conf={s['confidence']:.2f}")
