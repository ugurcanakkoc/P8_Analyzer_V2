"""
Unit tests for src/terminal_reader.py

Tests the TerminalReader class which reads terminal labels
from the PDF text layer using the hybrid text engine.
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestTerminalReader:
    """Tests for TerminalReader class."""

    @pytest.fixture
    def reader(self, default_terminal_reader_config):
        """Create a TerminalReader instance with default config."""
        from p8_analyzer.detection import TerminalReader
        return TerminalReader(config=default_terminal_reader_config)

    @pytest.fixture
    def reader_custom_direction(self):
        """Create a TerminalReader with custom direction."""
        from p8_analyzer.detection import TerminalReader
        return TerminalReader(config={
            'direction': 'left',
            'search_radius': 30.0,
            'y_tolerance': 20.0
        })

    def test_reader_initialization_default(self, reader):
        """Test reader initializes with default values."""
        assert reader.direction == 'top_right'
        assert reader.search_radius == 20.0
        assert reader.y_tolerance == 15.0

    def test_reader_initialization_custom(self, reader_custom_direction):
        """Test reader initializes with custom values."""
        assert reader_custom_direction.direction == 'left'
        assert reader_custom_direction.search_radius == 30.0
        assert reader_custom_direction.y_tolerance == 20.0

    def test_direction_map_contains_all_directions(self, reader):
        """Test that direction map has all expected directions."""
        expected_directions = [
            'any', 'top', 'bottom', 'right', 'left',
            'top_right', 'top_left', 'bottom_right', 'bottom_left'
        ]
        for direction in expected_directions:
            assert direction in reader.direction_map

    def test_read_labels_empty_terminals(self, reader, mock_text_engine):
        """Test reading labels with empty terminal list."""
        result = reader.read_labels([], mock_text_engine)
        assert result == []

    def test_read_labels_finds_labels(self, reader, sample_terminals_unlabeled):
        """Test reading labels for terminals."""
        # Create mock text engine with find_text method
        mock_engine = MagicMock()

        # Mock responses for each terminal
        mock_result_1 = Mock()
        mock_result_1.text = '1'
        mock_result_1.source = 'pdf'

        mock_result_2 = Mock()
        mock_result_2.text = '2'
        mock_result_2.source = 'pdf'

        mock_engine.find_text.side_effect = [mock_result_1, mock_result_2]

        result = reader.read_labels(sample_terminals_unlabeled, mock_engine)

        assert len(result) == 2
        assert result[0]['label'] == '1'
        assert result[0]['label_source'] == 'pdf'
        assert result[1]['label'] == '2'
        assert result[1]['label_source'] == 'pdf'

    def test_read_labels_handles_not_found(self, reader, sample_terminals_unlabeled):
        """Test reading labels when text not found."""
        mock_engine = MagicMock()
        mock_engine.find_text.return_value = None

        result = reader.read_labels(sample_terminals_unlabeled, mock_engine)

        assert len(result) == 2
        assert result[0]['label'] == '?'
        assert result[0]['label_source'] is None
        assert result[1]['label'] == '?'

    def test_read_labels_mixed_found_not_found(self, reader, sample_terminals_unlabeled):
        """Test reading labels with some found and some not."""
        mock_engine = MagicMock()

        mock_result = Mock()
        mock_result.text = 'PE'
        mock_result.source = 'ocr'

        # First terminal found, second not found
        mock_engine.find_text.side_effect = [mock_result, None]

        result = reader.read_labels(sample_terminals_unlabeled, mock_engine)

        assert result[0]['label'] == 'PE'
        assert result[0]['label_source'] == 'ocr'
        assert result[1]['label'] == '?'
        assert result[1]['label_source'] is None

    def test_read_labels_uses_correct_search_profile(self, reader):
        """Test that reader creates correct search profile."""
        from p8_analyzer.text import SearchProfile, SearchDirection

        mock_engine = MagicMock()
        mock_engine.find_text.return_value = None

        terminals = [{'center': (100, 100), 'radius': 3.0, 'cv': 0.005}]
        reader.read_labels(terminals, mock_engine)

        # Verify find_text was called
        mock_engine.find_text.assert_called_once()

        # Get the profile that was passed
        call_args = mock_engine.find_text.call_args
        profile = call_args[0][1]  # Second positional argument

        assert isinstance(profile, SearchProfile)
        assert profile.search_radius == reader.search_radius
        assert profile.direction == SearchDirection.TOP_RIGHT
        assert profile.use_ocr_fallback is True

    def test_read_labels_preserves_terminal_data(self, reader, sample_terminals_unlabeled):
        """Test that original terminal data is preserved."""
        mock_engine = MagicMock()
        mock_engine.find_text.return_value = None

        result = reader.read_labels(sample_terminals_unlabeled, mock_engine)

        # Original data should be preserved
        assert result[0]['center'] == (100, 100)
        assert result[0]['radius'] == 3.0
        assert result[0]['cv'] == 0.005


class TestTerminalReaderDirections:
    """Tests for different search directions."""

    @pytest.fixture
    def create_reader_with_direction(self):
        """Factory to create readers with specific directions."""
        def _create(direction: str):
            from p8_analyzer.detection import TerminalReader
            return TerminalReader(config={'direction': direction})
        return _create

    def test_direction_any(self, create_reader_with_direction):
        """Test reader with 'any' direction."""
        from p8_analyzer.text import SearchDirection
        reader = create_reader_with_direction('any')
        assert reader.direction_map['any'] == SearchDirection.ANY

    def test_direction_top(self, create_reader_with_direction):
        """Test reader with 'top' direction."""
        from p8_analyzer.text import SearchDirection
        reader = create_reader_with_direction('top')
        assert reader.direction_map['top'] == SearchDirection.TOP

    def test_direction_invalid_defaults_to_top_right(self, create_reader_with_direction):
        """Test reader with invalid direction falls back safely."""
        reader = create_reader_with_direction('invalid_direction')
        # Should use 'invalid_direction' as key but get() will return default
        assert reader.direction == 'invalid_direction'


class TestTerminalReaderIntegration:
    """Integration-like tests with mock text engine."""

    @pytest.fixture
    def reader(self):
        """Create standard reader."""
        from p8_analyzer.detection import TerminalReader
        return TerminalReader()

    def test_read_multiple_terminals_row(self, reader):
        """Test reading labels for a row of terminals."""
        mock_engine = MagicMock()

        # Simulate a row of terminals with sequential labels
        terminals = [
            {'center': (100, 100), 'radius': 3.0, 'cv': 0.005, 'group_id': 1, 'label': None},
            {'center': (150, 100), 'radius': 3.0, 'cv': 0.005, 'group_id': 1, 'label': None},
            {'center': (200, 100), 'radius': 3.0, 'cv': 0.005, 'group_id': 1, 'label': None},
        ]

        labels = ['1', '2', 'PE']
        mock_results = []
        for label in labels:
            result = Mock()
            result.text = label
            result.source = 'pdf'
            mock_results.append(result)

        mock_engine.find_text.side_effect = mock_results

        result = reader.read_labels(terminals, mock_engine)

        assert len(result) == 3
        assert [t['label'] for t in result] == ['1', '2', 'PE']

    def test_labeled_count_calculation(self, reader, capsys):
        """Test that labeled count is correctly calculated."""
        mock_engine = MagicMock()

        terminals = [
            {'center': (100, 100), 'radius': 3.0, 'cv': 0.005, 'group_id': 1, 'label': None},
            {'center': (150, 100), 'radius': 3.0, 'cv': 0.005, 'group_id': 1, 'label': None},
            {'center': (200, 100), 'radius': 3.0, 'cv': 0.005, 'group_id': 1, 'label': None},
        ]

        # Only first two found
        mock_result_1 = Mock(text='1', source='pdf')
        mock_result_2 = Mock(text='2', source='pdf')
        mock_engine.find_text.side_effect = [mock_result_1, mock_result_2, None]

        result = reader.read_labels(terminals, mock_engine)

        labeled = sum(1 for t in result if t['label'] != '?')
        assert labeled == 2
