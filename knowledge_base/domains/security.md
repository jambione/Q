# Domain: Security

**Owner**: q  
**Review Cadence**: On every NEW DISCOVERY  
**Last Updated**: 2026-04-12  
**Health**: GREEN

---

## SEC-001: No Hardcoded Credentials

**Severity**: P0  
**Pattern**: API keys, passwords, tokens, secrets in string literals  
**Keywords**: password, api_key, secret, token, credential, auth, key  
**Languages**: All  

Any assignment where the left-hand side name contains `password`, `api_key`, `secret`,
`token`, `credential`, `private_key`, or `auth` and the right-hand side is a non-empty
string literal should be flagged. This includes all forms: `=`, `:`, `=>`.

**Exceptions**:
- Test fixture files (paths matching `test*/`, `spec*/`, `fixtures/`, `mock*`)
- Placeholder values that are clearly fake: `"YOUR_API_KEY_HERE"`, `"<secret>"`, `"xxx"`, `""`, `"changeme"`
- Environment variable reads: `os.getenv(...)`, `process.env.X`, `ENV["X"]`

### User Feedback History
_No entries yet. Updated by q-memory after user feedback._

---

## SEC-002: SQL Injection Risk

**Severity**: P1  
**Pattern**: String concatenation or f-string interpolation directly in SQL queries  
**Keywords**: SELECT, INSERT, UPDATE, DELETE, WHERE, execute, query, cursor  
**Languages**: Python, JavaScript, TypeScript, Java, C#, PHP, Ruby  

SQL strings that use `+`, `.format()`, `f"..."`, `%s` substitution, or template literals
to embed user-controlled variables directly into the query string. Safe patterns use
parameterized queries: `?`, `%s` as bound parameters, or an ORM.

**Exceptions**:
- Static SQL with no variable interpolation
- ORM query builders (SQLAlchemy, Prisma, ActiveRecord, Hibernate)
- Parameterized queries where variables appear only in the params argument

### User Feedback History
_No entries yet._

---

## SEC-003: Sensitive Data in Logs

**Severity**: P1  
**Pattern**: Logging statements that include password, token, key, or credit card variables  
**Keywords**: log, print, console.log, logger, logging  
**Languages**: All  

Any `print()`, `log.*()`, `console.log()`, or logger call where an argument variable name
contains `password`, `token`, `secret`, `key`, `ssn`, `card`, or `cvv`.

**Exceptions**:
- Debug logs explicitly wrapped in `if DEBUG:` or environment checks
- Logging the variable *name* as a string (not its value)

### User Feedback History
_No entries yet._

---

## SEC-004: Disabled Security Controls

**Severity**: P0  
**Pattern**: SSL verification disabled, certificate checks bypassed, security headers removed  
**Keywords**: verify=False, ssl_verify, checkCertificate, DISABLE_SSL, no-verify  
**Languages**: All  

`verify=False` in requests/urllib calls, `ssl._create_unverified_context()`,
`rejectUnauthorized: false` in Node.js, or any comment/flag explicitly disabling
certificate validation or security checks.

**Exceptions**:
- Local development configs explicitly scoped to `localhost` or `127.0.0.1`
- Test environments where the comment clearly indicates intent and scope

### User Feedback History
_No entries yet._

---

## SEC-005: Overly Permissive File Permissions

**Severity**: P2  
**Pattern**: `chmod 777`, `chmod 0o777`, world-writable file creation  
**Keywords**: chmod, permissions, 0777, 0o777  
**Languages**: Python, Shell, Go  

File permission values of `777`, `0777`, or `0o777`. Acceptable values are `0o644` for
files and `0o755` for executables.

### User Feedback History
_No entries yet._
