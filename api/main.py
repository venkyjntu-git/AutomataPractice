"""
api/main.py — FastAPI application entry point (practice-only).

Run with:
    uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.db import engine, Base
from api.routers import practice

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AutomataGen Practice API", version="1.0.0")

# Allow the React dev server (port 5173) and production build
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(practice.router)


@app.get("/health")
def health():
    return {"status": "ok"}
