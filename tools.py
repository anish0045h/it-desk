"""
tools.py — Mock implementations of internal IT system operations.

Each function simulates a call to a real internal system:
  check_entitlement  → Identity / Software catalogue service
  create_ticket      → ITSM (e.g. ServiceNow)
  get_ticket_status  → ITSM read
  check_vpn          → Network provisioning service
  reset_password     → Identity / AD service
  send_email         → Internal mail relay
  notify_it_team     → IT ops notification channel (e.g. Teams / PagerDuty)

All functions return plain dicts so results are trivially JSON-serialisable.
"""

import logging
import uuid
from datetime import datetime
from difflib import get_close_matches

import mock_data
from mock_data import (
    EMPLOYEES,
    ENTITLEMENTS,
    VPN_STATUS,
    TICKETS,
    EMAIL_LOG,
    IT_NOTIFICATION_LOG,
    PASSWORD_RESET_LOG,
)
from db import is_db_configured, get_db_cursor

logger = logging.getLogger(__name__)

# ── Team routing rules ─────────────────────────────────────────────────────
TEAM_ROUTING: dict[str, str] = {
    "software": "L1 Support",
    "vpn": "Network Team",
    "password": "Identity Team",
    "access": "Security Team",
    "general": "L1 Support",
}


def _normalize_software_with_list(software: str, software_list: list[str]) -> str | None:
    """
    Match the requested software name against a list of software catalogue items.
    """
    sw_lower = software.lower()
    # 1. Exact match
    for s in software_list:
        if s.lower() == sw_lower:
            return s
    # 2. Substring match
    for s in software_list:
        if sw_lower in s.lower() or s.lower() in sw_lower:
            return s
    # 3. Fuzzy match
    matches = get_close_matches(software, list(software_list), n=1, cutoff=0.55)
    return matches[0] if matches else None


def _normalize_software(software: str) -> str | None:
    """
    Match the requested software name against the known mock catalogue.
    """
    all_software: set[str] = set()
    for entitlements in ENTITLEMENTS.values():
        all_software.update(entitlements)
    return _normalize_software_with_list(software, list(all_software))


def _route_team(issue_lower: str) -> str:
    if any(k in issue_lower for k in ("vpn", "network", "tunnel", "cisco")):
        return TEAM_ROUTING["vpn"]
    if any(k in issue_lower for k in ("password", "locked", "reset", "credential", "login", "mfa")):
        return TEAM_ROUTING["password"]
    if any(k in issue_lower for k in ("access", "permission", "entitlement", "licence", "license", "security")):
        return TEAM_ROUTING["access"]
    if any(k in issue_lower for k in ("software", "install", "application", "app")):
        return TEAM_ROUTING["software"]
    return TEAM_ROUTING["general"]


def _next_ticket_id() -> str:
    mock_data._ticket_counter += 1
    return f"TKT-{mock_data._ticket_counter}"


# ── Tool implementations ────────────────────────────────────────────────────

def check_entitlement(employee_id: str, software: str) -> dict:
    """
    Check whether an employee is entitled to use a specific software application.
    """
    logger.info("[TOOL] check_entitlement | employee=%s software=%s", employee_id, software)

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT name FROM employees WHERE id = %s", (employee_id,))
                emp = cur.fetchone()
                if not emp:
                    return {
                        "success": False,
                        "error": f"Employee '{employee_id}' not found in the directory.",
                    }

                cur.execute("SELECT software_name FROM entitlements WHERE employee_id = %s", (employee_id,))
                user_ents = [row["software_name"] for row in cur.fetchall()]

                canonical = _normalize_software_with_list(software, user_ents)
                if canonical:
                    return {
                        "success": True,
                        "employee_id": employee_id,
                        "employee_name": emp["name"],
                        "software_requested": software,
                        "canonical_name": canonical,
                        "entitled": True,
                    }

                cur.execute("SELECT DISTINCT software_name FROM entitlements")
                all_catalog = [row["software_name"] for row in cur.fetchall()]
                canonical = _normalize_software_with_list(software, all_catalog)

                if canonical:
                    return {
                        "success": True,
                        "employee_id": employee_id,
                        "employee_name": emp["name"],
                        "software_requested": software,
                        "canonical_name": canonical,
                        "entitled": False,
                    }

                return {
                    "success": True,
                    "employee_id": employee_id,
                    "employee_name": emp["name"],
                    "software_requested": software,
                    "canonical_name": software,
                    "entitled": False,
                    "note": "Software not found in the approved catalogue. A ticket will still be raised for review.",
                }
        except Exception as e:
            logger.error("DB check_entitlement error, falling back to mock: %s", e)

    # Fallback to mock
    if employee_id not in EMPLOYEES:
        return {
            "success": False,
            "error": f"Employee '{employee_id}' not found in the directory.",
        }

    canonical = _normalize_software(software)
    employee_entitlements = ENTITLEMENTS.get(employee_id, [])

    if canonical:
        entitled = canonical in employee_entitlements
        return {
            "success": True,
            "employee_id": employee_id,
            "employee_name": EMPLOYEES[employee_id]["name"],
            "software_requested": software,
            "canonical_name": canonical,
            "entitled": entitled,
        }

    return {
        "success": True,
        "employee_id": employee_id,
        "employee_name": EMPLOYEES[employee_id]["name"],
        "software_requested": software,
        "canonical_name": software,
        "entitled": False,
        "note": "Software not found in the approved catalogue. A ticket will still be raised for review.",
    }


