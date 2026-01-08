# Estimate Timeline

Standalone command to recalculate timeline, perform PERT analysis, and adjust buffers for an existing PRP.

## Usage

```
/estimate-timeline PRPs/customer-portal-auth-system.md
```

## What This Command Does

1. Reads PRP file with task estimates
2. Launches timeline-estimator subagent
3. Returns comprehensive timeline analysis

## Output

- PERT analysis (expected duration, σ, confidence intervals)
- Task timeline with dates
- Buffer plan (project buffer, feeding buffers)
- Milestone schedule
- Gantt chart data
- Probability analysis (if deadline provided)

## Use Case

Run this command to:
- Recalculate timeline after estimate changes
- Adjust buffer sizes
- Perform "what-if" analysis
- Get probability of meeting deadline

## Optional: Specify Deadline

```
/estimate-timeline PRPs/project.md --deadline 2025-06-30
```

Returns Z-score and probability of meeting specified deadline.

---

**Version:** 1.0.0
