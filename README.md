# DeskMate - AI Powered IT Helpdesk Assistant


DeskMate is an AI-powered IT Helpdesk Assistant designed to automate common IT support workflows inside an organization. It uses a Large Language Model (Gemini) combined with internal tools and business logic to understand employee requests, decide which action to perform, execute the required tools, and provide a human-friendly response.

The system can handle requests such as password resets, VPN status checks, software entitlement verification, ticket creation, and ticket status tracking.


# Features

## AI-Powered Request Understanding
- Understands natural language employee requests
- Detects user intent automatically
- Handles conversational interactions
- Maintains conversation history

## Password Reset Automation
- Processes password reset requests
- Generates temporary access codes

## Software Entitlement Verification
- Checks if employees have access to requested software
- Performs entitlement validation
- Raises tickets if access is unavailable

## Ticket Management
- Creates support tickets automatically
- Assigns tickets to appropriate teams
- Tracks ticket status
- Provides ticket updates

## VPN Management
- Checks employee VPN status
- Retrieves connection details
- Displays provisioning status

## Email Notifications
- Sends notifications to employees
- Alerts IT teams automatically

## Database Integration
- Supports PostgreSQL
- Falls back to mock data when database is unavailable

## Web Interface
- Streamlit-based interactive UI
- FastAPI backend APIs
- Chat-style interface


# Project Architecture

The application follows a modular architecture:

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


# Project Structure

```text
DeskMate/
│
├── agent.py
│       Main AI agent logic
│       Handles tool execution flow
│
├── app.py
│       Streamlit frontend application
│
├── main.py
│       FastAPI backend server
│
├── db.py
│       PostgreSQL connection management
│
├── tools.py
│       Internal tool implementations
│
├── mock_data.py
│       In-memory mock database
│
├── seed_db.py
│       Database seeding script
│
├── test_agent_flow.py
│       Test script for agent workflow
│
├── requirements.txt
│       Project dependencies
│
├── .env.example
│       Example environment variables
│
├── .gitignore
│
├── README.md
│
└── static/
        └── index.html
```


# Technology Stack

- Python
- FastAPI
- Streamlit
- Google Gemini API
- PostgreSQL
- psycopg2
- Python-dotenv


- PostgreSQL

**Language**
- Python


# Installation and Setup

## 1. Clone Repository

```bash
git clone https://github.com/your-username/deskmate.git

cd deskmate
```

## 2. Create Virtual Environment

**Windows**

```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac**

```bash
python3 -m venv venv
source venv/bin/activate
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Create Environment File

Create a `.env` file and add:

```env
GEMINI_API_KEY=your_api_key

DB_HOST=localhost
DB_PORT=5432
DB_NAME=deskmate
DB_USER=postgres
DB_PASSWORD=password
```

## 5. Get Gemini API Key

1. Open: https://aistudio.google.com/
2. Login with Google
3. Generate API key
4. Add it to `.env`

## 6. Setup PostgreSQL

Create database:

```sql
CREATE DATABASE deskmate;
```

Seed sample data:

```bash
python seed_db.py
```

---

# Run Application

**Streamlit UI**

```bash
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

**FastAPI Backend**

```bash
uvicorn main:app --reload
```

Open:

```text
http://localhost:8000
```

---



---

# Run Tests

```bash
python test_agent_flow.py
```

---

# Sample Requests

```text
I forgot my password

Check my VPN status

I need Adobe access

What is the status of ticket TKT-1001?
```




# Author

Anish  
AI/ML Developer | Python Developer

