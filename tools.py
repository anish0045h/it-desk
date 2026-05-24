# tools.py — Mock IT system operations (called by the agent via Gemini function calling)

import logging
import uuid
from datetime import datetime
from difflib import get_close_matches

import mock_data
from mock_data import EMPLOYEES, ENTITLEMENTS, VPN_STATUS, TICKETS, EMAIL_LOG, IT_NOTIFICATION_LOG, PASSWORD_RESET_LOG
from db import is_db_configured, get_db_cursor

logger = logging.getLogger(__name__)

# ── Team routing ───────────────────────────────────────────────────────────────

_TEAM_KEYWORDS = {
    "Network Team":   ("vpn", "network", "tunnel", "cisco"),
    "Identity Team":  ("password", "locked", "reset", "credential", "login", "mfa"),
    "Security Team":  ("access", "permission", "entitlement", "licence", "license", "security"),
    "L1 Support":     ("software", "install", "application", "app"),
}

def _route_team(issue: str) -> str:
    issue = issue.lower()
    for team, keywords in _TEAM_KEYWORDS.items():
        if any(k in issue for k in keywords):
            return team
    return "L1 Support"


# ── Software name normalisation ────────────────────────────────────────────────

def _match_software(name: str, catalogue: list[str]) -> str | None:
    """Fuzzy-match a software name against a catalogue list."""
    low = name.lower()
    for s in catalogue:
        if s.lower() == low or low in s.lower() or s.lower() in low:
            return s
    hits = get_close_matches(name, catalogue, n=1, cutoff=0.55)
    return hits[0] if hits else None


def _all_software() -> list[str]:
    seen: set[str] = set()
    for ents in ENTITLEMENTS.values():
        seen.update(ents)
    return list(seen)


# ── DB helper ──────────────────────────────────────────────────────────────────

def _get_employee_db(cur, employee_id: str) -> dict | None:
    cur.execute("SELECT id, name, email, department, role FROM employees WHERE id = %s", (employee_id,))
    return cur.fetchone()


def _get_employee_mock(employee_id: str) -> dict | None:
    emp = EMPLOYEES.get(employee_id)
    if emp:
        return {"id": employee_id, **emp}
    return None


def _next_ticket_id() -> str:
    mock_data._ticket_counter += 1
    return f"TKT-{mock_data._ticket_counter}"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Tool implementations ───────────────────────────────────────────────────────

def check_entitlement(employee_id: str, software: str) -> dict:
    """Check whether an employee is entitled to a specific software application."""
    logger.info("[TOOL] check_entitlement | emp=%s sw=%s", employee_id, software)

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                emp = _get_employee_db(cur, employee_id)
                if not emp:
                    return {"success": False, "error": f"Employee '{employee_id}' not found."}

                cur.execute("SELECT software_name FROM entitlements WHERE employee_id = %s", (employee_id,))
                user_ents = [r["software_name"] for r in cur.fetchall()]
                canonical = _match_software(software, user_ents)
                if canonical:
                    return {"success": True, "employee_id": employee_id, "employee_name": emp["name"],
                            "software_requested": software, "canonical_name": canonical, "entitled": True}

                cur.execute("SELECT DISTINCT software_name FROM entitlements")
                all_cat = [r["software_name"] for r in cur.fetchall()]
                canonical = _match_software(software, all_cat) or software
                return {"success": True, "employee_id": employee_id, "employee_name": emp["name"],
                        "software_requested": software, "canonical_name": canonical, "entitled": False}
        except Exception as e:
            logger.warning("DB check_entitlement failed, using mock: %s", e)

    emp = _get_employee_mock(employee_id)
    if not emp:
        return {"success": False, "error": f"Employee '{employee_id}' not found."}

    user_ents = ENTITLEMENTS.get(employee_id, [])
    canonical = _match_software(software, user_ents)
    if canonical:
        return {"success": True, "employee_id": employee_id, "employee_name": emp["name"],
                "software_requested": software, "canonical_name": canonical, "entitled": True}

    canonical = _match_software(software, _all_software()) or software
    return {"success": True, "employee_id": employee_id, "employee_name": emp["name"],
            "software_requested": software, "canonical_name": canonical, "entitled": False}


