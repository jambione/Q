# Q Onboarding Guide

> Q is your team's code conscience. It watches every file save, judges changes against a shared rulebook, and learns from your feedback. This guide gets you up and running in under 10 minutes.

---

## What Q Does

Q runs in two modes simultaneously:

| Mode | How it fires | Output |
|------|-------------|--------|
| **Silent Hook** | After every file save (Claude Code) | Terminal verdict — no interruption unless P0/P1 |
| **Copilot Chat** | When you ask Q directly | Conversational verdict with Q's... *theatrical* commentary |

Q flags violations against a shared rulebook. When Q is wrong, you tell it — and it remembers. Your dismissals stay local (gitignored); team-wide exceptions require a PR.

---

## Prerequisites

- Git repository with `q-config.json` in root (already present in this repo)
- One of:
  - **Claude Code** (for silent hook mode) — [claude.ai/code](https://claude.ai/code)
  - **GitHub Copilot** in VS Code (for extension mode)
  - **Both** (recommended)

---

## Setup: Silent Hook Mode (Claude Code)

Q hooks into Claude Code's `PostToolUse` event. Every `Edit` or `Write` tool call automatically triggers a judgment.

**Step 1** — Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
# Add to ~/.bashrc or ~/.zshrc to persist
```

**Step 2** — The hook is already wired in `.claude/settings.json`. Verify it's there:
```bash
cat .claude/settings.json
```

That's it. Open Claude Code, edit a file, and watch the terminal.

**Verify it works:**
```bash
python scripts/q-judge.py --file scripts/q-judge.py
```

---

## Setup: VS Code Extension Mode

Q runs as a plain JS extension — no build step, no npm install.

**Step 1** — Install via junction (no admin required on Windows):
```bash
python scripts/install-extension.py
```

**Step 2** — Reload VS Code (Ctrl+Shift+P → "Developer: Reload Window")

**Step 3** — Open a workspace that contains `q-config.json` (this repo)

The status bar shows `Q: ◦` when idle. Save any watched file to trigger a check.

**Manual review**: Click `Q: ◦` in the status bar or run `Q: Review Current File` from the command palette.

---

## Your Personal Exceptions (Local Only)

When Q flags something you've already reviewed and accepted, dismiss it:

**In Copilot Chat:**
```
[Q-OVERRIDE: test fixture — not a real credential]
```

**From the terminal (after a silent hook verdict):**
```bash
python scripts/q-learn.py \
  --verdict-id 20260412-143022-auth-py \
  --response override \
  --reason "test fixture"
```

Your dismissals are written to `knowledge_base/personal/q-learned.md`, which is gitignored. Q will not re-flag the same pattern for you again.

---

## Admitting Q Was Right

When Q catches something real:

**In Copilot Chat:**
```
[Q-ACCEPT]
```

**From the terminal:**
```bash
python scripts/q-learn.py \
  --verdict-id 20260412-143022-auth-py \
  --response accept
```

---

## Promoting a Pattern to Team-Wide Exception

If Q keeps flagging something that's genuinely fine for the whole team (e.g., a framework pattern it mistakes for a violation):

```bash
python scripts/q-learn.py \
  --verdict-id 20260412-143022-auth-py \
  --response override \
  --reason "Django's select_related is not an N+1 — it's a JOIN" \
  --team
```

This modifies `knowledge_base/team/exceptions/approved.md`, which is committed. **Open a PR** so the team can review before it merges.

---

## Tuning Your Sensitivity

Edit `q-config.json` in the repo root:

```json
{
  "sensitivity": "normal"
}
```

| Setting | What you see |
|---------|-------------|
| `strict` | P0 through P3 (everything) |
| `normal` | P0 through P2 (default — P3 silent) |
| `quiet` | P0 and P1 only |
| `silent` | P0 only (critical violations) |

`p3_silent: true` (default) means P3 observations are always logged but never interrupt you.

---

## Checking the Verdict History

```bash
# View all verdicts
cat knowledge_base/verdicts/index.md

# Generate a weekly digest
python scripts/q-report.py

# Last 30 days
python scripts/q-report.py --days 30

# Save to file
python scripts/q-report.py --output reports/my-report.md
```

---

## Validating the KB

```bash
python scripts/q-validate.py
```

Returns `0` if everything is healthy. Run this after editing any KB document.

---

## Common Questions

**Q keeps flagging something I've already dismissed.**
Your personal exception in `q-learned.md` should suppress it. If not, check that the file path or rule ID matches what Q is seeing. Run `python scripts/q-learn.py` again with `--file` and `--rule-id` for a more precise match.

**The silent hook isn't firing.**
Check that `ANTHROPIC_API_KEY` is set. Verify `.claude/settings.json` has the PostToolUse hook. Make sure the file extension is in `watched_extensions` in `q-config.json`.

**The VS Code extension shows `Q: ✕`.**
GitHub Copilot may not be signed in, or no Copilot model is available. Check the Copilot status bar icon.

**I want to propose a new rule.**
Open a PR using the `.github/PULL_REQUEST_TEMPLATE/rule-proposal.md` template. See `docs/rule-governance.md` for the full process.

---

## What Q Watches

By default, Q watches these extensions: `.py`, `.ts`, `.js`, `.go`, `.java`, `.cs`, `.rb`, `.php`, `.swift`, `.kt`

Q ignores: `node_modules`, `.git`, `dist`, `build`, `__pycache__`, `*.min.js`, `vendor`

To customize, edit `watched_extensions` and `exclude_patterns` in `q-config.json`.
