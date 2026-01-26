"""Unit tests for the AnalysisEngine class."""
import pytest
from unittest.mock import Mock, MagicMock, patch
import math

from p8_analyzer.core.analysis_engine import AnalysisEngine


class TestOrderAlongWirePath:
    """Tests for _order_along_wire_path method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = AnalysisEngine()
        # Mock the clusters attribute
        self.engine._clusters = []

    def test_empty_input(self):
        """Empty input returns empty list."""
        result = self.engine._order_along_wire_path([], None, [], {})
        assert result == []

    def test_single_element(self):
        """Single element returns as-is."""
        result = self.engine._order_along_wire_path(['-X1:L1'], None, [], {})
        assert result == ['-X1:L1']

    def test_filters_redundant_components(self):
        """Components without pins are filtered when pins exist."""
        comp_ids = ['-X1:L1', '-X1', '-1Q21:1', '-1Q21', '-1Q21:2']
        terminals = [
            {'full_label': '-X1:L1', 'center': (100, 500)},
        ]
        pins_by_component = {
            '-1Q21': [
                {'full_label': '-1Q21:1', 'location': (200, 400)},
                {'full_label': '-1Q21:2', 'location': (200, 300)},
            ]
        }

        result = self.engine._order_along_wire_path(
            comp_ids, None, terminals, pins_by_component
        )

        # -X1 and -1Q21 (bare components) should be filtered out
        assert '-X1' not in result
        assert '-1Q21' not in result
        # Pins should remain
        assert '-X1:L1' in result
        assert '-1Q21:1' in result
        assert '-1Q21:2' in result

    def test_sorts_bottom_left_to_top_right(self):
        """Elements are sorted from bottom-left to top-right."""
        comp_ids = ['A', 'B', 'C']
        terminals = [
            {'full_label': 'A', 'center': (100, 100)},  # top-left
            {'full_label': 'B', 'center': (200, 500)},  # bottom-right
            {'full_label': 'C', 'center': (50, 300)},   # middle-left
        ]

        result = self.engine._order_along_wire_path(
            comp_ids, None, terminals, {}
        )

        # B has highest y (500) so comes first (bottom)
        # C has y=300, comes second
        # A has lowest y (100) so comes last (top)
        assert result == ['B', 'C', 'A']

    def test_uses_pin_positions(self):
        """Pin positions are used for sorting."""
        comp_ids = ['-1Q21:1', '-1Q21:2']
        pins_by_component = {
            '-1Q21': [
                {'full_label': '-1Q21:1', 'location': (200, 500)},  # bottom
                {'full_label': '-1Q21:2', 'location': (200, 100)},  # top
            ]
        }

        result = self.engine._order_along_wire_path(
            comp_ids, None, [], pins_by_component
        )

        # Pin 1 at y=500 (bottom) should come before pin 2 at y=100 (top)
        assert result == ['-1Q21:1', '-1Q21:2']

    def test_endpoint_labels_parameter(self):
        """Endpoint labels are included in sorting."""
        comp_ids = ['-X1:L1', 'L1']
        terminals = [
            {'full_label': '-X1:L1', 'center': (100, 500)},
        ]
        endpoint_labels = [
            {'label': 'L1', 'location': (300, 100)},  # top-right
        ]

        result = self.engine._order_along_wire_path(
            comp_ids, None, terminals, {}, endpoint_labels
        )

        # -X1:L1 at y=500 (bottom) first, L1 at y=100 (top) last
        assert result == ['-X1:L1', 'L1']

    def test_endpoint_labels_default_none(self):
        """Method works when endpoint_labels is not provided."""
        comp_ids = ['-X1:L1']
        terminals = [{'full_label': '-X1:L1', 'center': (100, 500)}]

        # Should not raise when endpoint_labels is omitted
        result = self.engine._order_along_wire_path(
            comp_ids, None, terminals, {}
        )
        assert result == ['-X1:L1']


class TestDetectEndpointLabels:
    """Tests for _detect_endpoint_labels method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = AnalysisEngine()

    def test_no_clusters_returns_empty(self):
        """Returns empty dict when no clusters exist."""
        self.engine._clusters = None
        result = self.engine._detect_endpoint_labels()
        assert result == {}

    def test_empty_clusters_returns_empty(self):
        """Returns empty dict when clusters list is empty."""
        self.engine._clusters = []
        result = self.engine._detect_endpoint_labels()
        assert result == {}

    def test_skips_labeled_clusters(self):
        """Labeled clusters are skipped (handled by _detect_pins)."""
        # Create mock labeled cluster
        labeled_cluster = Mock()
        labeled_cluster.label = Mock(text='-1Q21')
        labeled_cluster.objects = []

        self.engine._clusters = [labeled_cluster]
        self.engine._analysis_result = Mock(structural_groups=[])

        result = self.engine._detect_endpoint_labels()
        assert result == {}


