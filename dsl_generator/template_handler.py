"""
template_handler.py
===================
Loads .dsl template files, validates them, and instantiates them into
concrete question dicts.

Public API
----------
  load_template(filepath)  → TemplateNode | None
  load_templates(dir)      → list[TemplateNode]
  build_question(node)     → dict
"""

from __future__ import annotations

import glob
import os
import random
import re
from typing import Any

from lexer import Lexer
from parser import Parser, ParseError
from ast_nodes import (
    AlphabetNode, RoleBindingNode,
    ScalarParamNode, StringParamNode,
    CountConstraintNode, CountModConstraintNode,
    LengthConstraintNode, LengthModConstraintNode,
    PrefixCountConstraintNode,
    VarConstraintNode, PalindromeNode, NoAdjacentSameNode, PrefixOrderNode,
    StringPredicateNode, FollowPredicateNode, KthFromEndNode,
    IntLitNode, IdentNode, MulExprNode, AddExprNode, SubExprNode,
    CountExprNode, TemplateNode, DecimalEquivalentConstraintNode,
    OrConstraintNode,
)


# ══════════════════════════════════════════════════════════════════════════════
#  VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def validate_template(node: TemplateNode) -> list[str]:
    """
    Return a list of warning strings for structural problems.
    Does not reject the template; warnings are printed at load time.

    Checks:
    1. Every role's alpha_index must be < alphabet size.
    2. No two roles may share the same alpha_index (they would get the
       same symbol, making the condition ambiguous).
    3. If no pool has >= size elements, a note is printed at instantiation
       time (not here, because the actual pool is chosen randomly).
    """
    warnings: list[str] = []
    size = node.alphabet.size

    for rb in node.roles:
        if rb.alpha_index == -1:
            continue  # RANDOM_INDEX: resolved at instantiation
        if rb.alpha_index >= size:
            warnings.append(
                f"role '{rb.name}' uses alpha[{rb.alpha_index}] "
                f"but alphabet size is {size} — "
                f"alpha[{rb.alpha_index}] is out of range"
            )

    # Duplicate alpha_index check (skip -1: each RANDOM_INDEX gets independent random)
    idx_map: dict[int, list[str]] = {}
    for rb in node.roles:
        if rb.alpha_index == -1:
            continue
        idx_map.setdefault(rb.alpha_index, []).append(rb.name)
    for idx, names in idx_map.items():
        if len(names) > 1:
            warnings.append(
                f"roles {names} all use alpha[{idx}] — "
                f"each role must have a distinct alpha index"
            )

    return warnings


# ══════════════════════════════════════════════════════════════════════════════
#  INSTANTIATOR
# ══════════════════════════════════════════════════════════════════════════════

