---
name: security-audit
description: >
  USE THIS before showing any code output to the user, when the code you just wrote touches at least one of:
  - user input (form fields, query params, request body, file uploads)
  - database queries or ORM calls
  - HTML rendering or DOM manipulation
  - external API calls or webhook handlers
  - authentication, sessions, tokens, or credentials
  - logging statements

  DO NOT USE when:
  - the code is pure in-memory logic with no I/O boundary (e.g., a sorting algorithm, a math utility)
  - you only changed comments, types, or whitespace

  In short: run this whenever new code crosses a trust boundary (user → app, app → DB, app → HTML).
---

# Security & Accessibility Audit

> Run silently before delivering any code to the user. Fix violations in place. Only surface to the user if a fix is impossible.

## Frontend Checks  *(skip entire section if no frontend code)*

### B1 — ARIA Correctness
```
ACTION : Find all role and aria-* attributes in new/changed markup.
IF unnecessary ARIA exists : Replace with equivalent native HTML element
                             (<button>, <nav>, <main>, <header>, etc.).
IF ARIA is spec-compliant and required : Pass.
```

### B2 — Keyboard Navigation
```
ACTION : Trace the tab order through changed components.
         Check that dynamically rendered content has aria-live or aria-atomic where needed.
IF focus order is illogical : Fix tabindex values.
IF dynamic content lacks live region : Add aria-live="polite" or aria-atomic="true".
IF clean : Pass.
```

### B3 — Alt Text & Color Contrast
```
ACTION : Find all <img> tags without alt attribute.
IF missing alt : Add meaningful alt text (decorative images use alt="").
IF color values are present in CSS : Verify text/background contrast ratio ≥ 4.5:1 (WCAG AA).
IF clean : Pass.
```

## Backend Checks

### B4 — SQL Injection
```
ACTION : Search for string concatenation patterns that include user input in SQL queries.
         Pattern: query = "SELECT ... " + userInput
                  query = `SELECT ... ${userInput}`
IF found : Replace with parameterized query / prepared statement.
IF not found : Pass.
```

### B5 — XSS
```
ACTION : Search for innerHTML, dangerouslySetInnerHTML, document.write, or eval
         containing user-supplied or external data.
IF found : Apply escaping or DOMPurify sanitization before insertion.
IF not found : Pass.
```

### B6 — Log Injection
```
ACTION : Search for log statements that write raw user input.
IF found : Escape \n and \r characters, or switch to structured logging.
IF not found : Pass.
```

### B7 — Hardcoded Secrets
```
ACTION : Search for API keys, passwords, and tokens hardcoded in source files.
         Also check if sensitive data appears in response bodies.
IF found : Move to environment variables. Remove from response payloads.
IF not found : Pass.
```

## Done Criteria
All seven checks pass **or** all violations are fixed before code is shown to the user.
