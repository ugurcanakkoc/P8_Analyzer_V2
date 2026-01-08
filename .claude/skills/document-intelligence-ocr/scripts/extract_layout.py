#!/usr/bin/env python3
"""
Extract text and layout from images using Azure Document Intelligence Layout model.
"""
import os
import sys
import json
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential


def extract_layout(image_path, output_format="text"):
    """
    Extract layout from image using Document Intelligence.

    Args:
        image_path: Path to image file
        output_format: "text", "json", or "tables"

    Returns:
        Extracted content in specified format
    """
    # Get credentials from environment
    endpoint = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")

    if not endpoint or not key:
        raise ValueError(
            "Missing environment variables:\n"
            "  AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT\n"
            "  AZURE_DOCUMENT_INTELLIGENCE_KEY"
        )

    # Create client
    client = DocumentAnalysisClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key)
    )

    # Read image file
    with open(image_path, "rb") as f:
        poller = client.begin_analyze_document("prebuilt-layout", document=f)

    result = poller.result()

    # Extract content based on format
    if output_format == "text":
        return result.content

    elif output_format == "json":
        # Build JSON structure
        output = {
            "content": result.content,
            "pages": [],
            "tables": [],
            "paragraphs": []
        }

        # Extract pages
        for page in result.pages:
            output["pages"].append({
                "page_number": page.page_number,
                "width": page.width,
                "height": page.height,
                "unit": page.unit,
                "lines": [
                    {
                        "content": line.content,
                        "polygon": [{"x": p.x, "y": p.y} for p in line.polygon]
                    }
                    for line in page.lines
                ]
            })

        # Extract tables
        for table in result.tables:
            cells = []
            for cell in table.cells:
                cells.append({
                    "row_index": cell.row_index,
                    "column_index": cell.column_index,
                    "row_span": cell.row_span,
                    "column_span": cell.column_span,
                    "content": cell.content
                })

            output["tables"].append({
                "row_count": table.row_count,
                "column_count": table.column_count,
                "cells": cells
            })

        # Extract paragraphs
        for para in result.paragraphs:
            output["paragraphs"].append({
                "content": para.content,
                "role": para.role if hasattr(para, 'role') else None
            })

        return output

    elif output_format == "tables":
        # Extract only tables in markdown format
        tables_md = []
        for i, table in enumerate(result.tables):
            # Build markdown table
            md_table = f"\n## Table {i+1}\n\n"

            # Build table matrix
            max_row = max(cell.row_index for cell in table.cells) + 1
            max_col = max(cell.column_index for cell in table.cells) + 1
            matrix = [["" for _ in range(max_col)] for _ in range(max_row)]

            for cell in table.cells:
                matrix[cell.row_index][cell.column_index] = cell.content

            # Convert to markdown
            for row_idx, row in enumerate(matrix):
                md_table += "| " + " | ".join(row) + " |\n"
                if row_idx == 0:  # Add separator after header
                    md_table += "|" + "|".join(["---" for _ in range(len(row))]) + "|\n"

            tables_md.append(md_table)

        return "\n".join(tables_md) if tables_md else "No tables found."


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_layout.py <image_path> [--format text|json|tables]")
        sys.exit(1)

    image_path = sys.argv[1]
    output_format = "text"

    # Parse optional format argument
    if len(sys.argv) > 2 and sys.argv[2] == "--format":
        if len(sys.argv) > 3:
            output_format = sys.argv[3]

    if "--tables-only" in sys.argv:
        output_format = "tables"

    try:
        result = extract_layout(image_path, output_format)

        if output_format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(result)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
