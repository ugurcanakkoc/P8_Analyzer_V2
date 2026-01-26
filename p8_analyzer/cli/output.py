"""
Output formatters for CLI analysis results.

Provides JSON, CSV, and text output formats.
"""
import csv
import json
from abc import ABC, abstractmethod
from io import StringIO
from typing import TextIO, Optional

from p8_analyzer.core.session import AnalysisSession, PageAnalysis


class OutputFormatter(ABC):
    """Base class for output formatters."""

    @abstractmethod
    def format_session(self, session: AnalysisSession) -> str:
        """Format a complete analysis session."""
        pass

    @abstractmethod
    def format_page(self, page: PageAnalysis) -> str:
        """Format a single page analysis."""
        pass

    def write_to_file(self, session: AnalysisSession, filepath: str):
        """Write formatted output to file."""
        content = self.format_session(session)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)


class JSONFormatter(OutputFormatter):
    """JSON output formatter."""

    def __init__(self, indent: int = 2, include_raw: bool = False):
        self.indent = indent
        self.include_raw = include_raw

    def format_session(self, session: AnalysisSession) -> str:
        """Format session as JSON."""
        return session.model_dump_json(indent=self.indent)

    def format_page(self, page: PageAnalysis) -> str:
        """Format single page as JSON."""
        return page.model_dump_json(indent=self.indent)


class CSVFormatter(OutputFormatter):
    """CSV output formatter for tabular data."""

    def __init__(self, include_annotations: bool = True):
        self.include_annotations = include_annotations

    def format_session(self, session: AnalysisSession) -> str:
        """Format session as CSV (terminals with annotations)."""
        output = StringIO()
        writer = csv.writer(output)

        # Header
        header = [
            'Page', 'Terminal_ID', 'Full_Label', 'Group_Label', 'Label',
            'Center_X', 'Center_Y', 'Radius', 'Structural_Group_ID'
        ]
        if self.include_annotations:
            header.extend([
                'Annotation_Count', 'Signal_Names', 'Destination_Refs',
                'Wire_Specs', 'Color_Codes', 'Component_Refs'
            ])
        writer.writerow(header)

        # Data rows
        for page_num, page in sorted(session.pages.items()):
            for terminal in page.terminals:
                row = [
                    page_num,
                    terminal.id,
                    terminal.full_label or '',
                    terminal.group_label or '',
                    terminal.label or '',
                    f"{terminal.center_x:.2f}",
                    f"{terminal.center_y:.2f}",
                    f"{terminal.radius:.2f}",
                    terminal.structural_group_id or ''
                ]

                if self.include_annotations:
                    anns = terminal.wire_annotations
                    signal_names = [a.text for a in anns if a.annotation_type == 'signal_name']
                    dest_refs = [a.text for a in anns if a.annotation_type == 'destination']
                    wire_specs = [a.text for a in anns if a.annotation_type == 'wire_spec']
                    color_codes = [a.text for a in anns if a.annotation_type == 'color_code']
                    comp_refs = [a.text for a in anns if a.annotation_type == 'component_ref']

                    row.extend([
                        len(anns),
                        '; '.join(signal_names),
                        '; '.join(dest_refs),
                        '; '.join(wire_specs),
                        '; '.join(color_codes),
                        '; '.join(comp_refs)
                    ])

                writer.writerow(row)

        return output.getvalue()

    def format_page(self, page: PageAnalysis) -> str:
        """Format single page as CSV."""
        output = StringIO()
        writer = csv.writer(output)

        # Simple terminal list for single page
        header = ['Terminal_ID', 'Full_Label', 'Annotations']
        writer.writerow(header)

        for terminal in page.terminals:
            ann_texts = [a.text for a in terminal.wire_annotations]
            row = [
                terminal.id,
                terminal.full_label or '',
                '; '.join(ann_texts)
            ]
            writer.writerow(row)

        return output.getvalue()


class TextFormatter(OutputFormatter):
    """Human-readable text output formatter."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def format_session(self, session: AnalysisSession) -> str:
        """Format session as readable text."""
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("P8 ANALYZER - ANALYSIS REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"PDF: {session.metadata.pdf_name}")
        lines.append(f"Pages Analyzed: {session.metadata.analyzed_pages}")
        lines.append(f"Generated: {session.metadata.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Summary
        lines.append("-" * 40)
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Total Terminals: {session.summary.total_terminals}")
        lines.append(f"  Total Components: {session.summary.total_components}")
        lines.append(f"  Total Connections: {session.summary.total_connections}")
        lines.append(f"  Total Wire Annotations: {session.summary.total_annotations}")
        if session.summary.pages_with_errors:
            lines.append(f"  Pages with Errors: {session.summary.pages_with_errors}")
        lines.append("")

        # Per-page details
        for page_num, page in sorted(session.pages.items()):
            lines.append(self.format_page(page))
            lines.append("")

        return '\n'.join(lines)

    def format_page(self, page: PageAnalysis) -> str:
        """Format single page as readable text."""
        lines = []

        lines.append("-" * 40)
        lines.append(f"PAGE {page.page_number}")
        lines.append("-" * 40)
        lines.append(f"  Dimensions: {page.page_width:.1f} x {page.page_height:.1f}")
        lines.append(f"  Structural Groups: {page.structural_group_count}")
        lines.append(f"  Terminals: {len(page.terminals)}")
        lines.append(f"  Components: {len(page.components)}")
        lines.append("")

        # Terminals with annotations
        if page.terminals:
            lines.append("  TERMINALS:")
            for term in page.terminals:
                label = term.full_label or term.label or "(unlabeled)"
                ann_count = len(term.wire_annotations)

                if ann_count > 0:
                    ann_texts = [a.text for a in term.wire_annotations]
                    lines.append(f"    {label}: {', '.join(ann_texts)}")
                elif self.verbose:
                    lines.append(f"    {label}: (no annotations)")

        # Components
        if page.components and self.verbose:
            lines.append("")
            lines.append("  COMPONENTS:")
            for comp in page.components:
                if not comp.label:
                    continue  # Skip unlabeled components in output
                pin_count = len(comp.pins)
                lines.append(f"    {comp.label}: {pin_count} pins")

        return '\n'.join(lines)


def get_formatter(format_type: str, **kwargs) -> OutputFormatter:
    """
    Factory function to get appropriate formatter.

    Args:
        format_type: One of 'json', 'csv', 'text'
        **kwargs: Additional arguments passed to formatter

    Returns:
        OutputFormatter instance
    """
    formatters = {
        'json': JSONFormatter,
        'csv': CSVFormatter,
        'text': TextFormatter,
    }

    formatter_class = formatters.get(format_type.lower())
    if formatter_class is None:
        raise ValueError(f"Unknown format: {format_type}. Use one of: {list(formatters.keys())}")

    # Filter kwargs based on formatter class
    if formatter_class == JSONFormatter:
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in ('indent', 'include_raw')}
    elif formatter_class == CSVFormatter:
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in ('include_annotations',)}
    elif formatter_class == TextFormatter:
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in ('verbose',)}
    else:
        filtered_kwargs = kwargs

    return formatter_class(**filtered_kwargs)
