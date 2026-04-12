# Team-Approved Exceptions

**Owner**: team (requires PR to modify)  
**Last Updated**: 2026-04-12  
**Governance**: Any change to this file requires a PR reviewed by at least one other developer. See [docs/rule-governance.md](../../../docs/rule-governance.md).

> These exceptions apply to **every developer on the team**. Q will not flag
> these patterns for anyone. To add an exception, open a PR using the
> rule-proposal template. To add a personal exception (just for you), run
> `python scripts/q-learn.py` — that writes to your local `knowledge_base/personal/`
> which is gitignored.

---

## Accepted Exceptions

_No team exceptions yet. Added via PR after team review._

---

## Exception Format

When a PR is merged adding an exception, it follows this format:

```markdown
### YYYY-MM-DD — <rule-id> — <pattern description>
**Approved by**: @reviewer
**Reason**: Why this pattern is acceptable for our codebase.
**Scope**: Where this exception applies (e.g., all test files, specific directory).
**Pattern**: The specific thing Q should not flag.
```

---

## Retired Exceptions

_Exceptions removed after review (pattern no longer valid or rule changed)._
