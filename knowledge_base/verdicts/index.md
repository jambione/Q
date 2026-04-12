# Q Verdict Registry

**Owner**: q  
**Last Updated**: 2026-04-12

> All Q verdicts are logged here. q-judge.py appends rows in silent mode.
> q (Copilot Chat mode) appends rows via the Edit tool.
> q-validate.py checks this file is well-formed.

---

## Verdict Log

| Date | Verdict ID | File | Rule | Severity | Message | Outcome | Mode |
|------|------------|------|------|----------|---------|---------|------|
| — | — | — | — | — | — | — | — |

_No verdicts yet._

---

## Outcome Key

| Outcome | Meaning |
|---------|---------|
| `flagged` | Verdict issued, awaiting user response |
| `accepted` | User responded [Q-ACCEPT] — confirmed as wrong |
| `overridden` | User responded [Q-OVERRIDE] — dismissed with reason |
| `clean` | No violation detected |
| `skipped` | File excluded by config or sensitivity setting |
