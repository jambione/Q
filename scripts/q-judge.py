"""
q-judge.py — Q's core judgment engine.

Usage:
  python scripts/q-judge.py --file <path>   Judge a single file (hook mode)
  python scripts/q-judge.py --diff          Judge all changed files (CI mode)

Pure stdlib. No external dependencies. Calls Claude API via urllib.request.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Add scripts/ to path for config import
sys.path.insert(0, str(Path(__file__).parent))
from q_config import load_config, get_api_key, get_model, should_watch_file, sensitivity_allows, is_ci_gate, load_exceptions


# ──────────────────────────────────────────────────────────────
# KB domain routing: maps keywords in diff to domain doc files
# ──────────────────────────────────────────────────────────────

DOMAIN_KEYWORDS = {
    "security.md": [
        "password", "api_key", "secret", "token", "credential", "private_key",
        "auth", "SELECT", "INSERT", "UPDATE", "DELETE", "WHERE", "execute",
        "query", "cursor", "verify=False", "ssl", "chmod", "0777", "log",
        "console.log", "print", "logger",
    ],
    "architecture.md": [
        "import", "require", "from", "class", "model", "entity", "repository",
        "schema", "controller", "handler", "route", "view", "component",
        "http://", "https://", "timeout", "retry", "localhost",
    ],
    "testing.md": [
        "def test_", "it(", "describe(", "@Test", "@skip", "pytest.mark.skip",
        "xit(", "xdescribe", "it.skip", "test.skip", "assertRaises",
        "expect(", "toThrow",
    ],
    "performance.md": [
        "for ", "while ", "forEach", ".map(", ".each(", "append(", "push(",
        "extend(", "async def", "async function", "await", "json.dumps",
        "JSON.stringify", "open(", "requests.get", "urllib",
    ],
    "error-handling.md": [
        "except", "catch", "try", "finally", "raise", "throw",
        "return None", "return {}", "return []", "return False",
        "TODO", "FIXME", "HACK", "pass",
    ],
}


def get_relevant_domains(diff_text: str, kb_path: str) -> dict[str, str]:
    """Return {filename: content} for KB domain docs relevant to the diff."""
    diff_lower = diff_text.lower()
    relevant = {}

    domains_dir = Path(kb_path) / "domains"
    for domain_file, keywords in DOMAIN_KEYWORDS.items():
        if any(kw.lower() in diff_lower for kw in keywords):
            doc_path = domains_dir / domain_file
            if doc_path.exists():
                relevant[domain_file] = doc_path.read_text(encoding="utf-8")

    return relevant


def load_learned(config: dict) -> str:
    """Load combined team + personal exceptions. Returns empty string if no real entries."""
    return load_exceptions(config)


def build_system_prompt() -> str:
    return """You are Q, a code conscience. Your job is to make binary judgments about code changes.

RULES:
- Only flag violations explicitly defined in the KB rules provided.
- Never invent rules. Never flag based on style preferences not in the KB.
- Be terse. One sentence. The developer is in flow — interrupt only when it matters.
- Apply learned exceptions: if q-learned.md contains a matching override, do NOT flag.

RESPONSE FORMAT — respond ONLY with valid JSON, no other text:
{
  "flagged": true,
  "severity": "P0",
  "rule_id": "SEC-001",
  "message": "One sentence explanation for the developer.",
  "kb_excerpt": "Exact rule text that triggered this flag."
}

OR if nothing is wrong:
{
  "flagged": false
}

