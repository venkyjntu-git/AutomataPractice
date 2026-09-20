"""
ast_nodes.py
============
All AST node types for the AutomataGen DSL.

Every parser production maps to exactly one node class here.
No logic lives in this file — only data definitions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# ── Alphabet & roles ──────────────────────────────────────────────────────────

@dataclass
class AlphabetNode:
    """
    Represents the alphabet section.

    size  : number of symbols to select from one pool.
    pools : list of candidate symbol lists.  Each pool is a homogeneous
            group (e.g. all lowercase letters, or all digits).

    Selection rule:
        Only pools whose length >= size are eligible.
        One eligible pool is chosen at random; `size` symbols are drawn
        from it as a contiguous window, giving a consistent symbol family.
    """
    size:  int
    pools: list[list[str]]


@dataclass
class RoleBindingNode:
    """
    A single role binding:   A <- alpha[0]

    name        : role name  (e.g. 'A', 'symbol1')
    alpha_index : position in the selected alphabet  (0 → alpha[0], 1 → alpha[1], …)

    After alphabet selection (one pool of `size` symbols), alpha[0] is the
    first symbol, alpha[1] the second, etc.  alpha_index must be < size.
    """
    name:        str
    alpha_index: int


# ── Parameter nodes ───────────────────────────────────────────────────────────

@dataclass
class ScalarParamNode:
    """  k in [2, 6]   or   k in {2, 3, 5}  """
    name:   str
    values: list[int]


@dataclass
class StringParamNode:
    """  S in strings({A, B}, K)  — generates a random string of length K """
    name:       str
    role_names: list[str]   # role names whose symbols form the sampling alphabet
    length_ref: str         # name of the scalar param giving the length


# ── Constraint nodes (one per condition line) ─────────────────────────────────

@dataclass
class CountConstraintNode:
    """  count(R) <rel> <rhs>   or   count(R) <rel> count(R2)  """
    role: str
    rel:  str          # '==' | '!=' | '<' | '>' | '<=' | '>='
    rhs:  Any          # IntLitNode | IdentNode | MulExprNode | AddExprNode | CountExprNode


@dataclass
class CountModConstraintNode:
    """  count(R) % <mod> == <val>  """
    role:    str
    modulus: Any
    value:   Any

@dataclass
class DecimalEquivalentConstraintNode:
    """  decimal_equivalent % <mod> == <val>  """
    modulus: Any
    value:   Any
    
@dataclass
class LengthConstraintNode:
    """  length(string) <rel> <rhs>  """
    rel: str
    rhs: Any


@dataclass
class LengthModConstraintNode:
    """  length(string) % <mod> == <val>  """
    modulus: Any
    value:   Any


@dataclass
class PrefixCountConstraintNode:
    """  prefix_count(R1) <rel> prefix_count(R2)  — at every prefix, count(R1) <rel> count(R2).  """
    role1: str
    rel:   str   # '==' | '!=' | '<' | '>' | '<=' | '>='
    role2: str


@dataclass
class VarConstraintNode:
    """  M > N   or   N > 0   (between free / existential variables)  """
    lhs: str
    rel: str
    rhs: Any           # IntLitNode | IdentNode


@dataclass
class PalindromeNode:
    """  palindrome  """
    pass


@dataclass
class NoAdjacentSameNode:
    """  no_adjacent_same  — no two adjacent symbols are the same  """
    pass


@dataclass
class PrefixOrderNode:
    """
    prefix_order(A, B)         — all A symbols precede all B symbols
    prefix_order(A, B, C)      — A block, then B block, then C block
    prefix_order(A, B, C, D)   — four consecutive blocks, etc.

    Semantics: the input string consists of zero or more of role[0],
    followed by zero or more of role[1], …  in the given order.
    Symbols from each role appear ONLY in their block — no interleaving.

    This is a purely structural (ordering) constraint.  Count constraints
    (how many of each) are expressed separately with count(R) == …
    and combined with this node in the same condition list.

    Examples:
        # A^N B^(K*N) — block order + counts
        prefix_order(A, B)
        count(A) == N
        count(B) == K*N
        N > 0

        # A^M B^N C^(M+N) — three-block order + sum constraint
        prefix_order(A, B, C)
        count(A) == M
        count(B) == N
        count(C) == (M+N)
        M > 0
        N > 0
    """
    roles: list[str]   # role names in the required left-to-right order


@dataclass
class StringPredicateNode:
    """  begins_with(S) | ends_with(S) | contains(S)  """
    kind:  str    # 'begins_with' | 'ends_with' | 'contains'
    param: str    # name of the StringParamNode (e.g. 'S')


@dataclass
class FollowPredicateNode:
    """  every(A) followed_by(B)  """
    trigger:  str    # role that must be immediately followed
    follower: str    # role that must immediately follow


@dataclass
class KthFromEndNode:
    """
    kth_from_end(K, A)

    The K-th symbol from the end of the string equals the symbol bound
    to role A.  K is a scalar parameter name (e.g. 'K'), not a literal.
    The string must have length >= K for any string to be accepted.

    Semantics:  w[len(w) - K]  ==  role_map[A]

    K is 1-indexed:  K=1 means the very last symbol,
                     K=2 means second-to-last, etc.

    Template example:
        parameters:
            K in [2, 5]
        condition:
            length >= K
            kth_from_end(K, A)
    """
    position_param: str   # name of the scalar parameter giving K
    role:           str   # role name whose concrete symbol must appear there


@dataclass
class OrConstraintNode:
    """
    <lhs_constraint> or <rhs_constraint> [or ...]

    Semantics: the string satisfies this node iff it satisfies AT LEAST ONE
    of the operands.  At the top level, all items in the condition list are
    still AND-ed together — only the operands within one OrConstraintNode
    are OR-ed.

    Example:  M != N or N != P
      operands = [VarConstraintNode('M', '!=', IdentNode('N')),
                  VarConstraintNode('N', '!=', IdentNode('P'))]
    """
    operands: list[Any]   # at least 2 constraint nodes


# ── Expression nodes ──────────────────────────────────────────────────────────

@dataclass
class IntLitNode:
    value: int


@dataclass
class IdentNode:
    name: str      # scalar param name  or  free variable (N, M, P, …)


@dataclass
class MulExprNode:
    left:  Any
    right: Any


@dataclass
class AddExprNode:
    left:  Any
    right: Any


@dataclass
class SubExprNode:
    left:  Any
    right: Any


@dataclass
class CountExprNode:
    """  count(R)  appearing on the right-hand side of a constraint  """
    role: str


# ── Top-level template node ────────────────────────────────────────────────────

@dataclass
class TemplateNode:
    source_file:    str
    machine:        str              # 'DFA' | 'NFA' | 'PDA' | 'TM'
    template_id:    str
    pattern_family: list[str]
    difficulty:     int
    description:    str
    alphabet:       AlphabetNode
    roles:          list[RoleBindingNode]
    parameters:     list[Any]        # ScalarParamNode | StringParamNode
    conditions:     list[Any]        # constraint nodes, implicitly AND-ed
    testing:        dict             # {'cases': int, 'max_length': int}
    tags:           list[str]
    closure_allowed: bool = True
