"""
closure_handler.py
==================
Generates closure-property questions from base question pairs.

Closure rules (what each machine class is closed under):

  DFA (Regular)  : UNION, INTERSECTION, DIFFERENCE, COMPLEMENT, REVERSAL
  NFA (Regular)  : same as DFA
  PDA (CFL)      : UNION, REVERSAL   (NOT closed under INTERSECTION, DIFFERENCE, COMPLEMENT)
  TM  (Recursive): UNION, INTERSECTION, DIFFERENCE, COMPLEMENT, REVERSAL

Cross-machine closure (result is the more expressive class):
  DFA ∩ PDA → PDA   (CFL ∩ Regular = CFL; product construction on states)

Public API
----------
  generate_combinations(base_questions, n) → list[dict]
"""

from __future__ import annotations

import re
import random
from typing import Any


# ══════════════════════════════════════════════════════════════════════════════
#  CLOSURE TABLE
# ══════════════════════════════════════════════════════════════════════════════

# Each tuple: (op_id, arity, english_name, pattern_tag)
#   arity 2 = binary (needs two questions with same machine + same alphabet)
#   arity 1 = unary  (needs one question, no alphabet constraint)

_CLOSURE_OPS: dict[str, list[tuple]] = {
    "DFA": [
        ("UNION",        2, "union",         "UNION"),
        ("INTERSECTION", 2, "intersection",  "INTERSECT"),
        ("DIFFERENCE",   2, "set difference","DIFF"),
        ("COMPLEMENT",   1, "complement",    "COMPLEMENT"),
        ("REVERSAL",     1, "reversal",      "REVERSAL"),
    ],
    "NFA": [
        ("UNION",        2, "union",         "UNION"),
        ("INTERSECTION", 2, "intersection",  "INTERSECT"),
        ("DIFFERENCE",   2, "set difference","DIFF"),
        ("COMPLEMENT",   1, "complement",    "COMPLEMENT"),
        ("REVERSAL",     1, "reversal",      "REVERSAL"),
    ],
    "PDA": [
        # CFL is NOT closed under INTERSECTION, DIFFERENCE, COMPLEMENT
        ("UNION",    2, "union",   "UNION"),
        ("REVERSAL", 1, "reversal","REVERSAL"),
    ],
    "TM": [
        ("UNION",        2, "union",         "UNION"),
        ("INTERSECTION", 2, "intersection",  "INTERSECT"),
        ("DIFFERENCE",   2, "set difference","DIFF"),
        ("COMPLEMENT",   1, "complement",    "COMPLEMENT"),
        ("REVERSAL",     1, "reversal",      "REVERSAL"),
    ],
}

# Sampling weights — simpler operations appear more often
_OP_WEIGHTS: dict[str, float] = {
    "UNION":                3.0,
    "INTERSECTION":         2.0,
    "DIFFERENCE":           2.0,
    "COMPLEMENT":           2.0,
    "REVERSAL":             1.5,
    "DFA_PDA_INTERSECTION": 4.0,
}

# Cross-machine operations that produce a result of a different (more expressive) class.
# Each tuple: (op_id, machine1, machine2, result_machine, arity, english_name, pattern_tag)
_CROSS_MACHINE_OPS: list[tuple] = [
    ("DFA_PDA_INTERSECTION", "DFA", "PDA", "PDA", 2,
     "intersection (DFA ∩ PDA → PDA)", "DFA_PDA_INTERSECT"),
]

# Fraction of the n-budget that may be filled by cross-machine questions.
_CROSS_MACHINE_FRACTION = 0.30


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _alphabet_key(q: dict) -> tuple:
    """Canonical order-independent alphabet key."""
    return tuple(sorted(q["alphabet"]))


def _body(q: dict) -> str:
    """
    Extract the acceptance condition clause from a question dict.
    Strips the trailing period and any  (given: …)  footnote.
    """
    marker = " that accepts all strings where "
    body   = q["text"].split(marker, 1)[-1]
    body   = re.sub(r'\.\s*\(given:[^)]*\)\s*$', '', body)
    return body.rstrip(".")


def _weighted_choice(ops: list[tuple]) -> tuple:
    weights = [_OP_WEIGHTS.get(op[0], 1.0) for op in ops]
    total   = sum(weights)
    r       = random.random() * total
    cum     = 0.0
    for op, w in zip(ops, weights):
        cum += w
        if r <= cum:
            return op
    return ops[-1]


