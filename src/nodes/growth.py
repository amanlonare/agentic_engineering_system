from typing import Any, Dict, List

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI

from src.core.config import settings
from src.core.state import EngineeringState
from src.schemas import (
    GrowthRecommendation,
    GrowthRecommendationType,
    StepExecutionRecord,
    StepStatus,
)
from src.tools.growth_tools import analyze_prediction_accuracy, detect_activity_trends
from src.tools.codebase_tools import get_restricted_tools
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("growth")

MAX_TOOL_CALLS = 10

def growth_node(state: EngineeringState) -> Dict[str, Any]:
    """
    Growth Agent: Analyzes user metrics and proposes strategies.
    Uses LLM tool-calling to process mobility data.
    """
    logger.info("📈 Growth Agent starting analysis...")

    # 1. Setup Tools & Persona
    repo = state.trigger.repo_name if state.trigger and state.trigger.repo_name else "main-app"
    growth_tools = [analyze_prediction_accuracy, detect_activity_trends]
    # Also add standard codebase tools for context
    code_tools = get_restricted_tools(repo)
    all_tools = growth_tools + code_tools
    
    persona = load_agent_persona("growth")
    system_prompt = build_system_prompt(persona)
    # Inject repo context manually since build_system_prompt doesn't take it
    system_prompt = f"{system_prompt}\n\nTarget Repository Context: {repo}"
    
    llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME, temperature=0)
    llm_with_tools = llm.bind_tools(all_tools)
    
    # 2. Prepare Messages
    messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
    
    # Add relevant history or the current user request
    if state.messages:
        messages.extend(state.messages[-5:]) # Last few messages for context
    else:
        messages.append(HumanMessage(content=f"Analyze mobility performance for {repo}."))

    # 3. Tool-Calling Loop
    logger.info("🤖 Starting tool-calling loop...")
    for _ in range(MAX_TOOL_CALLS):
        response = llm_with_tools.invoke(messages)
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
                result = tool_fn.invoke(tool_args)
                messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
            else:
                messages.append(ToolMessage(content=f"Error: Tool {tool_name} not found.", tool_call_id=tool_call["id"]))

    # 4. Final Structured Output
    logger.info("🎯 Generating final growth recommendation...")
    analyzer_llm = llm.with_structured_output(GrowthRecommendation)
    analysis_input = messages + [HumanMessage(content="Based on your findings, provide the final structured recommendation.")]
    
    # Cast/validate the result
    recommendation_data = analyzer_llm.invoke(analysis_input)
    if isinstance(recommendation_data, dict):
        recommendation = GrowthRecommendation(**recommendation_data)
    else:
        recommendation = recommendation_data

    logger.info("📈 Final Growth Recommendation:\n%s", recommendation.analysis)

    # 5. Track Completion
    completed_ids = []
    history = []
    if state.task_plan:
        for step in state.task_plan.steps:
            if step.assigned_to == "growth" and step.id not in (state.completed_step_ids or []):
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
        "messages": [AIMessage(content=f"### Growth Analysis\n{recommendation.analysis}")],
        "growth_recommendations": [recommendation],
        "completed_step_ids": completed_ids,
        "execution_history": history,
    }
