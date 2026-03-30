---
name: session-wrapup
description: >
  USE THIS only when the user's message clearly signals they are done working for now. Concrete signals:
  - Explicit end phrases: "세션 종료", "오늘 마무리", "wrap up", "끝내자", "다 됐어"
  - Commit requests tied to finishing: "커밋하고 끝내줘", "커밋 후 정리해줘", "오늘 작업 커밋해줘"
  - Knowledge-save requests: "오늘 배운 거 저장해줘", "CLAUDE.md 업데이트해줘"

  DO NOT USE when:
  - the user just says "커밋해줘" in the middle of a task (mid-session commit → use plain git commit instead)
  - the user says "thanks" or "good" without any end-of-session signal
  - the user is asking a question or requesting more code

  In short: run this only when the user is closing out the current work session, not just saving progress mid-task.
---

# Session Wrap-up & Knowledge Persistence

> Run only when the user explicitly ends the session. Execute steps C1–C6 in order.

## Steps

### C1 — Summarize Changes
```
ACTION : List all files modified this session.
         Group related changes into logical commit units.
OUTPUT : Proposed commit groups with file lists and intent.
```

### C2 — Pre-commit Quality Gate
```
IF architecture-review or security-audit was NOT run this session:
  Run both now before proceeding to C3.
```

### C3 — Git Commit
```
ACTION : For each commit group from C1:
           git add <files>
           git commit -m "<type>(<scope>): <summary>"

Commit message types : feat | fix | refactor | docs | test | chore
Example             : feat(auth): add JWT refresh logic
```

### C4 — Extract New Knowledge
```
Scan the session for items in these four categories:

CATEGORY               | WHAT TO LOOK FOR
-----------------------|--------------------------------------------------
Business Edge Cases    | Conditions that required special-case handling
Architecture Decisions | "Why this approach" agreements made this session
Recurring Fix Patterns | Any code pattern corrected more than once
External System Quirks | Non-obvious behavior of integrated APIs / DBs / libs

IF any item found : Proceed to C5.
IF nothing new    : Skip C5, go to C6.
```

### C5 — Update CLAUDE.md
```
ACTION : Read the project-root CLAUDE.md.
         IF file does not exist : Create it with the skeleton below.
         Append new knowledge under the matching section.
         Do NOT delete or overwrite existing content.
         End each new entry with: <!-- added: YYYY-MM-DD -->

SKELETON (use only when creating a new file):
---
# Project Context

## Architecture Decisions

## Business Rules & Edge Cases

## Recurring Patterns to Avoid

## External System Quirks
---
```

### C6 — Final Report
```
Report to user (concise, bullet list):
  - Commits created  : <hash> <message>
  - CLAUDE.md        : <N> entries added to sections <names>
  - Caution for next session : <item>  (omit line if nothing to note)
```