SEVERITY GUIDE:
- P0: Critical — never merge (security, data loss, disabled safety controls)
- P1: Significant risk — should fix before merge
- P2: Code quality concern — worth fixing, not blocking
- P3: Observation — log silently, never interrupt"""


def build_user_prompt(file_path: str, diff_text: str, domain_docs: dict, learned: str) -> str:
    parts = []

    if domain_docs:
        parts.append("[KNOWLEDGE BASE — APPLICABLE RULES]")
        for name, content in domain_docs.items():
            parts.append(f"--- {name} ---")
            # Truncate very long docs to keep prompt size reasonable
            if len(content) > 3000:
                content = content[:3000] + "\n... (truncated)"
            parts.append(content)

    if learned:
        parts.append("\n[LEARNED EXCEPTIONS — DO NOT RE-FLAG THESE PATTERNS]")
        parts.append(learned)

    parts.append(f"\n[CODE CHANGE]")
    parts.append(f"File: {file_path}")
    parts.append(f"Diff:\n{diff_text}")

    return "\n\n".join(parts)


def call_claude_api(system_prompt: str, user_prompt: str, model: str, api_key: str) -> dict:
    """Call Anthropic Messages API via urllib. Returns parsed JSON dict."""
    url = "https://api.anthropic.com/v1/messages"

    payload = {
        "model": model,
        "max_tokens": 256,
        "system": [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "prompt-caching-2024-07-31",
        },
        method="POST",
    )

    # Retry with exponential backoff on transient errors (rate limits, network blips)
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            break  # success
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            # 429 = rate limit, 529 = overloaded — retry after backoff
            if e.code in (429, 529) and attempt < 2:
                wait = 2 ** (attempt + 1)
                print(f"[Q] API rate limited ({e.code}), retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                last_err = e
                continue
            # 5xx transient server errors — retry once
            if e.code >= 500 and attempt < 2:
                time.sleep(2)
                last_err = e
                continue
            print(f"[Q ERROR] API call failed ({e.code}): {error_body}", file=sys.stderr)
            return {"flagged": False, "api_error": True}
        except urllib.error.URLError as e:
            if attempt < 2:
                time.sleep(2)
                last_err = e
                continue
            print(f"[Q ERROR] Network error: {e.reason}", file=sys.stderr)
            return {"flagged": False, "api_error": True}
    else:
        print(f"[Q ERROR] API unavailable after 3 attempts: {last_err}", file=sys.stderr)
        return {"flagged": False, "api_error": True}

    # Extract text content from response
    content = body.get("content", [])
    if not content or content[0].get("type") != "text":
        print("[Q ERROR] Unexpected API response structure", file=sys.stderr)
        return {"flagged": False}

    raw_text = content[0]["text"].strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Balanced-brace extraction — handles nested JSON the simple regex can't
        start = raw_text.find("{")
        if start != -1:
            depth, end = 0, -1
            for i, ch in enumerate(raw_text[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end != -1:
                try:
                    return json.loads(raw_text[start:end + 1])
                except json.JSONDecodeError:
                    pass
        print(f"[Q ERROR] Could not parse verdict JSON: {raw_text[:200]}", file=sys.stderr)
        return {"flagged": False}


def get_file_diff(file_path: str) -> str:
    """Get git diff for a specific file against HEAD.

    Returns empty string for untracked files (no git context = no meaningful diff).
    Uses -U30 to include 30 lines of context so Q can see surrounding code.
    """
    cwd = str(Path(file_path).parent)
    try:
        # Skip untracked files — no git history means no actionable diff context
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", file_path],
            capture_output=True, text=True, timeout=5, cwd=cwd
        )
        if status.returncode == 0 and status.stdout.strip().startswith("??"):
            return ""

        # -U30: 30 lines of context so Q understands hot paths, class boundaries, etc.
        result = subprocess.run(
            ["git", "diff", "-U30", "HEAD", "--", file_path],
            capture_output=True, text=True, timeout=10, cwd=cwd
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout

        result = subprocess.run(
            ["git", "diff", "-U30", "--", file_path],
            capture_output=True, text=True, timeout=10, cwd=cwd
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout

        # Staged new file
        result = subprocess.run(
            ["git", "diff", "-U30", "--cached", "--", file_path],
            capture_output=True, text=True, timeout=10, cwd=cwd
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return ""


def get_changed_files() -> list[str]:
    """Get list of changed files from git diff (CI mode)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: staged files
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return []


def append_verdict(config: dict, verdict_id: str, file_path: str, verdict: dict) -> None:
    """Append a verdict row to knowledge_base/verdicts/index.md."""
    verdicts_path = Path(config["verdicts_path"])
    if not verdicts_path.exists():
        return

    date = datetime.now().strftime("%Y-%m-%d")
    severity = verdict.get("severity", "—")
    rule_id = verdict.get("rule_id", "—")
    message = verdict.get("message", "—").replace("|", "/")  # Sanitize for markdown table
    outcome = "flagged" if verdict.get("flagged") else "clean"

    row = f"| {date} | {verdict_id} | `{file_path}` | {rule_id} | {severity} | {message} | {outcome} | silent-hook |"

    content = verdicts_path.read_text(encoding="utf-8")
    # Insert before the "_No verdicts yet._" placeholder or append after last row
    if "_No verdicts yet._" in content:
        content = content.replace(
            "| — | — | — | — | — | — | — | — |\n\n_No verdicts yet._",
            f"| — | — | — | — | — | — | — | — |\n{row}"
        )
    else:
        # Find the last table row and append after it
        lines = content.splitlines()
        # Find last line starting with |
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].startswith("|"):
                lines.insert(i + 1, row)
                break
        content = "\n".join(lines) + "\n"

    verdicts_path.write_text(content, encoding="utf-8")


