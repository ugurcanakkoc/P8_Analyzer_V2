# Generate Automation Project PRP

Generate a comprehensive Project Requirements Planning (PRP) document from an INITIAL.md file by orchestrating specialized subagents for project management, technical research, dependency analysis, and timeline estimation.

## Usage

```
/generate-automation-prp PRPs/INITIAL.md
```

or

```
/generate-automation-prp PRPs/MY_PROJECT_INITIAL.md
```

## What This Command Does

1. **Validates INITIAL.md** - Ensures required sections exist
2. **Launches 4 PRP-Specialized Subagents in Parallel:**
   - **project-structure-architect** - Creates WBS, task breakdown, resource plan, risks
   - **technical-researcher** - Researches technologies, integration patterns, gotchas
   - **dependency-analyzer** - Creates dependency graph, identifies critical path
   - **timeline-estimator** - Calculates timeline, buffers, milestones
3. **Consolidates Results** - Merges all subagent outputs into comprehensive PRP
4. **Generates PRP File** - Writes complete PRP to `PRPs/{project-name}.md` **in 7 sections** (mandatory for large PRPs)

## ⚠️ CRITICAL IMPLEMENTATION RULES

**1. CORRECT SUBAGENT PATHS:**
- Subagent definitions are in `.claude/agents/` NOT `.claude/subagents/`
- Subagent files:
  - `.claude/agents/project-structure-architect.md`
  - `.claude/agents/technical-researcher.md`
  - `.claude/agents/dependency-analyzer.md`
  - `.claude/agents/timeline-estimator.md`

**2. CORRECT SUBAGENT TYPES:**
- Use exact names: "project-structure-architect", "technical-researcher", "dependency-analyzer", "timeline-estimator"
- NOT "general-purpose", NOT "project-manager"

**3. TOKEN-LIMIT PROTECTION (MANDATORY):**
- PRPs are typically 10,000-20,000 lines
- NEVER write entire PRP in one operation
- ALWAYS split into 7 sections (see Step 7)
- Each section MUST be < 10,000 characters
- Use Write for Section 1, Edit for Sections 2-7

**4. EXECUTION ORDER:**
- Parallel: project-structure-architect + technical-researcher (round 1)
- Sequential: dependency-analyzer (round 2, needs task list)
- Sequential: timeline-estimator (round 3, needs critical path)

**Note:** This command launches the 4 PRP-generation subagents. Other subagents are available for different tasks:
- **Explore** - For codebase exploration and pattern finding (use proactively for "where is..." questions)
- **For Notion operations:** Use Notion MCP tools directly (mcp__Notion__*) - no subagent needed

## Expected Input Format

INITIAL.md must contain these sections:

```markdown
# INITIAL: {Project Component Name}

## PROJEKT-KONTEXT
- Overall project name
- This component's role
- Integration points

## FUNKTIONALE ANFORDERUNGEN
- Features to automate
- User stories
- Acceptance criteria

## TECHNOLOGIE-STACK
- Languages, frameworks, libraries
- Infrastructure
- External services

## ABHÄNGIGKEITEN
- Prerequisites
- Blocking relationships

## RESSOURCEN
- Team composition
- Timeline estimate
- Budget

## RISIKEN
- Technical risks
- Operational risks
- Mitigation strategies
```

See `PRPs/INITIAL.md` for complete example.

## Execution Steps

### Step 1: Validate Input File

```bash
# Check file exists
test -f {provided_path}

# Check file has required sections
grep -q "## PROJEKT-KONTEXT" {file}
grep -q "## FUNKTIONALE ANFORDERUNGEN" {file}
grep -q "## TECHNOLOGIE-STACK" {file}
```

If validation fails:
- Alert user which sections are missing
- Provide example format
- Exit gracefully

### Step 2: Read INITIAL.md Completely

```
Read: {provided_path}
```

Extract key information:
- Project name
- Technology stack
- Dependencies
- Resources
- Risks
- Timeline constraints

### Step 3: Launch Subagents in Parallel

**CRITICAL: Use single message with multiple Task tool calls to launch in parallel!**

**IMPORTANT PATHS:**
- Subagent definitions are in `.claude/agents/` NOT `.claude/subagents/`
- Use correct subagent_type names: "project-structure-architect", "technical-researcher", "dependency-analyzer", "timeline-estimator"

