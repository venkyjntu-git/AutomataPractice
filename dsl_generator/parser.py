"""
parser.py
=========
Recursive-descent parser for the AutomataGen DSL.

Input  : flat Token list from lexer.Lexer.tokenise()
Output : ast_nodes.TemplateNode  (raises ParseError on failure)

Each parse_* method corresponds to one grammar production.
"""

from __future__ import annotations
from typing import Any

from lexer import TT, Token
from ast_nodes import (
    AlphabetNode, RoleBindingNode, ScalarParamNode, StringParamNode,
    CountConstraintNode, CountModConstraintNode,
    LengthConstraintNode, LengthModConstraintNode,
    PrefixCountConstraintNode,
    VarConstraintNode, PalindromeNode, NoAdjacentSameNode, PrefixOrderNode,
    StringPredicateNode, FollowPredicateNode, KthFromEndNode,
    IntLitNode, IdentNode, MulExprNode, AddExprNode, SubExprNode, CountExprNode,
    TemplateNode, DecimalEquivalentConstraintNode, OrConstraintNode,
)


class ParseError(Exception):
    pass


# Section keywords that terminate a section being parsed
_TOP_LEVEL: set[TT] = {
    TT.TEMPLATE_ID, TT.PATTERN_FAM, TT.DIFFICULTY, TT.DESCRIPTION,
    TT.ALPHABET, TT.ROLES, TT.PARAMETERS, TT.CONDITION,
    TT.TESTING, TT.TAGS, TT.CLOSURE_ALLOWED, TT.END, TT.EOF,
}


