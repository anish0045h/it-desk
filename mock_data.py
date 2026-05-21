# mock_data.py — Simulated in-memory database store for IT systems.

EMPLOYEES = {
    "emp_001": {
        "name": "Alice Johnson",
        "email": "alice.johnson@company.com",
        "department": "Marketing",
        "role": "Marketing Manager",
    },
    "emp_002": {
        "name": "Bob Smith",
        "email": "bob.smith@company.com",
        "department": "Engineering",
        "role": "Software Engineer",
    },
    "emp_003": {
        "name": "Carol Davis",
        "email": "carol.davis@company.com",
        "department": "Finance",
        "role": "Financial Analyst",
    },
    "emp_004": {
        "name": "David Lee",
        "email": "david.lee@company.com",
        "department": "HR",
        "role": "HR Specialist",
    },
}

ENTITLEMENTS = {
    "emp_001": ["O365", "Slack", "Adobe Creative Suite", "Zoom", "Salesforce"],
    "emp_002": ["O365", "Slack", "GitHub Enterprise", "VS Code", "Zoom", "Jira", "Confluence"],
    "emp_003": ["O365", "Slack", "SAP S/4HANA", "Zoom", "Tableau"],
    "emp_004": ["O365", "Slack", "Zoom"],
}

VPN_STATUS = {
    "emp_001": {
        "status": "active",
        "last_connected": "2026-05-20 14:32:10",
        "device": "macbook-pro-01",
        "profile": "marketing-vpn",
    },
    "emp_002": {
        "status": "inactive",
        "last_connected": "2026-05-19 09:15:22",
        "device": "thinkpad-x1-02",
        "profile": "eng-vpn",
    },
    "emp_003": {
        "status": "locked",
        "last_connected": "2026-05-18 11:45:00",
        "device": "dell-latitude-03",
        "profile": "finance-vpn",
    },
    "emp_004": {
        "status": "active",
        "last_connected": "2026-05-20 16:50:45",
        "device": "ipad-pro-04",
        "profile": "general-vpn",
    },
}

TICKETS = {}
EMAIL_LOG = []
IT_NOTIFICATION_LOG = []
PASSWORD_RESET_LOG = []
_ticket_counter = 0
