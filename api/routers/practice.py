"""
routers/practice.py — Unauthenticated practice: session id, generate, fetch, submit.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.db import get_db
from api import models, schemas
from api.generator_bridge import run_generation_practice
from api.practice_access import practice_can_access_question
from api.simulate_common import build_simulate_response
from api.simulator import run_test_cases

router = APIRouter(prefix="/practice", tags=["practice"])

ALLOWED_MACHINES = frozenset({"DFA", "PDA", "TM"})
ALLOWED_DIFFICULTIES = frozenset(str(i) for i in range(6))  # legacy 0–5
ALLOWED_QUESTION_STYLES = frozenset({"random", "simple", "closure"})
ALLOWED_DIFFICULTY_TIERS = frozenset({"easy", "medium", "hard", "any"})


def _normalize_practice_key(key: str) -> str:
    try:
        return str(uuid.UUID(key.strip()))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid practice_user_key")


@router.post("/session", response_model=schemas.PracticeSessionOut)
def create_session():
    return schemas.PracticeSessionOut(practice_user_key=str(uuid.uuid4()))


@router.post("/generate", response_model=schemas.PracticeGenerateOut)
def generate_one(payload: schemas.PracticeGenerateIn, db: Session = Depends(get_db)):
    machine = payload.machine.strip().upper()
    if machine not in ALLOWED_MACHINES:
        raise HTTPException(
            status_code=400,
            detail=f"machine must be one of {sorted(ALLOWED_MACHINES)}",
        )
    practice_key = _normalize_practice_key(payload.practice_user_key)

    style = (payload.question_style or "").strip().lower()
    if not style:
        style = "closure" if payload.closure_only else "simple"
    if style not in ALLOWED_QUESTION_STYLES:
        raise HTTPException(
            status_code=400,
            detail=f"question_style must be one of {sorted(ALLOWED_QUESTION_STYLES)}",
        )

    tier_raw = (payload.difficulty_tier or "").strip().lower()
    tier: str | None = tier_raw if tier_raw else None
    if tier and tier not in ALLOWED_DIFFICULTY_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"difficulty_tier must be one of {sorted(ALLOWED_DIFFICULTY_TIERS)} or omitted",
        )

    diff: str | None = None
    if (not tier or tier == "any") and payload.difficulty is not None and str(
        payload.difficulty
    ).strip() != "":
        diff = str(payload.difficulty).strip()
        if diff not in ALLOWED_DIFFICULTIES:
            raise HTTPException(
                status_code=400,
                detail=f"difficulty must be one of {sorted(ALLOWED_DIFFICULTIES)} or omitted",
            )

    try:
        qdict = run_generation_practice(
            machine,
            difficulty=diff,
            closure_only=bool(payload.closure_only),
            question_style=style,
            difficulty_tier=tier,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    obj = models.Question(
        template_id=qdict.get("template_id", ""),
        machine=qdict.get("machine", machine),
        difficulty=str(qdict.get("difficulty", "")),
        text=qdict.get("text", qdict.get("question_text", "")),
        pattern=qdict.get("pattern", ""),
        alphabet=qdict.get("alphabet", []),
        max_length=qdict.get("max_length", 30),
        test_cases=qdict.get("test_cases", []),
        public_examples=qdict.get("public_examples", []),
        reference_dfa=qdict.get("reference_dfa"),
        is_closure=bool(qdict.get("closure_info")),
        practice_session_key=practice_key,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return schemas.PracticeGenerateOut(question_id=obj.id)


@router.get("/history", response_model=list[schemas.PracticeHistoryRow])
def practice_history(
    practice_user_key: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Questions for this practice user: created under this session key, plus any
    question they submitted to under this key (deduped, newest first).
    """
    practice_key = _normalize_practice_key(practice_user_key)

    created = (
        db.query(models.Question)
        .filter(models.Question.practice_session_key == practice_key)
        .all()
    )
    seen: set[int] = {q.id for q in created}
    extra_ids = [
        row[0]
        for row in db.query(models.Submission.question_id)
        .filter(models.Submission.practice_user_key == practice_key)
        .distinct()
        .all()
        if row[0] not in seen
    ]
    extra: list[models.Question] = []
    if extra_ids:
        extra = (
            db.query(models.Question)
            .filter(models.Question.id.in_(extra_ids))
            .all()
        )
    combined = list(created) + [q for q in extra if q.id not in seen]
    combined.sort(key=lambda q: q.generated_at, reverse=True)
    return [schemas.PracticeHistoryRow.model_validate(r) for r in combined]


