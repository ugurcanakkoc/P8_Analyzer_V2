"""
Integration tests for GUI analysis workflow.

These tests simulate the GUI analysis flow to catch errors before they crash the actual GUI.
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pymupdf
from p8_analyzer.core.analysis_engine import AnalysisEngine
from p8_analyzer.core.session import PageAnalysis


class TestGUIAnalysisWorkflow:
    """Tests that simulate the GUI analysis workflow."""

    @pytest.fixture
    def sample_pdf_path(self):
        """Path to sample PDF."""
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'ornek.pdf'
        )

    @pytest.fixture
    def pdf_page(self, sample_pdf_path):
        """Load page 11 from sample PDF."""
        doc = pymupdf.open(sample_pdf_path)
        return doc[10]  # Page 11 (0-indexed)

    def test_analysis_engine_returns_page_analysis(self, pdf_page):
        """AnalysisEngine.analyze_page returns valid PageAnalysis."""
        engine = AnalysisEngine()
        result = engine.analyze_page(pdf_page, 11)

        assert isinstance(result, PageAnalysis)
        assert result.page_number == 11
        assert result.page_width > 0
        assert result.page_height > 0

    def test_page_analysis_has_terminals(self, pdf_page):
        """PageAnalysis contains terminal data."""
        engine = AnalysisEngine()
        result = engine.analyze_page(pdf_page, 11)

        assert hasattr(result, 'terminals')
        assert isinstance(result.terminals, list)
        # Page 11 should have terminals
        assert len(result.terminals) > 0

    def test_page_analysis_has_components(self, pdf_page):
        """PageAnalysis contains component data."""
        engine = AnalysisEngine()
        result = engine.analyze_page(pdf_page, 11)

        assert hasattr(result, 'components')
        assert isinstance(result.components, list)

    def test_page_analysis_has_connections(self, pdf_page):
        """PageAnalysis contains connection data."""
        engine = AnalysisEngine()
        result = engine.analyze_page(pdf_page, 11)

        assert hasattr(result, 'connections')
        assert isinstance(result.connections, list)

    def test_terminals_have_required_fields(self, pdf_page):
        """Each terminal has all required fields."""
        engine = AnalysisEngine()
        result = engine.analyze_page(pdf_page, 11)

        for terminal in result.terminals:
            assert hasattr(terminal, 'id')
            assert hasattr(terminal, 'center_x')
            assert hasattr(terminal, 'center_y')
            assert hasattr(terminal, 'radius')
            assert hasattr(terminal, 'full_label')
            assert hasattr(terminal, 'wire_annotations')

    def test_components_have_required_fields(self, pdf_page):
        """Each component has all required fields."""
        engine = AnalysisEngine()
        result = engine.analyze_page(pdf_page, 11)

        for component in result.components:
            assert hasattr(component, 'id')
            assert hasattr(component, 'label')
            assert hasattr(component, 'bbox_min_x')
            assert hasattr(component, 'bbox_min_y')
            assert hasattr(component, 'bbox_max_x')
            assert hasattr(component, 'bbox_max_y')
            assert hasattr(component, 'pins')

    def test_connections_have_required_fields(self, pdf_page):
        """Each connection has all required fields."""
        engine = AnalysisEngine()
        result = engine.analyze_page(pdf_page, 11)

        for connection in result.connections:
            assert hasattr(connection, 'source_id')
            assert hasattr(connection, 'target_id')
            assert hasattr(connection, 'net_id')

    def test_page_analysis_serializable(self, pdf_page):
        """PageAnalysis can be serialized to JSON."""
        engine = AnalysisEngine()
        result = engine.analyze_page(pdf_page, 11)

        # Should not raise
        json_str = result.model_dump_json()
        assert len(json_str) > 0

    def test_page_analysis_dict_conversion(self, pdf_page):
        """PageAnalysis can be converted to dict."""
        engine = AnalysisEngine()
        result = engine.analyze_page(pdf_page, 11)

        # Should not raise
        data = result.model_dump()
        assert isinstance(data, dict)
        assert 'terminals' in data
        assert 'components' in data
        assert 'connections' in data


class TestGUIConnectionReport:
    """Tests for connection report generation (used by GUI)."""

    @pytest.fixture
    def sample_pdf_path(self):
        """Path to sample PDF."""
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'ornek.pdf'
        )

    @pytest.fixture
    def pdf_page(self, sample_pdf_path):
        """Load page 11 from sample PDF."""
        doc = pymupdf.open(sample_pdf_path)
        return doc[10]

    def test_connection_check_imports(self):
        """Connection check modules can be imported."""
        from p8_analyzer.circuit.connection_logic import check_intersections, CircuitComponent
        assert check_intersections is not None
        assert CircuitComponent is not None

    def test_circuit_component_creation(self):
        """CircuitComponent can be created with required fields."""
        from p8_analyzer.circuit.connection_logic import CircuitComponent

        comp = CircuitComponent(
            id='TEST-1',
            label='Test',
            bbox={'min_x': 0, 'min_y': 0, 'max_x': 100, 'max_y': 100}
        )
        assert comp.id == 'TEST-1'
        assert comp.label == 'Test'

    def test_check_intersections_empty_input(self):
        """check_intersections handles empty input."""
        from p8_analyzer.circuit.connection_logic import check_intersections

        # Create minimal mock result
        mock_result = Mock()
        mock_result.structural_groups = []

        result = check_intersections([], mock_result)
        assert isinstance(result, dict)


class TestGUIWorkerSimulation:
    """Tests that simulate what the GUI worker does."""

    @pytest.fixture
    def sample_pdf_path(self):
        """Path to sample PDF."""
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'ornek.pdf'
        )

    def test_full_analysis_workflow(self, sample_pdf_path):
        """Simulate full GUI analysis workflow."""
        # This is what the GUI worker does
        doc = pymupdf.open(sample_pdf_path)
        page = doc[10]  # Page 11

        engine = AnalysisEngine()

        # Step 1: Run analysis
        page_analysis = engine.analyze_page(page, 11)
        assert page_analysis is not None

        # Step 2: Access terminals (GUI displays these)
        terminals = page_analysis.terminals
        assert isinstance(terminals, list)

        # Step 3: Access components (GUI displays these)
        components = page_analysis.components
        assert isinstance(components, list)

        # Step 4: Access connections (GUI displays these)
        connections = page_analysis.connections
        assert isinstance(connections, list)

        # Step 5: Iterate through for display (what GUI does)
        for term in terminals:
            # GUI accesses these properties
            _ = term.full_label
            _ = term.center_x
            _ = term.center_y
            _ = term.wire_annotations

        for comp in components:
            # GUI accesses these properties
            _ = comp.label
            _ = comp.bbox_min_x
            _ = comp.pins

        for conn in connections:
            # GUI accesses these properties
            _ = conn.source_id
            _ = conn.target_id
            _ = conn.net_id

    def test_multiple_pages_analysis(self, sample_pdf_path):
        """Test analyzing multiple pages doesn't cause issues."""
        doc = pymupdf.open(sample_pdf_path)
        engine = AnalysisEngine()

        # Analyze pages 11, 12, 13
        for page_num in [11, 12, 13]:
            if page_num <= len(doc):
                page = doc[page_num - 1]
                result = engine.analyze_page(page, page_num)
                assert result.page_number == page_num