def create_ticket(employee_id: str, issue: str, priority: str) -> dict:
    """
    Create a new ITSM support ticket and persist it in the store.
    """
    logger.info("[TOOL] create_ticket | employee=%s priority=%s", employee_id, priority)

    valid_priorities = {"low", "medium", "high", "critical"}
    priority = priority.lower()
    if priority not in valid_priorities:
        priority = "medium"

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT name FROM employees WHERE id = %s", (employee_id,))
                emp = cur.fetchone()
                if not emp:
                    return {
                        "success": False,
                        "error": f"Employee '{employee_id}' not found.",
                    }

                cur.execute("SELECT COUNT(*) as count FROM tickets")
                cnt = cur.fetchone()["count"]
                ticket_id = f"TKT-{1005 + cnt}"
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                assigned_team = _route_team(issue.lower())

                insert_sql = """
                    INSERT INTO tickets (ticket_id, employee_id, issue, priority, status, assigned_team, created_at, updated_at, timestamp, latest_update)
                    VALUES (%s, %s, %s, %s, 'Open', %s, %s, %s, %s, 'Ticket created and assigned to team.')
                """
                cur.execute(insert_sql, (ticket_id, employee_id, issue, priority, assigned_team, now, now, now))
                logger.info("[TOOL] ticket created in DB | id=%s team=%s", ticket_id, assigned_team)

                return {
                    "success": True,
                    "ticket_id": ticket_id,
                    "employee_id": employee_id,
                    "employee_name": emp["name"],
                    "issue": issue,
                    "priority": priority,
                    "status": "Open",
                    "assigned_team": assigned_team,
                    "created_at": now,
                }
        except Exception as e:
            logger.error("DB create_ticket error, falling back to mock: %s", e)

    # Fallback to mock
    if employee_id not in EMPLOYEES:
        return {
            "success": False,
            "error": f"Employee '{employee_id}' not found.",
        }

    ticket_id = _next_ticket_id()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    assigned_team = _route_team(issue.lower())

    ticket = {
        "employee_id": employee_id,
        "issue": issue,
        "priority": priority,
        "status": "Open",
        "assigned_team": assigned_team,
        "created_at": now,
        "updated_at": now,
        "timestamp": now,
        "latest_update": "Ticket created and assigned to team.",
    }
    TICKETS[ticket_id] = ticket

    logger.info("[TOOL] ticket created | id=%s team=%s", ticket_id, assigned_team)

    return {
        "success": True,
        "ticket_id": ticket_id,
        "employee_id": employee_id,
        "employee_name": EMPLOYEES[employee_id]["name"],
        "issue": issue,
        "priority": priority,
        "status": "Open",
        "assigned_team": assigned_team,
        "created_at": now,
    }


