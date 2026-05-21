# Production Design – DeskMate

## Overview

DeskMate is an AI-powered IT Helpdesk Assistant that uses FastAPI, Streamlit, Gemini API, PostgreSQL, and internal tool execution to automate IT support workflows such as password resets, VPN checks, entitlement validation, and ticket creation.

The current implementation is a Proof of Concept (POC). This document describes how the system would be transformed into a production-ready application on Azure.

---

# Current Architecture

```text
User
   ↓
Streamlit UI / FastAPI API
   ↓
DeskMate Agent
   ↓
Gemini LLM
   ↓
Tool Dispatcher
   ↓
Internal Services
   ├── Ticket System
   ├── Password System
   ├── VPN Service
   └── Database
```

---

# Production Architecture on Azure

```text
Users
   ↓
Azure Application Gateway
   ↓
Azure App Service / AKS
   ↓
FastAPI Backend
   ↓
DeskMate Agent Layer
   ↓
Gemini API
   ↓
Azure PostgreSQL Database
   ↓
Azure Key Vault
   ↓
Azure Monitor + Application Insights
```

---

# Key Production Decisions

## Containerized Deployment

- Package applications using Docker
- Deploy frontend and backend independently
- Scale services independently

Reason:
Allows better scalability and easier deployment.

---

## Managed Database

Replace local/mock storage with:

- Azure Database for PostgreSQL
- Automated backups
- High availability
- Failover support

Reason:
Ensures persistent and reliable storage.

---

## Secrets Management

Remove sensitive values from:

- .env files
- source code

Store:

- API keys
- database credentials
- application secrets

Use:

- Azure Key Vault

Reason:
Prevents accidental exposure of credentials.

---

## Authentication and Authorization

Replace direct employee ID input with:

- Azure Active Directory
- Role-based access control

Reason:
Prevents unauthorized access.

---

## Monitoring and Logging

Use:

- Azure Monitor
- Application Insights

Monitor:

- API failures
- tool failures
- database errors
- response time
- Gemini failures

Reason:
Allows issue detection and debugging.

---

# Major Risks

## AI Hallucination

Risk:

AI may trigger incorrect actions such as:

- wrong password resets
- wrong ticket creation
- incorrect entitlement checks

Mitigation:

- strict prompt rules
- tool validation
- approval flow for critical actions

---

## Security Risk

Risk:

Sensitive employee data or API keys could be exposed.

Mitigation:

- Azure Key Vault
- encryption
- access control
- secure authentication

---

## External Dependency Risk

Risk:

Gemini API downtime can affect DeskMate functionality.

Mitigation:

- retry mechanisms
- fallback workflows
- graceful error handling

---

# Scope Decisions

Areas intentionally not prioritized:

- Multi-region deployment
- Kubernetes optimization
- advanced CI/CD pipelines

Reason:

For DeskMate, security, reliability, and controlled AI behavior are more critical than infrastructure complexity at the current stage.

---

# Conclusion

The transition from POC to production focuses primarily on security, reliability, scalability, and controlled AI behavior while minimizing operational risk.
