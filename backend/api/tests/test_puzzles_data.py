"""The seed puzzle bank must be internally consistent: a correct reference
solution has to reproduce every expected output (samples and hidden alike).

If a puzzle is added to puzzles_data.ALL_PUZZLES without a reference solver here,
this test fails on purpose.
"""
import pytest

from scripts.puzzles_data import ALL_PUZZLES


def _rate_limiter(inp: str) -> str:
    data = inp.split()
    n, ts = int(data[0]), list(map(int, data[1:]))
    accepted: list[int] = []
    out = []
    for t in ts:
        while accepted and accepted[0] <= t - 60:
            accepted.pop(0)
        if len(accepted) < n:
            accepted.append(t)
            out.append("ALLOW")
        else:
            out.append("REJECT")
    return " ".join(out)


def _idempotency(inp: str) -> str:
    lines = inp.splitlines()
    seen: set[str] = set()
    charged = dups = 0
    for row in lines[1 : int(lines[0]) + 1]:
        key, amount = row.split()
        if key in seen:
            dups += 1
        else:
            seen.add(key)
            charged += int(amount)
    return f"charged {charged}\nduplicates {dups}"


def _deadlock(inp: str) -> str:
    data = inp.split()
    p, e = int(data[0]), int(data[1])
    adj: dict[int, list[int]] = {i: [] for i in range(1, p + 1)}
    it = iter(data[2 : 2 + 2 * e])
    for a, b in zip(it, it):
        adj[int(a)].append(int(b))
    color = {i: 0 for i in range(1, p + 1)}

    def dfs(u: int) -> bool:
        color[u] = 1
        for v in adj[u]:
            if color[v] == 1 or (color[v] == 0 and dfs(v)):
                return True
        color[u] = 2
        return False

    return "DEADLOCK" if any(color[i] == 0 and dfs(i) for i in range(1, p + 1)) else "OK"


REFERENCE = {
    "Sliding-Window Rate Limiter": _rate_limiter,
    "Idempotent Webhook Processing": _idempotency,
    "Transaction Deadlock Detection": _deadlock,
}


@pytest.mark.parametrize("puzzle", ALL_PUZZLES, ids=lambda p: p["title"])
def test_reference_solution_matches_every_expected_output(puzzle):
    solver = REFERENCE[puzzle["title"]]
    assert puzzle["testcases"], "puzzle has no testcases"
    for tc in puzzle["testcases"]:
        assert solver(tc["stdin"]).strip() == tc["expected"].strip(), tc["stdin"]


def test_every_puzzle_has_at_least_one_sample_and_one_hidden_case():
    for puzzle in ALL_PUZZLES:
        kinds = {tc["is_sample"] for tc in puzzle["testcases"]}
        assert kinds == {True, False}, puzzle["title"]
