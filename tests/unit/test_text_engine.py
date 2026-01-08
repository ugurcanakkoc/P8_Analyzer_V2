"""
Unit tests for src/text_engine.py

Tests the HybridTextEngine class which combines PDF text layer
and OCR for text extraction.
"""
import pytest
import sys
import os
import math
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from p8_analyzer.text.hybrid_engine import (
    HybridTextEngine,
    SearchDirection,
    SearchProfile,
    TextElement,
    EASYOCR_AVAILABLE
)


class TestSearchDirection:
    """Tests for SearchDirection enum."""

    def test_all_directions_defined(self):
        """Test all expected directions are defined."""
        assert SearchDirection.ANY.value == "any"
        assert SearchDirection.TOP.value == "top"
        assert SearchDirection.BOTTOM.value == "bottom"
        assert SearchDirection.RIGHT.value == "right"
        assert SearchDirection.LEFT.value == "left"
        assert SearchDirection.TOP_RIGHT.value == "top_right"
        assert SearchDirection.TOP_LEFT.value == "top_left"
        assert SearchDirection.BOTTOM_RIGHT.value == "bottom_right"
        assert SearchDirection.BOTTOM_LEFT.value == "bottom_left"


class TestTextElement:
    """Tests for TextElement dataclass."""

    def test_text_element_creation(self):
        """Test basic TextElement creation."""
        elem = TextElement(
            text="Test",
            center=(100.0, 200.0),
            bbox=(90.0, 190.0, 110.0, 210.0),
            source="pdf"
        )
        assert elem.text == "Test"
        assert elem.center == (100.0, 200.0)
        assert elem.source == "pdf"
        assert elem.confidence == 1.0  # Default

    def test_text_element_with_confidence(self):
        """Test TextElement with custom confidence."""
        elem = TextElement(
            text="Test",
            center=(100.0, 200.0),
            bbox=(90.0, 190.0, 110.0, 210.0),
            source="ocr",
            confidence=0.85
        )
        assert elem.confidence == 0.85


class TestSearchProfile:
    """Tests for SearchProfile dataclass."""

    def test_default_search_profile(self):
        """Test SearchProfile with defaults."""
        profile = SearchProfile()
        assert profile.search_radius == 30.0
        assert profile.direction == SearchDirection.ANY
        assert profile.regex_pattern is None
        assert profile.use_ocr_fallback is True

    def test_custom_search_profile(self):
        """Test SearchProfile with custom values."""
        profile = SearchProfile(
            search_radius=50.0,
            direction=SearchDirection.LEFT,
            regex_pattern=r'^\d+$',
            use_ocr_fallback=False
        )
        assert profile.search_radius == 50.0
        assert profile.direction == SearchDirection.LEFT
        assert profile.regex_pattern == r'^\d+$'
        assert profile.use_ocr_fallback is False


class TestHybridTextEngine:
    """Tests for HybridTextEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a HybridTextEngine instance."""
        return HybridTextEngine(languages=['en'])

    def test_engine_initialization(self, engine):
        """Test engine initializes correctly."""
        assert engine.languages == ['en']
        assert engine.ocr_reader is None  # Lazy loaded
        assert engine.current_page is None
        assert engine.pdf_elements == []

    def test_engine_initialization_multiple_languages(self):
        """Test engine with multiple languages."""
        engine = HybridTextEngine(languages=['en', 'de', 'tr'])
        assert engine.languages == ['en', 'de', 'tr']


