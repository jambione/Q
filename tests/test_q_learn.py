"""
Unit tests for q-learn.py — exception recording helpers.

Run: python -m unittest tests/test_q_learn.py
"""

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# q-learn.py has a hyphen — load it by file path
_scripts = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_scripts))
_spec = importlib.util.spec_from_file_location("q_learn", _scripts / "q-learn.py")
q_learn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q_learn)


PERSONAL_KB_TEMPLATE = (
    "# Q Personal Learned Exceptions\n\n"
    "**Owner**: you\n"
    "**Last Updated**: 2026-01-01\n\n"
    "---\n\n"
    "## Confirmed Wrong (Q-ACCEPT)\n\n"
    "_No entries yet. Added by q-memory after user responds [Q-ACCEPT]._\n\n"
    "---\n\n"
    "## Accepted Exceptions (Q-OVERRIDE)\n\n"
    "_No entries yet. Added by q-memory after user responds [Q-OVERRIDE: reason]._\n\n"
    "---\n\n"
    "## Patterns Detected\n\n"
    "_No patterns yet._\n"
)


def _write_kb(path: Path, content: str = PERSONAL_KB_TEMPLATE) -> None:
    path.write_text(content, encoding="utf-8")


class TestEnsurePersonalKb(unittest.TestCase):

    def test_creates_file_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "personal" / "q-learned.md"
            self.assertFalse(kb_path.exists())
            q_learn.ensure_personal_kb(kb_path)
            self.assertTrue(kb_path.exists())

    def test_created_file_has_required_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "q-learned.md"
            q_learn.ensure_personal_kb(kb_path)
            content = kb_path.read_text(encoding="utf-8")
            self.assertIn("## Confirmed Wrong (Q-ACCEPT)", content)
            self.assertIn("## Accepted Exceptions (Q-OVERRIDE)", content)
            self.assertIn("## Patterns Detected", content)

    def test_does_not_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "q-learned.md"
            kb_path.write_text("existing content", encoding="utf-8")
            q_learn.ensure_personal_kb(kb_path)
            self.assertEqual(kb_path.read_text(encoding="utf-8"), "existing content")


