# Domain: Performance

**Owner**: q  
**Review Cadence**: On every NEW DISCOVERY  
**Last Updated**: 2026-04-12  
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
