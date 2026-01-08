"""
Integration tests for the detection pipeline.

Tests the interaction between TerminalDetector, TerminalReader,
and TerminalGrouper components.
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestDetectionToReadingPipeline:
    """Tests for TerminalDetector -> TerminalReader pipeline."""

    @pytest.fixture
    def detector(self, default_terminal_detector_config):
        """Create detector."""
        with patch.dict('sys.modules', {'external.uvp.src.models': Mock()}):
            from p8_analyzer.detection import TerminalDetector
            return TerminalDetector(config=default_terminal_detector_config)

    @pytest.fixture
    def reader(self, default_terminal_reader_config):
        """Create reader."""
        from p8_analyzer.detection import TerminalReader
        return TerminalReader(config=default_terminal_reader_config)

    def test_detected_terminals_can_be_read(
        self, detector, reader, sample_vector_analysis_with_terminals
    ):
        """Test that detected terminals can be passed to reader."""
        # Detect terminals
        detected = detector.detect(sample_vector_analysis_with_terminals)
        assert len(detected) > 0

        # Mock text engine
        mock_engine = MagicMock()
        mock_result = Mock()
        mock_result.text = '1'
        mock_result.source = 'pdf'
        mock_engine.find_text.return_value = mock_result

        # Read labels
        labeled = reader.read_labels(detected, mock_engine)

        # Verify structure is preserved
        assert len(labeled) == len(detected)
        for term in labeled:
            assert 'center' in term
            assert 'radius' in term
            assert 'label' in term

    def test_detected_terminals_have_correct_structure_for_reader(
        self, detector, sample_vector_analysis_with_terminals
    ):
        """Test detected terminals have required fields for reader."""
        detected = detector.detect(sample_vector_analysis_with_terminals)

        required_fields = ['center', 'radius', 'cv', 'is_filled', 'group_id', 'label']

        for terminal in detected:
            for field in required_fields:
                assert field in terminal, f"Missing field: {field}"


class TestReadingToGroupingPipeline:
    """Tests for TerminalReader -> TerminalGrouper pipeline."""

    @pytest.fixture
    def reader(self):
        """Create reader."""
        from p8_analyzer.detection import TerminalReader
        return TerminalReader()

    @pytest.fixture
    def grouper(self):
        """Create grouper."""
        from p8_analyzer.detection import TerminalGrouper
        return TerminalGrouper()

    def test_labeled_terminals_can_be_grouped(self, reader, grouper):
        """Test that labeled terminals can be grouped."""
        # Simulate labeled terminals
        mock_engine = MagicMock()
        mock_result = Mock()
        mock_result.text = '1'
        mock_result.source = 'pdf'
        mock_engine.find_text.return_value = mock_result

        terminals = [
            {'center': (100, 100), 'radius': 3.0, 'cv': 0.005, 'is_filled': False, 'group_id': 1, 'label': None},
        ]

        # Read labels
        labeled = reader.read_labels(terminals, mock_engine)

        # Group them
        mock_group_engine = MagicMock()
        group_result = Mock()
        group_result.text = '-X1'
        group_result.source = 'pdf'
        mock_group_engine.find_text.return_value = group_result

        grouped = grouper.group_terminals(labeled, mock_group_engine)

        # Verify full_label is created
        assert len(grouped) == 1
        assert 'full_label' in grouped[0]
        assert ':' in grouped[0]['full_label']  # Format: Group:Label


class TestFullDetectionPipeline:
    """Tests for complete Detection -> Reading -> Grouping pipeline."""

    @pytest.fixture
    def detector(self, default_terminal_detector_config):
        """Create detector."""
        with patch.dict('sys.modules', {'external.uvp.src.models': Mock()}):
            from p8_analyzer.detection import TerminalDetector
            return TerminalDetector(config=default_terminal_detector_config)

    @pytest.fixture
    def reader(self):
        """Create reader."""
        from p8_analyzer.detection import TerminalReader
        return TerminalReader()

    @pytest.fixture
    def grouper(self):
        """Create grouper."""
        from p8_analyzer.detection import TerminalGrouper
        return TerminalGrouper()

    def test_full_pipeline_produces_labeled_grouped_terminals(
        self, detector, reader, grouper, sample_vector_analysis_with_terminals
    ):
        """Test full pipeline from detection to grouped terminals."""
        # Step 1: Detect
        detected = detector.detect(sample_vector_analysis_with_terminals)
        assert len(detected) > 0

        # Step 2: Read labels
        mock_read_engine = MagicMock()
        mock_read_engine.find_text.side_effect = [
            Mock(text='1', source='pdf'),
            Mock(text='2', source='pdf'),
        ]
        labeled = reader.read_labels(detected, mock_read_engine)

        # Step 3: Group
        mock_group_engine = MagicMock()
        mock_group_engine.find_text.side_effect = [
            Mock(text='-X1', source='pdf'),
            None,  # Second terminal inherits
        ]
        grouped = grouper.group_terminals(labeled, mock_group_engine)

        # Verify final output
        assert len(grouped) == len(detected)
        for term in grouped:
            assert 'full_label' in term
            assert term['full_label'] is not None

    def test_pipeline_handles_empty_input(self, detector, reader, grouper):
        """Test pipeline handles empty/None input gracefully."""
        # Empty detection
        detected = detector.detect(None)
        assert detected == []

        # Empty reading
        mock_engine = MagicMock()
        labeled = reader.read_labels([], mock_engine)
        assert labeled == []

        # Empty grouping
        grouped = grouper.group_terminals([], mock_engine)
        assert grouped == []

    def test_pipeline_preserves_data_through_stages(
        self, detector, reader, grouper, sample_vector_analysis_with_terminals
    ):
        """Test that data is preserved through all pipeline stages."""
        # Detect
        detected = detector.detect(sample_vector_analysis_with_terminals)
        original_centers = [t['center'] for t in detected]

        # Read
        mock_read_engine = MagicMock()
        mock_read_engine.find_text.return_value = Mock(text='1', source='pdf')
        labeled = reader.read_labels(detected, mock_read_engine)

        # Group
        mock_group_engine = MagicMock()
        mock_group_engine.find_text.return_value = Mock(text='-X1', source='pdf')
        grouped = grouper.group_terminals(labeled, mock_group_engine)

        # Verify centers are preserved
        final_centers = [t['center'] for t in grouped]
        assert original_centers == final_centers


class TestPipelineErrorHandling:
    """Tests for error handling in pipeline."""

    @pytest.fixture
    def detector(self, default_terminal_detector_config):
        """Create detector."""
        with patch.dict('sys.modules', {'external.uvp.src.models': Mock()}):
            from p8_analyzer.detection import TerminalDetector
            return TerminalDetector(config=default_terminal_detector_config)

    @pytest.fixture
    def reader(self):
        """Create reader."""
        from p8_analyzer.detection import TerminalReader
        return TerminalReader()

    @pytest.fixture
    def grouper(self):
        """Create grouper."""
        from p8_analyzer.detection import TerminalGrouper
        return TerminalGrouper()

    def test_pipeline_continues_with_missing_labels(
        self, detector, reader, grouper, sample_vector_analysis_with_terminals
    ):
        """Test pipeline continues when labels are not found."""
        detected = detector.detect(sample_vector_analysis_with_terminals)

        # Reader finds nothing
        mock_read_engine = MagicMock()
        mock_read_engine.find_text.return_value = None
        labeled = reader.read_labels(detected, mock_read_engine)

        # All should have '?' label
        for term in labeled:
            assert term['label'] == '?'

        # Grouper should still work
        mock_group_engine = MagicMock()
        mock_group_engine.find_text.return_value = None
        grouped = grouper.group_terminals(labeled, mock_group_engine)

        # All should have full_label with UNK group
        for term in grouped:
            assert 'UNK' in term['full_label']
            assert '?' in term['full_label']

    def test_pipeline_handles_mixed_success_failure(
        self, detector, reader, grouper, sample_vector_analysis_with_terminals
    ):
        """Test pipeline handles some successes and some failures."""
        detected = detector.detect(sample_vector_analysis_with_terminals)
        assert len(detected) >= 2

        # Reader: first succeeds, second fails
        mock_read_engine = MagicMock()
        mock_read_engine.find_text.side_effect = [
            Mock(text='1', source='pdf'),
            None,
        ]
        labeled = reader.read_labels(detected, mock_read_engine)

        assert labeled[0]['label'] == '1'
        assert labeled[1]['label'] == '?'

        # Grouper: similar pattern
        mock_group_engine = MagicMock()
        mock_group_engine.find_text.side_effect = [
            Mock(text='-X1', source='pdf'),
            None,
        ]
        grouped = grouper.group_terminals(labeled, mock_group_engine)

        assert '-X1:1' == grouped[0]['full_label']
        # Second inherits from first or gets UNK


class TestPipelinePerformance:
    """Performance-related integration tests."""

    @pytest.fixture
    def detector(self):
        """Create detector."""
        with patch.dict('sys.modules', {'external.uvp.src.models': Mock()}):
            from p8_analyzer.detection import TerminalDetector
            return TerminalDetector()

    @pytest.fixture
    def reader(self):
        """Create reader."""
        from p8_analyzer.detection import TerminalReader
        return TerminalReader()

    def test_pipeline_handles_many_terminals(
        self, detector, reader, mock_structural_group_factory
    ):
        """Test pipeline can handle many terminals."""
        # Create group with many circles
        many_circles = [
            {"center_x": 100 + i * 10, "center_y": 100, "radius": 3.0, "cv": 0.005, "is_filled": False}
            for i in range(50)
        ]
        group = mock_structural_group_factory(group_id=1, circle_params=many_circles)

        mock_analysis = Mock()
        mock_analysis.structural_groups = [group]

        # Detect all
        detected = detector.detect(mock_analysis)
        assert len(detected) == 50

        # Read all
        mock_engine = MagicMock()
        mock_engine.find_text.return_value = Mock(text='X', source='pdf')
        labeled = reader.read_labels(detected, mock_engine)
        assert len(labeled) == 50
