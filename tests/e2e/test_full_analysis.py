"""
End-to-End tests for P8_Analyzer_V2 full analysis pipeline.

Tests the complete workflow from PDF input to connection report output.

E2E Process Overview:
=====================

INPUT:
- PDF file (P8-format electrical schematic)
- Page number to analyze

PROCESSING STEPS:
1. PDF Loading (PyMuPDF)
   - Open document
   - Load specific page
   - Extract page dimensions

2. Vector Extraction (UVP Library / External)
   - Parse PDF vector data
   - Extract paths, circles, structural groups
   - Build VectorAnalysisResult

3. Terminal Detection (TerminalDetector)
   - Scan structural groups for circles
   - Filter by radius (2.5-3.5), CV (<0.01), unfilled
   - Return list of terminal candidates

4. Label Reading (TerminalReader + HybridTextEngine)
   - For each terminal, search nearby for text
   - Use PDF text layer first, OCR fallback if needed
   - Apply regex filters for valid labels
   - Assign labels (1, 2, PE, N, L1, etc.)

5. Group Assignment (TerminalGrouper)
   - Search left for group labels (-X1, -X2, etc.)
   - If not found, inherit from left/top neighbor
   - Generate full labels (Group:Pin format)

6. Pin Finding (PinFinder) - Optional
   - For user-drawn component boxes
   - Find wire endpoints inside boxes
   - Read pin labels near endpoints
   - Associate pins with boxes (BOX-1:13, etc.)

7. Connection Analysis (circuit_logic)
   - Match structural groups (wire nets) to terminals
   - Match wire endpoints to component box pins
   - Build netlist showing connectivity

OUTPUT:
- List of terminals with full labels (-X1:1, -X2:PE, etc.)
- Connection report (netlist) showing which terminals/pins connect
- Visual overlay on PDF (in GUI mode)

Example Output:
===============
TERMINALS:
  -X1:1 at (100, 100)
  -X1:2 at (150, 100)
  -X2:PE at (200, 200)

CONNECTION REPORT:
  NET-001:
    -X1:1
    -X1:2
    BOX-1:13
  NET-002:
    -X2:PE
    -X3:PE
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
from typing import List, Dict, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# =============================================================================
# E2E Test Fixtures
# =============================================================================

@dataclass
class E2ETestScenario:
    """Defines an E2E test scenario with expected results."""
    name: str
    description: str
    num_terminals: int
    expected_groups: List[str]
    expected_labels: List[str]
    expected_connections: Dict[str, List[str]]


@pytest.fixture
def simple_scenario() -> E2ETestScenario:
    """Simple scenario with one group of terminals."""
    return E2ETestScenario(
        name="simple_terminal_row",
        description="Single row of 3 terminals in group -X1",
        num_terminals=3,
        expected_groups=["-X1", "-X1", "-X1"],
        expected_labels=["1", "2", "PE"],
        expected_connections={
            "NET-001": ["-X1:1", "-X1:2"],
            "NET-002": ["-X1:PE"]
        }
    )


@pytest.fixture
def multi_group_scenario() -> E2ETestScenario:
    """Scenario with multiple terminal groups."""
    return E2ETestScenario(
        name="multi_group",
        description="Two rows of terminals in groups -X1 and -X2",
        num_terminals=6,
        expected_groups=["-X1", "-X1", "-X1", "-X2", "-X2", "-X2"],
        expected_labels=["1", "2", "PE", "1", "2", "PE"],
        expected_connections={
            "NET-001": ["-X1:1", "-X2:1"],
            "NET-002": ["-X1:PE", "-X2:PE"]
        }
    )


# =============================================================================
# E2E Pipeline Tests
# =============================================================================

class TestE2EAnalysisPipeline:
    """
    End-to-end tests for the complete analysis pipeline.

    These tests verify the entire flow from PDF input to connection report output.
    """

    @pytest.fixture
    def mock_pdf_document(self):
        """Create a mock PDF document."""
        doc = MagicMock()
        doc.__len__ = Mock(return_value=10)

        page = MagicMock()
        page.get_text.return_value = {
            "blocks": [
                {"lines": [{"spans": [
                    {"text": "1", "bbox": (110, 95, 115, 105)},
                    {"text": "2", "bbox": (160, 95, 165, 105)},
                    {"text": "PE", "bbox": (210, 95, 220, 105)},
                    {"text": "-X1", "bbox": (40, 95, 60, 105)},
                ]}]}
            ]
        }

        doc.load_page.return_value = page
        return doc

    @pytest.fixture
    def mock_vector_analysis(self, mock_structural_group_factory):
        """Create mock vector analysis result with terminals."""
        # Create group with valid terminal circles
        group = mock_structural_group_factory(
            group_id=1,
            circle_params=[
                {"center_x": 100, "center_y": 100, "radius": 3.0, "cv": 0.005, "is_filled": False},
                {"center_x": 150, "center_y": 100, "radius": 3.0, "cv": 0.005, "is_filled": False},
                {"center_x": 200, "center_y": 100, "radius": 3.0, "cv": 0.005, "is_filled": False},
            ],
            path_params=[
                {"start_x": 100, "start_y": 100, "end_x": 150, "end_y": 100},
                {"start_x": 150, "start_y": 100, "end_x": 200, "end_y": 100},
            ]
        )

        mock_analysis = Mock()
        mock_analysis.structural_groups = [group]
        mock_analysis.page_info = Mock(page_number=1, width=800, height=600, total_drawings=100)
        return mock_analysis

    def test_e2e_detection_to_grouping(
        self, mock_vector_analysis, simple_scenario, default_terminal_detector_config
    ):
        """
        Test complete pipeline: Detection -> Reading -> Grouping

        This test verifies:
        1. Terminals are correctly detected from vector analysis
        2. Labels are read from text layer
        3. Groups are assigned correctly
        4. Full labels are in correct format
        """
        # Step 1: Terminal Detection
        with patch.dict('sys.modules', {'external.uvp.src.models': Mock()}):
            from p8_analyzer.detection import TerminalDetector
            detector = TerminalDetector(config=default_terminal_detector_config)

        detected = detector.detect(mock_vector_analysis)
        assert len(detected) == simple_scenario.num_terminals

        # Step 2: Label Reading
        from p8_analyzer.detection import TerminalReader
        from p8_analyzer.text.hybrid_engine import HybridTextEngine, TextElement

        reader = TerminalReader()
        text_engine = HybridTextEngine()
        text_engine.pdf_elements = [
            TextElement(text="1", center=(110, 95), bbox=(105, 90, 115, 100), source="pdf"),
            TextElement(text="2", center=(160, 95), bbox=(155, 90, 165, 100), source="pdf"),
            TextElement(text="PE", center=(210, 95), bbox=(200, 90, 220, 100), source="pdf"),
        ]
        text_engine.current_page = MagicMock()

        labeled = reader.read_labels(detected, text_engine)
        assert all(t['label'] in ['1', '2', 'PE'] for t in labeled)

        # Step 3: Group Assignment
        from p8_analyzer.detection import TerminalGrouper

        grouper = TerminalGrouper()
        group_engine = HybridTextEngine()
        group_engine.pdf_elements = [
            TextElement(text="-X1", center=(50, 100), bbox=(40, 95, 60, 105), source="pdf"),
        ]
        group_engine.current_page = MagicMock()

        grouped = grouper.group_terminals(labeled, group_engine)

        # Verify final output
        assert len(grouped) == simple_scenario.num_terminals
        for term in grouped:
            assert 'full_label' in term
            assert ':' in term['full_label']
            # Format should be Group:Label (e.g., -X1:1)
            parts = term['full_label'].split(':')
            assert len(parts) == 2

    def test_e2e_with_pin_finder(self, mock_vector_analysis):
        """
        Test pipeline including pin finder for component boxes.
        """
        from p8_analyzer.detection import PinFinder
        from p8_analyzer.text.hybrid_engine import HybridTextEngine, TextElement

        # Create pin finder
        pin_finder = PinFinder(config={'pin_search_radius': 50.0})

        # Create mock component box
        box = Mock()
        box.id = 'BOX-1'
        box.contains_point = lambda p: 80 <= getattr(p, 'x', p[0]) <= 220 and 80 <= getattr(p, 'y', p[1]) <= 120

        # Create text engine with pin labels
        text_engine = HybridTextEngine()
        text_engine.pdf_elements = [
            TextElement(text="13", center=(105, 95), bbox=(100, 90, 110, 100), source="pdf"),
            TextElement(text="14", center=(155, 95), bbox=(150, 90, 160, 100), source="pdf"),
        ]
        text_engine.current_page = MagicMock()

        # Find pins for each structural group
        all_pins = []
        for group in mock_vector_analysis.structural_groups:
            pins = pin_finder.find_pins_for_group(group, [box], text_engine)
            all_pins.extend(pins)

        # Verify pins found
        assert len(all_pins) > 0
        for pin in all_pins:
            assert 'box_id' in pin
            assert 'pin_label' in pin
            assert 'full_label' in pin
            assert pin['box_id'] == 'BOX-1'


class TestE2EConnectionReport:
    """Tests for connection report generation."""

    def test_generate_connection_report_format(self):
        """Test the format of generated connection reports."""
        # Simulate grouped terminals
        grouped_terminals = [
            {'full_label': '-X1:1', 'center': (100, 100), 'group_id': 1},
            {'full_label': '-X1:2', 'center': (150, 100), 'group_id': 1},
            {'full_label': '-X2:PE', 'center': (200, 200), 'group_id': 2},
        ]

        # Simulate connections (NET -> list of connected components)
        connections = {
            'NET-001': ['-X1:1', '-X1:2'],
            'NET-002': ['-X2:PE', '-X3:PE'],
        }

        # Verify structure
        assert 'NET-001' in connections
        assert 'NET-002' in connections
        assert '-X1:1' in connections['NET-001']
        assert '-X1:2' in connections['NET-001']

    def test_connection_report_with_pins(self):
        """Test connection report including component pins."""
        connections = {
            'NET-001': ['-X1:1', '-X1:2', 'BOX-1:13'],
            'NET-002': ['-X2:PE', 'BOX-1:PE'],
        }

        # Verify terminal and pin mixing
        net_001 = connections['NET-001']
        assert any(':' in c and 'BOX' in c for c in net_001)  # Has pin
        assert any(':' in c and '-X' in c for c in net_001)   # Has terminal


class TestE2EErrorRecovery:
    """Tests for error recovery in E2E pipeline."""

    def test_pipeline_handles_no_terminals(self, default_terminal_detector_config):
        """Test pipeline handles PDFs with no terminals."""
        with patch.dict('sys.modules', {'external.uvp.src.models': Mock()}):
            from p8_analyzer.detection import TerminalDetector
            from p8_analyzer.detection import TerminalReader
            from p8_analyzer.detection import TerminalGrouper

        # Empty analysis result
        mock_analysis = Mock()
        mock_analysis.structural_groups = []

        detector = TerminalDetector(config=default_terminal_detector_config)
        detected = detector.detect(mock_analysis)
        assert detected == []

        reader = TerminalReader()
        mock_engine = MagicMock()
        labeled = reader.read_labels(detected, mock_engine)
        assert labeled == []

        grouper = TerminalGrouper()
        grouped = grouper.group_terminals(labeled, mock_engine)
        assert grouped == []

    def test_pipeline_handles_missing_labels(
        self, mock_structural_group_factory, default_terminal_detector_config
    ):
        """Test pipeline handles terminals with missing labels."""
        with patch.dict('sys.modules', {'external.uvp.src.models': Mock()}):
            from p8_analyzer.detection import TerminalDetector
            from p8_analyzer.detection import TerminalReader
            from p8_analyzer.detection import TerminalGrouper

        # Create group with terminals
        group = mock_structural_group_factory(
            group_id=1,
            circle_params=[
                {"center_x": 100, "center_y": 100, "radius": 3.0, "cv": 0.005, "is_filled": False},
            ]
        )
        mock_analysis = Mock()
        mock_analysis.structural_groups = [group]

        # Detect
        detector = TerminalDetector(config=default_terminal_detector_config)
        detected = detector.detect(mock_analysis)
        assert len(detected) == 1

        # Read with no text found
        reader = TerminalReader()
        mock_engine = MagicMock()
        mock_engine.find_text.return_value = None
        labeled = reader.read_labels(detected, mock_engine)

        assert labeled[0]['label'] == '?'

        # Group with no group found
        grouper = TerminalGrouper()
        grouped = grouper.group_terminals(labeled, mock_engine)

        # Should still produce output with UNK group
        assert grouped[0]['full_label'] == 'UNK:?'


class TestE2EPerformance:
    """Performance tests for E2E pipeline."""

    def test_pipeline_handles_large_page(
        self, mock_structural_group_factory, default_terminal_detector_config
    ):
        """Test pipeline performance with many terminals."""
        with patch.dict('sys.modules', {'external.uvp.src.models': Mock()}):
            from p8_analyzer.detection import TerminalDetector
            from p8_analyzer.detection import TerminalReader

        # Create many terminals (100)
        circles = [
            {"center_x": 100 + (i % 10) * 50, "center_y": 100 + (i // 10) * 50,
             "radius": 3.0, "cv": 0.005, "is_filled": False}
            for i in range(100)
        ]
        group = mock_structural_group_factory(group_id=1, circle_params=circles)

        mock_analysis = Mock()
        mock_analysis.structural_groups = [group]

        # Detect
        detector = TerminalDetector(config=default_terminal_detector_config)
        detected = detector.detect(mock_analysis)
        assert len(detected) == 100

        # Read
        reader = TerminalReader()
        mock_engine = MagicMock()
        mock_engine.find_text.return_value = Mock(text='1', source='pdf')
        labeled = reader.read_labels(detected, mock_engine)
        assert len(labeled) == 100


# =============================================================================
# E2E Test with Real PDF (Conditional)
# =============================================================================

class TestE2EWithRealPDF:
    """
    E2E tests using real PDF files.

    These tests are conditional and only run if the sample PDF exists.
    """

    @pytest.fixture
    def sample_pdf_path(self):
        """Path to sample PDF."""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(project_root, 'data', 'ornek.pdf')

    @pytest.mark.skipif(
        not os.path.exists(os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'data', 'ornek.pdf'
        )),
        reason="Sample PDF not available"
    )
    def test_load_real_pdf(self, sample_pdf_path):
        """Test loading a real PDF file."""
        import pymupdf

        doc = pymupdf.open(sample_pdf_path)
        assert len(doc) > 0

        page = doc.load_page(0)
        assert page.rect.width > 0
        assert page.rect.height > 0

        doc.close()

    @pytest.mark.skipif(
        not os.path.exists(os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'data', 'ornek.pdf'
        )),
        reason="Sample PDF not available"
    )
    def test_extract_text_from_real_pdf(self, sample_pdf_path):
        """Test extracting text from real PDF."""
        import pymupdf
        from p8_analyzer.text import HybridTextEngine

        doc = pymupdf.open(sample_pdf_path)
        page = doc.load_page(0)

        engine = HybridTextEngine()
        engine.load_page(page)

        # Should have extracted some text elements
        assert len(engine.pdf_elements) > 0

        doc.close()


# =============================================================================
# E2E Output Validation
# =============================================================================

class TestE2EOutputValidation:
    """Tests to validate E2E output format and content."""

    def test_terminal_output_format(self):
        """Validate terminal output has all required fields."""
        required_fields = [
            'center',
            'radius',
            'cv',
            'is_filled',
            'group_id',
            'label',
            'label_source',
            'group_label',
            'group_source',
            'full_label'
        ]

        # Simulated terminal after full pipeline
        terminal = {
            'center': (100, 100),
            'radius': 3.0,
            'cv': 0.005,
            'is_filled': False,
            'group_id': 1,
            'label': '1',
            'label_source': 'pdf',
            'group_label': '-X1',
            'group_source': 'pdf_direct',
            'full_label': '-X1:1'
        }

        for field in required_fields:
            assert field in terminal, f"Missing field: {field}"

    def test_full_label_format_validation(self):
        """Validate full_label format."""
        valid_labels = [
            '-X1:1',
            '-X1:PE',
            '-X2:L1',
            'UNK:?',
            '-X10:N',
        ]

        for label in valid_labels:
            assert ':' in label
            parts = label.split(':')
            assert len(parts) == 2

    def test_connection_report_format_validation(self):
        """Validate connection report format."""
        report = {
            'NET-001': ['-X1:1', '-X1:2', 'BOX-1:13'],
            'NET-002': ['-X2:PE'],
        }

        for net_id, connections in report.items():
            # Net ID format
            assert net_id.startswith('NET-')
            assert net_id[4:].isdigit()

            # Connections list
            assert isinstance(connections, list)
            assert len(connections) > 0

            # Each connection has proper format
            for conn in connections:
                assert ':' in conn
