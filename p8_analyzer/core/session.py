"""
P8 Analyzer Session Models - Unified Data Structure

This module defines the canonical data structure used by GUI, CLI, and tests.
AnalysisSession is the single source of truth for all analysis results.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum
from datetime import datetime
import re


class WireAnnotationType(str, Enum):
    """Types of wire annotations found along wires leading to terminals."""
    SIGNAL_NAME = "signal_name"      # P24.i2, N24.i, PE, L+, M
    DESTINATION_REF = "destination"  # /6.4, /13.34
    WIRE_SPEC = "wire_spec"          # 3x1,5mm Cu
    COLOR_CODE = "color_code"        # WH, BN, GN, YE
    COMPONENT_REF = "component_ref"  # =070, =077
    UNKNOWN = "unknown"


# DIN 47100 wire color codes
DIN_COLOR_CODES = {
    'WH': 'white', 'BN': 'brown', 'GN': 'green', 'YE': 'yellow',
    'GY': 'grey', 'PK': 'pink', 'BU': 'blue', 'RD': 'red',
    'BK': 'black', 'VT': 'violet', 'OG': 'orange', 'SE': 'shield'
}


# Regex patterns for annotation classification
# Keys must match WireAnnotationType enum values
ANNOTATION_PATTERNS = {
    'signal_name': [
        r'^[PN]\d+(\.[a-zA-Z0-9]+)?$',   # P24, N24, P24.i2
        r'^[LMN]$',                        # L, M, N
        r'^L[123]$',                       # L1, L2, L3
        r'^PE$',                           # PE (protective earth)
        r'^L\+$',                          # L+ (positive)
        r'^D\d+/[PN]\d+:[A-Z]\d*$',       # D3/P24:L1
    ],
    'destination': [                       # NOTE: key matches enum value
        r'^/\d+\.\d+$',                   # /6.4, /13.34
        r'^/\d+$',                         # /52
    ],
    'wire_spec': [
        r'^\d+[x,]\d+.*mm',               # 3x1,5mm, 4x0,5mm
        r'.*Cu$',                          # ...Cu
        r'^\d+x\d+x\d+\s+\w+',            # 3x4x0 VAC,60Hz,PE
    ],
    'color_code': [
        r'^(WH|BN|GN|YE|GY|PK|BU|RD|BK|VT|OG|SE)$',  # DIN 47100 codes
    ],
    'component_ref': [
        r'^=\d+$',                         # =070, =077
    ],
}


def classify_annotation(text: str) -> WireAnnotationType:
    """
    Classify annotation type based on text pattern.

    Args:
        text: The annotation text to classify

    Returns:
        WireAnnotationType enum value
    """
    text = text.strip()

    for ann_type, patterns in ANNOTATION_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return WireAnnotationType(ann_type)

    return WireAnnotationType.UNKNOWN


class WireAnnotation(BaseModel):
    """Annotation found along wire leading to terminal."""
    text: str
    position_x: float
    position_y: float
    annotation_type: WireAnnotationType = WireAnnotationType.UNKNOWN
    distance_to_terminal: float = 0.0
    direction: str = ""  # 'left', 'right', 'top', 'bottom'
    source: str = "pdf"  # 'pdf' or 'ocr'
    confidence: float = 1.0

    def __init__(self, **data):
        super().__init__(**data)
        # Auto-classify if not set
        if self.annotation_type == WireAnnotationType.UNKNOWN:
            object.__setattr__(self, 'annotation_type', classify_annotation(self.text))


class Terminal(BaseModel):
    """A detected terminal (Klemens) with all metadata."""
    id: str  # Unique ID: "{page}_{group_label}_{label}"
    center_x: float
    center_y: float
    radius: float
    label: Optional[str] = None
    label_source: Optional[str] = None  # 'pdf', 'ocr', None
    group_label: Optional[str] = None   # -X1, -X2, etc.
    group_source: Optional[str] = None  # 'pdf_direct', 'inherited', None
    full_label: Optional[str] = None    # -X1:5, -X2:PE
    structural_group_id: Optional[int] = None
    wire_annotations: List[WireAnnotation] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict, page_number: int = 0) -> "Terminal":
        """Create Terminal from legacy terminal dict format."""
        center = data.get('center', (0, 0))
        cx, cy = center if isinstance(center, (list, tuple)) else (0, 0)

        full_label = data.get('full_label', '')
        group_label = data.get('group_label', '')
        label = data.get('label', '')

        # Generate unique ID (no UNK placeholder)
        id_base = full_label or group_label or label or ""
        term_id = f"{page_number}_{id_base}_{label}".strip("_")

        return cls(
            id=term_id,
            center_x=cx,
            center_y=cy,
            radius=data.get('radius', 3.0),
            label=label,
            label_source=data.get('label_source'),
            group_label=group_label,
            group_source=data.get('group_source'),
            full_label=full_label,
            structural_group_id=data.get('group_id'),
            wire_annotations=[]
        )


class Pin(BaseModel):
    """A pin on a component."""
    label: str
    position_x: float
    position_y: float


class Component(BaseModel):
    """A detected component (device box)."""
    id: str
    label: Optional[str] = None
    component_type: Optional[str] = None  # 'contactor', 'motor', 'plc', etc.
    bbox_min_x: float
    bbox_min_y: float
    bbox_max_x: float
    bbox_max_y: float
    pins: List[Pin] = Field(default_factory=list)

    @property
    def width(self) -> float:
        return self.bbox_max_x - self.bbox_min_x

    @property
    def height(self) -> float:
        return self.bbox_max_y - self.bbox_min_y

    @property
    def center(self) -> tuple:
        return (
            (self.bbox_min_x + self.bbox_max_x) / 2,
            (self.bbox_min_y + self.bbox_max_y) / 2
        )


class Connection(BaseModel):
    """A connection between two elements."""
    source_id: str
    source_pin: Optional[str] = None
    target_id: str
    target_pin: Optional[str] = None
    net_id: str
    wire_annotations: List[str] = Field(default_factory=list)


class PageAnalysis(BaseModel):
    """Complete analysis result for one page."""
    page_number: int
    page_width: float
    page_height: float
    terminals: List[Terminal] = Field(default_factory=list)
    components: List[Component] = Field(default_factory=list)
    connections: List[Connection] = Field(default_factory=list)
    structural_group_count: int = 0
    analysis_timestamp: datetime = Field(default_factory=datetime.now)

    def get_terminal_by_label(self, full_label: str) -> Optional[Terminal]:
        """Find terminal by full label (e.g., '-X1:5')."""
        for t in self.terminals:
            if t.full_label == full_label:
                return t
        return None

    def get_terminals_by_group(self, group_label: str) -> List[Terminal]:
        """Get all terminals in a group (e.g., '-X1')."""
        return [t for t in self.terminals if t.group_label == group_label]


class SessionMetadata(BaseModel):
    """Metadata about the analysis session."""
    pdf_path: str
    pdf_name: str
    total_pages: int
    analyzed_pages: List[int] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    analyzer_version: str = "2.0.0"


class AnalysisSummary(BaseModel):
    """Summary statistics across all pages."""
    total_terminals: int = 0
    total_components: int = 0
    total_connections: int = 0
    total_annotations: int = 0
    pages_with_errors: List[int] = Field(default_factory=list)


class AnalysisSession(BaseModel):
    """
    Complete analysis session - THE canonical data structure.
    Used by GUI, CLI, and tests.
    """
    metadata: SessionMetadata
    pages: Dict[int, PageAnalysis] = Field(default_factory=dict)
    summary: AnalysisSummary = Field(default_factory=AnalysisSummary)

    def save(self, path: str) -> None:
        """
        Save session to JSON file.

        Args:
            path: File path to save to (recommended: .p8session or .json)
        """
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: str) -> "AnalysisSession":
        """
        Load session from JSON file.

        Args:
            path: File path to load from

        Returns:
            AnalysisSession instance
        """
        with open(path, 'r', encoding='utf-8') as f:
            return cls.model_validate_json(f.read())

    def compute_summary(self) -> None:
        """Recompute summary from page data."""
        self.summary.total_terminals = sum(
            len(p.terminals) for p in self.pages.values()
        )
        self.summary.total_components = sum(
            len(p.components) for p in self.pages.values()
        )
        self.summary.total_connections = sum(
            len(p.connections) for p in self.pages.values()
        )
        self.summary.total_annotations = sum(
            sum(len(t.wire_annotations) for t in p.terminals)
            for p in self.pages.values()
        )

    def add_page(self, page: PageAnalysis) -> None:
        """Add a page analysis result."""
        self.pages[page.page_number] = page
        if page.page_number not in self.metadata.analyzed_pages:
            self.metadata.analyzed_pages.append(page.page_number)
            self.metadata.analyzed_pages.sort()
        self.compute_summary()

    def get_page(self, page_number: int) -> Optional[PageAnalysis]:
        """Get analysis for a specific page."""
        return self.pages.get(page_number)

    def get_all_terminals(self) -> List[Terminal]:
        """Get all terminals across all pages."""
        return [t for p in self.pages.values() for t in p.terminals]

    def get_all_connections(self) -> List[Connection]:
        """Get all connections across all pages."""
        return [c for p in self.pages.values() for c in p.connections]


def create_session(pdf_path: str, total_pages: int) -> AnalysisSession:
    """
    Create a new analysis session.

    Args:
        pdf_path: Path to the PDF file
        total_pages: Total number of pages in the PDF

    Returns:
        New AnalysisSession instance
    """
    import os

    metadata = SessionMetadata(
        pdf_path=pdf_path,
        pdf_name=os.path.basename(pdf_path),
        total_pages=total_pages,
        analyzed_pages=[]
    )

    return AnalysisSession(
        metadata=metadata,
        pages={},
        summary=AnalysisSummary()
    )
