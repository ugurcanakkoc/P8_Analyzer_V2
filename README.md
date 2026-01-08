# P8 Analyzer V2

A professional PDF-based electrical schematic analysis tool for P8-format drawings. Automatically detects terminals, reads labels, and generates connection reports (netlists).

## Features

- **Vector Analysis**: Parse PDF vector data to detect structural elements (lines, circles, paths)
- **Terminal Detection**: Identify terminal blocks as unfilled circles in electrical schematics
- **Hybrid Text Recognition**: Combine PDF text layer with OCR fallback for accurate label reading
- **Smart Grouping**: Assign group labels (e.g., -X1, -X2) using inheritance algorithm
- **Pin Detection**: Find pin labels at wire endpoints inside component boxes
- **Connection Reports**: Generate netlists showing terminal-to-component connectivity
- **Interactive GUI**: Navigate PDFs, draw component boxes, view analysis results

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

### Dependencies

```bash
pip install PyQt5 pymupdf pydantic pillow numpy
```

Optional (for OCR fallback):
```bash
pip install easyocr
```

Optional (for YOLO component detection):
```bash
pip install ultralytics
```

### Clone and Run

```bash
git clone https://github.com/your-repo/P8_Analyzer_V2.git
cd P8_Analyzer_V2
python start_gui.py
```

## Usage

### Basic Workflow

1. **Open PDF**: Click "PDF Ac" or let the app auto-load `data/ornek.pdf`
2. **Navigate**: Use "Onceki/Sonraki" buttons to browse pages
3. **Analyze**: Click "Analiz Et" to run vector analysis
4. **Draw Boxes**: Switch to "Kutu Ciz" mode to mark component boundaries
5. **Check Connections**: Click "Baglanti Kontrol" to generate netlist

### Analysis Output

The analysis produces:
- **Terminals**: List of detected terminal blocks with labels
- **Groups**: Terminal groupings (-X1:1, -X1:2, -X2:PE, etc.)
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
├── start_gui.py              # Application entry point
├── gui/                      # PyQt5 GUI components
│   ├── main_window.py        # Main application window
│   ├── viewer.py             # Interactive PDF viewer
│   ├── worker.py             # Background analysis thread
│   ├── circuit_logic.py      # Connection detection logic
│   └── ocr_worker.py         # OCR comparison worker
├── src/                      # Core analysis modules
│   ├── models.py             # Pydantic data models
│   ├── terminal_detector.py  # Terminal circle detection
│   ├── terminal_reader.py    # Label reading with text engine
│   ├── terminal_grouper.py   # Group assignment algorithm
│   ├── pin_finder.py         # Pin detection in boxes
│   └── text_engine.py        # Hybrid PDF/OCR text engine
├── YOLO/                     # ML component detection
│   ├── scripts/              # Training scripts
│   ├── images/               # Training images
│   ├── labels/               # Annotation labels
│   └── best.pt               # Trained model weights
├── data/                     # Sample files
│   └── ornek.pdf             # Example P8 schematic
└── tests/                    # Test suite
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
│  6. Pin Finding (PinFinder)                                      │
│     - Find wire endpoints inside component boxes                 │
│     - Read pin labels near endpoints                             │
│     - Associate pins with boxes                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. Connection Analysis (circuit_logic)                          │
│     - Match structural groups to terminals and boxes             │
│     - Build netlist from intersections                           │
│     - Generate connection report                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         OUTPUT                                   │
│  - Terminal list with labels and groups                          │
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
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov=gui --cov-report=html
```

## Development

### Adding New Terminal Types

1. Modify `src/terminal_detector.py`
2. Update the `_is_terminal()` method with new criteria
3. Add tests in `tests/unit/test_terminal_detector.py`

### Improving OCR Accuracy

1. Adjust `SearchProfile` parameters in `src/text_engine.py`
2. Fine-tune regex patterns for label validation
3. Test with the OCR comparison tool in the GUI

### Training YOLO Model

1. Add annotated images to `YOLO/images/` and `YOLO/labels/`
2. Update `YOLO/multi_class_data.yaml` with class definitions
3. Run training: `python YOLO/scripts/train_multi_class.py`

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
