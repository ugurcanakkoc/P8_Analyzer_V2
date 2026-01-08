"""
Background worker for LLM-based component detection.

Uses vision LLM (OpenAI GPT-4o) to identify electrical components
in schematic pages and return bounding box suggestions.
"""

import os
import sys
import json
import base64
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

from PyQt5.QtCore import QThread, pyqtSignal
import pymupdf

# Try to load environment from .env
try:
    from dotenv import load_dotenv
    for env_path in [
        Path(__file__).parent.parent.parent / '.env',
        Path(__file__).parent.parent.parent / 'YOLO' / '.env',
    ]:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass


# Component classes for POC
COMPONENT_CLASSES = {
    0: "PLC_Module",
    1: "Terminal",
    2: "Contactor",
}

# Colors for visualization (RGB)
CLASS_COLORS = {
    "PLC_Module": (0, 128, 255),    # Blue
    "Terminal": (255, 165, 0),       # Orange
    "Contactor": (0, 200, 0),        # Green
}

SYSTEM_PROMPT = """You are an expert P8 electrical schematic analyzer. Analyze this industrial electrical schematic and identify ALL instances of these component types:

## Component Classes (ONLY use these 3):

1. **PLC_Module** - Control modules, I/O modules, power supplies, logic controllers
   - Look for: Rectangular boxes with multiple terminals/connections
   - Usually have input/output labels (IN, OUT, RST, NC, etc.)
   - Typically near a component label starting with minus sign (e.g., -XXX)

2. **Terminal** - Individual wire connection points (Klemens)
   - Look for: Small unfilled circles where wires connect
   - Each circle is ONE terminal - count them individually
   - Often found in groups/strips with nearby position numbers (1, 2, 3, PE, L1, U, V, W, etc.)
   - Typically near a component label starting with minus sign (e.g., -XXX)

3. **Contactor** - Electromagnetic switches (German: Schütz)
   - Look for: Rectangular symbol with coil (A1/A2) and main contacts
   - Has switching contacts (normally open/closed symbols)
   - Typically near a component label starting with minus sign (e.g., -XXX)

## Output Format:
For EACH component instance, provide:
- class_name: Exactly "PLC_Module", "Terminal", or "Contactor"
- x_center: Center X position (0-100% from left)
- y_center: Center Y position (0-100% from top)
- width: Bounding box width (0-100% of image)
- height: Bounding box height (0-100% of image)
- confidence: 0.0-1.0
- label: The component label if visible (usually starts with -)
- reasoning: Brief explanation

## Important:
- Find ALL instances, not just one example of each type
- Terminals are INDIVIDUAL circles - a strip of 5 terminals = 5 detections
- Be thorough - scan the entire schematic systematically

Respond with ONLY a JSON array."""


@dataclass
class DetectedComponent:
    """A detected component from LLM analysis."""
    class_name: str
    x_center: float  # Normalized [0, 1]
    y_center: float
    width: float
    height: float
    confidence: float
    label: str
    reasoning: str

    @property
    def bbox_pixels(self) -> Tuple[int, int, int, int]:
        """Get pixel bounding box (x1, y1, x2, y2) - requires page dimensions."""
        # This will be set by the caller with actual dimensions
        return (0, 0, 0, 0)

    def to_pixel_bbox(self, page_width: int, page_height: int) -> Tuple[int, int, int, int]:
        """Convert normalized coords to pixel bbox."""
        cx = self.x_center * page_width
        cy = self.y_center * page_height
        w = self.width * page_width
        h = self.height * page_height

        x1 = int(cx - w/2)
        y1 = int(cy - h/2)
        x2 = int(cx + w/2)
        y2 = int(cy + h/2)

        return (x1, y1, x2, y2)


class LLMAnalysisWorker(QThread):
    """Background thread for LLM-based component detection."""

    # Signals
    progress = pyqtSignal(str)  # status message
    finished = pyqtSignal(list)  # list of DetectedComponent
    error = pyqtSignal(str)

    def __init__(self, pdf_path: str, page_num: int, provider: str = "openai"):
        super().__init__()
        self.pdf_path = pdf_path
        self.page_num = page_num
        self.provider = provider
        self._cancelled = False

    def cancel(self):
        """Request cancellation."""
        self._cancelled = True

    def _encode_image(self, image_path: str) -> Tuple[str, str]:
        """Encode image to base64."""
        suffix = Path(image_path).suffix.lower()
        media_type = 'image/png' if suffix == '.png' else 'image/jpeg'

        with open(image_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')

        return image_data, media_type

    def _parse_response(self, response_text: str) -> List[DetectedComponent]:
        """Parse LLM response to extract components."""
        import re

        # Find JSON array in response
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if not json_match:
            return []

        try:
            components = json.loads(json_match.group())
        except json.JSONDecodeError:
            return []

        valid_components = []
        for comp in components:
            if not isinstance(comp, dict):
                continue

            class_name = comp.get('class_name', '')
            if class_name not in COMPONENT_CLASSES.values():
                continue

            try:
                detected = DetectedComponent(
                    class_name=class_name,
                    x_center=float(comp.get('x_center', 0)) / 100.0,
                    y_center=float(comp.get('y_center', 0)) / 100.0,
                    width=float(comp.get('width', 0)) / 100.0,
                    height=float(comp.get('height', 0)) / 100.0,
                    confidence=float(comp.get('confidence', 0.5)),
                    label=comp.get('label', ''),
                    reasoning=comp.get('reasoning', '')
                )

                # Validate bounds
                if (0 <= detected.x_center <= 1 and
                    0 <= detected.y_center <= 1 and
                    0 < detected.width <= 1 and
                    0 < detected.height <= 1):
                    valid_components.append(detected)

            except (ValueError, TypeError):
                continue

        return valid_components

    def run(self):
        """Run LLM analysis in background."""
        doc = None

        try:
            self.progress.emit("Loading page...")

            # Check API key
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self.error.emit("OPENAI_API_KEY not set. Add it to YOLO/.env file.")
                self.finished.emit([])
                return

            # Import openai
            try:
                import openai
            except ImportError:
                self.error.emit("openai package not installed. Run: pip install openai")
                self.finished.emit([])
                return

            # Open PDF and render page
            doc = pymupdf.open(self.pdf_path)
            page = doc.load_page(self.page_num - 1)

            # Render to temp image
            self.progress.emit("Rendering page image...")
            mat = pymupdf.Matrix(150/72, 150/72)  # 150 DPI
            pix = page.get_pixmap(matrix=mat)

            temp_dir = tempfile.gettempdir()
            tmp_path = os.path.join(temp_dir, "llm_analysis_temp.png")
            pix.save(tmp_path)

            if self._cancelled:
                self.finished.emit([])
                return

            # Encode image
            self.progress.emit("Sending to LLM...")
            image_data, media_type = self._encode_image(tmp_path)

            # Call OpenAI
            client = openai.OpenAI(api_key=api_key)

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Analyze this electrical schematic and identify all visible components. Return ONLY a JSON array."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096
            )

            if self._cancelled:
                self.finished.emit([])
                return

            self.progress.emit("Parsing results...")
            response_text = response.choices[0].message.content
            components = self._parse_response(response_text)

            # Clean up
            try:
                os.unlink(tmp_path)
            except:
                pass

            self.progress.emit(f"Found {len(components)} components")
            self.finished.emit(components)

        except Exception as e:
            self.error.emit(f"LLM analysis failed: {e}")
            self.finished.emit([])

        finally:
            if doc:
                doc.close()
