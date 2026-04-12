# Q Rule Proposal

Use this template when proposing a new rule, modifying an existing rule, retiring a rule, or promoting a personal exception to a team exception.

---

## Type of Change

- [ ] New rule
- [ ] Modify existing rule (change severity, refine pattern, add exception)
- [ ] Retire rule (remove — with justification)
- [ ] Promote personal exception → team exception
- [ ] Add team exception (suppress a false positive for the whole team)

---

## Rule / Exception Summary

**Rule ID** (new rules: propose an ID following the pattern `DOM-NNN`):

**Domain** (security / architecture / testing / performance / error-handling):

**Proposed Severity** (P0 / P1 / P2 / P3):

**One-line summary**:

---

## Pattern Description

What code pattern should Q flag?

```
# Example of code that SHOULD trigger this rule
```

```
# Example of code that should NOT trigger (exception/safe pattern)
```

---

## Why This Matters

Explain the real risk or value. Link to incidents, post-mortems, or production issues if applicable.

---

## Exceptions

List any patterns that should explicitly NOT be flagged by this rule:

- [ ] Test fixtures
- [ ] Generated code
- [ ] Specific file paths: `______`
- [ ] Other: `______`

---

## KB Doc Update

Which domain doc will be updated?

- [ ] `knowledge_base/domains/security.md`
- [ ] `knowledge_base/domains/architecture.md`
- [ ] `knowledge_base/domains/testing.md`
- [ ] `knowledge_base/domains/performance.md`
- [ ] `knowledge_base/domains/error-handling.md`

Paste the exact block you're adding/modifying below:

```markdown
## RULE-ID: Rule Name

**Severity**: P?
**Pattern**: ...
**Exceptions**: ...
```

---

## For Team Exceptions (promoting personal → team)

If promoting a personal exception to the team tier:

**Original personal exception** (paste the entry from your `q-learned.md`):

**Why the whole team should share this exception**:

**Risks of sharing** (could this mask real violations for others?):

---

## Reviewer Checklist

- [ ] Pattern is clearly defined — not ambiguous
- [ ] Severity is calibrated (P0 = never merge, P1 = fix before merge, P2 = quality, P3 = silent)
- [ ] At least one real example exists (not just hypothetical)
- [ ] Exceptions are specific enough to avoid suppressing real violations
- [ ] `knowledge_base/index.md` rule table updated
- [ ] `python scripts/q-validate.py` passes after change
