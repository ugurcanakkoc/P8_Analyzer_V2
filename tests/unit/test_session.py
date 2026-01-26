"""
Unit tests for AnalysisSession and related models.
"""
import pytest
import tempfile
import os
from datetime import datetime

from p8_analyzer.core.session import (
    WireAnnotationType,
    WireAnnotation,
    Terminal,
    Pin,
    Component,
    Connection,
    PageAnalysis,
    SessionMetadata,
    AnalysisSummary,
    AnalysisSession,
    create_session,
    classify_annotation,
)


class TestClassifyAnnotation:
    """Test annotation classification."""

    def test_signal_name_p24(self):
        assert classify_annotation("P24") == WireAnnotationType.SIGNAL_NAME

    def test_signal_name_n24(self):
        assert classify_annotation("N24") == WireAnnotationType.SIGNAL_NAME

    def test_signal_name_p24_i2(self):
        assert classify_annotation("P24.i2") == WireAnnotationType.SIGNAL_NAME

    def test_signal_name_pe(self):
        assert classify_annotation("PE") == WireAnnotationType.SIGNAL_NAME

    def test_signal_name_l_plus(self):
        assert classify_annotation("L+") == WireAnnotationType.SIGNAL_NAME

    def test_signal_name_m(self):
        assert classify_annotation("M") == WireAnnotationType.SIGNAL_NAME

    def test_signal_name_l1(self):
        assert classify_annotation("L1") == WireAnnotationType.SIGNAL_NAME

    def test_destination_ref_simple(self):
        assert classify_annotation("/6.4") == WireAnnotationType.DESTINATION_REF

    def test_destination_ref_larger(self):
        assert classify_annotation("/13.34") == WireAnnotationType.DESTINATION_REF

    def test_wire_spec_mm(self):
        assert classify_annotation("3x1,5mm") == WireAnnotationType.WIRE_SPEC

    def test_wire_spec_cu(self):
        # This might match wire_spec due to Cu ending
        result = classify_annotation("4x0,5mm Cu")
        assert result in [WireAnnotationType.WIRE_SPEC, WireAnnotationType.UNKNOWN]

    def test_color_code_wh(self):
        assert classify_annotation("WH") == WireAnnotationType.COLOR_CODE

    def test_color_code_bn(self):
        assert classify_annotation("BN") == WireAnnotationType.COLOR_CODE

    def test_color_code_gn(self):
        assert classify_annotation("GN") == WireAnnotationType.COLOR_CODE

    def test_color_code_se(self):
        assert classify_annotation("SE") == WireAnnotationType.COLOR_CODE

    def test_component_ref(self):
        assert classify_annotation("=070") == WireAnnotationType.COMPONENT_REF

    def test_unknown(self):
        assert classify_annotation("random text") == WireAnnotationType.UNKNOWN


class TestWireAnnotation:
    """Test WireAnnotation model."""

    def test_create_annotation(self):
        ann = WireAnnotation(
            text="P24",
            position_x=100.0,
            position_y=200.0,
            distance_to_terminal=50.0,
            direction="left"
        )
        assert ann.text == "P24"
        assert ann.annotation_type == WireAnnotationType.SIGNAL_NAME
        assert ann.position_x == 100.0
        assert ann.distance_to_terminal == 50.0

    def test_auto_classification(self):
        ann = WireAnnotation(
            text="/6.4",
            position_x=0,
            position_y=0
        )
        assert ann.annotation_type == WireAnnotationType.DESTINATION_REF


class TestTerminal:
    """Test Terminal model."""

    def test_create_terminal(self):
        term = Terminal(
            id="11_-X1_5",
            center_x=245.5,
            center_y=312.8,
            radius=3.0,
            label="5",
            group_label="-X1",
            full_label="-X1:5"
        )
        assert term.id == "11_-X1_5"
        assert term.full_label == "-X1:5"
        assert len(term.wire_annotations) == 0

    def test_terminal_with_annotations(self):
        ann = WireAnnotation(
            text="P24.i2",
            position_x=180.0,
            position_y=312.5,
            distance_to_terminal=65.3,
            direction="left"
        )
        term = Terminal(
            id="11_-X1_1",
            center_x=245.5,
            center_y=312.8,
            radius=3.0,
            wire_annotations=[ann]
        )
        assert len(term.wire_annotations) == 1
        assert term.wire_annotations[0].text == "P24.i2"

    def test_terminal_from_dict(self):
        data = {
            'center': (245.5, 312.8),
            'radius': 3.0,
            'label': '5',
            'group_label': '-X1',
            'full_label': '-X1:5',
            'label_source': 'pdf',
            'group_source': 'pdf_direct',
            'group_id': 42
        }
        term = Terminal.from_dict(data, page_number=11)
        assert term.center_x == 245.5
        assert term.center_y == 312.8
        assert term.full_label == '-X1:5'
        assert term.structural_group_id == 42


class TestComponent:
    """Test Component model."""

    def test_create_component(self):
        comp = Component(
            id="comp_1",
            label="-1F45",
            component_type="plc",
            bbox_min_x=100,
            bbox_min_y=100,
            bbox_max_x=300,
            bbox_max_y=200
        )
        assert comp.width == 200
        assert comp.height == 100
        assert comp.center == (200, 150)

    def test_component_with_pins(self):
        pins = [
            Pin(label="OUT1", position_x=120, position_y=180),
            Pin(label="OUT2", position_x=150, position_y=180),
        ]
        comp = Component(
            id="comp_1",
            label="-1F45",
            bbox_min_x=100,
            bbox_min_y=100,
            bbox_max_x=300,
            bbox_max_y=200,
            pins=pins
        )
        assert len(comp.pins) == 2
        assert comp.pins[0].label == "OUT1"