class Instantiator:
    """
    Converts a TemplateNode into a concrete instance dict:
    {
      'alphabet':   list[str],
      'role_map':   dict[str, str],
      'param_map':  dict[str, int],
      'string_map': dict[str, str],
      'free_vars':  set[str],
    }

    Alphabet selection rule
    -----------------------
    Only pools whose length >= size are eligible.
    One eligible pool is chosen at random; `size` symbols are drawn
    from a random contiguous window within it — giving a fully
    homogeneous symbol family (all letters OR all digits, never mixed).

    If no pool has >= size elements the smallest pool with the most
    elements is used and size is capped at its length.
    """

    def __init__(self, node: TemplateNode) -> None:
        self._node = node

    def instantiate(self) -> dict:
        alphabet  = self._sample_alphabet()
        role_map  = self._bind_roles(alphabet)
        param_map = self._sample_params()
        str_map   = self._sample_strings(role_map, param_map)
        free_vars = self._find_free_vars(param_map, str_map)
        return {
            "alphabet":   alphabet,
            "role_map":   role_map,
            "param_map":  param_map,
            "string_map": str_map,
            "free_vars":  free_vars,
        }

    # ── alphabet ──────────────────────────────────────────────────────────────

    def _sample_alphabet(self) -> list[str]:
        """
        Select the concrete alphabet of `size` symbols.

        Algorithm
        ---------
        1. Find all pools whose length >= size  (eligible pools).
        2. Choose one eligible pool at random.
        3. Draw a contiguous window of `size` symbols starting at a
           random offset within that pool.

        Because each pool is a homogeneous family (e.g. all lowercase
        letters, or all digits, or all brackets), the resulting alphabet
        is always internally consistent — never a mix like {a, 0, (}.

        If no pool has >= size elements, emit a [NOTE] and use the
        largest pool available, capping the alphabet at its length.
        """
        alph  = self._node.alphabet
        size  = alph.size
        pools = alph.pools

        eligible = [p for p in pools if len(p) >= size]

        if eligible:
            pool  = random.choice(eligible)
            start = random.randint(0, len(pool) - size)
            return pool[start: start + size]

        # No pool is large enough — warn and use what is available
        best   = max(pools, key=len)
        actual = len(best)
        tid    = self._node.template_id
        print(f"    [NOTE] {tid}: no pool has >= {size} symbols "
              f"(largest has {actual}) — using {actual} symbols")
        return best[:actual]

    # ── role binding ──────────────────────────────────────────────────────────

    def _bind_roles(self, alphabet: list[str]) -> dict[str, str]:
        """
        Map every role to its concrete symbol.

        rule:  role.alpha_index  →  alphabet[alpha_index]

        alpha_index is validated at load time (must be < size).
        At instantiation time, if it is still out of range (e.g. because
        the alphabet was capped by a small pool) we emit a note and
        assign the last available symbol rather than crashing.
        """
        role_map: dict[str, str] = {}
        n = len(alphabet)

        for rb in self._node.roles:
            if rb.alpha_index == -1:
                # RANDOM_INDEX: pick random symbol from alphabet at instantiation
                role_map[rb.name] = alphabet[random.randint(0, n - 1)]
            elif rb.alpha_index < n:
                role_map[rb.name] = alphabet[rb.alpha_index]
            else:
                # alpha_index out of range after pool capping — use last symbol
                print(f"    [NOTE] {self._node.template_id}: role '{rb.name}' "
                      f"alpha[{rb.alpha_index}] out of range for alphabet of "
                      f"size {n} — assigning last symbol '{alphabet[-1]}'")
                role_map[rb.name] = alphabet[-1]

        return role_map

    # ── parameters ────────────────────────────────────────────────────────────

    def _sample_params(self) -> dict[str, int]:
        return {p.name: random.choice(p.values)
                for p in self._node.parameters
                if isinstance(p, ScalarParamNode) and p.values}

    # ── string parameters ─────────────────────────────────────────────────────

    def _sample_strings(self, role_map: dict, param_map: dict) -> dict[str, str]:
        str_map: dict[str, str] = {}
        for p in self._node.parameters:
            if isinstance(p, StringParamNode):
                syms = [role_map[r] for r in p.role_names if r in role_map]
                if not syms:
                    syms = list(role_map.values()) or ["a"]
                length = param_map.get(p.length_ref, 2)
                str_map[p.name] = "".join(random.choices(syms, k=length))
        return str_map

    # ── free-variable detection ───────────────────────────────────────────────

    def _find_free_vars(self, param_map: dict, str_map: dict) -> set[str]:
        bound = set(param_map) | set(str_map) | {rb.name for rb in self._node.roles}
        free:  set[str] = set()
        for c in self._node.conditions:
            self._collect_free(c, bound, free)
        return free

    def _collect_free(self, node: Any, bound: set[str],
                      free: set[str]) -> None:
        if isinstance(node, IdentNode):
            if node.name not in bound:
                free.add(node.name)
        elif hasattr(node, "__dataclass_fields__"):
            for fname in node.__dataclass_fields__:
                self._collect_free(getattr(node, fname), bound, free)

    # ── expression evaluator ──────────────────────────────────────────────────

    @staticmethod
    def eval_expr(node: Any, role_map: dict, param_map: dict) -> str:
        if isinstance(node, IntLitNode):
            return str(node.value)
        if isinstance(node, IdentNode):
            if node.name in param_map:
                return str(param_map[node.name])
            if node.name in role_map:
                return f"'{role_map[node.name]}'"
            return node.name          # free variable
        if isinstance(node, CountExprNode):
            sym = role_map.get(node.role, node.role)
            return f"count({sym})"
        if isinstance(node, MulExprNode):
            l = Instantiator.eval_expr(node.left,  role_map, param_map)
            r = Instantiator.eval_expr(node.right, role_map, param_map)
            if l == "1":
                return r
            if r == "1":
                return l
            try:
                return str(int(l) * int(r))
            except ValueError:
                return f"{l}·{r}"
        if isinstance(node, AddExprNode):
            l = Instantiator.eval_expr(node.left,  role_map, param_map)
            r = Instantiator.eval_expr(node.right, role_map, param_map)
            try:
                return str(int(l) + int(r))
            except ValueError:
                return f"({l}+{r})"
        if isinstance(node, SubExprNode):
            l = Instantiator.eval_expr(node.left,  role_map, param_map)
            r = Instantiator.eval_expr(node.right, role_map, param_map)
            try:
                return str(int(l) - int(r))
            except ValueError:
                return f"({l}-{r})"
        return str(node)


