"""
models.py — SQLAlchemy ORM models (practice-only subset).
"""
from __future__ import annotations

import datetime
from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime,
    ForeignKey, Text, JSON
)
from api.db import Base


class Question(Base):
    __tablename__ = "questions"

    id           = Column(Integer, primary_key=True, index=True)
    template_id  = Column(String(200))
    machine      = Column(String(10), nullable=False)   # DFA / NFA / PDA / TM
    difficulty   = Column(String(20))
    text         = Column(Text, nullable=False)         # English question text
    pattern      = Column(Text)                         # pattern string for grading reference
    alphabet     = Column(JSON, nullable=False)         # list[str]
    max_length   = Column(Integer, default=30)
    test_cases    = Column(JSON, nullable=False)         # list[{input, label}] — grading (private)
    public_examples = Column(JSON, nullable=False)  # safe examples for students
    reference_dfa = Column(JSON, nullable=True)          # reference DFA for equivalence check (DFA only)
    is_closure    = Column(Boolean, default=False)
    generated_at = Column(DateTime, default=datetime.datetime.utcnow)
    practice_session_key = Column(String(64), nullable=True, index=True)


class Submission(Base):
    __tablename__ = "submissions"

    id           = Column(Integer, primary_key=True, index=True)
    student_id   = Column(Integer, nullable=True)  # always NULL for practice
    question_id  = Column(Integer, ForeignKey("questions.id"), nullable=False)
    practice_user_key = Column(String(64), nullable=True, index=True)
    automata_json = Column(JSON, nullable=False)   # {states:[...], transitions:[...]}
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow)
    result       = Column(String(10), default="pending")  # "pass" | "fail" | "pending"
    score        = Column(Float, default=0.0)              # 0–20
    details      = Column(JSON)                            # per-test-case results
