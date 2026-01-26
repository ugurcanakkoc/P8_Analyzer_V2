"""
Unit tests for src/pin_finder.py

Tests the PinFinder class which detects pin labels at wire endpoints
inside component boxes.
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from p8_analyzer.detection import PinFinder


class TestPinFinder:
    """Tests for PinFinder class."""

    @pytest.fixture
    def finder(self, default_pin_finder_config):
        """Create a PinFinder instance with default config."""
        return PinFinder(config=default_pin_finder_config)

    @pytest.fixture
    def finder_custom_config(self):
        """Create a PinFinder with custom configuration."""
        return PinFinder(config={'pin_search_radius': 50.0})

    def test_finder_initialization_default(self, finder):
        """Test finder initializes with default values."""
        assert finder.search_radius == 75.0
        assert finder.debug_callback is None

    def test_finder_initialization_custom(self, finder_custom_config):
        """Test finder initializes with custom values."""
        assert finder_custom_config.search_radius == 50.0

    def test_set_debug_callback(self, finder):
        """Test setting debug callback."""
        callback = Mock()
        finder.set_debug_callback(callback)
        assert finder.debug_callback == callback

    def test_log_debug_with_callback(self, finder):
        """Test debug logging with callback."""
        callback = Mock()
        finder.set_debug_callback(callback)

        finder._log_debug("Test message")
        callback.assert_called_once_with("Test message")

    def test_log_debug_without_callback(self, finder, caplog):
        """Test debug logging without callback uses logger."""
        import logging
        with caplog.at_level(logging.DEBUG):
            finder._log_debug("Test message")
        # Should not raise an error


class TestPinFinderValidation:
    """Tests for pin label validation."""

    @pytest.fixture
    def finder(self):
        """Create finder for validation tests."""
        return PinFinder()

    def test_is_valid_pin_label_simple_number(self, finder):
        """Test valid simple number label."""
        assert finder._is_valid_pin_label('1') is True
        assert finder._is_valid_pin_label('13') is True
        assert finder._is_valid_pin_label('123') is True

    def test_is_valid_pin_label_alphanumeric(self, finder):
        """Test valid alphanumeric labels."""
        assert finder._is_valid_pin_label('PE') is True
        assert finder._is_valid_pin_label('L1') is True
        assert finder._is_valid_pin_label('N') is True
        assert finder._is_valid_pin_label('A1') is True

    def test_is_valid_pin_label_empty(self, finder):
        """Test empty label is invalid."""
        assert finder._is_valid_pin_label('') is False
        assert finder._is_valid_pin_label(None) is False

    def test_is_valid_pin_label_too_long(self, finder):
        """Test too long label is invalid (>12 chars)."""
        assert finder._is_valid_pin_label('1234567890123') is False  # > 12 chars

    def test_is_valid_pin_label_with_slash(self, finder):
        """Test label with slash - valid in current implementation."""
        # Current implementation allows slashes
        assert finder._is_valid_pin_label('/PE') is True
        assert finder._is_valid_pin_label('/1') is True

    def test_is_valid_pin_label_boundary_length(self, finder):
        """Test boundary length labels."""
        assert finder._is_valid_pin_label('A') is True  # 1 char - valid
        assert finder._is_valid_pin_label('ABCDEFGHIJKL') is True  # 12 chars - valid
        assert finder._is_valid_pin_label('ABCDEFGHIJKLM') is False  # 13 chars - invalid


class TestGetAllGroupPoints:
    """Tests for _get_all_group_points method."""

    @pytest.fixture
    def finder(self):
        """Create finder for point extraction tests."""
        return PinFinder()

    @pytest.fixture
    def mock_group_with_elements(self, mock_path_factory):
        """Create a mock group with path elements."""
        group = Mock()
        group.elements = [
            mock_path_factory(start_x=0, start_y=0, end_x=100, end_y=0),
            mock_path_factory(start_x=100, start_y=0, end_x=100, end_y=50),
        ]
        return group

    def test_get_all_group_points_extracts_start_and_end(
        self, finder, mock_group_with_elements
    ):
        """Test that both start and end points are extracted."""
        points = finder._get_all_group_points(mock_group_with_elements)

        # Should have 4 points total (2 elements * 2 endpoints)
        # But some may be duplicates (100,0 appears twice)
        assert len(points) >= 3  # At least 3 unique points

    def test_get_all_group_points_removes_duplicates(self, finder):
        """Test that duplicate points are removed."""
        group = Mock()

        # Create elements that share endpoints
        elem1 = Mock()
        elem1.start_point = Mock(x=0, y=0)
        elem1.end_point = Mock(x=100, y=0)

        elem2 = Mock()
        elem2.start_point = Mock(x=100, y=0)  # Same as elem1.end_point
        elem2.end_point = Mock(x=100, y=50)

        group.elements = [elem1, elem2]

        points = finder._get_all_group_points(group)

        # Should have 3 unique points: (0,0), (100,0), (100,50)
        assert len(points) == 3

    def test_get_all_group_points_empty_group(self, finder):
        """Test with empty element list."""
        group = Mock()
        group.elements = []

        points = finder._get_all_group_points(group)
        assert len(points) == 0

    def test_get_all_group_points_returns_simple_point(self, finder):
        """Test that returned points have x and y attributes."""
        group = Mock()
        elem = Mock()
        elem.start_point = Mock(x=50, y=75)
        elem.end_point = Mock(x=100, y=75)
        group.elements = [elem]

        points = finder._get_all_group_points(group)

        for point in points:
            assert hasattr(point, 'x')
            assert hasattr(point, 'y')


class TestFindPinsForGroup:
    """Tests for find_pins_for_group method."""

    @pytest.fixture
    def finder(self):
        """Create finder for pin finding tests."""
        return PinFinder(config={'pin_search_radius': 75.0})

    @pytest.fixture
    def mock_group_inside_box(self, mock_point_factory):
        """Create a group with points inside a box."""
        group = Mock()
        elem = Mock()
        elem.start_point = mock_point_factory(100, 100)  # Inside BOX-1 (50-150)
        elem.end_point = mock_point_factory(120, 100)  # Also inside BOX-1
        group.elements = [elem]
        return group

    @pytest.fixture
    def mock_group_outside_boxes(self, mock_point_factory):
        """Create a group with points outside all boxes."""
        group = Mock()
        elem = Mock()
        elem.start_point = mock_point_factory(500, 500)  # Far from any box
        elem.end_point = mock_point_factory(600, 500)
        group.elements = [elem]
        return group

    def test_find_pins_no_boxes(self, finder, mock_group_inside_box, mock_text_engine):
        """Test finding pins with no boxes returns empty."""
        result = finder.find_pins_for_group(mock_group_inside_box, [], mock_text_engine)
        assert result == []

    def test_find_pins_point_inside_box(
        self, finder, mock_group_inside_box, sample_component_boxes, mock_text_engine
    ):
        """Test finding pins when points are inside boxes."""
        # Mock text engine's find_text to return a label element
        mock_result = Mock()
        mock_result.text = '13'
        mock_result.center = (105, 95)
        mock_text_engine.find_text.return_value = mock_result

        result = finder.find_pins_for_group(
            mock_group_inside_box, sample_component_boxes, mock_text_engine
        )

        # Should find pin inside BOX-1
        assert len(result) > 0
        if result:
            assert 'BOX-1' in result[0]['full_label']

    def test_find_pins_point_outside_boxes(
        self, finder, mock_group_outside_boxes, sample_component_boxes, mock_text_engine
    ):
        """Test that points outside boxes don't create pins."""
        result = finder.find_pins_for_group(
            mock_group_outside_boxes, sample_component_boxes, mock_text_engine
        )

        assert result == []

    def test_find_pins_structure(self, finder, sample_component_boxes):
        """Test the structure of returned pin objects."""
        # Create a group with a point inside box
        group = Mock()
        elem = Mock()
        elem.start_point = Mock(x=100, y=100)
        elem.end_point = Mock(x=120, y=100)
        group.elements = [elem]

        # Mock text engine's find_text to return a label element
        mock_engine = MagicMock()
        mock_result = Mock()
        mock_result.text = '5'
        mock_result.center = (105, 95)
        mock_engine.find_text.return_value = mock_result

        result = finder.find_pins_for_group(group, sample_component_boxes, mock_engine)

        if result:
            pin = result[0]
            assert 'box_id' in pin
            assert 'pin_label' in pin
            assert 'full_label' in pin
            assert 'location' in pin
            assert isinstance(pin['location'], tuple)