```
Launch 4 subagents concurrently in a SINGLE message:

Task(
  subagent_type="project-structure-architect",
  description="Project structure and task breakdown",
  prompt="""
  You are the project-structure-architect subagent for creating comprehensive Work Breakdown Structures.

  Your subagent definition is available at: /home/felix/projects/automation-project-planner/.claude/agents/project-structure-architect.md

  Your task: Analyze the INITIAL.md file and create complete project structure with WBS.

  INITIAL.md content:
  {paste full INITIAL.md content}

  Follow all instructions in your subagent definition.

  Return your complete deliverables:
  1. Project Hierarchy (WBS with codes like 1.2.3)
  2. Complete Task List (75+ tasks across 8 phases)
  3. Resource Allocation Plan (team roles, utilization %)
  4. Risk Register (5+ risks with mitigation)
  5. Milestone Schedule

  Ensure all tasks have three-point estimates (Optimistic, Most Likely, Pessimistic).
  """
)

Task(
  subagent_type="technical-researcher",
  description="Technology research and analysis",
  prompt="""
  You are the technical-researcher subagent for comprehensive technology assessment.

  Your subagent definition is available at: /home/felix/projects/automation-project-planner/.claude/agents/technical-researcher.md

  Your task: Research all technologies mentioned in INITIAL.md and create comprehensive assessment.

  INITIAL.md content:
  {paste full INITIAL.md content}

  Focus on:
  - All mentioned technologies (evaluate pros/cons/gotchas)
  - Pending decisions (e.g., technology comparisons with ADRs)
  - Integration patterns (how components connect)
  - Best practices and common pitfalls
  - Cost analysis where applicable

  Return your complete deliverables:
  1. Technology Assessment Report (15+ technologies analyzed)
  2. Architecture Decision Records (ADRs) for key decisions
  3. Integration Pattern Documentation
  4. Consolidated Gotchas and Best Practices
  5. Technical Risk Analysis
  """
)

Task(
  subagent_type="dependency-analyzer",
  description="Dependency and critical path analysis",
  prompt="""
  You are the dependency-analyzer subagent for CPM analysis.

  Your subagent definition is available at: /home/felix/projects/automation-project-planner/.claude/agents/dependency-analyzer.md

  Your task will be to analyze dependencies AFTER project-structure-architect provides task list.

  For now: Acknowledge readiness and wait for task list from consolidation phase.

  Return exactly: "Ready to analyze dependencies. Waiting for task list from project-structure-architect."
  """
)

Task(
  subagent_type="timeline-estimator",
  description="Timeline estimation and buffer planning",
  prompt="""
  You are the timeline-estimator subagent for PERT analysis and buffer planning.

  Your subagent definition is available at: /home/felix/projects/automation-project-planner/.claude/agents/timeline-estimator.md

  Your task will be to calculate timeline AFTER receiving task estimates and critical path from other subagents.

  For now: Acknowledge readiness and wait for inputs.

  Return exactly: "Ready to calculate timeline. Waiting for task estimates and critical path data."
  """
)
```

**Note on Parallelization:**
- project-structure-architect and technical-researcher run fully in parallel (independent)
- dependency-analyzer and timeline-estimator wait for project-structure-architect output
- After first round completes, launch dependency-analyzer and timeline-estimator sequentially with actual data

### Step 4: Wait for Subagent Completion

All subagents will return their results. Collect:
- Project structure from project-manager
- Technology research from technical-researcher
- Placeholder acknowledgments from dependency-analyzer and timeline-estimator

### Step 5: Second Round - Dependency and Timeline Analysis

**CRITICAL: Launch these sequentially, NOT in parallel!**

Now launch dependency-analyzer with actual task data from project-structure-architect:

```
Task(
  subagent_type="dependency-analyzer",
  description="Dependency analysis with task list",
  prompt="""
  You are the dependency-analyzer subagent for Critical Path Method (CPM) analysis.

  Your subagent definition: /home/felix/projects/automation-project-planner/.claude/agents/dependency-analyzer.md

  Task list from project-structure-architect:
  {paste complete task list with:
   - WBS codes (e.g., 1.2.3)
   - Task names
   - Durations (use Most Likely estimate from three-point)
   - Mentioned dependencies (FS, SS, FF, SF)
   - Resource assignments
  }

  Perform complete dependency analysis following your subagent definition.

  Return all deliverables including:
  - Complete dependency matrix (147 dependencies)
  - Critical path analysis (identify 38+ critical tasks)
  - Float analysis (ES, EF, LS, LF, TF for all tasks)
  - Bottleneck analysis (resource conflicts, long chains)
  - Circular dependency check (must be zero)
  - Optimization recommendations
  - Gantt chart data structure (JSON format)
  """
)
```

