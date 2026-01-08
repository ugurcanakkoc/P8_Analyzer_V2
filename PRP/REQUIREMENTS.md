# P8 Analyzer V2 - Unified Requirements Document

**Version:** 1.0
**Date:** January 2026
**Status:** Active Development
**Stakeholders:** UVP Schaltschränke, neurawork GmbH

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Project Overview](#2-project-overview)
3. [Current State Analysis](#3-current-state-analysis)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Technical Requirements](#6-technical-requirements)
7. [YOLO Model Training Requirements](#7-yolo-model-training-requirements)
8. [Integration Requirements](#8-integration-requirements)
9. [Acceptance Criteria](#9-acceptance-criteria)
10. [Dependencies & Constraints](#10-dependencies--constraints)
11. [Risk Assessment](#11-risk-assessment)
12. [Roadmap & Milestones](#12-roadmap--milestones)
13. [Appendix](#13-appendix)

---

## 1. Executive Summary

**P8 Analyzer V2** is a professional PDF-based electrical schematic analysis tool designed for P8-format drawings. The system automatically detects terminals (Klemens), reads labels, groups them using an inheritance algorithm, finds pins at wire endpoints, and generates connection reports (netlists).

### Key Objectives
- Automate electrical schematic analysis for P8-format PDFs
- Achieve high accuracy in terminal and component detection
- Generate reliable netlists for production use
- Support multiple CAD software outputs (EPLAN, WS CAD, etc.)

### Target Users
- Electrical engineers at UVP Schaltschränke
- Control panel manufacturers
- Automation engineers

---

## 2. Project Overview

### 2.1 Purpose

Transform PDF electrical schematics into structured data:
- **Input**: P8-format PDF files (electrical schematics)
- **Output**: Terminal lists, connection reports (netlists), visual overlays

### 2.2 Core Capabilities

| Capability | Description | Status |
|------------|-------------|--------|
| Vector Analysis | Parse PDF vector data (lines, circles, paths) | Implemented |
| Terminal Detection | Identify unfilled circles as terminals | Implemented |
| Label Reading | Hybrid PDF text + OCR fallback | Implemented |
| Group Assignment | Inheritance algorithm (-X1, -X2) | Implemented |
| Pin Detection | Find pins at wire endpoints | Implemented |
| Connection Reports | Generate netlists | Implemented |
| YOLO Detection | ML-based component detection | In Progress |
| Line/Wire Detection | Detect wire connections | Planned |

### 2.3 Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Language | Python 3.8+ | Core development |
| GUI Framework | PyQt5 | Desktop application |
| PDF Processing | PyMuPDF (pymupdf) | Vector extraction, rendering |
| Data Models | Pydantic | Type-safe data structures |
| OCR Engine | EasyOCR | Fallback text recognition |
| ML Detection | Ultralytics YOLO | Component detection |
| Vector Library | UVP (external) | Vector analysis |

---

## 3. Current State Analysis

### 3.1 Implemented Features

```
[x] PDF Loading and Navigation
[x] Vector Extraction Pipeline
[x] Terminal Detection (unfilled circles)
[x] Terminal Label Reading
[x] Group Assignment Algorithm
[x] Pin Finding in Component Boxes
[x] Connection Report Generation
[x] Interactive GUI with PDF Viewer
[x] YOLO Annotator with AI-Assist
[x] Label Validation Script
[x] Consolidated Training Data Structure
```

### 3.2 Known Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| Duplicate MainWindow | Medium | Multiple MainWindow classes in `gui/main_window.py` |
| External Dependency | High | `external.uvp.src.models` not included in repo |
| No CI/CD | Medium | Manual testing required |
| Forked Path Handling | High | Continuity breaks at branching points (see `ornek.pdf` p.26) |
| Limited Training Data | High | Only ~3 training images in repository |

### 3.3 Current YOLO Model Classes

```yaml
# Current classes (3)
0: PLC_Module
1: Terminal
2: Contactor
```

---

## 4. Functional Requirements

### 4.1 Terminal Detection (FR-TD)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-TD-01 | Detect terminals as unfilled circles in PDF vector layer | High | Done |
| FR-TD-02 | Filter circles by radius (2.5-3.5 default) | High | Done |
| FR-TD-03 | Filter circles by coefficient of variation (<0.01) | High | Done |
| FR-TD-04 | Support configurable detection parameters | Medium | Done |
| FR-TD-05 | Handle terminals from different CAD software | High | Planned |

### 4.2 Label Reading (FR-LR)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-LR-01 | Read terminal labels from PDF text layer | High | Done |
| FR-LR-02 | OCR fallback when PDF text unavailable | High | Partial |
| FR-LR-03 | Apply regex validation for label formats | High | Done |
| FR-LR-04 | Support search radius configuration | Medium | Done |
| FR-LR-05 | Read pin labels near wire endpoints | High | Done |
| FR-LR-06 | Read device/component names via OCR | High | Planned |

### 4.3 Group Assignment (FR-GA)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-GA-01 | Search for group labels (-X1, -X2) to the left | High | Done |
| FR-GA-02 | Inherit group from left/top neighbor if not found | High | Done |
| FR-GA-03 | Generate full labels in Group:Pin format | High | Done |
| FR-GA-04 | Support Y-axis tolerance configuration | Medium | Done |

### 4.4 Connection Analysis (FR-CA)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-CA-01 | Match structural groups to terminals | High | Done |
| FR-CA-02 | Match structural groups to component boxes | High | Done |
| FR-CA-03 | Build netlist from intersections | High | Done |
| FR-CA-04 | Generate human-readable connection report | High | Done |
| FR-CA-05 | Handle forked/branching wire paths | High | **Planned** |

### 4.5 YOLO Component Detection (FR-YC)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-YC-01 | Detect PLC modules in schematics | Medium | In Progress |
| FR-YC-02 | Detect terminal blocks | Medium | In Progress |
| FR-YC-03 | Detect contactors | Medium | In Progress |
| FR-YC-04 | Detect relays | Medium | Planned |
| FR-YC-05 | Detect circuit breakers | Medium | Planned |
| FR-YC-06 | Detect fuses | Low | Planned |
| FR-YC-07 | Detect motors | Low | Planned |
| FR-YC-08 | Detect transformers | Low | Planned |

### 4.6 Line/Wire Detection (FR-LD)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-LD-01 | Detect wire connections using YOLO model | High | **Planned** |
| FR-LD-02 | Trace wire paths between components | High | **Planned** |
| FR-LD-03 | Handle branching/forked wire paths | High | **Planned** |
| FR-LD-04 | Associate wires with terminals and pins | High | **Planned** |

### 4.7 OCR Integration Enhancement (FR-OCR)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-OCR-01 | Graceful fallback when vector data unavailable | High | **Planned** |
| FR-OCR-02 | Read pin labels via OCR | High | **Planned** |
| FR-OCR-03 | Read terminal (Klemens) names via OCR | High | **Planned** |
| FR-OCR-04 | Read device names via OCR | High | **Planned** |
| FR-OCR-05 | Continue analysis without errors when OCR is needed | High | **Planned** |

---

## 5. Non-Functional Requirements

### 5.1 Performance (NFR-P)

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-P-01 | Page analysis time | < 5 seconds per page |
| NFR-P-02 | YOLO inference time | < 2 seconds per page |
| NFR-P-03 | GUI responsiveness | No UI freeze during analysis |
| NFR-P-04 | Memory usage | < 2GB for 100-page PDF |

### 5.2 Reliability (NFR-R)

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-R-01 | Terminal detection accuracy | > 95% |
| NFR-R-02 | Label reading accuracy | > 90% |
| NFR-R-03 | Connection report accuracy | > 95% |
| NFR-R-04 | YOLO detection mAP50 | > 0.8 |

### 5.3 Usability (NFR-U)

| ID | Requirement | Description |
|----|-------------|-------------|
| NFR-U-01 | Turkish UI | All interface text in Turkish |
| NFR-U-02 | Intuitive workflow | Open → Analyze → Report in 3 clicks |
| NFR-U-03 | Visual feedback | Overlay terminals on PDF view |
| NFR-U-04 | Error messages | Clear, actionable error descriptions |

### 5.4 Maintainability (NFR-M)

| ID | Requirement | Description |
|----|-------------|-------------|
| NFR-M-01 | Code documentation | English docstrings for new code |
| NFR-M-02 | Test coverage | > 70% for src/ and gui/ |
| NFR-M-03 | Modular architecture | Separate concerns (detection, reading, grouping) |
| NFR-M-04 | Type hints | All function signatures typed |

---

## 6. Technical Requirements

### 6.1 Development Environment

```bash
# Required
Python 3.8+
PyQt5 >= 5.15
PyMuPDF >= 1.21
Pydantic >= 1.10

# Optional
EasyOCR >= 1.6  # OCR fallback
Ultralytics >= 8.0  # YOLO detection
```

### 6.2 Project Structure

```
P8_Analyzer_V2/
├── start_gui.py              # Entry point
├── gui/                      # PyQt5 GUI components
│   ├── main_window.py        # Main application window
│   ├── viewer.py             # Interactive PDF viewer
│   ├── worker.py             # Background analysis thread
│   ├── circuit_logic.py      # Connection detection logic
│   └── ocr_worker.py         # OCR comparison worker
├── src/                      # Core analysis modules
│   ├── models.py             # Pydantic data models
│   ├── terminal_detector.py  # Terminal circle detection
│   ├── terminal_reader.py    # Label reading
│   ├── terminal_grouper.py   # Group assignment
│   ├── pin_finder.py         # Pin detection
│   └── text_engine.py        # Hybrid PDF/OCR engine
├── YOLO/                     # ML component detection
│   ├── scripts/              # Training and annotation scripts
│   ├── data/                 # Training data (images + labels)
│   ├── runs/                 # Training outputs
│   └── best.pt               # Trained model weights
├── tests/                    # Test suite
│   ├── unit/                 # Component tests
│   ├── integration/          # Pipeline tests
│   └── e2e/                  # End-to-end tests
├── data/                     # Sample files
│   └── ornek.pdf             # Example P8 schematic
├── external/                 # External dependencies
│   └── uvp/                  # UVP vector library (not in repo)
└── PRP/                      # Project requirements
    └── requirements/         # Source requirement documents
```

### 6.3 Configuration Parameters

#### Terminal Detection
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `min_radius` | 2.5 | 1.0-5.0 | Minimum terminal radius |
| `max_radius` | 3.5 | 2.0-10.0 | Maximum terminal radius |
| `max_cv` | 0.01 | 0.001-0.1 | Max coefficient of variation |
| `only_unfilled` | True | Boolean | Only unfilled circles |

#### Text Search
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `search_radius` | 20.0 | 5.0-50.0 | Text search radius (pt) |
| `direction` | top_right | enum | Primary search direction |
| `y_tolerance` | 15.0 | 5.0-30.0 | Y-axis grouping tolerance |

#### Pin Finder
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `pin_search_radius` | 75.0 | 25.0-150.0 | Pin label search radius |

---

## 7. YOLO Model Training Requirements

### 7.1 Training Data Strategy

| Requirement | Target | Current |
|-------------|--------|---------|
| Total training images | 500-1000 | ~3 |
| Images per class | 50-100 minimum | Variable |
| Data sources | Multiple customers/CAD software | Single source |
| Train/Val/Test split | 60/20/20 | Not split |

### 7.2 Model Strategy Decision

**Decision**: Train ONE unified model for all CAD software variants (EPLAN, WS CAD, etc.)

**Rationale**:
- Large Language Models succeed by generalizing, not specializing
- Start with unified model, evaluate performance
- Split into separate models only if performance analysis shows significant divergence
- Single model reduces deployment complexity

### 7.3 Class Definitions

#### Current Classes (3)
```yaml
0: PLC_Module
1: Terminal
2: Contactor
```

#### Proposed Classes (8+)
```yaml
0: PLC_Module
1: Terminal_Block
2: Contactor
3: Relay
4: Circuit_Breaker
5: Fuse
6: Motor
7: Transformer
8: Sensor        # Optional
9: Power_Supply  # Optional
```

### 7.4 Training Configuration

```yaml
# OBB (Oriented Bounding Box) Configuration
task: 'obb'
model: 'yolov8n-obb.pt'
imgsz: 1280  # High resolution for small components
epochs: 100
patience: 30

# Augmentation (schematic-appropriate)
mosaic: 1.0
close_mosaic: 15
degrees: 0      # NO rotation (symbols have meaning)
flipud: 0       # NO vertical flip
fliplr: 0       # NO horizontal flip
scale: 0.8-1.2  # Scale variations
hsv_h: 0.015
hsv_s: 0.4
hsv_v: 0.4
```

### 7.5 Data Augmentation Pipeline

**Allowed Augmentations**:
- Scale variations (0.8-1.2x)
- Brightness/contrast adjustment
- Gaussian blur (simulate scan quality)
- Noise injection (salt & pepper, Gaussian)
- Color jitter / grayscale conversion
- Crop and pad variations

**Forbidden Augmentations**:
- Rotation (symbols have directional meaning)
- Horizontal/Vertical flip (text becomes unreadable)

---

## 8. Integration Requirements

### 8.1 External Dependencies

| Dependency | Type | Resolution |
|------------|------|------------|
| `external.uvp.src.models` | Required | Include in repo or document installation |
| EasyOCR models | Optional | Download on first use |
| YOLO weights | Optional | Train or download pretrained |

### 8.2 File Format Support

| Format | Read | Write | Notes |
|--------|------|-------|-------|
| PDF (P8) | Yes | - | Primary input format |
| PNG/JPG | Yes | Yes | Training images, exports |
| TXT (YOLO) | Yes | Yes | Annotation labels |
| JSON | - | Yes | Netlist export (future) |
| CSV | - | Yes | Report export (future) |

---

## 9. Acceptance Criteria

### 9.1 Terminal Detection AC

- [ ] AC-TD-01: Detects >95% of terminals in `ornek.pdf`
- [ ] AC-TD-02: False positive rate <5%
- [ ] AC-TD-03: Works with EPLAN-generated PDFs
- [ ] AC-TD-04: Works with WS CAD-generated PDFs
- [ ] AC-TD-05: Works with other CAD software PDFs

### 9.2 Label Reading AC

- [ ] AC-LR-01: Reads >90% of terminal labels correctly
- [ ] AC-LR-02: OCR fallback activates when PDF text missing
- [ ] AC-LR-03: Handles German/Turkish special characters

### 9.3 Connection Analysis AC

- [ ] AC-CA-01: Generates correct netlist for simple circuits
- [ ] AC-CA-02: Handles forked paths correctly (ornek.pdf p.26)
- [ ] AC-CA-03: Report format is human-readable
- [ ] AC-CA-04: All connections verified against manual check

### 9.4 YOLO Detection AC

- [ ] AC-YC-01: mAP50 > 0.8 on validation set
- [ ] AC-YC-02: Inference time < 2 seconds per page
- [ ] AC-YC-03: Model generalizes across CAD software variants
- [ ] AC-YC-04: AI-assist in annotator suggests >80% of components

### 9.5 System AC

- [ ] AC-SYS-01: Application starts without errors
- [ ] AC-SYS-02: No crash during 100-page PDF analysis
- [ ] AC-SYS-03: All unit tests pass
- [ ] AC-SYS-04: All integration tests pass

---

## 10. Dependencies & Constraints

### 10.1 Technical Constraints

| Constraint | Description | Impact |
|------------|-------------|--------|
| Windows Primary | Tested on Windows, should work on Linux/macOS | Deployment complexity |
| GPU Optional | CUDA for faster YOLO training/inference | Training time |
| External UVP | Dependency not in repository | Onboarding difficulty |

### 10.2 Business Constraints

| Constraint | Description |
|------------|-------------|
| Contract Timeline | Project completion targeted for January 2026 |
| Training Data | Access to customer PDFs is project-specific (restricted) |
| Holiday Closure | neurawork closed Dec 24 - Jan 1 |

### 10.3 Resource Constraints

| Resource | Availability |
|----------|-------------|
| Training PDFs | Limited access, customer-provided |
| GPU Resources | Local development machines |
| Testing | Manual verification required (no CI/CD) |

---

## 11. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Model Overfitting | Medium | High | Collect diverse training data from multiple customers |
| CAD Variance | High | Medium | Train unified model, evaluate per-CAD performance |
| Insufficient Data | High | High | Data collection strategy, augmentation pipeline |
| External Dependency | Medium | High | Document UVP installation or refactor to local models |
| OCR Accuracy | Medium | Medium | Fine-tune search profiles, test edge cases |
| Forked Path Logic | High | High | Algorithm improvement for continuity detection |

---

## 12. Roadmap & Milestones

### Phase 1: Training Infrastructure (Current)
- [x] Consolidate YOLO training data in repository
- [x] Create label validation script
- [x] Add AI-assisted labeling to annotator
- [ ] Implement data augmentation pipeline
- [ ] Set up OBB training script

### Phase 2: Data Collection
- [ ] Obtain diverse PDFs from multiple customers
- [ ] Annotate 500+ training images
- [ ] Validate class distribution balance
- [ ] Document data collection strategy

### Phase 3: Model Training
- [ ] Train unified YOLO model
- [ ] Evaluate per-CAD-software performance
- [ ] Iterate based on performance metrics
- [ ] Achieve mAP50 > 0.8

### Phase 4: Feature Enhancement
- [ ] Implement line/wire detection
- [ ] Enhance OCR integration
- [ ] Fix forked path handling
- [ ] Expand component class definitions

### Phase 5: Production Readiness
- [ ] Resolve external UVP dependency
- [ ] Clean up duplicate MainWindow classes
- [ ] Set up CI/CD pipeline
- [ ] Comprehensive testing

---

## 13. Appendix

### A. Reference Documents

| Document | Location | Description |
|----------|----------|-------------|
| Meeting Transcript | `PRP/requirements/KI-Strategie-*.md` | Dec 10, 2025 strategy meeting |
| Development Message | `PRP/requirements/message.md` | Planned development tasks (Turkish) |
| Project Guidelines | `CLAUDE.md` | Development workflow and conventions |
| Architecture Memory | `.serena/memories/architecture.md` | System architecture overview |

### B. Glossary

| Term | Definition |
|------|------------|
| P8 | PDF format for electrical schematics |
| Klemens | Turkish for terminal/terminal block |
| Netlist | Connection report showing component connectivity |
| OBB | Oriented Bounding Box (rotated rectangles) |
| UVP | Vector processing library (external) |
| CV | Coefficient of Variation (roundness measure) |

### C. Sample Output

```
====== CONNECTION REPORT ======
NET-001 Line:
   Terminal -X1:1
   Terminal -X1:2
   BOX-1:13
NET-002 Line:
   Terminal -X2:PE
   Terminal -X3:PE
   Ground Rail
NET-003 Line:
   Terminal -X1:3
   PLC-1:DI0
```

### D. Contact Information

| Role | Organization | Contact |
|------|--------------|---------|
| Project Lead | neurawork GmbH | Maximilian König |
| Customer | UVP Schaltschränke | Mustafa Vural |
| Development | neurawork GmbH | Development Team |

---

**Document History**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Claude Code | Initial unified requirements document |

