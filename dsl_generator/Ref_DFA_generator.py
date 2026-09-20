import re
from itertools import product

# =====================================
# BASIC DFA UTILITIES
# =====================================

def complete_dfa(dfa, alphabet):
    dead = "DEAD"
    states = set(dfa["states"])
    transitions = dict(dfa["transitions"])

    states.add(dead)

    for s in states:
        for a in alphabet:
            if (s, a) not in transitions:
                transitions[(s, a)] = dead

    for a in alphabet:
        transitions[(dead, a)] = dead

    return {
        "states": list(states),
        "start": dfa["start"],
        "accept": set(dfa["accept"]),
        "transitions": transitions
    }


def product_dfa(dfa1, dfa2, alphabet):
    dfa1 = complete_dfa(dfa1, alphabet)
    dfa2 = complete_dfa(dfa2, alphabet)

    states = set()
    transitions = {}
    accept = set()

    for s1 in dfa1["states"]:
        for s2 in dfa2["states"]:
            states.add((s1, s2))

    start = (dfa1["start"], dfa2["start"])

    for (s1, s2) in states:
        for a in alphabet:
            t1 = dfa1["transitions"][(s1, a)]
            t2 = dfa2["transitions"][(s2, a)]
            transitions[((s1, s2), a)] = (t1, t2)

    for (s1, s2) in states:
        if s1 in dfa1["accept"] and s2 in dfa2["accept"]:
            accept.add((s1, s2))

    return {
        "states": list(states),
        "start": start,
        "accept": accept,
        "transitions": transitions
    }


def union_dfa(dfa1, dfa2, alphabet):
    """Product construction with accept = (s1 in accept1) or (s2 in accept2)."""
    dfa1 = complete_dfa(dfa1, alphabet)
    dfa2 = complete_dfa(dfa2, alphabet)

    states = set()
    transitions = {}
    accept = set()

    for s1 in dfa1["states"]:
        for s2 in dfa2["states"]:
            states.add((s1, s2))

    start = (dfa1["start"], dfa2["start"])

    for (s1, s2) in states:
        for a in alphabet:
            t1 = dfa1["transitions"][(s1, a)]
            t2 = dfa2["transitions"][(s2, a)]
            transitions[((s1, s2), a)] = (t1, t2)

    for (s1, s2) in states:
        if s1 in dfa1["accept"] or s2 in dfa2["accept"]:
            accept.add((s1, s2))

    return {
        "states": list(states),
        "start": start,
        "accept": accept,
        "transitions": transitions
    }


def difference_dfa(dfa1, dfa2, alphabet):
    """Product construction with accept = (s1 in accept1) and (s2 not in accept2)."""
    dfa1 = complete_dfa(dfa1, alphabet)
    dfa2 = complete_dfa(dfa2, alphabet)

    states = set()
    transitions = {}
    accept = set()

    for s1 in dfa1["states"]:
        for s2 in dfa2["states"]:
            states.add((s1, s2))

    start = (dfa1["start"], dfa2["start"])

    for (s1, s2) in states:
        for a in alphabet:
            t1 = dfa1["transitions"][(s1, a)]
            t2 = dfa2["transitions"][(s2, a)]
            transitions[((s1, s2), a)] = (t1, t2)

    for (s1, s2) in states:
        if s1 in dfa1["accept"] and s2 not in dfa2["accept"]:
            accept.add((s1, s2))

    return {
        "states": list(states),
        "start": start,
        "accept": accept,
        "transitions": transitions
    }


def complement_dfa(dfa, alphabet):
    """Complete the DFA then flip accept to non-accept."""
    completed = complete_dfa(dfa, alphabet)
    all_states = set(completed["states"])
    new_accept = all_states - completed["accept"]
    return {
        "states": completed["states"],
        "start": completed["start"],
        "accept": new_accept,
        "transitions": completed["transitions"]
    }


# =====================================
# NFA REVERSAL + SUBSET CONSTRUCTION (Option A)
# =====================================

def nfa_reverse(dfa):
    """
    Turn a DFA into an NFA that accepts the reversal of the language.
    For each (s, a) -> t in DFA, add (t, a) -> s in NFA.
    NFA start = DFA accept set; NFA accept = {DFA start}.
    NFA transitions: (state, symbol) -> set of states.
    """
    rev_trans = {}  # (state, symbol) -> set of states
    for (s, a), t in dfa["transitions"].items():
        key = (t, a)
        if key not in rev_trans:
            rev_trans[key] = set()
        rev_trans[key].add(s)

    nfa_states = set(dfa["states"])
    nfa_start = set(dfa["accept"])  # DFA accept becomes NFA start
    nfa_accept = {dfa["start"]}     # DFA start becomes NFA accept

    return {
        "states": list(nfa_states),
        "start": nfa_start,
        "accept": nfa_accept,
        "transitions": rev_trans,
    }


