# agent.py — DeskMate AI agent (Gemini function-calling loop)

import logging
import os
import time
from google.protobuf.struct_pb2 import Struct

import google.generativeai as genai
import google.ai.generativelanguage as glm
from dotenv import load_dotenv

from mock_data import EMPLOYEES
from tools import TOOL_FUNCTIONS
from db import is_db_configured, get_db_cursor

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are DeskMate, an AI-powered IT helpdesk assistant for internal company employees.

ROLE
Understand natural-language IT requests, decide which tools to use, execute them in
the correct order, and reply with a clear, professional, human-friendly response.

ABSOLUTE RULES
1. Never return raw JSON, internal IDs, or database records to the user.
2. Never hallucinate — every fact must come from a tool result.
3. Refuse any request unrelated to IT helpdesk support.
4. For ticket creation: call create_ticket FIRST, then send_email, then notify_it_team.
5. Always include the ticket ID in your response when a ticket is created.
6. Keep responses concise, professional, and empathetic. End with next steps.
7. Never reveal temporary access codes or tokens to the user — just confirm the reset
   was successful and that instructions have been sent to their registered email.

SUPPORTED REQUEST TYPES
Password resets | Software access checks | VPN status | Ticket creation | Ticket status | General IT questions

TOOL USAGE
- check_entitlement  → always call before creating a software-access ticket. Requires employee_id.
- create_ticket      → then send_email, then notify_it_team. Requires employee_id.
- get_ticket_status  → when user asks about an existing ticket. If not found, reply: "Unable to locate the ticket."
- check_vpn          → any VPN query. Requires employee_id.
- reset_password     → password reset requests. Requires employee_id.
- send_email         → notify employee after ticket creation or password reset.
- notify_it_team     → IT-ops alert after ticket creation.

MISSING INFORMATION
- No employee ID → ask: "Could you please provide your Employee ID (e.g., emp_001)?"
- No software name → ask: "Which software do you need access to?"
- No ticket ID → ask: "Please provide the ticket ID."
- Ambiguous request → ask one focused clarifying question.

OUT OF SCOPE
Reply exactly: "I can assist only with IT helpdesk requests."

