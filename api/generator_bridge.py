"""
generator_bridge.py — Wraps the dsl_generator pipeline for the practice endpoint.

Imports the dsl_generator package directly (no subprocess) and returns
structured data suitable for inserting into the database.
"""
from __future__ import annotations

import sys
import os

# Make dsl_generator importable
_DSL_PATH = os.path.join(os.path.dirname(__file__), "..", "dsl_generator")
if _DSL_PATH not in sys.path:
    sys.path.insert(0, _DSL_PATH)

import random
from template_handler import load_templates, build_question
from testcase_generator import generate_test_cases
from closure_handler import generate_combinations
from ref_dfa_adapter import build_reference_dfa

from api.simulator import validate_automaton_state_count


def _passes_generation_state_guard(q: dict) -> bool:
    """
    Drop DFA questions whose reference automaton exceeds AUTOMATA_MAX_STATES
    (same limit as simulation / grading).
    """
    if q.get("machine") != "DFA":
        return True
    ref = q.get("reference_dfa")
    if not ref:
        return True
    try:
        validate_automaton_state_count({"states": ref.get("states") or []})
    except ValueError:
        return False
    return True


def build_public_examples(question: dict, grading_cases: list[dict], n_each: int = 2) -> list[dict]:
    """
    Public examples for students — prefer inputs not present in grading test_cases.
    Each item: {input, label} with label ACCEPT | REJECT.
    """
    grading_inputs = {tc.get("input") for tc in grading_cases if isinstance(tc, dict)}
    pool: list[dict] = []
    for _ in range(10):
        try:
            batch = generate_test_cases(question, n_accept=8, n_reject=8)
        except Exception:
            break
        for tc in batch:
            if tc.get("input") not in grading_inputs:
                pool.append(tc)
        acc = [x for x in pool if x.get("label") == "ACCEPT"]
        rej = [x for x in pool if x.get("label") == "REJECT"]
        if len(acc) >= n_each and len(rej) >= n_each:
            break

    def _dedupe(seq: list[dict]) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []
        for tc in seq:
            inp = tc.get("input", "")
            if inp in seen:
                continue
            seen.add(inp)
            out.append(tc)
        return out

    pool = _dedupe(pool)
    acc = [x for x in pool if x.get("label") == "ACCEPT"][:n_each]
    rej = [x for x in pool if x.get("label") == "REJECT"][:n_each]

    # Last resort: allow overlap so we always return something small
    while len(acc) < n_each or len(rej) < n_each:
        try:
            batch = generate_test_cases(question, n_accept=4, n_reject=4)
        except Exception:
            break
        for tc in batch:
            if tc.get("label") == "ACCEPT" and len(acc) < n_each:
                acc.append(tc)
            elif tc.get("label") == "REJECT" and len(rej) < n_each:
                rej.append(tc)
        acc = _dedupe(acc)[:n_each]
        rej = _dedupe(rej)[:n_each]
        if len(acc) >= n_each or len(rej) >= n_each:
            break
        if not batch:
            break

    return acc + rej


def _filter_templates_by_machine_and_difficulty(
    templates: list, machine: str, difficulty: str | int | None
):
    """Return template list filtered by machine and optional difficulty."""
    cands = [t for t in templates if t.machine == machine]
    if difficulty is None or difficulty == "":
        return cands
    try:
        want = int(difficulty)
    except (TypeError, ValueError):
        return cands
    strict = [t for t in cands if int(getattr(t, "difficulty", -1)) == want]
    return strict if strict else cands


# Template difficulty ints (DSL) grouped for practice tiers — overlaps intentional.
_TIER_TO_DIFFICULTIES: dict[str, set[int]] = {
    "easy": {0, 1, 2},
    "medium": {2, 3, 4},
    "hard": {4, 5},
}


def _filter_templates_by_machine_and_tier(
    templates: list, machine: str, tier: str | None
) -> list:
    """Filter by machine and difficulty tier (easy/medium/hard/any)."""
    cands = [t for t in templates if t.machine == machine]
    if not tier or tier == "any":
        return cands
    allowed = _TIER_TO_DIFFICULTIES.get(tier, set())
    if not allowed:
        return cands
    strict = [
        t for t in cands if int(getattr(t, "difficulty", -99)) in allowed
    ]
    return strict if strict else cands


def _make_hashable_key(s) -> str:
    """Convert any state (frozenset, tuple, int, str) to a stable string key."""
    if isinstance(s, (frozenset, set)):
        return "{" + ",".join(sorted(_make_hashable_key(x) for x in s)) + "}"
    if isinstance(s, (list, tuple)):
        return "(" + ",".join(_make_hashable_key(x) for x in s) + ")"
    return str(s)


def _serialise_dfa(dfa: dict) -> dict:
    """
    Convert a reference DFA dict to a fully JSON-serialisable form.
    States may be frozensets, tuples, or ints — normalise all to strings.
    Transition dict keys (state, symbol) become a list of {from, symbol, to}.
    """
    state_key = _make_hashable_key

    states  = [state_key(s) for s in dfa.get("states", [])]
    start   = state_key(dfa["start"])
    accept  = [state_key(s) for s in dfa.get("accept", [])]
    alphabet = list(dfa.get("alphabet", []))

    transitions = []
    for (src, sym), dst in dfa.get("transitions", {}).items():
        transitions.append({
            "from":   state_key(src),
            "symbol": sym,
            "to":     state_key(dst),
        })

    return {
        "states":      states,
        "start":       start,
        "accept":      accept,
        "alphabet":    alphabet,
        "transitions": transitions,
    }


