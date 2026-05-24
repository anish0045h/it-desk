# DeskMate – Design Notes

## 1. LLM Selection: Gemini Function Calling

I used Gemini as the core LLM because it supports function calling. Instead of returning static responses, the model can decide which internal operation needs to be executed.

Reason:
- Supports multi-step workflows
- Converts natural language into actions
- Reduces hardcoded logic

Example:

User:
"I need access to Adobe Creative Suite. If I am not entitled, raise a ticket."

Workflow:

check_entitlement()
→ create_ticket()
→ send_email()
→ notify_it_team()

---

## 2. Tool-Based Design

Business operations are separated into independent tools:

- check_entitlement()
- create_ticket()
- check_vpn()
- reset_password()
- get_ticket_status()
- send_email()
- notify_it_team()

Reason:

Separating AI reasoning from business logic makes the system easier to maintain, test, and extend.

---

## 3. PostgreSQL + Mock Fallback

PostgreSQL is used as the primary persistent database.

Stored data:

- Employees
- Tickets
- VPN status
- Email logs
- Password reset logs
- Notification logs

Mock data acts as a fallback when the database is unavailable.

Reason:

- Allows development without infrastructure dependency
- Supports offline testing
- Improves resilience

---

## 4. Observable Execution

Every request generates a trace containing:

- User intent
- Tool calls
- Tool outputs
- Final response

Reason:

Makes debugging easier and provides transparency into the system workflow.

---

## 5. Error Handling

The system handles:

- Missing employee IDs
- Invalid ticket IDs
- Missing information
- Out-of-scope requests
- Internal system failures

Reason:

Prevent technical errors from being exposed directly to users.

---

## Trade-offs

For this POC, some production features were intentionally simplified:

- No JWT authentication
- No rate limiting
- Basic ticket ID generation
- No asynchronous processing

The focus was on demonstrating AI orchestration and system behavior.
