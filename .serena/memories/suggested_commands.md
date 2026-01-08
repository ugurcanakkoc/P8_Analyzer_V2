# Suggested Commands for P8_Analyzer_V2

## Running the Application
```bash
# Main GUI application
python start_gui.py
```

## Development Commands (Windows)

### File Operations
```bash
# List directory (PowerShell)
Get-ChildItem -Path . -Recurse -Depth 2

# Search for files
Get-ChildItem -Path . -Recurse -Filter "*.py"

# Search in files (grep equivalent)
Select-String -Path "*.py" -Pattern "class.*:"
```

### Git Commands
```bash
git status
git add .
git commit -m "message"
git push
git log --oneline -10
```

### Python Environment
```bash
# Install dependencies (if requirements.txt exists)
pip install -r requirements.txt

# Install specific packages used
pip install PyQt5 pymupdf pydantic easyocr pillow numpy
```

## YOLO Training (if needed)
```bash
# Located in YOLO/scripts/
python YOLO/scripts/train_yolo.py
python YOLO/scripts/train_multi_class.py
python YOLO/scripts/annotator.py
```

## Testing
No formal test framework detected. Manual testing via GUI:
1. Run `python start_gui.py`
2. Load PDF from `data/ornek.pdf` (auto-loads by default)
3. Click "Analiz Et" to run analysis
4. Check terminal detection in log panel
