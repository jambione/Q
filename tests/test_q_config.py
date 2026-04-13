"""
Unit tests for q_config.py — config loading and policy helpers.

Run: python -m unittest tests/test_q_config.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import q_config


def _cfg(**overrides) -> dict:
    """Build a minimal config dict for testing."""
    base = {
        "mode": "normal",
        "model_fast": "claude-haiku-4-5-20251001",
        "model_normal": "claude-sonnet-4-6",
        "watched_extensions": [".py", ".ts", ".js"],
        "exclude_patterns": ["**/node_modules/**", "**/.git/**", "**/dist/**"],
        "sensitivity": "normal",
        "p3_silent": True,
        "advisory_only": False,
        "ci_gate_severities": ["P0", "P1"],
        "team_exceptions_path": "",
        "personal_kb_path": "",
    }
    base.update(overrides)
    return base


class TestShouldWatchFile(unittest.TestCase):

    def test_watched_extension_passes(self):
        cfg = _cfg()
        self.assertTrue(q_config.should_watch_file(cfg, "app/auth.py"))

    def test_unwatched_extension_blocked(self):
        cfg = _cfg()
        self.assertFalse(q_config.should_watch_file(cfg, "README.md"))

    def test_empty_watched_list_allows_all(self):
        cfg = _cfg(watched_extensions=[])
        self.assertTrue(q_config.should_watch_file(cfg, "anything.log"))

    def test_node_modules_excluded(self):
        cfg = _cfg()
        self.assertFalse(q_config.should_watch_file(cfg, "app/node_modules/lodash/index.js"))

    def test_dist_excluded(self):
        cfg = _cfg()
        self.assertFalse(q_config.should_watch_file(cfg, "project/dist/bundle.js"))

    def test_git_excluded(self):
        cfg = _cfg()
        self.assertFalse(q_config.should_watch_file(cfg, "repo/.git/config"))

    def test_normal_ts_file_passes(self):
        cfg = _cfg()
        self.assertTrue(q_config.should_watch_file(cfg, "src/components/Button.ts"))

    def test_custom_exclude_pattern(self):
        cfg = _cfg(exclude_patterns=["**/fixtures/**"])
        self.assertFalse(q_config.should_watch_file(cfg, "tests/fixtures/mock_config.py"))
        self.assertTrue(q_config.should_watch_file(cfg, "tests/helpers/utils.py"))


class TestSensitivityAllows(unittest.TestCase):

    def test_normal_p0(self):
        self.assertTrue(q_config.sensitivity_allows(_cfg(sensitivity="normal"), "P0"))

    def test_normal_p1(self):
        self.assertTrue(q_config.sensitivity_allows(_cfg(sensitivity="normal"), "P1"))

    def test_normal_p2(self):
        self.assertTrue(q_config.sensitivity_allows(_cfg(sensitivity="normal"), "P2"))

    def test_normal_p3_silenced_by_default(self):
        self.assertFalse(q_config.sensitivity_allows(_cfg(sensitivity="normal", p3_silent=True), "P3"))

    def test_strict_p3_allowed_when_p3_silent_false(self):
        # strict threshold includes P3; p3_silent=False lifts the early-exit guard
        self.assertTrue(q_config.sensitivity_allows(_cfg(sensitivity="strict", p3_silent=False), "P3"))

    def test_normal_p3_blocked_by_threshold_even_without_p3_silent(self):
        # normal threshold = P2, so P3 is below threshold regardless of p3_silent
        self.assertFalse(q_config.sensitivity_allows(_cfg(sensitivity="normal", p3_silent=False), "P3"))

    def test_strict_p3_still_silenced_by_p3_silent(self):
        self.assertFalse(q_config.sensitivity_allows(_cfg(sensitivity="strict", p3_silent=True), "P3"))

    def test_quiet_p2_blocked(self):
        self.assertFalse(q_config.sensitivity_allows(_cfg(sensitivity="quiet"), "P2"))

    def test_quiet_p1_allowed(self):
        self.assertTrue(q_config.sensitivity_allows(_cfg(sensitivity="quiet"), "P1"))

    def test_silent_p1_blocked(self):
        self.assertFalse(q_config.sensitivity_allows(_cfg(sensitivity="silent"), "P1"))

    def test_silent_p0_allowed(self):
        self.assertTrue(q_config.sensitivity_allows(_cfg(sensitivity="silent"), "P0"))


class TestIsCiGate(unittest.TestCase):

    def test_p0_is_gate(self):
        self.assertTrue(q_config.is_ci_gate(_cfg(), "P0"))

    def test_p1_is_gate(self):
        self.assertTrue(q_config.is_ci_gate(_cfg(), "P1"))

    def test_p2_is_not_gate(self):
        self.assertFalse(q_config.is_ci_gate(_cfg(), "P2"))

    def test_advisory_only_disables_all_gates(self):
        cfg = _cfg(advisory_only=True)
        self.assertFalse(q_config.is_ci_gate(cfg, "P0"))
        self.assertFalse(q_config.is_ci_gate(cfg, "P1"))

    def test_custom_gate_severities(self):
        cfg = _cfg(ci_gate_severities=["P0"])
        self.assertTrue(q_config.is_ci_gate(cfg, "P0"))
        self.assertFalse(q_config.is_ci_gate(cfg, "P1"))


class TestGetModel(unittest.TestCase):

    def test_normal_mode_returns_normal_model(self):
        self.assertEqual(q_config.get_model(_cfg(mode="normal")), "claude-sonnet-4-6")

    def test_fast_mode_returns_fast_model(self):
        self.assertEqual(q_config.get_model(_cfg(mode="fast")), "claude-haiku-4-5-20251001")

    def test_force_fast_overrides_mode(self):
        self.assertEqual(q_config.get_model(_cfg(mode="normal"), force_fast=True), "claude-haiku-4-5-20251001")


class TestLoadExceptions(unittest.TestCase):

    def test_no_files_returns_empty(self):
        cfg = _cfg(team_exceptions_path="/nonexistent/team.md", personal_kb_path="/nonexistent/personal.md")
        self.assertEqual(q_config.load_exceptions(cfg), "")

    def test_file_with_only_placeholder_excluded(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# Q Exceptions\n\n_No entries yet._\n")
            tmp = f.name
        cfg = _cfg(team_exceptions_path=tmp, personal_kb_path="/nonexistent.md")
        result = q_config.load_exceptions(cfg)
        self.assertEqual(result, "")

    def test_file_with_real_entry_included(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# Q Exceptions\n\n### 2026-01-01 — SEC-001 — tests/mock.py\nVerdict: `abc123`\n")
            tmp = f.name
        cfg = _cfg(team_exceptions_path=tmp, personal_kb_path="/nonexistent.md")
        result = q_config.load_exceptions(cfg)
        self.assertIn("### 2026-01-01", result)
        self.assertIn("Team-Approved", result)

    def test_both_files_combined(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tf:
            tf.write("### 2026-01-01 — SEC-001 — file.py\nVerdict: `team-123`\n")
            team_tmp = tf.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as pf:
            pf.write("### 2026-01-02 — ERR-001 — other.py\nVerdict: `personal-456`\n")
            personal_tmp = pf.name
        cfg = _cfg(team_exceptions_path=team_tmp, personal_kb_path=personal_tmp)
        result = q_config.load_exceptions(cfg)
        self.assertIn("team-123", result)
        self.assertIn("personal-456", result)


if __name__ == "__main__":
    unittest.main()
