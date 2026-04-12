"""
q-learn.py — Q's learning loop writer.

Usage:
  python scripts/q-learn.py --verdict-id <id> --response <accept|override> --reason <text>

  By default, exceptions are written to YOUR personal KB (knowledge_base/personal/q-learned.md)
  which is gitignored and applies only to you.

  To promote an exception to the whole team (requires PR review):
  python scripts/q-learn.py --verdict-id <id> --response override --reason <text> --team

Pure stdlib. No external dependencies.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from q_config import load_config


def append_accepted_exception(learned_path: Path, verdict_id: str, reason: str, rule_id: str = None, file_path: str = None) -> None:
    """Append an override entry to the Accepted Exceptions section."""
    date = datetime.now().strftime("%Y-%m-%d")
    rule_str = f" — {rule_id}" if rule_id else ""
    file_str = f" — {file_path}" if file_path else ""

    entry = f"""
### {date}{rule_str}{file_str}
Verdict: `{verdict_id}`
User override: {reason}
"""

    content = learned_path.read_text(encoding="utf-8")

    if "## Accepted Exceptions (Q-OVERRIDE)" in content:
        marker = "## Accepted Exceptions (Q-OVERRIDE)"
        placeholder = "_No entries yet. Added by q-memory after user responds [Q-OVERRIDE: reason]._"

        if placeholder in content:
            content = content.replace(placeholder, entry.strip())
        else:
            # Find the section and append before the next ## heading or end of section
            idx = content.index(marker) + len(marker)
            # Find the next ## heading after this section
            next_section = content.find("\n## ", idx)
            if next_section != -1:
                content = content[:next_section] + "\n" + entry + content[next_section:]
            else:
                content = content.rstrip() + "\n" + entry
    else:
        content = content.rstrip() + "\n\n## Accepted Exceptions (Q-OVERRIDE)\n" + entry

    learned_path.write_text(content, encoding="utf-8")


def append_confirmed_wrong(learned_path: Path, verdict_id: str, rule_id: str = None, file_path: str = None, message: str = None) -> None:
    """Append a confirmation entry to the Confirmed Wrong section."""
    date = datetime.now().strftime("%Y-%m-%d")
    rule_str = f" — {rule_id}" if rule_id else ""
    file_str = f" — {file_path}" if file_path else ""
    msg_str = f"\nUser confirmed: {message}" if message else ""

    entry = f"""
### {date}{rule_str}{file_str}
Verdict: `{verdict_id}`{msg_str}
"""

    content = learned_path.read_text(encoding="utf-8")

    if "## Confirmed Wrong (Q-ACCEPT)" in content:
        marker = "## Confirmed Wrong (Q-ACCEPT)"
        placeholder = "_No entries yet. Added by q-memory after user responds [Q-ACCEPT]._"

        if placeholder in content:
            content = content.replace(placeholder, entry.strip())
        else:
            idx = content.index(marker) + len(marker)
            next_section = content.find("\n## ", idx)
            if next_section != -1:
                content = content[:next_section] + "\n" + entry + content[next_section:]
            else:
                content = content.rstrip() + "\n" + entry
    else:
        content = content.rstrip() + "\n\n## Confirmed Wrong (Q-ACCEPT)\n" + entry

    learned_path.write_text(content, encoding="utf-8")


def update_last_updated(learned_path: Path) -> None:
    """Update the Last Updated date in q-learned.md."""
    date = datetime.now().strftime("%Y-%m-%d")
    content = learned_path.read_text(encoding="utf-8")

    import re
    content = re.sub(
        r'\*\*Last Updated\*\*: \d{4}-\d{2}-\d{2}',
        f'**Last Updated**: {date}',
        content
    )
    learned_path.write_text(content, encoding="utf-8")


def ensure_personal_kb(personal_path: Path) -> None:
    """Create personal KB file from template if it doesn't exist yet."""
    if personal_path.exists():
        return
    personal_path.parent.mkdir(parents=True, exist_ok=True)
    personal_path.write_text(
        "# Q Personal Learned Exceptions\n\n"
        "**Owner**: you (this file is gitignored — never committed)\n"
        f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        "---\n\n"
        "## Confirmed Wrong (Q-ACCEPT)\n\n"
        "_No entries yet._\n\n"
        "---\n\n"
        "## Accepted Exceptions (Q-OVERRIDE)\n\n"
        "_No entries yet._\n\n"
        "---\n\n"
        "## Patterns Detected\n\n"
        "_No patterns yet._\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description="Q — Learning Loop Writer")
    parser.add_argument("--verdict-id", required=True, help="Verdict ID to close")
    parser.add_argument("--response", required=True, choices=["accept", "override"],
                        help="User response: accept (confirms wrong) or override (dismisses)")
    parser.add_argument("--reason", default="", help="User's explanation (required for override)")
    parser.add_argument("--rule-id", default=None, help="Rule ID from the original verdict")
    parser.add_argument("--file", default=None, help="File path from the original verdict")
    parser.add_argument("--message", default=None, help="Q's original verdict message")
    parser.add_argument("--team", action="store_true",
                        help="Write to team exceptions (knowledge_base/team/exceptions/approved.md). "
                             "Reminder: this requires a PR review before merging.")
    args = parser.parse_args()

    if args.response == "override" and not args.reason:
        print("[Q ERROR] --reason is required when --response is override", file=sys.stderr)
        sys.exit(1)

    config = load_config()

    if args.team:
        target_path = Path(config["team_exceptions_path"])
        scope = "team"
        if not target_path.exists():
            print(f"[Q ERROR] Team exceptions file not found at {target_path}", file=sys.stderr)
            sys.exit(1)
        print()
        print("  ⚠  You are writing to the TEAM exceptions file.")
        print("     This affects all developers. Please open a PR for review.")
        print(f"     File: {target_path}")
        print()
    else:
        target_path = Path(config["personal_kb_path"])
        scope = "personal"
        ensure_personal_kb(target_path)

    if args.response == "accept":
        append_confirmed_wrong(
            target_path,
            verdict_id=args.verdict_id,
            rule_id=args.rule_id,
            file_path=args.file,
            message=args.message,
        )
        print(f"[Q-LEARNED: {scope}/q-learned.md | Confirmed wrong: verdict {args.verdict_id}]")

    elif args.response == "override":
        append_accepted_exception(
            target_path,
            verdict_id=args.verdict_id,
            reason=args.reason,
            rule_id=args.rule_id,
            file_path=args.file,
        )
        print(f"[Q-LEARNED: {scope}/q-learned.md | Accepted exception: {args.reason[:80]}]")

        if not args.team:
            print()
            print("  Tip: to apply this exception to the whole team, rerun with --team")
            print(f"  python scripts/q-learn.py --verdict-id {args.verdict_id} --response override "
                  f"--reason \"{args.reason}\" --team")

    update_last_updated(target_path)
    print(f"[Q-VERDICT-CLOSED: {args.verdict_id}]")


if __name__ == "__main__":
    main()
