    
    # test_agent_flow.py — Basic agent flow tests (uses live Gemini API)

import os
import sys
import logging
from unittest.mock import patch
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
load_dotenv()

from agent import DeskMateAgent

logging.basicConfig(level=logging.INFO)


def get_agent() -> DeskMateAgent:
    try:
        return DeskMateAgent()
    except Exception as e:
        print(f"[ERROR] Could not initialise agent: {e}")
        sys.exit(1)


def test_software_entitlement_flow():
    """Carol (emp_003) is NOT entitled to Adobe — should trigger ticket + email + IT notification."""
    print("\n=== Test 1: Software entitlement + ticket creation ===")
    agent = get_agent()
    result = agent.process(
        employee_id="emp_003",
        message="I need access to Adobe Creative Suite. If I'm not entitled, raise a high-priority ticket.",
        history=[],
    )
    print("Response:", result["response"])

    tools_called = [s["tool"] for s in result["trace"] if s["step"] == "Tool called"]
    print("Tools called:", tools_called)

    expected = ["check_entitlement", "create_ticket", "send_email", "notify_it_team"]
    missing = [t for t in expected if t not in tools_called]
    if missing:
        print(f"[FAIL] Missing tools: {missing}")
    else:
        print("[PASS] All expected tools called.")
    return result


def test_unknown_ticket():
    """Querying a non-existent ticket should return 'Unable to locate the ticket.'"""
    print("\n=== Test 2: Non-existent ticket ===")
    agent = get_agent()
    result = agent.process(employee_id="emp_001", message="What is the status of ticket TKT-999999?", history=[])
    print("Response:", result["response"])
    if "unable to locate" in result["response"].lower():
        print("[PASS] Correct not-found response.")
    else:
        print("[FAIL] Expected 'Unable to locate the ticket.'")


def test_out_of_scope():
    """Non-IT request should be refused."""
    print("\n=== Test 3: Out-of-scope request ===")
    agent = get_agent()
    result = agent.process(employee_id=None, message="What's the weather like today?", history=[])
    print("Response:", result["response"])
    if "it helpdesk" in result["response"].lower() or "only with it" in result["response"].lower():
        print("[PASS] Out-of-scope request refused.")
    else:
        print("[WARN] Response may not be a clean refusal — check manually.")


def test_password_reset_no_token_leak():
    """Password reset response must NOT contain the raw temp token."""
    print("\n=== Test 4: Password reset — no token leak ===")
    agent = get_agent()
    result = agent.process(employee_id="emp_001", message="Please reset my password.", history=[])
    print("Response:", result["response"])

    # Check trace doesn't contain temp_access_code
    for step in result["trace"]:
        if step.get("step") == "Result" and step.get("tool") == "reset_password":
            assert "temp_access_code" not in step.get("result", {}), "[FAIL] Token found in trace!"
            assert "token" not in step.get("result", {}), "[FAIL] Token found in trace!"
    print("[PASS] No raw token in trace.")


if __name__ == "__main__":
    test_software_entitlement_flow()
    test_unknown_ticket()
    test_out_of_scope()
    test_password_reset_no_token_leak()
    print("\nAll tests completed.")