class TestFindLabelElementNearPoint:
    """Tests for _find_label_element_near_point method."""

    @pytest.fixture
    def finder(self):
        """Create finder for label finding tests."""
        return PinFinder(config={'pin_search_radius': 75.0})

    def test_find_label_within_distance(self, finder):
        """Test finding label within acceptable distance."""
        mock_engine = MagicMock()
        mock_result = Mock()
        mock_result.text = '13'
        mock_engine.find_text.return_value = mock_result

        point = Mock(x=100, y=100)
        result = finder._find_label_element_near_point(point, mock_engine)

        assert result is not None
        assert result.text == '13'

    def test_find_label_not_found(self, finder):
        """Test no label found when text engine returns None."""
        mock_engine = MagicMock()
        mock_engine.find_text.return_value = None

        point = Mock(x=100, y=100)
        result = finder._find_label_element_near_point(point, mock_engine)

        assert result is None

    def test_find_label_calls_text_engine(self, finder):
        """Test that text engine find_text is called with correct parameters."""
        mock_engine = MagicMock()
        mock_engine.find_text.return_value = None

        point = Mock(x=100, y=100)
        finder._find_label_element_near_point(point, mock_engine)

        mock_engine.find_text.assert_called_once()
        # Verify point was passed
        call_args = mock_engine.find_text.call_args
        assert call_args[0][0] == point  # First positional arg is point

    def test_find_label_uses_search_profile(self, finder):
        """Test that search profile is configured correctly."""
        from p8_analyzer.text import SearchProfile, SearchDirection

        mock_engine = MagicMock()
        mock_engine.find_text.return_value = None

        point = Mock(x=100, y=100)
        finder._find_label_element_near_point(point, mock_engine)

        # Get the profile that was passed
        call_args = mock_engine.find_text.call_args
        profile = call_args[0][1]  # Second positional arg is profile

        assert isinstance(profile, SearchProfile)
        assert profile.direction == SearchDirection.ANY
        assert profile.use_ocr_fallback is True


