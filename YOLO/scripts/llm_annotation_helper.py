"""
LLM-Based Annotation Helper

Uses vision LLM models (Claude, GPT-4V) to generate initial bounding box
suggestions for electrical schematic components.

The LLM analyzes the image and returns:
1. Component locations (approximate bounding boxes)
2. Component classifications
3. Confidence levels

These suggestions are then loaded into the annotator for human review.

Usage:
    python llm_annotation_helper.py --image schematic.jpg --output suggestions.json
    python llm_annotation_helper.py --image-dir ./schematics --output-dir ./suggestions
"""

import os
import sys
import json
import base64
import argparse
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Look for .env in script dir, YOLO dir, or project root
    script_dir = Path(__file__).parent
    for env_path in [
        script_dir / '.env',
        script_dir.parent / '.env',
        script_dir.parent.parent / '.env'
    ]:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[INFO] Loaded environment from: {env_path}")
            break
except ImportError:
    pass  # python-dotenv not installed, rely on system env vars

# API clients - install as needed
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


# Component classes for POC - focused set
COMPONENT_CLASSES = {
    0: "PLC_Module",
    1: "Terminal",
    2: "Contactor",  # German: Schütz
}

CLASS_NAME_TO_ID = {v: k for k, v in COMPONENT_CLASSES.items()}


@dataclass
class ComponentSuggestion:
    """A suggested component annotation from LLM."""
    class_id: int
    class_name: str
    x_center: float  # Normalized [0, 1]
    y_center: float
    width: float
    height: float
    confidence: float
    reasoning: str


@dataclass
class AnnotationSuggestions:
    """All suggestions for an image."""
    image_path: str
    image_width: int
    image_height: int
    timestamp: str
    model_used: str
    suggestions: List[Dict]
    raw_response: str


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

## P8 Schematic Conventions:
- Components typically have a label starting with minus sign: -XXX (varies greatly)
- Grid layout often has column numbers at top and row letters at bottom
- Components are drawn with standardized electrical symbols

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
- Ignore wires, text labels (unless part of component), and grid lines

