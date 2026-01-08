#!/usr/bin/env python3
"""
Convert PDF files to markdown using markitdown library.
"""
import sys
import os
from pathlib import Path

try:
    from markitdown import MarkItDown
except ImportError:
    print("Error: markitdown not installed. Run: pip install markitdown", file=sys.stderr)
    sys.exit(1)


def pdf_to_markdown(pdf_path, output_path=None):
    """
    Convert PDF to markdown.

    Args:
        pdf_path: Path to PDF file
        output_path: Optional output path (default: same name with .md extension)

    Returns:
        Markdown content as string
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Initialize converter
    md = MarkItDown()

    # Convert PDF to markdown
    result = md.convert(pdf_path)

    # Get markdown content
    markdown_content = result.text_content

    # Determine output path
    if output_path is None:
        output_path = Path(pdf_path).with_suffix('.md')

    # Save to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    return markdown_content, output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python pdf_to_markdown.py <pdf_path> [output_path]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        content, output_file = pdf_to_markdown(pdf_path, output_path)

        print(f"✓ PDF converted successfully")
        print(f"✓ Output saved to: {output_file}")
        print(f"✓ Content length: {len(content)} characters")
        print(f"\n--- Preview (first 500 chars) ---")
        print(content[:500])
        if len(content) > 500:
            print("\n... (truncated)")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