class TestGUIConnectionCheckSimulation:
    """Tests that simulate the GUI's run_connection_check method."""

    @pytest.fixture
    def sample_pdf_path(self):
        """Path to sample PDF."""
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'ornek.pdf'
        )

    def test_connection_check_with_vector_analysis_result(self, sample_pdf_path):
        """Simulate GUI's run_connection_check with VectorAnalysisResult."""
        from p8_analyzer.core import analyze_page_vectors, DEFAULT_CONFIG
        from p8_analyzer.circuit.connection_logic import CircuitComponent, check_intersections
        from p8_analyzer.detection import TerminalDetector, TerminalReader, TerminalGrouper
        from p8_analyzer.text import HybridTextEngine

        doc = pymupdf.open(sample_pdf_path)
        page = doc[10]  # Page 11

        # This is what AnalysisWorker does
        drawings = page.get_drawings()
        analysis_result = analyze_page_vectors(drawings, page.rect, 11, DEFAULT_CONFIG)

        # Terminal detection (as done in worker)
        detector = TerminalDetector()
        terminals = detector.detect(analysis_result)

        text_engine = HybridTextEngine(languages=['en'])
        text_engine.load_page(page)

        reader = TerminalReader()
        terminals = reader.read_labels(terminals, text_engine)

        grouper = TerminalGrouper()
        terminals = grouper.group_terminals(terminals, text_engine)

        analysis_result.terminals = terminals

        # NOW simulate run_connection_check (the GUI code)
        terminal_components = []
        used_term_ids = {}

        if hasattr(analysis_result, "terminals") and analysis_result.terminals:
            for term in analysis_result.terminals:
                # This is the exact code from main_window.py:307-308
                cx, cy = term["center"]  # <-- This line can crash if term is not a dict

                base_label = term.get("full_label") or term.get("label") or "TERM"

                if base_label in used_term_ids:
                    used_term_ids[base_label] += 1
                    term_id = f"{base_label} ({used_term_ids[base_label]})"
                else:
                    used_term_ids[base_label] = 1
                    term_id = base_label

                comp = CircuitComponent(
                    id=term_id, label="Terminal",
                    bbox={"min_x": cx-2, "min_y": cy-2, "max_x": cx+2, "max_y": cy+2}
                )
                terminal_components.append(comp)

        assert len(terminal_components) > 0, "Should have terminal components"

        # Continue with connection check
        connections = check_intersections(terminal_components, analysis_result)
        assert isinstance(connections, dict)

    def test_full_gui_worker_simulation(self, sample_pdf_path):
        """Simulate the complete GUI AnalysisWorker flow including cluster detection."""
        from p8_analyzer.core import analyze_page_vectors, DEFAULT_CONFIG
        from p8_analyzer.circuit.connection_logic import CircuitComponent, check_intersections
        from p8_analyzer.detection import (
            TerminalDetector, TerminalReader, TerminalGrouper,
            ClusterDetector, get_default_settings, PinFinder
        )
        from p8_analyzer.text import HybridTextEngine

        doc = pymupdf.open(sample_pdf_path)
        page = doc[10]  # Page 11

        # === STEP 1: Vector Analysis ===
        drawings = page.get_drawings()
        analysis_result = analyze_page_vectors(drawings, page.rect, 11, DEFAULT_CONFIG)

        # === STEP 2: Terminal Detection ===
        detector = TerminalDetector()
        terminals = detector.detect(analysis_result)

        text_engine = HybridTextEngine(languages=['en'])
        text_engine.load_page(page)

        reader = TerminalReader()
        terminals = reader.read_labels(terminals, text_engine)

        grouper = TerminalGrouper()
        terminals = grouper.group_terminals(terminals, text_engine)
        analysis_result.terminals = terminals

        # === STEP 3: Cluster Detection ===
        settings = get_default_settings()
        cluster_detector = ClusterDetector(
            vertical_weight=settings.vertical_weight,
            absolute_min_gap=settings.absolute_min_gap,
            density_factor=settings.density_factor,
            max_gap=settings.max_gap,
            label_max_distance=settings.label_max_distance,
            label_cluster_size_factor=settings.label_cluster_size_factor,
            cross_color_penalty=settings.cross_color_penalty,
            label_subsume_threshold=settings.label_subsume_threshold
        )

        clusters, labels, gap_fills, circle_pins, line_ends = cluster_detector.detect_clusters(
            page,
            analysis_result.broken_connections,
            analysis_result.structural_groups
        )

        analysis_result.component_clusters = clusters
        analysis_result.cluster_labels = labels

        # === STEP 4: Connection Check (GUI run_connection_check) ===
        terminal_components = []
        used_term_ids = {}

        for term in analysis_result.terminals:
            cx, cy = term["center"]
            base_label = term.get("full_label") or term.get("label") or "TERM"

            if base_label in used_term_ids:
                used_term_ids[base_label] += 1
                term_id = f"{base_label} ({used_term_ids[base_label]})"
            else:
                used_term_ids[base_label] = 1
                term_id = base_label

            comp = CircuitComponent(
                id=term_id, label="Terminal",
                bbox={"min_x": cx-2, "min_y": cy-2, "max_x": cx+2, "max_y": cy+2}
            )
            terminal_components.append(comp)

        # Cluster-detected components
        cluster_boxes = []
        for cluster in analysis_result.component_clusters:
            if cluster.label:
                label_text = cluster.label.text if hasattr(cluster.label, 'text') else str(cluster.label)
                bbox = cluster.bbox
                comp = CircuitComponent(
                    id=label_text,
                    label=label_text,
                    bbox={"min_x": bbox[0], "min_y": bbox[1], "max_x": bbox[2], "max_y": bbox[3]}
                )
                cluster_boxes.append(comp)

        all_comps = terminal_components + cluster_boxes
        connections = check_intersections(all_comps, analysis_result)

        # === STEP 5: Pin Finding ===
        all_pin_boxes = cluster_boxes
        pin_finder = PinFinder()

        for i, group in enumerate(analysis_result.structural_groups):
            original_net_id = f"NET-{i+1:03d}"
            found_pins = pin_finder.find_pins_for_group(group, all_pin_boxes, text_engine)
            if found_pins:
                pins_formatted = [p["full_label"] for p in found_pins]
                connections.setdefault(original_net_id, []).extend(pins_formatted)

        # Verify we have connections
        assert len(connections) > 0, "Should have detected connections"
        print(f"Detected {len(connections)} networks")


