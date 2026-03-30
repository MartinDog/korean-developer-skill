---
name: smarter-ai-develop
description: >
  USE THIS when the situation matches any of the following, and you are unsure which sub-skill to invoke:
  - You just wrote or changed code AND the user is also closing the session in the same message
  - The user asks broadly for "코드 리뷰 후 마무리", "다 검토하고 커밋해줘", or similar all-in-one requests
  - You need a single entry point that decides which combination of checks to run

  For targeted use, prefer the sub-skills directly:
  - Code logic changed → architecture-review
  - Code touches user input / DB / HTML / auth → security-audit
  - User is ending the session → session-wrapup

  DO NOT USE this orchestrator when only one sub-skill clearly applies.
---

# Smarter AI Develop — Orchestrator

## Routing Logic

```
GIVEN the current context, evaluate all three conditions independently:

CONDITION 1 — Was code logic written or changed this turn?
  YES → run architecture-review

CONDITION 2 — Does the new code touch a trust boundary?
             (user input | DB query | HTML rendering | auth | logging)
  YES → run security-audit

CONDITION 3 — Did the user signal end of session?
             ("세션 종료" | "마무리" | "wrap up" | "끝내자" | "커밋하고 끝내줘")
  YES → run session-wrapup
       (session-wrapup re-checks conditions 1 and 2 internally if they were skipped)

Multiple YES answers → run matching skills in order: architecture-review → security-audit → session-wrapup
All NO              → do not invoke any sub-skill
```

## Sub-skills

| Skill | Trigger |
|---|---|
| [architecture-review](architecture-review/SKILL.md) | Code logic was written or restructured |
| [security-audit](security-audit/SKILL.md) | Code crosses a trust boundary |
| [session-wrapup](session-wrapup/SKILL.md) | User explicitly ends the session |
