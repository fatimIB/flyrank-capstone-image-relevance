"""
FastAPI app entry point — kept small on purpose. Actual endpoint logic
lives in app/routes/; this file just creates the app, does startup
setup, and wires the routers in.

Run: uvicorn app.main:app --reload
Docs (auto-generated): http://localhost:8000/docs
"""

from fastapi import FastAPI

from app.models.database import init_db
from app.routes import api

app = FastAPI(title="AI Image Understanding & Content Matching Engine")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return {"status": "ok", "service": "AI Image Understanding & Content Matching Engine"}


app.include_router(api.router)