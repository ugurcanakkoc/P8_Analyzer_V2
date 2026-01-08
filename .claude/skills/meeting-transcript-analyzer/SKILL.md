---
name: meeting-transcript-analyzer
description: Analyze meeting transcripts to extract tasks, action items, participants with roles, decisions, and key discussion points. Output structured data for PRP creation and Notion project planning. Recognizes task assignments, deadlines, responsibilities, and follow-up items. Use when user mentions "meeting transcript", "meeting notes", "action items from meeting", or provides transcript files.
allowed-tools: Read, Write, Grep, mcp__archon__manage_task, mcp__archon__manage_project, mcp__Notion__notion-create-pages
---

# Meeting Transcript Analyzer

## Purpose
Automatically extract structured information from meeting transcripts including:
- **Tasks & Action Items** - What needs to be done
- **Participants & Roles** - Who attended and their responsibilities
- **Decisions Made** - Key decisions and agreements
- **Discussion Points** - Important topics discussed
- **Deadlines & Timelines** - When things are due
- **Follow-up Items** - What needs to happen next

Output is optimized for:
- Creating Archon tasks
- Generating Notion project pages
- Feeding into PRP (Project Requirements Plan) generation
- Team accountability tracking

## When to Use

**Automatic Activation Triggers:**
- User mentions "meeting transcript" or "meeting notes"
- User uploads or references a file in `data/transcripts/`
- User asks to "extract action items from meeting"
- User says "create tasks from meeting notes"
- User requests "analyze meeting" or "summarize meeting"

**Proactive Usage:**
- After finding transcript files in data/transcripts/
- When preparing PRPs that reference meeting outcomes
- Before creating Notion project structures from meetings
- When user needs to assign tasks from discussions

## Instructions

### Step 1: Identify & Read Transcript

1. **Locate transcript file:**
   - Check `data/transcripts/` directory
   - User-provided file path
   - Ask user if location unclear

2. **Read transcript:**
   - Use Read tool to load full transcript
   - Note file format (TXT, MD, DOCX, PDF)
   - Identify transcript source (Zoom, Teams, manual notes, etc.)

### Step 2: Extract Participants & Roles

**Look for participant indicators:**
- Speaker labels: "Speaker 1:", "John Doe:", "[Max]"
- Role mentions: "John as Product Owner said..."
- Attendance lists: "Attendees: John (PM), Sarah (Dev), ..."
- Email signatures or introductions

**Extract structure:**
```json
{
  "participants": [
    {
      "name": "John Doe",
      "role": "Product Owner",
      "email": "john@example.com",
      "responsibility": "Decision maker for requirements"
    },
    {
      "name": "Sarah Miller",
      "role": "Lead Developer",
      "email": "sarah@example.com",
      "responsibility": "Technical implementation"
    }
  ]
}
```

**Role inference patterns:**
- Product Owner, PM, Manager → Decision-making authority
- Developer, Engineer, Tech Lead → Implementation responsibility
- Designer, UX → Design and user experience
- QA, Tester → Quality assurance
- Stakeholder, Client → Requirements and acceptance

### Step 3: Extract Tasks & Action Items

**Task indicator patterns:**
- "TODO:", "Action item:", "Follow-up:"
- "[Name] will [action]"
- "[Name] to [action] by [date]"
- "We need to [action]"
- "Decision: [Name] should [action]"

**Extract structure:**
```json
{
  "tasks": [
    {
      "title": "Design authentication flow",
      "description": "Create wireframes for OAuth2 login process",
      "assigned_to": "Sarah Miller",
      "assigned_to_role": "Lead Developer",
      "due_date": "2026-01-15",
      "priority": "High",
      "status": "todo",
      "mentioned_at": "Line 42-45",
      "context": "Discussed during security requirements section"
    }
  ]
}
```

**Priority inference:**
- "ASAP", "urgent", "critical" → High/Critical
- "important", "should", "needed" → High
- "would be nice", "if time allows" → Medium/Low
- Deadlines <1 week → High
- No deadline mentioned → Medium

### Step 4: Extract Decisions

**Decision indicator patterns:**
- "Decided to...", "We'll go with..."
- "Agreement reached:", "Consensus:"
- "Final decision:", "Resolved:"
- "Approved:", "Rejected:"

