---
name: markitdown-pdf
description: Extract text and convert PDF files to markdown using markitdown library locally. Use when user wants to convert PDFs to markdown, extract PDF content, or parse PDF documents locally without cloud services.
allowed-tools: Read, Write, Bash
---

# Markitdown PDF Converter

Convert PDF files to markdown format using the markitdown library (local processing, no cloud required).

## When to Use
- Convert PDF to markdown
- Extract text from PDF files
- Parse PDF documents locally
- User wants offline PDF processing
- User mentions "markitdown" or "PDF to markdown"

## Prerequisites

**Python Package:**
```bash
pip install markitdown
```

**No API keys or environment variables required** - runs completely locally!

## Instructions

1. Check if `markitdown` is installed (if not, install it)
2. Run `python scripts/pdf_to_markdown.py <pdf_path>`
3. Script converts PDF to markdown
4. Save output to `.md` file or display to user

## Example

```bash
python .claude/skills/markitdown-pdf/scripts/pdf_to_markdown.py document.pdf
```

Output: `document.md` with converted content
