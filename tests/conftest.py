"""
Shared pytest fixtures for P8_Analyzer_V2 test suite.

This file provides common test fixtures used across unit, integration, and e2e tests.
Fixtures are organized hierarchically to support different testing levels.
"""
import os
import sys
import pytest
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
from typing import List, Dict, Optional

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# =============================================================================
# Mock Data Classes (Simulating external.uvp.src.models)
# =============================================================================

@dataclass
class MockPoint:
    """Mock Point class for testing."""
    x: float
    y: float


@dataclass
class MockCircle:
    """Mock Circle class for testing terminal detection."""
    index: int
    center: MockPoint
    radius: float
    coefficient_of_variation: float
    segments: int
    is_closed: bool
    is_filled: bool
    fill_color: Optional[str] = None
    drawing_data: Optional[Dict] = None

    def contains_point(self, point, tolerance: float = 0.0) -> bool:
        px = point.x if hasattr(point, 'x') else point[0]
        py = point.y if hasattr(point, 'y') else point[1]
        dist = ((self.center.x - px)**2 + (self.center.y - py)**2)**0.5
        return dist <= self.radius + tolerance


@dataclass
class MockPathElement:
    """Mock PathElement class for testing."""
    index: int
    type: str
    path_data: str
    start_point: MockPoint
    end_point: MockPoint
    length: Optional[float] = None
    direction_angle: Optional[float] = None


@dataclass
class MockStructuralGroup:
    """Mock StructuralGroup class for testing."""
    group_id: int
    color: str
    elements: List[MockPathElement]
    circles: List[MockCircle]
    has_long_lines: bool = True
    group_type: str = "structural"
    total_length: Optional[float] = None
    bounding_box: Optional[Dict[str, float]] = None

    def calculate_bounding_box(self) -> Dict[str, float]:
        if self.bounding_box is None:
            xs = [e.start_point.x for e in self.elements] + [e.end_point.x for e in self.elements]
            ys = [e.start_point.y for e in self.elements] + [e.end_point.y for e in self.elements]
            for c in self.circles:
                xs.extend([c.center.x - c.radius, c.center.x + c.radius])
                ys.extend([c.center.y - c.radius, c.center.y + c.radius])

            if xs and ys:
                self.bounding_box = {"min_x": min(xs), "max_x": max(xs), "min_y": min(ys), "max_y": max(ys)}
            else:
                self.bounding_box = {"min_x": 0, "max_x": 0, "min_y": 0, "max_y": 0}
        return self.bounding_box


@dataclass
class MockPageInfo:
    """Mock PageInfo class for testing."""
    page_number: int
    width: float
    height: float
    total_drawings: int
    area: Optional[float] = None


@dataclass
class MockAnalysisStatistics:
    """Mock AnalysisStatistics class for testing."""
    total_elements: int
    total_circles: int
    total_paths: int
    structural_groups: int
    text_like_groups: int
    single_elements: int
    broken_connections: int
    total_groups: int
    definitive_circles: int = 0
    potential_circles: int = 0


@dataclass
class MockAnalysisConfig:
    """Mock AnalysisConfig class for testing."""
    target_angle: float = 90.0
    angle_tolerance: float = 1.0
    min_circle_segments: int = 8


@dataclass
class MockVectorAnalysisResult:
    """Mock VectorAnalysisResult class for testing."""
    page_info: MockPageInfo
    all_circles: List[MockCircle]
    all_paths: List[MockPathElement]
    structural_groups: List[MockStructuralGroup]
    text_like_groups: List[MockStructuralGroup]
    single_elements: List[MockPathElement]
    broken_connections: List
    statistics: MockAnalysisStatistics
    config: MockAnalysisConfig
    analysis_timestamp: Optional[str] = None


# =============================================================================
# Fixtures: Mock Data Factory
# =============================================================================

@pytest.fixture
def mock_point_factory():
    """Factory fixture to create MockPoint instances."""
    def _create(x: float, y: float) -> MockPoint:
        return MockPoint(x=x, y=y)
    return _create


@pytest.fixture
def mock_circle_factory(mock_point_factory):
    """Factory fixture to create MockCircle instances."""
    def _create(
        index: int = 0,
        center_x: float = 100.0,
        center_y: float = 100.0,
        radius: float = 3.0,
        cv: float = 0.005,
        is_filled: bool = False
    ) -> MockCircle:
        return MockCircle(
            index=index,
            center=mock_point_factory(center_x, center_y),
            radius=radius,
            coefficient_of_variation=cv,
            segments=12,
            is_closed=True,
            is_filled=is_filled
        )
    return _create


