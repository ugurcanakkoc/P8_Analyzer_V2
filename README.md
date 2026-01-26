# P8 Analyzer V2

A professional PDF-based electrical schematic analysis tool for P8-format drawings. Automatically detects terminals, reads labels, and generates connection reports (netlists).

> **See [OPEN_TASKS.md](OPEN_TASKS.md) for pending tasks and known issues.**

## Features

- **Vector Analysis**: Parse PDF vector data to detect structural elements (lines, circles, paths)
- **Terminal Detection**: Identify terminal blocks as unfilled circles in electrical schematics
- **Hybrid Text Recognition**: Combine PDF text layer with OCR fallback for accurate label reading
- **Smart Grouping**: Assign group labels (e.g., -X1, -X2) using inheritance algorithm
- **Pin Detection**: Find pin labels at wire endpoints inside component boxes
- **Wire Annotation Capture**: Detect and read wire annotation labels from schematics
- **Connection Reports**: Generate netlists showing terminal-to-component connectivity
- **Interactive GUI**: Navigate PDFs, draw component boxes, view analysis results
- **CLI Support**: Headless analysis for batch processing and automation

## Screenshots

The application provides:
- PDF viewer with zoom and pan
- Terminal overlay visualization
- Log panel for analysis results
- Connection report generation

## Installation

### Prerequisites

- Python 3.8+
- Windows (tested), Linux/macOS (should work)

### Setup with Virtual Environment (Recommended)

```bash
git clone https://github.com/your-repo/P8_Analyzer_V2.git
cd P8_Analyzer_V2

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

Core dependencies (in requirements.txt):
- PyQt5 - GUI framework
- pymupdf - PDF processing
- pydantic - Data models
- pillow - Image processing
- numpy - Numerical operations

Optional:
- easyocr - OCR fallback
- ultralytics - YOLO component detection

## Usage

### GUI Mode

```bash
# Windows
.\venv\Scripts\python.exe start_gui.py

# Linux/macOS
./venv/bin/python start_gui.py
```

### CLI Mode

```bash
# Analyze single page with wire annotations
.\venv\Scripts\python.exe analyze_pdf.py analyze data/ornek.pdf -p 11 --include-annotations

# Analyze multiple pages, save as JSON
.\venv\Scripts\python.exe analyze_pdf.py analyze data/ornek.pdf -p 11-14 --include-annotations -f json -o results.json

# CSV output for spreadsheet import
.\venv\Scripts\python.exe analyze_pdf.py analyze data/ornek.pdf -p 11 --include-annotations -f csv -o terminals.csv

# Show PDF info
.\venv\Scripts\python.exe analyze_pdf.py info data/ornek.pdf

# Full help
.\venv\Scripts\python.exe analyze_pdf.py --help
```

### Basic GUI Workflow

1. **Open PDF**: Click "PDF Ac" or let the app auto-load `data/ornek.pdf`
2. **Navigate**: Use "Onceki/Sonraki" buttons to browse pages
3. **Analyze**: Click "Analiz Et" to run vector analysis
4. **Draw Boxes**: Switch to "Kutu Ciz" mode to mark component boundaries
5. **Check Connections**: Click "Baglanti Kontrol" to generate netlist

### Analysis Output

The analysis produces:
- **Terminals**: List of detected terminal blocks with labels
- **Groups**: Terminal groupings (-X1:1, -X1:2, -X2:PE, etc.)
- **Wire Annotations**: Detected wire labels from schematics
- **Connections**: Netlist showing which terminals connect to which components

Example output:
```
====== CONNECTION REPORT ======
NET-001 Line:
   Terminal -X1:1
   Terminal -X1:2
   BOX-1:13
NET-002 Line:
   Terminal -X2:PE
   Terminal -X3:PE
