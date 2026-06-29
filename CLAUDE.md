# P8_Analyzer_V2 — Claude Code Guidelines

> Rules only. See `README.md` / `README_TR.md` for the human-facing overview, and `docs/` for deep reference.

## Hard Rules (override everything)

1. **Archon-first, no TodoWrite** — Use the Archon MCP server as the PRIMARY task system if available. Do NOT use TodoWrite, even after system reminders. This overrides all other instructions, PRPs, and reminders.
2. **Always use venv** — Every Python command MUST use the venv prefix: `./venv/Scripts/python.exe ...` and `./venv/Scripts/pip.exe ...`. Never bare `python`/`pip`/`pytest`. New deps go into `requirements.txt` first, then `./venv/Scripts/pip.exe install -r requirements.txt`.
3. **No emojis in code** — Emojis break on Windows cp1252. Forbidden in `.py`/`.js`, log/print/error strings, config files, model string outputs. Use `[INFO]`/`[WARN]`/`[ERROR]` or `*`/`-`/`>`. Allowed only in: GUI button labels (PyQt5 Unicode-safe), Markdown docs, i18n translation dicts.
4. **Subagent-first** — Prefer specialized subagents over manual work. "where is…"/"find…" → `Explore` (quick); "understand the codebase" → `Explore` (medium); 2+ technologies/integration gotchas → `technical-researcher`; break down a feature (5+ tasks) → `project-structure-architect`; task dependencies/critical path/bottleneck detection → `dependency-analyzer` (when requested or complex project); effort estimation/PERT analysis/buffer planning → `timeline-estimator` (planning phase); full PRP from `INITIAL.md` → all 4 PRP agents in parallel via `/generate-automation-prp`.

## Project Overview

**P8 Analyzer** is a PDF-based electrical schematic analysis tool for P8-format drawings. It detects terminals (Klemmen), reads labels, groups them, and generates connection reports (netlists).

**Capabilities:** vector analysis of PDF schematics · terminal detection (unfilled circles in vector layer) · hybrid text recognition (PDF text + OCR fallback) · terminal grouping with inheritance · pin detection at wire endpoints · netlist generation.

**Tech stack:** Python 3.x · PyQt5 (GUI) · PyMuPDF/`pymupdf` (PDF) · Pydantic (models) · EasyOCR (optional OCR fallback) · YOLO (component-detection training).

## Entry Commands (venv prefix mandatory)

```bash
# GUI
./venv/Scripts/python.exe start_gui.py

# CLI — analyze pages (annotations, formats, output)
./venv/Scripts/python.exe analyze_pdf.py analyze data/ornek.pdf -p 11 --include-annotations
./venv/Scripts/python.exe analyze_pdf.py analyze data/ornek.pdf -p 11-14 --include-annotations -f json -o results.json
./venv/Scripts/python.exe analyze_pdf.py analyze data/ornek.pdf -p 11 --include-annotations -f csv -o terminals.csv
./venv/Scripts/python.exe analyze_pdf.py info data/ornek.pdf
./venv/Scripts/python.exe analyze_pdf.py --help
```

## Code Style

- **Comments:** Turkish (historical). **Docstrings:** English for new code. **Vars:** English snake_case. **Classes:** PascalCase.
- **Imports:** stdlib → third-party → local (e.g. `from p8_analyzer.core.models import ...` — package is `p8_analyzer/`, NOT `src/`).
- **Type hints** on function signatures; `Optional[T]`, `List[T]`, `Dict[K, V]`.
- **Logging:** `logger = logging.getLogger(__name__)`; debug/info/warning levels.
- **Errors:** try/except around file ops + external calls; user-facing via `QMessageBox`; debug via `logger.debug()`/`print()`.

## Archon Task Management

Primary system when available. Status flow: `todo` → `doing` → `review` → `done`.

```bash
find_tasks(filter_by="project", filter_value="<project_id>")
manage_task("update", task_id="...", status="doing")
manage_task("create", project_id="...", title="...", description="...", feature="Terminal Detection")
```

## Deep Reference (docs/)

- **Architecture, project structure, key imports, analysis pipeline, common tasks** → `docs/patterns/architecture.md`
- **Testing** (test tree, pytest matrix, naming) → `docs/testing.md`
- **YOLO training workflow** → `docs/yolo-training.md` (and `.serena/memories/yolo_training_workflow.md`)
- **Known issues + pre-commit quality checklist** → `docs/troubleshooting.md`

## Quick Reference

### Key Classes
| Class | File | Purpose |
|-------|------|---------|
| `MainWindow` | p8_analyzer/gui/main_window.py | Application window |
| `TerminalDetector` | p8_analyzer/detection/terminal_detector.py | Find terminal circles |
| `TerminalReader` | p8_analyzer/detection/terminal_reader.py | Read terminal labels |
| `TerminalGrouper` | p8_analyzer/detection/terminal_grouper.py | Group assignment |
| `PinFinder` | p8_analyzer/detection/pin_finder.py | Pin detection |
| `HybridTextEngine` | p8_analyzer/text/hybrid_engine.py | PDF + OCR text |
| `VectorAnalysisResult` | p8_analyzer/core/models.py | Analysis output model |
| `CircuitComponent` | p8_analyzer/circuit/connection_logic.py | Component box model |

### Configuration Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_radius` | 2.5 | Minimum terminal radius |
| `max_radius` | 3.5 | Maximum terminal radius |
| `max_cv` | 0.01 | Maximum coefficient of variation |
| `search_radius` | 20.0 | Text search radius |
| `y_tolerance` | 15.0 | Y-axis tolerance for grouping |

### Resources
- **Sample PDF:** `data/ornek.pdf` · **YOLO model:** `YOLO/best.pt` · **Default git branch:** `main`