def subset_construction(nfa, alphabet):
    """
    Determinize NFA to DFA via subset construction.
    NFA: transitions (state, symbol) -> set of states (or single state).
    DFA states = frozenset of NFA states; start = nfa["start"]; accept if subset meets nfa["accept"].
    """
    if isinstance(nfa["start"], set):
        start_set = frozenset(nfa["start"])
    else:
        start_set = frozenset([nfa["start"]])
    nfa_accept = set(nfa["accept"]) if isinstance(nfa["accept"], set) else {nfa["accept"]}

    def get_next_states(nfa, state_set, symbol):
        out = set()
        for s in state_set:
            key = (s, symbol)
            if key in nfa["transitions"]:
                t = nfa["transitions"][key]
                if isinstance(t, set):
                    out.update(t)
                else:
                    out.add(t)
        return frozenset(out)

    # BFS to find reachable subsets (include empty set as dead state)
    empty_set = frozenset()
    dfa_states = {start_set, empty_set}
    stack = [start_set]
    while stack:
        s_set = stack.pop()
        for a in alphabet:
            next_s = get_next_states(nfa, s_set, a)
            if next_s not in dfa_states:
                dfa_states.add(next_s)
                if next_s:
                    stack.append(next_s)

    dfa_transitions = {}
    for s_set in dfa_states:
        for a in alphabet:
            next_s = get_next_states(nfa, s_set, a)
            dfa_transitions[(s_set, a)] = next_s if next_s in dfa_states else empty_set

    dfa_accept = {s_set for s_set in dfa_states if s_set & nfa_accept}

    return {
        "states": list(dfa_states),
        "start": start_set,
        "accept": dfa_accept,
        "transitions": dfa_transitions,
    }


def reversal_dfa(dfa, alphabet):
    """Reversal of DFA language via NFA reverse + subset construction (Option A)."""
    nfa = nfa_reverse(dfa)
    return subset_construction(nfa, alphabet)


# =====================================
# DFA BUILDERS
# =====================================

def build_prefix_dfa(alphabet, s):
    """Accept strings that begin with s.
    States 0..n track how many characters of s have been matched from
    the START of the input; any mismatch goes to a dead sink (state n+1).
    State n is a sink-accept (any further input keeps the string accepted).
    """
    n = len(s)
    dead = n + 1
    states = list(range(n + 2))   # 0..n (live), n+1 (dead)
    start = 0
    accept = {n}
    transitions = {}

    for i in range(n):
        for a in alphabet:
            if a == s[i]:
                transitions[(i, a)] = i + 1
            else:
                transitions[(i, a)] = dead

    # Accept state: self-loop (string still begins with s regardless of tail)
    for a in alphabet:
        transitions[(n, a)] = n

    # Dead sink
    for a in alphabet:
        transitions[(dead, a)] = dead

    return {
        "states": states,
        "start": start,
        "accept": accept,
        "transitions": transitions
    }


def build_contains_dfa(alphabet, s):
    """Accept strings that contain s as a substring.
    Uses the KMP automaton: state i = length of the longest prefix of s
    that is a suffix of the input seen so far.  State n is a sink-accept.
    """
    n = len(s)
    states = list(range(n + 1))
    start = 0
    accept = {n}
    transitions = {}

    for i in range(n + 1):
        for a in alphabet:
            if i < n and a == s[i]:
                transitions[(i, a)] = i + 1
            else:
                temp = s[:i] + a
                nxt = 0
                for j in range(n, -1, -1):
                    if temp.endswith(s[:j]):
                        nxt = j
                        break
                transitions[(i, a)] = nxt

    # Once the pattern is found, stay accepting
    for a in alphabet:
        transitions[(n, a)] = n

    return {
        "states": states,
        "start": start,
        "accept": accept,
        "transitions": transitions
    }


def build_suffix_dfa(alphabet, s):
    n = len(s)
    states = list(range(n + 1))
    start = 0
    accept = {n}
    transitions = {}

    for i in range(n + 1):
        for a in alphabet:
            temp = s[:i] + a
            nxt = 0
            for j in range(n, -1, -1):
                if temp.endswith(s[:j]):
                    nxt = j
                    break
            transitions[(i, a)] = nxt

    return {
        "states": states,
        "start": start,
        "accept": accept,
        "transitions": transitions
    }


def build_mod_count_dfa(alphabet, symbol, k, remainder=0):
    """Accept strings where count(symbol) % k == remainder."""
    states = list(range(k))
    start = 0
    accept = {remainder % k}
    transitions = {}

    for s in states:
        for a in alphabet:
            if a == symbol:
                transitions[(s, a)] = (s + 1) % k
            else:
                transitions[(s, a)] = s

    return {
        "states": states,
        "start": start,
        "accept": accept,
        "transitions": transitions
    }


def build_length_leq_dfa(alphabet, k):
    states = list(range(k + 2))  # last is overflow
    start = 0
    accept = set(range(k + 1))
    transitions = {}

    for s in states:
        for a in alphabet:
            if s <= k:
                transitions[(s, a)] = s + 1
            else:
                transitions[(s, a)] = s

    return {
        "states": states,
        "start": start,
        "accept": accept,
        "transitions": transitions
    }


# =====================================
# CONDITION PARSER
# =====================================

def parse_condition(condition):
    condition = condition.strip()

    if "AND" in condition:
        parts = [c.strip() for c in condition.split("AND")]
        return ("AND", [parse_condition(p) for p in parts])

    return ("ATOM", condition)


