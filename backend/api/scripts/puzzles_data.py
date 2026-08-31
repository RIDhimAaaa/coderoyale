"""Seed puzzle content.

Every puzzle is a *situational* problem framed around a real backend/infra scenario,
solved by reading stdin and writing stdout. `testcases` with is_sample=True are shown
to players; the rest are hidden and decide the match.

Each reference solution lives in the module docstring of its dict entry so the
expected outputs are auditable.
"""

RATE_LIMITER = {
    "topic": "dsa",
    "title": "Sliding-Window Rate Limiter",
    "difficulty": 2,
    "time_limit_s": 240,
    "prompt_md": """\
You are building the rate limiter that sits in front of a payments API.

A single client may make **at most `N` requests in any rolling 60-second window**.
You are given the ordered timestamps (integer seconds, non-decreasing) of the
requests arriving from one client. For each request, decide whether it is
`ALLOW`ed or `REJECT`ed.

- A request at time `t` is rejected if there are already `N` *allowed* requests
  with timestamp in the window `[t - 59, t]`.
- Rejected requests never executed, so they do **not** count toward later windows.

### Input
```
N
t1 t2 ... tk
```

### Output
One line: the verdict (`ALLOW` / `REJECT`) for each request, in order, space-separated.

### Example
```
Input:            Output:
2                 ALLOW ALLOW REJECT ALLOW
1 2 3 70
```
""",
    "starter_code": """\
import sys

def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    timestamps = list(map(int, data[1:]))
    # TODO: emit ALLOW / REJECT for each timestamp
    ...

main()
""",
    "testcases": [
        {"stdin": "2\n1 2 3 70\n", "expected": "ALLOW ALLOW REJECT ALLOW", "is_sample": True},
        {"stdin": "1\n5 20 65\n", "expected": "ALLOW REJECT ALLOW", "is_sample": True},
        {"stdin": "3\n1 1 1 1 1\n", "expected": "ALLOW ALLOW ALLOW REJECT REJECT", "is_sample": False},
        {
            "stdin": "2\n10 20 30 40 50 60 70 80\n",
            "expected": "ALLOW ALLOW REJECT REJECT REJECT REJECT ALLOW ALLOW",
            "is_sample": False,
        },
        {"stdin": "2\n100\n", "expected": "ALLOW", "is_sample": False},
    ],
}


IDEMPOTENCY = {
    "topic": "backend",
    "title": "Idempotent Webhook Processing",
    "difficulty": 1,
    "time_limit_s": 180,
    "prompt_md": """\
Your payment service receives webhook deliveries from an upstream provider that
**retries aggressively**, so the same event can arrive several times.

Each event has an idempotency `key` and an `amount` in cents. Process events in
the order received:

- The **first** time you see a key, charge that amount.
- Any later event whose key you have already processed is a duplicate delivery
  and must be **ignored** (do not charge again).

Print the total amount charged and how many duplicates you ignored.

### Input
```
M
key1 amount1
...
keyM amountM
```

### Output
```
charged <total-cents>
duplicates <count>
```
""",
    "starter_code": """\
import sys

def main() -> None:
    lines = sys.stdin.read().splitlines()
    m = int(lines[0])
    # TODO
    ...

main()
""",
    "testcases": [
        {"stdin": "3\nabc 100\nabc 100\ndef 250\n", "expected": "charged 350\nduplicates 1", "is_sample": True},
        {"stdin": "1\nx 999\n", "expected": "charged 999\nduplicates 0", "is_sample": True},
        {"stdin": "5\na 10\nb 20\na 10\nc 30\nb 20\n", "expected": "charged 60\nduplicates 2", "is_sample": False},
        {"stdin": "4\nk1 500\nk2 500\nk3 500\nk4 500\n", "expected": "charged 2000\nduplicates 0", "is_sample": False},
        {"stdin": "6\ns 1\ns 2\ns 3\ns 4\ns 5\ns 6\n", "expected": "charged 1\nduplicates 5", "is_sample": False},
    ],
}


DEADLOCK = {
    "topic": "dsa",
    "title": "Transaction Deadlock Detection",
    "difficulty": 2,
    "time_limit_s": 240,
    "prompt_md": """\
A database scheduler maintains a **waits-for graph**: an edge `a b` means
transaction `a` is blocked waiting on a lock currently held by transaction `b`.

The scheduler is **deadlocked if and only if this graph contains a cycle**
(a self-loop `a a` counts as a cycle).

Given the graph, print `OK` if there is no deadlock, or `DEADLOCK` otherwise.

### Input
```
P E
a1 b1
...
aE bE
```
`P` = number of transactions (ids `1..P`), `E` = number of waits-for edges.

### Output
`OK` or `DEADLOCK`
""",
    "starter_code": """\
import sys

def main() -> None:
    data = sys.stdin.read().split()
    p, e = int(data[0]), int(data[1])
    # edges follow as pairs
    ...

main()
""",
    "testcases": [
        {"stdin": "3 3\n1 2\n2 3\n3 1\n", "expected": "DEADLOCK", "is_sample": True},
        {"stdin": "3 2\n1 2\n2 3\n", "expected": "OK", "is_sample": True},
        {"stdin": "4 4\n1 2\n2 3\n3 4\n4 2\n", "expected": "DEADLOCK", "is_sample": False},
        {"stdin": "2 1\n1 1\n", "expected": "DEADLOCK", "is_sample": False},
        {"stdin": "5 0\n", "expected": "OK", "is_sample": False},
        {"stdin": "4 3\n1 2\n3 2\n4 2\n", "expected": "OK", "is_sample": False},
    ],
}


ALL_PUZZLES = [RATE_LIMITER, IDEMPOTENCY, DEADLOCK]
