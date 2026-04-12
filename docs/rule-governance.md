# Q Rule Governance

> Rules in Q's knowledge base are shared contracts. They affect every developer on the team. This document defines how rules are proposed, reviewed, accepted, and retired.

---

## Philosophy

Q's rules exist to prevent real harm — not to enforce style, not to gatekeep opinions. Every rule must be justifiable by a concrete risk: security breach, data loss, production incident, or significant quality degradation. If you can't articulate the harm, the rule doesn't belong here.

Rules are maintained in `knowledge_base/domains/`. The rule table in `knowledge_base/index.md` is the authoritative registry.

---

## Rule Tiers

| Tier | Location | Who can change | Process |
|------|----------|---------------|---------|
| **Team rules** | `knowledge_base/domains/*.md` | Any developer | PR → 2 approvals → merge |
| **Team exceptions** | `knowledge_base/team/exceptions/approved.md` | Any developer | PR → 1 approval → merge |
| **Personal exceptions** | `knowledge_base/personal/q-learned.md` | You only | No review — local, gitignored |

---

## Proposing a New Rule

1. **Check for overlap** — Does an existing rule already cover this? Run `python scripts/q-validate.py` and search `knowledge_base/index.md`.

2. **Open a PR** using the rule proposal template:
   - From GitHub: New PR → select `.github/PULL_REQUEST_TEMPLATE/rule-proposal.md`
   - The template asks for: rule ID, pattern, severity, exceptions, and a real example

3. **Required for approval**:
   - At least one real incident or concrete harm motivating the rule
   - Clear false-positive boundaries (what explicitly should NOT be flagged)
   - The severity is calibrated against the scale below
   - `python scripts/q-validate.py` passes after your KB doc edit

4. **Approval threshold**: 2 team member approvals before merging

---

## Severity Calibration

| Level | Meaning | Examples |
|-------|---------|---------|
| **P0** | Never merge — immediate risk to security, data, or system integrity | Hardcoded credentials, disabled SSL |
| **P1** | Fix before merge — significant production risk | SQL injection, N+1 in hot path, resource leaks |
| **P2** | Quality concern — worth fixing, not blocking | God class, hardcoded config values, missing tests |
| **P3** | Observation — log silently, never interrupt | TODO in error handler, happy-path-only tests |

When in doubt, go lower (less severe). P0 is reserved for "merge this and we have a breach."

---

## Modifying an Existing Rule

Same process as adding a new rule — PR with the proposal template. Clearly state:
- What's changing (severity, pattern, exception list)
- Why the current rule is wrong or insufficient
- Whether any existing verdicts in `verdicts/index.md` would be reclassified

---

## Retiring a Rule

Rules should be retired when:
- The codebase no longer uses the affected technology
- The pattern has been superseded by a framework-level fix
- The false-positive rate makes the rule net-negative

Retirement PR must include:
- Reason for retirement
- A scan showing the rule has fired recently (proving we know what we're removing)
- Sign-off from the engineer who originally proposed it, if still on the team

---

## Team Exceptions vs. Personal Exceptions

**Personal exception** (no review needed):
You've dismissed a verdict for a reason that applies only to your context. Write it to your local `knowledge_base/personal/q-learned.md` via `q-learn.py` or the VS Code extension. No PR, no review.

**Team exception** (PR required):
The same pattern recurs for multiple developers, or the rule is firing on a shared pattern everyone has agreed is acceptable (e.g., a framework idiom Q misidentifies).

To promote a personal exception to team-wide:
```bash
python scripts/q-learn.py \
  --verdict-id <id> \
  --response override \
  --reason "Django select_related is not an N+1" \
  --team
```

This modifies `knowledge_base/team/exceptions/approved.md`. Open a PR. One approval required.

---

## Reviewing a Rule Proposal PR

As a reviewer, check:

1. **Is the harm real?** Ask for an incident, a CVE, or a concrete failure mode. "I read it's bad practice" is insufficient.
2. **Is the pattern specific enough?** Vague patterns produce false positives.
3. **Are exceptions adequate?** Test fixtures, generated code, and framework idioms are common false-positive sources.
4. **Is the severity calibrated?** Challenge P0 assignments — they block merges.
5. **Does `q-validate.py` pass?** Required before approving.

---

## KB Maintenance

**Monthly** (suggested):
- Run `python scripts/q-report.py --days 30` and review override rate by rule
- Rules with override rate > 50% are candidates for severity reduction or retirement
- Rules with 0 verdicts in 90 days may no longer be relevant

**Quarterly**:
- Review `knowledge_base/domains/*.md` for accuracy
- Archive verdicts older than 6 months (move to `verdicts/archive/`)
- Update rule descriptions if the codebase has changed

---

## Rule ID Assignment

New rules use the next available ID in their domain:

| Domain | Prefix | Current range |
|--------|--------|--------------|
| Security | SEC | SEC-001 to SEC-005 |
| Architecture | ARCH | ARCH-001 to ARCH-005 |
| Testing | TEST | TEST-001 to TEST-004 |
| Performance | PERF | PERF-001 to PERF-004 |
| Error Handling | ERR | ERR-001 to ERR-005 |

Claim the next ID in sequence. Rule IDs are never reused after retirement — retired rules are marked `[RETIRED: YYYY-MM-DD]` in `knowledge_base/index.md`.
