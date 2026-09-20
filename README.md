# AutomataGen — Practice

A web platform for practising automata theory construction, where **every
problem is generated on demand** from a domain-specific language rather than
drawn from a fixed bank. Instructors author a small set of parameterized `.dsl`
specifications; at practice time a student's request triggers live
instantiation, validation, and expansion through class-aware closure properties
into a fresh question with its own machine-synthesized test suite — and, for
DFA questions, a reference automaton for exact equivalence-based self-checking.

- **Live demo:** <https://automata-gen.onrender.com/practice>
- **License:** MIT — see [`LICENSE`](LICENSE)

## Running locally

### Backend

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r api/requirements.txt

cp .env.example .env             # required — see note below
uvicorn api.main:app --reload --port 8000
```

Smoke test: `curl http://localhost:8000/health` → `{"status":"ok"}`.


The `questions` and `submissions` tables are created automatically at import
time via `Base.metadata.create_all()` — no migrations are needed for a fresh
database.

#### Using Postgres instead of sqlite

`.env.example` defaults to `sqlite:///./practice.db`. To use the bundled
Postgres container instead:

```bash
docker compose up -d
```

Then set in `.env`:

```
DATABASE_URL=postgresql://user:password@localhost:5432/user
```

#### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | none (required) | SQLAlchemy connection string |
| `AUTOMATA_MAX_STATES` | `20` | rejects submitted or generated automata with more states, to bound Hopcroft/simulation cost |

`AUTOMATA_MAX_STATES` is defined in `api/simulator.py`. Closure-derived DFAs are
product constructions and can easily exceed 20 states, so raise this
(e.g. `AUTOMATA_MAX_STATES=128`) when working with closure questions.

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Opens on <http://localhost:5173>. Available routes:

- `/practice` — machine-type and difficulty picker
- `/practice/question/:id` — construction canvas, submission, step-by-step simulation
- `/automata/viewer/:token` — read-only automaton viewer

The API base URL is **hardcoded** to `http://localhost:8000` in
`frontend/src/api/client.ts`; change it there to point at a different backend.
The backend's CORS allowlist (`api/main.py`) permits `localhost:5173` and
`localhost:3000`.

Other scripts: `pnpm lint`, `pnpm typecheck`, `pnpm build`, `pnpm preview`.
There is no automated test suite in this repository.


## How generation works

```
  template_NN.dsl
        │
        ▼
  ┌─────────────────────── DSL Compiler ───────────────────────┐
  │  lexer  →  recursive-descent parser  →  AST                │
  │            → free-variable solver → renderer               │
  └────────────────────────────────────────────────────────────┘
        │
        ▼
  Natural-language question  +  test cases  +  reference DFA (DFA only)
        │
        │◀────────────  student's automaton (web canvas)
        ▼
  ┌─────────────── Evaluator ───────────────┐
  │  Hopcroft minimization + BFS product    │
  │  simulation over the symmetric diff     │
  └─────────────────────────────────────────┘
        │
        ▼
  Score  +  witness string / counter-example
```

Stage by stage:

| Stage | Where |
|---|---|
| Lexer — tokenizes the specification against 61 token types (`TT`) | `dsl_generator/lexer.py` |
| Recursive-descent parser — builds a typed AST | `dsl_generator/parser.py` |
| AST — 25 node dataclasses | `dsl_generator/ast_nodes.py` |
| Instantiator — samples the alphabet window, binds roles, samples parameters | `dsl_generator/template_handler.py` (`Instantiator`) |
| Free-variable solver — resolves inequality chains (`M < N < P`) to a consistent instance | `dsl_generator/testcase_generator.py` (`_solve_free_vars`) |
| Renderer — AST pattern → English question | `dsl_generator/template_handler.py` (`Renderer`) |
| Test-case synthesis | `dsl_generator/testcase_generator.py` (`generate_test_cases`) |
| Closure-property derivation | `dsl_generator/closure_handler.py` (`generate_combinations`) |
| Reference-DFA construction + Hopcroft minimization | `dsl_generator/Ref_DFA_generator.py` (`minimize_dfa`), `ref_dfa_extended.py`, `ref_dfa_adapter.py` |
| Equivalence check + scoring (out of 20) | `api/simulator.py` (`_hopcroft`, `_sym_diff_bfs`, `run_test_cases`) |
| PDA / TM simulation | `api/machine_sim.py` |

`dsl_generator/` is imported flat — it has no `__init__.py` and is placed on
`sys.path` by `api/generator_bridge.py`, which is the single seam between the
generator and the web API.

## The DSL

A specification is a plain-text `.dsl` file. Here is `dsl_generator/templates/template_01.dsl`
in full:

```
AUTOMATA DFA

template_id: DFA_MOD_COUNT

pattern_family: {counting}

difficulty: 1

description:
Construct a DFA accepting strings where the number of A symbols is divisible by k.

alphabet:
    size: 2
    symbol_pools:{a,b,c}
                 {0,1}

roles:{
    A <- alpha[0]
}

parameters:
    k in [2,6]

condition:
    count(A) % k == 0

testing:
    cases: 200
    max_length: 50

tags: {dfa,counting}

closure_allowed: true

END
```

