import warnings
from typing import Any, Dict, List, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig
from langfuse import observe

from src.core.config_manager import config_manager
from src.core.resource_manager import ResourceManager
from src.core.state import EngineeringState
from src.schemas import StepExecutionRecord, StepStatus, TestReport
from src.tools.e2b_aider_tool import kill_sandbox, run_aider_in_e2b
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("ops")
resource_manager = ResourceManager()


@observe(name="Agent: Verification & Ops")
async def ops_node(
    state: EngineeringState, config: RunnableConfig, **kwargs
) -> Dict[str, Any]:
    """
    Ops Agent: Verifies code changes and deployment.
    """
    logger.info("🛠️ Ops Agent starting verification...")

    # 1. Identify Target Step and Repo (Standard compliance)
    last_message = state.messages[-1].content if state.messages else ""
    instructions = str(last_message)
    current_step = None
    history = []
    completed_ids = []

    if state.task_plan:
        for step in state.task_plan.steps:
            if step.id in instructions and step.assigned_to == "ops":
                current_step = step
                break

        if not current_step:
            logger.warning(
                "⚠️ No explicit Step ID. Falling back to first uncompleted step."
            )
            for step in state.task_plan.steps:
                if step.assigned_to == "ops" and step.id not in (
                    state.completed_step_ids or []
                ):
                    current_step = step
                    break

    if not current_step:
        repo = (
            state.trigger.repo_name
            if state.trigger and state.trigger.repo_name
            else "unknown"
        )
        logger.info(
            "ℹ️ No specific step identified. Operating in general verification mode."
        )
    else:
        repo = current_step.target_repo or (
            state.trigger.repo_name
            if state.trigger and state.trigger.repo_name
            else "unknown"
        )
        if current_step.id in (state.completed_step_ids or []):
            logger.warning(
                "⚠️ Supervisor requested step %s which is already complete.",
                current_step.id,
            )

        instructions = (
            f"Current Plan Step [{current_step.id}]: {current_step.description}"
        )
        if state.verification_scripts:
            instructions += f"\nVerification Scripts to run: {', '.join(state.verification_scripts)}"

        if current_step.verification_criteria:
            instructions += (
                f"\nVerification Criteria: {current_step.verification_criteria}"
            )

        # 1.1 Inject Growth Recommendations into Git steps
        if state.accumulated_growth_notes and (
            "git" in current_step.description.lower()
            or "commit" in current_step.description.lower()
            or "push" in current_step.description.lower()
        ):
            instructions += (
                f"\n\n🚀 ADDITIONAL GROWTH RECOMMENDATIONS TO INCLUDE:\n"
                f"{state.accumulated_growth_notes}"
            )
    logger.info(f"🔒 Locking tools to repository: {repo}")

    # 2. Setup Persona, LLM, and message context
    persona = load_agent_persona("ops")
    system_prompt = build_system_prompt(persona)
    llm = config_manager.get_agent_llm("ops")

    messages: List[BaseMessage] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=instructions),
    ]

    try:
        # 3. Call Aider in Sandbox (Verification Mode)
        aider_instructions = instructions
        if current_step and current_step.verification_criteria:
            aider_instructions += (
                f"\n\nVerification Criteria: {current_step.verification_criteria}"
            )

        # Decide if we should push (only if it's a git-related step or explicitly mentioned)
        skip_push = True
        if current_step and any(
            word in current_step.description.lower()
            for word in ["push", "git", "remote"]
        ):
            skip_push = False
            logger.info("🚀 Step involves git/push. skip_push -> False.")

        # Logic for the last step: always push if successful
        is_last_step = False
        if state.task_plan and state.task_plan.steps:
            if current_step and current_step.id == state.task_plan.steps[-1].id:
                is_last_step = True

        repo_name = state.trigger.repo_name if state.trigger else ""
        repo_url = f"https://github.com/{repo_name}.git" if repo_name else ""

        # Resolve Aider model, region, and thinking
        ops_model = config_manager.get_aider_model_id("ops")
        ops_region = config_manager.get_agent_region("ops")
        thinking = config_manager.get_agent_thinking("ops")
        thinking_budget = config_manager.get_agent_thinking_budget("ops")

        aider_res = await run_aider_in_e2b(
            repo_url=repo_url,
            instructions=aider_instructions,
            fnames=[],  # Ops usually doesn't need to specify files to edit
            branch=state.branch_name,
            model=ops_model,
            sandbox_id=state.sandbox_id,
            run_only=True,
            skip_push=skip_push and not is_last_step,
            is_env_rework=state.is_env_rework,
            system_prompt=system_prompt,
            region=ops_region,
            thinking=thinking,
            thinking_budget=thinking_budget,
        )

        if not aider_res["success"]:
            raise Exception(aider_res.get("error", "Aider failed in sandbox"))

        # 4. Generate Structured TestReport via LLM analysis of Aider output
        logger.info("📋 Finalizing structured TestReport from Aider output...")
        structured_llm = llm.with_structured_output(TestReport)

        # We need to feed the Aider outcome back to the LLM to get a structured report
        aider_outcome_msg = HumanMessage(
            content=f"Aider finished the verification task. SUCCESS: {aider_res['success']}\n"
            f"Sandboxed Aider logs (truncated if too long): {aider_res.get('logs', 'No logs returned')}\n\n"
            "Analyze these results and generate the final structured TestReport. "
            "Focus on actual test failures or dependency issues. Ignore noise from successful installations."
            "If tests failed or critical deps couldn't be installed, succeed should be False."
        )
        messages.append(aider_outcome_msg)

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", category=UserWarning, message=".*Pydantic.*"
            )
            report = cast(
                TestReport,
                await structured_llm.ainvoke(
                    messages,
                    config={**config, "run_name": "Ops: Diagnostic Formulation"},
                ),
            )

        # 5. Extract Branch Name (if a git push occurred)
        # Legacy: ops previously searched for branch name. Now handled by coder.
        branch_name = state.branch_name

        # 6. Populate Execution History
        if current_step:
            status = StepStatus.COMPLETED if report.success else StepStatus.FAILED
            outcome = (
                f"Verification {'Passed' if report.success else 'Failed'}.\n\n"
                f"LOGS:\n{aider_res.get('logs', 'No logs')}\n\n"
                f"SUMMARY: {report.logs or 'None'}"
            )
            history = [
                StepExecutionRecord(
                    step_id=current_step.id,
                    status=status,
                    agent="ops",
                    outcome=outcome,
                )
            ]
            completed_ids = [current_step.id] if report.success else []

        final_msg = AIMessage(
            content=f"Ops Verification {'Passed' if report.success else 'Failed'}: {report.logs or 'No summary'}"
        )
        messages.append(final_msg)

        response_payload: Dict[str, Any] = {
            "messages": [final_msg],
            "validation_report": report,
            "completed_step_ids": completed_ids,
            "execution_history": history,
            "branch_name": branch_name,
            "sandbox_id": state.sandbox_id,
        }

        return response_payload
    except Exception:
        logger.exception("Ops Agent failed unexpectedly")
        await kill_sandbox(state.sandbox_id)
        return {
            "messages": [
                AIMessage(content="Ops Agent failed due to an internal error.")
            ],
            "completed_step_ids": [],
            "execution_history": [],
        }
    finally:
        await resource_manager.cleanup()
