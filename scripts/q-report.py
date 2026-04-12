"""
q-report.py — Q weekly digest generator.

Reads knowledge_base/verdicts/index.md and produces a Markdown summary:
  - Total verdicts this week
  - Top rules fired (by count)
  - Override rate (how often devs disagreed)
  - Files with most flags
  - P0/P1 verdict list (the ones that matter)

Usage:
  python scripts/q-report.py                    Print to stdout
  python scripts/q-report.py --days 30          Look back 30 days (default: 7)
  python scripts/q-report.py --output report.md Write to file

Pure stdlib. No external dependencies.
"""

import argparse
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from q_config import load_config


def parse_override_counts(config: dict) -> Counter:
    """Parse accepted exception counts per rule from team + personal KB files.

    Used for self-calibration: rules with high override rates are miscalibrated.
    """
    override_counts: Counter = Counter()

    for path_key in ("team_exceptions_path", "personal_kb_path"):
        exc_path = Path(config.get(path_key, ""))
        if not exc_path.exists():
            continue
        content = exc_path.read_text(encoding="utf-8")

        in_exceptions = False
        for line in content.splitlines():
            if "## Accepted Exceptions" in line:
                in_exceptions = True
            elif line.startswith("## "):
                in_exceptions = False
            elif in_exceptions and line.startswith("### "):
                # Header format: ### DATE — RULE-ID — filename
                parts = line.lstrip("# ").split(" — ")
                if len(parts) >= 2:
                    rule_id = parts[1].strip()
                    if re.match(r"^[A-Z]+-\d+$", rule_id):
                        override_counts[rule_id] += 1

    return override_counts


def build_calibration_section(flag_counts: Counter, override_counts: Counter) -> list[str]:
    """Build a 'Rules Needing Review' section based on override rates."""
    if not flag_counts:
        return []

    lines = [
        "## Rule Calibration",
        "",
        "> Rules with a high override rate are firing too aggressively.",
        "> Rules with zero fires in this period may no longer be relevant.",
        "",
        "| Rule | Flags | Overrides | Override Rate | Recommendation |",
        "|------|-------|-----------|--------------|----------------|",
    ]

    flagged_rules = set(flag_counts.keys()) | set(override_counts.keys())
    needs_attention = False

    for rule in sorted(flagged_rules):
        flags = flag_counts.get(rule, 0)
        overrides = override_counts.get(rule, 0)
        rate = (overrides / flags * 100) if flags > 0 else 0
        rate_str = f"{rate:.0f}%" if flags > 0 else "n/a"

        if flags == 0 and overrides > 0:
            rec = "Investigate — overrides but no recent flags"
            needs_attention = True
        elif rate >= 60:
            rec = "⚠️ Reduce severity or add path exception"
            needs_attention = True
        elif rate >= 40:
            rec = "Consider severity reduction"
            needs_attention = True
        elif flags == 0:
            rec = "No recent activity — consider retiring"
        else:
            rec = "Healthy"

        lines.append(f"| {rule} | {flags} | {overrides} | {rate_str} | {rec} |")

    lines.append("")
    if not needs_attention:
        lines.append("_All rules are well-calibrated in this period._")
        lines.append("")

    return lines


def parse_verdict_table(verdicts_path: Path) -> list[dict]:
    """Parse the markdown table in verdicts/index.md into a list of dicts."""
    if not verdicts_path.exists():
        return []

    content = verdicts_path.read_text(encoding="utf-8")
    rows = []

    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Skip header and separator rows
        if "Date" in line or "---" in line:
            continue

        parts = [cell.strip() for cell in line.split("|")]
        # Remove empty cells from leading/trailing |
        parts = [p for p in parts if p]

        if len(parts) < 8:
            continue

        try:
            rows.append({
                "date": parts[0],
                "verdict_id": parts[1],
                "file": parts[2].strip("`"),
                "rule": parts[3],
                "severity": parts[4],
                "message": parts[5],
                "outcome": parts[6],
                "mode": parts[7],
            })
        except IndexError:
            continue

    return rows


def filter_by_days(rows: list[dict], days: int) -> list[dict]:
    """Return only rows within the last N days."""
    cutoff = datetime.now() - timedelta(days=days)
    result = []
    for row in rows:
        try:
            row_date = datetime.strptime(row["date"], "%Y-%m-%d")
            if row_date >= cutoff:
                result.append(row)
        except ValueError:
            continue
    return result


