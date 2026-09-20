"""
lexer.py
========
Hand-written character-level lexer for the AutomataGen DSL.

Produces a flat list of Token objects from a source string.

Key rules
---------
- Lines starting with '#' are comments and are skipped entirely.
- NEWLINE tokens are emitted ONLY inside the condition block
  (between the 'condition:' keyword and the next top-level keyword).
  Everywhere else newlines are treated as whitespace.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


# ── Token types ────────────────────────────────────────────────────────────────

class TT(Enum):
    # ── Machine-type keywords
    AUTOMATA     = auto()
    END          = auto()
    DFA          = auto()
    NFA          = auto()
    PDA          = auto()
    TM           = auto()
    # ── Section keywords
    TEMPLATE_ID  = auto()
    PATTERN_FAM  = auto()
    DIFFICULTY   = auto()
    DESCRIPTION  = auto()
    ALPHABET     = auto()
    SIZE         = auto()
    SYMBOL_POOLS = auto()
    ROLES        = auto()
    PARAMETERS   = auto()
    CONDITION    = auto()
    TESTING      = auto()
    CASES        = auto()
    MAX_LENGTH   = auto()
    TAGS         = auto()
    CLOSURE_ALLOWED = auto()
    # ── Expression keywords
    IN           = auto()
    STRINGS_KW   = auto()
    COUNT        = auto()
    LENGTH       = auto()
    PREFIX_COUNT = auto()
    PALINDROME       = auto()
    NO_ADJACENT_SAME = auto()   
    PREFIX_ORDER     = auto()   # prefix_order(R, R, …)
    EVERY        = auto()
    FOLLOWED_BY  = auto()
    KTH_FROM_END = auto()   
    BEGINS_WITH  = auto()
    ENDS_WITH    = auto()
    CONTAINS     = auto()
    DECIMAL_EQUIVALENT = auto()
    OR           = auto()   # 'or' — disjunction between two constraints
    # ── Literals
    IDENT        = auto()   # identifiers, role names, free variables
    INT          = auto()
    # ── Punctuation
    COLON        = auto()
    COMMA        = auto()
    LPAREN       = auto()
    RPAREN       = auto()
    LBRACE       = auto()
    RBRACE       = auto()
    LBRACKET     = auto()
    RBRACKET     = auto()
    ARROW        = auto()   
    ALPHA_IDX    = auto()   
    EQ           = auto()   
    NEQ          = auto()   
    LT           = auto()
    GT           = auto()
    LTE          = auto()   
    GTE          = auto()   
    PERCENT      = auto()
    STAR         = auto()
    PLUS         = auto()
    MINUS        = auto()
    NEWLINE      = auto()   
    EOF          = auto()


# Map bare words → keyword token types
_KEYWORDS: dict[str, TT] = {
    "AUTOMATA":       TT.AUTOMATA,
    "END":            TT.END,
    "DFA":            TT.DFA,
    "NFA":            TT.NFA,
    "PDA":            TT.PDA,
    "TM":             TT.TM,
    "template_id":    TT.TEMPLATE_ID,
    "pattern_family": TT.PATTERN_FAM,
    "difficulty":     TT.DIFFICULTY,
    "description":    TT.DESCRIPTION,
    "alphabet":       TT.ALPHABET,
    "size":           TT.SIZE,
    "symbol_pools":   TT.SYMBOL_POOLS,
    "roles":          TT.ROLES,
    "parameters":     TT.PARAMETERS,
    "condition":      TT.CONDITION,
    "testing":        TT.TESTING,
    "cases":          TT.CASES,
    "max_length":     TT.MAX_LENGTH,
    "tags":           TT.TAGS,
    "closure_allowed": TT.CLOSURE_ALLOWED,
    "in":             TT.IN,
    "strings":        TT.STRINGS_KW,
    "count":          TT.COUNT,
    "length":         TT.LENGTH,
    "prefix_count":   TT.PREFIX_COUNT,
    "palindrome":       TT.PALINDROME,
    "no_adjacent_same": TT.NO_ADJACENT_SAME,
    "prefix_order":   TT.PREFIX_ORDER,
    "every":          TT.EVERY,
    "followed_by":    TT.FOLLOWED_BY,
    "kth_from_end":   TT.KTH_FROM_END,
    "begins_with":    TT.BEGINS_WITH,
    "ends_with":      TT.ENDS_WITH,
    "contains":       TT.CONTAINS,
    "decimal_equivalent": TT.DECIMAL_EQUIVALENT,
    "or":                 TT.OR,
}

# Section keywords that end the condition block
_CONDITION_ENDERS: set[TT] = {
    TT.TESTING, TT.TAGS, TT.CLOSURE_ALLOWED, TT.END, TT.TEMPLATE_ID,
    TT.PATTERN_FAM, TT.DIFFICULTY, TT.DESCRIPTION,
    TT.ALPHABET, TT.ROLES, TT.PARAMETERS,
}


@dataclass
class Token:
    type:  TT
    value: Any
    line:  int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, L{self.line})"


class LexError(Exception):
    pass


class Lexer:
    def __init__(self, src: str, filename: str = "<?>") -> None:
        self._src      = src
        self._pos      = 0
        self._line     = 1
        self._fname    = filename
        self._in_cond  = False   # True between CONDITION token and next section keyword
        self._tokens:  list[Token] = []

    # ── public entry point ────────────────────────────────────────────────────

    def tokenise(self) -> list[Token]:
        while self._pos < len(self._src):
            self._scan_one()
        self._tokens.append(Token(TT.EOF, None, self._line))
        return self._tokens

    # ── internal helpers ──────────────────────────────────────────────────────

    def _peek(self, offset: int = 0) -> str:
        idx = self._pos + offset
        return self._src[idx] if idx < len(self._src) else ""

    def _advance(self) -> str:
        ch = self._src[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
        return ch

    def _emit(self, tt: TT, val: Any) -> None:
        self._tokens.append(Token(tt, val, self._line))

    def _skip_to_eol(self) -> None:
        while self._pos < len(self._src) and self._src[self._pos] != "\n":
            self._pos += 1

    def _read_int(self) -> int:
        start = self._pos
        while self._pos < len(self._src) and self._src[self._pos].isdigit():
            self._pos += 1
        return int(self._src[start:self._pos])

    def _read_word(self) -> str:
        start = self._pos
        while self._pos < len(self._src) and \
              (self._src[self._pos].isalnum() or self._src[self._pos] == "_"):
            self._pos += 1
        return self._src[start:self._pos]


    def _scan_one(self) -> None:
        ch = self._peek()

        # comment
        if ch == "#":
            self._skip_to_eol()
            return

        # newline
        if ch == "\n":
            self._advance()
            if self._in_cond:
                self._emit(TT.NEWLINE, "\n")
            return

        # other whitespace
        if ch in " \t\r":
            self._advance()
            return

        # alpha[N] or alpha[RANDOM_INDEX]
        if self._src[self._pos: self._pos + 5] == "alpha" and \
           self._pos + 5 < len(self._src) and \
           self._src[self._pos + 5] == "[":
            self._pos += 6          
            if self._peek().isdigit():
                idx = self._read_int()
            else:
                word = self._read_word()
                idx = -1 if word == "RANDOM_INDEX" else 0
            if self._peek() == "]":
                self._advance()
            self._emit(TT.ALPHA_IDX, idx)
            return

        # <- (ARROW)
        if ch == "<" and self._peek(1) == "-":
            self._pos += 2
            self._emit(TT.ARROW, "<-")
            return

        # two-character operators
        two = self._src[self._pos: self._pos + 2]
        _two_map = {
            "==": TT.EQ, "!=": TT.NEQ,
            "<=": TT.LTE, ">=": TT.GTE,
        }
        if two in _two_map:
            self._pos += 2
            self._emit(_two_map[two], two)
            return

        # single-character punctuation
        _single_map = {
            ":": TT.COLON,    ",": TT.COMMA,
            "(": TT.LPAREN,   ")": TT.RPAREN,
            "{": TT.LBRACE,   "}": TT.RBRACE,
            "[": TT.LBRACKET, "]": TT.RBRACKET,
            "%": TT.PERCENT,  "*": TT.STAR,
            "+": TT.PLUS,     "-": TT.MINUS,
            "<": TT.LT,       ">": TT.GT,
        }
        if ch in _single_map:
            self._advance()
            self._emit(_single_map[ch], ch)
            return

        # bare '=' → treat as '=='
        if ch == "=":
            self._advance()
            self._emit(TT.EQ, "==")
            return

        # integer literal
        if ch.isdigit():
            self._emit(TT.INT, self._read_int())
            return

        # identifier or keyword
        if ch.isalpha() or ch == "_":
            word = self._read_word()
            tt   = _KEYWORDS.get(word, TT.IDENT)
            # Track condition block boundaries
            if tt == TT.CONDITION:
                self._in_cond = True
            elif tt in _CONDITION_ENDERS:
                self._in_cond = False
            self._emit(tt, word)
            return

        # Anything else is emitted as a single-char IDENT
        # (handles bracket symbols used inside pool definitions)
        self._advance()
        self._emit(TT.IDENT, ch)