def get_ticket_status(ticket_id: str) -> dict:
    """
    Retrieve the current status of an ITSM ticket.
    """
    logger.info("[TOOL] get_ticket_status | ticket_id=%s", ticket_id)

    ticket_id = ticket_id.upper().replace(" ", "-")
    if not ticket_id.startswith("TKT-"):
        ticket_id = f"TKT-{ticket_id}"

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                query = """
                    SELECT t.ticket_id, t.status, t.issue, t.priority, t.assigned_team, t.created_at, t.updated_at, t.latest_update, e.name as employee_name
                    FROM tickets t
                    LEFT JOIN employees e ON t.employee_id = e.id
                    WHERE t.ticket_id = %s
                """
                cur.execute(query, (ticket_id,))
                row = cur.fetchone()
                if not row:
                    return {
                        "success": False,
                        "error": f"Ticket '{ticket_id}' not found.",
                    }
                return {
                    "success": True,
                    "ticket_id": row["ticket_id"],
                    "status": row["status"],
                    "issue": row["issue"],
                    "priority": row["priority"],
                    "assigned_team": row["assigned_team"],
                    "created_at": str(row["created_at"]),
                    "updated_at": str(row["updated_at"]),
                    "latest_update": row["latest_update"],
                    "employee_name": row["employee_name"] or "Unknown",
                }
        except Exception as e:
            logger.error("DB get_ticket_status error, falling back to mock: %s", e)

    # Fallback to mock
    ticket = TICKETS.get(ticket_id)
    if not ticket:
        return {
            "success": False,
            "error": f"Ticket '{ticket_id}' not found.",
        }

    employee = EMPLOYEES.get(ticket["employee_id"], {})
    return {
        "success": True,
        "ticket_id": ticket_id,
        "status": ticket["status"],
        "issue": ticket["issue"],
        "priority": ticket["priority"],
        "assigned_team": ticket["assigned_team"],
        "created_at": ticket["created_at"],
        "updated_at": ticket["updated_at"],
        "latest_update": ticket["latest_update"],
        "employee_name": employee.get("name", "Unknown"),
    }


def check_vpn(employee_id: str) -> dict:
    """
    Return VPN connection status for an employee.
    """
    logger.info("[TOOL] check_vpn | employee=%s", employee_id)

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT name FROM employees WHERE id = %s", (employee_id,))
                emp = cur.fetchone()
                if not emp:
                    return {
                        "success": False,
                        "error": f"Employee '{employee_id}' not found.",
                    }

                cur.execute("SELECT status, last_connected, device, profile FROM vpn_status WHERE employee_id = %s", (employee_id,))
                vpn = cur.fetchone()
                vpn_status_val = vpn["status"] if vpn else "not_provisioned"
                last_connected_val = str(vpn["last_connected"]) if vpn and vpn["last_connected"] else None
                device_val = vpn["device"] if vpn else None
                profile_val = vpn["profile"] if vpn else None

                return {
                    "success": True,
                    "employee_id": employee_id,
                    "employee_name": emp["name"],
                    "vpn_status": vpn_status_val,
                    "last_connected": last_connected_val,
                    "device": device_val,
                    "profile": profile_val,
                }
        except Exception as e:
            logger.error("DB check_vpn error, falling back to mock: %s", e)

    # Fallback to mock
    if employee_id not in EMPLOYEES:
        return {
            "success": False,
            "error": f"Employee '{employee_id}' not found.",
        }

    vpn = VPN_STATUS.get(employee_id, {"status": "not_provisioned"})
    return {
        "success": True,
        "employee_id": employee_id,
        "employee_name": EMPLOYEES[employee_id]["name"],
        "vpn_status": vpn.get("status"),
        "last_connected": vpn.get("last_connected"),
        "device": vpn.get("device"),
        "profile": vpn.get("profile"),
    }


def reset_password(employee_id: str) -> dict:
    """
    Trigger a password reset for the employee's corporate account.
    """
    logger.info("[TOOL] reset_password | employee=%s", employee_id)

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT name FROM employees WHERE id = %s", (employee_id,))
                emp = cur.fetchone()
                if not emp:
                    return {
                        "success": False,
                        "error": f"Employee '{employee_id}' not found.",
                    }

                temp_token = str(uuid.uuid4())[:8].upper()
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                insert_sql = """
                    INSERT INTO password_reset_log (employee_id, employee_name, token, reset_at)
                    VALUES (%s, %s, %s, %s)
                """
                cur.execute(insert_sql, (employee_id, emp["name"], temp_token, now))

                return {
                    "success": True,
                    "employee_id": employee_id,
                    "employee_name": emp["name"],
                    "message": "Password reset initiated successfully.",
                    "temp_access_code": temp_token,
                    "expires_in": "24 hours",
                    "reset_at": now,
                    "instructions": (
                        "A temporary access code has been generated. "
                        "Use it to log in and set a new password immediately via the self-service portal."
                    ),
                }
        except Exception as e:
            logger.error("DB reset_password error, falling back to mock: %s", e)

    # Fallback to mock
    if employee_id not in EMPLOYEES:
        return {
            "success": False,
            "error": f"Employee '{employee_id}' not found.",
        }

    temp_token = str(uuid.uuid4())[:8].upper()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    reset_record = {
        "employee_id": employee_id,
        "employee_name": EMPLOYEES[employee_id]["name"],
        "reset_at": now,
        "token": temp_token,
    }
    PASSWORD_RESET_LOG.append(reset_record)

    logger.info("[TOOL] password reset logged | employee=%s", employee_id)

    return {
        "success": True,
        "employee_id": employee_id,
        "employee_name": EMPLOYEES[employee_id]["name"],
        "message": "Password reset initiated successfully.",
        "temp_access_code": temp_token,
        "expires_in": "24 hours",
        "reset_at": now,
        "instructions": (
            "A temporary access code has been generated. "
            "Use it to log in and set a new password immediately via the self-service portal."
        ),
    }