# ══════════════════════════════════════════════════════════════════════════════
#  RENDERER
# ══════════════════════════════════════════════════════════════════════════════

_REL_WORDS = {
    "==": "equals",        "!=": "does not equal",
    "<":  "is less than",  ">":  "is greater than",
    "<=": "is at most",    ">=": "is at least",
}


class Renderer:
    """Converts instantiated constraint nodes → English text + pattern string."""

    def __init__(self, role_map: dict, param_map: dict,
                 string_map: dict, free_vars: set) -> None:
        self._rm  = role_map
        self._pm  = param_map
        self._sm  = string_map
        self._fv  = free_vars

    def english(self, conditions: list) -> str:
        clauses = [self._en(c) for c in conditions
                   if c is not None and not self._is_positivity(c)]
        return ", and ".join(clauses) if clauses else "(no condition)"

    def pattern(self, conditions: list) -> str:
        parts = [self._pat(c) for c in conditions if c is not None]
        return "  &  ".join(p for p in parts if p)

    # ── positivity guards (N > 0) are implicit — don't surface them ───────────

    def _is_positivity(self, node: Any) -> bool:
        return (isinstance(node, VarConstraintNode)
                and isinstance(node.rhs, IntLitNode)
                and node.rhs.value == 0
                and node.rel == ">")

    # ── English renderers ─────────────────────────────────────────────────────

    def _en(self, node: Any) -> str:
        if isinstance(node, CountConstraintNode):
            return self._en_count(node)
        if isinstance(node, DecimalEquivalentConstraintNode):
            mod = Instantiator.eval_expr(node.modulus, self._rm, self._pm)
            val = Instantiator.eval_expr(node.value,   self._rm, self._pm)
            if val == "0":
                return f" The decimal equivalent of binary string is divisible by {mod}"
            return f" The decimal equivalent of binary string mod {mod} equals {val}"
        if isinstance(node, CountModConstraintNode):
            sym = self._rm.get(node.role, node.role)
            mod = Instantiator.eval_expr(node.modulus, self._rm, self._pm)
            val = Instantiator.eval_expr(node.value,   self._rm, self._pm)
            if val == "0":
                return f"the number of '{sym}' symbols is divisible by {mod}"
            return f"the number of '{sym}' symbols mod {mod} equals {val}"
        if isinstance(node, LengthConstraintNode):
            rhs = Instantiator.eval_expr(node.rhs, self._rm, self._pm)
            rel = _REL_WORDS.get(node.rel, node.rel)
            return f"the total length of the string {rel} {rhs}"
        if isinstance(node, LengthModConstraintNode):
            mod = Instantiator.eval_expr(node.modulus, self._rm, self._pm)
            val = Instantiator.eval_expr(node.value,   self._rm, self._pm)
            if val == "0":
                return f"the total length of the string is divisible by {mod}"
            return f"the total length of the string mod {mod} equals {val}"
        if isinstance(node, PrefixCountConstraintNode):
            sym1 = self._rm.get(node.role1, node.role1)
            sym2 = self._rm.get(node.role2, node.role2)
            rel = _REL_WORDS.get(node.rel, node.rel)
            return (f"at every prefix of the string, the number of '{sym1}' symbols "
                    f"{rel} the number of '{sym2}' symbols")
        if isinstance(node, VarConstraintNode):
            rhs = Instantiator.eval_expr(node.rhs, self._rm, self._pm)
            rel = _REL_WORDS.get(node.rel, node.rel)
            return f"{node.lhs} {rel} {rhs}"
        if isinstance(node, PalindromeNode):
            return "the string is a palindrome (reads the same forwards and backwards)"
        if isinstance(node, NoAdjacentSameNode):
            return "no two adjacent symbols are the same"
        if isinstance(node, PrefixOrderNode):
            syms = [f"'{self._rm.get(r, r)}'" for r in node.roles]
            if len(syms) == 2:
                return (f"all {syms[0]} symbols appear before any {syms[1]} symbol "
                        f"(the string has the form {syms[0]}* {syms[1]}*)")
            blocks = " ".join(syms)
            order  = ", then ".join(syms)
            return (f"the symbols appear in consecutive blocks: "
                    f"{order} (form: {blocks})")
        if isinstance(node, StringPredicateNode):
            s = self._sm.get(node.param, node.param)
            verb = {"begins_with": "begins with the sequence",
                    "ends_with":   "ends with the sequence",
                    "contains":    "contains"}[node.kind]
            return f"the string {verb} '{s}'"
        if isinstance(node, FollowPredicateNode):
            t = self._rm.get(node.trigger,  node.trigger)
            f = self._rm.get(node.follower, node.follower)
            return f"every occurrence of '{t}' is immediately followed by '{f}'"
        if isinstance(node, KthFromEndNode):
            sym = self._rm.get(node.role, node.role)
            k   = self._pm.get(node.position_param, node.position_param)
            return (f"the {k}-th symbol from the end of the string "
                    f"is '{sym}'  (i.e. position len(w)-{k} equals '{sym}')")
        if isinstance(node, OrConstraintNode):
            parts = [self._en(op) for op in node.operands]
            return "(" + " or ".join(parts) + ")"
        return str(node)

    def _en_count(self, node: CountConstraintNode) -> str:
        sym = self._rm.get(node.role, node.role)
        rel = _REL_WORDS.get(node.rel, node.rel)
        # count(A) == count(B)
        if isinstance(node.rhs, CountExprNode):
            sym2 = self._rm.get(node.rhs.role, node.rhs.role)
            return (f"the number of '{sym}' symbols {rel} "
                    f"the number of '{sym2}' symbols")
        # count(A) == N  (plain free variable)
        if isinstance(node.rhs, IdentNode) and node.rhs.name in self._fv:
            v = node.rhs.name
            if node.rel == "==":
                return f"{v} number of '{sym}' symbols"
            return f"the number of '{sym}' symbols {rel} {v}"
        # count(A) == K*N  (suppress K=1)
        if isinstance(node.rhs, MulExprNode) and node.rel == "==":
            for side, other in [(node.rhs.left,  node.rhs.right),
                                 (node.rhs.right, node.rhs.left)]:
                if isinstance(other, IdentNode) and other.name in self._fv:
                    k_val = Instantiator.eval_expr(side, self._rm, self._pm)
                    v     = other.name
                    if k_val == "1":
                        return f"{v} number of '{sym}' symbols"
                    return (f"the number of '{sym}' symbols "
                            f"equals {k_val}·{v}")
        rhs = Instantiator.eval_expr(node.rhs, self._rm, self._pm)
        return f"the number of '{sym}' symbols {rel} {rhs}"

    # ── pattern renderers ─────────────────────────────────────────────────────

    def _pat(self, node: Any) -> str:
        if isinstance(node, CountConstraintNode):
            sym = self._rm.get(node.role, node.role)
            if isinstance(node.rhs, CountExprNode):
                sym2 = self._rm.get(node.rhs.role, node.rhs.role)
                return f"count({sym}) {node.rel} count({sym2})"
            rhs = Instantiator.eval_expr(node.rhs, self._rm, self._pm)
            return f"count({sym}) {node.rel} {rhs}"
        if isinstance(node, DecimalEquivalentConstraintNode):
            mod = Instantiator.eval_expr(node.modulus, self._rm, self._pm)
            val = Instantiator.eval_expr(node.value,   self._rm, self._pm)
            return f"decimal_equivalent % {mod} == {val}"
        if isinstance(node, CountModConstraintNode):
            sym = self._rm.get(node.role, node.role)
            mod = Instantiator.eval_expr(node.modulus, self._rm, self._pm)
            val = Instantiator.eval_expr(node.value,   self._rm, self._pm)
            return f"count({sym}) % {mod} == {val}"
        if isinstance(node, LengthConstraintNode):
            rhs = Instantiator.eval_expr(node.rhs, self._rm, self._pm)
            return f"length {node.rel} {rhs}"
        if isinstance(node, LengthModConstraintNode):
            mod = Instantiator.eval_expr(node.modulus, self._rm, self._pm)
            val = Instantiator.eval_expr(node.value,   self._rm, self._pm)
            return f"length % {mod} == {val}"
        if isinstance(node, PrefixCountConstraintNode):
            sym1 = self._rm.get(node.role1, node.role1)
            sym2 = self._rm.get(node.role2, node.role2)
            return f"prefix_count({sym1}) {node.rel} prefix_count({sym2})"
        if isinstance(node, PalindromeNode):
            return "palindrome"
        if isinstance(node, NoAdjacentSameNode):
            return "no_adjacent_same"
        if isinstance(node, PrefixOrderNode):
            syms = [self._rm.get(r, r) for r in node.roles]
            return "prefix_order(" + ", ".join(syms) + ")"
        if isinstance(node, VarConstraintNode):
            rhs = Instantiator.eval_expr(node.rhs, self._rm, self._pm)
            return f"{node.lhs} {node.rel} {rhs}"
        if isinstance(node, StringPredicateNode):
            s = self._sm.get(node.param, node.param)
            return f"{node.kind}({s})"
        if isinstance(node, FollowPredicateNode):
            t = self._rm.get(node.trigger,  node.trigger)
            f = self._rm.get(node.follower, node.follower)
            return f"every({t}) followed_by({f})"
        if isinstance(node, KthFromEndNode):
            sym = self._rm.get(node.role, node.role)
            k   = self._pm.get(node.position_param, node.position_param)
            return f"kth_from_end({k}, {sym})"
        if isinstance(node, OrConstraintNode):
            parts = [self._pat(op) for op in node.operands if self._pat(op)]
            return "(" + " | ".join(parts) + ")"
        return ""