@pytest.fixture
def mock_path_factory(mock_point_factory):
    """Factory fixture to create MockPathElement instances."""
    def _create(
        index: int = 0,
        start_x: float = 0.0,
        start_y: float = 0.0,
        end_x: float = 100.0,
        end_y: float = 0.0
    ) -> MockPathElement:
        return MockPathElement(
            index=index,
            type="path",
            path_data=f"M{start_x},{start_y} L{end_x},{end_y}",
            start_point=mock_point_factory(start_x, start_y),
            end_point=mock_point_factory(end_x, end_y),
            length=((end_x - start_x)**2 + (end_y - start_y)**2)**0.5
        )
    return _create


@pytest.fixture
def mock_structural_group_factory(mock_circle_factory, mock_path_factory):
    """Factory fixture to create MockStructuralGroup instances."""
    def _create(
        group_id: int = 1,
        num_circles: int = 0,
        num_paths: int = 1,
        circle_params: List[Dict] = None,
        path_params: List[Dict] = None
    ) -> MockStructuralGroup:
        circles = []
        paths = []

        if circle_params:
            for i, params in enumerate(circle_params):
                circles.append(mock_circle_factory(index=i, **params))
        else:
            for i in range(num_circles):
                circles.append(mock_circle_factory(index=i, center_x=100+i*50, center_y=100))

        if path_params:
            for i, params in enumerate(path_params):
                paths.append(mock_path_factory(index=i, **params))
        else:
            for i in range(num_paths):
                paths.append(mock_path_factory(index=i, start_x=i*100, end_x=(i+1)*100))

        return MockStructuralGroup(
            group_id=group_id,
            color="#FF0000",
            elements=paths,
            circles=circles
        )
    return _create


# =============================================================================
# Fixtures: Terminal Detection
# =============================================================================

@pytest.fixture
def valid_terminal_circle(mock_circle_factory) -> MockCircle:
    """A circle that matches terminal detection criteria."""
    return mock_circle_factory(
        index=0,
        center_x=100.0,
        center_y=100.0,
        radius=3.0,  # Within 2.5-3.5 range
        cv=0.005,    # Below 0.01 threshold
        is_filled=False  # Unfilled
    )


@pytest.fixture
def invalid_terminal_too_large(mock_circle_factory) -> MockCircle:
    """A circle that's too large to be a terminal."""
    return mock_circle_factory(
        index=1,
        center_x=200.0,
        center_y=100.0,
        radius=5.0,  # Exceeds 3.5 max
        cv=0.005,
        is_filled=False
    )


@pytest.fixture
def invalid_terminal_filled(mock_circle_factory) -> MockCircle:
    """A filled circle (not a terminal)."""
    return mock_circle_factory(
        index=2,
        center_x=300.0,
        center_y=100.0,
        radius=3.0,
        cv=0.005,
        is_filled=True  # Filled circles are not terminals
    )


@pytest.fixture
def invalid_terminal_rough(mock_circle_factory) -> MockCircle:
    """A circle with high CV (not round enough)."""
    return mock_circle_factory(
        index=3,
        center_x=400.0,
        center_y=100.0,
        radius=3.0,
        cv=0.05,  # Exceeds 0.01 threshold
        is_filled=False
    )


@pytest.fixture
def sample_vector_analysis_with_terminals(
    valid_terminal_circle,
    invalid_terminal_too_large,
    mock_structural_group_factory
) -> MockVectorAnalysisResult:
    """A complete VectorAnalysisResult with mixed terminal candidates."""
    group_with_valid = mock_structural_group_factory(
        group_id=1,
        circle_params=[
            {"center_x": 100, "center_y": 100, "radius": 3.0, "cv": 0.005, "is_filled": False},
            {"center_x": 150, "center_y": 100, "radius": 3.0, "cv": 0.005, "is_filled": False},
        ]
    )

    group_with_invalid = mock_structural_group_factory(
        group_id=2,
        circle_params=[
            {"center_x": 200, "center_y": 200, "radius": 5.0, "cv": 0.005, "is_filled": False},  # Too large
            {"center_x": 250, "center_y": 200, "radius": 3.0, "cv": 0.005, "is_filled": True},   # Filled
        ]
    )

    return MockVectorAnalysisResult(
        page_info=MockPageInfo(page_number=1, width=800, height=600, total_drawings=100),
        all_circles=[],
        all_paths=[],
        structural_groups=[group_with_valid, group_with_invalid],
        text_like_groups=[],
        single_elements=[],
        broken_connections=[],
        statistics=MockAnalysisStatistics(
            total_elements=10, total_circles=4, total_paths=6,
            structural_groups=2, text_like_groups=0, single_elements=0,
            broken_connections=0, total_groups=2
        ),
        config=MockAnalysisConfig()
    )


# =============================================================================
# Fixtures: Text Engine
# =============================================================================

@pytest.fixture
def mock_text_element():
    """Factory for creating mock text elements."""
    def _create(text: str, center_x: float, center_y: float, source: str = 'pdf'):
        return {
            'text': text,
            'center': (center_x, center_y),
            'bbox': (center_x - 10, center_y - 5, center_x + 10, center_y + 5),
            'source': source,
            'confidence': 1.0
        }
    return _create


