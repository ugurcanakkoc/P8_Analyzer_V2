# P8_Analyzer_V2 Architecture

## Component Flow

```
PDF File
    │
    ▼
┌─────────────────────────────────┐
│  PyMuPDF (pymupdf)              │
│  - Load PDF pages               │
│  - Extract vector drawings      │
│  - Get text layer               │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  UVP Vector Analysis            │
│  (external.uvp.src.models)      │
│  - VectorAnalysisResult         │
│  - StructuralGroup              │
│  - Circle, PathElement          │
└─────────────────────────────────┘
    │
    ├──────────────────┬──────────────────┐
    ▼                  ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│ Terminal     │ │ Pin Finder   │ │ Circuit Logic    │
│ Detection    │ │ (box pins)   │ │ (connections)    │
│              │ │              │ │                  │
│ - detector   │ │ - pin_finder │ │ - circuit_logic  │
│ - reader     │ │              │ │                  │
│ - grouper    │ │              │ │                  │
└──────────────┘ └──────────────┘ └──────────────────┘
    │                  │                  │
    └──────────────────┴──────────────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  Connection      │
              │  Report          │
              │  (Netlist)       │
              └──────────────────┘
```

## Directory Structure
```
P8_Analyzer_V2/
├── start_gui.py          # Entry point
├── gui/                  # PyQt5 GUI components
│   ├── main_window.py    # Main window
│   ├── viewer.py         # Graphics view
│   ├── worker.py         # Analysis thread
│   ├── circuit_logic.py  # Connection detection
│   └── ocr_worker.py     # OCR comparison worker
├── src/                  # Core logic
│   ├── models.py         # Pydantic data models
│   ├── terminal_detector.py
│   ├── terminal_reader.py
│   ├── terminal_grouper.py
│   ├── pin_finder.py
│   └── text_engine.py    # Hybrid text/OCR engine
├── YOLO/                 # ML training scripts
│   ├── scripts/          # Training scripts
│   ├── images/           # Training images
│   ├── labels/           # Annotations
│   └── best.pt           # Trained model weights
├── data/                 # Sample PDFs
│   └── ornek.pdf         # Example schematic
└── external/             # External dependencies
    └── uvp/              # UVP vector processing lib
```

## Key Classes
- `MainWindow` (gui/main_window.py) - Application window
- `InteractiveGraphicsView` (gui/viewer.py) - PDF display canvas
- `AnalysisWorker` (gui/worker.py) - Background analysis
- `TerminalDetector` (src/terminal_detector.py) - Find terminal circles
- `TerminalReader` (src/terminal_reader.py) - Read terminal labels
- `TerminalGrouper` (src/terminal_grouper.py) - Group terminals
- `PinFinder` (src/pin_finder.py) - Find pins in boxes
- `HybridTextEngine` (src/text_engine.py) - PDF + OCR text search
