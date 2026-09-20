"""
testcase_generator.py
=====================
Generates 20 test cases per question: 10 ACCEPT + 10 REJECT.

Each test case is a dict with exactly two keys:
    {'input': str, 'label': 'ACCEPT' | 'REJECT'}

The test cases are deliberately constructed (not purely random) so that
they cover boundary conditions for each condition type:

  CountModConstraint   count(R) % k == v   → counts ≡ v and ≡ v+1 (mod k)
  CountConstraint      count(R) == N        → exact counts, off-by-one
  LengthConstraint     length(s) <rel> k    → lengths straddling threshold
  LengthModConstraint  length(s) % k == v  → lengths ≡ v and ≡ v+1 (mod k)
  PalindromeNode                            → constructed palindromes / broken
  StringPredicateNode  begins/ends/contains → with / without the target string
  FollowPredicateNode  every(A) followed_by(B) → valid / invalid sequences

Public API
----------
  generate_test_cases(question, n_accept=10, n_reject=10) -> list[dict]
  Each dict: {'input': str, 'label': 'ACCEPT' | 'REJECT'}
"""

from __future__ import annotations

import itertools
import random
from typing import Any

from ast_nodes import (
    CountConstraintNode, CountModConstraintNode,
    LengthConstraintNode, LengthModConstraintNode,
    PrefixCountConstraintNode,
    VarConstraintNode, PalindromeNode, NoAdjacentSameNode, PrefixOrderNode,
    StringPredicateNode, FollowPredicateNode, KthFromEndNode,
    IntLitNode, IdentNode, MulExprNode, DecimalEquivalentConstraintNode,
    OrConstraintNode,
)
from template_handler import Instantiator


# ══════════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _tc(inp: str, label: str) -> dict:
    return {"input": inp, "label": label}

def _shuffle(lst: list) -> list:
    lst = list(lst); random.shuffle(lst); return lst

def _cap(s: str, max_len: int) -> str:
    return s[:max_len]

def _make(symbols: list[str], length: int) -> str:
    if not symbols or length <= 0:
        return ""
    return "".join(random.choices(symbols, k=length))

def _resolve(node: Any, param_map: dict, default: int = 2) -> int:
    try:
        return int(Instantiator.eval_expr(node, {}, param_map))
    except (ValueError, TypeError):
        return default

def _pad(cases: list[dict], label: str, alphabet: list[str],
         target: int, max_len: int) -> None:
    while len(cases) < target:
        cases.append(_tc(_make(alphabet, random.randint(0, max_len)), label))


# ══════════════════════════════════════════════════════════════════════════════
#  PER-CONDITION GENERATORS
# ══════════════════════════════════════════════════════════════════════════════

def _gen_count_mod(role_sym: str, others: list[str], k: int, v: int,
                   max_len: int, na: int, nr: int) -> list[dict]:
    acc, rej = [], []
    for mult in range(na):
        cnt = v + mult * k
        if cnt > max_len:
            cnt = v % (max_len + 1)
        fill = min(random.randint(0, max_len - cnt), max_len - cnt)
        s = list(role_sym * cnt)
        if others and fill > 0:
            s += list(_make(others, fill))
        random.shuffle(s)
        acc.append(_tc(_cap("".join(s), max_len), "ACCEPT"))
    for mult in range(nr):
        bad = v + 1 + mult * k
        if bad > max_len:
            bad = (v + 1) % k if k > 1 else v + 2
        bad = max(bad, 1)
        rej.append(_tc(_cap(role_sym * bad, max_len), "REJECT"))
    return acc + rej


