# Domain: Testing

**Owner**: q  
**Review Cadence**: On every NEW DISCOVERY  
**Last Updated**: 2026-04-13  
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

---

## TEST-005: No Assertion in Test

**Severity**: P2  
**Pattern**: Test function that calls code but makes no assertion  
**Keywords**: def test_, it(, describe(, @Test  
**Languages**: All  

A test function that exercises code but contains no `assert`, `expect`, `assertEqual`,
or `verify` call. The test will always pass regardless of what the code does — it
provides false coverage confidence.

**Exceptions**:
- Tests that intentionally verify no exception is raised (must have a comment explaining this)
- Smoke tests that check a process runs without checking output (must be in a clearly named `smoke_tests/` directory)

### User Feedback History
_No entries yet._

---

## TEST-006: Test Contains Real Credentials or PII

**Severity**: P0  
**Pattern**: Real-looking email addresses, phone numbers, SSNs, or API keys in test fixtures  
**Keywords**: @gmail.com, @yahoo.com, @hotmail.com, 555-, SSN, card_number  
**Languages**: All  

Test fixtures containing real-format PII (valid email domains, realistic phone numbers,
social security numbers, real-looking API keys). Even in test data, real-format PII
creates compliance risk, accidentally leaks into logs, and confuses production data
audits.

**Safe pattern**: Use clearly fake formats: `test@example.com`, `555-0100`, `xxx-xx-0000`

**Exceptions**:
- Example.com, example.org, example.net email addresses (RFC 2606 reserved)
- Synthetic data generation libraries where fake-ness is guaranteed by the generator

### User Feedback History
_No entries yet._

---

## TEST-007: Mocking What You Don't Own

**Severity**: P2  
**Pattern**: Tests that mock third-party library internals or standard library classes  
**Keywords**: mock.patch, jest.mock, sinon.stub, MagicMock  
**Languages**: Python, JavaScript, TypeScript  

Tests that mock internal methods of third-party libraries (e.g., patching `requests.Session._send`)
are testing implementation details of code you don't control. When the library updates,
the mocks break even if your code is correct. Prefer mocking at the boundary your code
controls — the function that calls the library, not inside it.

**Safe pattern**: Mock the wrapper function in your own code, not the library internals.
Use contract tests or recorded HTTP responses (VCR, responses library) for external services.

**Exceptions**:
- Standard library builtins that are genuinely the boundary (e.g., `open()` for file I/O tests)
- Libraries your team owns and maintains

### User Feedback History
_No entries yet._