At generation time the system samples a 2-symbol window from one of the pools
(say `{a,b}` from `{a,b,c}`), binds the abstract role `A` to `alpha[0]` = `a`,
samples `k = 6`, and renders:

> *Construct a DFA over the alphabet {a, b} that accepts all strings where the
> number of 'a' symbols is divisible by 6.*

Roles are what keep a specification alphabet-agnostic: the same file yields
questions over `{a,b}`, `{b,c}` or `{0,1}` without rewriting the condition.

### Block keywords

| Keyword | Contents | Default if omitted |
|---|---|---|
| `AUTOMATA` | `DFA` \| `NFA` \| `PDA` \| `TM` — must be the first token | required |
| `template_id` | bare identifier | `""` |
| `pattern_family` | `{tag, tag}` brace list | `[]` |
| `difficulty` | integer 0–5 | `0` |
| `description` | free text until the next block | `""` |
| `alphabet` | `size:` *int* and `symbol_pools:` one or more `{a,b,c}` lists | **required** |
| `roles` | `{ A <- alpha[0] … }`; `alpha[RANDOM_INDEX]` picks a random index | `[]` |
| `parameters` | see below | `[]` |
| `condition` | newline-separated constraints, `or`-chainable | `[]` |
| `testing` | `cases:` *int* and `max_length:` *int* | `cases: 200`, `max_length: 12` |¹
| `tags` | `{tag, tag}` brace list | `[]` |
| `closure_allowed` | `true` / `false` | `true` |
| `END` | terminates the block | optional (EOF also ends it) |

Only `alphabet` is strictly required; block order is free-form. `#` starts a comment.

¹ `max_length` is honoured, but `cases:` currently is not — `api/generator_bridge.py`
calls `generate_test_cases(..., n_accept=10, n_reject=10)`, so every question gets
20 grading cases regardless of what the specification declares.

### Parameter forms

| Form | Meaning |
|---|---|
| `k in [2,6]` | integer sampled from the **inclusive** range 2…6 |
| `k in {2,3,5}` | integer sampled from an explicit set |
| `S in strings({A,B}, K)` | a random string of length `K` over the symbols bound to roles `A` and `B` |

### Condition primitives

| Primitive | Syntax |
|---|---|
| `count` | `count(R) <rel> <expr>` |
| `count` (modular) | `count(R) % <expr> == <expr>` |
| `length` | `length <rel> <expr>` — bare keyword, no parentheses |
| `length` (modular) | `length % <expr> == <expr>` |
| `decimal_equivalent` | `decimal_equivalent % <expr> == <expr>` — bare, no parentheses |
| `prefix_count` | `prefix_count(R1) <rel> prefix_count(R2)` — both sides must be `prefix_count` |
| `prefix_order` | `prefix_order(A, B, …)` — variadic; blocks appear in this order |
| `palindrome` | bare keyword |
| `no_adjacent_same` | bare keyword |
| `kth_from_end` | `kth_from_end(K, A)` |
| `every` / `followed_by` | `every(A) followed_by(B)` |
| `begins_with` / `ends_with` / `contains` | `begins_with(S)` where `S` is a string parameter |
| free variable | `N > 0`, `M != N` — introduces a variable solved at instantiation |
| `or` | `A or B or C`, flattened into one constraint |

Relational operators: `==`, `!=`, `<`, `>`, `<=`, `>=` (a bare `=` is read as `==`).

### The shipped library

`dsl_generator/templates/` contains **55 specifications**:

| | Count |
|---|---|
| DFA | 17 |
| PDA | 16 |
| TM | 22 |

By difficulty: 0 → 4, 1 → 10, 2 → 11, 3 → 5, 4 → 10, 5 → 15.
36 are marked `closure_allowed: true`, 19 opt out.

Pattern families in the library: counting (34), palindromes (5), and one each of
adjacency, balanced parenthesis, begins-with, begins-and-ends-with, contains,
ends-with, every-symbol-followed-by, length-at-least-k, length-at-most-k,
length-divisible-by-k, length-equal-to-k, Nth-symbol-from-end, linear,
parenthesis, strings, and counting-closure.

## Closure-property generation

Given two instantiated base questions over the same alphabet, the generator
synthesizes a new problem by applying a closure operation — union, intersection,
set difference, complement, or reversal. From *n* base specifications this yields
up to **3·C(n,2) + 2n** structurally distinct problems with no extra authoring.

The derivation engine respects each class's real closure boundaries
(`_CLOSURE_OPS` in `dsl_generator/closure_handler.py`):

| Class | Operations |
|---|---|
| DFA / NFA | union, intersection, difference, complement, reversal |
| TM | union, intersection, difference, complement, reversal |
| **PDA** | **union and reversal only** — context-free languages are not closed under intersection, difference, or complement |

