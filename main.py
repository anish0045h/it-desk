"""
main.py — FastAPI application entry point for DeskMate.

Endpoints:
  GET  /           → serves the chat UI (static/index.html)
  POST /chat       → main agent endpoint
  GET  /employees  → list available demo employees for the UI dropdown
  GET  /health     → liveness probe
  GET  /logs       → inspect email + IT-notification logs (debug/demo)
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import DeskMateAgent
from mock_data import EMAIL_LOG, EMPLOYEES, IT_NOTIFICATION_LOG, TICKETS

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Lifespan (initialise agent once at startup) ────────────────────────────
agent: DeskMateAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    logger.info("DeskMate starting up …")
    from dotenv import load_dotenv
    load_dotenv()
    try:
        agent = DeskMateAgent()
        logger.info("DeskMate ready.")
    except Exception as e:
        logger.warning("DeskMate agent could not be initialised at startup. Will try lazy initialisation: %s", e)
    yield
    logger.info("DeskMate shutting down.")


# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="DeskMate — AI IT Helpdesk",
    description="POC for Black Box Network Services AI CoE take-home exercise.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (HTML UI)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Pydantic schemas ───────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    employee_id: str | None = Field(default=None, example="emp_001")
    message: str = Field(..., min_length=1, example="I need access to Adobe Creative Suite.")
    conversation_history: list[dict] = Field(
        default_factory=list,
        description="Prior turns in the format [{role, parts}].",
    )


class ChatResponse(BaseModel):
    response: str
    trace: list[dict]
    conversation_history: list[dict]



# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """Serve the chat UI."""
    with open("static/index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/health")
async def health():
    return {"status": "ok", "model": "gemini-3.1-flash-lite"}


@app.get("/employees")
async def list_employees():
    """Return demo employee list for the UI dropdown."""
    return [
        {"id": eid, **info}
        for eid, info in EMPLOYEES.items()
    ]


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Main agent endpoint.

    Accepts a user message and optional conversation history.
    Returns the agent response, full execution trace, and updated history.
    """
    global agent
    if agent is None:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            agent = DeskMateAgent()
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail="Gemini API key is not set. Please set GEMINI_API_KEY in a .env file or environment variables."
            )


    emp_id = req.employee_id
    if emp_id and emp_id not in EMPLOYEES:
        emp_id = None

    logger.info("Chat request | employee=%s | message='%s'", emp_id, req.message[:80])

    result = agent.process(emp_id, req.message, req.conversation_history)

    logger.info(
        "Chat response | employee=%s | trace_steps=%d",
        emp_id,
        len(result["trace"]),
    )


    return ChatResponse(**result)


@app.get("/logs")
async def get_logs():
    """
    Debug endpoint — inspect email and IT-notification logs,
    and the current state of the ticket store.
    """
    return {
        "tickets": TICKETS,
        "email_log": EMAIL_LOG,
        "it_notification_log": IT_NOTIFICATION_LOG,
    }


# ── Dev server ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=True,
        log_level="info",
    )