class TestUpdateLastUpdated(unittest.TestCase):

    def test_updates_date_in_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "q-learned.md"
            _write_kb(kb_path)
            q_learn.update_last_updated(kb_path)
            content = kb_path.read_text(encoding="utf-8")
            today = datetime.now().strftime("%Y-%m-%d")
            self.assertIn(f"**Last Updated**: {today}", content)

    def test_does_not_duplicate_date_field(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "q-learned.md"
            _write_kb(kb_path)
            q_learn.update_last_updated(kb_path)
            q_learn.update_last_updated(kb_path)
            content = kb_path.read_text(encoding="utf-8")
            self.assertEqual(content.count("**Last Updated**"), 1)


class TestAppendConfirmedWrong(unittest.TestCase):

    def test_replaces_placeholder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "q-learned.md"
            _write_kb(kb_path)
            q_learn.append_confirmed_wrong(kb_path, "verdict-001", rule_id="SEC-001", file_path="auth.py")
            content = kb_path.read_text(encoding="utf-8")
            self.assertIn("verdict-001", content)
            self.assertIn("SEC-001", content)
            self.assertNotIn("_No entries yet. Added by q-memory after user responds [Q-ACCEPT]._", content)

    def test_appends_to_existing_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "q-learned.md"
            _write_kb(kb_path)
            q_learn.append_confirmed_wrong(kb_path, "verdict-001")
            q_learn.append_confirmed_wrong(kb_path, "verdict-002")
            content = kb_path.read_text(encoding="utf-8")
            self.assertIn("verdict-001", content)
            self.assertIn("verdict-002", content)

    def test_includes_message_if_provided(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "q-learned.md"
            _write_kb(kb_path)
            q_learn.append_confirmed_wrong(kb_path, "v-001", message="hardcoded credential confirmed")
            content = kb_path.read_text(encoding="utf-8")
            self.assertIn("hardcoded credential confirmed", content)


class TestAppendAcceptedException(unittest.TestCase):

    def test_replaces_placeholder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "q-learned.md"
            _write_kb(kb_path)
            q_learn.append_accepted_exception(
                kb_path, "verdict-001", reason="test fixture mock passwords are OK"
            )
            content = kb_path.read_text(encoding="utf-8")
            self.assertIn("verdict-001", content)
            self.assertIn("test fixture mock passwords are OK", content)
            self.assertNotIn("_No entries yet. Added by q-memory after user responds [Q-OVERRIDE: reason]._", content)

    def test_appends_multiple_exceptions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "q-learned.md"
            _write_kb(kb_path)
            q_learn.append_accepted_exception(kb_path, "v-001", reason="reason one")
            q_learn.append_accepted_exception(kb_path, "v-002", reason="reason two")
            content = kb_path.read_text(encoding="utf-8")
            self.assertIn("reason one", content)
            self.assertIn("reason two", content)

    def test_includes_rule_id_in_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "q-learned.md"
            _write_kb(kb_path)
            q_learn.append_accepted_exception(
                kb_path, "v-001", reason="ok", rule_id="SEC-001", file_path="tests/mock.py"
            )
            content = kb_path.read_text(encoding="utf-8")
            self.assertIn("SEC-001", content)
            self.assertIn("tests/mock.py", content)

    def test_includes_path_pattern_when_file_given(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "q-learned.md"
            _write_kb(kb_path)
            # Patch get_path_pattern to return a predictable value
            with patch.object(q_learn, "get_path_pattern", return_value="tests/fixtures/**"):
                q_learn.append_accepted_exception(
                    kb_path, "v-001", reason="test mock",
                    file_path="tests/fixtures/mock.py"
                )
            content = kb_path.read_text(encoding="utf-8")
            self.assertIn("tests/fixtures/**", content)


class TestGetPathPattern(unittest.TestCase):

    def test_empty_path_returns_none(self):
        self.assertIsNone(q_learn.get_path_pattern(""))

    def test_none_like_empty_string(self):
        self.assertIsNone(q_learn.get_path_pattern(None))

    def test_returns_string_ending_with_glob(self):
        # Mock git to return a repo root
        with patch("subprocess.run") as mock_run:
            import subprocess
            mock_run.return_value = type("R", (), {
                "returncode": 0,
                "stdout": "/repo\n",
            })()
            result = q_learn.get_path_pattern("/repo/tests/fixtures/mock.py")
            # Should end with /**
            if result:
                self.assertTrue(result.endswith("/**"), f"Expected /**-ending pattern, got: {result}")

    def test_fallback_when_git_fails(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
            result = q_learn.get_path_pattern("/some/dir/file.py")
            # Fallback: parent dir + /**
            if result:
                self.assertTrue(result.endswith("/**"))


class TestTightenRule(unittest.TestCase):

    def _make_domain_doc(self, tmpdir, rule_id="SEC-001"):
        """Create a minimal domain doc with a User Feedback History section."""
        doc_path = Path(tmpdir) / "domains" / "security.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(
            f"# Domain: Security\n\n"
            f"**Owner**: q\n**Review Cadence**: quarterly\n**Last Updated**: 2026-01-01\n\n"
            f"---\n\n"
            f"## {rule_id}: No Hardcoded Credentials\n\n"
            f"**Severity**: P0\n\nDescription here.\n\n"
            f"### User Feedback History\n"
            f"_No entries yet._\n",
            encoding="utf-8",
        )
        return doc_path

    def _make_config(self, tmpdir):
        return {
            "kb_path": str(tmpdir),
            "personal_kb_path": str(Path(tmpdir) / "personal" / "q-learned.md"),
            "team_exceptions_path": str(Path(tmpdir) / "team" / "exceptions" / "approved.md"),
        }

    def test_appends_to_feedback_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            doc = self._make_domain_doc(tmpdir)
            cfg = self._make_config(tmpdir)
            result = q_learn.tighten_rule("SEC-001", "Mock credentials in fixtures are OK", cfg)
            self.assertTrue(result)
            content = doc.read_text(encoding="utf-8")
            self.assertIn("Mock credentials in fixtures are OK", content)

    def test_replaces_placeholder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_domain_doc(tmpdir)
            cfg = self._make_config(tmpdir)
            q_learn.tighten_rule("SEC-001", "First feedback entry", cfg)
            doc = Path(tmpdir) / "domains" / "security.md"
            content = doc.read_text(encoding="utf-8")
            self.assertNotIn("_No entries yet._", content)
            self.assertIn("First feedback entry", content)

    def test_unknown_rule_returns_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_domain_doc(tmpdir)
            cfg = self._make_config(tmpdir)
            result = q_learn.tighten_rule("NONEXISTENT-999", "some feedback", cfg)
            self.assertFalse(result)

    def test_multiple_feedbacks_accumulate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            doc = self._make_domain_doc(tmpdir)
            cfg = self._make_config(tmpdir)
            q_learn.tighten_rule("SEC-001", "First entry", cfg)
            q_learn.tighten_rule("SEC-001", "Second entry", cfg)
            content = doc.read_text(encoding="utf-8")
            self.assertIn("First entry", content)
            self.assertIn("Second entry", content)


if __name__ == "__main__":
    unittest.main()
