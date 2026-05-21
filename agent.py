import json
import logging
import os
import re
import time

from dotenv import load_dotenv
import google.generativeai as genai
import google.ai.generativelanguage as glm

from mock_data import EMPLOYEES
from tools import TOOL_FUNCTIONS
from db import is_db_configured, get_db_cursor

logger = logging.getLogger(__name__)

# Load local .env file
load_dotenv()

# ── System prompt ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are DeskMate, an AI-powered IT helpdesk assistant for internal company employees.

ROLE
You understand natural-language IT requests, decide which internal tools to use,
execute them in the right order, reason on the results, and reply with a clear,
professional, human-friendly response.

ABSOLUTE RULES
1. Never return raw database records, internal IDs, or JSON blobs to the user.
2. Never hallucinate information — every fact in your reply must come from a tool result.
3. Refuse any request that is not related to IT helpdesk support.
4. For ticket creation: always call create_ticket FIRST, then send_email to the employee,
   then notify_it_team. Do all three before composing your reply.
5. When a ticket is created always include the ticket ID in your response.
6. Keep responses concise, professional, and empathetic. End with next steps.

SUPPORTED REQUEST TYPES
1. Password resets
2. Software access / entitlement checks
3. VPN status and provisioning
4. Ticket creation
5. Ticket status checks
6. General IT questions

TOOL USAGE GUIDE
• check_entitlement  — always call this before creating a software-access ticket. Requires employee_id.
• create_ticket      — create ticket, then send_email, then notify_it_team. Requires employee_id.
• get_ticket_status  — use when the user asks about an existing ticket. If the ticket is not found in the database, reply exactly: "Unable to locate the ticket."
• check_vpn          — use for any VPN-related query. Requires employee_id.
• reset_password     — use for password-reset requests. Requires employee_id.
• send_email         — employee notification after ticket creation or password reset. Subject format: "Ticket Created: {ticket_id}".
• notify_it_team     — IT-ops alert after ticket creation.

HANDLING MISSING INFORMATION
• If the employee ID is missing or unknown → Ask the user to provide their Employee ID (e.g., "Could you please provide your Employee ID?"). Do not invoke any tools requiring an employee_id parameter until it is known.
• If software name is not specified → ask: "Please specify the software you need access to."
• If ticket ID is missing           → ask: "Please provide the ticket ID."
• If request is ambiguous           → ask one focused clarifying question.

OUT-OF-SCOPE REQUESTS
If the query is out of scope or unrelated to IT, reply exactly: "I can assist only with IT helpdesk requests."

