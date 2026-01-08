# Generate Codebase Exploration PRP

Generate a comprehensive Project Requirements Planning (PRP) document for exploring and understanding a large open-source codebase. This command creates a structured exploration plan with targeted tasks for deep-diving into architecture, patterns, and implementation details.

## Usage

```
/generate-exploration-prp PRPs/INITIAL.md
```

## What This Command Does

1. **Validates INITIAL.md** - Ensures exploration goals and focus areas are defined
2. **Analyzes Codebase Structure** - Uses Serena to map top-level structure
3. **Launches Exploration Subagents in Parallel:**
   - **Explore agent (architecture)** - Maps high-level architecture and patterns
   - **Explore agent (entry-points)** - Identifies key entry points and flows
   - **technical-researcher** - Researches technologies and conventions used
4. **Creates Exploration Tasks** - Generates Archon tasks for systematic exploration
5. **Generates PRP File** - Writes exploration plan to `PRPs/{project-name}-exploration.md`

## Expected Input Format

INITIAL.md for exploration should contain:

```markdown
# INITIAL: {Codebase Name} Exploration

## EXPLORATION GOALS
- What do you want to understand?
- What features are you planning to add?
- What problems are you trying to solve?

## FOCUS AREAS
- Specific modules or features to explore
- Integration points of interest
- Patterns you want to understand

## KNOWN CONTEXT (Optional)
- What you already know about the codebase
- Documentation you've read
- Previous experience with similar projects

## QUESTIONS TO ANSWER
- Specific technical questions
- Architecture decisions to understand
- Implementation details to discover

## TARGET ADDITIONS (Optional)
- Features you plan to implement
- Modifications you're considering
- Integration points you need to understand
```

## Execution Steps

### Step 1: Validate Input File

```
Read: {provided_path}
```

Check for required sections:
- EXPLORATION GOALS (required)
- FOCUS AREAS (required)
- QUESTIONS TO ANSWER (recommended)

If validation fails, alert user with example format.

### Step 2: Get Codebase Overview with Serena

Use Serena tools to understand project structure:

```
mcp__serena__list_dir(relative_path=".", recursive=false)
mcp__serena__list_memories()
mcp__serena__read_memory("codebase_structure.md")  # If exists
mcp__serena__read_memory("tech_stack.md")  # If exists
```

### Step 3: Launch Exploration Subagents in Parallel

**CRITICAL: Use single message with multiple Task tool calls!**

```
Task(
  subagent_type="Explore",
  description="Architecture exploration",
  model="haiku",
  prompt="""
  Explore the codebase architecture for: {project_name}

  EXPLORATION GOALS from INITIAL.md:
  {paste EXPLORATION GOALS section}

  FOCUS AREAS:
  {paste FOCUS AREAS section}

  Your task:
  1. Identify the high-level architecture pattern (monolith, microservices, modular, etc.)
  2. Map the main modules/components and their responsibilities
  3. Find configuration and environment handling
  4. Identify database/storage layers
  5. Map API routes and entry points
  6. Find authentication/authorization patterns
  7. Identify background jobs and async processing
  8. Note any interesting design patterns used

  Return a structured report with:
  - Architecture Overview (diagram description)
  - Module Map (name, purpose, key files)
  - Key Patterns Identified
  - Configuration Approach
  - Questions that emerged during exploration
  """
)

Task(
  subagent_type="Explore",
  description="Entry points and data flows",
  model="haiku",
  prompt="""
  Explore entry points and data flows for: {project_name}

  FOCUS AREAS from INITIAL.md:
  {paste FOCUS AREAS section}

  QUESTIONS TO ANSWER:
  {paste QUESTIONS section}

  Your task:
  1. Find all user-facing entry points (routes, CLI, etc.)
  2. Trace data flow for key operations
  3. Identify external integrations (APIs, services)
  4. Map event handling and WebSocket patterns
  5. Find cron jobs and scheduled tasks
  6. Identify middleware chains
  7. Note error handling patterns

  Return a structured report with:
  - Entry Points Catalog (route, handler, purpose)
  - Data Flow Diagrams (text descriptions)
  - External Integrations List
  - Event System Description
  - Key Files to Read for Deep Understanding
  """
)

Task(
  subagent_type="technical-researcher",
  description="Technology and convention research",
  model="haiku",
  prompt="""
  Research the technologies and conventions used in: {project_name}

  Based on the tech stack identified (from Serena memories or package files):
  {paste tech stack info}

  Your task:
  1. Research best practices for the main framework
  2. Identify coding conventions used in this codebase
  3. Document the testing approach
  4. Note build and deployment patterns
  5. Research any unfamiliar libraries/tools
  6. Identify potential gotchas for contributors

  Return:
  - Technology Quick Reference (framework, version, key concepts)
  - Coding Conventions Observed
  - Testing Strategy
  - Build/Deploy Pipeline
  - Gotchas and Tips for New Contributors
  """
)
```

### Step 4: Create Archon Exploration Tasks

Based on subagent findings, create targeted exploration tasks in Archon:

```
mcp__archon__manage_task("create",
  project_id="{project_id}",
  title="Explore: {module_name}",
  description="Deep dive into {module_name}:\n- Key files: {files}\n- Questions: {questions}\n- Goal: {goal}",
  feature="Codebase Exploration",
  task_order={priority}
)
```

Create tasks for:
- Each major module identified
- Each focus area from INITIAL.md
- Each unanswered question
- Each planned addition (if specified)

### Step 5: Generate Exploration PRP

Write the PRP in sections (to avoid token limits):

**Section 1: Header and Executive Summary**
```markdown
# {Project Name} - Codebase Exploration PRP

**Generated:** {date}
**Codebase:** {repo_url or local_path}
**Version:** {version from package.json or similar}

---

## Executive Summary

This exploration plan provides a systematic approach to understanding
the {project_name} codebase, focusing on:

- {goal_1}
- {goal_2}
- {goal_3}

### Quick Stats
- **Architecture:** {pattern}
- **Primary Language:** {language}
- **Framework:** {framework}
- **LOC Estimate:** {estimate}
- **Key Modules:** {count}

---
```

**Section 2: Architecture Overview**
```markdown
## 1. Architecture Overview

{From Explore agent - architecture report}

### Module Map

| Module | Purpose | Key Files | Priority |
|--------|---------|-----------|----------|
| ... | ... | ... | ... |

### Architecture Diagram (Text)

{ASCII or description of architecture}

---
```

**Section 3: Entry Points and Data Flows**
```markdown
## 2. Entry Points & Data Flows

{From Explore agent - entry points report}

### API Routes

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| ... | ... | ... | ... |

### Data Flow: {Key Operation}

{Text description of data flow}

---
```

**Section 4: Technology Reference**
```markdown
## 3. Technology Reference

{From technical-researcher report}

### Framework Quick Reference

{Key concepts and patterns}

### Coding Conventions

{Observed conventions}

### Gotchas for Contributors

{Pitfalls to avoid}

---
```

**Section 5: Exploration Tasks**
```markdown
## 4. Exploration Tasks

Tasks created in Archon for systematic exploration:

| Task | Focus Area | Priority | Status |
|------|------------|----------|--------|
| ... | ... | ... | Todo |

### Exploration Order (Recommended)

1. **Start Here:** {entry_point}
2. **Then:** {next_module}
3. **Deep Dive:** {complex_area}

---
```

**Section 6: Questions and Next Steps**
```markdown
## 5. Questions to Answer

### From INITIAL.md
{Original questions}

### Discovered During Exploration
{New questions from subagents}

## 6. Next Steps

1. Execute exploration tasks: `/execute-exploration-prp PRPs/{filename}.md`
2. Read key files identified
3. Answer outstanding questions
4. Update Serena memories with findings

---

**End of Exploration PRP**
```

### Step 6: Report to User

```markdown
✅ **Exploration PRP Generated!**

**Output File:** `PRPs/{project-name}-exploration.md`

**Summary:**
- **Codebase:** {project_name}
- **Architecture:** {pattern}
- **Modules Identified:** {count}
- **Entry Points Found:** {count}
- **Exploration Tasks Created:** {count} in Archon

**Subagents Executed:**
- ✅ Architecture Exploration
- ✅ Entry Points & Flows
- ✅ Technology Research

**Archon Tasks Created:**
{list of task titles}

**Next Steps:**
1. Review the PRP: `PRPs/{filename}.md`
2. Start with recommended exploration order
3. Execute: `/execute-exploration-prp PRPs/{filename}.md`
4. Or manually explore using Serena tools

**Quick Start:**
- First file to read: `{recommended_file}`
- Key module to understand: `{key_module}`
- Main entry point: `{entry_point}`
```

## Differences from /generate-automation-prp

| Aspect | Automation PRP | Exploration PRP |
|--------|---------------|-----------------|
| **Purpose** | Plan implementation tasks | Plan understanding tasks |
| **Output** | WBS with estimates | Exploration map with priorities |
| **Tasks** | 8-80 hour work items | 30-120 min exploration sessions |
| **Focus** | Deliverables | Knowledge acquisition |
| **Notion** | Full project structure | Optional documentation |
| **Subagents** | 4 (PM, Tech, Deps, Time) | 3 (2x Explore, Tech) |

## Troubleshooting

### "INITIAL.md too vague"

**Fix:** Add specific questions and focus areas. Example:
```markdown
## FOCUS AREAS
- Authentication system (how JWT is handled)
- WebSocket implementation (real-time features)
- Plugin/extension architecture

## QUESTIONS TO ANSWER
- How are routes organized?
- Where is state managed?
- How does the build system work?
```

### "Too many modules identified"

**Behavior:** Focus on FOCUS AREAS from INITIAL.md first, prioritize others lower.

### "Missing tech stack info"

**Fix:** Run `/primer` first to complete Serena onboarding, or manually read package.json/pyproject.toml.

---

**Version:** 1.0.0
**Last Updated:** 2025-11-25