def format_verdict_output(file_path: str, verdict: dict, verdict_id: str) -> str:
    """Format verdict for terminal output."""
    if not verdict.get("flagged"):
        return f"[Q] ✓ {file_path} — clean"

    severity = verdict.get("severity", "?")
    rule_id = verdict.get("rule_id", "?")
    message = verdict.get("message", "No message")

    severity_icons = {"P0": "🔴", "P1": "🟠", "P2": "🟡", "P3": "⚪"}
    icon = severity_icons.get(severity, "❓")

    lines = [
        f"[Q] {icon} {severity} [{rule_id}] — {file_path}",
        f"    {message}",
        f"    Verdict ID: {verdict_id}",
        f"    Respond: [Q-ACCEPT] to confirm | [Q-OVERRIDE: reason] to dismiss",
    ]
    return "\n".join(lines)


def judge_file(file_path: str, config: dict, api_key: str) -> dict:
    """Run judgment on a single file. Returns verdict dict."""
    if not should_watch_file(config, file_path):
        return {"flagged": False, "skipped": True}

    diff = get_file_diff(file_path)
    if not diff:
        return {"flagged": False, "skipped": True, "reason": "no diff"}

    # Smart truncation: keep first half + last half so violations near the
    # end of a large diff aren't silently dropped.
    max_lines = config.get("max_diff_lines", 300)
    diff_lines = diff.splitlines()
    if len(diff_lines) > max_lines:
        half = max_lines // 2
        diff = (
            "\n".join(diff_lines[:half])
            + f"\n\n... ({len(diff_lines) - max_lines} lines omitted) ...\n\n"
            + "\n".join(diff_lines[-half:])
        )

    domain_docs = get_relevant_domains(diff, config["kb_path"])
    learned = load_learned(config)

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(file_path, diff, domain_docs, learned)

    model = get_model(config)
    verdict = call_claude_api(system_prompt, user_prompt, model, api_key)

    return verdict


def main():
    parser = argparse.ArgumentParser(description="Q — Code Conscience Judgment Engine")
    parser.add_argument("--file", help="Judge a single file (silent hook mode)")
    parser.add_argument("--diff", action="store_true", help="Judge all changed files (CI mode)")
    parser.add_argument("--fast", action="store_true", help="Use fast model (P0/P1 only)")
    args = parser.parse_args()

    if not args.file and not args.diff:
        parser.print_help()
        sys.exit(1)

    config = load_config()
    api_key = get_api_key(config)

    if args.fast:
        config["mode"] = "fast"

    files_to_judge = []
    if args.file:
        files_to_judge = [args.file]
    elif args.diff:
        files_to_judge = get_changed_files()
        if not files_to_judge:
            print("[Q] No changed files detected.")
            sys.exit(0)

    any_flagged = False

    # Rate limiting: track API call timestamps
    rate_limit = config.get("rate_limit_per_minute", 10)
    call_times: list[float] = []

    def rate_limited_judge(fp: str) -> tuple[str, dict]:
        """Judge a file, sleeping if needed to stay within rate limit."""
        now = time.time()
        window_start = now - 60.0
        # Prune old timestamps (thread-safe via GIL for list ops)
        while call_times and call_times[0] < window_start:
            call_times.pop(0)
        if len(call_times) >= rate_limit:
            sleep_for = 60.0 - (now - call_times[0]) + 0.1
            if sleep_for > 0:
                time.sleep(sleep_for)
        call_times.append(time.time())
        return fp, judge_file(fp, config, api_key)

    if args.diff and len(files_to_judge) > 1:
        # CI mode: judge files in parallel (up to 4 at a time, rate-limited)
        results: list[tuple[str, dict]] = []
        with ThreadPoolExecutor(max_workers=min(4, len(files_to_judge))) as executor:
            futures = {executor.submit(rate_limited_judge, fp): fp for fp in files_to_judge}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:
                    print(f"[Q ERROR] {futures[future]}: {exc}", file=sys.stderr)
    else:
        # Hook mode or single file: sequential
        results = [rate_limited_judge(fp) for fp in files_to_judge]

    for file_path, verdict in results:
        if verdict.get("skipped"):
            continue

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        short_file = Path(file_path).name.replace(".", "-")
        verdict_id = f"{timestamp}-{short_file}"

        if verdict.get("flagged"):
            severity = verdict.get("severity", "P2")
            append_verdict(config, verdict_id, file_path, verdict)

            if not sensitivity_allows(config, severity):
                continue

            print(format_verdict_output(file_path, verdict, verdict_id))

            if is_ci_gate(config, severity):
                any_flagged = True

    sys.exit(1 if any_flagged else 0)


if __name__ == "__main__":
    main()
