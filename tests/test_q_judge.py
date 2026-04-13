"""
Unit tests for q-judge.py — judgment helpers and JSON extraction.

Run: python -m unittest tests/test_q_judge.py
"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

# q-judge.py has a hyphen — load it by file path
_scripts = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_scripts))
_spec = importlib.util.spec_from_file_location("q_judge", _scripts / "q-judge.py")
q_judge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q_judge)


class TestExtractJson(unittest.TestCase):

    def test_pure_json_object(self):
        result = q_judge.extract_json('{"flagged": false}')
        self.assertEqual(result, {"flagged": False})

    def test_json_with_preamble(self):
        result = q_judge.extract_json('Here is my verdict:\n{"flagged": true, "severity": "P1"}')
        self.assertTrue(result["flagged"])
        self.assertEqual(result["severity"], "P1")

    def test_json_with_postamble(self):
        result = q_judge.extract_json('{"flagged": false}\n\nLet me know if you need more.')
        self.assertEqual(result, {"flagged": False})

    def test_nested_json_object(self):
        raw = '{"flagged": true, "details": {"rule": "SEC-001", "line": 42}}'
        result = q_judge.extract_json(raw)
        self.assertTrue(result["flagged"])
        self.assertEqual(result["details"]["rule"], "SEC-001")

    def test_full_verdict_json(self):
        raw = '{"flagged": true, "severity": "P0", "rule_id": "SEC-001", "message": "API key assigned."}'
        result = q_judge.extract_json(raw)
        self.assertEqual(result["severity"], "P0")
        self.assertEqual(result["rule_id"], "SEC-001")

    def test_invalid_json_returns_not_flagged(self):
        result = q_judge.extract_json("this is not JSON at all")
        self.assertEqual(result, {"flagged": False})

    def test_empty_string_returns_not_flagged(self):
        result = q_judge.extract_json("")
        self.assertEqual(result, {"flagged": False})

    def test_unclosed_brace_returns_not_flagged(self):
        result = q_judge.extract_json('{"flagged": true, "severity":')
        self.assertEqual(result, {"flagged": False})

    def test_confidence_and_fix_fields_pass_through(self):
        raw = '{"flagged": true, "severity": "P1", "rule_id": "ERR-001", "message": "Silent catch.", "confidence": 0.92, "suggested_fix": "Log the exception."}'
        result = q_judge.extract_json(raw)
        self.assertEqual(result['confidence'], 0.92)
        self.assertEqual(result['suggested_fix'], 'Log the exception.')


class TestGetRelevantDomains(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        domains_dir = Path(self.tmpdir) / "domains"
        domains_dir.mkdir()
        (domains_dir / "security.md").write_text("# Security Rules\n## SEC-001: Hardcoded credentials\n", encoding="utf-8")
        (domains_dir / "performance.md").write_text("# Performance Rules\n## PERF-001: N+1 query\n", encoding="utf-8")

    def test_security_keyword_routes_to_security_doc(self):
        diff = "+  api_key = 'abc123'\n"
        result = q_judge.get_relevant_domains(diff, self.tmpdir)
        self.assertIn("security.md", result)
        self.assertNotIn("performance.md", result)

    def test_sql_keyword_routes_to_security_doc(self):
        diff = "+  cursor.execute(f'SELECT * FROM users WHERE id={user_id}')\n"
        result = q_judge.get_relevant_domains(diff, self.tmpdir)
        self.assertIn("security.md", result)

    def test_loop_keyword_routes_to_performance_doc(self):
        diff = "+  for item in queryset:\n+    obj = Model.objects.get(id=item.id)\n"
        result = q_judge.get_relevant_domains(diff, self.tmpdir)
        self.assertIn("performance.md", result)

    def test_generic_diff_matches_nothing(self):
        diff = "+  x = 1\n+  y = 2\n"
        result = q_judge.get_relevant_domains(diff, self.tmpdir)
        self.assertEqual(len(result), 0)

    def test_missing_domains_dir_returns_empty(self):
        result = q_judge.get_relevant_domains("password = 'abc'", "/nonexistent/path")
        self.assertEqual(result, {})


class TestBuildSystemPrompt(unittest.TestCase):

    def test_contains_required_format_fields(self):
        prompt = q_judge.build_system_prompt()
        self.assertIn('"flagged"', prompt)
        self.assertIn('"severity"', prompt)
        self.assertIn('"rule_id"', prompt)
        self.assertIn("P0", prompt)
        self.assertIn("P1", prompt)

    def test_does_not_invent_rules_instruction(self):
        prompt = q_judge.build_system_prompt()
        self.assertIn("Never invent rules", prompt)


class TestBuildUserPrompt(unittest.TestCase):

    def test_includes_file_path(self):
        prompt = q_judge.build_user_prompt("auth.py", "+api_key='x'\n", {}, "")
        self.assertIn("auth.py", prompt)

    def test_includes_diff(self):
        prompt = q_judge.build_user_prompt("auth.py", "+api_key='secret'\n", {}, "")
        self.assertIn("+api_key='secret'", prompt)

    def test_includes_domain_docs_when_provided(self):
        docs = {"security.md": "# Security Rules\nSEC-001: ..."}
        prompt = q_judge.build_user_prompt("auth.py", "+x=1\n", docs, "")
        self.assertIn("KNOWLEDGE BASE", prompt)
        self.assertIn("security.md", prompt)

    def test_includes_learned_exceptions_when_provided(self):
        learned = "## Accepted Exceptions\n### 2026-01-01 — SEC-001\nUser override: test fixture\n"
        prompt = q_judge.build_user_prompt("tests/mock.py", "+pw='fake'\n", {}, learned)
        self.assertIn("LEARNED EXCEPTIONS", prompt)
        self.assertIn("test fixture", prompt)

    def test_no_domain_section_when_empty(self):
        prompt = q_judge.build_user_prompt("file.py", "+x=1\n", {}, "")
        self.assertNotIn("KNOWLEDGE BASE", prompt)

    def test_no_exceptions_section_when_empty(self):
        prompt = q_judge.build_user_prompt("file.py", "+x=1\n", {}, "")
        self.assertNotIn("LEARNED EXCEPTIONS", prompt)


class TestFormatVerdictOutput(unittest.TestCase):

    def test_clean_verdict_shows_checkmark(self):
        output = q_judge.format_verdict_output("app.py", {"flagged": False}, "v-001")
        self.assertIn("✓", output)
        self.assertIn("app.py", output)

    def test_p0_verdict_shows_red_icon(self):
        verdict = {"flagged": True, "severity": "P0", "rule_id": "SEC-001", "message": "API key."}
        output = q_judge.format_verdict_output("app.py", verdict, "v-001")
        self.assertIn("🔴", output)
        self.assertIn("P0", output)
        self.assertIn("SEC-001", output)

    def test_p1_verdict_shows_orange_icon(self):
        verdict = {"flagged": True, "severity": "P1", "rule_id": "ARCH-001", "message": "Circular import."}
        output = q_judge.format_verdict_output("module.py", verdict, "v-002")
        self.assertIn("🟠", output)

    def test_verdict_contains_message(self):
        verdict = {"flagged": True, "severity": "P1", "rule_id": "ERR-001", "message": "Silent exception catch."}
        output = q_judge.format_verdict_output("handler.py", verdict, "v-003")
        self.assertIn("Silent exception catch", output)

    def test_verdict_shows_suggested_fix(self):
        verdict = {
            "flagged": True, "severity": "P0", "rule_id": "SEC-001",
            "message": "Hardcoded credential.", "suggested_fix": "Use os.getenv('API_KEY')"
        }
        output = q_judge.format_verdict_output("auth.py", verdict, "v-001")
        self.assertIn("os.getenv", output)


class TestDeterministicPrecheck(unittest.TestCase):

    def test_hardcoded_password_flagged(self):
        diff = "+password = 'supersecret123'\n"
        result = q_judge.deterministic_precheck(diff)
        self.assertIsNotNone(result)
        self.assertTrue(result['flagged'])
        self.assertEqual(result['rule_id'], 'SEC-001')
        self.assertEqual(result['severity'], 'P0')

    def test_placeholder_password_not_flagged(self):
        diff = "+password = 'YOUR_PASSWORD_HERE'\n"
        result = q_judge.deterministic_precheck(diff)
        self.assertIsNone(result)

    def test_env_var_not_flagged(self):
        diff = "+api_key = os.getenv('API_KEY')\n"
        result = q_judge.deterministic_precheck(diff)
        self.assertIsNone(result)

    def test_verify_false_flagged(self):
        diff = "+resp = requests.get(url, verify=False)\n"
        result = q_judge.deterministic_precheck(diff)
        self.assertIsNotNone(result)
        self.assertEqual(result['rule_id'], 'SEC-004')

    def test_silent_catch_flagged(self):
        diff = "+except Exception:\n+    pass\n"
        result = q_judge.deterministic_precheck(diff)
        self.assertIsNotNone(result)
        self.assertEqual(result['rule_id'], 'ERR-001')

    def test_removed_lines_ignored(self):
        # Only added lines (starting with +) should be checked
        diff = "-password = 'supersecret'\n+password = os.getenv('PASSWORD')\n"
        result = q_judge.deterministic_precheck(diff)
        self.assertIsNone(result)

    def test_empty_diff_returns_none(self):
        result = q_judge.deterministic_precheck("")
        self.assertIsNone(result)

    def test_precheck_includes_suggested_fix(self):
        diff = "+secret = 'abc123xyz'\n"
        result = q_judge.deterministic_precheck(diff)
        self.assertIsNotNone(result)
        self.assertIn('suggested_fix', result)
        self.assertIsInstance(result['suggested_fix'], str)
        self.assertGreater(len(result['suggested_fix']), 5)

    def test_precheck_confidence_is_1(self):
        diff = "+token = 'ghp_realtoken123456'\n"
        result = q_judge.deterministic_precheck(diff)
        self.assertIsNotNone(result)
        self.assertEqual(result['confidence'], 1.0)


if __name__ == "__main__":
    unittest.main()
