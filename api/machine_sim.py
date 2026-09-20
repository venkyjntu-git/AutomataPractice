"""
PDA / TM canvas JSON parsing and simulation (aligned with test/evaluator.py).
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

# Same limits as test/evaluator.py
MAX_TM_STEPS = 5000
MAX_PDA_CONFIGS = 5000


def _norm_eps_str(s: object | None) -> str:
    if s is None:
        return ""
    x = str(s).strip()
    if x in ("ε", "epsilon", "eps", ""):
        return ""
    return x


def _norm_tm_sym(s: object | None) -> str:
    """Blank tape cell is '_' (matches test/evaluator TMSimulator)."""
    x = _norm_eps_str(s)
    return "_" if x == "" else x


def parse_pda_canvas(automata: dict) -> dict:
    states: set[str] = set()
    start: str | None = None
    accept: set[str] = set()
    for s in automata.get("states", []):
        sid = str(s["id"])
        states.add(sid)
        if s.get("initial"):
            start = sid
        if s.get("accept"):
            accept.add(sid)

    trans: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    for t in automata.get("transitions", []):
        src = str(t["from_state"])
        dst = str(t["to_state"])
        raw = str(t.get("symbol", ""))
        if raw in ("ε", "epsilon", "eps", ""):
            reads = [""]
        else:
            reads = [x.strip() for x in raw.split(",") if x.strip()]
            if not reads:
                reads = [""]
        pop = _norm_eps_str(t.get("stack_top"))
        push_raw = str(t.get("stack_push") or "")
        push = "" if push_raw in ("ε", "epsilon", "eps", "") else push_raw
        for read in reads:
            trans[(src, read, pop)].append((dst, push))

    if start is None and states:
        start = sorted(states)[0]
    return {"states": states, "start": start, "accept": accept, "transitions": trans}


def parse_tm_canvas(automata: dict) -> dict:
    states: set[str] = set()
    start: str | None = None
    accept: set[str] = set()
    for s in automata.get("states", []):
        sid = str(s["id"])
        states.add(sid)
        if s.get("initial"):
            start = sid
        if s.get("accept"):
            accept.add(sid)

    transitions: dict[tuple[str, str], tuple[str, str, str]] = {}
    for t in automata.get("transitions", []):
        src = str(t["from_state"])
        dst = str(t["to_state"])
        read = _norm_tm_sym(t.get("symbol"))
        write = _norm_tm_sym(t.get("write"))
        move = str(t.get("direction") or "R").upper()
        if move not in ("L", "R"):
            move = "R"
        transitions[(src, read)] = (dst, write, move)

    if start is None and states:
        start = sorted(states)[0]
    return {"states": states, "start": start, "accept": accept, "transitions": transitions}


class PDASimulator:
    """Same logic as test/evaluator.PDASimulator."""

    def __init__(self, pda: dict):
        self.start = pda["start"]
        self.accept = set(pda["accept"]) if not isinstance(pda["accept"], set) else pda["accept"]
        self.transitions = pda["transitions"]
        self.accept_by_final = len(self.accept) > 0
        self.accept_by_empty = True
        self.initial_stack = self._infer_initial_stack()

    def _infer_initial_stack(self) -> list[str]:
        for (state, read, pop), moves in self.transitions.items():
            if state == self.start and read == "" and pop == "":
                for _, push in moves:
                    if push:
                        return list(push)
        return ["Z"]

    def run(self, inp: str) -> tuple[int, str]:
        queue = deque([(self.start, 0, self.initial_stack.copy())])
        visited: set = set()

        while queue:
            state, i, stack = queue.popleft()
            config = (state, i, tuple(stack))
            if config in visited:
                continue
            visited.add(config)
            if len(visited) > MAX_PDA_CONFIGS:
                return 0, "Exceeded PDA configuration limit"

            if i == len(inp):
                if self.accept_by_final and state in self.accept:
                    return 1, "Accepted (final state)"
                if self.accept_by_empty and len(stack) == 0:
                    return 1, "Accepted (empty stack)"

            top = stack[-1] if stack else ""
            for (s, read, pop), moves in self.transitions.items():
                if s != state:
                    continue
                if read != "":
                    if i >= len(inp) or inp[i] != read:
                        continue
                if pop != "":
                    if top != pop:
                        continue
                for to, push in moves:
                    new_stack = stack.copy()
                    if pop != "":
                        new_stack.pop()
                    if push != "":
                        for sym in reversed(push):
                            new_stack.append(sym)
                    new_i = i + (1 if read != "" else 0)
                    queue.append((to, new_i, new_stack))

        return 0, "No accepting computation"


class TMSimulator:
    """Same logic as test/evaluator.TMSimulator."""

    def __init__(self, tm: dict):
        self.start = tm["start"]
        self.accept = set(tm["accept"]) if not isinstance(tm["accept"], set) else tm["accept"]
        self.transitions = tm["transitions"]

    def run(self, inp: str) -> tuple[int, str]:
        tape = list(inp) if inp else ["_"]
        head = 0
        state = self.start

        for _ in range(MAX_TM_STEPS):
            symbol = tape[head] if head < len(tape) else "_"
            if (state, symbol) not in self.transitions:
                break
            state, write, move = self.transitions[(state, symbol)]
            tape[head] = write
            if move == "R":
                head += 1
                if head == len(tape):
                    tape.append("_")
            elif move == "L":
                head = max(0, head - 1)
            if state in self.accept:
                return 1, "Accepted"

        return 0, "Rejected (step limit or no transition)"


def pda_simulation_trace(inp: str, pda: dict) -> tuple[list[dict[str, Any]], bool, str]:
    """
    BFS with parent pointers — one witness path on accept; on reject, path to
    a config that consumed the most input (then deepest stack).
    """
    sim = PDASimulator(pda)
    ok, msg = sim.run(inp)
    accepted = ok == 1

    start = pda["start"]
    accept_states = set(pda["accept"]) if not isinstance(pda["accept"], set) else pda["accept"]
    transitions = pda["transitions"]
    accept_by_final = len(accept_states) > 0
    accept_by_empty = True
    initial_stack = sim.initial_stack

    if start is None:
        return (
            [{"kind": "pda", "state": None, "remaining_input": inp, "stack": [], "note": "No initial state"}],
            False,
            "No initial state defined",
        )

    queue: deque[tuple[str, int, list[str]]] = deque([(start, 0, initial_stack.copy())])
    parent: dict[tuple[str, int, tuple[str, ...]], tuple[str, int, tuple[str, ...]] | None] = {}
    start_cfg = (start, 0, tuple(initial_stack))
    parent[start_cfg] = None
    visited: set[tuple[str, int, tuple[str, ...]]] = set()
    accepting_cfg: tuple[str, int, tuple[str, ...]] | None = None

    while queue:
        state, i, stack = queue.popleft()
        config = (state, i, tuple(stack))
        if config in visited:
            continue
        visited.add(config)
        if len(visited) > MAX_PDA_CONFIGS:
            break

        if i == len(inp):
            if accept_by_final and state in accept_states:
                accepting_cfg = config
                break
            if accept_by_empty and len(stack) == 0:
                accepting_cfg = config
                break

        top = stack[-1] if stack else ""
        for (s, read, pop), moves in transitions.items():
            if s != state:
                continue
            if read != "":
                if i >= len(inp) or inp[i] != read:
                    continue
            if pop != "":
                if top != pop:
                    continue
            for to, push in moves:
                new_stack = stack.copy()
                if pop != "":
                    new_stack.pop()
                if push != "":
                    for sym in reversed(push):
                        new_stack.append(sym)
                new_i = i + (1 if read != "" else 0)
                nxt = (to, new_i, tuple(new_stack))
                if nxt not in parent:
                    parent[nxt] = config
                    queue.append((to, new_i, new_stack))

    end_cfg = accepting_cfg
    if end_cfg is None and visited:
        end_cfg = max(
            visited,
            key=lambda c: (c[1], len(c[2])),
        )

    if end_cfg is None:
        return [], accepted, msg

    path: list[tuple[str, int, tuple[str, ...]]] = []
    cur: tuple[str, int, tuple[str, ...]] | None = end_cfg
    while cur is not None:
        path.append(cur)
        cur = parent.get(cur)
    path.reverse()

    steps: list[dict[str, Any]] = []
    for idx, (st, pos, st_stack) in enumerate(path):
        note = "Start configuration" if idx == 0 else "After transition"
        if idx == len(path) - 1 and accepting_cfg and end_cfg == accepting_cfg and accepted:
            note = msg
        steps.append(
            {
                "kind": "pda",
                "state": st,
                "remaining_input": inp[pos:],
                "stack": list(st_stack),
                "note": note,
            }
        )

    if not accepted and steps:
        steps[-1]["note"] = msg

    return steps, accepted, msg


def tm_simulation_trace(inp: str, tm: dict) -> tuple[list[dict[str, Any]], bool, str]:
    """Step trace matching TMSimulator.run() (same transition order)."""
    tape = list(inp) if inp else ["_"]
    head = 0
    state = tm["start"]
    trans = tm["transitions"]
    accept = set(tm["accept"]) if not isinstance(tm["accept"], set) else tm["accept"]

    steps: list[dict[str, Any]] = []
    if state is None:
        return (
            [
                {
                    "kind": "tm",
                    "state": None,
                    "tape": tape.copy(),
                    "head": head,
                    "note": "No initial state defined",
                }
            ],
            False,
            "No initial state defined",
        )

    for _ in range(MAX_TM_STEPS):
        sym = tape[head] if head < len(tape) else "_"
        steps.append(
            {
                "kind": "tm",
                "state": state,
                "tape": tape.copy(),
                "head": head,
                "note": f"Before transition on read {sym!r}",
            }
        )
        if (state, sym) not in trans:
            return steps, False, f"No transition from state {state!r} on symbol {sym!r}"
        nstate, write, move = trans[(state, sym)]
        tape[head] = write
        if move == "R":
            head += 1
            if head == len(tape):
                tape.append("_")
        elif move == "L":
            head = max(0, head - 1)
        state = nstate
        if state in accept:
            steps.append(
                {
                    "kind": "tm",
                    "state": state,
                    "tape": tape.copy(),
                    "head": head,
                    "note": "Accepted (halt in accept state)",
                }
            )
            return steps, True, "Accepted"

    return (
        steps,
        False,
        "Rejected (step limit or no transition)",
    )
