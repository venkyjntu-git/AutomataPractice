"""Helpers for practice_user_key access to questions (owned or submitted)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from api import models


def practice_can_access_question(db: Session, question_id: int, practice_key: str) -> models.Question | None:
    """
    Return Question if the practice key may load it:
    - question was generated under this session, or
    - at least one practice submission exists for this key + question.
    """
    q = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not q:
        return None
    if q.practice_session_key == practice_key:
        return q
    sub = (
        db.query(models.Submission)
        .filter(
            models.Submission.question_id == question_id,
            models.Submission.practice_user_key == practice_key,
        )
        .first()
    )
    return q if sub else None