# ══════════════════════════════════════════════════════════════════════════════
#  QUESTION BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def _apply_binary(q1: dict, q2: dict,
                  op_id: str, op_en: str, op_tag: str) -> dict:
    """
    Binary closure operation on two questions with the same machine + alphabet.
    Produces well-formed English text naming the operation precisely.
    """
    alpha_str = "{" + ", ".join(q1["alphabet"]) + "}"
    machine   = q1["machine"]

    _intros = {
        "UNION":
            ("the union of the two languages below — "
             "strings accepted by L1, or by L2, or by both",
             "L1", "L2"),
        "INTERSECTION":
            ("the intersection of the two languages below — "
             "strings accepted by BOTH L1 and L2",
             "L1", "L2"),
        "DIFFERENCE":
            ("the set difference L1 \\ L2 — "
             "strings in L1 that are NOT in L2",
             "L1", "L2"),
    }
    intro, tag1, tag2 = _intros[op_id]

    text = (
        f"Construct a {machine} over the alphabet {alpha_str} that "
        f"accepts exactly {intro}.\n"
        f"  {tag1}: {{ w  |  {_body(q1)} }}\n"
        f"  {tag2}: {{ w  |  {_body(q2)} }}"
    )

    return {
        "machine":     machine,
        "template_id": f"{q1['template_id']}_{op_tag}_{q2['template_id']}",
        "difficulty":  max(q1["difficulty"], q2["difficulty"]) + 1,
        "tags":        sorted(set(q1["tags"] + q2["tags"])),
        "pattern_fam": q1["pattern_fam"],
        "alphabet":    q1["alphabet"],
        "role_map":    q1.get("role_map",   {}),
        "param_map":   q1.get("param_map",  {}),
        "string_map":  q1.get("string_map", {}),
        "free_vars":   q1.get("free_vars",  set()),
        "conditions":  [],
        "text":        text,
        "pattern":     f"{q1['pattern']} | {op_tag} | {q2['pattern']}",
        "combined":    True,
        "max_length":  max(q1.get("max_length", 12), q2.get("max_length", 12)),
        # ── closure info for test-case generation ────────────────────────
        "closure_info": {
            "op":            op_id,     # UNION | INTERSECTION | DIFFERENCE
            "sub_questions": [q1, q2],
        },
    }


def _apply_dfa_pda_intersection(dfa_q: dict, pda_q: dict) -> dict:
    """
    Cross-machine binary operation: DFA ∩ PDA → PDA.

    Theoretical basis: the intersection of a regular language (DFA) with a
    context-free language (PDA) is always context-free.  The resulting machine
    is a PDA built via the product construction — states are (dfa_state,
    pda_state) pairs; on each real symbol the DFA component advances
    deterministically while the PDA component makes its usual stack moves;
    on ε-moves only the PDA component advances.  Accept when both components
    are in an accepting state.
    """
    alpha_str = "{" + ", ".join(dfa_q["alphabet"]) + "}"

    text = (
        f"Construct a PDA over the alphabet {alpha_str} that accepts exactly "
        f"the intersection of the regular language L1 and the context-free "
        f"language L2 — strings accepted by BOTH L1 and L2.\n"
        f"  L1: {{ w  |  {_body(dfa_q)} }}\n"
        f"  L2: {{ w  |  {_body(pda_q)} }}\n"
        f"  (Hint: use the product construction — states are pairs "
        f"(dfa_state, pda_state); advance the DFA state on each real input "
        f"symbol; on ε-moves only the PDA state changes.  Accept when both "
        f"components are in accepting states.)"
    )

    return {
        "machine":     "PDA",
        "template_id": f"{dfa_q['template_id']}_DFA_PDA_INTERSECT_{pda_q['template_id']}",
        "difficulty":  max(dfa_q["difficulty"], pda_q["difficulty"]) + 2,
        "tags":        sorted(set(dfa_q["tags"] + pda_q["tags"])),
        "pattern_fam": pda_q["pattern_fam"],
        "alphabet":    dfa_q["alphabet"],
        "role_map":    {**dfa_q.get("role_map",  {}), **pda_q.get("role_map",  {})},
        "param_map":   {**dfa_q.get("param_map", {}), **pda_q.get("param_map", {})},
        "string_map":  {**dfa_q.get("string_map",{}), **pda_q.get("string_map",{})},
        "free_vars":   dfa_q.get("free_vars", set()) | pda_q.get("free_vars", set()),
        "conditions":  [],
        "text":        text,
        "pattern":     f"{dfa_q['pattern']} | DFA_PDA_INTERSECT | {pda_q['pattern']}",
        "combined":    True,
        "max_length":  max(dfa_q.get("max_length", 12), pda_q.get("max_length", 12)),
        "closure_info": {
            "op":            "DFA_PDA_INTERSECTION",
            "sub_questions": [dfa_q, pda_q],   # [0]=DFA, [1]=PDA
        },
    }


