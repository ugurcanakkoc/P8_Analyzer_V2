# Architecture & Analysis Pipeline

Back-link: referenced from `CLAUDE.md`. See `README.md` / `README_TR.md` for the human-facing overview.

## Project Structure

```
P8_Analyzer_V2/
├── start_gui.py              # GUI entry point
├── analyze_pdf.py            # CLI entry point
├── p8_analyzer/              # Main package (modern structure)
│   ├── __init__.py           # Package exports
│   ├── core/                 # Vector analysis (UVP integrated)
│   │   ├── models.py         # Pydantic data models
│   │   ├── analyzer.py       # Page vector analysis
│   │   ├── session.py        # AnalysisSession data structure
│   │   └── export.py         # SVG/PNG export
│   ├── models/               # Additional data models package
│   ├── detection/            # Terminal & component detection
│   │   ├── terminal_detector.py
│   │   ├── terminal_reader.py
│   │   ├── terminal_grouper.py
│   │   ├── wire_annotation_reader.py  # Wire annotation capture
│   │   ├── pin_finder.py
│   │   ├── busbar_finder.py
│   │   ├── cluster_detector.py / cluster_settings.py
│   │   ├── component_detector.py / component_namer.py
│   │   ├── device_tagger.py
│   │   └── label_detector.py / label_matcher.py
│   ├── text/                 # Text extraction
│   │   └── hybrid_engine.py  # PDF + OCR text engine
│   ├── circuit/              # Connection analysis
│   │   └── connection_logic.py
│   ├── cli/                  # Command-line interface
│   │   ├── analyzer.py       # PDFAnalyzer class
│   │   ├── output.py         # JSON/CSV/Text formatters
│   │   └── main.py           # CLI entry point
│   └── gui/                  # PyQt5 GUI components
│       ├── main_window.py
│       ├── viewer.py
│       ├── worker.py / classifier_worker.py / llm_worker.py / ocr_worker.py
│       └── i18n.py
├── YOLO/                     # ML training for component detection
├── data/                     # Sample PDFs (ornek.pdf)
├── tests/                    # Test suite (hierarchical)
├── venv/                     # Python virtual environment
└── requirements.txt          # All dependencies
```

## Key Imports

```python
# Core analysis
from p8_analyzer.core import analyze_page_vectors, VectorAnalysisResult, Point

# Detection
from p8_analyzer.detection import TerminalDetector, TerminalReader, PinFinder

# Text
from p8_analyzer.text import HybridTextEngine

# Circuit
from p8_analyzer.circuit import check_intersections, CircuitComponent
```

## Analysis Pipeline

**Input:** PDF file (P8-format electrical schematic) + page number to analyze.

**Processing steps:**
1. **PDF Loading** — PyMuPDF opens document
2. **Vector Extraction** — Extract paths, circles from PDF
3. **Terminal Detection** — Find unfilled circles matching terminal criteria
4. **Label Reading** — Read text near terminals (PDF text layer + OCR)
5. **Group Assignment** — Assign group labels (-X1, -X2) with inheritance
6. **Pin Finding** — Detect pins at wire endpoints in component boxes
7. **Connection Analysis** — Build netlist from structural groups

**Output:** Terminal list with labels/groups, connection report (netlist), visual overlay on PDF.

## Common Tasks

### Adding new terminal detection criteria
1. Modify `p8_analyzer/detection/terminal_detector.py`
2. Update `_is_terminal()` method
3. Add unit tests in `tests/unit/test_terminal_detector.py`

### Improving OCR accuracy
1. Modify `p8_analyzer/text/hybrid_engine.py`
2. Adjust `SearchProfile` parameters
3. Compare against `p8_analyzer/gui/ocr_worker.py`

### Adding new component types
1. Update YOLO training data in `YOLO/images/` and `YOLO/labels/`
2. Modify `YOLO/multi_class_data.yaml`
3. Retrain — see `docs/yolo-training.md`
