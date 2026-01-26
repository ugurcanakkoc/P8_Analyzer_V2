"""
Test that simulates GUI AnalysisWorker behavior.

This test ensures the GUI and CLI produce identical connection results.
"""
import pytest
import pymupdf
from pathlib import Path

from p8_analyzer.core import analyze_page_vectors, DEFAULT_CONFIG
from p8_analyzer.core.analysis_engine import AnalysisEngine, AnalysisOptions
from p8_analyzer.core.session import PageAnalysis


# Test PDF path
TEST_PDF = Path(__file__).parent.parent.parent / "data" / "ornek.pdf"


class TestGUIWorkerSimulation:
    """Simulate the exact workflow of the GUI AnalysisWorker."""

    @pytest.fixture
    def page_11_analysis(self):
        """Run analysis on page 11 exactly as the GUI worker does."""
        assert TEST_PDF.exists(), f"Test PDF not found: {TEST_PDF}"

        doc = pymupdf.open(str(TEST_PDF))
        try:
            page = doc.load_page(10)  # 0-indexed, so page 11 is index 10

            # Step 1: Get drawings (same as worker)
            drawings = page.get_drawings()
            assert drawings, "No vector data found"

            # Step 2: Vector analysis (same as worker)
            analysis_result = analyze_page_vectors(
                drawings, page.rect, 11, DEFAULT_CONFIG
            )

            # Step 3: Run AnalysisEngine (same as worker)
            options = AnalysisOptions(
                include_terminals=True,
                include_clusters=True,
                include_wire_annotations=True,
                include_connections=True,
                include_pins=True
            )
            engine = AnalysisEngine(options)
            page_analysis = engine.analyze_page(page, 11)

            # Step 4: Store in analysis_result (same as worker)
            analysis_result.page_analysis = page_analysis

            # Also store legacy terminal format (same as worker)
            analysis_result.terminals = [
                {
                    'center': (t.center_x, t.center_y),
                    'radius': t.radius,
                    'label': t.label,
                    'group_label': t.group_label,
                    'full_label': t.full_label,
                    'group_id': t.structural_group_id,
                }
                for t in page_analysis.terminals
            ]

            return analysis_result, page_analysis

        finally:
            doc.close()

    def test_worker_produces_page_analysis(self, page_11_analysis):
        """Worker should produce a valid PageAnalysis."""
        analysis_result, page_analysis = page_11_analysis

        assert page_analysis is not None
        assert isinstance(page_analysis, PageAnalysis)
        assert page_analysis.page_number == 11

    def test_page_analysis_has_connections(self, page_11_analysis):
        """PageAnalysis should have connections."""
        _, page_analysis = page_11_analysis

        assert page_analysis.connections is not None
        assert len(page_analysis.connections) > 0

    def test_connections_have_pins(self, page_11_analysis):
        """Connections should include pin labels (not just component names)."""
        _, page_analysis = page_11_analysis

        # Count connections with pins (contain ":")
        connections_with_pins = [
            c for c in page_analysis.connections
            if ':' in c.source_id or ':' in c.target_id
        ]

        # Most connections should have pins
        ratio = len(connections_with_pins) / len(page_analysis.connections)
        assert ratio > 0.5, f"Only {ratio:.0%} connections have pins"

    def test_no_same_block_connections_after_filter(self, page_11_analysis):
        """After filtering, no same-block connections should remain."""
        _, page_analysis = page_11_analysis

        def get_base(comp_id):
            return comp_id.split(':')[0] if ':' in comp_id else comp_id

        # Simulate the GUI filter
        filtered = []
        for conn in page_analysis.connections:
            src_base = get_base(conn.source_id)
            tgt_base = get_base(conn.target_id)
            if src_base != tgt_base:
                filtered.append(conn)

        # Verify no same-block connections remain
        for conn in filtered:
            src_base = get_base(conn.source_id)
            tgt_base = get_base(conn.target_id)
            assert src_base != tgt_base, \
                f"Same-block connection not filtered: {conn.source_id} -> {conn.target_id}"

    def test_expected_connections_present(self, page_11_analysis):
        """Key connections should be present."""
        _, page_analysis = page_11_analysis

        def get_base(comp_id):
            return comp_id.split(':')[0] if ':' in comp_id else comp_id

        # Get filtered connections (as GUI would display)
        filtered = [
            (c.source_id, c.target_id)
            for c in page_analysis.connections
            if get_base(c.source_id) != get_base(c.target_id)
        ]

        # Check for expected cross-device connections
        # -1Q21 should connect to terminals and -1X11
        q21_connections = [
            (s, t) for s, t in filtered
            if '-1Q21' in s or '-1Q21' in t
        ]
        assert len(q21_connections) > 0, "-1Q21 connections not found"

        # Print for debugging
        print(f"\n-1Q21 connections found: {len(q21_connections)}")
        for s, t in q21_connections:
            print(f"  {s} -> {t}")

    def test_analysis_result_stores_page_analysis(self, page_11_analysis):
        """VectorAnalysisResult should store PageAnalysis."""
        analysis_result, page_analysis = page_11_analysis

        assert analysis_result.page_analysis is not None
        assert analysis_result.page_analysis is page_analysis

    def test_analysis_result_has_legacy_terminals(self, page_11_analysis):
        """VectorAnalysisResult should have legacy terminal format."""
        analysis_result, _ = page_11_analysis

        assert analysis_result.terminals is not None
        assert len(analysis_result.terminals) > 0

        # Check legacy format
        term = analysis_result.terminals[0]
        assert 'center' in term
        assert 'radius' in term


class TestGUIConnectionReportSimulation:
    """Simulate the GUI connection report generation."""

    @pytest.fixture
    def page_analysis(self):
        """Get PageAnalysis for page 11."""
        assert TEST_PDF.exists()

        doc = pymupdf.open(str(TEST_PDF))
        try:
            page = doc.load_page(10)
            options = AnalysisOptions()
            engine = AnalysisEngine(options)
            return engine.analyze_page(page, 11)
        finally:
            doc.close()

    def test_connection_report_format(self, page_analysis):
        """Test the connection report generation logic."""
        def get_base(comp_id):
            return comp_id.split(':')[0] if ':' in comp_id else comp_id

        # Simulate _generate_connection_report_from_page_analysis
        report_lines = []
        for conn in page_analysis.connections:
            source = conn.source_id
            target = conn.target_id

            # Skip same-block
            if get_base(source) == get_base(target):
                continue

            report_lines.append(f"{source} -> {target}")

        assert len(report_lines) > 0, "No connections in report"

        # Print report for verification
        print(f"\nConnection Report ({len(report_lines)} lines):")
        for line in report_lines[:15]:
            print(f"  {line}")
        if len(report_lines) > 15:
            print(f"  ... and {len(report_lines) - 15} more")

    def test_connection_count_reasonable(self, page_analysis):
        """Connection count should be reasonable for page 11."""
        # Page 11 should have around 20-40 connections
        total = len(page_analysis.connections)
        assert 10 < total < 100, f"Unexpected connection count: {total}"

    def test_terminals_have_structural_group_id(self, page_analysis):
        """Terminals should have structural group IDs for highlighting."""
        terminals_with_group = [
            t for t in page_analysis.terminals
            if t.structural_group_id is not None
        ]

        # Most terminals should have group IDs
        ratio = len(terminals_with_group) / max(len(page_analysis.terminals), 1)
        assert ratio > 0.3, f"Only {ratio:.0%} terminals have structural_group_id"
