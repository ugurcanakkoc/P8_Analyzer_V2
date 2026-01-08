# Analyze Dependencies

Standalone command to analyze task dependencies, identify critical path, and detect bottlenecks for an existing PRP.

## Usage

```
/analyze-dependencies PRPs/customer-portal-auth-system.md
```

## What This Command Does

1. Reads PRP file
2. Launches dependency-analyzer subagent
3. Returns dependency analysis report

## Output

- Dependency matrix
- Critical path identification
- Float/slack analysis
- Bottleneck detection
- Circular dependency check
- Optimization recommendations

## Use Case

Run this command to:
- Re-analyze dependencies after changes
- Get detailed dependency report
- Identify optimization opportunities
- Validate no circular dependencies

---

**Version:** 1.0.0
