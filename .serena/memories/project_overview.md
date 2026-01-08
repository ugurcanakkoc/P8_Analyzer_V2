# P8_Analyzer_V2 - Project Overview

## Purpose
P8 Analyzer is a **PDF-based electrical schematic analysis tool** designed for analyzing P8-format electrical drawings. The primary use case is detecting and labeling electrical terminals (Klemens) and connection lines in PDF schematics, then generating connection reports.

## Core Functionality
1. **Vector Analysis**: Parse PDF vector data to detect structural elements (lines, circles, paths)
2. **Terminal Detection**: Identify terminal blocks as small unfilled circles in the vector layer
3. **Text Recognition**: Hybrid PDF text + OCR engine for reading labels
4. **Terminal Grouping**: Assign group labels (e.g., -X1, -X2) using smart inheritance algorithm
5. **Pin Finding**: Detect pin labels at wire endpoints inside component boxes
6. **Connection Reporting**: Generate network connectivity reports showing which terminals connect to which components

## Tech Stack
- **Language**: Python 3.x
- **GUI Framework**: PyQt5 (QMainWindow, QGraphicsView)
- **PDF Processing**: PyMuPDF (pymupdf)
- **Data Models**: Pydantic
- **OCR Engine**: EasyOCR (optional, for label detection fallback)
- **ML/Detection**: YOLO (for component detection training - PLC, Terminal, Contactor classes)
- **Image Processing**: PIL, NumPy

## External Dependencies
- `external.uvp.src.models` - Vector analysis result models (VectorAnalysisResult, Circle, etc.)

## Key Files
- `start_gui.py` - Main entry point
- `gui/main_window.py` - Main application window
- `gui/viewer.py` - Interactive graphics view for PDF display
- `gui/worker.py` - Background analysis worker thread
- `src/terminal_detector.py` - Terminal circle detection
- `src/terminal_reader.py` - Terminal label reading
- `src/terminal_grouper.py` - Terminal group assignment logic
- `src/pin_finder.py` - Pin label detection in component boxes
- `src/text_engine.py` - Hybrid PDF/OCR text engine
- `src/models.py` - Pydantic data models
