---
description: Generate a new skill for Claude Code to perform specialized tasks
argument-hint: <skill-name> <description>
---

# Create New Skill

Generate a new skill to extend Claude Code's capabilities for specialized tasks.

## Instructions

1. **Parse Arguments**:
   - $1: skill-name (lowercase, hyphens only, max 64 chars)
   - $2+: description (what the skill does and when to use it)

2. **Create Skill Directory**:
   - Location: `.claude/skills/$1/`
   - Create directory if it doesn't exist

3. **Generate SKILL.md**:
   - Add YAML frontmatter with name and description
   - Include comprehensive instructions section
   - Add examples section with concrete use cases
   - Add troubleshooting section if applicable

4. **Determine Required Tools**:
   - Ask user what Claude should be able to do in this skill
   - Add `allowed-tools` frontmatter if restrictions needed
   - Default: no restrictions (Claude has full access)

5. **Create Supporting Files** (if needed):
   - Ask user if they need:
     - Python scripts (`scripts/`)
     - Templates (`templates/`)
     - Reference documentation (`reference.md`)
     - Examples file (`examples.md`)

6. **Test Skill**:
   - Inform user to restart Claude Code or run reload
   - Explain how to invoke the skill (it's automatic based on description)

## Best Practices

- **Specific descriptions**: Include concrete keywords users would mention
- **Single responsibility**: Each skill should do one thing well
- **Clear examples**: Show real-world usage scenarios
- **Tool restrictions**: Use `allowed-tools` for read-only or security-sensitive workflows

## Example Usage

```bash
/create-skill pdf-processor "Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF files."
```

## Template Structure

```yaml
---
name: skill-name
description: What it does and when to use it (include specific triggers)
allowed-tools: Read, Write, Bash  # Optional: restrict tools
---

# Skill Name

## Purpose
Clear explanation of what this skill accomplishes.

## When to Use
- Specific scenario 1
- Specific scenario 2
- Specific scenario 3

## Instructions
Step-by-step guidance for Claude:

1. First step with clear action
2. Second step with decision criteria
3. Third step with validation

## Examples

### Example 1: Common Use Case
**User request**: "Process invoice.pdf"
**Expected action**:
- Extract text using appropriate tool
- Parse invoice data
- Format output as structured JSON

### Example 2: Edge Case
**User request**: "Merge 5 PDFs"
**Expected action**:
- Validate all files exist
- Use merge tool/library
- Confirm output

## Error Handling
- What to do if files don't exist
- How to handle malformed data
- When to ask user for clarification

## Success Criteria
- ✅ Task completed successfully
- ✅ User receives expected output
- ✅ No errors or clear error messages
```

---

**After creating the skill, inform the user**:
1. Skill location: `.claude/skills/$1/`
2. How to use it (automatic, based on description)
3. How to test it (just ask Claude to do the task)
4. Team sharing: Commit to git and teammates get it automatically