**Wait for dependency-analyzer to complete**, then launch timeline-estimator:

```
Task(
  subagent_type="timeline-estimator",
  description="Timeline calculation and buffer planning",
  prompt="""
  You are the timeline-estimator subagent for PERT analysis and Critical Chain buffer planning.

  Your subagent definition: /home/felix/projects/automation-project-planner/.claude/agents/timeline-estimator.md

  Inputs from other subagents:

  1. Task list with three-point estimates from project-structure-architect:
  {paste tasks with O, M, P estimates}

  2. Critical path from dependency-analyzer:
  - Critical path duration: {X} days
  - Critical tasks: {list of WBS codes}
  - Float data: {ES, LS, TF for all tasks}
  - Bottlenecks: {identified bottlenecks}

  3. Project context:
  - Start date: {from INITIAL.md or default: 2025-01-15}
  - Resource constraints: {from project-structure-architect}

  Calculate complete timeline following your subagent definition.

  Return all deliverables including:
  - PERT analysis (TE, σ for each task)
  - Project-level statistics (project σ, confidence intervals)
  - Buffer plan (project buffer 40%, feeding buffers, resource buffers)
  - Complete timeline with calendar dates
  - Milestone schedule (M1-M7 with dates)
  - Risk-adjusted scenarios (optimistic, expected, conservative)
  - Optimization recommendations (crashing, fast-tracking)
  - Gantt chart data (JSON format)
  """
)
```

### Step 6: Consolidate All Results

Merge all subagent outputs into single comprehensive PRP using the base template:

```
Read: PRPs/templates/prp_automation_base.md
```

Fill in all placeholders with actual data from subagents:
- Project structure → from project-manager
- Task breakdown → from project-manager
- Technology assessments → from technical-researcher
- Dependency graph → from dependency-analyzer
- Timeline → from timeline-estimator
- Risk register → from project-manager + technical-researcher
- Resource plan → from project-manager

### Step 7: Generate PRP File

**Filename Convention:**
```
PRPs/{project-name-kebab-case}.md
```

Example: `PRPs/aie-scaler-phase1.md`

**CRITICAL: TOKEN-LIMIT PROTECTION**

PRPs are typically very large (10,000+ lines). Writing them in one operation will exceed response token limits and fail.

**MANDATORY APPROACH: Write PRP in sections**

```
Section 1: Header + Executive Summary
Write: PRPs/{filename}.md
Content:
---
# {Project Name} - Project Requirements Planning (PRP)

**Generated:** {date}
**Version:** 1.0.0
**Status:** Draft

---

## Executive Summary

{2-3 paragraphs from project-structure-architect}

### Key Metrics
- Total Tasks: {count}
- Duration: {X} days (50% confidence), {Y} days (95% confidence)
- Critical Path: {X} days
- Team Size: {count} roles
- Budget Estimate: €{amount}

---

Section 2: Project Context & Requirements
Edit: PRPs/{filename}.md
old_string: "---\n\n"
new_string: "---

## 1. Project Context

{from INITIAL.md PROJEKT-KONTEXT}

## 2. Functional Requirements

{from INITIAL.md FUNKTIONALE ANFORDERUNGEN}

## 3. Technology Stack

{from INITIAL.md TECHNOLOGIE-STACK + technical-researcher summary}

---

"

Section 3: Project Structure
Edit: PRPs/{filename}.md
old_string: "---\n\n"
new_string: "---

## 4. Project Structure (WBS)

{from project-structure-architect - hierarchical WBS with codes}

### 4.1 Level 1: Project Phases

{8 phases}

### 4.2 Level 2: Subprojects

{~20 subprojects}

### 4.3 Level 3: Tasks

{75+ tasks - use table format to save space}

| WBS Code | Task Name | Duration (M) | Resources | Dependencies |
|----------|-----------|--------------|-----------|--------------|
| 1.1.1 | ... | 3d | PM | - |
| ... | ... | ... | ... | ... |

---

"

Section 4: Dependency Analysis
Edit: PRPs/{filename}.md
old_string: "---\n\n"
new_string: "---

## 5. Dependency Analysis

{from dependency-analyzer}

### 5.1 Critical Path
- Duration: {X} days
- Tasks: {38+ critical tasks}

### 5.2 Dependency Matrix (Summary)
{First 20 dependencies + link to appendix}

### 5.3 Bottleneck Analysis
{from dependency-analyzer}

---

"

Section 5: Timeline & Resources
Edit: PRPs/{filename}.md
old_string: "---\n\n"
new_string: "---

## 6. Timeline Estimation

{from timeline-estimator}

### 6.1 PERT Analysis Summary
{key findings}

### 6.2 Project Schedule
| Phase | Start Date | End Date | Duration |
|-------|-----------|----------|----------|
| ... | ... | ... | ... |

### 6.3 Buffer Plan
- Project Buffer: {61} days (40% of critical path)
- Feeding Buffers: {count} buffers

### 6.4 Milestones
| Milestone | Date | Deliverables |
|-----------|------|--------------|
| M1 | ... | ... |

## 7. Resource Allocation

{from project-structure-architect}

---

"

Section 6: Risks & Technology
Edit: PRPs/{filename}.md
old_string: "---\n\n"
new_string: "---

## 8. Risk Register

{from project-structure-architect + technical-researcher}

| Risk ID | Description | Probability | Impact | Mitigation |
|---------|-------------|-------------|--------|------------|
| R1 | ... | High | High | ... |

## 9. Technology Assessments

{from technical-researcher - summarized}

### 9.1 Key Technologies
{15+ technologies with brief assessment}

### 9.2 Architecture Decision Records (ADRs)
{5 major ADRs}

---

"

Section 7: Appendices
Edit: PRPs/{filename}.md
old_string: "---\n\n"
new_string: "---

## Appendices

### Appendix A: Complete Dependency Matrix
{full 147 dependencies from dependency-analyzer}

### Appendix B: Complete Task Breakdown
{all 75+ tasks with full details}

### Appendix C: PERT Analysis (Full)
{complete PERT tables from timeline-estimator}

### Appendix D: Technology Research (Full)
{complete technology research from technical-researcher}

### Appendix E: Gantt Chart Data
```json
{JSON from dependency-analyzer or timeline-estimator}
```

---

**End of PRP**
"
```