ERRORS
If a tool returns an error, do not expose technical details. Reply:
"The service is temporarily unavailable. Please try again later."
"""

MAX_HISTORY_TURNS = 10  # keep last N user pairs to prevent context overflow


class DeskMateAgent:
    """Stateless agent — conversation continuity is managed by the caller via history."""

    MAX_TOOL_ITERATIONS = 10

    def __init__(self, api_key: str | None = None) -> None:
        api_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY is not set.")
        genai.configure(api_key=api_key)
        self.model_name = "gemini-2.0-flash"  # available model
        logger.info("DeskMateAgent ready with %s", self.model_name)

    def process(self, employee_id: str | None, message: str, history: list[dict]) -> dict:
        """
        Process one user turn.

        Args:
            employee_id: caller's employee ID (can be None)
            message:     raw user message
            history:     list of {"role": "user"|"model", "parts": [str]} dicts

        Returns:
            {"response": str, "trace": list[dict], "conversation_history": list[dict]}
        """
        trace: list[dict] = [{"step": "Intent detected", "detail": f'Query: "{message}"'}]

        # ── 1. Resolve employee context ────────────────────────────────────
        employee = self._resolve_employee(employee_id)

        # ── 2. Build enriched user message ─────────────────────────────────
        if employee:
            ctx = (
                f"[Employee context]\n"
                f"Name: {employee['name']} | ID: {employee_id} | "
                f"Department: {employee['department']} | Role: {employee['role']}\n\n"
                f"[Query]\n{message}"
            )
        else:
            ctx = f"[Employee context]\nUnknown — ask for employee_id if a tool call is needed.\n\n[Query]\n{message}"

        # ── 3. Build Gemini history (trim to last N turns) ─────────────────
        trimmed = history[-(MAX_HISTORY_TURNS * 2):]
        gemini_history = [
            glm.Content(role="user" if t["role"] == "user" else "model",
                        parts=[glm.Part(text=p) for p in t.get("parts", [])])
            for t in trimmed
        ]

        # ── 4. Start Gemini chat ───────────────────────────────────────────
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=SYSTEM_PROMPT,
                tools=list(TOOL_FUNCTIONS.values()),
            )
            chat = model.start_chat(history=gemini_history)
            response = self._call_with_retry(lambda: chat.send_message(ctx))
        except Exception as exc:
            logger.error("Gemini initial call failed: %s", exc, exc_info=True)
            return self._error_response(trace, history)

        # ── 5. Tool-call loop ──────────────────────────────────────────────
        for iteration in range(self.MAX_TOOL_ITERATIONS):
            function_parts = self._extract_function_calls(response)
            if not function_parts:
                break

            tool_response_parts = []
            for fc in function_parts:
                name = fc.function_call.name
                args = dict(fc.function_call.args)

                trace.append({"step": "Tool called", "tool": name, "arguments": args, "iteration": iteration + 1})

                try:
                    fn = TOOL_FUNCTIONS.get(name)
                    if fn is None:
                        raise ValueError(f"Unknown tool: {name}")
                    result = fn(**args)
                except Exception as exc:
                    logger.error("Tool '%s' raised: %s", name, exc)
                    result = {"success": False, "error": str(exc)}

                trace.append({"step": "Result", "tool": name, "result": self._safe_result(name, result)})
                tool_response_parts.append(self._build_function_response(name, result))

            try:
                response = self._call_with_retry(lambda: chat.send_message(tool_response_parts))
            except Exception as exc:
                logger.error("Gemini tool-response call failed: %s", exc, exc_info=True)
                return self._error_response(trace, history)

        # ── 6. Extract final text ──────────────────────────────────────────
        final_text = self._extract_text(response) or "I'm sorry, I couldn't generate a response. Please try again."
        trace.append({"step": "Final response", "detail": final_text})

        updated_history = history + [
            {"role": "user",  "parts": [ctx]},
            {"role": "model", "parts": [final_text]},
        ]

        return {"response": final_text, "trace": trace, "conversation_history": updated_history}

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _resolve_employee(self, employee_id: str | None) -> dict | None:
        if not employee_id:
            return None
        if is_db_configured():
            try:
                with get_db_cursor() as cur:
                    cur.execute("SELECT name, department, role FROM employees WHERE id = %s", (employee_id,))
                    row = cur.fetchone()
                    if row:
                        return dict(row)
            except Exception as e:
                logger.warning("DB employee lookup failed: %s", e)
        return EMPLOYEES.get(employee_id)

    @staticmethod
    def _extract_function_calls(response) -> list:
        try:
            return [p for p in response.candidates[0].content.parts if p.function_call]
        except (IndexError, AttributeError):
            return []

    @staticmethod
    def _extract_text(response) -> str:
        try:
            return "".join(p.text for p in response.candidates[0].content.parts if p.text).strip()
        except (IndexError, AttributeError):
            return ""

    @staticmethod
    def _build_function_response(name: str, result: dict):
        s = Struct()
        s.update(result)
        return glm.Part(function_response=glm.FunctionResponse(name=name, response=s))

    @staticmethod
    def _safe_result(tool_name: str, result: dict) -> dict:
        """Strip sensitive fields from the trace (never log temp tokens)."""
        safe = dict(result)
        safe.pop("temp_access_code", None)
        safe.pop("token", None)
        return safe

    @staticmethod
    def _call_with_retry(fn, retries: int = 3, delay: float = 1.0):
        for attempt in range(retries + 1):
            try:
                return fn()
            except Exception as exc:
                transient = any(s in str(exc) for s in ("503", "500", "429", "UNAVAILABLE", "ResourceExhausted"))
                if transient and attempt < retries:
                    logger.warning("Transient Gemini error (attempt %d/%d), retrying in %.1fs...", attempt + 1, retries, delay)
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise

    @staticmethod
    def _error_response(trace: list, history: list) -> dict:
        msg = "The service is temporarily unavailable. Please try again later."
        trace.append({"step": "Final response", "detail": msg})
        return {"response": msg, "trace": trace, "conversation_history": history}
