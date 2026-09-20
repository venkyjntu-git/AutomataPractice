"""
ref_dfa_extended.py
===================
Extended reference DFA builders. Does NOT modify Ref_DFA_generator;
imports from it and adds support for: length >= k, length == k,
length % k == 0, count(A) == count(B), every(A) followed_by(B).

DFA structure: {"states", "start", "accept" (set), "transitions" ((s,sym)->next)}.
"""

from __future__ import annotations

import re

from Ref_DFA_generator import (
    complete_dfa,
    product_dfa,
    parse_condition,
    build_from_atom as ref_build_from_atom,
    build_mod_count_dfa,
)


# ── Normalize params so Ref_DFA_generator gets 'k' when template uses 'K' ─────

def _params_for_ref(params: dict) -> dict:
    p = dict(params)
    if "k" not in p and "K" in p:
        p["k"] = p["K"]
    for key in ("K1", "K2"):
        if key in p and key.lower() not in p:
            p[key.lower()] = p[key]
    return p


# ── New DFA builders (not in Ref_DFA_generator) ───────────────────────────────

def build_length_geq_dfa(alphabet: list, k: int):
    """Accept strings of length >= k. States 0..k; state k and beyond accept."""
    states = list(range(k + 2))  # 0..k, k+1 = "accept all longer"
    start = 0
    accept = set(range(k, k + 2))  # k and k+1
    transitions = {}
    for s in states:
        for a in alphabet:
            if s <= k:
                transitions[(s, a)] = min(s + 1, k + 1)
            else:
                transitions[(s, a)] = k + 1
    return {"states": states, "start": start, "accept": accept, "transitions": transitions}


def build_length_eq_dfa(alphabet: list, k: int):
    """Accept strings of length exactly k. States 0..k; only k accepting; from k go to dead."""
    states = list(range(k + 2))  # 0..k, k+1 = dead
    start = 0
    accept = {k}
    transitions = {}
    for s in states:
        for a in alphabet:
            if s < k:
                transitions[(s, a)] = s + 1
            else:
                transitions[(s, a)] = k + 1
    return {"states": states, "start": start, "accept": accept, "transitions": transitions}


def build_length_mod_dfa(alphabet: list, k: int):
    """Accept strings whose length is divisible by k. State = length % k; accept 0."""
    states = list(range(k))
    start = 0
    accept = {0}
    transitions = {}
    for s in states:
        for a in alphabet:
            transitions[(s, a)] = (s + 1) % k
    return {"states": states, "start": start, "accept": accept, "transitions": transitions}


def build_count_eq_count_dfa(alphabet: list, sym_a: str, sym_b: str, max_len: int = 100):
    """
    Accept strings where count(sym_a) == count(sym_b).
    State = (count_a - count_b) bounded; we need a finite DFA so cap at ±max_len.
    States: -max_len .. 0 .. max_len; accept 0. Transitions: on sym_a go +1, on sym_b go -1, else same.
    """
    states = list(range(-max_len, max_len + 1))
    start = 0
    accept = {0}
    transitions = {}
    for d in states:
        for a in alphabet:
            if a == sym_a:
                nxt = min(d + 1, max_len)
            elif a == sym_b:
                nxt = max(d - 1, -max_len)
            else:
                nxt = d
            transitions[(d, a)] = nxt
    return {"states": states, "start": start, "accept": accept, "transitions": transitions}


def build_no_adjacent_same_dfa(alphabet: list):
    """
    Accept strings where no two adjacent symbols are the same.
    State = last symbol seen, or 'start' for empty/initial; DEAD if we saw a repeat.
    """
    states = ["start", "DEAD"] + list(alphabet)
    start = "start"
    accept = set(states) - {"DEAD"}
    transitions = {}
    for a in alphabet:
        transitions[("start", a)] = a
    for s in alphabet:
        for a in alphabet:
            transitions[(s, a)] = "DEAD" if a == s else a
    for a in alphabet:
        transitions[("DEAD", a)] = "DEAD"
    return {"states": states, "start": start, "accept": accept, "transitions": transitions}


def build_every_followed_by_dfa(alphabet: list, trigger: str, follower: str):
    """
    Accept strings where every occurrence of trigger is immediately followed by follower.
    Reject if trigger at end or trigger not followed by follower.
    States: 0 = normal, 1 = just saw trigger (must see follower next), 2 = dead.
    """
    states = [0, 1, 2]
    start = 0
    accept = {0, 1}  # 1 is "just saw trigger" - empty string after trigger is invalid, so actually accept only 0
    accept = {0}
    transitions = {}
    for s in states:
        for a in alphabet:
            if s == 0:
                if a == trigger:
                    transitions[(s, a)] = 1
                else:
                    transitions[(s, a)] = 0
            elif s == 1:
                if a == follower:
                    transitions[(s, a)] = 0
                else:
                    transitions[(s, a)] = 2  # trigger not followed by follower
            else:
                transitions[(s, a)] = 2
    # If we end in state 1 (last char was trigger), reject
    return {"states": states, "start": start, "accept": accept, "transitions": transitions}