class TestFindStructuralGroupForPoint:
    """Tests for _find_structural_group_for_point method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = AnalysisEngine()

    def test_returns_none_when_no_groups(self):
        """Returns None when no structural groups exist."""
        self.engine._analysis_result = Mock(structural_groups=[])
        result = self.engine._find_structural_group_for_point(100, 100)
        assert result is None

    def test_finds_matching_group(self):
        """Finds the structural group containing the point."""
        # Create mock structural group
        elem = Mock()
        elem.start_point = Mock(x=100, y=100)
        elem.end_point = Mock(x=200, y=100)

        group = Mock(elements=[elem])
        self.engine._analysis_result = Mock(structural_groups=[group])

        # Point near start_point
        result = self.engine._find_structural_group_for_point(101, 101)
        assert result == 0

    def test_respects_tolerance(self):
        """Point must be within tolerance distance."""
        elem = Mock()
        elem.start_point = Mock(x=100, y=100)
        elem.end_point = Mock(x=200, y=100)

        group = Mock(elements=[elem])
        self.engine._analysis_result = Mock(structural_groups=[group])

        # Point too far away (default tolerance is 5.0)
        result = self.engine._find_structural_group_for_point(110, 110)
        assert result is None


class TestGetClusterObjectPoints:
    """Tests for _get_cluster_object_points method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = AnalysisEngine()

    def test_gap_returns_start_and_end(self):
        """Gap objects return gap_start and gap_end positions."""
        obj = Mock()
        obj.obj_type = 'gap'
        obj.original = Mock()
        obj.original.gap_start = (100, 200)
        obj.original.gap_end = (150, 200)

        result = self.engine._get_cluster_object_points(obj)

        assert len(result) == 2
        assert (100, 200) in result
        assert (150, 200) in result

    def test_circle_returns_position(self):
        """Circle objects return their position."""
        obj = Mock()
        obj.obj_type = 'circle'
        obj.position = (100, 200)

        result = self.engine._get_cluster_object_points(obj)

        assert result == [(100, 200)]

    def test_line_end_returns_position(self):
        """Line end objects return their position."""
        obj = Mock()
        obj.obj_type = 'line_end'
        obj.position = (100, 200)

        result = self.engine._get_cluster_object_points(obj)

        assert result == [(100, 200)]

    def test_gap_missing_start(self):
        """Gap with missing gap_start only returns gap_end."""
        obj = Mock()
        obj.obj_type = 'gap'
        obj.original = Mock()
        obj.original.gap_start = None
        obj.original.gap_end = (150, 200)

        result = self.engine._get_cluster_object_points(obj)

        assert result == [(150, 200)]


class TestIsValidPinLabel:
    """Tests for _is_valid_pin_label method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = AnalysisEngine()

    def test_empty_string_invalid(self):
        """Empty string is invalid."""
        assert self.engine._is_valid_pin_label('') is False

    def test_none_invalid(self):
        """None is invalid."""
        assert self.engine._is_valid_pin_label(None) is False

    def test_long_string_invalid(self):
        """Strings longer than 10 chars are invalid."""
        assert self.engine._is_valid_pin_label('12345678901') is False

    def test_component_label_invalid(self):
        """Labels starting with - are invalid (component labels)."""
        assert self.engine._is_valid_pin_label('-X1') is False
        assert self.engine._is_valid_pin_label('-1Q21') is False

    def test_valid_pin_labels(self):
        """Valid pin labels are accepted."""
        assert self.engine._is_valid_pin_label('1') is True
        assert self.engine._is_valid_pin_label('L1') is True
        assert self.engine._is_valid_pin_label('PE') is True
        assert self.engine._is_valid_pin_label('A1') is True
        assert self.engine._is_valid_pin_label('L1(+)') is True


class TestAnalyzePageIntegration:
    """Integration tests for analyze_page method."""

    @pytest.fixture
    def mock_page(self):
        """Create a mock PDF page."""
        page = Mock()
        page.rect = Mock(width=1122, height=810)
        page.number = 10
        page.get_drawings.return_value = []  # Empty drawings triggers early return
        page.get_text.return_value = ''
        return page

    def test_analyze_page_empty_drawings_returns_empty_analysis(self, mock_page):
        """analyze_page with no drawings returns empty PageAnalysis."""
        engine = AnalysisEngine()

        result = engine.analyze_page(mock_page, 11)

        assert result.page_number == 11
        assert result.page_width == 1122
        assert result.page_height == 810
        assert len(result.terminals) == 0
        assert len(result.components) == 0
        assert len(result.connections) == 0
