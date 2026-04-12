# Q — The Conscience

Q is a lightweight, always-on code conscience. Not a team. One voice.

It watches your code changes and speaks up when something is wrong — based on a knowledge base that gets smarter every time you respond.

---

## What Q Does

- **Judges code changes** against a set of rules (security, architecture, testing, performance, error handling)
- **Speaks up** when something is wrong. Stays silent when it isn't.
- **Learns** from your feedback — overrides and confirmations update its knowledge base permanently
- **Runs two ways**: always-on in VS Code (no API key — uses your Copilot subscription), or on-demand in Copilot Chat

---

## Two Modes

### Mode 1 — Copilot Chat (On-Demand)

Open GitHub Copilot Chat in VS Code and invoke Q:

```
Q, review my last change to auth.py
```

Q loads your learned exceptions, applies its embedded rules, and returns a verdict in 3–5 seconds. One tool call. No round-trips loading domain docs.

**Respond to a verdict:**
- `[Q-ACCEPT]` — confirms the flag is correct (Q reinforces the rule)
- `[Q-OVERRIDE: reason]` — dismisses the flag (Q won't re-flag this pattern)

q-memory updates `knowledge_base/learned/q-learned.md` automatically.

### Mode 2 — VS Code Extension (Always-On, No API Key)

Install Q as a VS Code extension once. After that it fires automatically on every file save — no terminal, no API key, no background process. Uses your existing GitHub Copilot subscription.

```
Q: ◦   status bar idle
Q: ⟳   checking a saved file
Q: ● P1  verdict waiting for your response
```

When a violation is found, a notification pops up:

```
Q 🟠 [SEC-001] auth.py: api_key assigned a string literal on line 42
[That's wrong]  [That's fine]  [Teach Q]
```

Responding updates `q-learned.md` so Q never flags the same dismissed pattern again.

**Install:**
```bash
python scripts/install-extension.py
```
Restart VS Code. `Q: ◦` appears in the status bar. Open any project with a `q-config.json` and Q is live.

**Other commands:**
```bash
python scripts/install-extension.py --status   # check if installed
python scripts/install-extension.py --remove   # uninstall
```

---

## Setup

### 1. Install the VS Code extension (always-on, no API key needed)

```bash
python scripts/install-extension.py
```

Restart VS Code. Q loads automatically from that point forward. No terminal to keep open, no API key.

**Requirements**: VS Code 1.90+, GitHub Copilot extension installed and signed in.

### 2. Add GitHub Actions secret (optional — for CI checks on push/PR)

In repo Settings → Secrets → Actions: add `ANTHROPIC_API_KEY`. Skip this if you only want local checking via the extension.

### 3. Configure Q

Edit `q-config.json` to tune sensitivity, watched file types, and model selection.

| Setting | Default | Description |
|---------|---------|-------------|
| `sensitivity` | `normal` | `strict` / `normal` / `quiet` / `silent` |
| `mode` | `normal` | `normal` (full rules) or `fast` (P0/P1 only) |
| `watched_extensions` | `.py .ts .js .go...` | File types Q watches |
| `p3_silent` | `true` | P3 observations never interrupt |

### 4. Validate KB structure

```bash
python scripts/q-validate.py
```

Should output: `Q validation passed.`

---

## Priority Levels

| Level | Meaning | Action |
|-------|---------|--------|
| P0 | Critical — never merge | Blocks CI; immediate attention |
| P1 | Significant risk | Should fix before merge |
| P2 | Code quality concern | Worth fixing, not blocking |
| P3 | Observation | Logged silently, never shown |

---

## Agents

| Agent | Role | Invoke |
|-------|------|--------|
| `q` | The conscience — makes all judgments | `@q` in Copilot Chat |
| `q-memory` | Record keeper — updates KB after feedback | Triggered by Q automatically |
| `q-fast` | Fast mode — P0/P1 only | `@q-fast` or `"mode": "fast"` in config |

---

## Knowledge Base

```
knowledge_base/
├── domains/          ← Rules (security, architecture, testing, performance, error-handling)
├── learned/          ← Your feedback history (q-learned.md — grows over time)
└── verdicts/         ← Verdict registry (every judgment logged here)
```

To add or modify rules, edit the relevant domain file. Then update the matching rule block in `.github/agents/q.agent.md` (Copilot Chat reads from there at runtime).

See [PLAYBOOK.md](PLAYBOOK.md) for the full protocol.

---

## Scripts

```bash
# Judge a specific file
python scripts/q-judge.py --file path/to/file.py

# Judge all files changed since last commit (CI mode)
python scripts/q-judge.py --diff

# Fast mode (P0/P1 only)
python scripts/q-judge.py --diff --fast

# Close a verdict after responding
python scripts/q-learn.py --verdict-id <id> --response accept
python scripts/q-learn.py --verdict-id <id> --response override --reason "explanation"

# Validate KB structure
python scripts/q-validate.py
```

---

## Relationship to Team-Building

Q is the conscience extracted from the team-building framework. Team-building has 13 agents and a full 4-phase orchestration cycle — it is designed for complex missions. Q has 3 agents and one job: watch changes and flag what's wrong. No orchestration. No parallel dispatch. No mission lifecycle.

Q shares team-building's KB discipline: every judgment that receives user feedback must close the learning loop before it is considered final. The `[Q-LEARNED]` signal quality standard is the same as team-building's `[KB-UPDATED]` standard — specific, verifiable, not generic.
