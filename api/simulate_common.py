"""
Shared logic for POST /student|practice|faculty/simulate/{question_id}.
"""
from __future__ import annotations

from fastapi import HTTPException

from api import models, schemas
from api.simulator import run_simulation


def _tc_dict(tc: object) -> tuple[str, str]:
    if isinstance(tc, dict):
        return tc["input"], tc["label"]
    return tc.input, tc.label


def build_simulate_response(q: models.Question, payload: schemas.SimulateIn) -> schemas.SimulateOut:
    automata_dict = payload.automata.model_dump()
    mode = payload.mode
    max_len = int(q.max_length or 0) or 500

    try:
        if mode == "custom_input":
            inp = payload.input if payload.input is not None else ""
            if len(inp) > max_len:
                raise HTTPException(
                    status_code=400,
                    detail=f"Input length exceeds max_length ({max_len}) for this question",
                )
            r = run_simulation(automata_dict, q.machine, inp, None)
            return _to_simulate_out([r])

        if mode == "single_test":
            suite = payload.suite
            if suite not in ("public", "private"):
                raise HTTPException(
                    status_code=400,
                    detail="single_test requires suite: public or private",
                )
            idx = payload.test_index if payload.test_index is not None else 0
            raw = (
                (q.public_examples or [])
                if suite == "public"
                else (q.test_cases or [])
            )
            if not raw:
                raise HTTPException(
                    status_code=400,
                    detail="No test cases in the selected suite",
                )
            if idx < 0 or idx >= len(raw):
                raise HTTPException(
                    status_code=400,
                    detail=f"test_index must be between 0 and {len(raw) - 1}",
                )
            inp, label = _tc_dict(raw[idx])
            if len(inp) > max_len:
                raise HTTPException(
                    status_code=400,
                    detail=f"Input length exceeds max_length ({max_len}) for this question",
                )
            r = run_simulation(automata_dict, q.machine, inp, label)
            return _to_simulate_out([r])

        if mode == "test_suite":
            suite = (payload.suite or "all").strip().lower()
            if suite not in ("public", "private", "all"):
                raise HTTPException(
                    status_code=400,
                    detail="suite must be one of: public, private, all",
                )
            runs: list[dict] = []
            if suite in ("public", "all"):
                for tc in q.public_examples or []:
                    inp, label = _tc_dict(tc)
                    if len(inp) > max_len:
                        continue
                    runs.append(run_simulation(automata_dict, q.machine, inp, label))
            if suite in ("private", "all"):
                for tc in q.test_cases or []:
                    inp, label = _tc_dict(tc)
                    if len(inp) > max_len:
                        continue
                    runs.append(run_simulation(automata_dict, q.machine, inp, label))
            return _to_simulate_out(runs)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    raise HTTPException(status_code=400, detail="Invalid mode")


def _to_simulate_out(runs: list[dict]) -> schemas.SimulateOut:
    out: list[schemas.SingleSimResult] = []
    for r in runs:
        steps_raw = r.get("steps") or []
        steps = [schemas.SimStepOut(**s) for s in steps_raw]
        out.append(
            schemas.SingleSimResult(
                machine=r["machine"],
                input=r["input"],
                expected=r.get("expected"),
                got=r["got"],
                correct=r.get("correct"),
                accepted=bool(r["accepted"]),
                final_reason=r["final_reason"],
                steps=steps,
            )
        )
    return schemas.SimulateOut(runs=out)