# ══════════════════════════════════════════════════════════════════════════════
#  CONDITION INFERENCE  (fixes tautological / missing conditions)
# ══════════════════════════════════════════════════════════════════════════════

def _infer_string_conditions(node: TemplateNode) -> list | None:
    """
    If the template has StringParamNodes but only tautological
    length(S)==K conditions, replace them with the correct predicate
    inferred from pattern_family.
    """
    str_params = [p for p in node.parameters if isinstance(p, StringParamNode)]
    if not str_params:
        return None

    def is_tautological(conditions: list) -> bool:
        for c in conditions:
            if not isinstance(c, LengthConstraintNode):
                return False
        return True

    if not (not node.conditions or is_tautological(node.conditions)):
        return None

    pf = " ".join(node.pattern_family).lower()
    replacement: list = []
    if "begins with and ends with" in pf and len(str_params) >= 2:
        replacement.append(StringPredicateNode("begins_with", str_params[0].name))
        replacement.append(StringPredicateNode("ends_with",   str_params[1].name))
    elif "begins with" in pf:
        replacement.append(StringPredicateNode("begins_with", str_params[0].name))
    elif "ends with" in pf:
        replacement.append(StringPredicateNode("ends_with",   str_params[0].name))
    elif "contains" in pf:
        replacement.append(StringPredicateNode("contains",    str_params[0].name))
    return replacement or None


