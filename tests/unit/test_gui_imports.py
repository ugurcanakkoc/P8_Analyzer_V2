"""
Unit tests for GUI import paths.

These tests verify that all modules required by the GUI can be imported
without errors, which is a common source of GUI crashes.
"""
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestGUIImports:
    """Tests for GUI module imports."""

    def test_core_imports(self):
        """Test core module imports."""
        from p8_analyzer.core import analyze_page_vectors, DEFAULT_CONFIG
        assert analyze_page_vectors is not None
        assert DEFAULT_CONFIG is not None

    def test_core_models_imports(self):
        """Test core models imports."""
        from p8_analyzer.core.models import (
            Point, AnalysisConfig, Circle, PathElement,
            StructuralGroup, PageInfo, AnalysisStatistics,
            VectorAnalysisResult, ExportOptions
        )
        assert VectorAnalysisResult is not None

    def test_core_session_imports(self):
        """Test core session imports."""
        from p8_analyzer.core.session import (
            WireAnnotation, WireAnnotationType, Terminal, Pin,
            Component, Connection, PageAnalysis, SessionMetadata,
            AnalysisSummary, AnalysisSession, classify_annotation,
            ANNOTATION_PATTERNS, create_session
        )
        assert AnalysisSession is not None
        assert classify_annotation is not None

    def test_detection_imports(self):
        """Test detection module imports."""
        from p8_analyzer.detection import (
            TerminalDetector, TerminalReader, TerminalGrouper,
            PinFinder, LabelMatcher, BusbarFinder, ComponentNamer,
            ClusterDetector, get_default_settings
        )
        assert TerminalDetector is not None
        assert ClusterDetector is not None

    def test_wire_annotation_reader_imports(self):
        """Test wire annotation reader imports."""
        from p8_analyzer.detection import (
            WireAnnotationReader, WireAnnotationConfig,
            find_connected_paths, create_cardinal_paths
        )
        assert WireAnnotationReader is not None

    def test_text_engine_imports(self):
        """Test text engine imports."""
        from p8_analyzer.text import HybridTextEngine, SearchProfile, SearchDirection
        assert HybridTextEngine is not None
        assert SearchDirection is not None

    def test_circuit_imports(self):
        """Test circuit module imports."""
        from p8_analyzer.circuit import check_intersections, CircuitComponent
        assert check_intersections is not None
        assert CircuitComponent is not None

    def test_gui_worker_imports(self):
        """Test GUI worker module imports."""
        from p8_analyzer.gui.worker import AnalysisWorker
        assert AnalysisWorker is not None

    def test_gui_viewer_imports(self):
        """Test GUI viewer module imports."""
        from p8_analyzer.gui.viewer import InteractiveGraphicsView
        assert InteractiveGraphicsView is not None

    def test_gui_main_window_imports(self):
        """Test GUI main_window module imports."""
        from p8_analyzer.gui.main_window import MainWindow
        assert MainWindow is not None