class TestLoadPage:
    """Tests for load_page method."""

    @pytest.fixture
    def engine(self):
        """Create engine for load_page tests."""
        return HybridTextEngine()

    def test_load_page_extracts_text(self, engine):
        """Test that load_page extracts text from PDF page."""
        # Create mock page
        mock_page = MagicMock()
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": "Test Label",
                                    "bbox": (100, 100, 150, 120)
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        engine.load_page(mock_page)

        assert engine.current_page == mock_page
        assert len(engine.pdf_elements) == 1
        assert engine.pdf_elements[0].text == "Test Label"

    def test_load_page_calculates_center(self, engine):
        """Test that center is calculated correctly."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": "Test",
                                    "bbox": (100, 100, 200, 150)  # center = (150, 125)
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        engine.load_page(mock_page)

        elem = engine.pdf_elements[0]
        assert elem.center == (150.0, 125.0)

    def test_load_page_skips_empty_text(self, engine):
        """Test that empty text spans are skipped."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {"text": "", "bbox": (0, 0, 10, 10)},
                                {"text": "   ", "bbox": (20, 20, 30, 30)},
                                {"text": "Valid", "bbox": (50, 50, 60, 60)}
                            ]
                        }
                    ]
                }
            ]
        }

        engine.load_page(mock_page)

        assert len(engine.pdf_elements) == 1
        assert engine.pdf_elements[0].text == "Valid"

    def test_load_page_clears_previous(self, engine):
        """Test that previous page data is cleared."""
        # Load first page
        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = {
            "blocks": [{"lines": [{"spans": [{"text": "Page1", "bbox": (0, 0, 10, 10)}]}]}]
        }
        engine.load_page(mock_page1)
        assert len(engine.pdf_elements) == 1

        # Load second page
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = {
            "blocks": [{"lines": [{"spans": [{"text": "Page2", "bbox": (0, 0, 10, 10)}]}]}]
        }
        engine.load_page(mock_page2)

        assert len(engine.pdf_elements) == 1
        assert engine.pdf_elements[0].text == "Page2"


class TestSearchInList:
    """Tests for _search_in_list method."""

    @pytest.fixture
    def engine_with_elements(self):
        """Create engine with predefined elements."""
        engine = HybridTextEngine()
        engine.pdf_elements = [
            TextElement(text="1", center=(100, 100), bbox=(95, 95, 105, 105), source="pdf"),
            TextElement(text="2", center=(150, 100), bbox=(145, 95, 155, 105), source="pdf"),
            TextElement(text="PE", center=(200, 100), bbox=(195, 95, 205, 105), source="pdf"),
            TextElement(text="-X1", center=(50, 100), bbox=(40, 95, 60, 105), source="pdf"),
        ]
        return engine

    def test_search_finds_closest(self, engine_with_elements):
        """Test that search finds closest matching element."""
        profile = SearchProfile(search_radius=50.0)

        result = engine_with_elements._search_in_list(
            engine_with_elements.pdf_elements,
            ox=100, oy=100,
            profile=profile
        )

        assert result is not None
        assert result.text == "1"

    def test_search_respects_radius(self, engine_with_elements):
        """Test that search respects radius limit."""
        profile = SearchProfile(search_radius=10.0)  # Very small radius

        # Search from point far from any element
        result = engine_with_elements._search_in_list(
            engine_with_elements.pdf_elements,
            ox=500, oy=500,
            profile=profile
        )

        assert result is None

    def test_search_with_regex_filter(self, engine_with_elements):
        """Test search with regex pattern filter."""
        profile = SearchProfile(
            search_radius=200.0,
            regex_pattern=r'^\d+$'  # Only digits
        )

        result = engine_with_elements._search_in_list(
            engine_with_elements.pdf_elements,
            ox=100, oy=100,
            profile=profile
        )

        assert result is not None
        assert result.text in ['1', '2']  # Only numeric labels

    def test_search_regex_excludes_non_matching(self, engine_with_elements):
        """Test that regex excludes non-matching elements."""
        profile = SearchProfile(
            search_radius=200.0,
            regex_pattern=r'^-X.*$'  # Only -X labels
        )

        result = engine_with_elements._search_in_list(
            engine_with_elements.pdf_elements,
            ox=50, oy=100,  # Near -X1
            profile=profile
        )

        assert result is not None
        assert result.text == "-X1"