# =====================================
# CONDITION → DFA
# =====================================

def build_from_atom(atom, alphabet, params):
    # begins_with(S)
    if atom.startswith("begins_with("):
        key = atom[12:-1]
        return build_prefix_dfa(alphabet, params[key])

    # ends_with(S)
    if atom.startswith("ends_with("):
        key = atom[10:-1]
        return build_suffix_dfa(alphabet, params[key])

    # contains(S)
    if atom.startswith("contains("):
        key = atom[9:-1]
        return build_contains_dfa(alphabet, params[key])

    # count(A) % k == r
    if "count" in atom and "%" in atom:
        m = re.search(r'count\s*\(\s*(\w+)\s*\)\s*%\s*(\w+)\s*==\s*(\d+)', atom)
        if m:
            role, mod_key, rem_str = m.group(1), m.group(2), m.group(3)
            sym = params.get(role, role)
            k = params.get(mod_key, params.get('k'))
            return build_mod_count_dfa(alphabet, sym, int(k), int(rem_str))

    # length <= k
    if "length <=" in atom:
        k = params['k']
        return build_length_leq_dfa(alphabet, k)

    raise NotImplementedError(f"Unknown condition: {atom}")


def build_dfa(condition, alphabet, params):
    parsed = parse_condition(condition)

    if parsed[0] == "ATOM":
        return build_from_atom(parsed[1], alphabet, params)

    elif parsed[0] == "AND":
        dfas = [build_dfa(p[1], alphabet, params) for p in parsed[1]]
        result = dfas[0]
        for d in dfas[1:]:
            result = product_dfa(result, d, alphabet)
        return result


# =====================================
# DFA MINIMIZATION  (Hopcroft's algorithm)
# =====================================

def minimize_dfa(dfa, alphabet):
    """
    Minimize a DFA using Hopcroft's algorithm.
    Returns a new DFA whose states are consecutive integers 0, 1, 2, …
    The original DFA is completed first so every (state, symbol) has a transition.
    """
    completed = complete_dfa(dfa, alphabet)
    states = list(completed["states"])
    accept = set(completed["accept"])
    trans = completed["transitions"]

    # Edge case: no accepting states → single dead state DFA
    if not accept:
        new_trans = {(0, a): 0 for a in alphabet}
        return {"states": [0], "start": 0, "accept": set(),
                "transitions": new_trans, "alphabet": list(alphabet)}

    # Edge case: all states accepting → single accepting state DFA
    non_accept = set(states) - accept
    if not non_accept:
        new_trans = {(0, a): 0 for a in alphabet}
        return {"states": [0], "start": 0, "accept": {0},
                "transitions": new_trans, "alphabet": list(alphabet)}

    # Initial partition: {accept} and {non-accept}
    partition = [accept, non_accept]

    def part_of(s):
        for i, p in enumerate(partition):
            if s in p:
                return i
        return -1

    changed = True
    while changed:
        changed = False
        new_partition = []
        for group in partition:
            if len(group) <= 1:
                new_partition.append(group)
                continue
            # Split by transition signature
            by_sig: dict = {}
            for s in group:
                sig = tuple(part_of(trans[(s, a)]) for a in alphabet)
                by_sig.setdefault(sig, set()).add(s)
            for sub in by_sig.values():
                new_partition.append(sub)
            if len(by_sig) > 1:
                changed = True
        partition = new_partition

    # Build minimized DFA from partition representatives
    state_to_part = {}
    for i, p in enumerate(partition):
        for s in p:
            state_to_part[s] = i

    raw_start = state_to_part[completed["start"]]
    raw_accept = {i for i, p in enumerate(partition) if p & accept}
    raw_trans = {}
    for i, p in enumerate(partition):
        rep = next(iter(p))
        for a in alphabet:
            raw_trans[(i, a)] = state_to_part[trans[(rep, a)]]

    # Prune unreachable states (complete_dfa may have added an unreachable DEAD)
    reachable: set[int] = set()
    queue = [raw_start]
    while queue:
        s = queue.pop()
        if s in reachable:
            continue
        reachable.add(s)
        for a in alphabet:
            queue.append(raw_trans[(s, a)])

    # Renumber reachable states 0..n-1 in BFS order
    order: list[int] = []
    seen: set[int] = set()
    bfs = [raw_start]
    while bfs:
        s = bfs.pop(0)
        if s in seen:
            continue
        seen.add(s)
        order.append(s)
        for a in alphabet:
            nxt = raw_trans[(s, a)]
            if nxt not in seen:
                bfs.append(nxt)

    remap = {old: new for new, old in enumerate(order)}
    new_states = list(range(len(order)))
    new_start = remap[raw_start]
    new_accept = {remap[s] for s in raw_accept if s in remap}
    new_trans = {(remap[s], a): remap[raw_trans[(s, a)]]
                 for s in order for a in alphabet}

    return {
        "states": new_states,
        "start": new_start,
        "accept": new_accept,
        "transitions": new_trans,
        "alphabet": list(alphabet),
    }