"""
Unit tests for q-report.py — digest generation and calibration helpers.

Run: python -m unittest tests/test_q_report.py
"""

import importlib.util
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

# q-report.py has a hyphen — load it by file path
_scripts = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_scripts))
_spec = importlib.util.spec_from_file_location("q_report", _scripts / "q-report.py")
q_report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q_report)


def _cfg(**overrides) -> dict:
    base = {
        "team_exceptions_path": "",
        "personal_kb_path": "",
    }
    base.update(overrides)
    return base


class TestParseVerdictTable(unittest.TestCase):

    def test_empty_file_returns_empty_list(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# Verdicts\n\n_No verdicts yet._\n")
            tmp = f.name
        self.assertEqual(q_report.parse_verdict_table(Path(tmp)), [])

    def test_parses_single_row(self):
        row = "| 2026-04-01 | 20260401-001-auth | `auth.py` | SEC-001 | P0 | API key hardcoded | flagged | silent-hook |"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("| Date | Verdict ID | File | Rule | Severity | Message | Outcome | Mode |\n")
            f.write("|------|------------|------|------|----------|---------|---------|------|\n")
            f.write(row + "\n")
            tmp = f.name
        rows = q_report.parse_verdict_table(Path(tmp))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "2026-04-01")
        self.assertEqual(rows[0]["rule"], "SEC-001")
        self.assertEqual(rows[0]["severity"], "P0")
        self.assertEqual(rows[0]["outcome"], "flagged")
        self.assertEqual(rows[0]["file"], "auth.py")

    def test_parses_multiple_rows(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("| Date | Verdict ID | File | Rule | Severity | Message | Outcome | Mode |\n")
            f.write("|------|------------|------|------|----------|---------|---------|------|\n")
            f.write("| 2026-04-01 | v-001 | `a.py` | SEC-001 | P0 | msg1 | flagged | hook |\n")
            f.write("| 2026-04-02 | v-002 | `b.py` | ERR-001 | P1 | msg2 | clean | hook |\n")
            tmp = f.name
        rows = q_report.parse_verdict_table(Path(tmp))
        self.assertEqual(len(rows), 2)

    def test_nonexistent_file_returns_empty(self):
        self.assertEqual(q_report.parse_verdict_table(Path("/nonexistent.md")), [])


class TestFilterByDays(unittest.TestCase):

    def test_filters_old_rows(self):
        rows = [
            {"date": "2020-01-01", "severity": "P0"},
            {"date": "2026-04-10", "severity": "P1"},
        ]
        result = q_report.filter_by_days(rows, 7)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["severity"], "P1")

    def test_empty_input(self):
        self.assertEqual(q_report.filter_by_days([], 7), [])

    def test_malformed_date_skipped(self):
        rows = [{"date": "not-a-date", "severity": "P0"}]
        result = q_report.filter_by_days(rows, 7)
        self.assertEqual(result, [])


class TestParseOverrideCounts(unittest.TestCase):

    def test_no_files_returns_empty_counter(self):
        cfg = _cfg(team_exceptions_path="/nonexistent.md", personal_kb_path="/nonexistent2.md")
        result = q_report.parse_override_counts(cfg)
        self.assertEqual(len(result), 0)

    def test_counts_rule_ids_from_exception_headers(self):
        content = (
            "# Exceptions\n\n"
            "## Accepted Exceptions\n\n"
            "### 2026-01-01 — SEC-001 — tests/mock.py\nVerdict: `v-001`\n\n"
            "### 2026-01-02 — SEC-001 — tests/other.py\nVerdict: `v-002`\n\n"
            "### 2026-01-03 — ERR-001 — handler.py\nVerdict: `v-003`\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            tmp = f.name
        cfg = _cfg(team_exceptions_path=tmp, personal_kb_path="/nonexistent.md")
        result = q_report.parse_override_counts(cfg)
        self.assertEqual(result["SEC-001"], 2)
        self.assertEqual(result["ERR-001"], 1)

    def test_ignores_non_rule_id_headers(self):
        content = (
            "## Accepted Exceptions\n\n"
            "### 2026-01-01 — Some free-form note\nVerdict: `v-001`\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            tmp = f.name
        cfg = _cfg(team_exceptions_path=tmp, personal_kb_path="/nonexistent.md")
        result = q_report.parse_override_counts(cfg)
        self.assertEqual(len(result), 0)


class TestBuildCalibrationSection(unittest.TestCase):

    def test_empty_flags_returns_empty_list(self):
        result = q_report.build_calibration_section(Counter(), Counter())
        self.assertEqual(result, [])

    def test_healthy_rule_shows_healthy(self):
        flags = Counter({"SEC-001": 10})
        overrides = Counter({"SEC-001": 1})
        lines = q_report.build_calibration_section(flags, overrides)
        combined = "\n".join(lines)
        self.assertIn("SEC-001", combined)
        self.assertIn("Healthy", combined)

    def test_high_override_rate_flags_recommendation(self):
        flags = Counter({"SEC-001": 5})
        overrides = Counter({"SEC-001": 4})  # 80% override rate
        lines = q_report.build_calibration_section(flags, overrides)
        combined = "\n".join(lines)
        self.assertIn("Reduce severity", combined)

    def test_zero_fire_rule_suggests_retiring(self):
        flags = Counter({"SEC-002": 0})
        overrides = Counter()
        lines = q_report.build_calibration_section(flags, overrides)
        combined = "\n".join(lines)
        self.assertIn("consider retiring", combined.lower())

    def test_all_healthy_shows_summary_message(self):
        flags = Counter({"SEC-001": 10})
        overrides = Counter({"SEC-001": 1})
        lines = q_report.build_calibration_section(flags, overrides)
        combined = "\n".join(lines)
        self.assertIn("well-calibrated", combined)


class TestBuildReport(unittest.TestCase):

    def test_empty_rows_shows_no_verdicts(self):
        result = q_report.build_report([], 7)
        self.assertIn("No verdicts", result)

    def test_report_header_present(self):
        result = q_report.build_report([], 7)
        self.assertIn("Q Weekly Digest", result)

    def test_severity_counts_appear(self):
        rows = [
            {"date": "2026-04-10", "severity": "P0", "rule": "SEC-001",
             "file": "auth.py", "outcome": "flagged", "message": "key", "verdict_id": "v1", "mode": "hook"},
            {"date": "2026-04-11", "severity": "P1", "rule": "ERR-001",
             "file": "app.py", "outcome": "flagged", "message": "catch", "verdict_id": "v2", "mode": "hook"},
        ]
        result = q_report.build_report(rows, 7)
        self.assertIn("P0", result)
        self.assertIn("P1", result)


if __name__ == "__main__":
    unittest.main()
