# Execute Codebase Exploration PRP

Execute a generated exploration PRP to systematically explore and understand a large codebase. This command processes exploration tasks, uses Explore agents for deep dives, and documents findings in Serena memories.

## Usage

```
/execute-exploration-prp PRPs/open-webui-exploration.md
```

## What This Command Does

1. **Loads Exploration PRP** - Reads the exploration plan
2. **Gets Archon Tasks** - Retrieves exploration tasks for the project
3. **Executes Exploration Sessions** - For each task:
   - Launches Explore agent for targeted investigation
   - Documents findings
   - Updates Archon task status
   - Creates/updates Serena memories
4. **Consolidates Findings** - Creates summary documentation
5. **Reports Results** - Provides exploration summary and next steps

## Prerequisites

- ✅ Exploration PRP generated via `/generate-exploration-prp`
- ✅ Archon project with exploration tasks
- ✅ Serena onboarding completed

## Execution Steps

### Step 1: Load and Validate PRP

```
Read: {provided_path}
```

Extract:
- Project name and context
- Module map and entry points
- Exploration task list
- Questions to answer
- Recommended exploration order

### Step 2: Get Archon Exploration Tasks

```
mcp__archon__find_tasks(
  filter_by="project",
  filter_value="{project_id}",
  include_closed=false
)
```

Filter for exploration tasks (feature="Codebase Exploration" or status="todo").

### Step 3: Execute Exploration Sessions

For each exploration task, in recommended order:

**3a. Update Task Status**
```
mcp__archon__manage_task("update",
  task_id="{task_id}",
  status="doing"
)
```

**3b. Launch Targeted Explore Agent**
```
Task(
  subagent_type="Explore",
  description="Deep dive: {module_name}",
  model="haiku",
  prompt="""
  EXPLORATION TASK: {task_title}

  CONTEXT FROM PRP:
  - Module: {module_name}
  - Key Files: {key_files}
  - Questions to Answer: {questions}
  - Goal: {goal}

  CODEBASE CONTEXT:
  - Architecture: {architecture_pattern}
  - Framework: {framework}
  - Related Modules: {related_modules}

  Your task:
  1. Explore the specified module/area thoroughly
  2. Answer the listed questions
  3. Document patterns and conventions found
  4. Identify connections to other modules
  5. Note any gotchas or surprising behavior
  6. List files that warrant deeper reading

  Return a structured exploration report:

  ## {Module Name} - Exploration Report

  ### Overview
  {2-3 sentence summary}

  ### Key Findings
  - {finding_1}
  - {finding_2}
  - {finding_3}

  ### Architecture/Patterns
  {Patterns used in this module}

  ### Key Files
  | File | Purpose | Complexity |
  |------|---------|------------|
  | ... | ... | Low/Medium/High |

  ### Code Examples
  ```{language}
  // Key pattern or approach found
  {code_snippet}
  ```

  ### Connections to Other Modules
  - {connection_1}
  - {connection_2}

  ### Questions Answered
  - Q: {question}
    A: {answer}

  ### New Questions Discovered
  - {new_question_1}
  - {new_question_2}

  ### Gotchas / Important Notes
  - {gotcha_1}
  - {gotcha_2}

  ### Recommended Next Steps
  - {next_step_1}
  - {next_step_2}
  """
)
```

**3c. Save Findings to Serena Memory**

For significant findings, create or update Serena memories:

```
mcp__serena__write_memory(
  memory_file_name="exploration_{module_name}.md",
  content="{exploration_report}"
)
```

Or update existing memory:
```
mcp__serena__edit_memory(
  memory_file_name="codebase_structure.md",
  mode="literal",
  needle="{old_content}",
  repl="{new_content_with_findings}"
)
```

**3d. Update Archon Task with Findings**
```
mcp__archon__manage_task("update",
  task_id="{task_id}",
  status="done",
  description="{original_description}\n\n---\n## Findings\n{summary_of_findings}"
)
```

### Step 4: Answer Outstanding Questions

After all exploration tasks complete, review questions from PRP:

```
For each question in "Questions to Answer":
  - Check if answered in exploration reports
  - If not answered, create new exploration task OR
  - Launch quick Explore agent to answer
```

### Step 5: Consolidate Findings

Create a consolidated exploration summary:

```
mcp__serena__write_memory(
  memory_file_name="exploration_summary.md",
  content="""
# {Project Name} - Exploration Summary

**Completed:** {date}
**Exploration Sessions:** {count}
**Time Spent:** ~{estimate}

## Key Discoveries

### Architecture
{consolidated architecture findings}

### Key Patterns
{patterns found across modules}

### Important Files
{most important files to understand}

### Gotchas & Tips
{consolidated gotchas}

## Module Deep Dives

### {Module 1}
{summary}
See: exploration_{module_1}.md

### {Module 2}
{summary}
See: exploration_{module_2}.md

## Answered Questions
{list of Q&A}

## Remaining Questions
{unanswered questions}

## Recommended Reading Order
1. {file_1} - {reason}
2. {file_2} - {reason}
3. {file_3} - {reason}

## Ready for Implementation
Based on exploration, ready to work on:
- {feature_1}: Understood well, see {memory}
- {feature_2}: Needs more exploration in {area}
"""
)
```

### Step 6: Optional Notion Sync

If user wants to document findings in Notion:

```
mcp__Notion__notion-search(query="{project_name} exploration")

# If page exists, update it
mcp__Notion__notion-update-page(
  data={
    "page_id": "{page_id}",
    "command": "replace_content",
    "new_str": "{exploration_summary}"
  }
)

# If not, create new page
mcp__Notion__notion-create-pages(
  pages=[{
    "properties": {"title": "{Project Name} - Codebase Exploration"},
    "content": "{exploration_summary_markdown}"
  }]
)
```

### Step 7: Report Results

```markdown
✅ **Exploration Complete!**

## Summary

**Project:** {project_name}
**Exploration Sessions:** {count} completed
**Memories Created/Updated:** {count}
**Questions Answered:** {answered}/{total}

## Exploration Results

| Module | Status | Key Finding | Memory |
|--------|--------|-------------|--------|
| {mod_1} | ✅ Done | {finding} | exploration_{mod_1}.md |
| {mod_2} | ✅ Done | {finding} | exploration_{mod_2}.md |
| ... | ... | ... | ... |

## Key Discoveries

### Architecture
{1-2 sentence summary}

### Most Important Files
1. `{file_1}` - {why}
2. `{file_2}` - {why}
3. `{file_3}` - {why}

### Patterns Found
- {pattern_1}
- {pattern_2}

### Gotchas to Remember
- {gotcha_1}
- {gotcha_2}

## Questions Answered

| Question | Answer | Source |
|----------|--------|--------|
| {q1} | {a1} | {module} |
| {q2} | {a2} | {module} |

## Remaining Questions

{list any unanswered questions}

## Serena Memories Created

- `exploration_summary.md` - Consolidated findings
- `exploration_{module_1}.md` - Deep dive report
- `exploration_{module_2}.md` - Deep dive report
- Updated: `codebase_structure.md`

## Next Steps

1. **Read Key Files:**
   - Start with: `{recommended_file}`
   - Then: `{next_file}`

2. **If Planning Implementation:**
   - Create INITIAL.md for your feature
   - Run `/generate-exploration-prp` for feature-specific exploration
   - Or proceed to implementation with current knowledge

3. **If Questions Remain:**
   - Create new exploration task in Archon
   - Or ask specific questions in chat

4. **Review Memories:**
   ```
   mcp__serena__list_memories()
   mcp__serena__read_memory("exploration_summary.md")
   ```

## Quick Reference

**Entry Point:** `{main_entry_point}`
**Config:** `{config_file}`
**Routes:** `{routes_location}`
**Models:** `{models_location}`
**Tests:** `{tests_location}`
```

## Execution Modes

### Full Exploration (Default)
Executes all exploration tasks in recommended order.

### Selective Exploration
```
/execute-exploration-prp PRPs/file.md --focus="authentication"
```
Only executes tasks matching the focus area.

### Quick Exploration
```
/execute-exploration-prp PRPs/file.md --quick
```
Uses shorter exploration prompts, faster but less thorough.

### Resume Exploration
If interrupted, the command checks Archon task status and resumes from incomplete tasks.

## Troubleshooting

### "Task already completed"

The command skips tasks with status="done". To re-explore:
```
mcp__archon__manage_task("update", task_id="...", status="todo")
```

### "Too many tokens in exploration"

For very large modules, the Explore agent may truncate results. Solutions:
- Break exploration task into smaller sub-tasks
- Focus on specific files rather than entire modules
- Use `--quick` mode for overview, then targeted exploration

### "Memory write failed"

Check Serena is properly connected:
```
mcp__serena__list_memories()
```

If Serena unavailable, findings are still in Archon task descriptions.

### "Questions not answered"

Some questions require reading code directly rather than exploration. The command creates follow-up tasks for unanswered questions.

---

**Version:** 1.0.0
**Last Updated:** 2025-11-25
