---
description: Generate a new slash command for frequently-used prompts
argument-hint: <command-name> <description>
---

# Create New Slash Command

Generate a new slash command for frequently-used prompts and workflows.

## Instructions

1. **Parse Arguments**:
   - $1: command-name (will be `/command-name`)
   - $2+: description (what the command does)

2. **Create Command File**:
   - Location: `.claude/commands/$1.md`
   - Filename becomes the command name

3. **Generate Command Content**:
   - Add YAML frontmatter (optional but recommended):
     - `description`: What the command does (for `/help` listing)
     - `argument-hint`: Show expected arguments
     - `allowed-tools`: Restrict tools if needed
     - `model`: Specify model (sonnet/opus/haiku)
   - Add clear markdown instructions for Claude
   - Include examples if applicable
   - Use `$ARGUMENTS` for all args or `$1`, `$2` for specific ones

4. **Ask User for Command Type**:
   - **Simple prompt**: Just markdown instructions
   - **With arguments**: Use `$1`, `$2`, `$ARGUMENTS`
   - **With bash**: Use `!command` for shell execution
   - **With files**: Use `@file.txt` for file references

5. **Test Command**:
   - Commands are immediately available (no restart needed)
   - Test with `/command-name args`

## Command vs Skill Decision

**Use Slash Command when**:
- Simple, frequently-used prompt snippet
- Explicit user invocation desired
- Quick one-off tasks
- No complex file structure needed

**Use Skill when**:
- Complex workflow requiring multiple files
- Claude should auto-discover when relevant
- Needs scripts, templates, or extensive docs
- Reusable across many contexts

## Example Usage

```bash
/create-command analyze-logs "Parse and summarize application logs for errors and warnings"
```

## Template Structure

### Basic Command
```markdown
---
description: Brief description for /help
---

# Command Name

Clear instructions for Claude to follow.

## Expected Output

What the user should receive.
```

### Command with Arguments
```markdown
---
description: Process file with specific format
argument-hint: <file-path> <format>
---

# Process File

Process the file at $1 with format $2.

## Steps

1. Read file from $1
2. Parse according to $2 format
3. Return processed results
```

### Advanced Command
```markdown
---
description: Full-featured command example
argument-hint: <target> [options]
allowed-tools: Read, Grep, Bash
model: sonnet
---

# Advanced Command

Process target: $1
Options: $2

## Instructions

1. Validate target exists
2. !ls -la $1  # Execute bash command
3. Process @template.txt  # Reference file
4. Return results

## Validation

- Check $1 is valid path
- Verify permissions
- Handle errors gracefully
```

---

**After creating the command, inform the user**:
1. Command location: `.claude/commands/$1.md`
2. How to use it: `/$1 [arguments]`
3. Test it: Try running the command now
4. Team sharing: Commit to git for team access
