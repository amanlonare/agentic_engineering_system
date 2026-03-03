import unittest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage
from src.nodes.ops import ops_node
from src.core.state import EngineeringState
from src.schemas import TechnicalPlan, ExecutionStep, TestReport, TriggerContext, StepExecutionRecord, StepStatus, TestCaseResult

class TestOpsDeterministic(unittest.TestCase):
    def setUp(self):
        # Setup a mock state
        self.step_1 = ExecutionStep(
            id="STEP-1",
            description="Verify Auth service implementation",
            assigned_to="ops",
            target_repo="mobile-app"
        )
        self.plan = TechnicalPlan(
            title="Test Auth",
            summary="Verification of auth service",
            steps=[self.step_1]
        )
        self.trigger = TriggerContext(
            type="manual",
            repo_name="mobile-app",
            payload={"description": "Test Auth"}
        )

    @patch("src.nodes.ops.ChatOpenAI")
    @patch("src.nodes.ops.get_ops_tools")
    @patch("src.nodes.ops.load_agent_persona")
    @patch("src.nodes.ops.build_system_prompt")
    def test_ops_successful_verification(self, mock_build_prompt, mock_load_persona, mock_get_tools, mock_llm_class):
        # 1. Setup Mocks
        mock_load_persona.return_value = {"name": "ops", "system_prompt": "You are ops"}
        mock_build_prompt.return_value = "System prompt"
        
        mock_tool = MagicMock()
        mock_tool.name = "execute_command"
        mock_get_tools.return_value = [mock_tool]

        # Mock LLM behavior for tool calling loop
        mock_llm_instance = MagicMock()
        
        # First call returns a tool call
        tool_call_resp = MagicMock()
        tool_call_resp.tool_calls = [{"name": "execute_command", "args": {"command": "pytest"}, "id": "1"}]
        
        # Second call returns final reasoning
        final_resp = MagicMock()
        final_resp.tool_calls = []
        final_resp.content = "Everything looks good."
        
        mock_llm_instance.invoke.side_effect = [tool_call_resp, final_resp]
        
        # Bind tools mock
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        # Mock structured output for TestReport
        mock_structured_llm = MagicMock()
        mock_report = TestReport(
            suite_name="Auth Verification",
            total_tests=1,
            passed_count=1,
            failures=[],
            logs="Inspected AuthService.js, looks correct.",
            success=True
        )
        mock_structured_llm.invoke.return_value = mock_report
        
        # Configure mock_llm_class to return our instances
        mock_llm_instance.with_structured_output.return_value = mock_structured_llm
        mock_llm_class.return_value = mock_llm_instance

        # 2. Execute Node
        state = EngineeringState(
            messages=[HumanMessage(content="Current Plan Step [STEP-1]: ...")],
            task_plan=self.plan,
            completed_step_ids=[],
            execution_history=[],
            trigger=self.trigger
        )
        
        result = ops_node(state)

        # 3. Assertions
        self.assertEqual(result["completed_step_ids"], ["STEP-1"])
        self.assertIsInstance(result["validation_report"], TestReport)
        self.assertTrue(result["validation_report"].success)
        self.assertEqual(len(result["execution_history"]), 1)
        self.assertEqual(result["execution_history"][0].step_id, "STEP-1")
        self.assertEqual(result["execution_history"][0].status, StepStatus.COMPLETED)
        
        # Verify tool was called
        mock_tool.invoke.assert_called_once_with({"command": "pytest"})

    @patch("src.nodes.ops.ChatOpenAI")
    @patch("src.nodes.ops.get_ops_tools")
    def test_ops_failure_verification(self, mock_get_tools, mock_llm_class):
        # Mock failure scenario
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(tool_calls=[], content="Logic error found.")
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        mock_structured_llm = MagicMock()
        mock_report = TestReport(
            suite_name="Auth Verification",
            total_tests=1,
            passed_count=0,
            failures=[TestCaseResult(name="Step Verification", passed=False, error_message="Logic error")],
            logs="Found a missing null check.",
            success=False
        )
        mock_structured_llm.invoke.return_value = mock_report
        mock_llm_instance.with_structured_output.return_value = mock_structured_llm
        mock_llm_class.return_value = mock_llm_instance
        
        state = EngineeringState(
            messages=[HumanMessage(content="Current Plan Step [STEP-1]")],
            task_plan=self.plan,
            completed_step_ids=[],
            execution_history=[],
            trigger=self.trigger
        )
        
        result = ops_node(state)
        
        self.assertEqual(result["completed_step_ids"], []) # Failure should not complete ID
        self.assertEqual(result["execution_history"][0].status, StepStatus.FAILED)

if __name__ == "__main__":
    unittest.main()
