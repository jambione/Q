# Domain: Architecture

**Owner**: q  
**Review Cadence**: On every NEW DISCOVERY  
**Last Updated**: 2026-04-12  
**Health**: GREEN

---

## ARCH-001: Circular Import / Dependency

**Severity**: P1  
**Pattern**: Module A imports Module B which imports Module A  
**Keywords**: import, require, from  
**Languages**: Python, TypeScript, JavaScript  

Circular dependencies cause unpredictable initialization order, runtime errors, and
make code impossible to test in isolation. If a diff shows a new import that creates
a known cycle (A→B where B already imports A), flag it.

**Detection heuristic**: A imports something from a module that is higher in the call
hierarchy (e.g., a utility module importing from a feature module that depends on it).

**Exceptions**:
- Type-only imports in TypeScript (`import type { X }`) do not create runtime cycles
- `__init__.py` re-exports that consolidate a package

### User Feedback History
_No entries yet._

---

## ARCH-002: Business Logic in Data Layer

**Severity**: P1  
**Pattern**: Database models or repository classes containing domain rules, calculations, or workflow decisions  
**Keywords**: model, entity, repository, schema, orm  
**Languages**: All  

If a class whose name contains `Model`, `Entity`, `Repository`, `Schema`, or `Table`
contains methods that perform business calculations, apply discount logic, send
notifications, or make domain-level decisions, that logic belongs in a service layer.

**Exceptions**:
- Simple computed properties (full_name = first + last)
- Database-level constraints that are purely data integrity

### User Feedback History
_No entries yet._

---

## ARCH-003: God Class / God Function

**Severity**: P2  
**Pattern**: Single class or function exceeding clear complexity bounds  
**Keywords**: class, def, function  
**Languages**: All  

Flag when a single function exceeds 100 lines or a single class exceeds 500 lines in
a diff that adds to an already-large file. These are signals that Single Responsibility
Principle is being violated — one class or function is doing too many things.

**Exceptions**:
- Generated code (files with `# generated`, `// auto-generated`, or similar headers)
- Data transfer objects (DTOs) or config classes that are intentionally flat
- Test files where setup functions are naturally long

### User Feedback History
_No entries yet._

---

## ARCH-004: Direct Cross-Layer Dependency

**Severity**: P2  
**Pattern**: Presentation layer importing directly from data/persistence layer (skipping service layer)  
**Keywords**: controller, handler, route, view, component  
**Languages**: All  

If a class/file named `Controller`, `Handler`, `Route`, `View`, or `Component` imports
directly from a class/file named `Repository`, `DAO`, `Model`, or `Schema` without
going through a service or use-case layer, the layers are collapsing.

**Exceptions**:
- Simple CRUD apps explicitly built without a service layer
- Read-only projections where the query is the only logic

### User Feedback History
_No entries yet._

---

## ARCH-005: Hardcoded Configuration Values

**Severity**: P2  
**Pattern**: Magic numbers, URLs, timeouts, limits hardcoded inline in business logic  
**Keywords**: http://, https://, timeout, retry, limit, max, port  
**Languages**: All  

URLs, port numbers, timeout values, retry counts, or batch sizes written as literals
inside business logic functions. These should be constants (named, in a config module)
or read from environment/config files.

**Exceptions**:
- Standard port numbers used in comments for documentation
- Test files where hardcoded values are intentional fixtures

### User Feedback History
_No entries yet._
