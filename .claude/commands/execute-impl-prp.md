---
description: Execute implementation tasks from a PRP file, tracking progress through each task
argument-hint: <prp-file-path>
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Task, mcp__serena*, mcp__archon*
---

# Execute Implementation PRP

Execute the implementation tasks defined in a PRP file, working through each task systematically.

## Input

PRP file path: $1

## Instructions

1. **Read the PRP file** at the provided path

2. **Parse the implementation tasks** and create a task list:
   - Extract all tasks from each phase
   - Note dependencies between tasks
   - Identify acceptance criteria for each task

3. **For each task in order**:

   a. **Announce the task** you're starting

   b. **Read relevant files** mentioned in the task

   c. **Implement the changes**:
      - Use Edit tool for modifications
      - Use Write tool for new files
      - Follow the implementation steps in the PRP

   d. **Verify acceptance criteria**:
      - Check each criterion is met
      - Run any specified tests

   e. **Mark task complete** and move to next

4. **Handle blockers**:
   - If a task is blocked, note why and continue with unblocked tasks
   - Report blocked tasks at the end

5. **Final Report**:
   - List completed tasks
   - List any blocked/skipped tasks
   - Summarize changes made
   - Note any follow-up actions needed

## Execution Rules

- **DO NOT skip steps** - work through each task methodically
- **DO NOT make changes not specified** - stick to the PRP
- **DO verify before marking complete** - check acceptance criteria
- **DO use Serena tools** for symbol-based editing when appropriate
- **DO create Archon tasks** if the project exists in Archon

## Progress Tracking

Update the PRP file with progress markers as you work:
- `[x]` for completed criteria
- `[!]` for blocked criteria
- `[~]` for partially complete criteria

## Output

- Summary of completed tasks
- List of files modified/created
- Any issues encountered
- Recommendations for testing
