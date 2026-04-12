# Q Knowledge Base Index

**Owner**: q  
**Last Updated**: 2026-04-12

> This index lists all KB documents. Every document must have a row here.
> q-validate.py enforces this — missing entries fail the validation check.

---

## Domain Documents

| Document | Description | Severity Range | Last Updated | Owner |
|----------|-------------|---------------|-------------|-------|
| [security.md](domains/security.md) | Credentials, injection, SSL, permissions | P0–P2 | 2026-04-12 | q |
| [architecture.md](domains/architecture.md) | Circular deps, layering, god classes, magic values | P1–P2 | 2026-04-12 | q |
| [testing.md](domains/testing.md) | Missing tests, skipped tests, internal coupling | P2–P3 | 2026-04-12 | q |
| [performance.md](domains/performance.md) | N+1 queries, unbounded growth, blocking async | P1–P2 | 2026-04-12 | q |
| [error-handling.md](domains/error-handling.md) | Silent catches, base exceptions, resource leaks | P1–P3 | 2026-04-12 | q |

## Learned Documents

| Document | Description | Last Updated | Owner |
|----------|-------------|-------------|-------|
| [q-learned.md](learned/q-learned.md) | User-confirmed exceptions and overrides (grows over time) | 2026-04-12 | q-memory |

## Verdict Registry

| Document | Description | Last Updated | Owner |
|----------|-------------|-------------|-------|
| [verdicts/index.md](verdicts/index.md) | All Q verdicts (date, file, rule, severity, outcome) | 2026-04-12 | q |

---

## Rule ID Reference

| Rule ID | Domain | Severity | Summary |
|---------|--------|----------|---------|
| SEC-001 | Security | P0 | No hardcoded credentials |
| SEC-002 | Security | P1 | SQL injection via string interpolation |
| SEC-003 | Security | P1 | Sensitive data in logs |
| SEC-004 | Security | P0 | Disabled SSL/security controls |
| SEC-005 | Security | P2 | Overly permissive file permissions |
| ARCH-001 | Architecture | P1 | Circular import |
| ARCH-002 | Architecture | P1 | Business logic in data layer |
| ARCH-003 | Architecture | P2 | God class / god function |
| ARCH-004 | Architecture | P2 | Direct cross-layer dependency |
| ARCH-005 | Architecture | P2 | Hardcoded configuration values |
| TEST-001 | Testing | P2 | New public function without tests |
| TEST-002 | Testing | P3 | Test covers only happy path |
| TEST-003 | Testing | P2 | Skipped or commented-out tests |
| TEST-004 | Testing | P2 | Test imports production internals |
| PERF-001 | Performance | P1 | N+1 query pattern |
| PERF-002 | Performance | P2 | Unbounded collection growth |
| PERF-003 | Performance | P1 | Blocking I/O in async context |
| PERF-004 | Performance | P2 | Large object serialization in hot path |
| ERR-001 | Error Handling | P1 | Silent exception catch |
| ERR-002 | Error Handling | P1 | Catching base exception |
| ERR-003 | Error Handling | P2 | Missing error propagation |
| ERR-004 | Error Handling | P1 | Resource opened without cleanup guard |
| ERR-005 | Error Handling | P3 | TODO/FIXME in error handler |
