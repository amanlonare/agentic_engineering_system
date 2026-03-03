import os
import sys

# Ensure src is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import HumanMessage
from src.core.state import EngineeringState
from src.nodes.ops import ops_node
from src.schemas import StepStatus, TriggerContext

def main():
    print("🚀 Triggering Ops Agent Manually...")
    
    # 1. Provide a mock trigger (assuming mobile-backend exists in .context)
    # Ideally, replace 'mobile-backend' with a repository that exists in your .context
    trigger = TriggerContext(
        type="USER_PROMPT",
        payload={"content": "Please test the latest code changes in mobile-backend using pytest."},
        repo_name="mobile-backend" # Make sure this folder exists inside .context/
    )
    
    # 2. Setup mock state
    state = EngineeringState(
        messages=[
            HumanMessage(content="Please run `pytest` to see if the current backend tests pass.")
        ],
        trigger=trigger,
        completed_step_ids=[]
    )
    
    # 3. Call the Ops Node directly
    print("\n--------------------------")
    print("Calling ops_node()...")
    print("--------------------------\n")
    
    result = ops_node(state)
    
    # 4. Print Results
    print("\n--------------------------")
    print("✅ Ops Execution Complete")
    print("--------------------------\n")
    
    print("--- Tool Calls / Messages ---")
    for msg in result.get("messages", []):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print(f"🤖 Agent requested tool: {msg.tool_calls[0].get('name')} with args {msg.tool_calls[0].get('args')}")
        elif msg.type == "tool":
            print(f"🔧 Tool Output:\n{msg.content}\n")
            
    print("\n--- Structured Validation Report ---")
    report = result.get("validation_report")
    if report:
        print(f"Success: {report.success}")
        print(f"Logs: {report.logs}")
    else:
        print("No report generated.")

if __name__ == "__main__":
    main()