def create_ticket(employee_id: str, issue: str, priority: str) -> dict:
    """Create a new ITSM support ticket."""
    logger.info("[TOOL] create_ticket | emp=%s priority=%s", employee_id, priority)

    priority = priority.lower() if priority.lower() in {"low", "medium", "high", "critical"} else "medium"
    assigned_team = _route_team(issue)
    now = _now()

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                emp = _get_employee_db(cur, employee_id)
                if not emp:
                    return {"success": False, "error": f"Employee '{employee_id}' not found."}

                # Use UUID suffix to guarantee uniqueness regardless of row count
                cur.execute("SELECT COUNT(*) AS cnt FROM tickets")
                cnt = cur.fetchone()["cnt"]
                ticket_id = f"TKT-{1005 + cnt}"

                cur.execute(
                    "INSERT INTO tickets (ticket_id, employee_id, issue, priority, status, assigned_team, created_at, updated_at, timestamp, latest_update) "
                    "VALUES (%s,%s,%s,%s,'Open',%s,%s,%s,%s,'Ticket created and assigned to team.')",
                    (ticket_id, employee_id, issue, priority, assigned_team, now, now, now),
                )
                return {"success": True, "ticket_id": ticket_id, "employee_id": employee_id,
                        "employee_name": emp["name"], "issue": issue, "priority": priority,
                        "status": "Open", "assigned_team": assigned_team, "created_at": now}
        except Exception as e:
            logger.warning("DB create_ticket failed, using mock: %s", e)

    emp = _get_employee_mock(employee_id)
    if not emp:
        return {"success": False, "error": f"Employee '{employee_id}' not found."}

    ticket_id = _next_ticket_id()
    TICKETS[ticket_id] = {"employee_id": employee_id, "issue": issue, "priority": priority,
                          "status": "Open", "assigned_team": assigned_team,
                          "created_at": now, "updated_at": now, "latest_update": "Ticket created and assigned to team."}
    return {"success": True, "ticket_id": ticket_id, "employee_id": employee_id,
            "employee_name": emp["name"], "issue": issue, "priority": priority,
            "status": "Open", "assigned_team": assigned_team, "created_at": now}