def build_from_atom_extended(atom: str, alphabet: list, params: dict):
    """Handle atoms: Ref for begins_with/ends_with/contains/length<=; extended for the rest."""
    atom = atom.strip()
    params_ref = _params_for_ref(params)

    # count(A) % K == R  — intercept before ref_build_from_atom so K1/K2/remainder work.
    if "count" in atom and "%" in atom:
        m = re.search(r"count\s*\(\s*(\w+)\s*\)\s*%\s*(\w+)\s*==\s*(\d+)", atom)
        if m:
            role, mod_key, rem_str = m.group(1), m.group(2), m.group(3)
            sym = params.get(role, params_ref.get(role, role))
            k = params.get(mod_key, params_ref.get(mod_key))
            if k is not None:
                return build_mod_count_dfa(alphabet, sym, int(k), int(rem_str))

    # count(A) == count(B)  (no mod) — must precede ref_build_from_atom to avoid KeyError.
    if "count" in atom and "==" in atom and "%" not in atom:
        m = re.search(r"count\s*\(\s*(\w+)\s*\)\s*==\s*count\s*\(\s*(\w+)\s*\)", atom)
        if m:
            role_a, role_b = m.group(1), m.group(2)
            sym_a = params.get(role_a, role_a)
            sym_b = params.get(role_b, role_b)
            return build_count_eq_count_dfa(alphabet, sym_a, sym_b)
        raise NotImplementedError(f"Unknown condition: {atom}")

    try:
        return ref_build_from_atom(atom, alphabet, params_ref)
    except NotImplementedError:
        pass

    # length >= K
    if "length >=" in atom:
        k = params_ref.get("K", params_ref.get("k"))
        if k is None:
            raise ValueError("length >= requires K or k in params")
        return build_length_geq_dfa(alphabet, int(k))

    # length == K
    if "length ==" in atom or "length == " in atom:
        k = params_ref.get("K", params_ref.get("k"))
        if k is None:
            raise ValueError("length == requires K or k in params")
        return build_length_eq_dfa(alphabet, int(k))

    # length % K == 0
    if "length %" in atom or "length % " in atom:
        m = re.search(r"length\s*%\s*(\w+)\s*==\s*0", atom)
        if m:
            key = m.group(1)
            k = params_ref.get(key, params_ref.get("K", params_ref.get("k")))
            if k is None:
                raise ValueError(f"length % {key} == 0 requires param")
            return build_length_mod_dfa(alphabet, int(k))
        raise NotImplementedError(f"Unknown condition: {atom}")

    # every(A) followed_by(B)
    if "every(" in atom and "followed_by(" in atom:
        m1 = re.search(r"every\s*\(\s*(\w+)\s*\)", atom)
        m2 = re.search(r"followed_by\s*\(\s*(\w+)\s*\)", atom)
        if m1 and m2:
            trigger_role = m1.group(1)
            follower_role = m2.group(1)
            trigger = params.get(trigger_role, trigger_role)
            follower = params.get(follower_role, follower_role)
            return build_every_followed_by_dfa(alphabet, trigger, follower)
        raise NotImplementedError(f"Unknown condition: {atom}")

    # no_adjacent_same
    if atom.strip() == "no_adjacent_same":
        return build_no_adjacent_same_dfa(alphabet)

    raise NotImplementedError(f"Unknown condition: {atom}")


def build_dfa_extended(condition: str, alphabet: list, params: dict):
    """
    Build reference DFA from condition string (AND-separated atoms).
    Uses Ref_DFA_generator for supported atoms and extended builders for the rest.
    params: param_map merged with role_map and string_map; K/k normalized for Ref.
    """
    parsed = parse_condition(condition)
    if parsed[0] == "ATOM":
        return build_from_atom_extended(parsed[1], alphabet, params)
    if parsed[0] == "AND":
        dfas = [build_dfa_extended(p[1], alphabet, params) for p in parsed[1]]
        result = dfas[0]
        for d in dfas[1:]:
            result = product_dfa(result, d, alphabet)
        return result
    raise ValueError(f"Unexpected parsed condition: {parsed}")