@pytest.fixture
def mock_text_engine(mock_text_element):
    """Mock HybridTextEngine with predefined text elements."""
    engine = MagicMock()

    # Simulate PDF text elements
    engine.pdf_elements = [
        type('TextElement', (), {
            'text': '1',
            'center': (110, 95),
            'bbox': (105, 90, 115, 100),
            'source': 'pdf',
            'confidence': 1.0
        })(),
        type('TextElement', (), {
            'text': '2',
            'center': (160, 95),
            'bbox': (155, 90, 165, 100),
            'source': 'pdf',
            'confidence': 1.0
        })(),
        type('TextElement', (), {
            'text': '-X1',
            'center': (50, 100),
            'bbox': (40, 95, 60, 105),
            'source': 'pdf',
            'confidence': 1.0
        })(),
        type('TextElement', (), {
            'text': 'PE',
            'center': (210, 95),
            'bbox': (200, 90, 220, 100),
            'source': 'pdf',
            'confidence': 1.0
        })(),
    ]

    return engine


# =============================================================================
# Fixtures: Terminal Data
# =============================================================================

@pytest.fixture
def sample_terminals():
    """Sample terminal list for grouping tests."""
    return [
        {'center': (100, 100), 'radius': 3.0, 'cv': 0.005, 'is_filled': False, 'group_id': 1, 'label': '1'},
        {'center': (150, 100), 'radius': 3.0, 'cv': 0.005, 'is_filled': False, 'group_id': 1, 'label': '2'},
        {'center': (200, 100), 'radius': 3.0, 'cv': 0.005, 'is_filled': False, 'group_id': 1, 'label': 'PE'},
        {'center': (100, 200), 'radius': 3.0, 'cv': 0.005, 'is_filled': False, 'group_id': 2, 'label': '1'},
        {'center': (150, 200), 'radius': 3.0, 'cv': 0.005, 'is_filled': False, 'group_id': 2, 'label': '2'},
    ]


@pytest.fixture
def sample_terminals_unlabeled():
    """Sample terminals without labels (for reader tests)."""
    return [
        {'center': (100, 100), 'radius': 3.0, 'cv': 0.005, 'is_filled': False, 'group_id': 1, 'label': None},
        {'center': (150, 100), 'radius': 3.0, 'cv': 0.005, 'is_filled': False, 'group_id': 1, 'label': None},
    ]


# =============================================================================
# Fixtures: Component Boxes (for Pin Finder)
# =============================================================================

@pytest.fixture
def mock_component_box():
    """Factory for creating mock component boxes."""
    def _create(box_id: str, min_x: float, min_y: float, max_x: float, max_y: float):
        box = MagicMock()
        box.id = box_id
        box.bbox = {'min_x': min_x, 'min_y': min_y, 'max_x': max_x, 'max_y': max_y}

        def contains_point(point):
            px = point.x if hasattr(point, 'x') else point[0]
            py = point.y if hasattr(point, 'y') else point[1]
            return min_x <= px <= max_x and min_y <= py <= max_y

        box.contains_point = contains_point
        return box
    return _create


@pytest.fixture
def sample_component_boxes(mock_component_box):
    """Sample component boxes for pin finder tests."""
    return [
        mock_component_box('BOX-1', 50, 50, 150, 150),
        mock_component_box('BOX-2', 200, 50, 300, 150),
    ]


# =============================================================================
# Fixtures: File Paths
# =============================================================================

@pytest.fixture
def sample_pdf_path():
    """Path to sample PDF file."""
    return os.path.join(PROJECT_ROOT, 'data', 'ornek.pdf')


@pytest.fixture
def test_fixtures_path():
    """Path to test fixtures directory."""
    return os.path.join(PROJECT_ROOT, 'tests', 'fixtures')


# =============================================================================
# Fixtures: Configuration
# =============================================================================

@pytest.fixture
def default_terminal_detector_config():
    """Default configuration for TerminalDetector."""
    return {
        'min_radius': 2.5,
        'max_radius': 3.5,
        'max_cv': 0.01,
        'only_unfilled': True
    }


@pytest.fixture
def default_terminal_reader_config():
    """Default configuration for TerminalReader."""
    return {
        'direction': 'top_right',
        'search_radius': 20.0,
        'y_tolerance': 15.0
    }


@pytest.fixture
def default_terminal_grouper_config():
    """Default configuration for TerminalGrouper."""
    return {
        'search_direction': 'left',
        'search_radius': 100.0,
        'y_tolerance': 15.0,
        'label_pattern': r'^-?X.*',
        'neighbor_x_distance': 50.0
    }


@pytest.fixture
def default_pin_finder_config():
    """Default configuration for PinFinder."""
    return {
        'pin_search_radius': 75.0
    }
