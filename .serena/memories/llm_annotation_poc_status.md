# LLM Annotation POC Status

**Date:** 2026-01-07
**Status:** ON HOLD

## Summary

Attempted to use GPT-4o vision model for automated bounding box generation on P8 electrical schematics. Results show LLM can identify components but struggles with precise localization.

## Implementation

**Script:** `YOLO/scripts/llm_annotation_helper.py`

```bash
# Usage
python llm_annotation_helper.py --image schematic.png --provider openai --save-labels --visualize
```

**Features:**
- 3-class POC: PLC_Module, Terminal, Contactor
- JSON output with component labels and reasoning
- YOLO/OBB format label files
- Annotated image visualization with color-coded bboxes

## Test Results

**Image:** ornek_page0011.png (2337x1688)

| Metric | Value |
|--------|-------|
| Components found | 12 |
| Terminals | 10 |
| PLC_Modules | 2 |
| Labels correct | Yes |
| Bbox accuracy | Poor |

## Key Findings

1. **Good:** LLM correctly identifies component types and reads labels
2. **Good:** Understands P8 schematic conventions (-XXX naming)
3. **Bad:** Bounding box coordinates are approximate (±10-20% error)
4. **Bad:** Not suitable for generating training data directly

## Files Created

- `YOLO/scripts/llm_annotation_helper.py` - Main CLI script
- `p8_analyzer/gui/llm_worker.py` - GUI worker (not integrated)
- `tests/unit/test_llm_annotation.py` - 8 unit tests

## Recommendations

1. **Alternative 1:** Use LLM for label extraction only, combine with vector analysis for bbox
2. **Alternative 2:** Manual annotation with existing smart_annotator.py
3. **Alternative 3:** Train smaller YOLO model on manually annotated subset first

## Dependencies

- openai package
- OPENAI_API_KEY in YOLO/.env