**Extract structure:**
```json
{
  "decisions": [
    {
      "decision": "Use FastAPI instead of Flask for backend",
      "rationale": "Better async support and performance",
      "decided_by": "John Doe",
      "decided_at": "2026-01-10",
      "mentioned_at": "Line 78-82",
      "impacts": ["Backend architecture", "Development timeline"]
    }
  ]
}
```

### Step 5: Extract Discussion Points

**Look for:**
- Topic headings: "## Authentication Discussion"
- Agenda items: "1. Review requirements"
- Questions raised: "Open question: How to handle..."
- Concerns mentioned: "Risk identified:", "Blocker:"

**Extract structure:**
```json
{
  "discussion_points": [
    {
      "topic": "Authentication Architecture",
      "summary": "Discussed OAuth2 vs JWT approaches, decided on OAuth2",
      "key_points": [
        "OAuth2 provides better third-party integration",
        "JWT simpler but less flexible",
        "Need to support Google and Microsoft SSO"
      ],
      "open_questions": ["How to handle token refresh?"],
      "risks_identified": ["Token expiration handling complexity"]
    }
  ]
}
```

### Step 6: Generate Structured Output

**Output format:**
```markdown
# Meeting Analysis: [Meeting Title]

**Date:** [Meeting Date]
**Duration:** [If available]
**Transcript Source:** [File location]

---

## Participants

| Name | Role | Responsibility | Email |
|------|------|----------------|-------|
| John Doe | Product Owner | Requirements & Decisions | john@example.com |
| Sarah Miller | Lead Developer | Technical Implementation | sarah@example.com |

---

## Tasks & Action Items (X total)

### High Priority (X tasks)

1. **Design authentication flow** ← Sarah Miller
   - Due: 2026-01-15
   - Description: Create wireframes for OAuth2 login process
   - Context: Security requirements discussion (Line 42-45)

2. **Setup Azure OpenAI environment** ← DevOps Team
   - Due: 2026-01-12
   - Description: Configure API keys and test endpoints
   - Context: Infrastructure planning (Line 95-98)

### Medium Priority (X tasks)
...

### Unassigned Tasks (X tasks)
- [ ] Review competitive analysis document
- [ ] Schedule follow-up meeting for Phase 2

---

## Decisions Made (X total)

1. **Technology Stack**
   - Decision: Use FastAPI instead of Flask
   - Rationale: Better async support and performance
   - Decided by: John Doe
   - Impacts: Backend architecture, development timeline

2. **Timeline Adjustment**
   - Decision: Extend Phase 1 by 2 weeks
   - Rationale: Additional requirements discovered
   - Decided by: Consensus
   - Impacts: Project timeline, resource allocation

---

## Key Discussion Points

### Authentication Architecture
- **Summary:** Evaluated OAuth2 vs JWT, decided on OAuth2
- **Key Points:**
  - OAuth2 provides better third-party integration
  - Need to support Google and Microsoft SSO
  - Security compliance requirements met
- **Open Questions:** How to handle token refresh on mobile?
- **Risks:** Token expiration handling complexity

### Budget & Resources
...

---

## Follow-up Items

- [ ] Sarah to circulate authentication wireframes by Friday
- [ ] John to get budget approval from CFO
- [ ] Schedule Phase 2 kickoff meeting (Week of Jan 20)
- [ ] All team members review and comment on technical spec

---

## Timeline & Deadlines

| Task | Owner | Due Date | Priority |
|------|-------|----------|----------|
| Design authentication flow | Sarah Miller | 2026-01-15 | High |
| Setup Azure environment | DevOps | 2026-01-12 | High |
| Review competitive analysis | Unassigned | 2026-01-20 | Medium |

---

## Archon Integration Ready

**Project:** [Auto-detect or ask user]
**Tasks to create:** X tasks identified
**Assignees mapped:** X participants

**Command to create tasks:**
```bash
# Review above tasks, then run:
# mcp__archon__manage_task("create", project_id="...", ...)
```

---

## Notion Integration Ready

**Database:** Projects or Tasks
**Pages to create:** X action items + 1 meeting summary page

**Recommended structure:**
- Meeting Summary Page (parent)
  - Task 1 (child)
  - Task 2 (child)
  - ...
```

