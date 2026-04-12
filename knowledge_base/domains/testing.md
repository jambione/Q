# Domain: Testing

**Owner**: q  
**Review Cadence**: On every NEW DISCOVERY  
**Last Updated**: 2026-04-12  
**Health**: GREEN

---

## TEST-001: New Public Function Without Tests

**Severity**: P2  
**Pattern**: A new public function or method added without a corresponding test file change  
**Keywords**: def , public , function , export  
**Languages**: Python, TypeScript, JavaScript, Go, Java, C#  

When a diff adds a new public function or method in a non-test file, check whether
any test file was also changed in the same diff. If no test file appears in the diff,
flag as a reminder that the new function has no test coverage.

**Exceptions**:
- Private/internal functions (prefixed with `_`, `__`, or marked `private`/`internal`)
- Pure configuration functions (no logic, just returns constants)
- Abstract interface definitions
- The diff is already a test file itself

### User Feedback History
_No entries yet._

---

## TEST-002: Test Asserting Only One Outcome Path

**Severity**: P3  
**Pattern**: Test functions that test only the happy path with no error/edge case  
**Keywords**: def test_, it(, describe(, @Test  
**Languages**: Python, TypeScript, JavaScript, Java  

A test file where every test function only asserts the success case (no `assertRaises`,
`expect(...).toThrow`, `try/catch`, or similar) suggests that error paths are untested.
P3 only — log silently.

**Exceptions**:
- Tests explicitly named `test_happy_path` or `test_success_*`
- Integration smoke tests intentionally covering only the success path

### User Feedback History
_No entries yet._

---

## TEST-003: Skipped or Commented-Out Tests

**Severity**: P2  
**Pattern**: Tests marked as skipped, xfail, or commented out without explanation  
**Keywords**: @skip, @pytest.mark.skip, xit(, xdescribe(, it.skip, test.skip  
**Languages**: Python, TypeScript, JavaScript, Java  

Skipped tests that have no associated comment explaining why they are skipped and
when they will be un-skipped. Skipped tests that have been in the codebase for more
than one sprint without resolution are a sign that the test suite is degrading.

**Exceptions**:
- Skip decorators with a clear reason string: `@pytest.mark.skip(reason="pending JIRA-123")`
- `xfail` in pytest with strict=True (expected failure, explicitly managed)

### User Feedback History
_No entries yet._

---

## TEST-004: Test Importing From Production Internals

**Severity**: P2  
**Pattern**: Test file importing private/internal module members  
**Keywords**: import _, from _internal, from _private  
**Languages**: Python, TypeScript  

If a test file imports symbols that begin with `_` (Python convention for private) or
from modules named `_internal` or `_private`, the tests are coupled to implementation
details. This makes refactoring break tests even when behavior is unchanged.

**Exceptions**:
- Test utilities or fixtures that are intentionally internal (`conftest.py`, `test_helpers.py`)

### User Feedback History
_No entries yet._
