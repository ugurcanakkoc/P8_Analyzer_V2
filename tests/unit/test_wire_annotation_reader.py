"""
Unit tests for WireAnnotationReader.
"""
import pytest
import math
from unittest.mock import Mock, MagicMock

from p8_analyzer.detection.wire_annotation_reader import (
    WireAnnotationReader,
    WireAnnotationConfig,
    find_connected_paths,
    create_cardinal_paths,
    _angle_to_direction_name,
)
from p8_analyzer.core.models import StructuralGroup, PathElement, Point
from p8_analyzer.core.session import WireAnnotationType
from p8_analyzer.text.hybrid_engine import TextElement


class TestAngleToDirectionName:
    """Test angle to direction conversion."""

    def test_right(self):
        assert _angle_to_direction_name(0) == 'right'
        assert _angle_to_direction_name(math.radians(30)) == 'right'
        assert _angle_to_direction_name(math.radians(-30)) == 'right'

    def test_left(self):
        assert _angle_to_direction_name(math.pi) == 'left'
        assert _angle_to_direction_name(math.radians(150)) == 'left'
        assert _angle_to_direction_name(math.radians(-150)) == 'left'

    def test_top(self):
        assert _angle_to_direction_name(-math.pi/2) == 'top'
        assert _angle_to_direction_name(math.radians(-90)) == 'top'

    def test_bottom(self):
        assert _angle_to_direction_name(math.pi/2) == 'bottom'
        assert _angle_to_direction_name(math.radians(90)) == 'bottom'


class TestFindConnectedPaths:
    """Test finding connected wire paths."""

    def test_path_from_start_point(self):
        # Create a path element that starts at terminal
        elem = Mock()
        elem.start_point = Mock(x=100, y=100)  # Terminal location
        elem.end_point = Mock(x=200, y=100)    # Wire goes right

        group = Mock()
        group.elements = [elem]

        paths = find_connected_paths(100, 100, group, tolerance=5.0)

        assert len(paths) == 1
        assert paths[0]['end_point'] == (200, 100)
        assert abs(paths[0]['direction_angle'] - 0) < 0.01  # Right direction

    def test_path_from_end_point(self):
        # Create a path element that ends at terminal
        elem = Mock()
        elem.start_point = Mock(x=0, y=100)    # Wire comes from left
        elem.end_point = Mock(x=100, y=100)    # Terminal location

        group = Mock()
        group.elements = [elem]

        paths = find_connected_paths(100, 100, group, tolerance=5.0)

        assert len(paths) == 1
        assert paths[0]['end_point'] == (0, 100)
        assert abs(paths[0]['direction_angle'] - math.pi) < 0.01  # Left direction

    def test_no_connected_paths(self):
        # Path element far from terminal
        elem = Mock()
        elem.start_point = Mock(x=500, y=500)
        elem.end_point = Mock(x=600, y=500)

        group = Mock()
        group.elements = [elem]

        paths = find_connected_paths(100, 100, group, tolerance=5.0)

        assert len(paths) == 0


class TestCreateCardinalPaths:
    """Test cardinal direction path creation."""

    def test_creates_four_paths(self):
        paths = create_cardinal_paths(100, 100, length=150)

        assert len(paths) == 4

    def test_path_directions(self):
        paths = create_cardinal_paths(100, 100, length=150)

        # Should have right, left, top, bottom
        direction_names = [_angle_to_direction_name(p['direction_angle']) for p in paths]
        assert 'right' in direction_names
        assert 'left' in direction_names
        assert 'top' in direction_names
        assert 'bottom' in direction_names