def _apply_unary(q: dict,
                 op_id: str, op_en: str, op_tag: str) -> dict:
    """
    Unary closure operation (COMPLEMENT or REVERSAL).
    """
    alpha_str = "{" + ", ".join(q["alphabet"]) + "}"
    machine   = q["machine"]

    if op_id == "COMPLEMENT":
        desc   = (f"the complement of the language L — "
                  f"all strings over {alpha_str} that are NOT in L")
        hint   = ("  (Hint: construct the machine for L first, "
                  "then apply the complement construction.)")
    else:  # REVERSAL
        desc   = ("the reversal of the language L — "
                  "the set of all reversals of strings in L")
        hint   = ("  (Hint: to build the machine for L\u1d3f reverse "
                  "all transitions/rules of the machine for L.)")

    text = (
        f"Construct a {machine} over the alphabet {alpha_str} that "
        f"accepts exactly {desc}.\n"
        f"  L: {{ w  |  {_body(q)} }}\n"
        f"{hint}"
    )

    return {
        "machine":     machine,
        "template_id": f"{op_tag}_{q['template_id']}",
        "difficulty":  q["difficulty"] + 1,
        "tags":        list(q["tags"]),
        "pattern_fam": q["pattern_fam"],
        "alphabet":    q["alphabet"],
        "role_map":    q.get("role_map",   {}),
        "param_map":   q.get("param_map",  {}),
        "string_map":  q.get("string_map", {}),
        "free_vars":   q.get("free_vars",  set()),
        "conditions":  q.get("conditions", []),
        "text":        text,
        "pattern":     f"{q['pattern']} | {op_tag}",
        "combined":    True,
        "max_length":  q.get("max_length", 12),
        # ── closure info for test-case generation ────────────────────────
        "closure_info": {
            "op":            op_id,     # COMPLEMENT | REVERSAL
            "sub_questions": [q],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_combinations(base_questions: list[dict], n: int) -> list[dict]:
    """
    Generate up to n closure-property questions.

    Constraints enforced:
      1. Only operations valid for the machine class are used.
      2. Binary operations require the same machine AND the same alphabet.
      3. Cross-template pairs are preferred to avoid trivial A op A.
      4. Only templates with closure_allowed=True participate (author decision).
      5. Cross-machine DFA ∩ PDA → PDA operations are generated when DFA and
         PDA questions share the same alphabet; they fill at most
         _CROSS_MACHINE_FRACTION of the total budget.
    """
    # Respect the author's closure_allowed decision
    base_questions = [q for q in base_questions if q.get("closure_allowed", True)]

    # Group by (machine, alphabet_key) for binary ops
    groups: dict[tuple, list] = {}
    for q in base_questions:
        key = (q["machine"], _alphabet_key(q))
        groups.setdefault(key, []).append(q)

    # Index by machine for unary ops
    by_machine: dict[str, list] = {}
    for q in base_questions:
        by_machine.setdefault(q["machine"], []).append(q)

    # ── Pre-compute eligible cross-machine pairs (same alphabet required) ──────
    # Each entry: (op_id, result_fn, q1, q2)
    _cross_eligible: list[tuple] = []
    for op_id, m1, m2, *_ in _CROSS_MACHINE_OPS:
        pool1 = by_machine.get(m1, [])
        pool2 = by_machine.get(m2, [])
        for q1 in pool1:
            for q2 in pool2:
                if _alphabet_key(q1) == _alphabet_key(q2):
                    _cross_eligible.append((op_id, q1, q2))

    cross_budget = max(1, int(n * _CROSS_MACHINE_FRACTION)) if _cross_eligible else 0
    cross_count  = 0

    combined:     list[dict] = []
    used_keys:    set[str]  = set()
    attempts  = 0
    max_tries = n * 40

    while len(combined) < n and attempts < max_tries:
        attempts += 1

        # ── Occasionally emit a cross-machine DFA ∩ PDA question ─────────────
        if (cross_count < cross_budget
                and _cross_eligible
                and random.random() < _CROSS_MACHINE_FRACTION):
            op_id, q1, q2 = random.choice(_cross_eligible)
            key = f"{q1['template_id']}_DFA_PDA_INTERSECT_{q2['template_id']}"
            if key in used_keys:
                continue
            used_keys.add(key)
            combined.append(_apply_dfa_pda_intersection(q1, q2))
            cross_count += 1
            continue

        # ── Regular same-machine closure question ─────────────────────────────
        # Pick machine proportional to number of questions
        machines = list(by_machine.keys())
        weights  = [len(by_machine[m]) for m in machines]
        total_w  = sum(weights)
        r        = random.random() * total_w
        machine  = machines[0]
        cum      = 0.0
        for m, w in zip(machines, weights):
            cum += w
            if r <= cum:
                machine = m
                break

        ops = _CLOSURE_OPS.get(machine, [])
        if not ops:
            continue

        op_id, arity, op_en, op_tag = _weighted_choice(ops)

        if arity == 2:
            eligible = [qs for (mach, _), qs in groups.items()
                        if mach == machine and len(qs) >= 2]
            if not eligible:
                continue
            pool = random.choice(eligible)
            # Prefer cross-template pairs
            pairs = [(pool[i], pool[j])
                     for i in range(len(pool))
                     for j in range(i + 1, len(pool))
                     if pool[i]["template_id"] != pool[j]["template_id"]]
            if not pairs:
                if len(pool) >= 2:
                    pairs = [(pool[i], pool[i + 1])
                             for i in range(len(pool) - 1)]
                else:
                    continue
            q1, q2 = random.choice(pairs)
            key = f"{q1['template_id']}_{op_tag}_{q2['template_id']}"
            if key in used_keys:
                continue
            used_keys.add(key)
            combined.append(_apply_binary(q1, q2, op_id, op_en, op_tag))

        else:   # arity == 1
            q = random.choice(by_machine[machine])
            key = f"{op_tag}_{q['template_id']}"
            if key in used_keys:
                continue
            used_keys.add(key)
            combined.append(_apply_unary(q, op_id, op_en, op_tag))

    return combined
