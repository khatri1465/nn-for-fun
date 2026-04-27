import uuid
import os
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from dotenv import load_dotenv

from database import Session, Message, get_db, init_db, DEFAULT_TOKEN_BUDGET
from llm_clients import call_llm, get_available_models, MODELS

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="LLM Aggregator", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Schemas ---

class CreateSessionResponse(BaseModel):
    session_id: str
    token_budget: int
    tokens_used: int
    tokens_remaining: int


class SessionInfoResponse(BaseModel):
    session_id: str
    token_budget: int
    tokens_used: int
    tokens_remaining: int


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    session_id: str
    model: str
    messages: list[ChatMessage]
    system_prompt: Optional[str] = None
    max_tokens: int = 2048


class ChatResponse(BaseModel):
    reply: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    tokens_remaining: int


class HistoryMessage(BaseModel):
    role: str
    content: str
    model: Optional[str]
    tokens_used: int
    created_at: str


# --- Routes ---

@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.post("/api/sessions", response_model=CreateSessionResponse)
def create_session(db: DBSession = Depends(get_db)):
    session = Session(id=str(uuid.uuid4()), token_budget=DEFAULT_TOKEN_BUDGET, tokens_used=0)
    db.add(session)
    db.commit()
    db.refresh(session)
    return CreateSessionResponse(
        session_id=session.id,
        token_budget=session.token_budget,
        tokens_used=session.tokens_used,
        tokens_remaining=session.token_budget - session.tokens_used,
    )


@app.get("/api/sessions/{session_id}", response_model=SessionInfoResponse)
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionInfoResponse(
        session_id=session.id,
        token_budget=session.token_budget,
        tokens_used=session.tokens_used,
        tokens_remaining=session.token_budget - session.tokens_used,
    )


@app.get("/api/models")
def list_models():
    return get_available_models()


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    tokens_remaining = session.token_budget - session.tokens_used
    if tokens_remaining <= 0:
        raise HTTPException(status_code=402, detail="Token budget exhausted")

    if req.model not in MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model: {req.model}")

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    try:
        llm_response = call_llm(
            model_id=req.model,
            messages=messages,
            system_prompt=req.system_prompt,
            max_tokens=min(req.max_tokens, tokens_remaining),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")

    # Deduct tokens
    session.tokens_used += llm_response.total_tokens
    db.commit()

    # Persist assistant message
    db.add(Message(
        session_id=session.id,
        role="assistant",
        content=llm_response.content,
        model=req.model,
        tokens_used=llm_response.total_tokens,
    ))
    db.commit()

    return ChatResponse(
        reply=llm_response.content,
        model=req.model,
        input_tokens=llm_response.input_tokens,
        output_tokens=llm_response.output_tokens,
        total_tokens=llm_response.total_tokens,
        tokens_remaining=session.token_budget - session.tokens_used,
    )


@app.get("/api/history/{session_id}", response_model=list[HistoryMessage])
def get_history(session_id: str, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at)
        .all()
    )
    return [
        HistoryMessage(
            role=m.role,
            content=m.content,
            model=m.model,
            tokens_used=m.tokens_used,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]
