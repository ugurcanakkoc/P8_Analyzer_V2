# Prime Context for Claude Code

- Check your sub-agent files for specific roles and capabilities.

## Step 1: MCP Server Integration Check

### CRITICAL: Check Archon MCP Server first

- List available Archon projects: Use `mcp__archon__list_projects` to check for existing projects
- Check current tasks: Use `mcp__archon__list_tasks` to see if there are active tasks
- Review project context: If project exists, use `mcp__archon__get_project` to understand current state

### Serena MCP Server - Codebase Intelligence

- Check onboarding status: Use `mcp__serena__check_onboarding_performed`
- List available memories: Use `mcp__serena__list_memories` to see existing codebase knowledge
- Read relevant memories: Use `mcp__serena__read_memory` for project-specific context

### Notion MCP Server - Project Documentation

- Search for AIE Scaler project: Use `mcp__Notion__notion-search` with query "AIE Scaler"
- Fetch project details: Use `mcp__Notion__notion-fetch` with project URL/ID
- Review project structure: Check databases, pages, and linked content
- Note: This provides context on the AIE SCALER 2030 workflow documented in data/mural/

## Step 2: Project Structure Analysis

Use the command `tree` or `find` to get an understanding of the project structure.

Start with reading the CLAUDE.md file if it exists to get an understanding of the project guidelines and Archon workflow.

Read the README.md file to get an understanding of the project purpose and architecture.

Read key files in the src/ or root directory to understand implementation.

## Step 3: Context Summary

Explain back to me:

- **Archon Project Status**: Active projects, current tasks, and priorities
- **Serena Memory State**: Available memories and key codebase insights
- **Project Structure**: Directory layout and organization
- **Project Purpose**: Goals, architecture, and core services
- **Key Files**: Important configuration and implementation files
- **Dependencies**: Critical tools, libraries, and external services
- **Development Workflow**: Git flow, CI/CD, and deployment process

## Step 4: Readiness Check

Confirm:

- ✅ Archon project context loaded (or new project needed)
- ✅ Serena onboarding completed (or needs to be performed)
- ✅ CLAUDE.md guidelines understood
- ✅ Ready to follow Archon-first task management workflow
