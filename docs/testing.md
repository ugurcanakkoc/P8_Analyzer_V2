# Testing Guidelines

Back-link: referenced from `CLAUDE.md`. All pytest commands MUST use the venv prefix (`./venv/Scripts/python.exe -m pytest ...`).

## Test Structure (Hierarchical)

```
tests/
├── unit/                 # Isolated component tests
│   ├── test_models.py
│   ├── test_terminal_detector.py
│   ├── test_terminal_reader.py
│   ├── test_terminal_grouper.py
│   ├── test_pin_finder.py
│   └── test_text_engine.py
├── integration/          # Component interaction tests
│   ├── test_detection_pipeline.py
│   ├── test_text_extraction.py
│   └── test_grouping_workflow.py
├── e2e/                  # End-to-end tests
│   └── test_full_analysis.py
├── fixtures/             # Test data
│   ├── sample_pdfs/
│   └── mock_data/
└── conftest.py           # Shared fixtures
```

## Running Tests

```bash
# All tests
./venv/Scripts/python.exe -m pytest tests/ -v

# By layer
./venv/Scripts/python.exe -m pytest tests/unit/ -v
./venv/Scripts/python.exe -m pytest tests/integration/ -v
./venv/Scripts/python.exe -m pytest tests/e2e/ -v

# With coverage
./venv/Scripts/python.exe -m pytest tests/ --cov=p8_analyzer --cov-report=html
```

## Test Naming

- `test_<function_name>_<scenario>_<expected_result>`
- Example: `test_detect_terminals_with_valid_circles_returns_terminals`
