# Domain: Error Handling

**Owner**: q  
**Review Cadence**: On every NEW DISCOVERY  
**Last Updated**: 2026-04-13  
**Health**: GREEN

---

## ERR-001: Silent Exception Catch

**Severity**: P1  
**Pattern**: Bare except clause or catch block with no action (pass, continue, or empty body)  
**Keywords**: except, catch, try  
**Languages**: All  

A `try/except` or `try/catch` block where the exception handler body is `pass`,
`continue`, an empty block `{}`, or contains only a comment. Silent catches hide bugs
by swallowing errors — the program continues as if nothing happened, often producing
incorrect results downstream.

**Exceptions**:
- `except KeyboardInterrupt: pass` (intentionally ignoring user interrupt)
- `except StopIteration: pass` (iterator protocol — intentional)
- `except FileNotFoundError: pass` when the intent is "file is optional" AND a comment says so

### User Feedback History
_No entries yet._

---

## ERR-002: Catching Base Exception

**Severity**: P1  
**Pattern**: `except Exception`, `except BaseException`, or `catch (error)` with no type filter  
**Keywords**: except Exception, except BaseException, catch (  
**Languages**: Python, TypeScript, JavaScript  

Catching the base `Exception` class (or `BaseException`) without re-raising or
specifically handling it. This catches programming errors (AttributeError, TypeError,
NameError) alongside expected runtime errors, masking bugs that should be fixed.

**Exceptions**:
- Top-level error handlers in servers/CLI entry points that log and re-raise or exit
- Error boundaries that explicitly log the full stack trace
- `except Exception as e: log.error(e); raise` — re-raise is acceptable

### User Feedback History
_No entries yet._

---

## ERR-003: Missing Error Propagation

**Severity**: P2  
**Pattern**: Function returns None or a default value on error without signaling the caller  
**Keywords**: return None, return {}, return [], return False  
**Languages**: All  

A function that catches an exception and returns `None`, `False`, `{}`, or `[]` without
any logging or raising. The caller receives a falsy value but has no way to know an
error occurred — this is a form of silent failure that makes debugging very difficult.

**Exceptions**:
- Functions explicitly documented as returning None on not-found (lookup functions)
- Parse/try functions where None-return is the documented contract

### User Feedback History
_No entries yet._

---

## ERR-004: Error Swallowed Before Cleanup

**Severity**: P1  
**Pattern**: Resource opened without `finally` block or context manager for cleanup  
**Keywords**: open(, socket, connection, cursor, session, lock  
**Languages**: Python, Go, Java  

A file, socket, database connection, or lock that is opened/acquired without a
`with` statement (Python) or `defer` (Go) or `finally` block (Java/C#). If an exception
is raised between open and close, the resource leaks.

**Exceptions**:
- Resources managed by frameworks that handle cleanup (e.g., Flask request context)
- Class constructors where the resource is stored and closed in `__del__` with a comment

### User Feedback History
_No entries yet._

---

## ERR-005: TODO / FIXME in Error Handler

**Severity**: P3  
**Pattern**: TODO or FIXME comment inside an exception handler  
**Keywords**: TODO, FIXME, HACK, XXX  
**Languages**: All  

A `TODO` or `FIXME` comment inside an exception handler indicates that error handling
is known to be incomplete. P3 — logged silently, no interrupt.

### User Feedback History
_No entries yet._

---

## ERR-006: Unhandled Promise Rejection

**Severity**: P1  
**Pattern**: Async function called without await and without .catch()  
**Keywords**: async, Promise, .then(, fetch(, axios  
**Languages**: JavaScript, TypeScript  

An async function call (or Promise-returning function) that is not `await`-ed and has
no `.catch()` handler. Unhandled rejections silently swallow errors in Node.js and
browsers, making failures invisible and debugging extremely difficult.

**Safe patterns**:
- `await asyncFn()` inside an async context
- `asyncFn().catch(err => logger.error(err))`
- `Promise.all([...]).catch(...)`

**Exceptions**:
- Fire-and-forget background tasks that explicitly document they don't need error handling
- Top-level `process.on('unhandledRejection', ...)` handler present and documented

### User Feedback History
_No entries yet._

---

## ERR-007: Missing Timeout on External Calls

**Severity**: P1  
**Pattern**: HTTP request, database query, or subprocess call without an explicit timeout  
**Keywords**: requests.get, requests.post, fetch(, urllib, subprocess.run, execute(  
**Languages**: All  

An external call (HTTP, database, subprocess) with no explicit timeout. Without a
timeout, a slow or hanging dependency will block the caller indefinitely, consuming
a thread/connection and eventually exhausting the pool.

**Safe patterns**:
- `requests.get(url, timeout=5)`
- `fetch(url, { signal: AbortSignal.timeout(5000) })`
- `subprocess.run(cmd, timeout=30)`

**Exceptions**:
- Background jobs explicitly designed to run without time constraints (must be documented)
- Database connections managed by a connection pool with its own timeout configured

### User Feedback History
_No entries yet._

---

## ERR-008: Swallowing Partial Failure in Batch Operations

**Severity**: P2  
**Pattern**: Loop over items where exceptions are caught per-item but failures are not reported  
**Keywords**: for, while, try, except, catch  
**Languages**: All  

A batch loop that catches exceptions per item with `pass` or silent continue — the
caller receives no signal that some items failed. This produces partial results that
look complete.

**Safe pattern**: Accumulate failures and either raise after the loop or return them
alongside results: `return {"success": results, "failed": failures}`

**Exceptions**:
- Idempotent retry loops where per-item failure is expected and retried
- Logging pipelines where individual event failure should not halt processing (must log failures)

### User Feedback History
_No entries yet._