class TestSessionDataStructures:
    """Tests that session data structures work correctly."""

    def test_wire_annotation_type_enum(self):
        """WireAnnotationType enum has all expected values."""
        from p8_analyzer.core.session import WireAnnotationType

        assert WireAnnotationType.SIGNAL_NAME.value == "signal_name"
        assert WireAnnotationType.DESTINATION_REF.value == "destination"
        assert WireAnnotationType.WIRE_SPEC.value == "wire_spec"
        assert WireAnnotationType.COLOR_CODE.value == "color_code"
        assert WireAnnotationType.COMPONENT_REF.value == "component_ref"
        assert WireAnnotationType.UNKNOWN.value == "unknown"

    def test_classify_annotation_function(self):
        """classify_annotation correctly identifies annotation types."""
        from p8_analyzer.core.session import classify_annotation, WireAnnotationType

        # Signal names
        assert classify_annotation("P24") == WireAnnotationType.SIGNAL_NAME
        assert classify_annotation("N24") == WireAnnotationType.SIGNAL_NAME
        assert classify_annotation("PE") == WireAnnotationType.SIGNAL_NAME
        assert classify_annotation("L1") == WireAnnotationType.SIGNAL_NAME
        assert classify_annotation("L+") == WireAnnotationType.SIGNAL_NAME

        # Destination refs
        assert classify_annotation("/6.4") == WireAnnotationType.DESTINATION_REF
        assert classify_annotation("/13.34") == WireAnnotationType.DESTINATION_REF

        # Color codes
        assert classify_annotation("WH") == WireAnnotationType.COLOR_CODE
        assert classify_annotation("BN") == WireAnnotationType.COLOR_CODE

        # Component refs
        assert classify_annotation("=070") == WireAnnotationType.COMPONENT_REF

        # Unknown
        assert classify_annotation("random") == WireAnnotationType.UNKNOWN

    def test_wire_annotation_creation(self):
        """WireAnnotation can be created and serialized."""
        from p8_analyzer.core.session import WireAnnotation, WireAnnotationType

        ann = WireAnnotation(
            text="P24",
            position_x=100.0,
            position_y=200.0,
            annotation_type=WireAnnotationType.SIGNAL_NAME,
            distance_to_terminal=50.0,
            direction="left"
        )

        assert ann.text == "P24"
        assert ann.annotation_type == WireAnnotationType.SIGNAL_NAME

        # Test serialization
        data = ann.model_dump()
        assert data['text'] == "P24"
        assert data['annotation_type'] == "signal_name"

    def test_terminal_from_dict(self):
        """Terminal.from_dict creates Terminal from legacy dict format."""
        from p8_analyzer.core.session import Terminal

        legacy_dict = {
            'center': (100.0, 200.0),
            'radius': 3.0,
            'label': '5',
            'group_label': '-X1',
            'full_label': '-X1:5',
            'label_source': 'pdf',
            'group_source': 'pdf_direct',
            'group_id': 42
        }

        terminal = Terminal.from_dict(legacy_dict, page_number=11)

        assert terminal.center_x == 100.0
        assert terminal.center_y == 200.0
        assert terminal.radius == 3.0
        assert terminal.label == '5'
        assert terminal.group_label == '-X1'
        assert terminal.full_label == '-X1:5'
        assert terminal.structural_group_id == 42

    def test_page_analysis_creation(self):
        """PageAnalysis can be created and serialized."""
        from p8_analyzer.core.session import PageAnalysis, Terminal, Component

        page = PageAnalysis(
            page_number=11,
            page_width=800.0,
            page_height=600.0,
            structural_group_count=25
        )

        assert page.page_number == 11
        assert page.terminals == []
        assert page.components == []
        assert page.connections == []

        # Test serialization
        data = page.model_dump()
        assert data['page_number'] == 11

    def test_analysis_session_workflow(self):
        """AnalysisSession can be created, pages added, and summary computed."""
        from p8_analyzer.core.session import (
            create_session, PageAnalysis, Terminal
        )

        # Create session
        session = create_session("test.pdf", 100)
        assert session.metadata.pdf_name == "test.pdf"
        assert session.metadata.total_pages == 100

        # Add page
        page = PageAnalysis(
            page_number=11,
            page_width=800.0,
            page_height=600.0
        )
        page.terminals.append(Terminal(
            id="test_terminal",
            center_x=100.0,
            center_y=200.0,
            radius=3.0,
            full_label="-X1:5"
        ))

        session.add_page(page)

        assert 11 in session.pages
        assert session.summary.total_terminals == 1


class TestAnalysisEngineImports:
    """Tests for AnalysisEngine imports."""

    def test_analysis_engine_import(self):
        """AnalysisEngine can be imported."""
        from p8_analyzer.core.analysis_engine import AnalysisEngine
        assert AnalysisEngine is not None

    def test_analysis_engine_methods_exist(self):
        """AnalysisEngine has all required methods."""
        from p8_analyzer.core.analysis_engine import AnalysisEngine

        engine = AnalysisEngine()

        # Core method
        assert hasattr(engine, 'analyze_page')

        # Endpoint label detection methods
        assert hasattr(engine, '_detect_endpoint_labels')
        assert hasattr(engine, '_find_structural_group_for_point')
        assert hasattr(engine, '_order_along_wire_path')
        assert hasattr(engine, '_get_cluster_object_points')
        assert hasattr(engine, '_is_valid_pin_label')


class TestIntegrationImportChain:
    """Tests for the full import chain as used by GUI."""

    def test_full_gui_import_chain(self):
        """Test the complete import chain used by GUI main_window."""
        # These are the exact imports from main_window.py
        from p8_analyzer.circuit import check_intersections, CircuitComponent
        from p8_analyzer.detection import PinFinder
        from p8_analyzer.detection.label_matcher import LabelMatcher
        from p8_analyzer.detection.busbar_finder import BusbarFinder
        from p8_analyzer.detection.component_namer import ComponentNamer
        from p8_analyzer.text import HybridTextEngine

        assert check_intersections is not None
        assert CircuitComponent is not None
        assert PinFinder is not None
        assert LabelMatcher is not None
        assert BusbarFinder is not None
        assert ComponentNamer is not None
        assert HybridTextEngine is not None

    def test_full_worker_import_chain(self):
        """Test the complete import chain used by GUI worker."""
        # These are the exact imports from worker.py
        from p8_analyzer.core import analyze_page_vectors, DEFAULT_CONFIG
        from p8_analyzer.detection import (
            TerminalDetector, TerminalReader, TerminalGrouper,
            ClusterDetector, get_default_settings
        )
        from p8_analyzer.text import HybridTextEngine

        assert analyze_page_vectors is not None
        assert DEFAULT_CONFIG is not None
        assert TerminalDetector is not None
        assert ClusterDetector is not None
        assert HybridTextEngine is not None

    def test_full_viewer_import_chain(self):
        """Test the complete import chain used by GUI viewer."""
        # These are the exact imports from viewer.py
        from p8_analyzer.circuit import CircuitComponent
        from p8_analyzer.detection import visualize_clusters

        assert CircuitComponent is not None
        assert visualize_clusters is not None
