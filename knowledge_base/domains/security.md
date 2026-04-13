# Domain: Security

**Owner**: q  
**Review Cadence**: On every NEW DISCOVERY  
**Last Updated**: 2026-04-13  
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

---

## SEC-006: Path Traversal Vulnerability

**Severity**: P1  
**Pattern**: User-controlled input used directly in file path construction  
**Keywords**: open(, os.path.join, path.join, readFile, fs.open, __file__  
**Languages**: Python, JavaScript, TypeScript, Go, Java  

Any call to `open()`, `os.path.join()`, `path.join()`, or `fs.readFile()` where the
path argument includes a variable that originates from user input (request params,
form data, URL segments) without sanitization. Attackers can inject `../` sequences
to access files outside the intended directory.

**Safe pattern**: Resolve the path and verify it starts with the expected base directory:
`resolved = os.path.realpath(user_path); assert resolved.startswith(BASE_DIR)`

**Exceptions**:
- Paths constructed entirely from constants or config values
- Framework-managed static file serving (Flask send_from_directory, Express static)

### User Feedback History
_No entries yet._

---

## SEC-007: Server-Side Request Forgery (SSRF)

**Severity**: P1  
**Pattern**: HTTP request made to a URL derived from user input  
**Keywords**: requests.get, requests.post, fetch(, urllib, http.get, axios  
**Languages**: Python, JavaScript, TypeScript, Go, Java  

An outbound HTTP request where the URL includes a variable that could originate from
user input. SSRF allows attackers to make the server issue requests to internal
infrastructure (metadata services, internal APIs, localhost).

**Safe pattern**: Validate the URL against an allowlist of permitted domains before making the request.

**Exceptions**:
- URLs constructed entirely from constants
- Webhook callbacks where the URL is stored at registration time by an authenticated user and validated on storage

### User Feedback History
_No entries yet._

---

## SEC-008: JWT Without Expiry

**Severity**: P1  
**Pattern**: JWT token created without an expiration claim  
**Keywords**: jwt.encode, jwt.sign, JsonWebToken, PyJWT, token  
**Languages**: Python, JavaScript, TypeScript, Java  

A JWT token signed without an `exp` (expiration) claim. Tokens without expiry never
become invalid — a leaked token grants permanent access. Always set `exp` to a short
window appropriate for the token's use: 15 minutes for access tokens, longer for
refresh tokens (which should be rotatable).

**Exceptions**:
- API keys intentionally designed as long-lived (must be documented and rotatable)
- Internal service-to-service tokens with explicit justification

### User Feedback History
_No entries yet._

---

## SEC-009: Insecure Direct Object Reference (IDOR)

**Severity**: P1  
**Pattern**: Resource fetched by ID from user input without ownership check  
**Keywords**: find_by_id, get_by_id, findById, objects.get, Model.get  
**Languages**: All  

A database lookup using an ID that comes from user input (URL params, request body)
with no check that the requesting user owns or has permission to access that record.
Attackers can enumerate IDs to access other users' data.

**Safe pattern**: Always scope queries to the authenticated user:
`obj = Model.objects.get(id=user_id, owner=request.user)`

**Exceptions**:
- Public resources genuinely accessible to all authenticated users
- Admin endpoints with explicit role-check middleware documented above the handler

### User Feedback History
_No entries yet._
