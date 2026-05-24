# mock_data.py — In-memory store for IT systems (used when DB is not configured)

EMPLOYEES = {
    "emp_001": {"name": "Alice Johnson", "email": "alice.johnson@company.com", "department": "Marketing",   "role": "Marketing Manager"},
    "emp_002": {"name": "Bob Smith",     "email": "bob.smith@company.com",     "department": "Engineering", "role": "Software Engineer"},
    "emp_003": {"name": "Carol Davis",   "email": "carol.davis@company.com",   "department": "Finance",     "role": "Financial Analyst"},
    "emp_004": {"name": "David Lee",     "email": "david.lee@company.com",     "department": "HR",          "role": "HR Specialist"},
}

ENTITLEMENTS = {
    "emp_001": ["O365", "Slack", "Adobe Creative Suite", "Zoom", "Salesforce"],
    "emp_002": ["O365", "Slack", "GitHub Enterprise", "VS Code", "Zoom", "Jira", "Confluence"],
    "emp_003": ["O365", "Slack", "SAP S/4HANA", "Zoom", "Tableau"],
    "emp_004": ["O365", "Slack", "Zoom"],
}

VPN_STATUS = {
    "emp_001": {"status": "active",   "last_connected": "2026-05-20 14:32:10", "device": "macbook-pro-01",   "profile": "marketing-vpn"},
    "emp_002": {"status": "inactive", "last_connected": "2026-05-19 09:15:22", "device": "thinkpad-x1-02",   "profile": "eng-vpn"},
    "emp_003": {"status": "locked",   "last_connected": "2026-05-18 11:45:00", "device": "dell-latitude-03", "profile": "finance-vpn"},
    "emp_004": {"status": "active",   "last_connected": "2026-05-20 16:50:45", "device": "ipad-pro-04",      "profile": "general-vpn"},
}

# Mutable stores (append-only logs + ticket store)
TICKETS: dict = {}
EMAIL_LOG: list = []
IT_NOTIFICATION_LOG: list = []
PASSWORD_RESET_LOG: list = []

# Pre-seeded tickets
TICKETS.update({
    "TKT-1001": {"employee_id": "emp_002", "issue": "Cannot connect to VPN — authentication error on ThinkPad X1", "priority": "high",   "status": "In Progress",       "assigned_team": "Network Team",  "created_at": "2025-01-13 10:00:00", "updated_at": "2025-01-14 11:30:00", "latest_update": "Network Team is investigating the VPN gateway configuration."},
    "TKT-1002": {"employee_id": "emp_003", "issue": "Request for Adobe Creative Suite access",                    "priority": "medium", "status": "Pending Approval",   "assigned_team": "Security Team", "created_at": "2025-01-12 14:00:00", "updated_at": "2025-01-13 09:00:00", "latest_update": "Awaiting manager approval for additional software licence."},
    "TKT-1003": {"employee_id": "emp_001", "issue": "Password reset request — locked out of corporate account",  "priority": "medium", "status": "Resolved",           "assigned_team": "Identity Team", "created_at": "2025-01-10 08:00:00", "updated_at": "2025-01-10 09:00:00", "latest_update": "Password reset completed. Employee notified by email."},
    "TKT-1004": {"employee_id": "emp_004", "issue": "Request for Jira access — cross-team project",             "priority": "low",    "status": "Open",               "assigned_team": "L1 Support",    "created_at": "2025-01-14 16:00:00", "updated_at": "2025-01-14 16:00:00", "latest_update": "Ticket logged. L1 Support will process within 2 business days."},
})

_ticket_counter = 1004  # next ticket will be TKT-1005
