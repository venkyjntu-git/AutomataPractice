"""
ref_dfa_adapter.py
==================
Builds a reference DFA from a question dict (DFA only).
Skips if any condition is KthFromEndNode. Uses ref_dfa_extended for all atoms.
"""

from __future__ import annotations

from typing import Any

from ast_nodes import (
    CountConstraintNode,
    CountModConstraintNode,
    CountExprNode,
    LengthConstraintNode,
    LengthModConstraintNode,
    StringPredicateNode,
    FollowPredicateNode,
    KthFromEndNode,
    NoAdjacentSameNode,
    IntLitNode,
    IdentNode,
)
from template_handler import Instantiator
from ref_dfa_extended import build_dfa_extended
from Ref_DFA_generator import (
    complement_dfa,
    reversal_dfa,
    product_dfa,
    union_dfa,
    difference_dfa,
    minimize_dfa,
    build_suffix_dfa,
    subset_construction,
)


def _build_kth_from_end_dfa(symbol: str, k: int, alphabet: list) -> dict:
    """
    Build a DFA accepting strings where the k-th symbol from the end equals `symbol`.

    NFA construction (k+1 states: q0..qk):
      - q0 on `symbol`  → {q0, q1}   (non-deterministic branch)
      - q0 on any other → {q0}        (stay)
      - qi on any sym   → {q(i+1)}    for i = 1..k-1
      - qk is the sole accept state
    Then convert NFA → DFA via subset_construction, then minimize.
    """
    states = [f"q{i}" for i in range(k + 1)]
    nfa_transitions: dict = {}

    # q0 transitions
    for sym in alphabet:
        if sym == symbol:
            nfa_transitions[("q0", sym)] = {"q0", "q1"}
        else:
            nfa_transitions[("q0", sym)] = {"q0"}

    # q1..q(k-1) transitions: advance chain on any symbol
    for i in range(1, k):
        for sym in alphabet:
            nfa_transitions[(f"q{i}", sym)] = {f"q{i+1}"}

    # qk has no outgoing transitions (dead / sink for further input)

    nfa = {
        "states": states,
        "start": "q0",
        "accept": {f"q{k}"},
        "transitions": nfa_transitions,
    }

    dfa = subset_construction(nfa, alphabet)
    dfa["alphabet"] = list(alphabet)
    return minimize_dfa(dfa, alphabet)


