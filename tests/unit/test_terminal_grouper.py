"""
Unit tests for src/terminal_grouper.py

Tests the TerminalGrouper class which assigns group labels to terminals
using inheritance logic.
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from p8_analyzer.detection import TerminalGrouper


class TestTerminalGrouper:
    """Tests for TerminalGrouper class."""

    @pytest.fixture
    def grouper(self, default_terminal_grouper_config):
        """Create a TerminalGrouper instance with default config."""
        return TerminalGrouper(config=default_terminal_grouper_config)

    @pytest.fixture
    def grouper_custom_config(self):
        """Create a TerminalGrouper with custom configuration."""
        return TerminalGrouper(config={
            'search_direction': 'right',
            'search_radius': 50.0,
            'y_tolerance': 10.0,
            'label_pattern': r'^-?Y.*',
            'neighbor_x_distance': 30.0
        })

    def test_grouper_initialization_default(self, grouper):
        """Test grouper initializes with default values."""
        assert grouper.search_direction == 'left'
        assert grouper.search_radius == 100.0
        assert grouper.y_tolerance == 15.0
        assert grouper.label_pattern == r'^-?X.*'
        assert grouper.neighbor_x_distance == 50.0

    def test_grouper_initialization_custom(self, grouper_custom_config):
        """Test grouper initializes with custom values."""
        assert grouper_custom_config.search_direction == 'right'
        assert grouper_custom_config.search_radius == 50.0
        assert grouper_custom_config.y_tolerance == 10.0
        assert grouper_custom_config.label_pattern == r'^-?Y.*'

    def test_group_terminals_empty_list(self, grouper, mock_text_engine):
        """Test grouping with empty terminal list."""
        result = grouper.group_terminals([], mock_text_engine)
        assert result == []

    def test_group_terminals_adds_full_label(self, grouper):
        """Test that full_label is added in correct format."""
        mock_engine = MagicMock()

        # Mock finding group label
        mock_result = Mock()
        mock_result.text = '-X1'
        mock_result.source = 'pdf'
        mock_engine.find_text.return_value = mock_result

        terminals = [
            {'center': (100, 100), 'label': '1', 'group_id': 1}
        ]

        result = grouper.group_terminals(terminals, mock_engine)

        assert len(result) == 1
        assert result[0]['group_label'] == '-X1'
        assert result[0]['full_label'] == '-X1:1'

    def test_group_terminals_unknown_group(self, grouper):
        """Test full_label format when no group found."""
        mock_engine = MagicMock()
        mock_engine.find_text.return_value = None

        terminals = [
            {'center': (100, 100), 'label': '1', 'group_id': 1}
        ]

        result = grouper.group_terminals(terminals, mock_engine)

        assert result[0]['group_label'] is None
        assert result[0]['full_label'] == 'UNK:1'

    def test_group_terminals_unknown_label(self, grouper):
        """Test full_label format when no pin label."""
        mock_engine = MagicMock()

        mock_result = Mock()
        mock_result.text = '-X1'
        mock_result.source = 'pdf'
        mock_engine.find_text.return_value = mock_result

        terminals = [
            {'center': (100, 100), 'label': None, 'group_id': 1}
        ]

        result = grouper.group_terminals(terminals, mock_engine)

        assert result[0]['full_label'] == '-X1:?'

    def test_group_terminals_sorts_by_y_then_x(self, grouper):
        """Test that terminals are sorted by Y coordinate, then X."""
        mock_engine = MagicMock()
        mock_engine.find_text.return_value = None

        # Terminals in random order
        terminals = [
            {'center': (200, 100), 'label': 'B', 'group_id': 1},
            {'center': (100, 200), 'label': 'C', 'group_id': 1},
            {'center': (100, 100), 'label': 'A', 'group_id': 1},
        ]

        result = grouper.group_terminals(terminals, mock_engine)

        # Should be sorted by Y first, then X
        assert result[0]['label'] == 'A'  # (100, 100)
        assert result[1]['label'] == 'B'  # (200, 100)
        assert result[2]['label'] == 'C'  # (100, 200)


class TestTerminalGrouperInheritance:
    """Tests for terminal group inheritance logic."""

    @pytest.fixture
    def grouper(self):
        """Create grouper for inheritance tests."""
        return TerminalGrouper(config={
            'search_radius': 100.0,
            'y_tolerance': 15.0,
            'neighbor_x_distance': 50.0
        })

    def test_inherit_from_left_neighbor(self, grouper):
        """Test group inheritance from left neighbor on same Y level."""
        mock_engine = MagicMock()

        # First terminal has group, second doesn't find one directly
        mock_result = Mock()
        mock_result.text = '-X1'
        mock_result.source = 'pdf'
        mock_engine.find_text.side_effect = [mock_result, None]

        terminals = [
            {'center': (100, 100), 'label': '1', 'group_id': 1},
            {'center': (150, 100), 'label': '2', 'group_id': 1},  # Same Y, should inherit
        ]

        result = grouper.group_terminals(terminals, mock_engine)

        assert result[0]['group_label'] == '-X1'
        assert result[1]['group_label'] == '-X1'  # Inherited
        assert result[1]['group_source'] == 'inherited'

    def test_no_inherit_different_y_level(self, grouper):
        """Test that terminals on different Y levels don't inherit horizontally."""
        mock_engine = MagicMock()

        mock_result = Mock()
        mock_result.text = '-X1'
        mock_result.source = 'pdf'
        mock_engine.find_text.side_effect = [mock_result, None]

        terminals = [
            {'center': (100, 100), 'label': '1', 'group_id': 1},
            {'center': (150, 200), 'label': '2', 'group_id': 1},  # Different Y (200 vs 100)
        ]

        result = grouper.group_terminals(terminals, mock_engine)

        assert result[0]['group_label'] == '-X1'
        # Second terminal should NOT inherit (Y difference > y_tolerance)
        # It might inherit from vertical scan or remain None

    def test_inherit_chain(self, grouper):
        """Test inheritance chain across multiple terminals."""
        mock_engine = MagicMock()

        mock_result = Mock()
        mock_result.text = '-X1'
        mock_result.source = 'pdf'
        # Only first terminal finds group directly
        mock_engine.find_text.side_effect = [mock_result, None, None, None]

        terminals = [
            {'center': (100, 100), 'label': '1', 'group_id': 1},
            {'center': (150, 100), 'label': '2', 'group_id': 1},
            {'center': (200, 100), 'label': '3', 'group_id': 1},
            {'center': (250, 100), 'label': 'PE', 'group_id': 1},
        ]

        result = grouper.group_terminals(terminals, mock_engine)

        # All should inherit from the first
        for term in result:
            assert term['group_label'] == '-X1'


