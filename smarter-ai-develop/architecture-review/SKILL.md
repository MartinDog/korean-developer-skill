---
name: architecture-review
description: >
  USE THIS before showing any code output to the user, when YOU (the AI) have just:
  - written a new function, class, or module
  - refactored or restructured existing code
  - added a new data access or I/O call

  DO NOT USE when:
  - you are only reading, explaining, or summarizing code (no code was written/changed)
  - you made a config-only change (env file, JSON config, etc.)
  - the change is a single-line typo or string fix with no logic involved

  In short: run this every time code logic changes hands from AI to user.
---

# Architecture & Quality Review

> Run silently before delivering any code to the user. Fix violations in place. Only surface to the user if a fix is impossible.

## Checks

### A1 — Duplicate Detection
```
ACTION : Grep codebase for functions/classes with the same responsibility as what you just wrote.
IF found : Delete the new code. Reuse the existing one. Update all call sites.
IF not found : Pass.
```

### A2 — Single Responsibility Principle
```
ACTION : Check whether any single function or class handles more than one logical concern.
IF violation : Split into separate units. Update all call sites.
IF clean : Pass.
```

### A3 — Async/Sync Pattern Consistency
```
ACTION : Identify the async pattern used in the existing codebase
         (async/await | Promise | callback | synchronous).
         Check that every new DB call, API call, and file I/O matches that pattern.
IF mismatch : Rewrite new code to match the existing pattern.
IF consistent : Pass.
```

### A4 — N+1 Query Detection  *(skip if no DB code)*
```
ACTION : Search for DB queries executing inside loops (for / while / forEach / map).
IF found : Replace with a batch query or JOIN.
IF not found : Pass.
```

## Done Criteria
All four checks pass **or** all violations are fixed before code is shown to the user.
