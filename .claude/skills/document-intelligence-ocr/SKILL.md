---
name: document-intelligence-ocr
description: Extract text and layout from images using Microsoft Azure Document Intelligence Layout model. Use when user wants to OCR images, extract tables, or analyze document structure.
allowed-tools: Read, Write, Bash
---

# Document Intelligence OCR

Extract text, layout, and tables from images using Azure Document Intelligence.

## When to Use
- Extract text from images (PNG, JPG, TIFF, PDF)
- OCR scanned documents
- Extract tables from images
- Analyze document layout

## Prerequisites

**Environment Variables:**
```bash
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=your_key_here
```

**Python Package:**
```bash
pip install azure-ai-formrecognizer==3.3.0
```

## Instructions

1. Validate environment variables are set
2. Check if `azure-ai-formrecognizer` is installed
3. Run `python scripts/extract_layout.py <image_path>`
4. Parse JSON output and format for user

## Example

```bash
python .claude/skills/document-intelligence-ocr/scripts/extract_layout.py invoice.png
```
