# Domain: Performance

**Owner**: q  
**Review Cadence**: On every NEW DISCOVERY  
**Last Updated**: 2026-04-13  
**Health**: GREEN

---

## PERF-001: N+1 Query Pattern

**Severity**: P1  
**Pattern**: Database query inside a loop  
**Keywords**: for, while, forEach, map, each, loop, query, execute, find, get  
**Languages**: Python, TypeScript, JavaScript, Ruby, Java  

A database call (ORM method, raw query, `execute()`, `find()`, `get()`) placed inside
a `for`, `while`, `forEach`, or `.map()` loop. Each iteration issues a separate query,
causing O(n) database round trips.

The fix is to batch the query outside the loop and look up results from a dict/map.

**Exceptions**:
- Loops with explicit pagination or cursor-based continuation (designed to page through results)
- Loops iterating over a fixed small constant (e.g., `for i in range(3)`)
- ORMs with explicit `.prefetch_related()` / `.include()` / `.eager_load()` calls above the loop

### User Feedback History
_No entries yet._

---

## PERF-002: Unbounded Collection Growth

**Severity**: P2  
**Pattern**: Appending to a list/array in a loop with no size limit  
**Keywords**: append, push, extend, +=, accumulate  
**Languages**: All  

A list or array that is `.append()`-ed or `.push()`-ed to inside a loop with no
size check or limit. If the input is unbounded, the collection will grow without
bound and eventually exhaust memory.

**Exceptions**:
- Processing a known finite dataset (e.g., reading a fixed file)
- Collections with explicit `if len(x) > MAX_SIZE: break` guards

### User Feedback History
_No entries yet._

---

## PERF-003: Synchronous I/O in Async Context

**Severity**: P1  
**Pattern**: Blocking file or network call inside an async function  
**Keywords**: async def, async function, await, open(, requests.get, urllib  
**Languages**: Python, TypeScript, JavaScript  

An `async` function that calls blocking I/O (`open()`, `requests.get()`, `urllib.request`,
`time.sleep()`, blocking socket operations) without `await`. This blocks the event loop
and degrades throughput for all concurrent operations.

**Exceptions**:
- Functions explicitly documented as "sync wrapper for async" with a clear design note
- CLI scripts that are not part of an async service

### User Feedback History
_No entries yet._

---

## PERF-004: Large Object Serialization in Hot Path

**Severity**: P2  
**Pattern**: JSON serialization of large objects in a tight loop or request handler  
**Keywords**: json.dumps, JSON.stringify, serialize, marshal  
**Languages**: Python, TypeScript, JavaScript  

`json.dumps()` or `JSON.stringify()` called on a large data structure inside a loop
or in a per-request handler that is called frequently. Serialization is CPU-bound and
can become a bottleneck at scale.

**Exceptions**:
- One-time startup serialization
- Serialization of small config objects

### User Feedback History
_No entries yet._

---

## PERF-005: Event Listener Leak

**Severity**: P1  
**Pattern**: Event listener added without corresponding removal  
**Keywords**: addEventListener, on(, addListener, subscribe, .on('  
**Languages**: JavaScript, TypeScript  

An `addEventListener` or `.on()` call in a component, class, or module without a
corresponding `removeEventListener` or `.off()` in the cleanup path (componentWillUnmount,
destructor, unsubscribe). Each mount without unmount adds a listener that is never
removed, causing memory leaks and duplicate handler execution.

**Exceptions**:
- Module-level listeners intentionally registered once for the application lifetime
- Listeners registered inside a cleanup function that is itself called on teardown

### User Feedback History
_No entries yet._

---

## PERF-006: Regex Compiled in Hot Path

**Severity**: P2  
**Pattern**: Regular expression literal or re.compile() inside a loop or frequently-called function  
**Keywords**: re.compile, new RegExp, re.match, re.search, re.findall  
**Languages**: Python, JavaScript, TypeScript  

A `re.compile()` call or regex literal (`/pattern/`) inside a loop body or a function
called on every request/event. Regex compilation is expensive — compile once at module
level and reuse the compiled object.

**Safe pattern**:
```python
# Module level
PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}')

def parse_date(text):
    return PATTERN.search(text)
```

**Exceptions**:
- Dynamic patterns that must be constructed from runtime values (no choice but to compile dynamically)
- One-time startup code

### User Feedback History
_No entries yet._

---

## PERF-007: String Concatenation in Loop

**Severity**: P2  
**Pattern**: String built by concatenation inside a loop rather than join()  
**Keywords**: += , str +, string +, concat  
**Languages**: Python, JavaScript, TypeScript, Java  

Building a string with `+=` inside a loop creates a new string object on every iteration
(O(n²) time complexity). Use `''.join(parts)` in Python, `Array.join()` in JavaScript,
or a `StringBuilder` in Java.

**Exceptions**:
- Loops with a known small constant number of iterations (≤ 5)
- Template literal accumulation where readability outweighs performance concern

### User Feedback History
_No entries yet._