def _param_name_for_value(param_map: dict, value: Any) -> str | None:
    """Return a param key whose value equals value, or None."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    for k, pv in param_map.items():
        try:
            if int(pv) == v:
                return k
        except (TypeError, ValueError):
            continue
    return None


def _condition_to_ref_string(conditions: list, param_map: dict, role_map: dict, string_map: dict) -> str | None:
    """
    Serialize condition AST nodes to Ref-style condition string with param/role names.
    Returns None if any condition is not supported for reference DFA.
    """
    atoms = []
    for c in conditions:
        if isinstance(c, KthFromEndNode):
            return None  # handled separately via _build_kth_from_end_dfa
        if isinstance(c, CountModConstraintNode):
            role = c.role
            mod_val = Instantiator.eval_expr(c.modulus, role_map, param_map)
            val_val = Instantiator.eval_expr(c.value, role_map, param_map)
            mod_name = _param_name_for_value(param_map, mod_val)
            if mod_name is None:
                mod_name = "k"
            atoms.append(f"count({role}) % {mod_name} == {val_val}")
        elif isinstance(c, CountConstraintNode):
            if isinstance(c.rhs, CountExprNode):
                atoms.append(f"count({c.role}) == count({c.rhs.role})")
            else:
                # count(R) == N or count(R) == K*N - not a single Ref atom for DFA; skip or treat as unsupported
                return None
        elif isinstance(c, LengthConstraintNode):
            rhs_val = Instantiator.eval_expr(c.rhs, role_map, param_map)
            k_name = _param_name_for_value(param_map, rhs_val)
            if k_name is None:
                k_name = "K"
            rel = c.rel
            if rel == "<=":
                atoms.append(f"length <= {k_name}")
            elif rel == ">=":
                atoms.append(f"length >= {k_name}")
            elif rel == "==":
                atoms.append(f"length == {k_name}")
            else:
                return None
        elif isinstance(c, LengthModConstraintNode):
            mod_val = Instantiator.eval_expr(c.modulus, role_map, param_map)
            k_name = _param_name_for_value(param_map, mod_val)
            if k_name is None:
                k_name = "K"
            atoms.append(f"length % {k_name} == 0")
        elif isinstance(c, StringPredicateNode):
            param = c.param
            kind = c.kind
            if kind == "begins_with":
                atoms.append(f"begins_with({param})")
            elif kind == "ends_with":
                atoms.append(f"ends_with({param})")
            elif kind == "contains":
                atoms.append(f"contains({param})")
            else:
                return None
        elif isinstance(c, FollowPredicateNode):
            atoms.append(f"every({c.trigger}) followed_by({c.follower})")
        elif isinstance(c, NoAdjacentSameNode):
            atoms.append("no_adjacent_same")
        else:
            # VarConstraintNode, PalindromeNode, PrefixOrderNode, etc. - skip (no Ref atom)
            continue
    return " AND ".join(atoms) if atoms else None


def _pure_begins_with_reversed(question: dict) -> str | None:
    """
    Return the reversed pattern if question has exactly one begins_with(s) condition,
    otherwise None. Used to fix REVERSAL(begins_with(s)) → ends_with(reverse(s)).
    """
    conditions = question.get("conditions", [])
    if len(conditions) != 1:
        return None
    c = conditions[0]
    if not isinstance(c, StringPredicateNode) or c.kind != "begins_with":
        return None
    params = {}
    params.update(question.get("param_map", {}))
    params.update(question.get("role_map", {}))
    params.update(question.get("string_map", {}))
    s = params.get(c.param, c.param)
    return s[::-1]


def build_reference_dfa(question: dict) -> dict | None:
    """
    Build reference DFA for a DFA question dict.
    Returns DFA dict (states, start, accept, transitions) or None if not supported.
    Handles closure questions: COMPLEMENT/REVERSAL (unary) and UNION/INTERSECTION/DIFFERENCE (binary).
    """
    if question.get("machine") != "DFA":
        return None
    alphabet = question.get("alphabet", [])
    if not alphabet:
        return None

    # ── Closure: unary (COMPLEMENT / REVERSAL) ─────────────────────────────────
    closure = question.get("closure_info", {})
    op = closure.get("op", "")
    if op in ("COMPLEMENT", "REVERSAL"):
        sub_qs = closure.get("sub_questions", [])
        if len(sub_qs) != 1:
            return None
        sub_dfa = build_reference_dfa(sub_qs[0])
        if sub_dfa is None:
            return None
        if op == "COMPLEMENT":
            dfa = complement_dfa(sub_dfa, alphabet)
        else:
            # REVERSAL of a pure begins_with(s) DFA computes "contains(reverse(s))"
            # instead of the correct "ends_with(reverse(s))" because the sink-accept
            # self-loop at state n in the prefix DFA corrupts the NFA reversal.
            # Fix: detect this case and build suffix_dfa(reverse(s)) directly.
            rev_s = _pure_begins_with_reversed(sub_qs[0])
            if rev_s is not None:
                dfa = build_suffix_dfa(alphabet, rev_s)
            else:
                dfa = reversal_dfa(sub_dfa, alphabet)
        dfa["alphabet"] = list(alphabet)
        return minimize_dfa(dfa, alphabet)

    # ── Closure: binary (UNION / INTERSECTION / DIFFERENCE) ───────────────────
    if op in ("UNION", "INTERSECTION", "DIFFERENCE"):
        sub_qs = closure.get("sub_questions", [])
        if len(sub_qs) != 2:
            return None
        dfa1 = build_reference_dfa(sub_qs[0])
        dfa2 = build_reference_dfa(sub_qs[1])
        if dfa1 is None or dfa2 is None:
            return None
        if op == "UNION":
            dfa = union_dfa(dfa1, dfa2, alphabet)
        elif op == "INTERSECTION":
            dfa = product_dfa(dfa1, dfa2, alphabet)
        else:
            dfa = difference_dfa(dfa1, dfa2, alphabet)
        dfa["alphabet"] = list(alphabet)
        return minimize_dfa(dfa, alphabet)

    # ── Base question: build from conditions ───────────────────────────────────
    conditions = question.get("conditions", [])
    if not conditions:
        return None
    param_map = question.get("param_map", {})
    role_map = question.get("role_map", {})
    string_map = question.get("string_map", {})

    # Check for KthFromEnd — build NFA→DFA directly
    kth_nodes = [c for c in conditions if isinstance(c, KthFromEndNode)]
    if kth_nodes:
        # Use the first KthFromEndNode (templates have exactly one)
        c = kth_nodes[0]
        symbol = role_map.get(c.role, c.role)
        raw_k = param_map.get(c.position_param, c.position_param)
        try:
            k = int(raw_k)
        except (TypeError, ValueError):
            return None
        if k < 1 or symbol not in alphabet:
            return None
        try:
            return _build_kth_from_end_dfa(symbol, k, alphabet)
        except Exception:
            return None

    cond_str = _condition_to_ref_string(conditions, param_map, role_map, string_map)
    if not cond_str:
        return None

    params = dict(param_map)
    params.update(role_map)
    params.update(string_map)

    try:
        dfa = build_dfa_extended(cond_str, alphabet, params)
        dfa["alphabet"] = list(alphabet)
        return minimize_dfa(dfa, alphabet)
    except Exception:
        return None