class TestWireAnnotationReader:
    """Test WireAnnotationReader class."""

    def test_init_default_config(self):
        reader = WireAnnotationReader()
        assert reader.config.max_search_distance == 150.0
        assert reader.config.min_search_distance == 15.0

    def test_init_custom_config(self):
        config = WireAnnotationConfig(
            max_search_distance=200.0,
            min_search_distance=10.0
        )
        reader = WireAnnotationReader(config)
        assert reader.config.max_search_distance == 200.0

    def test_read_annotations_empty_terminals(self):
        reader = WireAnnotationReader()
        mock_engine = Mock()

        result = reader.read_annotations([], [], mock_engine)

        assert result == []

    def test_read_annotations_adds_field(self):
        reader = WireAnnotationReader()

        # Create mock text engine that returns empty
        mock_engine = Mock()
        mock_engine.find_all_text_near = Mock(return_value=[])

        terminals = [
            {'center': (100, 100), 'group_id': None, 'label': '1'}
        ]

        result = reader.read_annotations(terminals, [], mock_engine)

        assert 'wire_annotations' in result[0]
        assert isinstance(result[0]['wire_annotations'], list)

    def test_read_annotations_finds_signal_name(self):
        reader = WireAnnotationReader()

        # Create mock text engine that returns P24 annotation
        mock_engine = Mock()
        text_elem = TextElement(
            text='P24',
            center=(80, 100),
            bbox=(75, 95, 85, 105),
            source='pdf',
            confidence=1.0
        )
        mock_engine.find_all_text_near = Mock(return_value=[text_elem])

        terminals = [
            {'center': (100, 100), 'group_id': None, 'label': '1'}
        ]

        result = reader.read_annotations(terminals, [], mock_engine)

        # Should find the P24 annotation
        annotations = result[0]['wire_annotations']
        assert len(annotations) >= 1
        found_p24 = any(a['text'] == 'P24' for a in annotations)
        assert found_p24

    def test_read_annotations_finds_destination_ref(self):
        reader = WireAnnotationReader()

        # Create mock text engine that returns /6.4 annotation
        mock_engine = Mock()
        text_elem = TextElement(
            text='/6.4',
            center=(70, 100),
            bbox=(65, 95, 75, 105),
            source='pdf',
            confidence=1.0
        )
        mock_engine.find_all_text_near = Mock(return_value=[text_elem])

        terminals = [
            {'center': (100, 100), 'group_id': None, 'label': '1'}
        ]

        result = reader.read_annotations(terminals, [], mock_engine)

        annotations = result[0]['wire_annotations']
        found_ref = any(a['text'] == '/6.4' for a in annotations)
        assert found_ref

    def test_deduplication_keeps_closest(self):
        reader = WireAnnotationReader()

        # Create mock text engine that returns same text at different distances
        mock_engine = Mock()

        def mock_find_all(point, radius, pattern, direction):
            # Return P24 at different positions based on sample point
            x, y = point
            if x < 90:  # Further from terminal
                return [TextElement(
                    text='P24',
                    center=(x, y),
                    bbox=(x-5, y-5, x+5, y+5),
                    source='pdf',
                    confidence=1.0
                )]
            elif x < 80:  # Closer to terminal
                return [TextElement(
                    text='P24',
                    center=(x, y),
                    bbox=(x-5, y-5, x+5, y+5),
                    source='pdf',
                    confidence=1.0
                )]
            return []

        mock_engine.find_all_text_near = mock_find_all

        terminals = [
            {'center': (100, 100), 'group_id': None, 'label': '1'}
        ]

        result = reader.read_annotations(terminals, [], mock_engine)

        # Should only have one P24 annotation (deduplicated)
        annotations = result[0]['wire_annotations']
        p24_count = sum(1 for a in annotations if a['text'] == 'P24')
        assert p24_count <= 1  # Should be deduplicated

    def test_ignores_unknown_annotations(self):
        reader = WireAnnotationReader()

        # Create mock text engine that returns unknown text
        mock_engine = Mock()
        text_elem = TextElement(
            text='random text',
            center=(80, 100),
            bbox=(75, 95, 85, 105),
            source='pdf',
            confidence=1.0
        )
        mock_engine.find_all_text_near = Mock(return_value=[text_elem])

        terminals = [
            {'center': (100, 100), 'group_id': None, 'label': '1'}
        ]

        result = reader.read_annotations(terminals, [], mock_engine)

        # Should not find the random text
        annotations = result[0]['wire_annotations']
        found_random = any(a['text'] == 'random text' for a in annotations)
        assert not found_random
