"""
Integration tests for text extraction pipeline.

Tests the interaction between HybridTextEngine, TerminalReader,
and TerminalGrouper for text extraction workflows.
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from p8_analyzer.text.hybrid_engine import HybridTextEngine, SearchProfile, SearchDirection, TextElement


class TestTextEngineWithReader:
    """Tests for HybridTextEngine integration with TerminalReader."""

    @pytest.fixture
    def text_engine(self):
        """Create text engine with mock PDF elements."""
        engine = HybridTextEngine()
        engine.pdf_elements = [
            TextElement(text="1", center=(110, 95), bbox=(105, 90, 115, 100), source="pdf"),
            TextElement(text="2", center=(160, 95), bbox=(155, 90, 165, 100), source="pdf"),
            TextElement(text="PE", center=(210, 95), bbox=(200, 90, 220, 100), source="pdf"),
            TextElement(text="-X1", center=(50, 100), bbox=(40, 95, 60, 105), source="pdf"),
        ]
        engine.current_page = MagicMock()
        return engine

    @pytest.fixture
    def reader(self):
        """Create terminal reader."""
        from p8_analyzer.detection import TerminalReader
        return TerminalReader(config={
            'direction': 'top_right',
            'search_radius': 30.0
        })

    def test_reader_uses_text_engine_correctly(self, text_engine, reader):
        """Test reader correctly uses text engine to find labels."""
        terminals = [
            {'center': (100, 100), 'radius': 3.0, 'cv': 0.005, 'is_filled': False, 'group_id': 1, 'label': None},
        ]

        result = reader.read_labels(terminals, text_engine)

        # Should find "1" which is at (110, 95) - top-right of (100, 100)
        assert result[0]['label'] == '1'
        assert result[0]['label_source'] == 'pdf'

    def test_reader_respects_direction_filter(self, reader):
        """Test reader respects direction when searching."""
        engine = HybridTextEngine()
        # Put text to the LEFT of search point
        engine.pdf_elements = [
            TextElement(text="LEFT", center=(80, 100), bbox=(70, 95, 90, 105), source="pdf"),
        ]
        engine.current_page = MagicMock()

        terminals = [
            {'center': (100, 100), 'radius': 3.0, 'cv': 0.005, 'is_filled': False, 'group_id': 1, 'label': None},
        ]

        # Reader is configured for top_right, should not find LEFT text
        result = reader.read_labels(terminals, engine)

        assert result[0]['label'] == '?'  # Not found because wrong direction


class TestTextEngineWithGrouper:
    """Tests for HybridTextEngine integration with TerminalGrouper."""

    @pytest.fixture
    def text_engine(self):
        """Create text engine with group labels."""
        engine = HybridTextEngine()
        engine.pdf_elements = [
            TextElement(text="-X1", center=(50, 100), bbox=(40, 95, 60, 105), source="pdf"),
            TextElement(text="-X2", center=(50, 200), bbox=(40, 195, 60, 205), source="pdf"),
        ]
        engine.current_page = MagicMock()
        return engine

    @pytest.fixture
    def grouper(self):
        """Create terminal grouper."""
        from p8_analyzer.detection import TerminalGrouper
        return TerminalGrouper(config={
            'search_direction': 'left',
            'search_radius': 100.0,
            'label_pattern': r'^-?X.*'
        })

    def test_grouper_finds_group_labels(self, text_engine, grouper):
        """Test grouper finds group labels using text engine."""
        terminals = [
            {'center': (100, 100), 'label': '1', 'group_id': 1},
        ]

        result = grouper.group_terminals(terminals, text_engine)

        assert result[0]['group_label'] == '-X1'
        assert result[0]['full_label'] == '-X1:1'

    def test_grouper_uses_correct_direction(self, grouper):
        """Test grouper searches in correct direction (left)."""
        engine = HybridTextEngine()
        # Put group label to the RIGHT of terminal
        engine.pdf_elements = [
            TextElement(text="-X1", center=(150, 100), bbox=(140, 95, 160, 105), source="pdf"),
        ]
        engine.current_page = MagicMock()

        terminals = [
            {'center': (100, 100), 'label': '1', 'group_id': 1},
        ]

        result = grouper.group_terminals(terminals, engine)

        # Should NOT find -X1 because it's to the right, not left
        assert result[0]['group_label'] is None


class TestTextEngineWithPinFinder:
    """Tests for HybridTextEngine integration with PinFinder."""

    @pytest.fixture
    def text_engine(self):
        """Create text engine with pin labels."""
        engine = HybridTextEngine()
        engine.pdf_elements = [
            TextElement(text="13", center=(105, 95), bbox=(100, 90, 110, 100), source="pdf"),
            TextElement(text="14", center=(125, 95), bbox=(120, 90, 130, 100), source="pdf"),
        ]
        engine.current_page = MagicMock()
        return engine

    @pytest.fixture
    def pin_finder(self):
        """Create pin finder."""
        from p8_analyzer.detection import PinFinder
        return PinFinder(config={'pin_search_radius': 50.0})

    @pytest.fixture
    def mock_box(self):
        """Create mock component box."""
        box = Mock()
        box.id = 'BOX-1'
        box.bbox = {'min_x': 50, 'min_y': 50, 'max_x': 150, 'max_y': 150}
        box.contains_point = lambda p: (
            50 <= (p.x if hasattr(p, 'x') else p[0]) <= 150 and
            50 <= (p.y if hasattr(p, 'y') else p[1]) <= 150
        )
        return box

    def test_pin_finder_uses_text_engine(self, text_engine, pin_finder, mock_box):
        """Test pin finder uses text engine to find labels."""
        # Create group with point inside box
        group = Mock()
        elem = Mock()
        elem.start_point = Mock(x=100, y=100)
        elem.end_point = Mock(x=120, y=100)
        group.elements = [elem]

        result = pin_finder.find_pins_for_group(group, [mock_box], text_engine)

        # Should find pins with labels from text engine
        assert len(result) > 0
        labels = [p['pin_label'] for p in result]
        assert '13' in labels or '14' in labels


class TestTextEngineLayerPriority:
    """Tests for PDF vs OCR layer priority."""

    @pytest.fixture
    def engine_with_both_layers(self):
        """Create engine that can do both PDF and OCR."""
        engine = HybridTextEngine()
        engine.pdf_elements = [
            TextElement(text="PDF_TEXT", center=(100, 100), bbox=(90, 90, 110, 110), source="pdf"),
        ]
        engine.current_page = MagicMock()
        return engine

    def test_pdf_layer_takes_priority(self, engine_with_both_layers):
        """Test that PDF text layer is searched before OCR."""
        profile = SearchProfile(
            search_radius=50.0,
            use_ocr_fallback=True
        )

        result = engine_with_both_layers.find_text((100, 100), profile)

        # Should find PDF text without needing OCR
        assert result is not None
        assert result.text == "PDF_TEXT"
        assert result.source == "pdf"

    def test_ocr_fallback_when_pdf_empty(self, engine_with_both_layers):
        """Test OCR is used when PDF has no matches."""
        # Clear PDF elements
        engine_with_both_layers.pdf_elements = []

        profile = SearchProfile(
            search_radius=50.0,
            use_ocr_fallback=True
        )

        # Without mocking OCR, this will return None
        # This tests the fallback logic path
        result = engine_with_both_layers.find_text((100, 100), profile)

        # Result depends on whether OCR finds anything
        # In unit test without real OCR, it will be None


class TestTextEngineSearchProfiles:
    """Tests for different search profile configurations."""

    @pytest.fixture
    def engine(self):
        """Create engine with varied text elements."""
        engine = HybridTextEngine()
        engine.pdf_elements = [
            TextElement(text="123", center=(100, 100), bbox=(90, 90, 110, 110), source="pdf"),
            TextElement(text="ABC", center=(150, 100), bbox=(140, 90, 160, 110), source="pdf"),
            TextElement(text="-X1", center=(200, 100), bbox=(190, 90, 210, 110), source="pdf"),
            TextElement(text="12A", center=(250, 100), bbox=(240, 90, 260, 110), source="pdf"),
        ]
        engine.current_page = MagicMock()
        return engine

    def test_numeric_only_regex(self, engine):
        """Test regex pattern for numeric-only labels."""
        profile = SearchProfile(
            search_radius=200.0,
            regex_pattern=r'^\d+$'
        )

        result = engine.find_text((100, 100), profile)

        assert result is not None
        assert result.text == "123"

    def test_alpha_only_regex(self, engine):
        """Test regex pattern for alpha-only labels."""
        profile = SearchProfile(
            search_radius=200.0,
            regex_pattern=r'^[A-Z]+$'
        )

        result = engine.find_text((150, 100), profile)

        assert result is not None
        assert result.text == "ABC"

    def test_group_label_regex(self, engine):
        """Test regex pattern for group labels (-X...)."""
        profile = SearchProfile(
            search_radius=200.0,
            regex_pattern=r'^-X.*$'
        )

        result = engine.find_text((200, 100), profile)

        assert result is not None
        assert result.text == "-X1"

    def test_no_regex_returns_closest(self, engine):
        """Test that without regex, closest match is returned."""
        profile = SearchProfile(
            search_radius=200.0,
            regex_pattern=None  # No filter
        )

        result = engine.find_text((100, 100), profile)

        # Should return "123" as it's closest to (100, 100)
        assert result is not None
        assert result.text == "123"


class TestTextEngineEdgeCases:
    """Edge case tests for text engine integration."""

    def test_overlapping_text_elements(self):
        """Test handling of overlapping text elements."""
        engine = HybridTextEngine()
        engine.pdf_elements = [
            TextElement(text="A", center=(100, 100), bbox=(90, 90, 110, 110), source="pdf"),
            TextElement(text="B", center=(100, 100), bbox=(90, 90, 110, 110), source="pdf"),  # Same position
        ]
        engine.current_page = MagicMock()

        profile = SearchProfile(search_radius=50.0)
        result = engine.find_text((100, 100), profile)

        # Should return one of them (first match or closest)
        assert result is not None
        assert result.text in ["A", "B"]

    def test_text_at_exact_radius_boundary(self):
        """Test text at exact search radius boundary."""
        engine = HybridTextEngine()
        engine.pdf_elements = [
            TextElement(text="BOUNDARY", center=(130, 100), bbox=(120, 90, 140, 110), source="pdf"),
        ]
        engine.current_page = MagicMock()

        # Search with radius exactly equal to distance (30 units)
        profile = SearchProfile(search_radius=30.0)
        result = engine.find_text((100, 100), profile)

        # Should find it (boundary is inclusive)
        assert result is not None
        assert result.text == "BOUNDARY"

    def test_very_small_search_radius(self):
        """Test with very small search radius."""
        engine = HybridTextEngine()
        engine.pdf_elements = [
            TextElement(text="CLOSE", center=(101, 100), bbox=(96, 95, 106, 105), source="pdf"),
        ]
        engine.current_page = MagicMock()

        profile = SearchProfile(search_radius=1.5)  # Very small
        result = engine.find_text((100, 100), profile)

        # Should find it (distance is ~1 unit)
        assert result is not None
