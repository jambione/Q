# Q Conscience Protocol — PLAYBOOK

> This is Q's operating protocol. It defines how judgments are made, how the learning
> loop closes, and how the two modes (Copilot Chat and silent hook) interact.

---

## Overview

Q is a conscience, not a team. One voice. Two modes. One KB.

| Mode | Trigger | Agent | Speed | Learning |
|------|---------|-------|-------|---------|
| **Copilot Chat** | User invokes Q manually | q.agent.md | 3–5s | q-memory via Edit tool |
| **Silent Hook** | Claude Code PostToolUse fires | q-judge.py script | ~2s | q-learn.py script |

Both modes share `knowledge_base/learned/q-learned.md` and `knowledge_base/verdicts/index.md`.

---

## Mode 1: Copilot Chat — Judgment Cycle

```
STEP 1: OBSERVE
  User: "Q, review auth.py" or pastes a diff
  Q emits: [Q-OBSERVING: <file>]
  Q reads: knowledge_base/learned/q-learned.md  ← only dynamic file read

STEP 2: JUDGE
  Q applies embedded rules (in q.agent.md) against the change
  Q cross-references q-learned.md for granted exceptions
  
  If violation found:
    [Q-VERDICT: <P0|P1|P2|P3> | <file> | <rule-id> | one-sentence message]
    
  If clean:
    [Q-CLEAN: <file> | no violations detected]

STEP 3: USER RESPONSE
  [Q-ACCEPT]             ← confirms the flag was correct
  [Q-OVERRIDE: reason]   ← user explains why it's OK (reason required)

STEP 4: LEARN
  Q emits: [Q-SYNTHESIZE: <verdict-id>]
  q-memory activates (triggered by Q-SYNTHESIZE signal)
  q-memory reads q-learned.md
  q-memory writes the entry (Edit tool)
  q-memory emits: [Q-LEARNED: q-learned.md | <specific content description>]
  q-memory emits: [Q-VERDICT-CLOSED: <verdict-id>]
```

**Performance**: 1 tool call (q-learned.md) + reasoning. Target: 3–5 seconds.

---

## Mode 2: Silent Hook — Judgment Cycle

```
TRIGGER: Claude Code PostToolUse fires on Edit or Write tool call
  → python scripts/q-judge.py --file <path>

STEP 1: FILTER
  q-judge.py checks q-config.json:
  - Is the file extension in watched_extensions?
  - Does the path match any exclude_patterns?
  - If excluded: exit 0 silently

STEP 2: DIFF
  q-judge.py runs: git diff HEAD -- <file>
  Truncates to max_diff_lines (default: 300)

STEP 3: KB LOAD
  Keyword-match diff against DOMAIN_KEYWORDS table
  Load matching domain docs from knowledge_base/domains/
  Load knowledge_base/learned/q-learned.md

STEP 4: JUDGE
  Call Claude API (urllib.request, no SDK)
  System prompt: static, cached (prompt-caching-2024-07-31 beta)
  User prompt: KB context + learned exceptions + diff

STEP 5: OUTPUT
  If flagged (and sensitivity_allows):
    Print verdict to terminal:
      [Q] 🔴 P0 [SEC-001] — auth/config.py
          api_key assigned a string literal on line 42
          Verdict ID: 20260412-143022-auth-config-py
          Respond: [Q-ACCEPT] to confirm | [Q-OVERRIDE: reason] to dismiss
    Append row to knowledge_base/verdicts/index.md
    Exit 1 (non-zero signals CI failure for P0/P1)
    
  If clean:
    Exit 0 silently (no terminal output)

STEP 6: USER RESPONSE (optional)
  python scripts/q-learn.py \
    --verdict-id 20260412-143022-auth-config-py \
    --response override \
    --reason "test fixture, not a real credential"
    
  q-learn.py appends to q-learned.md
  q-learn.py prints: [Q-LEARNED: q-learned.md | Accepted exception: ...]
  q-learn.py prints: [Q-VERDICT-CLOSED: <verdict-id>]
```

**Performance**: Direct API call, no tool call overhead. Target: ~2 seconds.

---

## Priority Protocol

