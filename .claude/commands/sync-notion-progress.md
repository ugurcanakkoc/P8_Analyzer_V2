# Sync Notion Progress

Synchronize local task progress updates back to Notion.

## Usage

```
/sync-notion-progress
```

OR specify project:

```
/sync-notion-progress PRPs/customer-portal-auth-system.md
```

## What This Command Does

1. Prompts for updates (task status, actual hours, progress %)
2. Uses Notion MCP tools to sync to Notion
3. Updates Notion pages with new data
4. Reports sync summary

## Execution Steps

### Step 1: Gather Updates

Prompt user for updates:

```
Which tasks have updates? (provide WBS codes or task names)

Examples:
  - 1.1.2 (task by WBS code)
  - "Implement Authentication" (task by name)
  - all (update all tasks - will prompt for each)

Enter task identifier(s): _______

For Task {identifier}:
  - Current Status in Notion: {status}
  - New Status? [Todo/In Progress/Review/Done/Blocked]: _______
  - Actual Hours? (current: {X}): _______
  - Progress %? (current: {Y}%): _______

[Repeat for each task with updates]
```

### Step 2: Sync Updates to Notion

**Use Notion MCP tools directly to update task pages:**

```
For each task with updates:
  mcp__Notion__notion-update-page(
    data={
      "page_id": task_notion_id,
      "command": "update_properties",
      "properties": {
        "Status": new_status,
        "Actual Hours": actual_hours,
        "Progress": progress_percentage,
        ...
      }
    }
  )
```

**Rate limiting:** Respect 3 req/sec limit, batch updates if many tasks.

### Step 3: Report Results

```markdown
✅ **Notion Progress Synced**

**Updated {X} tasks:**
- Task 1.1.2: Status Todo → In Progress, 5 actual hours
- Task 1.1.3: Status In Progress → Done, 8 actual hours
- Task 2.1.1: Progress 50% → 75%

**Notion Links:**
- View updates: {task_database_url}
```

---

**Version:** 1.0.0
