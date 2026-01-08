"""
Unit tests for src/models.py

Tests the Pydantic data models used throughout the application.
"""
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from p8_analyzer.core import (
    Point,
    AnalysisConfig,
    Circle,
    PathElement,
    StructuralGroup,
    PageInfo,
    AnalysisStatistics,
    VectorAnalysisResult,
    ExportOptions,
    DEFAULT_CONFIG
)


class TestPoint:
    """Tests for Point model."""

    def test_point_creation(self):
        """Test basic Point creation."""
        point = Point(x=10.5, y=20.3)
        assert point.x == 10.5
        assert point.y == 20.3

    def test_point_with_zero_coordinates(self):
        """Test Point at origin."""
        point = Point(x=0.0, y=0.0)
        assert point.x == 0.0
        assert point.y == 0.0

    def test_point_with_negative_coordinates(self):
        """Test Point with negative values."""
        point = Point(x=-15.5, y=-25.3)
        assert point.x == -15.5
        assert point.y == -25.3


class TestAnalysisConfig:
    """Tests for AnalysisConfig model."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = AnalysisConfig()
        assert config.target_angle == 90.0
        assert config.angle_tolerance == 1.0
        assert config.min_radius is None or hasattr(config, 'min_radius') is False  # May not exist
        assert config.min_line_length == 10.0

    def test_custom_config_values(self):
        """Test custom configuration values."""
        config = AnalysisConfig(
            target_angle=45.0,
            angle_tolerance=2.0,
            extension_length=20.0
        )
        assert config.target_angle == 45.0
        assert config.angle_tolerance == 2.0
        assert config.extension_length == 20.0

    def test_get_summary(self):
        """Test config summary generation."""
        config = AnalysisConfig()
        summary = config.get_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0


class TestCircle:
    """Tests for Circle model."""

    def test_circle_creation(self):
        """Test basic Circle creation."""
        circle = Circle(
            index=0,
            center=Point(x=100, y=100),
            radius=3.0,
            coefficient_of_variation=0.005,
            segments=12,
            is_closed=True,
            is_filled=False
        )
        assert circle.index == 0
        assert circle.center.x == 100
        assert circle.center.y == 100
        assert circle.radius == 3.0
        assert circle.coefficient_of_variation == 0.005
        assert circle.is_filled is False

    def test_circle_contains_point_inside(self):
        """Test point containment - point inside circle."""
        circle = Circle(
            index=0,
            center=Point(x=100, y=100),
            radius=10.0,
            coefficient_of_variation=0.005,
            segments=12,
            is_closed=True,
            is_filled=False
        )
        # Point at center
        assert circle.contains_point(Point(x=100, y=100)) is True
        # Point near center
        assert circle.contains_point(Point(x=105, y=100)) is True

    def test_circle_contains_point_outside(self):
        """Test point containment - point outside circle."""
        circle = Circle(
            index=0,
            center=Point(x=100, y=100),
            radius=10.0,
            coefficient_of_variation=0.005,
            segments=12,
            is_closed=True,
            is_filled=False
        )
        # Point far outside
        assert circle.contains_point(Point(x=200, y=200)) is False

    def test_circle_contains_point_with_tolerance(self):
        """Test point containment with tolerance."""
        circle = Circle(
            index=0,
            center=Point(x=100, y=100),
            radius=10.0,
            coefficient_of_variation=0.005,
            segments=12,
            is_closed=True,
            is_filled=False
        )
        # Point just outside but within tolerance
        assert circle.contains_point(Point(x=112, y=100), tolerance=5.0) is True

    def test_circle_contains_tuple_point(self):
        """Test point containment with tuple coordinates."""
        circle = Circle(
            index=0,
            center=Point(x=100, y=100),
            radius=10.0,
            coefficient_of_variation=0.005,
            segments=12,
            is_closed=True,
            is_filled=False
        )
        assert circle.contains_point((100, 100)) is True
        assert circle.contains_point((200, 200)) is False


class TestPathElement:
    """Tests for PathElement model."""

    def test_path_element_creation(self):
        """Test basic PathElement creation."""
        path = PathElement(
            index=0,
            type="path",
            path_data="M0,0 L100,0",
            start_point=Point(x=0, y=0),
            end_point=Point(x=100, y=0)
        )
        assert path.index == 0
        assert path.type == "path"
        assert path.start_point.x == 0
        assert path.end_point.x == 100

    def test_path_element_with_length(self):
        """Test PathElement with length calculated."""
        path = PathElement(
            index=0,
            type="path",
            path_data="M0,0 L100,0",
            start_point=Point(x=0, y=0),
            end_point=Point(x=100, y=0),
            length=100.0
        )
        assert path.length == 100.0


class TestStructuralGroup:
    """Tests for StructuralGroup model."""

    def test_structural_group_creation(self):
        """Test basic StructuralGroup creation."""
        group = StructuralGroup(
            group_id=1,
            color="#FF0000",
            elements=[],
            circles=[]
        )
        assert group.group_id == 1
        assert group.color == "#FF0000"
        assert len(group.elements) == 0
        assert len(group.circles) == 0

    def test_structural_group_with_elements(self):
        """Test StructuralGroup with path elements."""
        path = PathElement(
            index=0,
            type="path",
            path_data="M0,0 L100,0",
            start_point=Point(x=0, y=0),
            end_point=Point(x=100, y=0)
        )
        group = StructuralGroup(
            group_id=1,
            color="#FF0000",
            elements=[path],
            circles=[]
        )
        assert len(group.elements) == 1

    def test_structural_group_bounding_box(self):
        """Test bounding box calculation."""
        path = PathElement(
            index=0,
            type="path",
            path_data="M0,0 L100,50",
            start_point=Point(x=0, y=0),
            end_point=Point(x=100, y=50)
        )
        group = StructuralGroup(
            group_id=1,
            color="#FF0000",
            elements=[path],
            circles=[]
        )
        bbox = group.calculate_bounding_box()
        assert bbox['min_x'] == 0
        assert bbox['max_x'] == 100
        assert bbox['min_y'] == 0
        assert bbox['max_y'] == 50


class TestPageInfo:
    """Tests for PageInfo model."""

    def test_page_info_creation(self):
        """Test basic PageInfo creation."""
        info = PageInfo(
            page_number=1,
            width=800.0,
            height=600.0,
            total_drawings=50
        )
        assert info.page_number == 1
        assert info.width == 800.0
        assert info.height == 600.0
        assert info.total_drawings == 50


class TestAnalysisStatistics:
    """Tests for AnalysisStatistics model."""

    def test_statistics_creation(self):
        """Test basic AnalysisStatistics creation."""
        stats = AnalysisStatistics(
            total_elements=100,
            total_circles=20,
            total_paths=80,
            structural_groups=5,
            text_like_groups=2,
            single_elements=10,
            broken_connections=3,
            total_groups=7
        )
        assert stats.total_elements == 100
        assert stats.total_circles == 20
        assert stats.total_groups == 7


class TestExportOptions:
    """Tests for ExportOptions model."""

    def test_default_export_options(self):
        """Test default export options."""
        options = ExportOptions()
        assert options.create_svg is True
        assert options.create_png is True
        assert options.create_json is True
        assert options.png_scale_factor == 4.0

    def test_custom_export_options(self):
        """Test custom export options."""
        options = ExportOptions(
            create_svg=False,
            png_scale_factor=2.0,
            output_prefix="custom"
        )
        assert options.create_svg is False
        assert options.png_scale_factor == 2.0
        assert options.output_prefix == "custom"


class TestDefaultConfig:
    """Tests for DEFAULT_CONFIG constant."""

    def test_default_config_exists(self):
        """Test that DEFAULT_CONFIG is available."""
        assert DEFAULT_CONFIG is not None
        assert isinstance(DEFAULT_CONFIG, AnalysisConfig)
