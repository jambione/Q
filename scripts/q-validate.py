"""
q-validate.py — Q Knowledge Base validator.

Checks:
  - All domain docs are listed in knowledge_base/index.md
  - Each domain doc has required headers (Owner, Review Cadence, Last Updated)
  - knowledge_base/learned/q-learned.md exists and has required sections
  - knowledge_base/verdicts/index.md exists and is well-formed

Usage:
  python scripts/q-validate.py

Returns 0 on pass, 1 on failure. Prints errors to stdout.
Pure stdlib. No external dependencies.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from q_config import load_config


REQUIRED_DOMAIN_HEADERS = ["**Owner**", "**Review Cadence**", "**Last Updated**"]

REQUIRED_LEARNED_SECTIONS = [
    "## Confirmed Wrong (Q-ACCEPT)",
    "## Accepted Exceptions (Q-OVERRIDE)",
    "## Patterns Detected (q-memory Synthesis)",
]

REQUIRED_VERDICTS_HEADERS = [
    "| Date |", "| Verdict ID |", "| File |", "| Rule |",
    "| Severity |", "| Message |", "| Outcome |", "| Mode |",
]


def check_domain_docs_indexed(config: dict) -> list[str]:
    """Verify every domain doc file is referenced in knowledge_base/index.md."""
    errors = []
    kb_path = Path(config["kb_path"])
    index_path = kb_path / "index.md"
    domains_dir = kb_path / "domains"

    if not index_path.exists():
        return [f"MISSING: knowledge_base/index.md not found"]

    index_content = index_path.read_text(encoding="utf-8")

    if not domains_dir.exists():
        return [f"MISSING: knowledge_base/domains/ directory not found"]

    for doc_path in sorted(domains_dir.glob("*.md")):
        doc_name = doc_path.name
        if doc_name not in index_content:
            errors.append(f"NOT INDEXED: domains/{doc_name} not found in knowledge_base/index.md")

    return errors


def check_domain_doc_headers(config: dict) -> list[str]:
    """Verify each domain doc has required headers."""
    errors = []
    kb_path = Path(config["kb_path"])
    domains_dir = kb_path / "domains"

    if not domains_dir.exists():
        return []

    for doc_path in sorted(domains_dir.glob("*.md")):
        content = doc_path.read_text(encoding="utf-8")
        for header in REQUIRED_DOMAIN_HEADERS:
            if header not in content:
                errors.append(f"MISSING HEADER: {doc_path.name} is missing '{header}'")

    return errors


def check_learned_doc(config: dict) -> list[str]:
    """Verify q-learned.md exists and has required sections."""
    errors = []
    learned_path = Path(config["learned_path"])

    if not learned_path.exists():
        return [f"MISSING: q-learned.md not found at {config['learned_path']}"]

    content = learned_path.read_text(encoding="utf-8")

    for section in REQUIRED_LEARNED_SECTIONS:
        if section not in content:
            errors.append(f"MISSING SECTION: q-learned.md is missing '{section}'")

    return errors


def check_verdicts_doc(config: dict) -> list[str]:
    """Verify verdicts/index.md exists and has the required table headers."""
    errors = []
    verdicts_path = Path(config["verdicts_path"])

    if not verdicts_path.exists():
        return [f"MISSING: verdicts/index.md not found at {config['verdicts_path']}"]

    content = verdicts_path.read_text(encoding="utf-8")

    # Check that the table header row exists (all required columns)
    for header in REQUIRED_VERDICTS_HEADERS:
        if header not in content:
            errors.append(f"MISSING COLUMN: verdicts/index.md is missing table column '{header}'")

    return errors


def check_rule_id_format(config: dict) -> list[str]:
    """Verify all rule IDs in domain docs follow the expected pattern (e.g., SEC-001)."""
    errors = []
    kb_path = Path(config["kb_path"])
    domains_dir = kb_path / "domains"

    if not domains_dir.exists():
        return []

    # Domain prefix map
    prefix_map = {
        "security.md": "SEC",
        "architecture.md": "ARCH",
        "testing.md": "TEST",
        "performance.md": "PERF",
        "error-handling.md": "ERR",
    }

    for doc_path in sorted(domains_dir.glob("*.md")):
        expected_prefix = prefix_map.get(doc_path.name)
        if not expected_prefix:
            continue  # user-defined domain, skip prefix check

        content = doc_path.read_text(encoding="utf-8")
        # Find rule ID headers like ## SEC-001: ...
        rule_headers = re.findall(r'^## ([A-Z]+-\d+):', content, re.MULTILINE)
        for rule_id in rule_headers:
            if not rule_id.startswith(expected_prefix):
                errors.append(
                    f"WRONG PREFIX: {doc_path.name} has rule '{rule_id}' — expected prefix '{expected_prefix}'"
                )

    return errors


def main() -> int:
    config = load_config()
    all_errors = []

    checks = [
        ("Domain docs indexed", check_domain_docs_indexed),
        ("Domain doc headers", check_domain_doc_headers),
        ("Learned doc structure", check_learned_doc),
        ("Verdicts doc structure", check_verdicts_doc),
        ("Rule ID format", check_rule_id_format),
    ]

    for check_name, check_fn in checks:
        errors = check_fn(config)
        if errors:
            print(f"\nFAILED: {check_name}")
            for err in errors:
                print(f"  - {err}")
            all_errors.extend(errors)

    if all_errors:
        print(f"\nQ validation failed: {len(all_errors)} error(s)")
        return 1

    print("Q validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