Respond with ONLY a JSON array:
[
  {"class_name": "Terminal", "x_center": 15.2, "y_center": 65.0, "width": 1.5, "height": 2.0, "confidence": 0.9, "label": "-X1:1", "reasoning": "Circle on terminal strip"},
  {"class_name": "PLC_Module", "x_center": 45.0, "y_center": 30.0, "width": 12.0, "height": 15.0, "confidence": 0.95, "label": "-1G35", "reasoning": "Power supply module with connections"}
]"""


class LLMAnnotationHelper:
    """Generates annotation suggestions using vision LLMs."""

    def __init__(self, provider: str = "anthropic", model: str = None):
        self.provider = provider
        self.model = model
        self.client = None

        if provider == "anthropic":
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = model or "claude-sonnet-4-20250514"

        elif provider == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError("openai package not installed. Run: pip install openai")
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.client = openai.OpenAI(api_key=api_key)
            self.model = model or "gpt-4o"

        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'anthropic' or 'openai'")

    def _encode_image(self, image_path: str) -> Tuple[str, str]:
        """Encode image to base64 and determine media type."""
        path = Path(image_path)
        suffix = path.suffix.lower()

        media_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }

        media_type = media_type_map.get(suffix, 'image/jpeg')

        with open(image_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')

        return image_data, media_type

    def _parse_llm_response(self, response_text: str) -> List[Dict]:
        """Parse LLM response to extract component suggestions."""
        # Try to find JSON array in response
        # Handle cases where LLM wraps response in markdown code blocks
        json_match = re.search(r'\[[\s\S]*\]', response_text)

        if not json_match:
            print(f"[WARNING] Could not find JSON array in response")
            return []

        try:
            components = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            print(f"[WARNING] JSON parse error: {e}")
            return []

        # Validate and normalize components
        valid_components = []
        for comp in components:
            if not isinstance(comp, dict):
                continue

            class_name = comp.get('class_name', '')
            if class_name not in CLASS_NAME_TO_ID:
                print(f"[WARNING] Unknown class: {class_name}")
                continue

            # Normalize percentages to [0, 1]
            try:
                suggestion = {
                    'class_id': CLASS_NAME_TO_ID[class_name],
                    'class_name': class_name,
                    'x_center': float(comp.get('x_center', 0)) / 100.0,
                    'y_center': float(comp.get('y_center', 0)) / 100.0,
                    'width': float(comp.get('width', 0)) / 100.0,
                    'height': float(comp.get('height', 0)) / 100.0,
                    'confidence': float(comp.get('confidence', 0.5)),
                    'label': comp.get('label', ''),
                    'reasoning': comp.get('reasoning', '')
                }

                # Validate bounds
                if (0 <= suggestion['x_center'] <= 1 and
                    0 <= suggestion['y_center'] <= 1 and
                    0 < suggestion['width'] <= 1 and
                    0 < suggestion['height'] <= 1):
                    valid_components.append(suggestion)
                else:
                    print(f"[WARNING] Component out of bounds: {class_name}")

            except (ValueError, TypeError) as e:
                print(f"[WARNING] Invalid component data: {e}")
                continue

        return valid_components

    def analyze_image_anthropic(self, image_path: str) -> Tuple[List[Dict], str]:
        """Analyze image using Anthropic Claude."""
        image_data, media_type = self._encode_image(image_path)

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": "Analyze this electrical schematic and identify all visible components. Return ONLY a JSON array."
                        }
                    ]
                }
            ]
        )

        response_text = message.content[0].text
        components = self._parse_llm_response(response_text)
        return components, response_text

    def analyze_image_openai(self, image_path: str) -> Tuple[List[Dict], str]:
        """Analyze image using OpenAI GPT-4V."""
        image_data, media_type = self._encode_image(image_path)

        response = self.client.chat.completions.create(
            model=self.model,
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

        response_text = response.choices[0].message.content
        components = self._parse_llm_response(response_text)
        return components, response_text

    def analyze_image(self, image_path: str) -> AnnotationSuggestions:
        """Analyze an image and return annotation suggestions."""
        print(f"[INFO] Analyzing: {image_path}")

        # Get image dimensions
        with Image.open(image_path) as img:
            width, height = img.size

        # Call appropriate provider
        if self.provider == "anthropic":
            components, raw_response = self.analyze_image_anthropic(image_path)
        else:
            components, raw_response = self.analyze_image_openai(image_path)

        print(f"[INFO] Found {len(components)} components")

        return AnnotationSuggestions(
            image_path=str(image_path),
            image_width=width,
            image_height=height,
            timestamp=datetime.now().isoformat(),
            model_used=self.model,
            suggestions=components,
            raw_response=raw_response
        )

    def suggestions_to_yolo(self, suggestions: AnnotationSuggestions) -> List[str]:
        """Convert suggestions to YOLO format labels."""
        lines = []
        for s in suggestions.suggestions:
            # YOLO format: class_id x_center y_center width height
            line = f"{s['class_id']} {s['x_center']:.6f} {s['y_center']:.6f} {s['width']:.6f} {s['height']:.6f}"
            lines.append(line)
        return lines

    def suggestions_to_obb(self, suggestions: AnnotationSuggestions) -> List[str]:
        """Convert suggestions to OBB format labels (axis-aligned, no rotation)."""
        lines = []
        for s in suggestions.suggestions:
            # Calculate corner points from center/width/height
            cx, cy = s['x_center'], s['y_center']
            w, h = s['width'] / 2, s['height'] / 2

            # Four corners (clockwise from top-left)
            x1, y1 = cx - w, cy - h  # Top-left
            x2, y2 = cx + w, cy - h  # Top-right
            x3, y3 = cx + w, cy + h  # Bottom-right
            x4, y4 = cx - w, cy + h  # Bottom-left

            # OBB format: class_id x1 y1 x2 y2 x3 y3 x4 y4
            line = f"{s['class_id']} {x1:.6f} {y1:.6f} {x2:.6f} {y2:.6f} {x3:.6f} {y3:.6f} {x4:.6f} {y4:.6f}"
            lines.append(line)
        return lines

    def visualize_suggestions(self, suggestions: AnnotationSuggestions, output_path: str = None) -> str:
        """Draw bounding boxes on the image and save visualization."""
        # Colors for each class (RGB)
        CLASS_COLORS = {
            "PLC_Module": (0, 128, 255),    # Blue
            "Terminal": (255, 165, 0),       # Orange
            "Contactor": (0, 200, 0),        # Green
        }

        # Load image
        img = Image.open(suggestions.image_path)
        draw = ImageDraw.Draw(img)

        # Try to load a font, fall back to default
        try:
            font = ImageFont.truetype("arial.ttf", 14)
            font_small = ImageFont.truetype("arial.ttf", 10)
        except:
            font = ImageFont.load_default()
            font_small = font

        width, height = img.size

        for s in suggestions.suggestions:
            class_name = s['class_name']
            color = CLASS_COLORS.get(class_name, (255, 0, 0))

            # Convert normalized coords to pixels
            cx = s['x_center'] * width
            cy = s['y_center'] * height
            w = s['width'] * width
            h = s['height'] * height

            x1 = int(cx - w/2)
            y1 = int(cy - h/2)
            x2 = int(cx + w/2)
            y2 = int(cy + h/2)

            # Draw rectangle
            draw.rectangle([x1, y1, x2, y2], outline=color, width=2)

            # Draw label background
            label = s.get('label', '') or class_name
            label_text = f"{label} ({s['confidence']:.0%})"

            # Get text bbox for background
            text_bbox = draw.textbbox((x1, y1 - 16), label_text, font=font_small)
            draw.rectangle(text_bbox, fill=color)
            draw.text((x1, y1 - 16), label_text, fill=(255, 255, 255), font=font_small)

        # Add legend
        legend_y = 10
        for class_name, color in CLASS_COLORS.items():
            count = sum(1 for s in suggestions.suggestions if s['class_name'] == class_name)
            if count > 0:
                draw.rectangle([10, legend_y, 25, legend_y + 15], fill=color, outline=color)
                draw.text((30, legend_y), f"{class_name}: {count}", fill=color, font=font)
                legend_y += 20

        # Save visualization
        if output_path is None:
            output_path = str(Path(suggestions.image_path).with_suffix('')) + "_annotated.png"

        img.save(output_path)
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate annotation suggestions using vision LLMs"
    )
    parser.add_argument('--image', type=str, help="Single image to analyze")
    parser.add_argument('--image-dir', type=str, help="Directory of images to analyze")
    parser.add_argument('--output', type=str, help="Output JSON file for single image")
    parser.add_argument('--output-dir', type=str, default='./llm_suggestions',
                        help="Output directory for batch processing")
    parser.add_argument('--provider', type=str, default='anthropic',
                        choices=['anthropic', 'openai'],
                        help="LLM provider (default: anthropic)")
    parser.add_argument('--model', type=str, default=None,
                        help="Specific model to use")
    parser.add_argument('--format', type=str, default='obb',
                        choices=['yolo', 'obb', 'json'],
                        help="Output label format (default: obb)")
    parser.add_argument('--save-labels', action='store_true',
                        help="Save YOLO/OBB label files alongside JSON")
    parser.add_argument('--visualize', action='store_true',
                        help="Save annotated image with bounding boxes")

    args = parser.parse_args()

    if not args.image and not args.image_dir:
        parser.error("Either --image or --image-dir is required")

    # Initialize helper
    try:
        helper = LLMAnnotationHelper(provider=args.provider, model=args.model)
    except (ImportError, ValueError) as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # Process single image
    if args.image:
        suggestions = helper.analyze_image(args.image)

        # Save JSON
        output_path = args.output or f"{Path(args.image).stem}_suggestions.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(suggestions), f, indent=2, ensure_ascii=False)
        print(f"[INFO] Saved suggestions to: {output_path}")

        # Save labels if requested
        if args.save_labels:
            label_path = Path(args.image).with_suffix('.txt')
            if args.format == 'obb':
                labels = helper.suggestions_to_obb(suggestions)
            else:
                labels = helper.suggestions_to_yolo(suggestions)

            with open(label_path, 'w') as f:
                f.write('\n'.join(labels))
            print(f"[INFO] Saved labels to: {label_path}")

        # Save visualization if requested
        if args.visualize:
            viz_path = helper.visualize_suggestions(suggestions)
            print(f"[INFO] Saved visualization to: {viz_path}")

        # Print summary
        print(f"\n[SUMMARY] Found {len(suggestions.suggestions)} components:")
        for s in suggestions.suggestions:
            label = s.get('label', '')
            label_str = f" [{label}]" if label else ""
            print(f"  - {s['class_name']}{label_str}: ({s['x_center']:.2f}, {s['y_center']:.2f}) "
                  f"conf={s['confidence']:.2f}")

    # Process directory
    if args.image_dir:
        image_dir = Path(args.image_dir)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find all images
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        images = [f for f in image_dir.iterdir()
                  if f.suffix.lower() in image_extensions]

        print(f"[INFO] Found {len(images)} images to process")

        all_suggestions = []
        for i, img_path in enumerate(images, 1):
            print(f"\n[{i}/{len(images)}] Processing {img_path.name}")

            try:
                suggestions = helper.analyze_image(str(img_path))
                all_suggestions.append(suggestions)

                # Save individual JSON
                json_path = output_dir / f"{img_path.stem}_suggestions.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(asdict(suggestions), f, indent=2, ensure_ascii=False)

                # Save labels if requested
                if args.save_labels:
                    label_path = output_dir / f"{img_path.stem}.txt"
                    if args.format == 'obb':
                        labels = helper.suggestions_to_obb(suggestions)
                    else:
                        labels = helper.suggestions_to_yolo(suggestions)

                    with open(label_path, 'w') as f:
                        f.write('\n'.join(labels))

            except Exception as e:
                print(f"[ERROR] Failed to process {img_path.name}: {e}")
                continue

        # Save batch summary
        summary = {
            'total_images': len(images),
            'processed': len(all_suggestions),
            'total_components': sum(len(s.suggestions) for s in all_suggestions),
            'model_used': helper.model,
            'timestamp': datetime.now().isoformat()
        }

        summary_path = output_dir / "batch_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)

        print(f"\n[SUMMARY]")
        print(f"  Images processed: {summary['processed']}/{summary['total_images']}")
        print(f"  Total components found: {summary['total_components']}")
        print(f"  Output directory: {output_dir}")


if __name__ == "__main__":
    main()