---

### Step 7: Offer Next Actions

After generating the analysis, ask user:

**Option 1: Create Archon Tasks**
> "I've identified X tasks. Would you like me to create them in Archon now? I'll need the project_id."

**Option 2: Create Notion Pages**
> "I can create a meeting summary page in Notion with all tasks. Should I proceed?"

**Option 3: Save Analysis**
> "Would you like me to save this analysis as a markdown file for your records?"

**Option 4: Generate PRP Section**
> "These tasks could feed into a PRP. Should I create a requirements section based on this meeting?"

## Examples

### Example 1: Simple Action Items Meeting

**User request:**
```
"Analyze the transcript in data/transcripts/kickoff-2026-01-10.txt"
```

**Expected process:**
1. Read file `data/transcripts/kickoff-2026-01-10.txt`
2. Extract participants (look for "Attendees:", speaker labels)
3. Identify action items (look for "ACTION:", "TODO:", "[Name] will...")
4. Extract deadlines ("by Friday", "end of week", specific dates)
5. Map tasks to assignees
6. Generate structured markdown output
7. Offer to create Archon tasks or Notion pages

**Sample output:**
```markdown
# Meeting Analysis: Project Kickoff

**Participants:** 5 (John Doe - PM, Sarah Miller - Dev Lead, ...)
**Tasks Identified:** 8 (4 High, 3 Medium, 1 Low)
**Decisions Made:** 3
**Open Questions:** 2
```

### Example 2: Technical Discussion with Decisions

**User request:**
```
"Extract decisions and tasks from our architecture meeting notes"
```

**Expected process:**
1. Locate most recent transcript (ask if multiple found)
2. Focus on decision patterns ("decided", "agreed", "consensus")
3. Extract technical decisions with rationale
4. Identify implementation tasks resulting from decisions
5. Map decisions to impacted components/tasks
6. Generate decision log format

**Sample output:**
```markdown
## Decisions Made

1. **Use FastAPI instead of Flask**
   - Rationale: Async support, better performance
   - Impacts: Backend rewrite, timeline +2 weeks
   - Resulting tasks:
     - Migrate existing endpoints to FastAPI
     - Update deployment configuration
```

### Example 3: Multi-Speaker Transcript

**User request:**
```
"Who said what in the requirements meeting? Extract responsibilities."
```

**Expected process:**
1. Read transcript with speaker labels
2. Map speakers to roles (if mentioned or inferable)
3. Extract statements per speaker
4. Identify who committed to what
5. Generate responsibility matrix
6. Highlight conflicts or unclear assignments

**Sample output:**
```markdown
## Participant Contributions & Responsibilities

**John Doe (Product Owner):**
- Commitments: Finalize requirements by Friday, get budget approval
- Decisions made: Approved OAuth2 approach, extended timeline
- Open questions raised: "How to handle offline mode?"

**Sarah Miller (Lead Developer):**
- Commitments: Design authentication flow, setup dev environment
- Concerns raised: "Token refresh complexity", "Testing coverage"
- Suggestions: Use pytest for testing, implement CI/CD early
```

### Example 4: Extract for PRP Generation

**User request:**
```
"Use this meeting to create INITIAL.md requirements section"
```

**Expected process:**
1. Analyze transcript for requirements
2. Extract functional requirements from decisions
3. Identify technology stack mentions
4. Map participants to project roles/resources
5. Extract timeline/deadline information
6. Identify risks mentioned
7. Generate INITIAL.md format output

**Sample output:**
```markdown
## FUNKTIONALE ANFORDERUNGEN (from Meeting 2026-01-10)

### 1. Authentication System (Priority: CRITICAL)
**Source:** Architecture discussion, decided by John Doe
**Anforderungen:**
- OAuth2 integration with Google and Microsoft
- Token refresh mechanism
- Session management

**Akzeptanzkriterien:**
- Support 100+ concurrent users
- Token refresh < 500ms
- 99.9% uptime

**Risks:**
- Token expiration handling complexity (raised by Sarah)
```

## Error Handling

