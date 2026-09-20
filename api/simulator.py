"""
simulator.py — DFA/NFA simulator + evaluator-style feedback.

Ported from test/evaluator.py:
  - DFA simulation with per-step reason
  - NFA simulation (ε-closure, subset construction)
  - DFA equivalence check via Hopcroft minimisation + symmetric-difference BFS
  - A-DEN-DIF partial-credit metric
  - Score: 20/20 if equivalent, else test-based (max 16) + 2 structure + 2 robustness

Input automata (from canvas JSON):
  {
    "states":      [{"id": "q0", "initial": True, "accept": False}, ...]
    "transitions": [{"from_state": "q0", "to_state": "q1", "symbol": "a"}, ...]
  }
"""
from __future__ import annotations

import os
from collections import defaultdict, deque
from typing import Any

# Override via env for large generated questions (e.g. closure DFAs with many states).
MAX_AUTOMATON_STATES = int(os.environ.get("AUTOMATA_MAX_STATES", "20"))


def validate_automaton_state_count(automata: dict) -> None:
    """Reject absurdly large diagrams to protect CPU (Hopcroft, simulation)."""
    n = len(automata.get("states") or [])
    if n > MAX_AUTOMATON_STATES:
        raise ValueError(
            f"Too many states ({n}); maximum is {MAX_AUTOMATON_STATES}. "
            "Ask your instructor to raise AUTOMATA_MAX_STATES on the server if needed."
        )

from api.machine_sim import (
    PDASimulator,
    TMSimulator,
    parse_pda_canvas,
    parse_tm_canvas,
    pda_simulation_trace,
    tm_simulation_trace,
)


# ─────────────────────────────────────────────────────────────────────────────
# DESERIALISE STORED REFERENCE DFA  (transitions list → delta dict)
# ─────────────────────────────────────────────────────────────────────────────