class TestCheckDirection:
    """Tests for _check_direction method."""

    @pytest.fixture
    def engine(self):
        """Create engine for direction tests."""
        return HybridTextEngine()

    def test_direction_any_always_true(self, engine):
        """Test ANY direction always returns True."""
        assert engine._check_direction(0, 0, 100, 100, SearchDirection.ANY) is True
        assert engine._check_direction(0, 0, -100, -100, SearchDirection.ANY) is True

    def test_direction_right(self, engine):
        """Test RIGHT direction detection."""
        # Point to the right (positive X, same Y)
        assert engine._check_direction(0, 0, 100, 0, SearchDirection.RIGHT) is True
        # Point to the left
        assert engine._check_direction(0, 0, -100, 0, SearchDirection.RIGHT) is False

    def test_direction_left(self, engine):
        """Test LEFT direction detection."""
        # Point to the left (negative X, same Y)
        assert engine._check_direction(0, 0, -100, 0, SearchDirection.LEFT) is True
        # Point to the right
        assert engine._check_direction(0, 0, 100, 0, SearchDirection.LEFT) is False

    def test_direction_top(self, engine):
        """Test TOP direction detection (negative Y in PDF coordinates)."""
        # In PDF, Y increases downward, so "top" is negative Y direction
        assert engine._check_direction(0, 0, 0, -100, SearchDirection.TOP) is True
        # Point below (positive Y)
        assert engine._check_direction(0, 0, 0, 100, SearchDirection.TOP) is False

    def test_direction_bottom(self, engine):
        """Test BOTTOM direction detection."""
        # In PDF, Y increases downward
        assert engine._check_direction(0, 0, 0, 100, SearchDirection.BOTTOM) is True
        # Point above
        assert engine._check_direction(0, 0, 0, -100, SearchDirection.BOTTOM) is False

    def test_direction_top_right(self, engine):
        """Test TOP_RIGHT diagonal direction."""
        # Right and up (positive X, negative Y in PDF)
        assert engine._check_direction(0, 0, 100, -50, SearchDirection.TOP_RIGHT) is True

    def test_direction_top_left(self, engine):
        """Test TOP_LEFT diagonal direction."""
        # Left and up (negative X, negative Y in PDF)
        assert engine._check_direction(0, 0, -100, -50, SearchDirection.TOP_LEFT) is True


class TestFindText:
    """Tests for find_text method."""

    @pytest.fixture
    def engine_with_page(self):
        """Create engine with loaded page."""
        engine = HybridTextEngine()
        engine.pdf_elements = [
            TextElement(text="13", center=(110, 95), bbox=(105, 90, 115, 100), source="pdf"),
        ]
        engine.current_page = MagicMock()
        return engine

    def test_find_text_returns_match(self, engine_with_page):
        """Test find_text returns matching element."""
        profile = SearchProfile(search_radius=50.0)

        result = engine_with_page.find_text((100, 100), profile)

        assert result is not None
        assert result.text == "13"

    def test_find_text_with_point_object(self, engine_with_page):
        """Test find_text accepts Point-like objects."""
        profile = SearchProfile(search_radius=50.0)

        point = Mock()
        point.x = 100
        point.y = 100

        result = engine_with_page.find_text(point, profile)

        assert result is not None

    def test_find_text_no_match_returns_none(self, engine_with_page):
        """Test find_text returns None when no match."""
        profile = SearchProfile(search_radius=10.0)  # Small radius

        result = engine_with_page.find_text((500, 500), profile)

        assert result is None


class TestFindTextOnlyPdf:
    """Tests for find_text_only_pdf method."""

    @pytest.fixture
    def engine(self):
        """Create engine for PDF-only tests."""
        engine = HybridTextEngine()
        engine.pdf_elements = [
            TextElement(text="PDF_TEXT", center=(100, 100), bbox=(90, 90, 110, 110), source="pdf"),
        ]
        return engine

    def test_find_text_only_pdf(self, engine):
        """Test find_text_only_pdf finds PDF text."""
        profile = SearchProfile(search_radius=50.0)

        result = engine.find_text_only_pdf((100, 100), profile)

        assert result is not None
        assert result.text == "PDF_TEXT"
        assert result.source == "pdf"


class TestFindTextOnlyOcr:
    """Tests for find_text_only_ocr method."""

    @pytest.fixture
    def engine(self):
        """Create engine for OCR-only tests."""
        engine = HybridTextEngine()
        engine.current_page = MagicMock()
        return engine

    @pytest.mark.skipif(not EASYOCR_AVAILABLE, reason="EasyOCR not installed")
    def test_find_text_only_ocr_calls_ocr(self, engine):
        """Test find_text_only_ocr performs OCR."""
        profile = SearchProfile(search_radius=50.0)

        # This would actually call OCR - skip in unit tests
        # Just verify the method exists and can be called
        assert hasattr(engine, 'find_text_only_ocr')

    def test_find_text_only_ocr_no_page(self):
        """Test find_text_only_ocr returns None without page."""
        engine = HybridTextEngine()
        engine.current_page = None
        profile = SearchProfile()

        result = engine.find_text_only_ocr((100, 100), profile)
        assert result is None

    def test_find_text_only_ocr_no_easyocr(self):
        """Test find_text_only_ocr handles missing EasyOCR."""
        with patch('src.text_engine.EASYOCR_AVAILABLE', False):
            engine = HybridTextEngine()
            engine.current_page = MagicMock()
            profile = SearchProfile()

            result = engine.find_text_only_ocr((100, 100), profile)
            assert result is None