def _gen_count_exact(role_sym: str, others: list[str], target: int | None,
                     is_free: bool, max_len: int, na: int, nr: int) -> list[dict]:
    acc, rej = [], []
    if is_free:
        for t in range(1, na + 1):
            headroom = max(0, max_len - t)
            fill = random.randint(0, headroom) if headroom > 0 else 0
            s = list(role_sym * t)
            if others and fill > 0:
                s += list(_make(others, fill))
            random.shuffle(s)
            acc.append(_tc(_cap("".join(s), max_len), "ACCEPT"))
        rej.append(_tc("", "REJECT"))
        for _ in range(nr - 1):
            rej.append(_tc(_cap(_make(others or [role_sym],
                                      random.randint(1, max_len)), max_len),
                           "REJECT"))
        return acc + rej
    k = target if target is not None else 2
    for _ in range(na):
        extra = min(random.randint(0, max_len - k), max_len - k)
        s = list(role_sym * k)
        if others and extra > 0:
            s += list(_make(others, extra))
        random.shuffle(s)
        acc.append(_tc(_cap("".join(s), max_len), "ACCEPT"))
    for delta in range(1, nr + 1):
        bad = k + (delta if delta % 2 == 1 else -(delta // 2))
        bad = max(0, min(bad, max_len))
        rej.append(_tc(_cap(role_sym * bad, max_len), "REJECT"))
    return acc + rej


def _gen_length(rel: str, k: int, alphabet: list[str],
                max_len: int, na: int, nr: int) -> list[dict]:
    """
    Generate test cases for  length <rel> k.

    Boundary-first strategy — the most instructive cases appear first:

      length == k   ACCEPT: exactly length k (varied content each time)
                    REJECT: k-1 and k+1 first, then spread away
      length != k   ACCEPT: k-1, k+1, spread; REJECT: exactly k
      length <= k   ACCEPT: k, k-1, …, 0    (boundary and below)
                    REJECT: k+1, k+2, …     (just above the boundary first)
      length >= k   ACCEPT: k, k+1, k+2, …  (boundary and above)
                    REJECT: k-1, k-2, …     (just below the boundary first)
      length < k    ACCEPT: k-1, k-2, …;    REJECT: k, k+1, …
      length > k    ACCEPT: k+1, k+2, …;    REJECT: k, k-1, …
    """
    ops = {"==": int.__eq__, "!=": int.__ne__,
           "<":  int.__lt__,  ">":  int.__gt__,
           "<=": int.__le__, ">=": int.__ge__}
    ok = ops.get(rel, lambda a, b: False)

    def satisfies(ln: int) -> bool:
        return ln >= 0 and ok(ln, k)

    # Priority list: boundary-adjacent first, then spread
    priority = [k, k - 1, k + 1, k - 2, k + 2, 0, 1, 2, 3]
    spread   = list(range(0, max_len + 1))
    seen: set[int] = set()
    ordered: list[int] = []
    for ln in priority + spread:
        if ln < 0 or ln > max_len or ln in seen:
            continue
        seen.add(ln)
        ordered.append(ln)

    acc_lens = [ln for ln in ordered if     satisfies(ln)]
    rej_lens = [ln for ln in ordered if not satisfies(ln)]

    acc = [_tc(_make(alphabet, ln), "ACCEPT") for ln in acc_lens[:na]]
    rej = [_tc(_make(alphabet, ln), "REJECT") for ln in rej_lens[:nr]]

    # Pad with the nearest valid length if not enough distinct lengths exist
    while len(acc) < na:
        ln = acc_lens[0] if acc_lens else 0
        acc.append(_tc(_make(alphabet, ln), "ACCEPT"))
    while len(rej) < nr:
        ln = rej_lens[0] if rej_lens else max(k + 1, 1)
        rej.append(_tc(_make(alphabet, ln), "REJECT"))

    return acc + rej

def _gen_decimal_equivalent(k: int, v: int, alphabet: list[str],
                            max_len: int, na: int, nr: int) -> list[dict]:
    """
    Generate test cases for  decimal_equivalent(s) % k == v.

    Boundary-first strategy (Boundary Value Analysis + Equivalence Partitioning):

    ACCEPT — systematically enumerate binary strings whose decimal value ≡ v (mod k):
      1. Smallest representative of the target residue class: the binary
         representation of v itself (or v + k, v + 2k, … if v is 0 and we want
         non-empty strings).
      2. Strings of length 1, 2, 3, … up to max_len, picking the first value
         in each length class that hits the target residue.  This gives one
         boundary representative per length — a standard BVA approach for
         modular constraints.

    REJECT — cover every non-v residue class (Equivalence Partitioning):
      Cycle through residues r ≠ v and emit the binary representation of r
      (or r + k, r + 2k, …) so that all k-1 failing classes are represented,
      not just v+1.  This mirrors the strategy used by _gen_length_mod.
    """
    acc: list[dict] = []
    rej: list[dict] = []

    # ── ACCEPT: one representative per length, boundary-first ─────────────────
    # For length L, the smallest binary string of length L with value ≡ v (mod k)
    # starts from  2^(L-1)  (leading 1) and steps by 1 until we hit the residue.
    for length in range(1, max_len + 1):
        if len(acc) >= na:
            break
        lo = 1 << (length - 1)          # smallest L-digit binary number
        hi = (1 << length) - 1          # largest  L-digit binary number
        # Find the first value in [lo, hi] with value % k == v
        offset = (v - lo % k) % k
        target = lo + offset
        if target <= hi:
            s = bin(target)[2:]          # strip '0b'
            acc.append(_tc(s, "ACCEPT"))

    # Pad by cycling through lengths again with random pick in the class
    while len(acc) < na:
        length = random.randint(1, max_len)
        lo = 1 << (length - 1)
        hi = (1 << length) - 1
        offset = (v - lo % k) % k
        target = lo + offset
        if target <= hi:
            # Pick a random element of the same residue class within this length
            target += random.randint(0, (hi - target) // k) * k
            s = bin(target)[2:]
            acc.append(_tc(s, "ACCEPT"))

    # ── REJECT: cycle through all non-v residue classes (BVA + EP) ────────────
    other_residues = [r for r in range(k) if r != v]
    if not other_residues:
        other_residues = [(v + 1) % max(k, 2)]   # k==1 edge-case

    cursor = 0
    mult   = {r: 0 for r in other_residues}
    while len(rej) < nr:
        r = other_residues[cursor % len(other_residues)]
        # Construct the binary string: r + mult[r]*k, represented in binary
        val = r + mult[r] * k
        if val == 0:
            val += k   # skip zero — use next representative in this class
        if len(bin(val)) - 2 > max_len:
            val = r if r > 0 else k   # wrap to smallest representative
        s = bin(val)[2:]
        if len(s) <= max_len:
            rej.append(_tc(s, "REJECT"))
        mult[r] += 1
        cursor   += 1
        if cursor > (nr + len(other_residues)) * 3:
            break   # safety valve against infinite loop on degenerate inputs

    return acc + rej

def _decimal_equivalent(s: str) -> int:
    return int(s, 2)
def _gen_length_mod(k: int, v: int, alphabet: list[str],
                    max_len: int, na: int, nr: int) -> list[dict]:
    """
    Generate test cases for  length % k == v.

    ACCEPT: lengths ≡ v (mod k) — v, v+k, v+2k, … clipped to max_len.

    REJECT: cycle through EVERY non-v residue class rather than only v+1.
        e.g. k=4, v=0 → reject residues 1, 2, 3, 1, 2, 3, …
        This ensures all failing residue classes are represented, not just
        the immediately adjacent one.
    """
    acc, rej = [], []

    # ACCEPT
    mult = 0
    while len(acc) < na:
        ln = v + mult * k
        if ln > max_len:
            ln = v          # wrap to smallest valid accept length
        acc.append(_tc(_make(alphabet, ln), "ACCEPT"))
        mult += 1

    # REJECT — spread across all non-v residue classes
    other_residues = [r for r in range(k) if r != v]
    if not other_residues:
        # k == 1: length%1 is always 0; edge case — pad with arbitrary strings
        other_residues = [0]

    mult_per_r = {r: 0 for r in other_residues}
    rej_cursor = 0
    while len(rej) < nr:
        r  = other_residues[rej_cursor % len(other_residues)]
        ln = r + mult_per_r[r] * k
        if ln > max_len:
            ln = r          # fallback to the representative of this residue
        if ln < 0:
            ln = r
        rej.append(_tc(_make(alphabet, ln), "REJECT"))
        mult_per_r[r] += 1
        rej_cursor    += 1

    return acc + rej


def _gen_palindrome(alphabet: list[str],
                    max_len: int, na: int, nr: int) -> list[dict]:
    acc, rej = [], []
    for i in range(na):
        half = random.randint(0, max_len // 2)
        h    = _make(alphabet, half)
        mid  = random.choice(alphabet) if i % 2 == 1 else ""
        acc.append(_tc(_cap(h + mid + h[::-1], max_len), "ACCEPT"))
    for _ in range(nr):
        s = _make(alphabet, random.randint(2, max_len))
        if s == s[::-1] and len(alphabet) > 1:
            alts = [c for c in alphabet if c != s[-1]]
            if alts:
                s = s[:-1] + random.choice(alts)
        rej.append(_tc(_cap(s, max_len), "REJECT"))
    return acc + rej


def _gen_string_pred(kind: str, pattern: str, alphabet: list[str],
                     max_len: int, na: int, nr: int) -> list[dict]:
    acc, rej = [], []
    plen = len(pattern)
    for _ in range(na):
        room   = max(0, max_len - plen)
        filler = _make(alphabet, random.randint(0, room))
        if kind == "begins_with":
            s = _cap(pattern + filler, max_len)
        elif kind == "ends_with":
            s = _cap(filler + pattern, max_len)
        else:  # contains
            pos = random.randint(0, len(filler))
            s   = _cap(filler[:pos] + pattern + filler[pos:], max_len)
        acc.append(_tc(s, "ACCEPT"))
    safe = [c for c in alphabet if c not in set(pattern)] or alphabet
    for _ in range(nr):
        s = _make(safe, random.randint(1, max_len))
        # Ensure it genuinely doesn't match
        if kind == "begins_with" and s.startswith(pattern):
            s = s[plen:] or _make(safe, 1)
        elif kind == "ends_with" and s.endswith(pattern):
            s = s[:-plen] or _make(safe, 1)
        rej.append(_tc(_cap(s, max_len), "REJECT"))
    return acc + rej


def _gen_no_adjacent_same(alphabet: list[str], max_len: int, na: int, nr: int) -> list[dict]:
    """Generate ACCEPT (no two adjacent same) and REJECT (at least one adjacent repeat) cases."""
    acc, rej = [], []
    # ACCEPT: empty, single-char, or build by always choosing next symbol different from previous
    for _ in range(na):
        L = random.randint(0, max_len)
        if L == 0:
            s = ""
        else:
            s_list = [random.choice(alphabet)]
            for _ in range(L - 1):
                others = [a for a in alphabet if a != s_list[-1]]
                s_list.append(random.choice(others))
            s = "".join(s_list)
        acc.append(_tc(_cap(s, max_len), "ACCEPT"))
    # REJECT: force at least one adjacent repeat
    for _ in range(nr):
        L = random.randint(2, max_len)
        pos = random.randint(0, L - 2)  # position where we repeat
        s_list = []
        for i in range(L):
            if i == pos + 1 and s_list:
                s_list.append(s_list[-1])
            else:
                prev = s_list[-1] if s_list else None
                choices = [a for a in alphabet if a != prev] if prev else alphabet
                s_list.append(random.choice(choices))
        rej.append(_tc(_cap("".join(s_list), max_len), "REJECT"))
    return acc + rej


def _gen_follow(trigger: str, follower: str, alphabet: list[str],
                max_len: int, na: int, nr: int) -> list[dict]:
    safe  = [s for s in alphabet if s not in (trigger, follower)] or [follower]
    acc, rej = [], []
    for _ in range(na):
        parts: list[str] = []
        target = random.randint(0, max_len)
        while len(parts) < target:
            if random.random() < 0.35 and len(parts) + 2 <= target:
                parts += [trigger, follower]
            else:
                parts.append(random.choice(safe + [follower]))
        acc.append(_tc(_cap("".join(parts), max_len), "ACCEPT"))
    for _ in range(nr):
        bad   = random.choice(safe) if safe else "X"
        pre   = _make(safe, random.randint(0, max(0, max_len - 2)))
        s     = _cap(pre + trigger + bad, max_len)
        rej.append(_tc(s, "REJECT"))
    return acc + rej


def _gen_prefix_count(sym1: str, sym2: str, rel: str, alphabet: list[str],
                      max_len: int, na: int, nr: int) -> list[dict]:
    """
    Generate ACCEPT/REJECT cases for prefix_count(sym1) <rel> prefix_count(sym2).
    For >= : at every prefix, count(sym1) >= count(sym2) (Dyck-like).
    """
    acc, rej = [], []
    # ACCEPT: strings satisfying the prefix condition (e.g. Dyck words for >=)
    for _ in range(na):
        for attempt in range(100):
            L = random.randint(2, min(max_len, 50))
            if L % 2 != 0:
                L -= 1
            if L < 2:
                L = 2
            n = L // 2
            positions = set(random.sample(range(L), n))
            s_list = [sym1 if i in positions else sym2 for i in range(L)]
            random.shuffle(s_list)
            s = "".join(s_list)
            valid = True
            for i in range(len(s) + 1):
                pre = s[:i]
                c1, c2 = pre.count(sym1), pre.count(sym2)
                op = {"==": int.__eq__, "!=": int.__ne__, "<": int.__lt__,
                      ">": int.__gt__, "<=": int.__le__, ">=": int.__ge__}.get(rel, lambda a, b: True)
                if not op(c1, c2):
                    valid = False
                    break
            if valid:
                acc.append(_tc(_cap(s, max_len), "ACCEPT"))
                break
        else:
            # fallback: all sym1 then all sym2 (valid for >=)
            half = min(max_len // 2, 25)
            acc.append(_tc(_cap(sym1 * half + sym2 * half, max_len), "ACCEPT"))
    # REJECT: violate prefix condition. Include structured cases where total count
    # matches but prefix condition fails (e.g. starting with sym2: ][, ][][, ]][[).
    structured_rej = []
    # sym2 + sym1  (e.g. ][) — count matches, but first prefix has 0 sym1, 1 sym2
    s1 = _cap(sym2 + sym1, max_len)
    if len(s1) >= 2:
        structured_rej.append(_tc(s1, "REJECT"))
    # sym2 + sym1 + sym2 + sym1  (e.g. ][][)
    s2 = _cap(sym2 + sym1 + sym2 + sym1, max_len)
    if len(s2) >= 4:
        structured_rej.append(_tc(s2, "REJECT"))
    # sym2 + sym2 + sym1 + sym1  (e.g. ]][[) — count matches, prefix after 2 chars fails
    s3 = _cap(sym2 + sym2 + sym1 + sym1, max_len)
    if len(s3) >= 4:
        structured_rej.append(_tc(s3, "REJECT"))
    rej.extend(structured_rej)
    # Fill remaining with random rejections (start with sym2)
    while len(rej) < nr:
        rest = _make([sym1, sym2], random.randint(0, max(0, max_len - 1)))
        s = _cap(sym2 + rest, max_len)
        if not s:
            s = sym2 + sym1
        rej.append(_tc(s, "REJECT"))
    # Trim to nr if we added too many structured cases
    rej = rej[:nr]
    return acc + rej


def _is_block_ordered(s: str, syms: list[str]) -> bool:
    """
    Return True iff all symbols in `syms` appear in consecutive blocks
    in left-to-right order — once a later-index symbol appears, no
    earlier-index symbol may appear again.
    """
    last_idx = -1
    for ch in s:
        if ch in syms:
            idx = syms.index(ch)
            if idx < last_idx:
                return False
            last_idx = idx
    return True


def _solve_free_vars(conditions: list, param_map: dict,
                     free_vars: set, max_len: int,
                     n_roles: int) -> dict[str, int]:
    """
    Solve for ALL free variables using one consistent base value so that
    every condition in the list is satisfied simultaneously.

    Algorithm
    ---------
    1. FIND BASE VARIABLE — the "deepest" free var in the inequality chain:
       the one that appears ONLY on the RHS of VarConstraintNodes (never as
       LHS of a free-var-to-free-var constraint).
       Example:  M > N > P  →  P is the base (M and N are derived from it).
       Fallback: a free var appearing bare on the RHS of a CountConstraint,
       then alphabetically first.

    2. COMPUTE MULTIPLIER SUM of base var across count constraints to ensure
       total string length stays within max_len.

    3. PICK base_val = randint(1, base_max).

    4. RESOLVE ALL OTHER FREE VARS in topological order using repeated passes
       over the VarConstraintNodes until no more changes occur.
         lhs > rhs  →  lhs = rhs + randint(1,3)
         lhs < rhs  →  lhs = max(1, rhs - randint(1,3))
         lhs > 0    →  skip (base_val >= 1 handles this)

    5. FILL any still-unresolved free vars with base_val.
    """
    from ast_nodes import IdentNode, MulExprNode, IntLitNode, VarConstraintNode

    # Identify free-var-to-free-var VarConstraints (exclude X > 0 guards)
    fv_constraints = [
        c for c in conditions
        if isinstance(c, VarConstraintNode)
        and c.lhs in free_vars
        and isinstance(c.rhs, IdentNode)
        and c.rhs.name in free_vars
    ]

    # ── Step 1: find base variable ────────────────────────────────────────────
    # Base = free var that never appears as LHS in a fv-to-fv constraint.
    # This is the "deepest" in the chain (e.g. P in M>N>P).
    lhs_vars = {c.lhs for c in fv_constraints}
    rhs_vars = {c.rhs.name for c in fv_constraints}

    # Candidates: appear on RHS but not as LHS of any fv-fv constraint
    candidates = rhs_vars - lhs_vars
    if candidates:
        base_var = sorted(candidates)[0]
    else:
        # No chain — fall back to free var bare in a count constraint RHS
        base_var = None
        for c in conditions:
            if isinstance(c, CountConstraintNode) and c.rel == "==":
                if isinstance(c.rhs, IdentNode) and c.rhs.name in free_vars:
                    base_var = c.rhs.name
                    break
        if base_var is None and free_vars:
            base_var = sorted(free_vars)[0]

    # ── Step 2: compute total multiplier for base var ─────────────────────────
    total_mult = 0
    for c in conditions:
        if not isinstance(c, CountConstraintNode) or c.rel != "==":
            continue
        rhs = c.rhs
        if isinstance(rhs, IdentNode) and rhs.name == base_var:
            total_mult += 1
        elif isinstance(rhs, MulExprNode):
            for side, other in [(rhs.left, rhs.right), (rhs.right, rhs.left)]:
                if isinstance(other, IdentNode) and other.name == base_var:
                    try:
                        total_mult += int(Instantiator.eval_expr(side, {}, param_map))
                    except (ValueError, TypeError):
                        total_mult += 1
                    break
    if total_mult <= 0:
        total_mult = max(n_roles, 1)

    # ── Step 3: pick base value ───────────────────────────────────────────────
    base_max = max(1, max_len // total_mult)
    base_val = random.randint(1, base_max)

    result: dict[str, int] = {}
    if base_var:
        result[base_var] = base_val

    # ── Step 4: resolve all other free vars iteratively ──────────────────────
    # Repeat until no new resolutions occur (handles chains of any length)
    def _try_resolve(c) -> bool:
        if not isinstance(c, VarConstraintNode):
            return True
        lhs = c.lhs
        if lhs not in free_vars or lhs in result:
            return True
        # Skip trivial positivity guards (X > 0)
        if isinstance(c.rhs, IntLitNode) and c.rhs.value == 0:
            return False
        try:
            rhs_val = int(Instantiator.eval_expr(
                c.rhs, {}, {**param_map, **result}))
        except (ValueError, TypeError):
            return False
        if c.rel == ">":
            result[lhs] = rhs_val + random.randint(1, 3)
        elif c.rel == "<":
            result[lhs] = max(1, rhs_val - random.randint(1, 3))
        elif c.rel == ">=":
            result[lhs] = rhs_val + random.randint(0, 2)
        elif c.rel == "<=":
            result[lhs] = max(1, rhs_val - random.randint(0, 2))
        elif c.rel == "==":
            result[lhs] = rhs_val
        return True

    # Up to len(free_vars) passes covers any chain depth
    for _ in range(max(2, len(free_vars))):
        for c in conditions:
            _try_resolve(c)

    # ── Step 5: fill any still-unresolved free vars with base_val ─────────────
    for v in free_vars:
        if v not in result:
            result[v] = base_val

    # ── Step 6: fix violated VarConstraints in dependency order ───────────────
    # Strategy: build a topological order of free-var constraints so that
    # "deepest" variables (those only on RHS) are fixed first, then variables
    # that depend on them.  This prevents fixing M<N from conflicting with N<P
    # in the same pass.
    #
    # Simple approach: sort constraints so that RHS variables are processed
    # before LHS variables that reference them.  Repeat until stable.

    # Collect only fv-to-fv strict inequality constraints
    fv_ineq = [c for c in conditions
               if isinstance(c, VarConstraintNode)
               and c.lhs in result
               and isinstance(c.rhs, IdentNode)
               and c.rhs.name in result]

    # Topological sort: if A < B, process B (RHS) before A (LHS)
    # We want the RHS variable to be correct before we fix the LHS.
    # Simple: repeatedly pick a constraint whose RHS is not the LHS of
    # any other unprocessed constraint.
    ordered = []
    remaining = list(fv_ineq)
    for _ in range(len(fv_ineq) + 1):
        if not remaining:
            break
        # Find a constraint whose RHS.name is not any remaining LHS
        remaining_lhs = {c.lhs for c in remaining}
        promoted = [c for c in remaining if c.rhs.name not in remaining_lhs]
        if promoted:
            ordered.extend(promoted)
            for c in promoted:
                remaining.remove(c)
        else:
            # Cycle — just append rest
            ordered.extend(remaining)
            break

    # Now fix in topological order (deepest RHS first), multiple passes
    for _pass in range(len(free_vars) + 2):
        changed = False
        for c in ordered:
            lhs, rhs_name = c.lhs, c.rhs.name
            if lhs not in result or rhs_name not in result:
                continue
            lhs_val = result[lhs]
            rhs_val = result[rhs_name]
            if c.rel == "<" and not (lhs_val < rhs_val):
                # Bump RHS up so there's room, then set LHS = RHS - 1
                result[rhs_name] = lhs_val + 2   # RHS = LHS + 2 → room for LHS+1
                result[lhs]      = lhs_val + 1   # LHS = old_LHS + 1 < new_RHS
                changed = True
            elif c.rel == ">" and not (lhs_val > rhs_val):
                result[lhs] = rhs_val + 1
                changed = True
            elif c.rel == "<=" and not (lhs_val <= rhs_val):
                result[lhs] = rhs_val
                changed = True
            elif c.rel == ">=" and not (lhs_val >= rhs_val):
                result[lhs] = rhs_val
                changed = True
        if not changed:
            break

    # ── Step 7: satisfy any violated OrConstraintNodes ────────────────────────
    # Best practice: when a disjunction like "M != N or N != P" exists, the
    # default assignment (all free vars = base_val) may violate every branch
    # simultaneously (all operands false → OR false → ACCEPT string rejected).
    # Fix: perturb the LHS of the first unsatisfied oprand to force at least
    # one branch true.  _derive_counts preserves the resulting ordering when
    # it scales, so the ACCEPT string remains valid after this adjustment.
    #
    # This implements the MC/DC (Modified Condition/Decision Coverage) principle:
    # ensure each sub-condition in a disjunction can independently determine
    # the outcome — which requires at least one assignment per branch.
    def _or_op_sat(op) -> bool:
        """Return True iff VarConstraintNode op is satisfied by current result."""
        if not isinstance(op, VarConstraintNode):
            return True  # non-Var operands assumed satisfied (not free-var constraints)
        lv = result.get(op.lhs, 0)
        try:
            rv = int(Instantiator.eval_expr(op.rhs, {}, result))
        except (ValueError, TypeError):
            return True
        return {"==": lv == rv, "!=": lv != rv, "<": lv < rv,
                ">": lv > rv, "<=": lv <= rv, ">=": lv >= rv}.get(op.rel, True)

    for c in conditions:
        if not isinstance(c, OrConstraintNode):
            continue
        if any(_or_op_sat(op) for op in c.operands):
            continue  # OR already satisfied — nothing to fix

        # Force-satisfy the first operand whose LHS is a free var in result
        for op in c.operands:
            if not isinstance(op, VarConstraintNode) or op.lhs not in result:
                continue
            try:
                rv = int(Instantiator.eval_expr(op.rhs, {}, result))
            except (ValueError, TypeError):
                continue
            if op.rel == "!=":
                result[op.lhs] = rv + random.randint(1, 3)
            elif op.rel == ">":
                result[op.lhs] = rv + random.randint(1, 3)
            elif op.rel == "<":
                result[op.lhs] = max(1, rv - random.randint(1, 3))
            elif op.rel == ">=":
                result[op.lhs] = rv
            elif op.rel == "<=":
                result[op.lhs] = max(1, rv - random.randint(0, 2))
            break  # first operand fixed → OR now satisfied

    return result





def _derive_counts(ordered_roles: list[str], role_map: dict,
                   conditions: list, param_map: dict,
                   free_var_vals: dict[str, int],
                   max_len: int) -> list[int]:
    """
    Evaluate each count constraint to get a concrete count per role,
    using the fully-resolved free_var_vals.

    Handles both equality and inequality count constraints:
      count(R) == expr  → count = eval(expr)
      count(R) > expr   → count = eval(expr) + 1
      count(R) >= expr  → count = eval(expr)
      count(R) < expr   → count = max(0, eval(expr) - 1)
      count(R) <= expr  → count = eval(expr)

    Equality constraints take priority (checked first). Inequality
    constraints are used only if no equality constraint exists for the role.

    Scaling: if total exceeds max_len, scale proportionally while
    preserving strict ordering relationships between counts.
    """
    augmented = {**param_map, **free_var_vals}
    counts = []
    for role in ordered_roles:
        sym   = role_map.get(role, role)
        count = None
        # Pass 1: equality constraints (most precise)
        for c in conditions:
            if not isinstance(c, CountConstraintNode) or c.rel != "==":
                continue
            if role_map.get(c.role, c.role) != sym:
                continue
            try:
                count = max(1, int(Instantiator.eval_expr(c.rhs, role_map, augmented)))
                break
            except (ValueError, TypeError):
                pass
        # Pass 2: inequality constraints (if no equality found)
        if count is None:
            for c in conditions:
                if not isinstance(c, CountConstraintNode):
                    continue
                if role_map.get(c.role, c.role) != sym:
                    continue
                try:
                    rhs_val = int(Instantiator.eval_expr(c.rhs, role_map, augmented))
                except (ValueError, TypeError):
                    continue
                if c.rel == ">":
                    count = rhs_val + random.randint(1, 3)
                elif c.rel == ">=":
                    count = rhs_val + random.randint(0, 2)
                elif c.rel == "<":
                    count = max(0, rhs_val - random.randint(1, 3))
                elif c.rel == "<=":
                    count = max(0, rhs_val - random.randint(0, 2))
                if count is not None:
                    count = max(1, count)
                    break
        counts.append(count if count is not None else 1)

    total = sum(counts)
    if total > max_len:
        # Scale while preserving strict ordering between counts
        factor = max_len / total
        scaled = [max(1, int(c * factor)) for c in counts]
        order  = sorted(range(len(counts)), key=lambda i: counts[i])
        for rank, idx in enumerate(order):
            if rank > 0:
                prev_idx = order[rank - 1]
                if counts[idx] > counts[prev_idx] and scaled[idx] <= scaled[prev_idx]:
                    scaled[idx] = scaled[prev_idx] + 1
        counts = scaled

    return counts


def _satisfies_conditions(s: str, ordered_roles: list[str], role_map: dict,
                           conditions: list, param_map: dict,
                           free_var_vals: dict[str, int] | None = None,
                           string_map: dict | None = None) -> bool:
    """
    Check whether string `s` satisfies ALL conditions simultaneously.

    Key design: free variable values are INFERRED from the actual counts
    in the string, not taken from an external assignment.  This ensures
    the check is always consistent with what is actually in the string.

    Specifically:
      For each CountConstraintNode  count(R) == expr(free_vars):
        actual_count = s.count(role_sym)
        We back-solve: if expr is just a bare variable V, then V = actual_count.
        If expr is K*V, then V = actual_count // K.
      VarConstraintNodes (M > N) are then evaluated using these inferred values.

    This means:
      - A string like 'aaaaaabbbbbb' (count(a)=6, count(b)=6) for
        language A^M B^N M>N  will infer M=6, N=6, then check 6>6 → False ✓
      - A string like 'aaaaaaabbbbbb' (count(a)=7, count(b)=6) will infer
        M=7, N=6, check 7>6 → True ✓ (valid accept)
    """
    from ast_nodes import (PrefixOrderNode, CountConstraintNode,
                           CountModConstraintNode, VarConstraintNode,
                           IdentNode, MulExprNode, IntLitNode,
                           DecimalEquivalentConstraintNode,
                           OrConstraintNode)

    syms = [role_map.get(r, r) for r in ordered_roles]

    # ── Step 1: check block ordering ─────────────────────────────────────────
    for c in conditions:
        if isinstance(c, PrefixOrderNode):
            if not _is_block_ordered(s, syms):
                return False

    # ── Step 2: infer free variable values from actual counts in s ───────────
    inferred: dict[str, int] = dict(param_map)   # start with concrete params

    for c in conditions:
        if not isinstance(c, CountConstraintNode) or c.rel != "==":
            continue
        sym    = role_map.get(c.role, c.role)
        actual = s.count(sym)
        rhs    = c.rhs
        # count(R) == V  →  V = actual
        if isinstance(rhs, IdentNode) and rhs.name not in inferred:
            inferred[rhs.name] = actual
        # count(R) == K*V  →  V = actual // K   (K already resolved)
        elif isinstance(rhs, MulExprNode):
            for scalar_side, var_side in [(rhs.left, rhs.right), (rhs.right, rhs.left)]:
                if isinstance(var_side, IdentNode) and var_side.name not in inferred:
                    try:
                        k = int(Instantiator.eval_expr(scalar_side, {}, inferred))
                        inferred[var_side.name] = actual // k if k > 0 else actual
                    except (ValueError, TypeError):
                        pass
                    break

    # ── Step 3: check all count constraints using actual counts ───────────────
    from ast_nodes import CountExprNode
    ops = {"==": int.__eq__, "!=": int.__ne__,
           "<":  int.__lt__,  ">":  int.__gt__,
           "<=": int.__le__, ">=": int.__ge__}
    for c in conditions:
        if isinstance(c, CountConstraintNode):
            sym    = role_map.get(c.role, c.role)
            actual = s.count(sym)
            # Handle count(R) <rel> count(R2)  — CountExprNode on the RHS
            if isinstance(c.rhs, CountExprNode):
                sym2     = role_map.get(c.rhs.role, c.rhs.role)
                expected = s.count(sym2)
            else:
                try:
                    expected = int(Instantiator.eval_expr(c.rhs, role_map, inferred))
                except (ValueError, TypeError):
                    continue
            if not ops.get(c.rel, lambda a,b: True)(actual, expected):
                return False

        elif isinstance(c, CountModConstraintNode):
            sym    = role_map.get(c.role, c.role)
            actual = s.count(sym)
            try:
                mod = int(Instantiator.eval_expr(c.modulus, role_map, inferred))
                val = int(Instantiator.eval_expr(c.value,   role_map, inferred))
            except (ValueError, TypeError):
                continue
            if actual % mod != val:
                return False

        elif isinstance(c, LengthConstraintNode):
            try:
                k = int(Instantiator.eval_expr(c.rhs, role_map, inferred))
            except (ValueError, TypeError):
                continue
            ops = {"==": int.__eq__, "!=": int.__ne__,
                   "<":  int.__lt__,  ">":  int.__gt__,
                   "<=": int.__le__, ">=": int.__ge__}
            if not ops.get(c.rel, lambda a, b: True)(len(s), k):
                return False

        elif isinstance(c, LengthModConstraintNode):
            try:
                mod = int(Instantiator.eval_expr(c.modulus, role_map, inferred))
                val = int(Instantiator.eval_expr(c.value,   role_map, inferred))
            except (ValueError, TypeError):
                continue
            if len(s) % mod != val:
                return False

        elif isinstance(c, VarConstraintNode):
            try:
                lhs_val = inferred.get(c.lhs, 0)
                rhs_val = int(Instantiator.eval_expr(c.rhs, {}, inferred))
            except (ValueError, TypeError):
                continue
            if not ops.get(c.rel, lambda a,b: True)(lhs_val, rhs_val):
                return False

        elif isinstance(c, PalindromeNode):
            if s != s[::-1]:
                return False

        elif isinstance(c, StringPredicateNode):
            # Resolve the concrete string from string_map if available,
            # otherwise use the param name as a literal fallback
            from ast_nodes import StringPredicateNode as SPN
            concrete = string_map.get(c.param, c.param) if string_map else c.param
            if c.kind == "begins_with":
                if not s.startswith(concrete):
                    return False
            elif c.kind == "ends_with":
                if not s.endswith(concrete):
                    return False
            elif c.kind == "contains":
                if concrete not in s:
                    return False

        elif isinstance(c, FollowPredicateNode):
            trigger  = role_map.get(c.trigger,  c.trigger)
            follower = role_map.get(c.follower, c.follower)
            # Every trigger must be immediately followed by follower
            for i in range(len(s) - 1):
                if s[i] == trigger and s[i + 1] != follower:
                    return False
            # Trigger at the very last position also fails
            if s and s[-1] == trigger:
                return False

        elif isinstance(c, KthFromEndNode):
            sym = role_map.get(c.role, c.role)
            k   = inferred.get(c.position_param,
                               param_map.get(c.position_param, 0))
            if not isinstance(k, int):
                try: k = int(k)
                except (ValueError, TypeError): continue
            if len(s) < k or k < 1:
                return False
            if s[len(s) - k] != sym:
                return False

        elif isinstance(c, PrefixCountConstraintNode):
            sym1 = role_map.get(c.role1, c.role1)
            sym2 = role_map.get(c.role2, c.role2)
            for i in range(len(s) + 1):
                pre = s[:i]
                c1, c2 = pre.count(sym1), pre.count(sym2)
                if not ops.get(c.rel, lambda a, b: True)(c1, c2):
                    return False

        elif isinstance(c, NoAdjacentSameNode):
            for i in range(len(s) - 1):
                if s[i] == s[i + 1]:
                    return False

        elif isinstance(c, DecimalEquivalentConstraintNode):
            try:
                mod = int(Instantiator.eval_expr(c.modulus, role_map, inferred))
                val = int(Instantiator.eval_expr(c.value,   role_map, inferred))
                dec = int(s, 2) if s else 0
            except (ValueError, TypeError):
                continue
            if dec % mod != val:
                return False

        elif isinstance(c, OrConstraintNode):
            # Satisfied iff at least one operand is satisfied.
            # Pass `inferred` (not raw param_map) so free variables such as M,
            # N, P that were back-solved from count(R)==V earlier in this loop
            # are visible when evaluating VarConstraintNode operands.
            if not any(
                _satisfies_conditions(
                    s, ordered_roles, role_map, [op],
                    inferred, string_map=string_map
                )
                for op in c.operands
            ):
                return False

    return True


def _gen_prefix_order(ordered_roles: list[str],
                      role_map:       dict,
                      conditions:     list,
                      param_map:      dict,
                      free_vars:      set,
                      max_len:        int,
                      na:             int,
                      nr:             int) -> list[dict]:
    """
    Generate test cases for prefix_order(R0, R1, …) combined with
    count constraints and optional free-variable inequality constraints,
    all evaluated with a SINGLE consistent free-variable assignment.

    ACCEPT strings
    --------------
    1. Solve free vars consistently (_solve_free_vars).
    2. Derive block counts (_derive_counts) using that assignment.
    3. Verify the resulting string satisfies ALL conditions
       (_satisfies_conditions) before emitting — retry if not.

    REJECT strings — three equal types (~nr//3 each)
    -------------------------------------------------
    Type 1 — WRONG ORDER, correct counts and free-var values:
        Shuffle or reverse the blocks.
        Verify the string does NOT satisfy ordering.

    Type 2 — CORRECT ORDER, wrong counts:
        Add 1 to one block, cycling through roles each time.
        CRITICAL: verify the perturbed string actually violates at least
        one condition before emitting. If the perturbation still satisfies
        all conditions (e.g. language accepts any M>N, so M+1>N still holds),
        try a different perturbation (subtract 1, try another block).

    Type 3 — RANDOM string:
        A random string from the role symbols.
        May violate ordering, counts, or both.
    """
    syms = [role_map.get(r, r) for r in ordered_roles]
    acc, rej = [], []

    def make_solution() -> tuple[list[int], dict] | None:
        """
        Return (counts, free_var_vals) for a valid ACCEPT string, or None
        if no valid solution is found within 50 attempts.
        """
        for _ in range(50):
            fv     = _solve_free_vars(conditions, param_map, free_vars,
                                      max_len, len(ordered_roles))
            counts = _derive_counts(ordered_roles, role_map, conditions,
                                    param_map, fv, max_len)
            s = "".join(sym * cnt for sym, cnt in zip(syms, counts))
            if _satisfies_conditions(s, ordered_roles, role_map,
                                     conditions, param_map, fv):
                return counts, fv
        return None   # signal failure — caller must handle

    # ── ACCEPT ────────────────────────────────────────────────────────────────
    for _ in range(na):
        result = make_solution()
        if result is None:
            continue          # skip — validation pass will pad with retries
        counts, fv = result
        s = "".join(sym * cnt for sym, cnt in zip(syms, counts))
        acc.append(_tc(_cap(s, max_len), "ACCEPT"))

    # Split nr into three groups
    n1 = nr // 3 + (1 if nr % 3 > 0 else 0)   # wrong order
    n2 = nr // 3 + (1 if nr % 3 > 1 else 0)   # wrong count
    n3 = nr - n1 - n2                           # random

    # ── REJECT type 1: correct counts, WRONG ORDER ───────────────────────────
    for _ in range(n1):
        result = make_solution()
        if result is None:
            continue
        counts, fv = result
        pool = []
        for sym, cnt in zip(syms, counts):
            pool.extend([sym] * cnt)
        # Try reversed; shuffle if reversal is accidentally ordered
        rev = list(reversed(pool))
        if not _is_block_ordered("".join(rev), syms):
            s = "".join(rev)
        else:
            random.shuffle(pool)
            for _ in range(8):
                if not _is_block_ordered("".join(pool), syms):
                    break
                random.shuffle(pool)
            s = "".join(pool)
        # Verify using the capped string — must actually fail some condition
        s_stored = _cap(s, max_len)
        if not _satisfies_conditions(s_stored, ordered_roles, role_map,
                                     conditions, param_map, fv):
            rej.append(_tc(s_stored, "REJECT"))

    # ── REJECT type 2: correct ORDER, wrong counts ───────────────────────────
    perturb_idx = 0
    attempts    = 0
    while len([r for r in rej if True]) < n1 + n2 and attempts < n2 * 20:
        attempts += 1
        result = make_solution()
        if result is None:
            attempts += 1
            continue
        counts, fv = result
        # Try all perturbations: +1 and -1 on each block in rotation
        idx        = perturb_idx % len(counts)
        perturb_idx += 1
        for delta in (+1, -1):
            bad_counts = list(counts)
            bad_counts[idx] = max(0, counts[idx] + delta)
            if bad_counts == counts:
                continue
            s_raw    = "".join(sym * cnt for sym, cnt in zip(syms, bad_counts))
            s_stored = _cap(s_raw, max_len)
            # Check the STORED (capped) string — not the raw one — because
            # truncation can turn a wrong-count string into a valid accept.
            if not _satisfies_conditions(s_stored, ordered_roles, role_map,
                                         conditions, param_map, fv):
                rej.append(_tc(s_stored, "REJECT"))
                break   # found a valid reject — move to next slot
        if len([r for r in rej if True]) >= n1 + n2:
            break

    # Fill remaining type-2 slots with type-1 style if needed
    while len(rej) < n1 + n2:
        result = make_solution()
        if result is None:
            continue
        counts, fv = result
        pool = [sym for sym, cnt in zip(syms, counts) for _ in range(cnt)]
        random.shuffle(pool)
        s_stored = _cap("".join(pool), max_len)
        if not _satisfies_conditions(s_stored, ordered_roles, role_map,
                                     conditions, param_map, fv):
            rej.append(_tc(s_stored, "REJECT"))

    # ── REJECT type 3: random strings (validated) ────────────────────────────
    # Each random string is checked; if it accidentally satisfies all
    # conditions it is discarded and we try again.  After 30 failed
    # attempts we emit a guaranteed violation: a single-symbol string of
    # the wrong symbol (e.g. all B's when A must come first).
    for _ in range(n3):
        for attempt in range(30):
            length = random.randint(0, max_len)
            s      = _make(syms, length)
            # Use a fresh fv for the check so the comparison is fair
            fv_check = _solve_free_vars(conditions, param_map, free_vars,
                                        max_len, len(ordered_roles))
            if not _satisfies_conditions(s, ordered_roles, role_map,
                                         conditions, param_map, fv_check):
                rej.append(_tc(s, "REJECT"))
                break
        else:
            # Guaranteed fallback: reversed single-block string (wrong order)
            s_stored = _cap(syms[-1] * 2 + syms[0] * 2, max_len)
            rej.append(_tc(s_stored, "REJECT"))

    # ── REJECT type 4: OR-branch exhaustion (MC/DC best practice) ────────────
    # MC/DC (Modified Condition/Decision Coverage) requires a test case where
    # EVERY operand of each OR constraint is simultaneously false.  The
    # standard type-2 perturbation often misses this because changing one
    # count while keeping others equal still satisfies "M != N or N != P"
    # via the perturbed role.
    #
    # Strategy: assign all free vars the same value so that all != operands
    # evaluate to false, then build a correctly-ordered block string.
    # _satisfies_conditions infers actual counts from the string, so the
    # "symmetric" string (e.g. a^k b^k c^k) correctly evaluates the OR as
    # False and is emitted as REJECT.
    or_nodes = [c for c in conditions if isinstance(c, OrConstraintNode)]
    if or_nodes and len(rej) < nr:
        need = nr - len(rej)
        for _ in range(need * 4):
            if len(rej) >= nr:
                break
            eq_val = random.randint(1, max(1, max_len // max(len(syms), 1)))
            eq_fv  = {v: eq_val for v in free_vars}
            # derive counts with equal free vars — result is equal block sizes
            sym_counts = _derive_counts(ordered_roles, role_map, conditions,
                                        param_map, eq_fv, max_len)
            s = "".join(sym * cnt for sym, cnt in zip(syms, sym_counts))
            s_stored = _cap(s, max_len)
            # Only emit if it genuinely fails (all OR branches false)
            if not _satisfies_conditions(s_stored, ordered_roles, role_map,
                                         conditions, param_map, eq_fv):
                rej.append(_tc(s_stored, "REJECT"))

    # Final trim to exact counts
    rej = rej[:nr]
    return acc + rej


def _gen_kth_from_end(sym: str, k: int, alphabet: list[str],
                      max_len: int, na: int, nr: int) -> list[dict]:
    """
    Generate test cases for  kth_from_end(K, A).

    Semantics: the K-th symbol from the end (1-indexed) must equal `sym`.
    Formally:  w[ len(w) - K ] == sym,   with len(w) >= K.

    String structure:
        w = <optional prefix of any symbols>  +  sym  +  <suffix of K-1 any symbols>
        length of w  =  p + 1 + (K-1)  =  p + K,   where p >= 0

    ACCEPT strategy
    ---------------
    Build strings of the form:
        random_prefix  +  sym  +  random_suffix_of_length_(K-1)
    where prefix length varies from 0 upward.
    This places sym exactly at position len(w)-K.

    REJECT strategy — two types
    ---------------------------
    Type 1 — Too short (length < K):
        Generate strings of length 0, 1, …, K-1.
        These are rejected because the K-th-from-end position does not exist.
    Type 2 — Long enough but wrong symbol at position len(w)-K:
        Build:  random_prefix  +  non_sym  +  random_suffix_of_length_(K-1)
        where non_sym is any alphabet symbol other than sym.
    """
    others = [s for s in alphabet if s != sym] or alphabet

    acc, rej = [], []

    # ── ACCEPT ───────────────────────────────────────────────────────────────
    for i in range(na):
        prefix_len = i                   # vary prefix length: 0, 1, 2, …
        total      = prefix_len + k      # total length = prefix + 1 + (K-1)
        if total > max_len:
            prefix_len = 0
            total      = k
        prefix = _make(alphabet, prefix_len)
        suffix = _make(alphabet, k - 1)  # K-1 arbitrary symbols after the target
        s      = prefix + sym + suffix
        acc.append(_tc(_cap(s, max_len), "ACCEPT"))

    # ── REJECT type 1: string too short ──────────────────────────────────────
    n_short  = nr // 2 + nr % 2
    n_wrong  = nr // 2
    for i in range(n_short):
        ln = i % k          # lengths 0, 1, …, K-1 cycling
        rej.append(_tc(_make(alphabet, ln), "REJECT"))

    # ── REJECT type 2: correct length but wrong symbol at position -K ────────
    for i in range(n_wrong):
        prefix_len = i
        total      = prefix_len + k
        if total > max_len:
            prefix_len = 0
            total      = k
        wrong_sym  = others[i % len(others)]   # cycle through non-sym symbols
        prefix     = _make(alphabet, prefix_len)
        suffix     = _make(alphabet, k - 1)
        s          = prefix + wrong_sym + suffix
        rej.append(_tc(_cap(s, max_len), "REJECT"))

    return acc + rej



def _in_language(s: str, q: dict) -> bool:
    """
    Check whether string s is accepted by the language described in
    question dict q.  Uses _satisfies_conditions with the inferred
    free-variable values derived from s itself.
    """
    return _satisfies_conditions(
        s,
        list(q.get("role_map", {}).keys()),
        q.get("role_map",   {}),
        q.get("conditions", []),
        q.get("param_map",  {}),
        string_map = q.get("string_map", {}),
    )


def _boundary_seeds(alphabet: list[str], max_len: int) -> list[str]:
    """
    Exhaustively enumerate all strings of length 0 to min(3, max_len).

    These cover the boundary cases that sub-question generators routinely
    miss because free-variable solvers avoid minimum values (e.g. N=0 in
    "M > N" always starts N at 1, so "a" — which satisfies M>N with M=1,
    N=0 — never appears in L2's accept pool).
    """
    seeds: list[str] = []
    for length in range(0, min(4, max_len + 1)):
        for combo in itertools.product(alphabet, repeat=length):
            seeds.append("".join(combo))
    return seeds


def _seed_eq_classes(op: str,
                     sub_qs: list[dict],
                     alphabet: list[str],
                     max_len: int) -> list[str]:
    """
    Constraint-driven equivalence-class seeding for closure operations.

    For binary operations (INTERSECTION, UNION, DIFFERENCE) the reject
    region has multiple independent failure modes.  Relying solely on
    sub-question generators produces a biased pool: each sub-question's
    generator is tuned to its own language and never produces strings
    that satisfy one sub-language while violating the other.

    Strategy — for each sub-question independently collect:
      • known accepts  (strings we know are IN that sub-language)
      • known rejects  (strings we know are NOT IN that sub-language)

    Adding all four pools to the candidate set guarantees that every
    membership-cell combination is seeded:

      op = INTERSECTION / DFA_PDA_INTERSECTION
        (L1∈, L2∈) → ACCEPT   seeded by q1_acc ∩ q2_acc overlap
        (L1∈, L2∉) → REJECT   seeded by q1_acc + q2_rej
        (L1∉, L2∈) → REJECT   seeded by q1_rej + q2_acc  ← previously missing
        (L1∉, L2∉) → REJECT   seeded by q1_rej + q2_rej

      op = UNION
        (L1∈, L2∈) → ACCEPT   seeded by q1_acc + q2_acc
        (L1∈, L2∉) → ACCEPT   seeded by q1_acc + q2_rej
        (L1∉, L2∈) → ACCEPT   seeded by q1_rej + q2_acc
        (L1∉, L2∉) → REJECT   seeded by q1_rej + q2_rej  ← previously thin

      op = DIFFERENCE  (L1 − L2)
        (L1∈, L2∉) → ACCEPT   seeded by q1_acc + q2_rej
        others      → REJECT   seeded by remaining combinations

    The `accepts()` oracle in the caller then correctly classifies every
    candidate — this function only ensures diverse coverage before oracle
    filtering.

    Short boundary strings (length 0-3) are always added first because
    they represent the edge cases most likely to live in unexpected cells.
    """
    seeds: list[str] = _boundary_seeds(alphabet, max_len)

    if len(sub_qs) < 2:
        return seeds

    q1, q2 = sub_qs[0], sub_qs[1]

    # Independent samples from each sub-language (no shared generator call)
    tcs1 = generate_test_cases(q1, n_accept=20, n_reject=10)
    tcs2 = generate_test_cases(q2, n_accept=20, n_reject=10)

    q1_acc = [tc["input"] for tc in tcs1 if tc["label"] == "ACCEPT"]
    q1_rej = [tc["input"] for tc in tcs1 if tc["label"] == "REJECT"]
    q2_acc = [tc["input"] for tc in tcs2 if tc["label"] == "ACCEPT"]
    q2_rej = [tc["input"] for tc in tcs2 if tc["label"] == "REJECT"]

    # Strategy 2: cross-filter to explicitly identify sparse cross-cell strings.
    #
    # Each sub-question generator is biased toward its own language and never
    # intentionally produces strings that satisfy one language while violating
    # the other.  Explicitly check q1_acc against L2 and q2_acc against L1 to
    # surface confirmed cross-boundary strings:
    #
    #   cell_b: (L1✓, L2✗) — q1_acc strings that fail L2 membership
    #   cell_c: (L1✗, L2✓) — q2_acc strings that fail L1 membership
    #
    # These are the cells most likely to be thin after naive pool merging.
    cell_b = [s for s in q1_acc if not _in_language(s, q2)]
    cell_c = [s for s in q2_acc if not _in_language(s, q1)]

    # If a cross-cell is still sparse after the initial sample, run the
    # relevant sub-question generator again with a larger accept budget to
    # find more cross-boundary strings.
    _CROSS_CELL_MIN = 3
    if len(cell_b) < _CROSS_CELL_MIN:
        extra = generate_test_cases(q1, n_accept=40, n_reject=0)
        cell_b.extend(
            tc["input"] for tc in extra
            if tc["label"] == "ACCEPT" and not _in_language(tc["input"], q2)
        )

    if len(cell_c) < _CROSS_CELL_MIN:
        extra = generate_test_cases(q2, n_accept=40, n_reject=0)
        cell_c.extend(
            tc["input"] for tc in extra
            if tc["label"] == "ACCEPT" and not _in_language(tc["input"], q1)
        )

    # Prepend confirmed cross-cell strings so they survive deduplication and
    # appear early in the candidate pool regardless of later random padding.
    seeds = cell_b + cell_c + seeds

    # Add all four pools — each seeds a different membership cell
    seeds.extend(q1_acc)
    seeds.extend(q2_acc)
    seeds.extend(q1_rej)
    seeds.extend(q2_rej)

    return seeds


def _gen_closure_test_cases(question: dict,
                             n_accept: int = 10,
                             n_reject: int = 10) -> list[dict]:
    """
    Generate test cases for closure-property (combined) questions.

    Dispatches on closure_info["op"]:

      COMPLEMENT   accepts s  iff  s ∉ L
      REVERSAL     accepts s  iff  reverse(s) ∈ L
      UNION        accepts s  iff  s ∈ L1  OR   s ∈ L2
      INTERSECTION accepts s  iff  s ∈ L1  AND  s ∈ L2
      DIFFERENCE   accepts s  iff  s ∈ L1  AND  s ∉ L2

    Strategy
    --------
    For each operation, generate candidate strings and check the
    correct membership predicate.  Candidate strings are built by:
      - Sampling ACCEPT strings from the sub-questions (via their own
        test-case generators) — these are known members of L1/L2.
      - Sampling REJECT strings from the sub-questions — known non-members.
      - Generating random strings from the shared alphabet.
    This gives us a diverse set of candidates that exercise all cases.
    """
    info        = question.get("closure_info", {})
    op          = info.get("op", "")
    sub_qs      = info.get("sub_questions", [])
    alphabet    = question.get("alphabet", ["a", "b"])
    max_len     = question.get("max_length", 16)

    if not op or not sub_qs:
        # No closure_info — fall back to random
        return _shuffle(
            [_tc(_make(alphabet, random.randint(0, max_len)), "ACCEPT")
             for _ in range(n_accept)] +
            [_tc(_make(alphabet, random.randint(0, max_len)), "REJECT")
             for _ in range(n_reject)]
        )

    # ── Membership predicate for this operation ───────────────────────────────
    if op == "COMPLEMENT":
        q_sub = sub_qs[0]
        def accepts(s: str) -> bool:
            return not _in_language(s, q_sub)

    elif op == "REVERSAL":
        q_sub = sub_qs[0]
        def accepts(s: str) -> bool:
            return _in_language(s[::-1], q_sub)

    elif op == "UNION":
        q1, q2 = sub_qs[0], sub_qs[1]
        def accepts(s: str) -> bool:
            return _in_language(s, q1) or _in_language(s, q2)

    elif op == "INTERSECTION":
        q1, q2 = sub_qs[0], sub_qs[1]
        def accepts(s: str) -> bool:
            return _in_language(s, q1) and _in_language(s, q2)

    elif op == "DIFFERENCE":
        q1, q2 = sub_qs[0], sub_qs[1]
        def accepts(s: str) -> bool:
            return _in_language(s, q1) and not _in_language(s, q2)

    elif op == "DFA_PDA_INTERSECTION":
        # sub_qs[0] is the DFA question, sub_qs[1] is the PDA question.
        # A string is accepted iff it satisfies BOTH languages.
        q_dfa, q_pda = sub_qs[0], sub_qs[1]
        def accepts(s: str) -> bool:
            return _in_language(s, q_dfa) and _in_language(s, q_pda)

    else:
        def accepts(s: str) -> bool:
            return True

    # ── Build a diverse candidate pool ───────────────────────────────────────
    # Phase 1 — Equivalence-class seeding (constraint-driven).
    #
    # For binary operations each reject region has multiple independent
    # failure modes (e.g. INTERSECTION has three distinct reject cells).
    # _seed_eq_classes guarantees at least one string per cell by:
    #   a) exhaustively enumerating all strings of length 0-3 (boundary seeds)
    #   b) independently sampling accepts + rejects from each sub-language
    #      so that cross-membership strings (e.g. L2✓ but L1✗) are present.
    #
    # For unary operations (COMPLEMENT, REVERSAL) only boundary seeds are
    # added here; the single sub-question generator call below handles the rest.
    if op in ("INTERSECTION", "DFA_PDA_INTERSECTION", "UNION", "DIFFERENCE"):
        candidates: list[str] = _seed_eq_classes(op, sub_qs, alphabet, max_len)
    else:
        candidates: list[str] = _boundary_seeds(alphabet, max_len)

    # Phase 2 — Sub-question generator samples (existing approach retained
    # as a supplement; provides longer / more structured strings).
    for q_src in sub_qs:
        sub_tcs = generate_test_cases(q_src, n_accept=8, n_reject=8)
        candidates.extend(tc["input"] for tc in sub_tcs)

    # Phase 3 — Random strings for additional coverage
    for _ in range(30):
        candidates.append(_make(alphabet, random.randint(0, max_len)))

    # For REVERSAL: also add reverses of sub-question accepts
    if op == "REVERSAL":
        q_sub = sub_qs[0]
        sub_acc = generate_test_cases(q_sub, n_accept=10, n_reject=0)
        candidates.extend(tc["input"][::-1] for tc in sub_acc)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in candidates:
        if s not in seen:
            seen.add(s)
            unique.append(s)

    # ── Partition candidates into ACCEPT / REJECT ─────────────────────────────
    acc_pool = [s for s in unique if     accepts(s)]
    rej_pool = [s for s in unique if not accepts(s)]

    # seen already contains all strings in unique; extend it with pools so the
    # padding loops below never introduce a duplicate.
    acc_seen: set[str] = set(acc_pool)
    rej_seen: set[str] = set(rej_pool)

    # Pad with generated strings if pools are too small
    for _ in range(500):
        if len(acc_pool) >= n_accept and len(rej_pool) >= n_reject:
            break
        s = _make(alphabet, random.randint(0, max_len))
        if s in seen:
            continue
        seen.add(s)
        if accepts(s):
            if len(acc_pool) < n_accept and s not in acc_seen:
                acc_seen.add(s)
                acc_pool.append(s)
        else:
            if len(rej_pool) < n_reject and s not in rej_seen:
                rej_seen.add(s)
                rej_pool.append(s)

    random.shuffle(acc_pool)
    random.shuffle(rej_pool)
    acc = [_tc(s, "ACCEPT") for s in acc_pool[:n_accept]]
    rej = [_tc(s, "REJECT") for s in rej_pool[:n_reject]]

    # Final top-up: if either list is still short, keep searching
    acc_out_seen: set[str] = {tc["input"] for tc in acc}
    rej_out_seen: set[str] = {tc["input"] for tc in rej}
    for _ in range(1000):
        if len(acc) >= n_accept and len(rej) >= n_reject:
            break
        s = _make(alphabet, random.randint(0, max_len))
        if accepts(s):
            if len(acc) < n_accept and s not in acc_out_seen:
                acc_out_seen.add(s)
                acc.append(_tc(s, "ACCEPT"))
        else:
            if len(rej) < n_reject and s not in rej_out_seen:
                rej_out_seen.add(s)
                rej.append(_tc(s, "REJECT"))

    return _shuffle(acc + rej)

# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def _run_primary_generator(primary, alphabet: list[str], role_map: dict,
                            param_map: dict, string_map: dict,
                            free_vars: set, conditions: list,
                            max_len: int, na: int, nr: int) -> list[dict]:
    """
    Run the primary-condition dispatcher to generate na ACCEPT + nr REJECT
    candidates without the full-condition validation wrapper.

    Used by the validation pad to get structured candidates for narrow
    languages where random sampling has a very low hit rate.
    """
    others = [s for s in alphabet if s not in role_map.values()] or alphabet
    cases: list[dict] = []

    # Re-check for special node types first
    prefix_node      = next((c for c in conditions if isinstance(c, PrefixOrderNode)), None)
    kth_node        = next((c for c in conditions if isinstance(c, KthFromEndNode)), None)
    prefix_count_node = next((c for c in conditions if isinstance(c, PrefixCountConstraintNode)), None)

    if prefix_node is not None:
        cases = _gen_prefix_order(
            ordered_roles = prefix_node.roles,
            role_map      = role_map,
            conditions    = conditions,
            param_map     = param_map,
            free_vars     = free_vars,
            max_len       = max_len,
            na            = na,
            nr            = nr,
        )
    elif kth_node is not None:
        sym = role_map.get(kth_node.role, kth_node.role)
        k   = param_map.get(kth_node.position_param,
                            int(kth_node.position_param)
                            if str(kth_node.position_param).isdigit() else 2)
        cases = _gen_kth_from_end(sym, k, alphabet, max_len, na, nr)
    elif prefix_count_node is not None:
        sym1 = role_map.get(prefix_count_node.role1, prefix_count_node.role1)
        sym2 = role_map.get(prefix_count_node.role2, prefix_count_node.role2)
        cases = _gen_prefix_count(sym1, sym2, prefix_count_node.rel, alphabet, max_len, na, nr)
    elif isinstance(primary, CountModConstraintNode):
        sym = role_map.get(primary.role, primary.role)
        k   = _resolve(primary.modulus, param_map, 2)
        v   = _resolve(primary.value,   param_map, 0)
        cases = _gen_count_mod(sym, others, k, v, max_len, na, nr)
    elif isinstance(primary, CountConstraintNode):
        sym     = role_map.get(primary.role, primary.role)
        is_free = isinstance(primary.rhs, IdentNode) and primary.rhs.name in free_vars
        target  = _resolve(primary.rhs, param_map, 2) if not is_free else None
        cases   = _gen_count_exact(sym, others, target, is_free, max_len, na, nr)
    elif isinstance(primary, LengthConstraintNode):
        k     = _resolve(primary.rhs, param_map, 3)
        cases = _gen_length(primary.rel, k, alphabet, max_len, na, nr)
    elif isinstance(primary, LengthModConstraintNode):
        k     = _resolve(primary.modulus, param_map, 2)
        v     = _resolve(primary.value,   param_map, 0)
        cases = _gen_length_mod(k, v, alphabet, max_len, na, nr)
    elif isinstance(primary, PalindromeNode):
        cases = _gen_palindrome(alphabet, max_len, na, nr)
    elif isinstance(primary, StringPredicateNode):
        pattern = string_map.get(primary.param, "ab")
        cases   = _gen_string_pred(primary.kind, pattern, alphabet, max_len, na, nr)
    elif isinstance(primary, FollowPredicateNode):
        t = role_map.get(primary.trigger,  primary.trigger)
        f = role_map.get(primary.follower, primary.follower)
        cases = _gen_follow(t, f, alphabet, max_len, na, nr)
    elif isinstance(primary, PrefixCountConstraintNode):
        sym1 = role_map.get(primary.role1, primary.role1)
        sym2 = role_map.get(primary.role2, primary.role2)
        cases = _gen_prefix_count(sym1, sym2, primary.rel, alphabet, max_len, na, nr)
    elif isinstance(primary, NoAdjacentSameNode):
        cases = _gen_no_adjacent_same(alphabet, max_len, na, nr)
    else:
        cases = ([_tc(_make(alphabet, random.randint(0, max_len)), "ACCEPT") for _ in range(na)] +
                 [_tc(_make(alphabet, random.randint(0, max_len)), "REJECT") for _ in range(nr)])

    return cases


def generate_test_cases(question: dict,
                        n_accept: int = 10,
                        n_reject: int = 10) -> list[dict]:
    """
    Generate n_accept ACCEPT + n_reject REJECT test cases.

    Returns a shuffled list of {'input': str, 'label': 'ACCEPT'|'REJECT'}.
    """
    alphabet   = question.get("alphabet",   ["a", "b"])
    conditions = question.get("conditions", [])
    role_map   = question.get("role_map",   {})
    param_map  = question.get("param_map",  {})
    string_map = question.get("string_map", {})
    free_vars  = question.get("free_vars",  set())
    max_len    = question.get("max_length",30)

    # ── If this is a closure-property question, dispatch to dedicated handler ─
    if question.get("closure_info"):
        return _gen_closure_test_cases(question, n_accept, n_reject)

    if not conditions:
        cases = ([_tc(_make(alphabet, random.randint(0, max_len)), "ACCEPT")
                  for _ in range(n_accept)] +
                 [_tc(_make(alphabet, random.randint(0, max_len)), "REJECT")
                  for _ in range(n_reject)])
        return _shuffle(cases)

    # ── If ANY condition is a PrefixOrderNode, it governs test generation ─────
    # (prefix_order may appear first or after count constraints)
    prefix_node = next(
        (c for c in conditions if isinstance(c, PrefixOrderNode)), None
    )
    cases: list[dict] = []
    if prefix_node is not None:
        cases = _gen_prefix_order(
            ordered_roles = prefix_node.roles,
            role_map      = role_map,
            conditions    = conditions,
            param_map     = param_map,
            free_vars     = free_vars,
            max_len       = max_len,
            na            = n_accept * 2,
            nr            = n_reject * 2,
        )
        # Fall through to the unified validation pass below

    # ── If ANY condition is a KthFromEndNode, it governs test generation ──────
    kth_node = next(
        (c for c in conditions if isinstance(c, KthFromEndNode)), None
    )
    if kth_node is not None and not cases:
        sym = role_map.get(kth_node.role, kth_node.role)
        k   = param_map.get(kth_node.position_param,
                            int(kth_node.position_param)
                            if kth_node.position_param.isdigit() else 2)
        cases = _gen_kth_from_end(sym, k, alphabet, max_len,
                                   n_accept * 2, n_reject * 2)
        # Fall through to the unified validation pass below

    prefix_count_node = next(
        (c for c in conditions if isinstance(c, PrefixCountConstraintNode)), None
    )
    if prefix_count_node is not None and not cases:
        sym1 = role_map.get(prefix_count_node.role1, prefix_count_node.role1)
        sym2 = role_map.get(prefix_count_node.role2, prefix_count_node.role2)
        cases = _gen_prefix_count(sym1, sym2, prefix_count_node.rel, alphabet,
                                   max_len, n_accept * 2, n_reject * 2)
        # Fall through to the unified validation pass below

    primary = conditions[0]
    others  = [s for s in alphabet if s not in role_map.values()] or alphabet
    if not cases:
        cases = []

    if isinstance(primary, CountModConstraintNode):
        sym = role_map.get(primary.role, primary.role)
        k   = _resolve(primary.modulus, param_map, 2)
        v   = _resolve(primary.value,   param_map, 0)
        cases = _gen_count_mod(sym, others, k, v, max_len, n_accept, n_reject)

    elif isinstance(primary, CountConstraintNode):
        sym     = role_map.get(primary.role, primary.role)
        is_free = isinstance(primary.rhs, IdentNode) and primary.rhs.name in free_vars
        target  = _resolve(primary.rhs, param_map, 2) if not is_free else None
        cases   = _gen_count_exact(sym, others, target, is_free,
                                    max_len, n_accept, n_reject)

    elif isinstance(primary, LengthConstraintNode):
        k     = _resolve(primary.rhs, param_map, 3)
        cases = _gen_length(primary.rel, k, alphabet,
                             max_len, n_accept, n_reject)
    elif isinstance(primary, DecimalEquivalentConstraintNode):
        k      = _resolve(primary.modulus, param_map, 2)
        v      = _resolve(primary.value, param_map, 0)
        cases  = _gen_decimal_equivalent(k,v, alphabet, max_len, n_accept, n_reject)

    elif isinstance(primary, LengthModConstraintNode):
        k     = _resolve(primary.modulus, param_map, 2)
        v     = _resolve(primary.value,   param_map, 0)
        cases = _gen_length_mod(k, v, alphabet, max_len, n_accept, n_reject)

    elif isinstance(primary, PalindromeNode):
        cases = _gen_palindrome(alphabet, max_len, n_accept, n_reject)

    elif isinstance(primary, StringPredicateNode):
        pattern = string_map.get(primary.param, "ab")
        cases   = _gen_string_pred(primary.kind, pattern, alphabet,
                                    max_len, n_accept, n_reject)

    elif isinstance(primary, FollowPredicateNode):
        t = role_map.get(primary.trigger,  primary.trigger)
        f = role_map.get(primary.follower, primary.follower)
        cases = _gen_follow(t, f, alphabet, max_len, n_accept, n_reject)

    elif isinstance(primary, PrefixCountConstraintNode):
        sym1 = role_map.get(primary.role1, primary.role1)
        sym2 = role_map.get(primary.role2, primary.role2)
        cases = _gen_prefix_count(sym1, sym2, primary.rel, alphabet,
                                   max_len, n_accept, n_reject)

    elif isinstance(primary, NoAdjacentSameNode):
        cases = _gen_no_adjacent_same(alphabet, max_len, n_accept, n_reject)

    else:
        cases = ([_tc(_make(alphabet, random.randint(0, max_len)), "ACCEPT")
                  for _ in range(n_accept)] +
                 [_tc(_make(alphabet, random.randint(0, max_len)), "REJECT")
                  for _ in range(n_reject)])

    # ── Validate every candidate against ALL conditions ───────────────────────
    # The primary-condition dispatcher above only considers one condition.
    # Re-check every generated string against the full condition list and
    # discard any that are mislabelled (e.g. a string generated as ACCEPT
    # that fails a secondary condition like count(B)%K2==0).
    ordered_roles = list(role_map.keys())

    def _sat_all(s: str) -> bool:
        return _satisfies_conditions(s, ordered_roles, role_map, conditions,
                                     param_map, string_map=string_map)

    validated = [t for t in cases if (_sat_all(t["input"]) == (t["label"] == "ACCEPT"))]

    # Separate into correct ACCEPT and REJECT pools
    acc = [t for t in validated if t["label"] == "ACCEPT"][:n_accept]
    rej = [t for t in validated if t["label"] == "REJECT"][:n_reject]

    # ── Pad with validated strings ────────────────────────────────────────────
    # Strategy: generate structured candidates from the primary-condition
    # generator (same logic used above), then verify ALL conditions.
    # This is far more effective than pure random sampling for narrow languages
    # like "begins_with(S1) AND ends_with(S2)" where random hit rate is <1%.
    need_acc = n_accept - len(acc)
    need_rej = n_reject - len(rej)
    if need_acc > 0 or need_rej > 0:
        # Generate a fresh batch from the primary-condition generator and
        # filter with _sat_all
        extra_cases = _run_primary_generator(
            primary, alphabet, role_map, param_map, string_map,
            free_vars, conditions, max_len,
            na=max(need_acc * 4, 20), nr=max(need_rej * 4, 20)
        )
        for tc in extra_cases:
            sat = _sat_all(tc["input"])
            if sat and len(acc) < n_accept:
                acc.append(_tc(tc["input"], "ACCEPT"))
            elif not sat and len(rej) < n_reject:
                rej.append(_tc(tc["input"], "REJECT"))
            if len(acc) >= n_accept and len(rej) >= n_reject:
                break

    # Final safety pad with random validated strings
    for _ in range(500):
        if len(acc) >= n_accept and len(rej) >= n_reject:
            break
        s   = _make(alphabet, random.randint(0, max_len))
        sat = _sat_all(s)
        if sat and len(acc) < n_accept:
            acc.append(_tc(s, "ACCEPT"))
        elif not sat and len(rej) < n_reject:
            rej.append(_tc(s, "REJECT"))

    # Absolute fallback — for very narrow languages where even 500 random
    # samples don't find enough accepts/rejects.  Use larger batches from
    # the primary generator and filter, increasing batch size each attempt.
    batch_mult = 1
    while len(acc) < n_accept or len(rej) < n_reject:
        need = max(n_accept - len(acc), n_reject - len(rej)) * batch_mult * 4
        batch_mult = min(batch_mult * 2, 32)   # grow batch, cap at 32×
        extra = _run_primary_generator(
            primary, alphabet, role_map, param_map, string_map,
            free_vars, conditions, max_len,
            na=need, nr=need
        )
        for tc in extra:
            sat = _sat_all(tc["input"])
            if sat and len(acc) < n_accept:
                acc.append(_tc(tc["input"], "ACCEPT"))
            elif not sat and len(rej) < n_reject:
                rej.append(_tc(tc["input"], "REJECT"))
            if len(acc) >= n_accept and len(rej) >= n_reject:
                break
        # Hard stop after 10 iterations to prevent infinite loops
        if batch_mult >= 32:
            break  # accept whatever we have — validation already discarded invalids

    return _shuffle(acc + rej)