### File Not Found
```
❌ Transcript file not found at: data/transcripts/meeting.txt

Options:
1. Check if file exists in a different location
2. Ask user to provide correct path
3. List available transcripts in data/transcripts/
```

### No Tasks Identified
```
⚠️  No clear action items found in transcript.

This could mean:
- Meeting was purely informational
- Action items not explicitly stated
- Transcript format unclear

Recommendation: Ask user if they'd like me to:
1. Extract discussion points instead
2. Look for implicit tasks ("we should...", "need to...")
3. Generate summary without tasks
```

### Ambiguous Assignments
```
⚠️  Task "Review requirements" mentioned but no clear assignee.

Found mentions:
- Line 42: "Someone should review requirements"
- Line 78: "Requirements need review before Friday"

Action: Mark as "Unassigned" and flag for user to clarify.
```

### Multiple Transcript Formats
```
ℹ️  Detected Zoom auto-transcript format (timestamps, speaker IDs).

Adjusting parsing:
- Using timestamps for chronology
- Mapping numeric speaker IDs to names (if directory available)
- Preserving original line numbers for reference
```

## Success Criteria

✅ **Complete Analysis:**
- All participants identified with roles
- All explicit tasks extracted and mapped
- All decisions documented with context
- Timeline and deadlines captured

✅ **Actionable Output:**
- Tasks ready to create in Archon or Notion
- Clear assignees for each task
- Priorities inferred or explicit
- No ambiguous or orphaned tasks

✅ **Structured Format:**
- Consistent markdown formatting
- Tables for easy reading
- Reference to original transcript lines
- Ready for PRP integration or project planning

✅ **User Satisfaction:**
- User confirms analysis is accurate
- Next actions clear (create tasks, save file, etc.)
- No manual re-parsing needed

## Integration with Other Workflows

### With Archon Task Management
After analysis, offer to create tasks:
```python
# Example task creation
for task in extracted_tasks:
    mcp__archon__manage_task(
        "create",
        project_id=user_specified_project,
        title=task["title"],
        description=task["description"],
        assignee=task["assigned_to"],
        status="todo",
        task_order=task["priority_score"]
    )
```

### With PRP Generation
Feed meeting outcomes into INITIAL.md:
- Requirements → FUNKTIONALE ANFORDERUNGEN
- Participants → RESSOURCEN (Team section)
- Risks mentioned → RISIKEN
- Decisions → Technology Stack or Architecture

### With Notion Project Planning
Create meeting summary page with sub-tasks:
```
Meeting Summary Page
├── Task 1: Design auth flow (assigned: Sarah)
├── Task 2: Setup Azure (assigned: DevOps)
└── Decision Log
```

## Advanced Features

### Pattern Recognition
- **Implicit tasks:** "We need to..." → Extract as task
- **Deadlines:** "by Friday", "end of month", "Q1" → Parse to dates
- **Priorities:** Urgency keywords → Auto-assign priority
- **Dependencies:** "After X is done, Y should..." → Map dependencies

### Multi-Meeting Analysis
If user provides multiple transcripts:
- Compare tasks across meetings
- Track decision evolution
- Identify recurring themes
- Build comprehensive task backlog

### Speaker Sentiment Analysis (Optional)
- Detect concerns: "I'm worried about...", "This is risky..."
- Identify enthusiasm: "Great idea!", "This will really help..."
- Flag conflicts: Multiple opinions on same decision

## Troubleshooting

**Issue:** Transcript has no clear structure (wall of text)

**Solution:**
- Use paragraph breaks as topic separators
- Look for question marks as discussion points
- Extract any capitalized phrases as potential topics
- Ask user to provide context or agenda

**Issue:** Names misspelled or inconsistent

**Solution:**
- Use fuzzy matching (e.g., "John" = "Jon")
- Build name mapping as you parse
- Ask user to confirm participant list

**Issue:** Very long transcript (10,000+ words)

**Solution:**
- Process in chunks (by topic/time)
- Summarize less critical sections
- Focus on task extraction first, details second
- Offer to create separate analysis per section

---

**Skill Location:** `.claude/skills/meeting-transcript-analyzer/`
**Auto-activated when:** User mentions meeting transcripts, action items, or references transcript files
**Next steps:** Just ask me to "analyze the meeting transcript" or reference a file!
