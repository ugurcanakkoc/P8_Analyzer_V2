"""
Unit tests for CLI module.
"""
import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime

from p8_analyzer.cli.analyzer import PDFAnalyzer, AnalysisOptions
from p8_analyzer.cli.output import (
    JSONFormatter,
    CSVFormatter,
    TextFormatter,
    get_formatter,
)
from p8_analyzer.cli.main import parse_page_range
from p8_analyzer.core.session import (
    AnalysisSession,
    SessionMetadata,
    PageAnalysis,
    Terminal,
    WireAnnotation,
    AnalysisSummary,
)


class TestParsePageRange:
    """Test page range parsing."""

    def test_single_page(self):
        assert parse_page_range("11") == [11]

    def test_comma_separated(self):
        assert parse_page_range("11,12,14") == [11, 12, 14]

    def test_range(self):
        assert parse_page_range("11-14") == [11, 12, 13, 14]

    def test_mixed(self):
        assert parse_page_range("11-14,20") == [11, 12, 13, 14, 20]

    def test_with_spaces(self):
        assert parse_page_range("11, 12, 14") == [11, 12, 14]

    def test_duplicates_removed(self):
        assert parse_page_range("11,11,12") == [11, 12]


class TestAnalysisOptions:
    """Test analysis options dataclass."""

    def test_default_options(self):
        options = AnalysisOptions()
        assert options.include_terminals is True
        assert options.include_clusters is True
        assert options.include_wire_annotations is True
        assert options.languages == ['en', 'de']

    def test_custom_options(self):
        options = AnalysisOptions(
            include_terminals=False,
            include_clusters=False,
            include_wire_annotations=True,
            languages=['de']
        )
        assert options.include_terminals is False
        assert options.include_clusters is False
        assert options.include_wire_annotations is True
        assert options.languages == ['de']


class TestPDFAnalyzer:
    """Test PDFAnalyzer class."""

    def test_init_default_options(self):
        analyzer = PDFAnalyzer()
        assert analyzer.options is not None
        assert analyzer.options.include_terminals is True

    def test_init_custom_options(self):
        options = AnalysisOptions(include_clusters=False)
        analyzer = PDFAnalyzer(options)
        assert analyzer.options.include_clusters is False

    def test_file_not_found(self):
        analyzer = PDFAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze_document("nonexistent.pdf")


class TestJSONFormatter:
    """Test JSON output formatter."""

    def test_format_session(self):
        session = _create_test_session()
        formatter = JSONFormatter()
        output = formatter.format_session(session)

        # Should be valid JSON
        data = json.loads(output)
        assert 'metadata' in data
        assert 'pages' in data
        assert 'summary' in data

    def test_format_page(self):
        page = _create_test_page()
        formatter = JSONFormatter()
        output = formatter.format_page(page)

        # Should be valid JSON
        data = json.loads(output)
        assert data['page_number'] == 11
        assert 'terminals' in data

    def test_indent_option(self):
        session = _create_test_session()
        formatter = JSONFormatter(indent=4)
        output = formatter.format_session(session)

        # Should be indented
        assert '    ' in output


class TestCSVFormatter:
    """Test CSV output formatter."""

    def test_format_session(self):
        session = _create_test_session()
        formatter = CSVFormatter()
        output = formatter.format_session(session)

        lines = output.strip().split('\n')
        # Header + data rows
        assert len(lines) >= 2

        # Check header
        header = lines[0]
        assert 'Page' in header
        assert 'Terminal_ID' in header
        assert 'Signal_Names' in header

    def test_format_session_without_annotations(self):
        session = _create_test_session()
        formatter = CSVFormatter(include_annotations=False)
        output = formatter.format_session(session)

        header = output.split('\n')[0]
        assert 'Signal_Names' not in header


class TestTextFormatter:
    """Test text output formatter."""

    def test_format_session(self):
        session = _create_test_session()
        formatter = TextFormatter()
        output = formatter.format_session(session)

        assert 'P8 ANALYZER' in output
        assert 'SUMMARY' in output
        assert 'PAGE 11' in output

    def test_format_page(self):
        page = _create_test_page()
        formatter = TextFormatter()
        output = formatter.format_page(page)

        assert 'PAGE 11' in output
        assert 'Terminals: 1' in output

    def test_verbose_mode(self):
        session = _create_test_session()
        formatter = TextFormatter(verbose=True)
        output = formatter.format_session(session)

        # Verbose should include components
        assert 'COMPONENTS' in output


class TestGetFormatter:
    """Test formatter factory function."""

    def test_get_json_formatter(self):
        formatter = get_formatter('json')
        assert isinstance(formatter, JSONFormatter)

    def test_get_csv_formatter(self):
        formatter = get_formatter('csv')
        assert isinstance(formatter, CSVFormatter)

    def test_get_text_formatter(self):
        formatter = get_formatter('text')
        assert isinstance(formatter, TextFormatter)

    def test_case_insensitive(self):
        formatter = get_formatter('JSON')
        assert isinstance(formatter, JSONFormatter)

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            get_formatter('xml')

    def test_kwargs_filtering(self):
        # Should not raise even with extra kwargs
        formatter = get_formatter('text', verbose=True, include_annotations=True)
        assert isinstance(formatter, TextFormatter)


# Helper functions to create test data

def _create_test_session() -> AnalysisSession:
    """Create a test AnalysisSession."""
    return AnalysisSession(
        metadata=SessionMetadata(
            pdf_path="/test/path.pdf",
            pdf_name="path.pdf",
            total_pages=100,
            analyzed_pages=[11],
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            analyzer_version="2.0.0"
        ),
        pages={11: _create_test_page()},
        summary=AnalysisSummary(
            total_terminals=1,
            total_components=1,
            total_connections=0,
            total_annotations=1
        )
    )


def _create_test_page() -> PageAnalysis:
    """Create a test PageAnalysis."""
    from p8_analyzer.core.session import Component, Pin

    return PageAnalysis(
        page_number=11,
        page_width=1122.0,
        page_height=810.0,
        terminals=[
            Terminal(
                id="11_-X1_1",
                center_x=100.0,
                center_y=500.0,
                radius=3.0,
                label="1",
                group_label="-X1",
                full_label="-X1:1",
                wire_annotations=[
                    WireAnnotation(
                        text="P24",
                        position_x=80.0,
                        position_y=500.0,
                        annotation_type="signal_name",
                        distance_to_terminal=20.0,
                        direction="left"
                    )
                ]
            )
        ],
        components=[
            Component(
                id="11_-1G35_1234",
                label="-1G35",
                component_type="power_supply",
                bbox_min_x=200.0,
                bbox_min_y=300.0,
                bbox_max_x=400.0,
                bbox_max_y=450.0,
                pins=[
                    Pin(label="U", position_x=200.0, position_y=350.0),
                    Pin(label="V", position_x=200.0, position_y=400.0),
                ]
            )
        ],
        connections=[],
        structural_group_count=5,
        analysis_timestamp=datetime(2024, 1, 1, 12, 0, 0)
    )