**Key Rules for Section Writing:**
1. **Start with Write** for Section 1 (creates file)
2. **Use Edit with old_string="---\n\n"** for Sections 2-7 (appends content)
3. **Each section < 10,000 characters** (prevents token overflow)
4. **Use tables for large data** (more compact than prose)
5. **Summarize in main body, full details in appendices**
6. **If a section is still too large**, split it further (e.g., Section 3a and 3b)

### Step 8: Validation

**Quality Checks:**
- ✅ All sections from base template filled (no TODO placeholders)
- ✅ Project structure is complete (3-4 levels)
- ✅ All tasks have estimates (O, M, P)
- ✅ Dependencies are documented
- ✅ Timeline has dates
- ✅ Risk register has 5+ risks
- ✅ Milestones defined

If validation fails:
- Identify missing sections
- Re-run relevant subagent
- Re-consolidate

### Step 9: Report to User

```markdown
✅ **PRP Generated Successfully!**

**Output File:** `PRPs/{filename}.md`

**Summary:**
- **Project:** {Project Name}
- **Total Tasks:** {count} tasks across {count} phases
- **Timeline:** {X} days (50% confidence), {Y} days (95% confidence)
- **Critical Path:** {X} days ({count} critical tasks)
- **Team Size:** {count} roles
- **Budget Estimate:** €{amount}/month
- **Risks Identified:** {count} (with mitigation strategies)
- **Milestones:** {count} major milestones

**PRP Structure (7 Sections):**
1. ✅ Executive Summary with Key Metrics
2. ✅ Project Context & Requirements (from INITIAL.md)
3. ✅ Technology Stack Analysis ({count} technologies researched)
4. ✅ Project Structure (WBS) - {count} tasks with 3-point estimates
5. ✅ Dependency Analysis - {count} dependencies, critical path identified
6. ✅ Timeline & Resource Allocation - PERT analysis, buffer plan
7. ✅ Risk Register & Technology Assessments - ADRs, gotchas
8. ✅ Appendices - Complete data tables, Gantt chart JSON

**Subagents Executed:**
- ✅ project-structure-architect ({X} seconds)
- ✅ technical-researcher ({X} seconds)
- ✅ dependency-analyzer ({X} seconds)
- ✅ timeline-estimator ({X} seconds)

**Next Steps:**
1. **Review PRP:** `cat PRPs/{filename}.md | less` or open in editor
2. **Verify Content:**
   - Task breakdown is logical and complete
   - Timeline is realistic for team capacity
   - Risks have appropriate mitigation strategies
   - Technology choices are justified
3. **Execute in Notion:** `/execute-automation-prp PRPs/{filename}.md`
   - This will use Notion MCP tools directly to create project structure
   - Creates full project structure in Notion with all relations
   - Estimated time: 3-5 minutes

**Quality Metrics:**
- WBS Depth: {2-4} levels
- Task Granularity: All tasks 8-80 hours ✓
- Dependency Coverage: {95-100}% of tasks have dependencies ✓
- Estimation Coverage: 100% tasks have 3-point estimates ✓
- Risk Coverage: All high-impact areas covered ✓
```

