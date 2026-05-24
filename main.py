# main.py — FastAPI entry point for DeskMate

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agent import DeskMateAgent
from mock_data import EMPLOYEES, EMAIL_LOG, IT_NOTIFICATION_LOG, TICKETS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

# ── Optional API key auth (set API_KEY env var to enable) ─────────────────────
API_KEY = os.environ.get("API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_key(key: str = Security(api_key_header)):
    if API_KEY and key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key.")

# ── Lifespan ───────────────────────────────────────────────────────────────────
_agent: DeskMateAgent | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    try:
        _agent = DeskMateAgent()
        logger.info("DeskMate agent initialised.")
    except Exception as e:
        logger.warning("Agent startup failed (will retry on first request): %s", e)
    yield
    logger.info("DeskMate shutting down.")

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="DeskMate — AI IT Helpdesk", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Schemas ────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    employee_id: str | None = Field(default=None, example="emp_001")
    message: str = Field(..., min_length=1, max_length=2000, example="I need access to Adobe Creative Suite.")
    conversation_history: list[dict] = Field(default_factory=list)

class ChatResponse(BaseModel):
    response: str
    trace: list[dict]
    conversation_history: list[dict]

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    with open("static/index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/health")
async def health():
    return {"status": "ok", "model": "gemini-1.5-flash"}

@app.get("/employees")
async def list_employees():
    return [{"id": eid, **info} for eid, info in EMPLOYEES.items()]

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, _: None = Security(verify_key)):
    global _agent
    if _agent is None:
        try:
            _agent = DeskMateAgent()
        except Exception:
            raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not set or invalid.")

    emp_id = req.employee_id if req.employee_id in EMPLOYEES else None
    logger.info("Chat | emp=%s | msg='%s'", emp_id, req.message[:80])

    result = _agent.process(emp_id, req.message, req.conversation_history)
    return ChatResponse(**result)

@app.get("/logs", dependencies=[Security(verify_key)])
async def get_logs():
    """Debug endpoint — inspect in-memory logs and ticket store."""
    return {"tickets": TICKETS, "email_log": EMAIL_LOG, "it_notification_log": IT_NOTIFICATION_LOG}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