| Level | Meaning | Copilot Chat | Silent Hook | CI Gate |
|-------|---------|-------------|-------------|---------|
| P0 | Critical — never merge | States clearly in chat | Terminal error, exit 1 | Fails build |
| P1 | Fix before merge | Warning in chat | Terminal warning, exit 1 | Fails build |
| P2 | Quality concern | Advisory in chat | Terminal advisory, exit 0 | Passes build |
| P3 | Silent observation | Logged only | No output (p3_silent: true) | Passes build |

P3 is always silent. P0 is always loud. P1/P2 behavior controlled by `q-config.json` sensitivity.

**Sensitivity settings** (`q-config.json` → `sensitivity`):
- `strict`: Surface P3 and above
- `normal`: Surface P2 and above (default)
- `quiet`: Surface P1 and above
- `silent`: Surface P0 only

---

## KB Update Protocol

Same enforcement discipline as team-building. Every verdict the user responds to must close the learning loop before the verdict is considered final.

```
User responds → Q emits [Q-SYNTHESIZE: <id>] → q-memory updates q-learned.md
             → q-memory emits [Q-LEARNED: <doc> | <specific content>]
             → q-memory emits [Q-VERDICT-CLOSED: <id>]
```

**Quality standard for [Q-LEARNED] signal**:

INVALID: `[Q-LEARNED: q-learned.md | updated learned doc]`

VALID: `[Q-LEARNED: q-learned.md | Added SEC-001 exception: test fixture passwords in paths matching tests/fixtures/ are acceptable — pattern confirmed by 3 user overrides]`

The description must name the rule, the pattern, and the source.

---

## Signal Reference

| Signal | Direction | Meaning |
|--------|-----------|---------|
| `[Q-OBSERVING: <file>]` | Q → User | Q is loading context and preparing to judge |
| `[Q-VERDICT: P? \| file \| rule \| msg]` | Q → User | Violation found |
| `[Q-CLEAN: <file> \| reason]` | Q → User | No violations |
| `[Q-ACCEPT]` | User → Q | Confirms flag is correct |
| `[Q-OVERRIDE: reason]` | User → Q | Dismisses flag, provides reason |
| `[Q-SYNTHESIZE: <verdict-id>]` | Q → q-memory | Triggers learning write |
| `[Q-LEARNED: <doc> \| <content>]` | q-memory → Q | Learning written, confirms specific content |
| `[Q-VERDICT-CLOSED: <id>]` | q-memory → Q | Verdict finalized, loop complete |
| `[Q-FAST-NOTE: <file> \| note]` | q-fast → User | Possible P2 concern, suggests full review |

---

## Agents

| Agent | Role | Invoked By | Writes KB? |
|-------|------|-----------|-----------|
| `q` | Conscience — makes all judgments | User (Copilot Chat) | No |
| `q-memory` | Record Keeper — updates q-learned.md | Q's `[Q-SYNTHESIZE]` signal | Yes — only q-learned.md |
| `q-fast` | Fast mode — P0/P1 only | User or config mode=fast | No |

---

## Scripts

| Script | Mode | Invoked By |
|--------|------|-----------|
| `scripts/q-judge.py --file <path>` | Silent hook | Claude Code PostToolUse hook |
| `scripts/q-judge.py --diff` | CI | GitHub Actions q-judge.yml |
| `scripts/q-learn.py` | Both | User manually, or q-learn.yml via PR comment signal |
| `scripts/q-validate.py` | CI | GitHub Actions q-validate.yml |

---

## Adding New Rules

To add a new rule:

1. Add a rule block to the appropriate `knowledge_base/domains/*.md` file following the existing format (Rule ID, Severity, Pattern, Keywords, Exceptions)
2. Add the rule to the **Embedded Rules** section in `.github/agents/q.agent.md` — this is what the Copilot Chat agent reads
3. Add the rule ID to the Rule ID Reference table in `knowledge_base/index.md`
4. Run `python scripts/q-validate.py` to confirm the KB is well-formed

Both the domain doc and the agent file must stay in sync. The domain doc is the source of truth for humans and the silent-mode script. The agent file is the source of truth for Copilot Chat Q.