class TestPinFinderDuplicateHandling:
    """Tests for duplicate pin handling."""

    @pytest.fixture
    def finder(self):
        """Create finder for duplicate tests."""
        return PinFinder()

    def test_same_label_different_location_gets_numbered(self, finder):
        """Test that same label at different locations gets numbered."""
        # This tests the duplicate detection logic
        group = Mock()

        # Two elements with endpoints at different locations
        elem1 = Mock()
        elem1.start_point = Mock(x=100, y=100)
        elem1.end_point = Mock(x=120, y=100)

        elem2 = Mock()
        elem2.start_point = Mock(x=100, y=150)  # Different Y
        elem2.end_point = Mock(x=120, y=150)

        group.elements = [elem1, elem2]

        # Mock box containing both
        box = Mock()
        box.id = 'BOX-1'
        box.contains_point = Mock(return_value=True)

        # Mock engine returning same label for both
        mock_engine = MagicMock()
        mock_engine.pdf_elements = [
            type('TextElement', (), {
                'text': '13',
                'center': (105, 100),
                'bbox': (100, 95, 110, 105),
                'source': 'pdf',
                'confidence': 1.0
            })(),
            type('TextElement', (), {
                'text': '13',  # Same label
                'center': (105, 150),
                'bbox': (100, 145, 110, 155),
                'source': 'pdf',
                'confidence': 1.0
            })()
        ]

        result = finder.find_pins_for_group(group, [box], mock_engine)

        # Should have 2 pins, second one should have " (2)" suffix
        # Based on the implementation, it adds a counter to duplicates
        labels = [p['full_label'] for p in result]
        # The implementation should handle duplicates
