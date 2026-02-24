import os
from typing import Any, Dict

import yaml


def load_agent_persona(agent_name: str) -> Dict[str, Any]:
    """
    Loads the YAML persona configuration for a given agent.
    """
    # The YAML files are located in src/agents/
    file_path = os.path.join("src", "agents", f"{agent_name}.yaml")

    if not os.path.exists(file_path):
        # Fallback to a default structure if file is missing
        return {
            "name": agent_name,
            "description": f"A specialized agent named {agent_name}.",
            "allowed_tools": [],
            "forbidden_actions": [],
        }

    with open(file_path, "r") as f:
        return yaml.safe_load(f)


def build_system_prompt(persona: Dict[str, Any]) -> str:
    """
    Constructs a strict system prompt from a persona dictionary.
    """
    prompt = f"Identity: {persona.get('name', 'Assistant')}\n"
    prompt += f"Role: {persona.get('description', '')}\n\n"

    tools = persona.get("allowed_tools", [])
    if tools:
        prompt += f"ALLOWED TOOLS: {', '.join(tools)}\n"

    forbidden = persona.get("forbidden_actions", [])
    if forbidden:
        prompt += "\nSTRICT LIMITATIONS (DO NOT EXCEED):\n"
        for item in forbidden:
            prompt += f"- {item}\n"

    return prompt