def _infer_follow_condition(node: TemplateNode) -> list | None:
    """
    If there are no conditions but pattern_family mentions 'followed',
    synthesise every(roles[0]) followed_by(roles[1]).
    """
    pf = " ".join(node.pattern_family).lower()
    if "followed" not in pf or node.conditions or len(node.roles) < 2:
        return None
    return [FollowPredicateNode(trigger=node.roles[0].name,
                                follower=node.roles[1].name)]


# ══════════════════════════════════════════════════════════════════════════════
#  QUESTION BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_question(node: TemplateNode) -> dict:
    """
    Instantiate a template into a concrete question dict.

    Returns
    -------
    {
      'machine', 'template_id', 'difficulty', 'tags', 'pattern_fam',
      'alphabet', 'role_map', 'param_map', 'string_map', 'free_vars',
      'conditions',   # the (possibly inferred) condition list
      'text',         # full English question string
      'pattern',      # compact grader pattern string
      'combined',     # False for base questions
    }
    """
    inst = Instantiator(node).instantiate()

    # Fix tautological / missing conditions
    conditions = node.conditions
    inferred   = _infer_string_conditions(node)
    if inferred is not None:
        conditions = inferred
    if not conditions:
        follow = _infer_follow_condition(node)
        if follow:
            conditions = follow

    rend = Renderer(
        role_map   = inst["role_map"],
        param_map  = inst["param_map"],
        string_map = inst["string_map"],
        free_vars  = inst["free_vars"],
    )

    alpha_str  = "{" + ", ".join(inst["alphabet"]) + "}"
    cond_en    = rend.english(conditions)
    cond_pat   = rend.pattern(conditions)

    param_note = ""
    if inst["param_map"]:
        param_note = "  (given: " + ", ".join(
            f"{k}={v}" for k, v in inst["param_map"].items()) + ")"

    text    = (f"Construct a {node.machine} over the alphabet {alpha_str}"
               f" that accepts all strings where {cond_en}.{param_note}")
    pattern = (f"{node.machine} | {cond_pat} | {' '.join(inst['alphabet'])}")
    if inst["param_map"]:
        pattern += " | " + ",".join(str(v) for v in inst["param_map"].values())

    return {
        "machine":     node.machine,
        "template_id": node.template_id,
        "difficulty":  node.difficulty,
        "tags":        list(node.tags),
        "pattern_fam": node.pattern_family,
        "alphabet":    inst["alphabet"],
        "role_map":    inst["role_map"],
        "param_map":   inst["param_map"],
        "string_map":  inst["string_map"],
        "free_vars":   inst["free_vars"],
        "conditions":  conditions,
        "text":            text,
        "pattern":         pattern,
        "combined":        False,
        "max_length":      node.testing.get("max_length", 12),
        "closure_allowed": node.closure_allowed,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  LOADER
# ══════════════════════════════════════════════════════════════════════════════

def load_template(filepath: str) -> TemplateNode | None:
    try:
        with open(filepath, encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        print(f"  [WARN] Cannot read {filepath}: {e}")
        return None
    try:
        tokens = Lexer(src, filename=filepath).tokenise()
        node   = Parser(tokens, filename=filepath).parse()
        for w in validate_template(node):
            print(f"    [NOTE] {os.path.basename(filepath)}: {w}")
        return node
    except (ParseError, Exception) as e:
        print(f"  [WARN] Parse error in {filepath}: {e}")
        return None


def load_templates(template_dir: str) -> list[TemplateNode]:
    import sys
    files = sorted(glob.glob(os.path.join(template_dir, "*.dsl")))
    if not files:
        print(f"[ERROR] No .dsl files found in '{template_dir}'")
        sys.exit(1)
    templates: list[TemplateNode] = []
    for fp in files:
        print(f"  Loading : {os.path.basename(fp)}")
        node = load_template(fp)
        if node:
            templates.append(node)
            print(f"  Loaded : {node.template_id:<44} [{node.machine}]"
                  f"  diff={node.difficulty}")
        else:
            print(f"  [SKIP]  {os.path.basename(fp)}")
    print(f"\n  {len(templates)} templates loaded.\n")
    return templates
