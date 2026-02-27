from typing import List, Optional
from pydantic import BaseModel, Field
from src.core.state import EngineeringState
from src.core.supervisor import supervisor_node
from src.schemas.plans import TechnicalPlan, ExecutionStep
from src.schemas.triggers import TriggerContext
from src.schemas.enums import TriggerType, ApprovalStatus
from langchain_core.messages import HumanMessage
import logging

# Setup basic logging to see the Supervisor output
logging.basicConfig(level=logging.INFO)

def test_deterministic_routing():
    """
    Manually test the Supervisor routing logic by creating a mock state.
    """
    print("\n🚀 Starting Deterministic Orchestration Test...")

    # 1. Create a Mock Plan
    plan = TechnicalPlan(
        title="Test Plan",
        summary="A test plan to verify routing.",
        steps=[
            ExecutionStep(id="STEP-1", description="Fix frontend", assigned_to="coder"),
            ExecutionStep(id="STEP-2", description="Verify fix", assigned_to="ops", dependencies=["STEP-1"]),
        ],
        definition_of_done=["Done"],
        estimated_risk="low"
    )

    # 2. Test Case A: Initial State (No steps completed)
    state_a = EngineeringState(
        messages=[HumanMessage(content="Test request")],
        trigger=TriggerContext(type=TriggerType.MANUAL, payload={"description": "Test"}),
        task_plan=plan,
        completed_step_ids=[],
        approval_status=ApprovalStatus.APPROVED
    )
    
    print("\n--- Scenario A: Plan exists, 0 steps completed ---")
    decision_a = supervisor_node(state_a)
    messages_a = decision_a.get('messages', [])
    reasoning_a = messages_a[0].content if messages_a else "N/A"
    print(f"Result: {decision_a.get('next_node')} | Reasoning: {reasoning_a}")

    # 3. Test Case B: Partial Completion (STEP-1 is done)
    state_b = EngineeringState(
        messages=[HumanMessage(content="Test request")],
        trigger=TriggerContext(type=TriggerType.MANUAL, payload={"description": "Test"}),
        task_plan=plan,
        completed_step_ids=["STEP-1"],
        approval_status=ApprovalStatus.APPROVED
    )
    
    print("\n--- Scenario B: STEP-1 ('coder') completed ---")
    decision_b = supervisor_node(state_b)
    messages_b = decision_b.get('messages', [])
    reasoning_b = messages_b[0].content if messages_b else "N/A"
    print(f"Result: {decision_b.get('next_node')} | Reasoning: {reasoning_b}")

    # 4. Test Case C: Full Completion
    state_c = EngineeringState(
        messages=[HumanMessage(content="Test request")],
        trigger=TriggerContext(type=TriggerType.MANUAL, payload={"description": "Test"}),
        task_plan=plan,
        completed_step_ids=["STEP-1", "STEP-2"],
        approval_status=ApprovalStatus.APPROVED
    )
    
    print("\n--- Scenario C: All steps completed ---")
    decision_c = supervisor_node(state_c)
    messages_c = decision_c.get('messages', [])
    reasoning_c = messages_c[0].content if messages_c else "N/A"
    print(f"Result: {decision_c.get('next_node')} | Reasoning: {reasoning_c}")

if __name__ == "__main__":
    test_deterministic_routing()