def _build_one_simple_question(candidates: list) -> dict | None:
    random.shuffle(candidates)
    for tmpl in candidates:
        try:
            built = build_question(tmpl)
            if built:
                return built
        except Exception:
            continue
    return None


def _finalize_practice_question_dict(built: dict) -> dict:
    """Attach reference DFA, test cases, and public examples; enforce AUTOMATA_MAX_STATES on DFA refs."""
    if built.get("machine") == "DFA":
        try:
            ref = build_reference_dfa(built)
            if ref is not None:
                serialized = _serialise_dfa(ref)
                validate_automaton_state_count({"states": serialized["states"]})
                built["reference_dfa"] = serialized
        except ValueError:
            raise
        except Exception:
            pass
    try:
        built["test_cases"] = generate_test_cases(built, n_accept=10, n_reject=10)
    except Exception:
        built["test_cases"] = []
    try:
        built["public_examples"] = build_public_examples(built, built["test_cases"])
    except Exception:
        built["public_examples"] = []
    return built


def _build_closure_pool(candidates: list, machine: str) -> list[dict]:
    base_questions: list[dict] = []
    random.shuffle(candidates)
    for tmpl in candidates:
        try:
            built = build_question(tmpl)
            if built:
                base_questions.append(built)
        except Exception:
            continue
    if not base_questions:
        return []
    n_combo = max(40, len(base_questions) * 4)
    closure_qs = generate_combinations(base_questions, n=n_combo)
    return [cq for cq in closure_qs if cq.get("machine") == machine]


def _run_generation_practice_once(
    machine: str,
    templates_dir: str | None = None,
    difficulty: str | int | None = None,
    closure_only: bool = False,
    question_style: str = "simple",
    difficulty_tier: str | None = None,
) -> dict:
    """
    Single attempt to build a practice question (may raise ValueError if DFA ref exceeds state limit).
    """
    if templates_dir is None:
        templates_dir = os.path.join(_DSL_PATH, "templates")

    templates = load_templates(templates_dir)
    tier = (difficulty_tier or "").strip().lower() or None
    if tier and tier != "any":
        candidates = _filter_templates_by_machine_and_tier(
            templates, machine, tier
        )
    else:
        candidates = _filter_templates_by_machine_and_difficulty(
            templates, machine, difficulty
        )
    if not candidates:
        raise RuntimeError(f"No templates found for machine {machine!r}")

    style = (question_style or "simple").strip().lower()
    if closure_only and style == "simple":
        style = "closure"

    q: dict | None = None

    if style == "simple":
        q = _build_one_simple_question(candidates)
        if not q:
            raise RuntimeError("Could not instantiate a practice question")
        return _finalize_practice_question_dict(q)

    if style == "closure":
        pool = _build_closure_pool(candidates, machine)
        if not pool:
            raise RuntimeError(
                "No closure questions available for this machine and settings. "
                "Try a different difficulty tier or use Simple / Random."
            )
        q = random.choice(pool)
        return _finalize_practice_question_dict(q)

    if style == "random":
        pool = _build_closure_pool(candidates, machine)
        if pool and random.random() < 0.5:
            q = random.choice(pool)
        else:
            q = _build_one_simple_question(candidates)
        if not q:
            raise RuntimeError("Could not instantiate a practice question")
        return _finalize_practice_question_dict(q)

    q = _build_one_simple_question(candidates)
    if not q:
        raise RuntimeError("Could not instantiate a practice question")
    return _finalize_practice_question_dict(q)


def run_generation_practice(
    machine: str,
    templates_dir: str | None = None,
    difficulty: str | int | None = None,
    closure_only: bool = False,
    question_style: str = "simple",
    difficulty_tier: str | None = None,
) -> dict:
    """
    Build a single practice question for the given machine (DFA / PDA / TM).

    question_style:
      - simple: base template only (no closure combinations).
      - closure: closure combinations only; raises if none available.
      - random: 50% closure when pool non-empty, else simple.

    difficulty_tier: easy | medium | hard | any — filters template.difficulty.
    Legacy ``difficulty`` (0–5) applies when tier is missing or any.

    Retries when a DFA reference exceeds AUTOMATA_MAX_STATES (same env as simulation).
    """
    last_state_err: ValueError | None = None
    for _ in range(40):
        try:
            return _run_generation_practice_once(
                machine,
                templates_dir=templates_dir,
                difficulty=difficulty,
                closure_only=closure_only,
                question_style=question_style,
                difficulty_tier=difficulty_tier,
            )
        except ValueError as e:
            if "Too many states" in str(e):
                last_state_err = e
                continue
            raise
    raise RuntimeError(
        "Could not generate a practice question within AUTOMATA_MAX_STATES after several attempts. "
        "Increase AUTOMATA_MAX_STATES or use a simpler question style."
    ) from last_state_err