def send_email(employee_id: str, subject: str, body: str) -> dict:
    """
    Send an email notification to the employee.
    """
    logger.info("[TOOL] send_email | to=%s subject='%s'", employee_id, subject)

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT name, email FROM employees WHERE id = %s", (employee_id,))
                emp = cur.fetchone()
                if not emp:
                    return {
                        "success": False,
                        "error": f"Employee '{employee_id}' not found.",
                    }

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                insert_sql = """
                    INSERT INTO email_log (recipient, subject, body, sent_at)
                    VALUES (%s, %s, %s, %s)
                """
                cur.execute(insert_sql, (emp["email"], subject, body, now))

                return {
                    "success": True,
                    "to": emp["email"],
                    "subject": subject,
                    "sent_at": now,
                }
        except Exception as e:
            logger.error("DB send_email error, falling back to mock: %s", e)

    # Fallback to mock
    if employee_id not in EMPLOYEES:
        return {
            "success": False,
            "error": f"Employee '{employee_id}' not found.",
        }

    employee = EMPLOYEES[employee_id]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    record = {
        "to": employee["email"],
        "employee_name": employee["name"],
        "subject": subject,
        "body": body,
        "sent_at": now,
    }
    EMAIL_LOG.append(record)

    logger.info("[TOOL] email queued | to=%s", employee["email"])

    return {
        "success": True,
        "to": employee["email"],
        "subject": subject,
        "sent_at": now,
    }


def notify_it_team(ticket_id: str, issue: str, employee_id: str, priority: str) -> dict:
    """
    Send an alert to the IT operations team.
    """
    logger.info("[TOOL] notify_it_team | ticket=%s priority=%s", ticket_id, priority)

    if is_db_configured():
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT name FROM employees WHERE id = %s", (employee_id,))
                emp = cur.fetchone()
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                insert_sql = """
                    INSERT INTO it_notification_log (ticket_id, channel, issue, priority, notified_at)
                    VALUES (%s, '#it-ops-alerts', %s, %s, %s)
                """
                cur.execute(insert_sql, (ticket_id, issue, priority, now))

                return {
                    "success": True,
                    "ticket_id": ticket_id,
                    "priority": priority,
                    "notified_at": now,
                    "channel": "#it-ops-alerts",
                }
        except Exception as e:
            logger.error("DB notify_it_team error, falling back to mock: %s", e)

    # Fallback to mock
    employee = EMPLOYEES.get(employee_id, {})
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    record = {
        "ticket_id": ticket_id,
        "issue": issue,
        "reported_by": employee.get("name", employee_id),
        "employee_id": employee_id,
        "priority": priority,
        "notified_at": now,
        "channel": "#it-ops-alerts",
    }
    IT_NOTIFICATION_LOG.append(record)

    logger.info("[TOOL] IT team notified | ticket=%s", ticket_id)

    return {
        "success": True,
        "ticket_id": ticket_id,
        "priority": priority,
        "notified_at": now,
        "channel": "#it-ops-alerts",
    }


# ── Dispatch table (used by the agent) ────────────────────────────────────

TOOL_FUNCTIONS: dict = {
    "check_entitlement": check_entitlement,
    "create_ticket": create_ticket,
    "get_ticket_status": get_ticket_status,
    "check_vpn": check_vpn,
    "reset_password": reset_password,
    "send_email": send_email,
    "notify_it_team": notify_it_team,
}
