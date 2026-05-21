import sys
import os

# Add local path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from db import is_db_configured, get_db_cursor
from mock_data import EMPLOYEES, ENTITLEMENTS, VPN_STATUS

def seed():
    if not is_db_configured():
        print("[ERROR] Database not configured!")
        return

    print("Seeding PostgreSQL tables...")
    try:
        with get_db_cursor() as cur:
            # 1. Clear tables
            cur.execute("TRUNCATE TABLE email_log, it_notification_log, password_reset_log, tickets, entitlements, vpn_status, employees CASCADE")
            print("Tables truncated successfully.")

            # 2. Seed employees
            for eid, emp in EMPLOYEES.items():
                cur.execute(
                    "INSERT INTO employees (id, name, email, department, role) VALUES (%s, %s, %s, %s, %s)",
                    (eid, emp["name"], emp["email"], emp["department"], emp["role"])
                )
            print("Employees seeded.")

            # 3. Seed entitlements
            for eid, ents in ENTITLEMENTS.items():
                for ent in ents:
                    cur.execute(
                        "INSERT INTO entitlements (employee_id, software_name) VALUES (%s, %s)",
                        (eid, ent)
                    )
            print("Entitlements seeded.")

            # 4. Seed VPN
            for eid, vpn in VPN_STATUS.items():
                cur.execute(
                    "INSERT INTO vpn_status (employee_id, status, last_connected, device, profile) VALUES (%s, %s, %s, %s, %s)",
                    (eid, vpn["status"], vpn["last_connected"], vpn["device"], vpn["profile"])
                )
            print("VPN Statuses seeded.")

            # 5. Seed initial tickets
            tickets_mock = {
                "TKT-1001": {
                    "employee_id": "emp_002",
                    "issue": "Cannot connect to VPN — authentication error on ThinkPad X1",
                    "priority": "high",
                    "status": "In Progress",
                    "assigned_team": "Network Team",
                    "created_at": "2025-01-13 10:00:00",
                    "updated_at": "2025-01-14 11:30:00",
                    "timestamp": "2025-01-13 10:00:00",
                    "latest_update": "Network Team is investigating the VPN gateway configuration.",
                },
                "TKT-1002": {
                    "employee_id": "emp_003",
                    "issue": "Request for Adobe Creative Suite access",
                    "priority": "medium",
                    "status": "Pending Approval",
                    "assigned_team": "Security Team",
                    "created_at": "2025-01-12 14:00:00",
                    "updated_at": "2025-01-13 09:00:00",
                    "timestamp": "2025-01-12 14:00:00",
                    "latest_update": "Awaiting manager approval for additional software licence.",
                },
                "TKT-1003": {
                    "employee_id": "emp_001",
                    "issue": "Password reset request — locked out of corporate account",
                    "priority": "medium",
                    "status": "Resolved",
                    "assigned_team": "Identity Team",
                    "created_at": "2025-01-10 08:00:00",
                    "updated_at": "2025-01-10 09:00:00",
                    "timestamp": "2025-01-10 08:00:00",
                    "latest_update": "Password reset completed successfully. Employee notified by email.",
                },
                "TKT-1004": {
                    "employee_id": "emp_004",
                    "issue": "Request for Jira access — cross-team project collaboration",
                    "priority": "low",
                    "status": "Open",
                    "assigned_team": "L1 Support",
                    "created_at": "2025-01-14 16:00:00",
                    "updated_at": "2025-01-14 16:00:00",
                    "timestamp": "2025-01-14 16:00:00",
                    "latest_update": "Ticket logged. L1 Support will process within 2 business days.",
                },
            }
            for tid, tkt in tickets_mock.items():
                cur.execute(
                    """
                    INSERT INTO tickets (ticket_id, employee_id, issue, priority, status, assigned_team, created_at, updated_at, timestamp, latest_update)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (tid, tkt["employee_id"], tkt["issue"], tkt["priority"], tkt["status"], tkt["assigned_team"], tkt["created_at"], tkt["updated_at"], tkt["created_at"], tkt["latest_update"])
                )
            print("Initial tickets seeded.")
            print("[SUCCESS] Database seeding completed successfully!")
    except Exception as e:
        print(f"[ERROR] Seeding failed: {e}")

if __name__ == "__main__":
    seed()