def build_report(rows: list[dict], days: int, config: dict | None = None) -> str:
    """Build the Markdown digest from parsed verdict rows."""
    today = datetime.now().strftime("%Y-%m-%d")
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    lines = [
        f"# Q Weekly Digest",
        f"",
        f"**Period**: {since} → {today} ({days} days)  ",
        f"**Generated**: {today}",
        f"",
        f"---",
        f"",
    ]

    if not rows:
        lines.append("_No verdicts in this period._")
        return "\n".join(lines)

    flagged = [r for r in rows if r["outcome"] == "flagged"]
    clean = [r for r in rows if r["outcome"] == "clean"]

    # ── Summary ──────────────────────────────────────────────
    lines += [
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total verdicts | {len(rows)} |",
        f"| Flagged | {len(flagged)} |",
        f"| Clean | {len(clean)} |",
        f"",
    ]

    if flagged:
        # Override rate: verdicts that appear in team/personal exceptions
        # (proxy: if a verdict_id appears in q-learned, it was overridden)
        # We can't check this without reading the learned files, so use a simpler
        # heuristic: count distinct verdict IDs to avoid double-counting.
        p0 = [r for r in flagged if r["severity"] == "P0"]
        p1 = [r for r in flagged if r["severity"] == "P1"]
        p2 = [r for r in flagged if r["severity"] == "P2"]
        p3 = [r for r in flagged if r["severity"] == "P3"]

        lines += [
            "## Severity Breakdown",
            "",
            "| Severity | Count | Meaning |",
            "|----------|-------|---------|",
            f"| 🔴 P0 | {len(p0)} | Critical — never merge |",
            f"| 🟠 P1 | {len(p1)} | Significant risk |",
            f"| 🟡 P2 | {len(p2)} | Quality concern |",
            f"| ⚪ P3 | {len(p3)} | Observation (silent) |",
            "",
        ]

        # ── Top rules ────────────────────────────────────────
        rule_counts = Counter(r["rule"] for r in flagged if r["rule"] != "—")
        if rule_counts:
            lines += [
                "## Top Rules Fired",
                "",
                "| Rule | Count |",
                "|------|-------|",
            ]
            for rule, count in rule_counts.most_common(10):
                lines.append(f"| {rule} | {count} |")
            lines.append("")

        # ── Top files ────────────────────────────────────────
        file_counts = Counter(r["file"] for r in flagged)
        if file_counts:
            lines += [
                "## Most-Flagged Files",
                "",
                "| File | Flags |",
                "|------|-------|",
            ]
            for file_path, count in file_counts.most_common(10):
                lines.append(f"| `{file_path}` | {count} |")
            lines.append("")

        # ── P0/P1 detail ─────────────────────────────────────
        critical = p0 + p1
        if critical:
            lines += [
                "## P0 / P1 Verdicts (action required)",
                "",
                "| Date | File | Rule | Severity | Message |",
                "|------|------|------|----------|---------|",
            ]
            for r in sorted(critical, key=lambda x: x["date"], reverse=True):
                sev_icon = "🔴" if r["severity"] == "P0" else "🟠"
                lines.append(
                    f"| {r['date']} | `{r['file']}` | {r['rule']} | {sev_icon} {r['severity']} | {r['message']} |"
                )
            lines.append("")

        # ── Per-day breakdown ─────────────────────────────────
        by_day: dict[str, list] = defaultdict(list)
        for r in flagged:
            by_day[r["date"]].append(r)

        if len(by_day) > 1:
            lines += [
                "## Daily Activity",
                "",
                "| Date | Flags | P0 | P1 | P2 |",
                "|------|-------|----|----|----|",
            ]
            for day in sorted(by_day.keys(), reverse=True):
                day_rows = by_day[day]
                lines.append(
                    f"| {day} | {len(day_rows)} "
                    f"| {sum(1 for r in day_rows if r['severity'] == 'P0')} "
                    f"| {sum(1 for r in day_rows if r['severity'] == 'P1')} "
                    f"| {sum(1 for r in day_rows if r['severity'] == 'P2')} |"
                )
            lines.append("")

    # ── Self-calibration ─────────────────────────────────────
    if config and flagged:
        rule_flag_counts = Counter(r["rule"] for r in flagged if r["rule"] != "—")
        override_counts = parse_override_counts(config)
        calibration_lines = build_calibration_section(rule_flag_counts, override_counts)
        if calibration_lines:
            lines += calibration_lines

    lines += [
        "---",
        "",
        "_Generated by Q · `python scripts/q-report.py`_",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Q — Weekly Digest Generator")
    parser.add_argument("--days", type=int, default=7, help="Look-back window in days (default: 7)")
    parser.add_argument("--output", default=None, help="Write report to this file path (default: stdout)")
    args = parser.parse_args()

    config = load_config()
    verdicts_path = Path(config["verdicts_path"])

    all_rows = parse_verdict_table(verdicts_path)
    rows = filter_by_days(all_rows, args.days)
    report = build_report(rows, args.days, config)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"[Q-REPORT] Written to {output_path} ({len(rows)} verdicts, last {args.days} days)")
    else:
        print(report)


if __name__ == "__main__":
    main()
