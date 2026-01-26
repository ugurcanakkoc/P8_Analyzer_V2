"""
CLI Entry Point - Main command-line interface for P8 Analyzer.

Usage:
    python -m p8_analyzer.cli.main analyze data/ornek.pdf -p 11 -f json -o output.json
    python -m p8_analyzer.cli.main analyze data/ornek.pdf -p 11-14 --include-annotations
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from .analyzer import PDFAnalyzer, AnalysisOptions
from .output import get_formatter


def setup_logging(verbose: bool = False, debug: bool = False):
    """Configure logging based on verbosity level."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format='%(levelname)s: %(message)s',
        stream=sys.stderr
    )


def parse_page_range(page_str: str) -> List[int]:
    """
    Parse page specification string into list of page numbers.

    Examples:
        "11" -> [11]
        "11,12,14" -> [11, 12, 14]
        "11-14" -> [11, 12, 13, 14]
        "11-14,20" -> [11, 12, 13, 14, 20]
    """
    pages = []
    parts = page_str.split(',')

    for part in parts:
        part = part.strip()
        if '-' in part:
            # Range: "11-14"
            start, end = part.split('-', 1)
            start = int(start.strip())
            end = int(end.strip())
            pages.extend(range(start, end + 1))
        else:
            # Single page
            pages.append(int(part))

    return sorted(set(pages))


def cmd_analyze(args):
    """Execute the analyze command."""
    # Parse pages
    pages = None
    if args.pages:
        pages = parse_page_range(args.pages)

    # Create options
    options = AnalysisOptions(
        include_terminals=True,
        include_clusters=not args.no_clusters,
        include_wire_annotations=args.include_annotations,
        languages=args.languages.split(',') if args.languages else ['en', 'de']
    )

    # Run analysis
    analyzer = PDFAnalyzer(options)

    print(f"Analyzing: {args.pdf_path}", file=sys.stderr)
    if pages:
        print(f"Pages: {pages}", file=sys.stderr)

    session = analyzer.analyze_document(args.pdf_path, pages)

    # Format output
    formatter = get_formatter(
        args.format,
        verbose=args.verbose,
        include_annotations=args.include_annotations
    )

    output = formatter.format_session(session)

    # Write output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"Output written to: {args.output}", file=sys.stderr)
    else:
        print(output)

    # Print summary to stderr
    print(f"\nSummary:", file=sys.stderr)
    print(f"  Terminals: {session.summary.total_terminals}", file=sys.stderr)
    print(f"  Components: {session.summary.total_components}", file=sys.stderr)
    print(f"  Annotations: {session.summary.total_annotations}", file=sys.stderr)

    return 0


def cmd_info(args):
    """Show PDF information without full analysis."""
    import pymupdf

    doc = pymupdf.open(args.pdf_path)
    try:
        print(f"PDF: {args.pdf_path}")
        print(f"Pages: {len(doc)}")
        print(f"Title: {doc.metadata.get('title', 'N/A')}")
        print(f"Author: {doc.metadata.get('author', 'N/A')}")

        if args.verbose:
            print("\nPage dimensions:")
            for i, page in enumerate(doc):
                rect = page.rect
                print(f"  Page {i+1}: {rect.width:.1f} x {rect.height:.1f}")
    finally:
        doc.close()

    return 0


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog='p8-analyzer',
        description='P8 Analyzer - Electrical schematic analysis tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze single page, output to stdout
  %(prog)s analyze data/ornek.pdf -p 11

  # Analyze pages 11-14 with annotations, save as JSON
  %(prog)s analyze data/ornek.pdf -p 11-14 --include-annotations -f json -o results.json

  # Analyze all pages, CSV format
  %(prog)s analyze data/ornek.pdf -f csv -o terminals.csv

  # Show PDF info
  %(prog)s info data/ornek.pdf
"""
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # analyze command
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Analyze PDF pages and extract electrical data'
    )
    analyze_parser.add_argument(
        'pdf_path',
        help='Path to PDF file'
    )
    analyze_parser.add_argument(
        '-p', '--pages',
        help='Page numbers to analyze (e.g., "11", "11-14", "11,12,14")'
    )
    analyze_parser.add_argument(
        '-f', '--format',
        choices=['json', 'csv', 'text'],
        default='text',
        help='Output format (default: text)'
    )
    analyze_parser.add_argument(
        '-o', '--output',
        help='Output file path (default: stdout)'
    )
    analyze_parser.add_argument(
        '--include-annotations',
        action='store_true',
        help='Include wire annotations in output'
    )
    analyze_parser.add_argument(
        '--no-clusters',
        action='store_true',
        help='Skip cluster/component detection'
    )
    analyze_parser.add_argument(
        '--languages',
        default='en,de',
        help='OCR languages comma-separated (default: en,de)'
    )
    analyze_parser.set_defaults(func=cmd_analyze)

    # info command
    info_parser = subparsers.add_parser(
        'info',
        help='Show PDF information'
    )
    info_parser.add_argument(
        'pdf_path',
        help='Path to PDF file'
    )
    info_parser.set_defaults(func=cmd_info)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    setup_logging(args.verbose, args.debug)

    if args.command is None:
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logging.exception("Analysis failed")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