INTERNAL ERRORS
If a tool returns an error field or there is an exception, do NOT expose technical details. Reply:
"The service is temporarily unavailable. Please try again later."
"""

# ── Agent class ─────────────────────────────────────────────────────────────

class DeskMateAgent:
    """
    Stateless agent: each call to process() is self-contained.
    Conversation continuity is maintained by the caller passing history in/out.
    """

    MAX_TOOL_ITERATIONS = 10

    def __init__(self, api_key: str | None = None) -> None:
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY environment variable is not set.")

        genai.configure(api_key=api_key)
        self.model = "gemini-3.1-flash-lite"
        self.system_prompt = SYSTEM_PROMPT
        logger.info(f"DeskMateAgent initialised with {self.model} using Google Generative AI SDK")

    # ── Public entry point ────────────────────────────────────────────────

    def process(self, employee_id: str | None, message: str, history: list[dict]) -> dict:
        """
        Process one user turn.

        Args:
            employee_id : caller's employee ID (can be None)
            message     : raw user message
            history     : list of {"role": "user"|"model", "parts": [str]} dicts

        Returns:
            {
                "response":             str,
                "trace":                list[dict],
                "conversation_history": list[dict],
            }
        """
        trace: list[dict] = []

        def _execute_with_retry(api_call_fn, max_retries=3, initial_delay=1.0):
            delay = initial_delay
            for attempt in range(max_retries + 1):
                try:
                    return api_call_fn()
                except Exception as exc:
                    exc_str = str(exc)
                    is_transient = any(status in exc_str for status in ("503", "500", "429", "UNAVAILABLE", "ResourceExhausted", "high demand"))
                    if is_transient and attempt < max_retries:
                        logger.warning(
                            "Gemini API returned transient error (attempt %d/%d). Retrying in %.1fs... Error: %s",
                            attempt + 1, max_retries + 1, delay, exc_str
                        )
                        time.sleep(delay)
                        delay *= 2
                    else:
                        raise exc

        trace.append({
            "step": "Intent detected",
            "detail": f"Query: \"{message}\"",
        })

        # ── 1. Resolve employee context ───────────────────────────────────
        employee = None
        if employee_id:
            if is_db_configured():
                try:
                    with get_db_cursor() as cur:
                        cur.execute("SELECT name, department, role FROM employees WHERE id = %s", (employee_id,))
                        employee = cur.fetchone()
                except Exception as e:
                    logger.error("DB employee query error in agent: %s", e)
            
            if not employee:
                employee = EMPLOYEES.get(employee_id)

        # ── 2. Build context-enriched prompt ─────────────────────────────
        if employee:
            enriched_message = (
                f"[Employee context]\n"
                f"Name      : {employee['name']}\n"
                f"ID        : {employee_id}\n"
                f"Department: {employee['department']}\n"
                f"Role      : {employee['role']}\n\n"
                f"[Employee query]\n{message}"
            )
        else:
            enriched_message = (
                f"[Employee context]\n"
                f"Unknown Employee (Please ask for employee_id if a tool call is needed)\n\n"
                f"[Employee query]\n{message}"
            )

        # Convert simple list[dict] history to Gemini chat history
        gemini_history = []
        for turn in history:
            role = "user" if turn.get("role") == "user" else "model"
            parts = [{"text": part} for part in turn.get("parts", [])]
            gemini_history.append(
                glm.Content(role=role, parts=parts)
            )

        # ── 3. Start Gemini chat ───────────────────────────────────────
        try:
            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=self.system_prompt,
                tools=list(TOOL_FUNCTIONS.values())
            )
            chat = model.start_chat(history=gemini_history)
            response = _execute_with_retry(lambda: chat.send_message(enriched_message))
        except Exception as exc:
            logger.error("Gemini initial completion failed: %s", exc, exc_info=True)
            return self._error_response(
                "The service is temporarily unavailable. Please try again later.",
                trace,
                history,
            )

        # ── 4. Tool-call loop ─────────────────────────────────────────────
        for iteration in range(self.MAX_TOOL_ITERATIONS):
            has_function_calls = False
            parts_to_send = []

            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        has_function_calls = True
                        name = part.function_call.name
                        try:
                            args = dict(part.function_call.args)
                        except Exception as e:
                            logger.error("Failed to parse function arguments: %s", e)
                            args = {}

                        trace.append({
                            "step": "Tool called",
                            "tool": name,
                            "arguments": args,
                            "iteration": iteration + 1,
                        })

                        try:
                            tool_fn = TOOL_FUNCTIONS.get(name)
                            if tool_fn is None:
                                raise ValueError(f"Unknown tool: {name}")
                            result = tool_fn(**args)
                        except Exception as exc:
                            logger.error("Tool '%s' error: %s", name, exc, exc_info=True)
                            result = {"success": False, "error": str(exc)}

                        trace.append({
                            "step": "Result",
                            "tool": name,
                            "result": result,
                        })

                        # Log Action Performed
                        if result.get("success"):
                            if name == "create_ticket":
                                trace.append({
                                    "step": "Action performed",
                                    "detail": f"Created ticket {result.get('ticket_id')} for {result.get('employee_name')} (Assigned: {result.get('assigned_team')})"
                                })
                            elif name == "reset_password":
                                trace.append({
                                    "step": "Action performed",
                                    "detail": f"Reset password for {result.get('employee_name')}. Code generated: {result.get('temp_access_code')}"
                                })
                            elif name == "check_entitlement":
                                ent = "entitled" if result.get("entitled") else "not entitled"
                                trace.append({
                                    "step": "Action performed",
                                    "detail": f"Checked entitlements for {result.get('employee_name')}: {ent} to {result.get('canonical_name')}"
                                })
                            elif name == "check_vpn":
                                trace.append({
                                    "step": "Action performed",
                                    "detail": f"Checked VPN status for {result.get('employee_name')}: {result.get('vpn_status')}"
                                })
                            elif name == "get_ticket_status":
                                trace.append({
                                    "step": "Action performed",
                                    "detail": f"Retrieved status of ticket {result.get('ticket_id')}: {result.get('status')}"
                                })

                        # Log Notifications Sent
                        if result.get("success"):
                            if name == "send_email":
                                trace.append({
                                    "step": "Notifications sent",
                                    "detail": f"Email notification sent to {result.get('to')} with subject: '{result.get('subject')}'"
                                })
                            elif name == "notify_it_team":
                                trace.append({
                                    "step": "Notifications sent",
                                    "detail": f"IT operations alert sent for ticket {result.get('ticket_id')} on channel {result.get('channel')}"
                                })

                        # Construct a FunctionResponse part
                        from google.protobuf.struct_pb2 import Struct
                        resp_struct = Struct()
                        resp_struct.update(result)

                        function_response_part = glm.Part(
                            function_response=glm.FunctionResponse(
                                name=name,
                                response=resp_struct
                            )
                        )
                        parts_to_send.append(function_response_part)

            if not has_function_calls:
                break

            # Send all tool results back to Gemini
            try:
                response = _execute_with_retry(lambda: chat.send_message(parts_to_send))
            except Exception as exc:
                logger.error("Gemini tool-response completion failed: %s", exc, exc_info=True)
                return self._error_response(
                    "The service is temporarily unavailable. Please try again later.",
                    trace,
                    history,
                )

        # ── 5. Extract final text ─────────────────────────────────────────
        final_text = ""
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            parts = response.candidates[0].content.parts
            final_text = "".join(part.text for part in parts if part.text)
        final_text = final_text.strip()

        if not final_text:
            final_text = (
                "I'm sorry, I couldn't generate a response. "
                "Please try rephrasing your request."
            )

        # If it contains ticket not found error, replace with standard "Unable to locate the ticket."
        if "ticket '" in final_text.lower() and "not found" in final_text.lower() and "unable to locate" not in final_text.lower():
            final_text = "Unable to locate the ticket."

        trace.append({
            "step": "Final response",
            "detail": final_text,
        })

        # ── 6. Update conversation history (text turns only) ──────────────
        updated_history = history + [
            {"role": "user",  "parts": [enriched_message]},
            {"role": "model", "parts": [final_text]},
        ]

        return {
            "response": final_text,
            "trace": trace,
            "conversation_history": updated_history,
        }

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _error_response(message: str, trace: list, history: list) -> dict:
        trace.append({"step": "Final response", "detail": message})
        return {
            "response": message,
            "trace": trace,
            "conversation_history": history,
        }
