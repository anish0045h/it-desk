import os
import sys
import logging
from dotenv import load_dotenv

# Ensure local imports work
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agent import DeskMateAgent
from db import is_db_configured

logging.basicConfig(level=logging.INFO)

def run_agent_test():
    load_dotenv()
    
    print("=== Checking DB configuration ===")
    print(f"DB configured: {is_db_configured()}")
    
    print("\n=== Initializing DeskMateAgent ===")
    try:
        agent = DeskMateAgent()
    except Exception as e:
        print(f"[ERROR] Failed to initialize agent: {e}")
        sys.exit(1)
        
    print("\n=== Test Case 1: Software Entitlement and Ticket Creation ===")
    message = "I need access to Adobe Creative Suite. Please check if I'm entitled, and if not, raise a high priority ticket."
    employee_id = "emp_003" # Carol Davis
    
    print(f"Sending message: '{message}' as employee {employee_id}")
    res = agent.process(employee_id=employee_id, message=message, history=[])
    
    print("\nAgent Response:")
    print(res["response"])
    
    print("\nExecution Trace:")
    for step in res["trace"]:
        print(f" - {step['step']}: {step.get('detail') or step.get('tool')}")
        if step['step'] == "Tool called":
            print(f"   Args: {step.get('arguments')}")
        elif step['step'] == "Result":
            print(f"   Result: {step.get('result')}")

    # Verify that the flow went through check_entitlement, create_ticket, send_email, notify_it_team
    steps_run = [step["tool"] for step in res["trace"] if step["step"] == "Tool called"]
    print(f"\nTools called in sequence: {steps_run}")
    
    expected_tools = ["check_entitlement", "create_ticket", "send_email", "notify_it_team"]
    all_passed = True
    for tool in expected_tools:
        if tool not in steps_run:
            print(f"[WARNING] Expected tool '{tool}' was not called.")
            all_passed = False
            
    if all_passed:
        print("[SUCCESS] All expected tools called in sequence!")
    else:
        print("[FAILURE] Some expected tools were missed.")

    print("\n=== Test Case 2: Querying Ticket Status (Unknown Ticket) ===")
    message2 = "What is the status of ticket TKT-999999?"
    print(f"Sending message: '{message2}'")
    res2 = agent.process(employee_id=employee_id, message=message2, history=res["conversation_history"])
    
    print("\nAgent Response:")
    print(res2["response"])
    
    print("\nExecution Trace:")
    for step in res2["trace"]:
        print(f" - {step['step']}: {step.get('detail') or step.get('tool')}")

    if "Unable to locate the ticket." in res2["response"]:
        print("[SUCCESS] Properly handled non-existent ticket error!")
    else:
        print("[WARNING] Did not reply with standard 'Unable to locate the ticket.'")

if __name__ == "__main__":
    run_agent_test()