class TestPageAnalysis:
    """Test PageAnalysis model."""

    def test_create_page_analysis(self):
        page = PageAnalysis(
            page_number=11,
            page_width=842,
            page_height=595
        )
        assert page.page_number == 11
        assert len(page.terminals) == 0
        assert len(page.connections) == 0

    def test_get_terminal_by_label(self):
        term = Terminal(
            id="11_-X1_5",
            center_x=245.5,
            center_y=312.8,
            radius=3.0,
            full_label="-X1:5"
        )
        page = PageAnalysis(
            page_number=11,
            page_width=842,
            page_height=595,
            terminals=[term]
        )
        found = page.get_terminal_by_label("-X1:5")
        assert found is not None
        assert found.id == "11_-X1_5"

    def test_get_terminals_by_group(self):
        terms = [
            Terminal(id="1", center_x=0, center_y=0, radius=3, group_label="-X1", label="1"),
            Terminal(id="2", center_x=10, center_y=0, radius=3, group_label="-X1", label="2"),
            Terminal(id="3", center_x=100, center_y=0, radius=3, group_label="-X2", label="1"),
        ]
        page = PageAnalysis(
            page_number=11,
            page_width=842,
            page_height=595,
            terminals=terms
        )
        x1_terms = page.get_terminals_by_group("-X1")
        assert len(x1_terms) == 2


class TestAnalysisSession:
    """Test AnalysisSession model."""

    def test_create_session(self):
        session = create_session("data/ornek.pdf", total_pages=60)
        assert session.metadata.pdf_name == "ornek.pdf"
        assert session.metadata.total_pages == 60
        assert len(session.pages) == 0

    def test_add_page(self):
        session = create_session("test.pdf", total_pages=10)
        page = PageAnalysis(
            page_number=1,
            page_width=842,
            page_height=595,
            terminals=[
                Terminal(id="1", center_x=100, center_y=100, radius=3)
            ]
        )
        session.add_page(page)
        assert 1 in session.pages
        assert session.summary.total_terminals == 1

    def test_compute_summary(self):
        session = create_session("test.pdf", total_pages=10)

        # Add page with 3 terminals, 1 component, 2 connections
        ann = WireAnnotation(text="P24", position_x=0, position_y=0)
        terms = [
            Terminal(id="1", center_x=0, center_y=0, radius=3, wire_annotations=[ann]),
            Terminal(id="2", center_x=10, center_y=0, radius=3),
            Terminal(id="3", center_x=20, center_y=0, radius=3),
        ]
        comps = [
            Component(id="c1", bbox_min_x=0, bbox_min_y=0, bbox_max_x=100, bbox_max_y=100)
        ]
        conns = [
            Connection(source_id="1", target_id="2", net_id="NET-001"),
            Connection(source_id="2", target_id="3", net_id="NET-001"),
        ]
        page = PageAnalysis(
            page_number=1,
            page_width=842,
            page_height=595,
            terminals=terms,
            components=comps,
            connections=conns
        )
        session.add_page(page)

        assert session.summary.total_terminals == 3
        assert session.summary.total_components == 1
        assert session.summary.total_connections == 2
        assert session.summary.total_annotations == 1

    def test_save_and_load(self):
        session = create_session("test.pdf", total_pages=10)

        # Add some data
        ann = WireAnnotation(text="P24", position_x=100, position_y=200)
        term = Terminal(
            id="11_-X1_1",
            center_x=245.5,
            center_y=312.8,
            radius=3.0,
            label="1",
            group_label="-X1",
            full_label="-X1:1",
            wire_annotations=[ann]
        )
        comp = Component(
            id="comp_1",
            label="-1F45",
            bbox_min_x=100,
            bbox_min_y=100,
            bbox_max_x=300,
            bbox_max_y=200,
            pins=[Pin(label="OUT1", position_x=120, position_y=180)]
        )
        conn = Connection(
            source_id="-X1:1",
            target_id="-X4:1",
            net_id="NET-001",
            wire_annotations=["P24"]
        )
        page = PageAnalysis(
            page_number=11,
            page_width=842,
            page_height=595,
            terminals=[term],
            components=[comp],
            connections=[conn]
        )
        session.add_page(page)

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            session.save(temp_path)

            # Load back
            loaded = AnalysisSession.load(temp_path)

            # Verify
            assert loaded.metadata.pdf_name == "test.pdf"
            assert 11 in loaded.pages
            assert len(loaded.pages[11].terminals) == 1
            assert loaded.pages[11].terminals[0].full_label == "-X1:1"
            assert len(loaded.pages[11].terminals[0].wire_annotations) == 1
            assert loaded.pages[11].terminals[0].wire_annotations[0].text == "P24"
            assert len(loaded.pages[11].components) == 1
            assert loaded.pages[11].components[0].label == "-1F45"
            assert len(loaded.pages[11].connections) == 1

        finally:
            os.unlink(temp_path)

    def test_get_all_terminals(self):
        session = create_session("test.pdf", total_pages=10)

        page1 = PageAnalysis(
            page_number=1,
            page_width=842,
            page_height=595,
            terminals=[
                Terminal(id="1", center_x=0, center_y=0, radius=3),
                Terminal(id="2", center_x=10, center_y=0, radius=3),
            ]
        )
        page2 = PageAnalysis(
            page_number=2,
            page_width=842,
            page_height=595,
            terminals=[
                Terminal(id="3", center_x=0, center_y=0, radius=3),
            ]
        )
        session.add_page(page1)
        session.add_page(page2)

        all_terms = session.get_all_terminals()
        assert len(all_terms) == 3