It also implements one cross-class construction: given a regular base question
and a context-free base question over the same alphabet, it derives a **PDA**
problem for L<sub>DFA</sub> ∩ L<sub>PDA</sub>, which is context-free. This case is
capped at 30% of the closure budget (`_CROSS_MACHINE_FRACTION`) so the derived mix
stays representative of all five operations. Operations are weighted so simpler
ones appear more often (`_OP_WEIGHTS`).

Derived questions are backed by a compositional reference construction: Boolean
operations become a product automaton over the two base machines' state sets, and
reversal reverses transitions and swaps the start/accept roles — which keeps
DFA-family closure questions exactly equivalence-checkable through the same
Hopcroft pipeline as base questions.

A specification opts out with `closure_allowed: false` when its combinations
would exceed the intended difficulty ceiling.

## Quality guards

Every instantiated question — base or closure-derived — is checked by four
always-on guards before it is offered to a student. They run in a cheapest-first
cascade that stops at the first failure:

| Guard | Check |
|---|---|
| `require_distinguishable` | no duplicate `(template_id, pattern)` within a session |
| `require_non_empty` | L ≠ ∅ within `max_length` |
| `require_non_trivial` | L ≠ Σ\* — rules out accept-everything machines |
| `require_balanced` | at least 3 ACCEPT and 3 REJECT strings reachable |

They live in `dsl_generator/question_guards.py` as `check_distinguishable`,
`check_non_empty`, `check_non_trivial`, `check_balanced`, and the cascade
`apply_guards(q, seen_patterns)`, which returns the list of failed guard names
and registers the question's pattern only when every guard passes.


## Repository layout

```
dsl_generator/
  lexer.py                  tokenizer, 61 token types
  parser.py                 recursive-descent parser → AST
  ast_nodes.py              25 AST node dataclasses
  template_handler.py       loading, validation, instantiation, NL rendering
  testcase_generator.py     free-variable solver + test-case synthesis
  closure_handler.py        class-aware closure-property derivation
  question_guards.py        the four always-on quality guards
  Ref_DFA_generator.py      reference-DFA construction + Hopcroft minimization
  ref_dfa_extended.py       additional DFA constructions
  ref_dfa_adapter.py        question dict → reference DFA
  templates/                55 .dsl specifications

api/
  main.py                   FastAPI app, CORS, table creation, /health
  db.py                     SQLAlchemy engine + session factory
  models.py                 questions, submissions tables
  schemas.py                Pydantic request/response models
  routers/practice.py       all /practice endpoints
  generator_bridge.py       the seam between dsl_generator and the API
  simulator.py              DFA/NFA simulation, equivalence, scoring
  machine_sim.py            PDA and TM simulators
  simulate_common.py        shared step-by-step simulation response
  practice_access.py        per-session question authorization

frontend/src/
  App.tsx                   routes
  pages/                    PracticePage, PracticeQuestionPage, AutomataViewerPage
  components/               AutomataCanvas, SimulationPanel, StateNode,
                            TransitionEdge, TransitionDialog, …
  api/                      axios client + endpoint wrappers

paper/                      main.tex, main.pdf, references.bib, ACM class files
```

### API endpoints

| Method | Path |
|---|---|
| `GET` | `/health` |
| `POST` | `/practice/session` |
| `POST` | `/practice/generate` |
| `GET` | `/practice/history` |
| `GET` | `/practice/question/{question_id}` |
| `POST` | `/practice/submit/{question_id}` |
| `POST` | `/practice/simulate/{question_id}` |
| `GET` | `/practice/submissions/{question_id}` |

`POST /practice/generate` takes a `practice_user_key`, a `machine`
(`DFA` / `PDA` / `TM`), and either a `difficulty` (`"0"`–`"5"`) or a
`difficulty_tier` (`easy` → 0–2, `medium` → 2–4, `hard` → 4–5, or `any`),
plus an optional `question_style` (`random` / `simple` / `closure`).


## Evaluation

Reported in the paper (§6), measured by requesting five instances per
specification across all 55 specifications plus 20 closure-derived questions
end to end:

| Metric | Value | Notes |
|---|---|---|
| DSL specifications authored | 55 | 17 DFA, 16 PDA, 22 TM |
| Base instances requested | 275 | 5 × 55 specifications |
| Base instances passing all guards | 232 (84.4%) | auto-retried |
| Closure questions requested | 20 | 5 operation types |
| Closure questions produced | 16 (80.0%) | |

Roughly one instance in six is discarded rather than shipped as an empty,
trivial, or duplicate problem.

<!-- ## Citing

```bibtex
@inproceedings{venkatesh2026automatagen,
  author    = {Venkatesh, Nandigama and Siddhartha, Kakaraparthy V N P},
  title     = {AutomataGen: A Domain-Specific Language for On-Demand Generation
               and Closure-Based Expansion of Automata Theory Practice Problems},
  booktitle = {Proceedings of the ACM COMPUTE Conference 2026 (COMPUTE '26)},
  address   = {Amrita Vishwa Vidyapeetham, India},
  year      = {2026},
  publisher = {ACM}
}
``` -->
