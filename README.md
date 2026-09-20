# AutomataGen — Practice

This folder is a standalone, self-contained extract of the AutomataGen
practice workflow: on-demand automata question generation and the anonymous
`/practice` self-check UI, as described in the accepted paper (see the
top-level `paper/` directory in the main repository).

It does **not** include the faculty/instructor auto-grading system
(authentication, roll-number assignment sets, submission history/grading for
enrolled students) — that is a separate, unpublished part of the project.

## Contents

- `dsl_generator/` — the DSL compiler and question-generation engine
  (lexer → parser → AST → template instantiation), closure-property
  generation, and reference-DFA construction.
- `api/` — a FastAPI backend exposing only the practice endpoints
  (`/practice/session`, `/practice/generate`, `/practice/question/{id}`,
  `/practice/submit/{id}`, `/practice/simulate/{id}`, `/practice/history`,
  `/practice/submissions/{id}`).
- `frontend/` — a Vite + React + TypeScript SPA with the practice picker,
  the construction canvas, and step-by-step simulation.

## Known gap

The paper describes four automatic quality guards (distinguishability,
non-emptiness, non-triviality, balance) implemented in
`dsl_generator/question_guards.py`. That module is included here, but the
live `/practice/generate` path does not currently call it — this is a
pre-existing gap between the paper description and the deployed pipeline,
not something introduced by this extraction.

## Running locally

### Backend

```bash
cd api
python -m venv ../venv
../venv/Scripts/activate   # or: source ../venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cd ..
cp .env.example .env       # defaults to a local sqlite file
uvicorn api.main:app --reload --port 8000
```

The app creates its tables (`questions`, `submissions`) automatically on
startup via `Base.metadata.create_all()` — no migrations needed for a fresh
database. Set `DATABASE_URL` in `.env` to a Postgres URL (see
`docker-compose.yml` for a local Postgres container) to use Postgres
instead of sqlite.

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

The dev server expects the API at `http://localhost:8000` (see
`frontend/src/api/client.ts`). Open `http://localhost:5173/practice`.

## License

MIT — see `LICENSE`.
