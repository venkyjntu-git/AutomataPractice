"""
schemas.py — Pydantic request / response models (practice-only subset).
"""
from __future__ import annotations

import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


# ── Questions ─────────────────────────────────────────────────────────────────

class TestCase(BaseModel):
    input: str
    label: str   # "ACCEPT" | "REJECT"

class QuestionOut(BaseModel):
    id: int
    template_id: Optional[str]
    machine: str
    difficulty: Optional[str]
    text: str
    pattern: Optional[str]
    alphabet: list[str]
    max_length: int
    is_closure: bool
    generated_at: datetime.datetime

    class Config:
        from_attributes = True

class QuestionDetail(QuestionOut):
    """Practice question payload — includes private grading tests for simulation UI."""
    public_examples: list[TestCase]
    grading_tests: list[TestCase] = Field(default_factory=list)


# ── Submissions ───────────────────────────────────────────────────────────────

class StateIn(BaseModel):
    id: str
    label: Optional[str] = None
    initial: bool = False
    accept: bool = False

class TransitionIn(BaseModel):
    from_state: str
    to_state: str
    symbol: str          # ε for epsilon; comma-separated for multiple symbols
    stack_top: Optional[str] = None   # PDA: pop symbol (ε = empty / no pop check)
    stack_push: Optional[str] = None  # PDA: push string (ε = push nothing)
    write: Optional[str] = None       # TM: write symbol
    direction: Optional[str] = None   # TM: L | R

class AutomataIn(BaseModel):
    states: list[StateIn]
    transitions: list[TransitionIn]


class SimStepOut(BaseModel):
    """One row in a step-by-step simulation trace (DFA/NFA/PDA/TM)."""

    model_config = ConfigDict(extra="ignore")

    kind: str
    state: Optional[str] = None
    remaining_input: Optional[str] = None
    active_states: Optional[list[str]] = None
    stack: Optional[list[str]] = None
    tape: Optional[list[str]] = None
    head: Optional[int] = None
    note: str = ""


class SingleSimResult(BaseModel):
    machine: str
    input: str
    expected: Optional[str] = None
    got: str
    correct: Optional[bool] = None
    accepted: bool
    final_reason: str
    steps: list[SimStepOut]


class SimulateIn(BaseModel):
    automata: AutomataIn
    mode: Literal["custom_input", "test_suite", "single_test"]
    input: Optional[str] = None
    suite: Optional[Literal["public", "private", "all"]] = None
    """For mode=single_test: public or private suite only."""
    test_index: Optional[int] = None
    """0-based index into the chosen suite (public_examples or test_cases)."""


class SimulateOut(BaseModel):
    runs: list[SingleSimResult]


class TestCaseResult(BaseModel):
    input: str
    expected: str
    got: str
    correct: bool
    reason: str = ""

class SubmissionResult(BaseModel):
    result:       str           # "pass" | "fail"
    score:        float         # 0–20
    passed:       int
    total:        int
    summary:      list[str]     # header lines matching evaluator.py format
    equiv_lines:  list[str]     # equivalence section
    test_details: list[TestCaseResult]


# ── Practice (unauthenticated) ─────────────────────────────────────────────────

class PracticeSessionOut(BaseModel):
    practice_user_key: str


class PracticeGenerateIn(BaseModel):
    practice_user_key: str
    machine: str
    difficulty: Optional[str] = None  # legacy "0".."5"; omitted if using tier
    closure_only: bool = False  # legacy; maps to question_style when style omitted
    question_style: Optional[str] = None  # random | simple | closure
    difficulty_tier: Optional[str] = None  # easy | medium | hard | any


class PracticeHistoryRow(BaseModel):
    id: int
    machine: str
    difficulty: Optional[str]
    is_closure: bool
    generated_at: datetime.datetime

    class Config:
        from_attributes = True


class PracticeGenerateOut(BaseModel):
    question_id: int