@router.get("/question/{question_id}", response_model=schemas.QuestionDetail)
def get_question(
    question_id: int,
    practice_user_key: str = Query(...),
    db: Session = Depends(get_db),
):
    practice_key = _normalize_practice_key(practice_user_key)
    q = practice_can_access_question(db, question_id, practice_key)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    def _tc(tc: Any) -> schemas.TestCase:
        if isinstance(tc, dict):
            return schemas.TestCase.model_validate(tc)
        return schemas.TestCase(input=tc.input, label=tc.label)

    return schemas.QuestionDetail(
        id=q.id,
        template_id=q.template_id,
        machine=q.machine,
        difficulty=q.difficulty,
        text=q.text,
        pattern=q.pattern,
        alphabet=q.alphabet,
        max_length=q.max_length,
        is_closure=q.is_closure,
        generated_at=q.generated_at,
        public_examples=[_tc(tc) for tc in (q.public_examples or [])],
        grading_tests=[_tc(tc) for tc in (q.test_cases or [])],
    )


@router.post("/submit/{question_id}", response_model=schemas.SubmissionResult)
def submit(
    question_id: int,
    automata: schemas.AutomataIn,
    practice_user_key: str = Query(...),
    db: Session = Depends(get_db),
):
    practice_key = _normalize_practice_key(practice_user_key)
    q = practice_can_access_question(db, question_id, practice_key)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    automata_dict = automata.model_dump()
    try:
        report = run_test_cases(
            automata_dict,
            q.test_cases,
            machine=q.machine,
            reference_dfa=q.reference_dfa,
            alphabet=q.alphabet,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    submission = models.Submission(
        student_id=None,
        practice_user_key=practice_key,
        question_id=question_id,
        automata_json=automata_dict,
        result=report["result"],
        score=report["score"],
        details=report["test_details"],
    )
    db.add(submission)
    db.commit()

    return schemas.SubmissionResult(
        result=report["result"],
        score=report["score"],
        passed=report["passed"],
        total=report["total"],
        summary=report["summary"],
        equiv_lines=report["equiv_lines"],
        test_details=[schemas.TestCaseResult(**d) for d in report["test_details"]],
    )


@router.post("/simulate/{question_id}", response_model=schemas.SimulateOut)
def practice_simulate(
    question_id: int,
    payload: schemas.SimulateIn,
    practice_user_key: str = Query(...),
    db: Session = Depends(get_db),
):
    practice_key = _normalize_practice_key(practice_user_key)
    q = practice_can_access_question(db, question_id, practice_key)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    return build_simulate_response(q, payload)


@router.get("/submissions/{question_id}")
def list_submissions(
    question_id: int,
    practice_user_key: str = Query(...),
    db: Session = Depends(get_db),
):
    practice_key = _normalize_practice_key(practice_user_key)
    q = practice_can_access_question(db, question_id, practice_key)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    subs = (
        db.query(models.Submission)
        .filter(
            models.Submission.question_id == question_id,
            models.Submission.practice_user_key == practice_key,
        )
        .order_by(models.Submission.submitted_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "submitted_at": s.submitted_at,
            "result": s.result,
            "score": s.score,
            "total": len(s.details) if s.details else 20,
            "automata_json": s.automata_json,
        }
        for s in subs
    ]