```

## Architecture

```
P8_Analyzer_V2/
├── start_gui.py              # GUI entry point
├── analyze_pdf.py            # CLI entry point
├── p8_analyzer/              # Main package
│   ├── __init__.py           # Package exports
│   ├── core/                 # Core analysis modules
│   │   ├── models.py         # Pydantic data models
│   │   ├── analyzer.py       # Page vector analysis
│   │   ├── analysis_engine.py # Unified analysis engine
│   │   ├── session.py        # Analysis session management
│   │   └── export.py         # SVG/PNG export
│   ├── detection/            # Detection modules
│   │   ├── terminal_detector.py
│   │   ├── terminal_reader.py
│   │   ├── terminal_grouper.py
│   │   ├── wire_annotation_reader.py
│   │   ├── pin_finder.py
│   │   ├── busbar_finder.py
│   │   └── cluster_detector.py
│   ├── text/                 # Text extraction
│   │   └── hybrid_engine.py  # PDF + OCR text engine
│   ├── circuit/              # Connection analysis
│   │   └── connection_logic.py
│   ├── cli/                  # CLI module
│   │   ├── analyzer.py       # PDFAnalyzer class
│   │   ├── output.py         # JSON/CSV/Text formatters
│   │   └── main.py           # CLI entry point
│   └── gui/                  # PyQt5 GUI components
│       ├── main_window.py
│       ├── viewer.py
│       └── worker.py
├── YOLO/                     # ML component detection
│   ├── scripts/              # Training scripts
│   ├── data/                 # Training data
│   └── best.pt               # Trained model weights
├── data/                     # Sample files
│   └── ornek.pdf             # Example P8 schematic
├── tests/                    # Test suite
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── e2e/                  # End-to-end tests
├── PRP/                      # Project requirements
│   ├── REQUIREMENTS.md       # Full requirements spec
│   ├── requirements/         # Additional docs
│   └── feedback/             # Customer feedback
├── OPEN_TASKS.md             # Pending tasks list
└── requirements.txt          # Python dependencies
```

## Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                         INPUT                                    │
│  PDF File (P8-format electrical schematic) + Page Number         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. PDF Loading (PyMuPDF)                                        │
│     - Open document                                              │
│     - Load specific page                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Vector Extraction (UVP Library)                              │
│     - Extract paths, circles, structural groups                  │
│     - Build VectorAnalysisResult                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Terminal Detection (TerminalDetector)                        │
│     - Find unfilled circles matching criteria                    │
│     - Filter by radius (2.5-3.5) and CV (<0.01)                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Label Reading (TerminalReader + HybridTextEngine)            │
│     - Search PDF text layer near terminal centers                │
│     - OCR fallback if PDF text not found                         │
│     - Apply regex filters for valid labels                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. Group Assignment (TerminalGrouper)                           │
│     - Search for group labels (-X1, -X2) on the left            │
│     - Inherit group from left/top neighbor if not found          │
│     - Generate full labels (Group:Pin format)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. Wire Annotation Capture (WireAnnotationReader)               │
│     - Find wire annotation labels near structural groups         │
│     - Associate annotations with wire segments                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. Pin Finding (PinFinder)                                      │
│     - Find wire endpoints inside component boxes                 │
│     - Read pin labels near endpoints                             │
│     - Associate pins with boxes                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  8. Connection Analysis (AnalysisEngine)                         │
│     - Match structural groups to terminals and boxes             │
│     - Build netlist from intersections                           │
│     - Generate connection report                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         OUTPUT                                   │
│  - Terminal list with labels and groups                          │
│  - Wire annotations                                              │
│  - Connection report (netlist)                                   │
│  - Visual overlay on PDF                                         │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration

### Terminal Detection Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_radius` | 2.5 | Minimum terminal circle radius |
| `max_radius` | 3.5 | Maximum terminal circle radius |
| `max_cv` | 0.01 | Maximum coefficient of variation (roundness) |
| `only_unfilled` | True | Only detect unfilled circles |

### Text Search Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `search_radius` | 20.0 | Search radius for text near terminals |
| `direction` | top_right | Primary search direction |
| `y_tolerance` | 15.0 | Y-axis tolerance for grouping |

### Pin Finder Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pin_search_radius` | 75.0 | Search radius for pin labels |

## Testing

```bash
# Run all tests
.\venv\Scripts\python.exe -m pytest tests/ -v

# Unit tests only
.\venv\Scripts\python.exe -m pytest tests/unit/ -v

# Integration tests
.\venv\Scripts\python.exe -m pytest tests/integration/ -v

# E2E tests
.\venv\Scripts\python.exe -m pytest tests/e2e/ -v

# With coverage
.\venv\Scripts\python.exe -m pytest tests/ --cov=p8_analyzer --cov-report=html
```

## Development

### Adding New Terminal Types

1. Modify `p8_analyzer/detection/terminal_detector.py`
2. Update the `_is_terminal()` method with new criteria
3. Add tests in `tests/unit/test_terminal_detector.py`

### Improving OCR Accuracy

1. Adjust `SearchProfile` parameters in `p8_analyzer/text/hybrid_engine.py`
2. Fine-tune regex patterns for label validation
3. Test with the OCR comparison tool in the GUI

### Training YOLO Model

1. Add annotated images to `YOLO/data/images/` and `YOLO/data/labels/`
2. Update `YOLO/data/dataset.yaml` with class definitions
3. Run training: `.\venv\Scripts\python.exe YOLO/scripts/train_label_detector.py`

See `YOLO/scripts/` for additional training utilities.

## Open Tasks

See [OPEN_TASKS.md](OPEN_TASKS.md) for:
- Pending development tasks
- Known issues and limitations
- Customer feedback integration status

## License

[Add your license here]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Acknowledgments

- PyMuPDF for PDF processing
- EasyOCR for optical character recognition
- Ultralytics YOLO for object detection