class TestEndpointLabelDetection:
    """Tests for endpoint label detection (new feature)."""

    @pytest.fixture
    def sample_pdf_path(self):
        """Path to sample PDF."""
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'ornek.pdf'
        )

    @pytest.fixture
    def pdf_page(self, sample_pdf_path):
        """Load page 11 from sample PDF."""
        doc = pymupdf.open(sample_pdf_path)
        return doc[10]

    def test_endpoint_labels_method_exists(self):
        """_detect_endpoint_labels method exists on AnalysisEngine."""
        engine = AnalysisEngine()
        assert hasattr(engine, '_detect_endpoint_labels')

    def test_find_structural_group_method_exists(self):
        """_find_structural_group_for_point method exists on AnalysisEngine."""
        engine = AnalysisEngine()
        assert hasattr(engine, '_find_structural_group_for_point')

    def test_order_along_wire_path_method_exists(self):
        """_order_along_wire_path method exists on AnalysisEngine."""
        engine = AnalysisEngine()
        assert hasattr(engine, '_order_along_wire_path')

    def test_connections_include_endpoint_labels(self, pdf_page):
        """Connections should include endpoint labels like L1, L2."""
        engine = AnalysisEngine()
        result = engine.analyze_page(pdf_page, 11)

        # Get all connection endpoints
        all_endpoints = set()
        for conn in result.connections:
            all_endpoints.add(conn.source_id)
            all_endpoints.add(conn.target_id)

        # Should find signal labels like L1, L2, L3 or combined labels like "L1 /2.11"
        signal_labels = [ep for ep in all_endpoints if 'L1' in ep or 'L2' in ep or 'L3' in ep]

        # Page 11 should have L-line endpoint labels
        assert len(signal_labels) > 0, f"Expected L-line endpoint labels, got: {all_endpoints}"
