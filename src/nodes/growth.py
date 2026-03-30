from typing import List, cast

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langfuse import observe

from src.core.config_manager import app_config, config_manager
from src.core.state import EngineeringState
from src.schemas import GrowthRecommendation, StepExecutionRecord, StepStatus
from src.tools.codebase_tools import get_restricted_tools
from src.tools.growth_tools import analyze_prediction_accuracy, detect_activity_trends
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("growth")


@observe(name="Agent: Growth & Analysis")
async def growth_node(
    state: EngineeringState, config: RunnableConfig, **kwargs
) -> dict:
    """
    Growth Agent: Analyzes user metrics and proposes strategies.
    Uses LLM tool-calling to process mobility data.
    """
    logger.info("📈 Growth Agent starting analysis...")

    # 1. Setup Tools & Persona
    repo = (
        state.trigger.repo_name
        if state.trigger and state.trigger.repo_name
        else "main-app"
    )
    growth_tools = [analyze_prediction_accuracy, detect_activity_trends]
    # Also add standard codebase tools for context
    code_tools = get_restricted_tools(repo)
    all_tools = growth_tools + code_tools

    persona = load_agent_persona("growth")
    system_prompt = build_system_prompt(persona)
    # Inject repo context manually since build_system_prompt doesn't take it
    system_prompt = f"{system_prompt}\n\nTarget Repository Context: {repo}"

    llm = config_manager.get_agent_llm("growth", config=config)
    llm_with_tools = llm.bind_tools(all_tools)

    # 2. Prepare Messages
    messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]

    # Add relevant history or the current user request
    if state.messages:
        messages.extend(state.messages[-5:])  # Last few messages for context
    else:
        messages.append(
            HumanMessage(content=f"Analyze mobility performance for {repo}.")
        )

    # 3. Tool-Calling Loop
    logger.info("🤖 Starting tool-calling loop...")
    agent_cfg = app_config.agents.get("growth")
    MAX_TOOL_CALLS = agent_cfg.max_tool_calls if agent_cfg else 10

    for _ in range(MAX_TOOL_CALLS):
        response = await llm_with_tools.ainvoke(
            messages, config={**config, "run_name": "Growth: Data Exploration"}
        )
        messages.append(response)

        if not response.tool_calls:
            break

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            # Find and execute tool
            tool_fn = next((t for t in all_tools if t.name == tool_name), None)
            if tool_fn:
                logger.info(f"🛠️ Executing tool: {tool_name}")
                if hasattr(tool_fn, "ainvoke"):
                    result = await tool_fn.ainvoke(tool_args)
                else:
                    result = tool_fn.invoke(tool_args)
                messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                )
            else:
                messages.append(
                    ToolMessage(
                        content=f"Error: Tool {tool_name} not found.",
                        tool_call_id=tool_call["id"],
                    )
                )

    # Step 4: Final Structured Output
    logger.info("🎯 Generating final growth recommendation...")
    structured_llm = llm.with_structured_output(GrowthRecommendation)
    analysis_input = messages + [
        HumanMessage(
            content="Based on your findings, provide the final structured recommendation."
        )
    ]

    # Cast/validate the result
    recommendation_data = await structured_llm.ainvoke(
        analysis_input, config={**config, "run_name": "Growth: Strategic Delivery"}
    )
    recommendation = cast(GrowthRecommendation, recommendation_data)
    if isinstance(recommendation_data, dict):
        recommendation = GrowthRecommendation(**recommendation_data)

    logger.info("📈 Final Growth Recommendation:\n%s", recommendation.analysis)

    # 5. Track Completion
    completed_ids = []
    history = []
    if state.task_plan:
        for step in state.task_plan.steps:
            if step.assigned_to == "growth" and step.id not in (
                state.completed_step_ids or []
            ):
                completed_ids.append(step.id)
                history.append(
                    StepExecutionRecord(
                        step_id=step.id,
                        status=StepStatus.COMPLETED,
                        agent="growth",
                        outcome=recommendation.analysis,
                    )
                )
                logger.info("✅ Growth completed step: %s", step.id)
                break

    return {
        "messages": [
            AIMessage(content=f"### Growth Analysis\n{recommendation.analysis}")
        ],
        "growth_recommendations": [recommendation],
        "completed_step_ids": completed_ids,
        "execution_history": history,
    }
