"""
question_guards.py
==================
Four automatic system guards, always enforced during question generation.

These guards ensure every generated question is suitable for student use.
They are the *system's* responsibility — the author cannot disable them.

  require_distinguishable  — no two instances from the same template produce
                             identical pattern strings (i.e. identical languages)
  require_non_empty        — the language L has at least one member string (L ≠ ∅)
  require_non_trivial      — L ≠ ∅  AND  L ≠ Σ*  (not a degenerate language)
  require_balanced         — within the max_length bound, the test-case generator
                             can produce ≥3 ACCEPT and ≥3 REJECT strings

Author vs. system responsibilities
------------------------------------
  Author  →  closure_allowed: true | false   (one line, one decision)
  System  →  require_distinguishable          ┐
             require_non_empty                │  four automatic guards,
             require_non_trivial              │  always on
             require_balanced                 ┘

Public API
----------
  check_distinguishable(q, seen_patterns) -> bool
  check_non_empty(q)    -> bool
  check_non_trivial(q)  -> bool
  check_balanced(q)     -> bool
  apply_guards(q, seen_patterns) -> list[str]
      Returns the (possibly empty) list of failed guard names.
      Empty list  → question passed all guards and is safe to use.
      Non-empty   → question should be discarded (or retried for distinguishable).
      Side-effect: registers q's pattern in seen_patterns ONLY when all guards pass,
                   so a discarded duplicate pattern can still be retried next time.
"""

from __future__ import annotations


# ── individual guard predicates ───────────────────────────────────────────────

def check_distinguishable(q: dict, seen_patterns: set) -> bool:
    """
    Return True if q's pattern has not been seen for the same template before.

    Two instances that produce the same (template_id, pattern) pair describe
    the same language — assigning both to different students would be unfair.

    Note: this function is read-only; the pattern is registered in seen_patterns
    only via apply_guards (after all other guards have also passed).
    """
    key = (q["template_id"], q["pattern"])
    return key not in seen_patterns


def check_non_empty(q: dict) -> bool:
    """
    Return True if the language L described by q contains at least one string.

    Verified by asking the test-case generator for one ACCEPT example within
    the template's max_length bound.  If no such string exists the language is
    effectively empty and the question is unsuitable.
    """
    from testcase_generator import generate_test_cases
    cases = generate_test_cases(q, n_accept=1, n_reject=0)
    return any(c["label"] == "ACCEPT" for c in cases)


def check_non_trivial(q: dict) -> bool:
    """
    Return True if L is neither empty (∅) nor universal (Σ*).

    A language equal to ∅ or Σ* produces a trivial automaton (0-state dead
    machine or single-state accept-all machine) that teaches nothing useful.
    Both an ACCEPT string and a REJECT string must exist within max_length.
    """
    from testcase_generator import generate_test_cases
    cases = generate_test_cases(q, n_accept=1, n_reject=1)
    return (any(c["label"] == "ACCEPT" for c in cases) and
            any(c["label"] == "REJECT"  for c in cases))


def check_balanced(q: dict) -> bool:
    """
    Return True if the test-case generator can produce ≥3 ACCEPT and ≥3 REJECT
    strings within the template's max_length bound.

    Stricter than require_non_trivial: the language may have both accepting and
    rejecting strings in general, but a tight max_length might starve one side —
    producing an unbalanced (and therefore unfair) test set.
    """
    from testcase_generator import generate_test_cases
    cases   = generate_test_cases(q, n_accept=3, n_reject=3)
    accepts = sum(1 for c in cases if c["label"] == "ACCEPT")
    rejects = sum(1 for c in cases if c["label"] == "REJECT")
    return accepts >= 3 and rejects >= 3


# ── combined entry point ──────────────────────────────────────────────────────

def apply_guards(q: dict, seen_patterns: set) -> list[str]:
    """
    Run all four guards against q in cheapest-first order.

    Returns a (possibly empty) list of failed guard names.
    Registers q's pattern in seen_patterns **only** when all guards pass,
    so a discarded duplicate is not permanently blacklisted.

    Cascade rule
    ------------
    If require_non_empty fails, require_non_trivial and require_balanced
    trivially fail too — they are added without re-running the generator.
    Same cascade applies when require_non_trivial fails.
    """
    failures: list[str] = []

    # Guard 1 — cheapest: pure set lookup, no generation needed
    if not check_distinguishable(q, seen_patterns):
        failures.append("require_distinguishable")

    # Guards 2–4 — language-property checks
    # One combined probe handles require_non_empty + require_non_trivial together.
    from testcase_generator import generate_test_cases

    probe      = generate_test_cases(q, n_accept=1, n_reject=1)
    has_accept = any(c["label"] == "ACCEPT" for c in probe)
    has_reject = any(c["label"] == "REJECT"  for c in probe)

    if not has_accept:
        # Empty language → non-trivial and balanced trivially fail too
        failures.extend(["require_non_empty", "require_non_trivial",
                         "require_balanced"])
    elif not has_reject:
        # Universal language (Σ*) → balanced trivially fails too
        failures.extend(["require_non_trivial", "require_balanced"])
    else:
        # Non-empty and non-trivial confirmed; check balance depth
        balanced_probe = generate_test_cases(q, n_accept=3, n_reject=3)
        n_acc = sum(1 for c in balanced_probe if c["label"] == "ACCEPT")
        n_rej = sum(1 for c in balanced_probe if c["label"] == "REJECT")
        if n_acc < 3 or n_rej < 3:
            failures.append("require_balanced")

    # Register pattern only when every guard passes
    if not failures:
        seen_patterns.add((q["template_id"], q["pattern"]))

    return failures