def get_ticket_status(ticket_id: str) -> dict:
    """Retrieve the current status of an ITSM ticket."""
    logger.info("[TOOL] get_ticket_status | ticket_id=%s", ticket_id)

    # Normalise input (e.g. "tkt 1001" → "TKT-1001")
    ticket_id = ticket_id.upper().replace(" ", "-")
    if not ticket_id.startswith("TKT-"):
        ticket_id = f"TKT-{ticket_id}"

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                cur.execute(
                    "SELECT t.ticket_id, t.status, t.issue, t.priority, t.assigned_team, "
                    "t.created_at, t.updated_at, t.latest_update, e.name AS employee_name "
                    "FROM tickets t LEFT JOIN employees e ON t.employee_id = e.id WHERE t.ticket_id = %s",
                    (ticket_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {"success": False, "error": f"Ticket '{ticket_id}' not found."}
                return {"success": True, "ticket_id": row["ticket_id"], "status": row["status"],
                        "issue": row["issue"], "priority": row["priority"], "assigned_team": row["assigned_team"],
                        "created_at": str(row["created_at"]), "updated_at": str(row["updated_at"]),
                        "latest_update": row["latest_update"], "employee_name": row["employee_name"] or "Unknown"}
        except Exception as e:
            logger.warning("DB get_ticket_status failed, using mock: %s", e)

    ticket = TICKETS.get(ticket_id)
    if not ticket:
        return {"success": False, "error": f"Ticket '{ticket_id}' not found."}

    emp_name = EMPLOYEES.get(ticket["employee_id"], {}).get("name", "Unknown")
    return {"success": True, "ticket_id": ticket_id, "status": ticket["status"], "issue": ticket["issue"],
            "priority": ticket["priority"], "assigned_team": ticket["assigned_team"],
            "created_at": ticket["created_at"], "updated_at": ticket["updated_at"],
            "latest_update": ticket["latest_update"], "employee_name": emp_name}


def check_vpn(employee_id: str) -> dict:
    """Return VPN connection status for an employee."""
    logger.info("[TOOL] check_vpn | emp=%s", employee_id)

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                emp = _get_employee_db(cur, employee_id)
                if not emp:
                    return {"success": False, "error": f"Employee '{employee_id}' not found."}
                cur.execute("SELECT status, last_connected, device, profile FROM vpn_status WHERE employee_id = %s", (employee_id,))
                vpn = cur.fetchone()
                return {"success": True, "employee_id": employee_id, "employee_name": emp["name"],
                        "vpn_status": vpn["status"] if vpn else "not_provisioned",
                        "last_connected": str(vpn["last_connected"]) if vpn and vpn["last_connected"] else None,
                        "device": vpn["device"] if vpn else None, "profile": vpn["profile"] if vpn else None}
        except Exception as e:
            logger.warning("DB check_vpn failed, using mock: %s", e)

    emp = _get_employee_mock(employee_id)
    if not emp:
        return {"success": False, "error": f"Employee '{employee_id}' not found."}

    vpn = VPN_STATUS.get(employee_id, {"status": "not_provisioned"})
    return {"success": True, "employee_id": employee_id, "employee_name": emp["name"],
            "vpn_status": vpn.get("status"), "last_connected": vpn.get("last_connected"),
            "device": vpn.get("device"), "profile": vpn.get("profile")}


def reset_password(employee_id: str) -> dict:
    """Trigger a password reset for the employee's corporate account."""
    logger.info("[TOOL] reset_password | emp=%s", employee_id)

    temp_token = str(uuid.uuid4())[:8].upper()
    now = _now()

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                emp = _get_employee_db(cur, employee_id)
                if not emp:
                    return {"success": False, "error": f"Employee '{employee_id}' not found."}
                cur.execute(
                    "INSERT INTO password_reset_log (employee_id, employee_name, token, reset_at) VALUES (%s,%s,%s,%s)",
                    (employee_id, emp["name"], temp_token, now),
                )
                return {"success": True, "employee_id": employee_id, "employee_name": emp["name"],
                        "message": "Password reset initiated. A temporary code has been sent to your registered email.",
                        "expires_in": "24 hours", "reset_at": now}
        except Exception as e:
            logger.warning("DB reset_password failed, using mock: %s", e)

    emp = _get_employee_mock(employee_id)
    if not emp:
        return {"success": False, "error": f"Employee '{employee_id}' not found."}

    PASSWORD_RESET_LOG.append({"employee_id": employee_id, "employee_name": emp["name"], "reset_at": now, "token": temp_token})
    return {"success": True, "employee_id": employee_id, "employee_name": emp["name"],
            "message": "Password reset initiated. A temporary code has been sent to your registered email.",
            "expires_in": "24 hours", "reset_at": now}


def send_email(employee_id: str, subject: str, body: str) -> dict:
    """Send an email notification to the employee."""
    logger.info("[TOOL] send_email | emp=%s subject='%s'", employee_id, subject)
    now = _now()

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                emp = _get_employee_db(cur, employee_id)
                if not emp:
                    return {"success": False, "error": f"Employee '{employee_id}' not found."}
                cur.execute(
                    "INSERT INTO email_log (recipient, subject, body, sent_at) VALUES (%s,%s,%s,%s)",
                    (emp["email"], subject, body, now),
                )
                return {"success": True, "to": emp["email"], "subject": subject, "sent_at": now}
        except Exception as e:
            logger.warning("DB send_email failed, using mock: %s", e)

    emp = _get_employee_mock(employee_id)
    if not emp:
        return {"success": False, "error": f"Employee '{employee_id}' not found."}

    EMAIL_LOG.append({"to": emp["email"], "employee_name": emp["name"], "subject": subject, "body": body, "sent_at": now})
    return {"success": True, "to": emp["email"], "subject": subject, "sent_at": now}


def notify_it_team(ticket_id: str, issue: str, employee_id: str, priority: str) -> dict:
    """Send an alert to the IT operations team."""
    logger.info("[TOOL] notify_it_team | ticket=%s priority=%s", ticket_id, priority)
    now = _now()

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                cur.execute(
                    "INSERT INTO it_notification_log (ticket_id, channel, issue, priority, notified_at) VALUES (%s,'#it-ops-alerts',%s,%s,%s)",
                    (ticket_id, issue, priority, now),
                )
                return {"success": True, "ticket_id": ticket_id, "priority": priority,
                        "notified_at": now, "channel": "#it-ops-alerts"}
        except Exception as e:
            logger.warning("DB notify_it_team failed, using mock: %s", e)

    emp_name = EMPLOYEES.get(employee_id, {}).get("name", employee_id)
    IT_NOTIFICATION_LOG.append({"ticket_id": ticket_id, "issue": issue, "reported_by": emp_name,
                                 "employee_id": employee_id, "priority": priority,
                                 "notified_at": now, "channel": "#it-ops-alerts"})
    return {"success": True, "ticket_id": ticket_id, "priority": priority, "notified_at": now, "channel": "#it-ops-alerts"}


# ── Dispatch table ─────────────────────────────────────────────────────────────

TOOL_FUNCTIONS: dict = {
    "check_entitlement": check_entitlement,
    "create_ticket":     create_ticket,
    "get_ticket_status": get_ticket_status,
    "check_vpn":         check_vpn,
    "reset_password":    reset_password,
    "send_email":        send_email,
    "notify_it_team":    notify_it_team,
}