def _load_reference_dfa(ref: dict) -> dict:
    """
    Convert the stored JSON reference DFA (transitions as list of
    {from, symbol, to}) back to the internal format used by _complete_dfa:
      states, start, accept, delta {(state,sym): state}, alphabet
    """
    delta: dict = {}
    for t in ref.get("transitions", []):
        delta[(t["from"], t["symbol"])] = t["to"]

    return {
        "states":   set(ref.get("states", [])),
        "start":    ref.get("start"),
        "accept":   set(ref.get("accept", [])),
        "delta":    delta,
        "alphabet": ref.get("alphabet", []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# BUILD DFA / NFA DICTS FROM CANVAS JSON
# ─────────────────────────────────────────────────────────────────────────────

def _parse_automata(automata: dict) -> dict:
    """
    Convert canvas JSON → internal dict:
      states      : set[str]
      start       : str | None
      accept      : set[str]
      transitions : dict[(from, symbol), set[to]]   (NFA-style; DFA has |set|=1)
      is_dfa      : bool  (no ε, no multiple targets per (state,sym))
    """
    states: set[str] = set()
    start:  str | None = None
    accept: set[str] = set()
    trans: dict[tuple, set[str]] = defaultdict(set)

    for s in automata.get("states", []):
        sid = str(s["id"])
        states.add(sid)
        if s.get("initial"):
            start = sid
        if s.get("accept"):
            accept.add(sid)

    has_epsilon = False
    for t in automata.get("transitions", []):
        src = str(t["from_state"])
        dst = str(t["to_state"])
        raw = t.get("symbol", "")
        syms = ["ε"] if raw in ("ε", "epsilon", "eps", "") else [s.strip() for s in raw.split(",") if s.strip()]
        for sym in syms:
            if sym == "ε":
                has_epsilon = True
            trans[(src, sym)].add(dst)

    # is_dfa: no epsilon, every (state,sym) maps to exactly one state
    is_dfa = (not has_epsilon) and all(len(v) == 1 for v in trans.values())

    if start is None and states:
        start = sorted(states)[0]

    return {
        "states": states,
        "start":  start,
        "accept": accept,
        "transitions": trans,
        "is_dfa": is_dfa,
    }


# ─────────────────────────────────────────────────────────────────────────────
# NFA SIMULATION  (covers DFA as special case)
# ─────────────────────────────────────────────────────────────────────────────

def _epsilon_closure(states: set[str], trans: dict) -> set[str]:
    closure = set(states)
    queue = deque(states)
    while queue:
        s = queue.popleft()
        for nxt in trans.get((s, "ε"), set()):
            if nxt not in closure:
                closure.add(nxt)
                queue.append(nxt)
    return closure


def _nfa_run(inp: str, parsed: dict) -> tuple[bool, str]:
    """Return (accepted, reason_string)."""
    if parsed["start"] is None:
        return False, "No initial state defined"

    current = _epsilon_closure({parsed["start"]}, parsed["transitions"])
    trans   = parsed["transitions"]

    for ch in inp:
        nxt: set[str] = set()
        for s in current:
            nxt |= trans.get((s, ch), set())
        current = _epsilon_closure(nxt, trans)
        if not current:
            return False, f"No transition on '{ch}' — machine died"

    accepting = current & parsed["accept"]
    if accepting:
        return True, f"Accepted in state(s) {sorted(accepting)}"
    return False, f"Ended in non-accepting state(s) {sorted(current)}"


def _run_machine_acceptance(inp: str, automata: dict, machine: str) -> tuple[bool, str]:
    """Run acceptance for canvas JSON; PDA/TM use test/evaluator semantics."""
    m = (machine or "DFA").strip().upper()
    try:
        if m == "PDA":
            pda = parse_pda_canvas(automata)
            ok, msg = PDASimulator(pda).run(inp)
            return ok == 1, msg
        if m == "TM":
            tm = parse_tm_canvas(automata)
            ok, msg = TMSimulator(tm).run(inp)
            return ok == 1, msg
    except Exception as e:
        return False, f"Error: {e}"
    parsed = _parse_automata(automata)
    return _nfa_run(inp, parsed)


def _dfa_nfa_simulation_detail(inp: str, parsed: dict) -> dict:
    """Return {accepted, final_reason, steps} for DFA or NFA (subset construction)."""
    if parsed["start"] is None:
        return {
            "accepted": False,
            "final_reason": "No initial state defined",
            "steps": [
                {
                    "kind": "dfa",
                    "state": None,
                    "remaining_input": inp,
                    "active_states": [],
                    "note": "No initial state defined",
                }
            ],
        }
    if parsed["is_dfa"]:
        steps: list[dict[str, Any]] = []
        state = parsed["start"]
        trans = parsed["transitions"]
        steps.append(
            {
                "kind": "dfa",
                "state": state,
                "remaining_input": inp,
                "active_states": [state],
                "note": "Start",
            }
        )
        for i, ch in enumerate(inp):
            nxt = trans.get((state, ch), set())
            if len(nxt) != 1:
                steps.append(
                    {
                        "kind": "dfa",
                        "state": state,
                        "remaining_input": inp[i:],
                        "active_states": [state],
                        "note": f"No transition on '{ch}'",
                    }
                )
                return {
                    "accepted": False,
                    "final_reason": f"No transition on '{ch}'",
                    "steps": steps,
                }
            state = next(iter(nxt))
            steps.append(
                {
                    "kind": "dfa",
                    "state": state,
                    "remaining_input": inp[i + 1 :],
                    "active_states": [state],
                    "note": f"After '{ch}'",
                }
            )
        acc = state in parsed["accept"]
        return {
            "accepted": acc,
            "final_reason": "Accepted" if acc else f"Rejected in non-final state {state!r}",
            "steps": steps,
        }

    current = _epsilon_closure({parsed["start"]}, parsed["transitions"])
    trans = parsed["transitions"]
    steps = [
        {
            "kind": "nfa",
            "state": None,
            "remaining_input": inp,
            "active_states": sorted(current),
            "note": "Initial ε-closure",
        }
    ]
    for i, ch in enumerate(inp):
        nxt: set[str] = set()
        for s in current:
            nxt |= trans.get((s, ch), set())
        current = _epsilon_closure(nxt, trans)
        if not current:
            steps.append(
                {
                    "kind": "nfa",
                    "state": None,
                    "remaining_input": inp[i + 1 :],
                    "active_states": [],
                    "note": f"No transition on '{ch}'",
                }
            )
            return {
                "accepted": False,
                "final_reason": f"No transition on '{ch}' — machine died",
                "steps": steps,
            }
        steps.append(
            {
                "kind": "nfa",
                "state": None,
                "remaining_input": inp[i + 1 :],
                "active_states": sorted(current),
                "note": f"After '{ch}' (ε-closure)",
            }
        )
    accepting = current & parsed["accept"]
    if accepting:
        return {
            "accepted": True,
            "final_reason": f"Accepted in state(s) {sorted(accepting)}",
            "steps": steps,
        }
    return {
        "accepted": False,
        "final_reason": f"Ended in non-accepting state(s) {sorted(current)}",
        "steps": steps,
    }


def _pack_simulation_run(
    steps: list[dict[str, Any]],
    accepted: bool,
    reason: str,
    inp: str,
    machine: str,
    expected_label: str | None = None,
) -> dict[str, Any]:
    got = "ACCEPT" if accepted else "REJECT"
    correct: bool | None = None
    if expected_label is not None:
        correct = got == expected_label
    return {
        "machine": machine,
        "input": inp if inp != "" else "(empty)",
        "expected": expected_label,
        "got": got,
        "correct": correct,
        "accepted": accepted,
        "final_reason": reason,
        "steps": steps,
    }


def run_simulation(
    automata: dict,
    machine: str,
    inp: str,
    expected_label: str | None = None,
) -> dict[str, Any]:
    """
    Full simulation result for one input string (steps + verdict).
    Used by HTTP simulate endpoints and optionally by tooling.
    """
    validate_automaton_state_count(automata)
    m = (machine or "DFA").strip().upper()
    try:
        if m == "PDA":
            pda = parse_pda_canvas(automata)
            steps, acc, reason = pda_simulation_trace(inp, pda)
            return _pack_simulation_run(steps, acc, reason, inp, m, expected_label)
        if m == "TM":
            tm = parse_tm_canvas(automata)
            steps, acc, reason = tm_simulation_trace(inp, tm)
            return _pack_simulation_run(steps, acc, reason, inp, m, expected_label)
    except Exception as e:
        return {
            "machine": m,
            "input": inp if inp != "" else "(empty)",
            "expected": expected_label,
            "got": "REJECT",
            "correct": (expected_label == "REJECT") if expected_label else None,
            "accepted": False,
            "final_reason": str(e),
            "steps": [],
        }

    parsed = _parse_automata(automata)
    detail = _dfa_nfa_simulation_detail(inp, parsed)
    return _pack_simulation_run(
        detail["steps"],
        detail["accepted"],
        detail["final_reason"],
        inp,
        m,
        expected_label,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DFA EQUIVALENCE  (ported from test/evaluator.py)
# ─────────────────────────────────────────────────────────────────────────────

def _complete_dfa(dfa: dict, alphabet: list[str]) -> dict:
    """Add a DEAD sink for any missing (state, symbol) pair."""
    delta  = dict(dfa.get("delta") or dfa.get("transitions", {}))
    # flatten set-valued transitions (NFA style) to single values
    flat: dict = {}
    for (s, a), v in delta.items():
        flat[(s, a)] = next(iter(v)) if isinstance(v, set) else v
    delta = flat

    states = set(dfa["states"])
    accept = set(dfa["accept"])
    start  = dfa["start"]
    dead   = "__DEAD__"
    need_dead = False

    for s in list(states):
        for a in alphabet:
            if (s, a) not in delta:
                delta[(s, a)] = dead
                need_dead = True

    if need_dead:
        states.add(dead)
        for a in alphabet:
            delta[(dead, a)] = dead

    return {"states": frozenset(states), "start": start,
            "accept": frozenset(accept), "delta": delta, "alphabet": alphabet}


def _reachable(start: Any, delta: dict, alphabet: list[str]) -> frozenset:
    visited: set = set()
    q = deque([start])
    while q:
        s = q.popleft()
        if s in visited:
            continue
        visited.add(s)
        for a in alphabet:
            t = delta.get((s, a))
            if t and t not in visited:
                q.append(t)
    return frozenset(visited)


def _hopcroft(dfa: dict) -> dict:
    """Minimise a complete DFA using Hopcroft's algorithm."""
    alphabet = dfa["alphabet"]
    delta    = dfa["delta"]
    accept   = dfa["accept"]
    states   = _reachable(dfa["start"], delta, alphabet)

    accept_r = states & accept
    reject_r = states - accept
    P = [b for b in (accept_r, reject_r) if b]
    W = list(P)

    while W:
        A = W.pop()
        for a in alphabet:
            X = frozenset(s for s in states if delta.get((s, a)) in A)
            if not X:
                continue
            new_P = []
            for Y in P:
                inter, diff = Y & X, Y - X
                if inter and diff:
                    new_P.extend([inter, diff])
                    if Y in W:
                        W.remove(Y)
                        W.extend([inter, diff])
                    else:
                        W.append(inter if len(inter) <= len(diff) else diff)
                else:
                    new_P.append(Y)
            P = new_P

    s2c: dict = {}
    for block in P:
        for s in block:
            s2c[s] = block

    q_start  = s2c[dfa["start"]]
    q_accept = frozenset(b for b in P if b & accept)
    q_delta: dict = {}
    for block in P:
        rep = next(iter(block))
        for a in alphabet:
            t = delta.get((rep, a))
            if t and t in s2c:
                q_delta[(block, a)] = s2c[t]

    return {"states": frozenset(P), "start": q_start,
            "accept": q_accept, "delta": q_delta, "alphabet": alphabet}


def _sym_diff_bfs(m1: dict, m2: dict, alphabet: list[str]) -> tuple[bool, str | None]:
    """Return (equivalent, witness_string_or_None)."""
    s1, s2   = m1["start"], m2["start"]
    d1, d2   = m1["delta"],  m2["delta"]
    a1, a2   = m1["accept"], m2["accept"]

    visited: set  = set()
    queue: deque  = deque()
    path: dict    = {}

    start_pair = (s1, s2)
    queue.append(start_pair)
    visited.add(start_pair)
    path[start_pair] = None
    witness_pair = None

    while queue:
        p, q = queue.popleft()
        if (p in a1) != (q in a2):
            witness_pair = (p, q)
            break
        for a in alphabet:
            np = d1.get((p, a), p)
            nq = d2.get((q, a), q)
            nxt = (np, nq)
            if nxt not in visited:
                visited.add(nxt)
                path[nxt] = ((p, q), a)
                queue.append(nxt)

    if witness_pair is None:
        return True, None

    chars = []
    cur = witness_pair
    while path[cur] is not None:
        parent, sym = path[cur]
        chars.append(sym)
        cur = parent
    witness = "".join(reversed(chars))
    return False, witness if witness else "(empty string)"


def _count_by_length(dfa: dict, max_len: int) -> list[int]:
    delta, accept, alphabet = dfa["delta"], dfa["accept"], dfa["alphabet"]
    curr: dict[Any, int] = defaultdict(int)
    curr[dfa["start"]] = 1
    counts = [sum(curr[s] for s in accept)]
    for _ in range(max_len):
        nxt: dict[Any, int] = defaultdict(int)
        for state, cnt in curr.items():
            for sym in alphabet:
                t = delta.get((state, sym))
                if t is not None:
                    nxt[t] += cnt
        curr = nxt
        counts.append(sum(curr[s] for s in accept))
    return counts


def _a_den_dif(stu: dict, ref: dict, alphabet: list[str]) -> tuple[float, int]:
    ref_c = _complete_dfa(ref, alphabet)
    stu_c = _complete_dfa(stu, alphabet)
    ref_m = _hopcroft(ref_c)
    k     = len(ref_m["states"])
    max_len = 2 * k

    ref_d, stu_d = ref_c["delta"], stu_c["delta"]
    ref_a, stu_a = ref_c["accept"], stu_c["accept"]

    sym_start = (stu_c["start"], ref_c["start"])
    sym_delta: dict = {}
    sym_accept: set = set()
    visited: set = set()
    queue: deque = deque([sym_start])

    while queue:
        pair = queue.popleft()
        if pair in visited:
            continue
        visited.add(pair)
        s1, s2 = pair
        if (s1 in stu_a) != (s2 in ref_a):
            sym_accept.add(pair)
        for sym in alphabet:
            n1 = stu_d.get((s1, sym), s1)
            n2 = ref_d.get((s2, sym), s2)
            nxt = (n1, n2)
            sym_delta[(pair, sym)] = nxt
            if nxt not in visited:
                queue.append(nxt)

    sym_dfa = {"states": frozenset(visited), "start": sym_start,
               "accept": frozenset(sym_accept), "delta": sym_delta, "alphabet": alphabet}

    ref_counts = _count_by_length(ref_c, max_len)
    sym_counts = _count_by_length(sym_dfa, max_len)

    score = sum(sym_counts[n] / max(ref_counts[n], 1) for n in range(max_len + 1))
    return score, k


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_test_cases(automata: dict, test_cases: list[dict],
                   machine: str = "DFA",
                   reference_dfa: dict | None = None,
                   alphabet: list[str] | None = None) -> dict:
    """
    Evaluate a student automaton and return a structured report matching
    the format of test/evaluator.py.

    Returns dict:
      score          : float  (0–20)
      result         : "pass" | "fail"
      summary        : list[str]   — header lines (machine, test counts, equiv, score)
      equiv_lines    : list[str]   — equivalence section lines
      test_details   : list[dict]  — per test: {input, expected, got, correct, reason}
    """
    validate_automaton_state_count(automata)
    parsed = _parse_automata(automata)

    # ── Run all test cases ─────────────────────────────────────────────────────
    test_details = []
    passed = 0
    for tc in test_cases:
        inp      = tc["input"]
        expected = tc["label"]                           # "ACCEPT" | "REJECT"
        accepted, reason = _run_machine_acceptance(inp, automata, machine)
        got     = "ACCEPT" if accepted else "REJECT"
        correct = (got == expected)
        if correct:
            passed += 1
        test_details.append({
            "input":    inp if inp != "" else "(empty)",
            "expected": expected,
            "got":      got,
            "correct":  correct,
            "reason":   reason,
        })

    total        = len(test_cases)
    test_score   = (passed / total) * 16 if total else 0.0
    structure    = 2.0
    robustness   = 2.0

    # ── Equivalence check (DFA only, when reference available) ────────────────
    equiv_lines: list[str] = []
    is_equiv:    bool | None = None
    a_den_dif_val: float | None = None
    k_states:      int | None   = None
    witness:       str | None   = None
    ref_states_before = ref_states_after = stu_states_before = stu_states_after = None

    if machine == "DFA" and reference_dfa and alphabet and parsed["is_dfa"] and parsed["start"]:
        alph = alphabet
        equiv_lines.append(f"Alphabet : {{{', '.join(alph)}}}")

        try:
            # Build student DFA dict in the format _complete_dfa expects
            stu_dict = {
                "states":      parsed["states"],
                "start":       parsed["start"],
                "accept":      parsed["accept"],
                "transitions": parsed["transitions"],
                "alphabet":    alph,
            }
            # Deserialise stored reference DFA (transitions list → delta dict)
            ref_dict = _load_reference_dfa(reference_dfa)
            ref_dict["alphabet"] = alph

            # Minimise both
            ref_c = _complete_dfa(ref_dict, alph)
            stu_c = _complete_dfa(stu_dict, alph)
            ref_m = _hopcroft(ref_c)
            stu_m = _hopcroft(stu_c)

            ref_states_before = len(reference_dfa.get("states", []))
            ref_states_after  = len(ref_m["states"])
            stu_states_before = len(parsed["states"])
            stu_states_after  = len(stu_m["states"])

            equiv_lines.append(
                f"Reference DFA : {ref_states_before} states "
                f"→ {ref_states_after} after minimisation"
            )
            equiv_lines.append(
                f"Student DFA   : {stu_states_before} states "
                f"→ {stu_states_after} after minimisation"
            )

            is_equiv, witness = _sym_diff_bfs(ref_m, stu_m, alph)

            if is_equiv:
                equiv_lines.append(
                    "✓ LANGUAGES ARE EQUAL — your DFA accepts exactly the required language."
                )
            else:
                equiv_lines.append(
                    f"✗ LANGUAGES DIFFER — witness: '{witness}' is accepted by one DFA but not the other."
                )
                try:
                    a_den_dif_val, k_states = _a_den_dif(stu_dict, ref_dict, alph)
                    equiv_lines.append(
                        f"A-DEN-DIF : {a_den_dif_val:.4f}  "
                        f"(k={k_states} minimal states, lengths 0..{2*k_states})"
                    )
                except Exception as e:
                    equiv_lines.append(f"A-DEN-DIF : computation failed — {e}")

        except Exception as e:
            equiv_lines.append(f"Equivalence check error: {e}")
            is_equiv = None

    elif machine == "DFA" and parsed["is_dfa"] and not reference_dfa:
        equiv_lines.append("No reference DFA available — equivalence check skipped.")
    elif machine == "DFA" and not parsed["is_dfa"]:
        equiv_lines.append("Submitted automaton has ε-transitions or non-determinism — treated as NFA, equivalence check skipped.")

    # ── Compute score ──────────────────────────────────────────────────────────
    if is_equiv is True:
        score = 20.0
    elif is_equiv is False and a_den_dif_val is not None:
        correctness = 16.0 / (1.0 + a_den_dif_val)
        score = round(correctness + structure + robustness, 2)
    else:
        score = round(test_score + structure + robustness, 2)

    score = min(score, 20.0)

    # ── Build summary lines ────────────────────────────────────────────────────
    summary: list[str] = [
        f"Machine      : {machine}",
        f"Test cases   : {passed}/{total} passed",
    ]
    if is_equiv is True:
        summary.append("Equivalence  : PROVED — languages are identical")
        summary.append(f"Score        : {score}/20  (full marks by equivalence)")
    elif is_equiv is False:
        summary.append("Equivalence  : DISPROVED — see witness string below")
        if a_den_dif_val is not None:
            summary.append(
                f"A-DEN-DIF    : {a_den_dif_val:.4f}  (k={k_states}, lengths 0..{2*k_states})"
            )
        summary.append(f"Score        : {score}/20  (partial credit via A-DEN-DIF)")
    else:
        summary.append(f"Score        : {score}/20")

    result = "pass" if (is_equiv is True or (is_equiv is None and passed == total)) else "fail"

    return {
        "score":        score,
        "result":       result,
        "passed":       passed,
        "total":        total,
        "summary":      summary,
        "equiv_lines":  equiv_lines,
        "test_details": test_details,
    }
