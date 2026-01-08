# YOLO Annotator v3.0 - AI-Assisted Labeling

## Location
`YOLO/scripts/annotator.py`

## Features Added (2025-12-04)

### AI-Assisted Labeling
- **Auto-Detect (Space)**: Runs YOLO inference on current page
- **AI Suggestions**: Displayed as green dashed boxes with confidence labels
- **Accept/Reject Workflow**: Enter to accept, X to reject, Ctrl+A for all
- **Confidence Slider**: Filter suggestions by threshold (10-95%)
- **Background Model Loading**: Non-blocking UI during initialization

### Model Discovery
The annotator searches for models in this order:
1. `YOLO/best.pt`
2. `YOLO/runs/role_detection/weights/best.pt`
3. `YOLO/customers/troester/models/plc_model.pt`

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| Space | Run Auto-Detect |
| Enter | Accept selected suggestion |
| X | Reject selected suggestion |
| Ctrl+A | Accept all suggestions |
| 1-9 | Select class |
| A/D | Previous/Next page |
| S | Save |
| Del | Delete selected label |

### Technical Notes
- Uses `ultralytics` YOLO library (graceful fallback if not installed)
- Threaded inference prevents UI freezing
- Suggestions stored separately from confirmed annotations
- Visual distinction: solid lines (confirmed) vs dashed lines (suggestions)
- Automatic class mapping between model and local classes

### Dependencies
```bash
pip install ultralytics  # Required for auto-detect
pip install pymupdf      # PDF rendering
pip install pillow       # Image processing
```

### Usage
```bash
cd YOLO/scripts
python annotator.py
```

1. Open PDF with "📂 PDF Aç"
2. Press Space to auto-detect components
3. Adjust confidence threshold slider
4. Accept (Enter) or reject (X) suggestions
5. Draw manual boxes if needed
6. Press S to save
