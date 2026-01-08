"""
Unit tests for src/terminal_detector.py

Tests the TerminalDetector class which identifies terminal blocks
as unfilled circles matching specific criteria.
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestTerminalDetector:
    """Tests for TerminalDetector class."""

    @pytest.fixture
    def detector(self, default_terminal_detector_config):
        """Create a TerminalDetector instance with default config."""
        # Mock the import since external.uvp.src.models may not exist
        with patch.dict('sys.modules', {'external.uvp.src.models': Mock()}):
            from p8_analyzer.detection import TerminalDetector
            return TerminalDetector(config=default_terminal_detector_config)

    @pytest.fixture
    def detector_custom_config(self):
        """Create a TerminalDetector with custom configuration."""
        with patch.dict('sys.modules', {'external.uvp.src.models': Mock()}):
            from p8_analyzer.detection import TerminalDetector
            return TerminalDetector(config={
                'min_radius': 2.0,
                'max_radius': 4.0,
                'max_cv': 0.02,
                'only_unfilled': False
            })

    def test_detector_initialization_default(self, detector):
        """Test detector initializes with default values."""
        assert detector.min_radius == 2.5
        assert detector.max_radius == 3.5
        assert detector.max_cv == 0.01
        assert detector.only_unfilled is True

    def test_detector_initialization_custom(self, detector_custom_config):
        """Test detector initializes with custom values."""
        assert detector_custom_config.min_radius == 2.0
        assert detector_custom_config.max_radius == 4.0
        assert detector_custom_config.max_cv == 0.02
        assert detector_custom_config.only_unfilled is False

    def test_is_terminal_valid_circle(self, detector, valid_terminal_circle):
        """Test that a valid terminal circle is detected."""
        result = detector._is_terminal(valid_terminal_circle)
        assert result is True

    def test_is_terminal_too_large(self, detector, invalid_terminal_too_large):
        """Test that circles too large are rejected."""
        result = detector._is_terminal(invalid_terminal_too_large)
        assert result is False

    def test_is_terminal_too_small(self, detector, mock_circle_factory):
        """Test that circles too small are rejected."""
        small_circle = mock_circle_factory(
            radius=2.0,  # Below min_radius of 2.5
            cv=0.005,
            is_filled=False
        )
        result = detector._is_terminal(small_circle)
        assert result is False

    def test_is_terminal_filled_rejected(self, detector, invalid_terminal_filled):
        """Test that filled circles are rejected when only_unfilled=True."""
        result = detector._is_terminal(invalid_terminal_filled)
        assert result is False

    def test_is_terminal_filled_accepted_when_disabled(
        self, detector_custom_config, mock_circle_factory
    ):
        """Test that filled circles are accepted when only_unfilled=False."""
        filled_circle = mock_circle_factory(
            radius=3.0,
            cv=0.005,
            is_filled=True
        )
        result = detector_custom_config._is_terminal(filled_circle)
        assert result is True

    def test_is_terminal_high_cv_rejected(self, detector, invalid_terminal_rough):
        """Test that circles with high CV (not round) are rejected."""
        result = detector._is_terminal(invalid_terminal_rough)
        assert result is False

    def test_detect_returns_empty_for_none_input(self, detector):
        """Test detection returns empty list for None input."""
        result = detector.detect(None)
        assert result == []

    def test_detect_returns_empty_for_no_groups(self, detector):
        """Test detection returns empty list when no structural groups."""
        mock_analysis = Mock()
        mock_analysis.structural_groups = []
        result = detector.detect(mock_analysis)
        assert result == []

    def test_detect_finds_valid_terminals(
        self, detector, sample_vector_analysis_with_terminals
    ):
        """Test detection finds valid terminals from analysis result."""
        result = detector.detect(sample_vector_analysis_with_terminals)

        # Should find 2 valid terminals (from group 1)
        # Group 2 has invalid circles (too large and filled)
        assert len(result) == 2

        # Check terminal structure
        for terminal in result:
            assert 'center' in terminal
            assert 'radius' in terminal
            assert 'cv' in terminal
            assert 'is_filled' in terminal
            assert 'group_id' in terminal
            assert 'label' in terminal
            assert terminal['label'] is None  # Not yet labeled

    def test_detect_terminal_center_format(
        self, detector, sample_vector_analysis_with_terminals
    ):
        """Test that terminal centers are in correct tuple format."""
        result = detector.detect(sample_vector_analysis_with_terminals)

        for terminal in result:
            center = terminal['center']
            assert isinstance(center, tuple)
            assert len(center) == 2
            assert isinstance(center[0], (int, float))
            assert isinstance(center[1], (int, float))

    def test_detect_preserves_group_id(
        self, detector, sample_vector_analysis_with_terminals
    ):
        """Test that group_id is preserved in detected terminals."""
        result = detector.detect(sample_vector_analysis_with_terminals)

        # All valid terminals should be from group 1
        for terminal in result:
            assert terminal['group_id'] == 1


class TestTerminalDetectorEdgeCases:
    """Edge case tests for TerminalDetector."""

    @pytest.fixture
    def detector(self, default_terminal_detector_config):
        """Create detector for edge case tests."""
        with patch.dict('sys.modules', {'external.uvp.src.models': Mock()}):
            from p8_analyzer.detection import TerminalDetector
            return TerminalDetector(config=default_terminal_detector_config)

    def test_detect_with_empty_circles_in_group(
        self, detector, mock_structural_group_factory
    ):
        """Test detection with groups that have no circles."""
        group = mock_structural_group_factory(num_circles=0, num_paths=5)
        mock_analysis = Mock()
        mock_analysis.structural_groups = [group]

        result = detector.detect(mock_analysis)
        assert result == []

    def test_boundary_radius_min(self, detector, mock_circle_factory):
        """Test circle at exact minimum radius boundary."""
        circle = mock_circle_factory(radius=2.5, cv=0.005, is_filled=False)
        assert detector._is_terminal(circle) is True

    def test_boundary_radius_max(self, detector, mock_circle_factory):
        """Test circle at exact maximum radius boundary."""
        circle = mock_circle_factory(radius=3.5, cv=0.005, is_filled=False)
        assert detector._is_terminal(circle) is True

    def test_boundary_cv_exact(self, detector, mock_circle_factory):
        """Test circle at exact CV boundary."""
        circle = mock_circle_factory(radius=3.0, cv=0.01, is_filled=False)
        assert detector._is_terminal(circle) is True

    def test_boundary_cv_exceeded(self, detector, mock_circle_factory):
        """Test circle just over CV boundary."""
        circle = mock_circle_factory(radius=3.0, cv=0.011, is_filled=False)
        assert detector._is_terminal(circle) is False