class Parser:

    def __init__(self, tokens: list[Token], filename: str = "<?>") -> None:
        self._tok   = tokens
        self._pos   = 0
        self._fname = filename

    # ── token stream helpers ──────────────────────────────────────────────────

    def _cur(self) -> Token:
        return self._tok[self._pos]

    def _advance(self) -> Token:
        t = self._tok[self._pos]
        if self._pos + 1 < len(self._tok):
            self._pos += 1
        return t

    def _expect(self, tt: TT) -> Token:
        t = self._cur()
        if t.type != tt:
            raise ParseError(
                f"{self._fname} L{t.line}: expected {tt.name} "
                f"but got {t.type.name} ({t.value!r})"
            )
        return self._advance()

    def _skip_newlines(self) -> None:
        while self._cur().type == TT.NEWLINE:
            self._advance()

    def _skip_colon(self) -> None:
        if self._cur().type == TT.COLON:
            self._advance()

    # ── top-level entry ───────────────────────────────────────────────────────

    def parse(self) -> TemplateNode:
        self._skip_newlines()
        self._expect(TT.AUTOMATA)
        machine = self._parse_machine_type()

        template_id    = ""
        pattern_family: list[str] = []
        difficulty     = 0
        description    = ""
        alphabet       = None
        roles:      list[RoleBindingNode] = []
        parameters: list[Any]            = []
        conditions: list[Any]            = []
        testing        = {"cases": 200, "max_length": 12}
        tags:       list[str]            = []
        closure_allowed                  = True

        while self._cur().type not in (TT.END, TT.EOF):
            self._skip_newlines()
            tt = self._cur().type

            if tt == TT.TEMPLATE_ID:
                self._advance(); self._skip_colon()
                template_id = self._read_bare_line()

            elif tt == TT.PATTERN_FAM:
                self._advance(); self._skip_colon()
                pattern_family = self._parse_brace_tag_list()

            elif tt == TT.DIFFICULTY:
                self._advance(); self._skip_colon()
                self._skip_newlines()
                difficulty = self._expect(TT.INT).value

            elif tt == TT.DESCRIPTION:
                self._advance(); self._skip_colon()
                description = self._read_free_text()

            elif tt == TT.ALPHABET:
                self._advance(); self._skip_colon()
                alphabet = self._parse_alphabet()

            elif tt == TT.ROLES:
                self._advance(); self._skip_colon()
                roles = self._parse_roles()

            elif tt == TT.PARAMETERS:
                self._advance(); self._skip_colon()
                parameters = self._parse_parameters()

            elif tt == TT.CONDITION:
                self._advance(); self._skip_colon()
                conditions = self._parse_conditions()

            elif tt == TT.TESTING:
                self._advance(); self._skip_colon()
                testing = self._parse_testing()

            elif tt == TT.TAGS:
                self._advance(); self._skip_colon()
                tags = self._parse_brace_tag_list()

            elif tt == TT.CLOSURE_ALLOWED:
                self._advance(); self._skip_colon()
                word = self._read_bare_line().strip().lower()
                closure_allowed = (word != "false")

            else:
                self._advance()     # skip unknown token at top level

        if self._cur().type == TT.END:
            self._advance()

        if alphabet is None:
            raise ParseError(f"{self._fname}: missing alphabet section")

        return TemplateNode(
            source_file     = self._fname,
            machine         = machine,
            template_id     = template_id,
            pattern_family  = pattern_family,
            difficulty      = difficulty,
            description     = description,
            alphabet        = alphabet,
            roles           = roles,
            parameters      = parameters,
            conditions      = conditions,
            testing         = testing,
            tags            = tags,
            closure_allowed = closure_allowed,
        )

    # ── machine type ──────────────────────────────────────────────────────────

    def _parse_machine_type(self) -> str:
        self._skip_newlines()
        t = self._cur()
        if t.type in (TT.DFA, TT.NFA, TT.PDA, TT.TM):
            self._advance()
            return t.value.upper()
        return self._advance().value.upper()

    # ── bare line (rest of line after a colon) ────────────────────────────────

    def _read_bare_line(self) -> str:
        parts = []
        while self._cur().type not in _TOP_LEVEL and \
              self._cur().type != TT.NEWLINE:
            parts.append(str(self._advance().value))
        return "".join(parts).strip()

    # ── free text (description body) ──────────────────────────────────────────

    def _read_free_text(self) -> str:
        parts = []
        while self._cur().type not in _TOP_LEVEL:
            t = self._advance()
            parts.append(" " if t.type == TT.NEWLINE else str(t.value))
        return " ".join(parts).strip()

    # ── brace tag list  { tag, tag, … }  (multi-word tags allowed) ───────────

    def _parse_brace_tag_list(self) -> list[str]:
        self._skip_newlines()
        tags: list[str] = []
        if self._cur().type != TT.LBRACE:
            return tags
        self._advance()
        current: list[str] = []
        while self._cur().type not in (TT.RBRACE, TT.EOF):
            t = self._cur()
            if t.type == TT.NEWLINE:
                self._advance()
            elif t.type == TT.COMMA:
                self._advance()
                tag = " ".join(current).strip()
                if tag:
                    tags.append(tag)
                current = []
            else:
                current.append(str(self._advance().value))
        tag = " ".join(current).strip()
        if tag:
            tags.append(tag)
        if self._cur().type == TT.RBRACE:
            self._advance()
        return tags

    # ── alphabet section ──────────────────────────────────────────────────────

    def _parse_alphabet(self) -> AlphabetNode:
        size  = 2
        pools: list[list[str]] = []
        self._skip_newlines()

        _STOP = {TT.ROLES, TT.PARAMETERS, TT.CONDITION,
                  TT.TESTING, TT.TAGS, TT.END, TT.EOF}

        while self._cur().type not in _STOP:
            self._skip_newlines()
            tt = self._cur().type
            if tt == TT.SIZE:
                self._advance(); self._skip_colon()
                self._skip_newlines()
                size = self._expect(TT.INT).value
            elif tt == TT.SYMBOL_POOLS:
                self._advance(); self._skip_colon()
                self._skip_newlines()
                while self._cur().type == TT.LBRACE:
                    pools.append(self._parse_symbol_list())
                    self._skip_newlines()
            else:
                if self._cur().type in _STOP:
                    break
                self._advance()

        if not pools:
            pools = [["a", "b", "c", "d"]]
        return AlphabetNode(size=size, pools=pools)

    def _parse_symbol_list(self) -> list[str]:
        """Parse { sym, sym, … } returning list of symbol strings."""
        self._expect(TT.LBRACE)
        syms: list[str] = []
        while self._cur().type not in (TT.RBRACE, TT.EOF):
            t = self._cur()
            if t.type in (TT.COMMA, TT.NEWLINE):
                self._advance()
            else:
                syms.append(str(self._advance().value))
        self._expect(TT.RBRACE)
        return syms

    # ── roles section ─────────────────────────────────────────────────────────
    #
    # Syntax:  A <- alpha[0]
    #          B <- alpha[1]
    #
    # alpha[N] was already lexed as ALPHA_IDX(N) by the Lexer.
    # alpha_index is a position within the selected alphabet, not a pool index.

    def _parse_roles(self) -> list[RoleBindingNode]:
        self._skip_newlines()
        bindings: list[RoleBindingNode] = []
        if self._cur().type != TT.LBRACE:
            return bindings
        self._advance()
        while self._cur().type not in (TT.RBRACE, TT.EOF):
            t = self._cur()
            if t.type in (TT.NEWLINE, TT.COMMA):
                self._advance()
                continue
            if t.type == TT.IDENT:
                name = self._advance().value
                self._skip_newlines()
                if self._cur().type == TT.ARROW:
                    self._advance()
                    self._skip_newlines()
                    if self._cur().type == TT.ALPHA_IDX:
                        idx = self._advance().value
                    else:
                        idx = 0   # fallback if token is unexpected
                    bindings.append(RoleBindingNode(name=name, alpha_index=idx))
            else:
                self._advance()
        if self._cur().type == TT.RBRACE:
            self._advance()
        return bindings

    # ── parameters section ────────────────────────────────────────────────────

    def _parse_parameters(self) -> list[Any]:
        self._skip_newlines()
        params: list[Any] = []
        _STOP = {TT.CONDITION, TT.TESTING, TT.TAGS, TT.END,
                  TT.ALPHABET, TT.ROLES, TT.EOF}
        while self._cur().type not in _STOP:
            self._skip_newlines()
            if self._cur().type == TT.IDENT:
                p = self._parse_one_param()
                if p:
                    params.append(p)
            elif self._cur().type not in _STOP:
                self._advance()
        return params

    def _parse_one_param(self) -> Any | None:
        name = self._advance().value
        self._skip_newlines()
        if self._cur().type != TT.IN:
            return None
        self._advance()
        self._skip_newlines()

        # strings({R,…}, K)
        if self._cur().type == TT.STRINGS_KW:
            self._advance()
            self._expect(TT.LPAREN)
            self._expect(TT.LBRACE)
            role_names: list[str] = []
            while self._cur().type not in (TT.RBRACE, TT.EOF):
                if self._cur().type == TT.COMMA:
                    self._advance()
                else:
                    role_names.append(str(self._advance().value))
            self._expect(TT.RBRACE)
            self._expect(TT.COMMA)
            self._skip_newlines()
            length_ref = str(self._advance().value)
            self._expect(TT.RPAREN)
            return StringParamNode(name=name, role_names=role_names,
                                   length_ref=length_ref)

        # [lo, hi]
        if self._cur().type == TT.LBRACKET:
            self._advance()
            lo = self._expect(TT.INT).value
            if self._cur().type == TT.COMMA:
                self._advance()
            hi = self._expect(TT.INT).value
            self._expect(TT.RBRACKET)
            return ScalarParamNode(name=name, values=list(range(lo, hi + 1)))

        # {v, v, …}
        if self._cur().type == TT.LBRACE:
            self._advance()
            vals: list[int] = []
            while self._cur().type not in (TT.RBRACE, TT.EOF):
                if self._cur().type == TT.COMMA:
                    self._advance()
                elif self._cur().type == TT.INT:
                    vals.append(self._advance().value)
                else:
                    self._advance()
            self._expect(TT.RBRACE)
            return ScalarParamNode(name=name, values=vals)

        return None

    # ── conditions section ────────────────────────────────────────────────────

    def _parse_conditions(self) -> list[Any]:
        constraints: list[Any] = []
        _STOP = {TT.TESTING, TT.TAGS, TT.CLOSURE_ALLOWED, TT.END, TT.ALPHABET,
                  TT.TEMPLATE_ID, TT.PATTERN_FAM, TT.DIFFICULTY,
                  TT.DESCRIPTION, TT.ROLES, TT.PARAMETERS, TT.EOF}
        while self._cur().type not in _STOP:
            if self._cur().type == TT.NEWLINE:
                self._advance()
                continue
            c = self._parse_one_constraint()
            if c is None:
                continue
            # OR chaining: A or B or C  →  OrConstraintNode([A, B, C])
            while self._cur().type == TT.OR:
                self._advance()                      # consume 'or'
                rhs = self._parse_one_constraint()
                if rhs is None:
                    break
                if isinstance(c, OrConstraintNode):
                    c.operands.append(rhs)           # extend existing chain
                else:
                    c = OrConstraintNode(operands=[c, rhs])
            constraints.append(c)
        return constraints

    def _parse_one_constraint(self) -> Any | None:
        t = self._cur()
        if t.type == TT.PALINDROME:
            self._advance()
            return PalindromeNode()
        if t.type == TT.NO_ADJACENT_SAME:
            self._advance()
            return NoAdjacentSameNode()
        if t.type == TT.PREFIX_ORDER:
            return self._parse_prefix_order()
        if t.type == TT.KTH_FROM_END:
            return self._parse_kth_from_end()
        if t.type == TT.COUNT:
            return self._parse_count_constraint()
        if t.type == TT.LENGTH:
            return self._parse_length_constraint()
        if t.type == TT.DECIMAL_EQUIVALENT:
            return self._parse_decimal_equivalent_constraint()
        if t.type == TT.PREFIX_COUNT:
            return self._parse_prefix_count_constraint()
        if t.type == TT.EVERY:
            return self._parse_follow_predicate()
        if t.type in (TT.BEGINS_WITH, TT.ENDS_WITH, TT.CONTAINS):
            return self._parse_string_predicate()
        if t.type == TT.IDENT:
            return self._parse_var_constraint()
        # Unknown — skip to next newline
        while self._cur().type not in (TT.NEWLINE, TT.EOF):
            self._advance()
        return None
    
    # decimal_equivalent % k == 0
    def _parse_decimal_equivalent_constraint(self) -> Any:
        self._advance()                      # consume 'decimal_equivalent'
        #self._expect(TT.LPAREN)
        #self._expect(TT.RPAREN)
        self._expect(TT.PERCENT)
        mod = self._parse_expr()
        self._expect(TT.EQ)
        val = self._parse_expr()
        return DecimalEquivalentConstraintNode(modulus=mod, value=val)

    def _parse_count_constraint(self) -> Any:
        self._advance()                      # consume 'count'
        self._expect(TT.LPAREN)
        role = str(self._advance().value)
        self._expect(TT.RPAREN)
        if self._cur().type == TT.PERCENT:
            self._advance()
            mod = self._parse_expr()
            self._expect(TT.EQ)
            val = self._parse_expr()
            return CountModConstraintNode(role=role, modulus=mod, value=val)
        rel = self._parse_rel()
        rhs = self._parse_expr()
        return CountConstraintNode(role=role, rel=rel, rhs=rhs)

    def _parse_length_constraint(self) -> Any:
        """
        New syntax:   length <= K
                      length % K == 0
                      length >= K

        'length' is a bare keyword with no argument.
        The parser consumes 'length' then reads the operator and rhs directly.
        """
        self._advance()                      # consume 'length'
        if self._cur().type == TT.PERCENT:
            self._advance()
            mod = self._parse_expr()
            self._expect(TT.EQ)
            val = self._parse_expr()
            return LengthModConstraintNode(modulus=mod, value=val)
        rel = self._parse_rel()
        rhs = self._parse_expr()
        return LengthConstraintNode(rel=rel, rhs=rhs)

    def _parse_prefix_count_constraint(self) -> PrefixCountConstraintNode:
        """
        prefix_count(R1) <rel> prefix_count(R2)
        """
        self._advance()                      # consume 'prefix_count'
        self._expect(TT.LPAREN)
        role1 = str(self._advance().value)
        self._expect(TT.RPAREN)
        rel = self._parse_rel()
        self._expect(TT.PREFIX_COUNT)
        self._expect(TT.LPAREN)
        role2 = str(self._advance().value)
        self._expect(TT.RPAREN)
        return PrefixCountConstraintNode(role1=role1, rel=rel, role2=role2)

    def _parse_follow_predicate(self) -> FollowPredicateNode:
        self._advance()                      # 'every'
        self._expect(TT.LPAREN)
        trigger = str(self._advance().value)
        self._expect(TT.RPAREN)
        self._expect(TT.FOLLOWED_BY)
        self._expect(TT.LPAREN)
        follower = str(self._advance().value)
        self._expect(TT.RPAREN)
        return FollowPredicateNode(trigger=trigger, follower=follower)

    def _parse_prefix_order(self) -> PrefixOrderNode:
        """
        prefix_order(A, B)         — two roles
        prefix_order(A, B, C)      — three roles
        prefix_order(A, B, C, D)   — four roles, etc.

        Parses:  PREFIX_ORDER LPAREN IDENT (COMMA IDENT)* RPAREN
        """
        self._advance()                      # consume 'prefix_order'
        self._expect(TT.LPAREN)
        roles: list[str] = []
        while self._cur().type not in (TT.RPAREN, TT.EOF):
            if self._cur().type == TT.COMMA:
                self._advance()
            elif self._cur().type == TT.IDENT:
                roles.append(str(self._advance().value))
            else:
                self._advance()             # skip unexpected token
        self._expect(TT.RPAREN)
        if not roles:
            raise ParseError(
                f"{self._fname} L{self._cur().line}: "
                f"prefix_order() requires at least two role names"
            )
        return PrefixOrderNode(roles=roles)

    def _parse_kth_from_end(self) -> KthFromEndNode:
        """
        kth_from_end(K, A)

        Parses:  KTH_FROM_END LPAREN IDENT COMMA IDENT RPAREN
          first arg  — scalar parameter name giving K  (e.g. 'K')
          second arg — role name whose symbol must be at position K from end
        """
        self._advance()                      # consume 'kth_from_end'
        self._expect(TT.LPAREN)
        pos_param = str(self._advance().value)   # e.g. 'K'
        self._expect(TT.COMMA)
        role = str(self._advance().value)        # e.g. 'A'
        self._expect(TT.RPAREN)
        return KthFromEndNode(position_param=pos_param, role=role)

    def _parse_string_predicate(self) -> StringPredicateNode:
        kind_map = {
            TT.BEGINS_WITH: "begins_with",
            TT.ENDS_WITH:   "ends_with",
            TT.CONTAINS:    "contains",
        }
        kind = kind_map[self._cur().type]
        self._advance()
        self._expect(TT.LPAREN)
        param = str(self._advance().value)
        self._expect(TT.RPAREN)
        return StringPredicateNode(kind=kind, param=param)

    def _parse_var_constraint(self) -> VarConstraintNode:
        lhs = str(self._advance().value)
        rel = self._parse_rel()
        rhs = self._parse_expr()
        return VarConstraintNode(lhs=lhs, rel=rel, rhs=rhs)

    # ── relational operator ───────────────────────────────────────────────────

    def _parse_rel(self) -> str:
        t = self._cur()
        rel_map = {TT.EQ: "==", TT.NEQ: "!=",
                   TT.LT: "<",  TT.GT: ">",
                   TT.LTE: "<=", TT.GTE: ">="}
        if t.type in rel_map:
            self._advance()
            return rel_map[t.type]
        raise ParseError(f"{self._fname} L{t.line}: expected relational "
                         f"operator, got {t.type.name} ({t.value!r})")

    # ── expression parser: atom ( (*|+|-) atom )* ─────────────────────────────

    def _parse_expr(self) -> Any:
        left = self._parse_atom()
        while self._cur().type in (TT.STAR, TT.PLUS, TT.MINUS):
            op    = self._advance().type
            right = self._parse_atom()
            if op == TT.STAR:
                left = MulExprNode(left=left, right=right)
            elif op == TT.PLUS:
                left = AddExprNode(left=left, right=right)
            else:
                left = SubExprNode(left=left, right=right)
        return left

    def _parse_atom(self) -> Any:
        t = self._cur()
        if t.type == TT.INT:
            self._advance()
            return IntLitNode(value=t.value)
        if t.type == TT.COUNT:
            self._advance()
            self._expect(TT.LPAREN)
            role = str(self._advance().value)
            self._expect(TT.RPAREN)
            return CountExprNode(role=role)
        if t.type == TT.LPAREN:
            self._advance()
            expr = self._parse_expr()
            self._expect(TT.RPAREN)
            return expr
        if t.type == TT.IDENT:
            self._advance()
            return IdentNode(name=t.value)
        # Fallback — keywords used as identifiers (e.g. role names)
        self._advance()
        return IdentNode(name=str(t.value))

    # ── testing section ───────────────────────────────────────────────────────

    def _parse_testing(self) -> dict:
        result = {"cases": 200, "max_length": 12}
        _STOP  = {TT.TAGS, TT.END, TT.TEMPLATE_ID, TT.PATTERN_FAM,
                   TT.DIFFICULTY, TT.DESCRIPTION, TT.ALPHABET, TT.ROLES,
                   TT.PARAMETERS, TT.CONDITION, TT.EOF}
        self._skip_newlines()
        while self._cur().type not in _STOP:
            tt = self._cur().type
            if tt == TT.CASES:
                self._advance(); self._skip_colon()
                self._skip_newlines()
                result["cases"] = self._expect(TT.INT).value
            elif tt == TT.MAX_LENGTH:
                self._advance(); self._skip_colon()
                self._skip_newlines()
                result["max_length"] = self._expect(TT.INT).value
            elif tt == TT.NEWLINE:
                self._advance()
            else:
                self._advance()
        return result
