# Task Completion Checklist

## Before Committing Changes

1. **Test the GUI**
   - Run `python start_gui.py`
   - Verify the application opens without errors
   - Test the specific functionality you modified

2. **Check Logs**
   - Review console output for warnings/errors
   - Check the log panel in the GUI for analysis results

3. **Code Review**
   - Ensure imports are correct (especially external.uvp.src.models)
   - Check for syntax errors
   - Verify type hints match actual types

## Testing

### Test Structure
```
tests/
├── conftest.py           # Shared fixtures
├── unit/                 # Isolated component tests
│   ├── test_models.py
│   ├── test_terminal_detector.py
│   ├── test_terminal_reader.py
│   ├── test_terminal_grouper.py
│   ├── test_pin_finder.py
│   └── test_text_engine.py
├── integration/          # Component interaction tests
│   ├── test_detection_pipeline.py
│   └── test_text_extraction.py
├── e2e/                  # End-to-end tests
│   └── test_full_analysis.py
└── fixtures/             # Test data
```

### Running Tests
```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# E2E tests
pytest tests/e2e/ -v

# With coverage
pytest tests/ --cov=src --cov=gui --cov-report=html
```

## No CI/CD Pipeline Yet
This project does not have:
- Linting configuration (flake8, pylint)
- Formatting tools (black, isort)
- Pre-commit hooks

## Manual Verification Steps
1. Load the default PDF (`data/ornek.pdf`)
2. Navigate to a page with terminals
3. Click "Analiz Et" (Analyze)
4. Verify terminal detection in logs
5. Check "Bağlantı Kontrol" (Connection Check) works