**If PRP is incomplete or has errors:**
- Check subagent outputs for errors/warnings
- Re-run specific subagent if needed
- Consolidate manually using base template

## Example Usage

```bash
# Create your INITIAL.md
cp PRPs/INITIAL.md PRPs/MY-auth-system.md
# Edit with your project details
nano PRPs/MY-auth-system.md

# Generate comprehensive PRP
/generate-automation-prp PRPs/MY-auth-system.md

# Wait 2-3 minutes for subagents to complete

# Review generated PRP
cat PRPs/customer-portal-auth-system.md

# If satisfied, execute to create in Notion
/execute-automation-prp PRPs/customer-portal-auth-system.md
```

## Troubleshooting

### Error: "INITIAL.md missing required sections"

**Fix:** Add missing sections to your INITIAL.md. Required sections are:
- PROJEKT-KONTEXT
- FUNKTIONALE ANFORDERUNGEN
- TECHNOLOGIE-STACK
- RESSOURCEN

### Error: "Subagent failed to complete"

**Possible causes:**
- Insufficient context (INITIAL.md too vague)
- Missing AI docs (check PRPs/ai_docs/ exists)
- Subagent definition file not found (check `.claude/agents/` directory)

**Fix:**
- Make INITIAL.md more detailed and specific
- Ensure all AI docs are present in PRPs/ai_docs/
- Verify subagent files exist: `ls .claude/agents/*.md`
- Retry command

### Error: "Response token limit exceeded" or "Output truncated"

**Cause:** PRP file too large to write in single operation (>15,000 lines)

**CRITICAL FIX: Use sectioned writing approach (mandatory for large PRPs)**

Instead of writing entire PRP at once:
```
# BAD - Will fail with token limit
Write: PRPs/huge-project.md
Content: {entire 20,000-line PRP}  ❌ FAILS
```

Use this approach:
```
# GOOD - Write in 7 sections
1. Write: PRPs/huge-project.md (Section 1: Header + Summary)
2. Edit: PRPs/huge-project.md (Section 2: Context - append)
3. Edit: PRPs/huge-project.md (Section 3: Structure - append)
4. Edit: PRPs/huge-project.md (Section 4: Dependencies - append)
5. Edit: PRPs/huge-project.md (Section 5: Timeline - append)
6. Edit: PRPs/huge-project.md (Section 6: Risks - append)
7. Edit: PRPs/huge-project.md (Section 7: Appendices - append)
```

**Rules for section splitting:**
- Each section MUST be < 10,000 characters
- Use tables for large data (more compact)
- Put detailed data in appendices
- Summarize in main sections
- If section still too large, split further (e.g., 3a, 3b)

**Validation:**
```bash
# Check section sizes before writing
echo "Section 3 length: $(echo "$section3" | wc -c)"
# If > 10000, split into 3a and 3b
```

### Warning: "High uncertainty in estimates"

**Meaning:** Many tasks have high standard deviation (σ > 1.5 days)

**Recommendation:**
- Review task breakdown (may need more detail)
- Add more specific requirements to INITIAL.md
- Consider breaking large uncertain tasks into smaller tasks

## Success Criteria

Generated PRP should have:
- ✅ Clear project hierarchy (WBS)
- ✅ All tasks 8-80 hours
- ✅ Three-point estimates for all tasks
- ✅ Complete dependency graph
- ✅ Identified critical path
- ✅ Realistic timeline with buffers
- ✅ Resource allocation plan
- ✅ Risk register (5+ risks)
- ✅ Technology assessments
- ✅ Milestone schedule
- ✅ Notion integration plan

## Time Estimate

**Total Time:** 2-4 minutes

Breakdown:
- Validation: 5 seconds
- project-manager + technical-researcher (parallel): 60-90 seconds
- dependency-analyzer + timeline-estimator (sequential): 60-90 seconds
- Consolidation: 10-20 seconds

---

**Version:** 1.0.0
**Last Updated:** 2025-01-10