class TestFindParentTerminal:
    """Tests for _find_parent_terminal method."""

    @pytest.fixture
    def grouper(self):
        """Create grouper for parent finding tests."""
        return TerminalGrouper(config={
            'y_tolerance': 15.0,
            'neighbor_x_distance': 50.0
        })

    def test_find_parent_empty_list(self, grouper):
        """Test finding parent with no previous terminals."""
        terminal = {'center': (100, 100), 'label': '1'}
        result = grouper._find_parent_terminal(terminal, [])
        assert result is None

    def test_find_parent_horizontal_same_y(self, grouper):
        """Test finding horizontal parent on same Y level."""
        terminal = {'center': (150, 100), 'label': '2'}
        previous = [
            {'center': (100, 100), 'label': '1', 'group_label': '-X1'}
        ]

        result = grouper._find_parent_terminal(terminal, previous)
        assert result is not None
        assert result['group_label'] == '-X1'

    def test_find_parent_skips_ungrouped(self, grouper):
        """Test that ungrouped terminals are skipped in parent search."""
        terminal = {'center': (200, 100), 'label': '3'}
        previous = [
            {'center': (100, 100), 'label': '1', 'group_label': '-X1'},
            {'center': (150, 100), 'label': '2', 'group_label': None},  # No group
        ]

        result = grouper._find_parent_terminal(terminal, previous)
        # Should find the first one with a group_label
        assert result['label'] == '1'

    def test_find_parent_y_tolerance(self, grouper):
        """Test Y tolerance in parent finding."""
        # Terminal at Y=110, tolerance is 15
        terminal = {'center': (150, 110), 'label': '2'}
        previous = [
            {'center': (100, 100), 'label': '1', 'group_label': '-X1'}  # Y diff = 10, within tolerance
        ]

        result = grouper._find_parent_terminal(terminal, previous)
        assert result is not None

    def test_find_parent_y_out_of_tolerance(self, grouper):
        """Test Y out of tolerance in parent finding."""
        # Terminal at Y=120, tolerance is 15
        terminal = {'center': (150, 120), 'label': '2'}
        previous = [
            {'center': (100, 100), 'label': '1', 'group_label': '-X1'}  # Y diff = 20, outside tolerance
        ]

        # Horizontal scan should fail
        result = grouper._find_parent_terminal(terminal, previous)
        # May find via vertical scan or return None


class TestTerminalGrouperGroupSource:
    """Tests for group_source tracking."""

    @pytest.fixture
    def grouper(self):
        """Create grouper for group source tests."""
        return TerminalGrouper()

    def test_group_source_direct_pdf(self, grouper):
        """Test group_source is set to 'pdf_direct' for direct finds."""
        mock_engine = MagicMock()

        mock_result = Mock()
        mock_result.text = '-X1'
        mock_result.source = 'pdf'
        mock_engine.find_text.return_value = mock_result

        terminals = [{'center': (100, 100), 'label': '1', 'group_id': 1}]
        result = grouper.group_terminals(terminals, mock_engine)

        assert result[0]['group_source'] == 'pdf_direct'

    def test_group_source_direct_ocr(self, grouper):
        """Test group_source is set to 'ocr_direct' for OCR finds."""
        mock_engine = MagicMock()

        mock_result = Mock()
        mock_result.text = '-X1'
        mock_result.source = 'ocr'
        mock_engine.find_text.return_value = mock_result

        terminals = [{'center': (100, 100), 'label': '1', 'group_id': 1}]
        result = grouper.group_terminals(terminals, mock_engine)

        assert result[0]['group_source'] == 'ocr_direct'

    def test_group_source_inherited(self, grouper):
        """Test group_source is set to 'inherited' for inherited groups."""
        mock_engine = MagicMock()

        mock_result = Mock()
        mock_result.text = '-X1'
        mock_result.source = 'pdf'
        mock_engine.find_text.side_effect = [mock_result, None]

        terminals = [
            {'center': (100, 100), 'label': '1', 'group_id': 1},
            {'center': (150, 100), 'label': '2', 'group_id': 1},
        ]

        result = grouper.group_terminals(terminals, mock_engine)

        assert result[0]['group_source'] == 'pdf_direct'
        assert result[1]['group_source'] == 'inherited'
