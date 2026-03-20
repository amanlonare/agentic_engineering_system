from src.utils.config_loader import load_agent_persona

# Few-shot examples are maintained in Python for easy manipulation of placeholders
# but the core instructions now reside in src/agents/supervisor.yaml
FEW_SHOT_EXAMPLES = """
Example 1: User says "Update the JWT token generation"
  → Thought: "JWT token" relates to auth/security. Checking <org_summary>, I see 'org/backend-service' has 'src/auth/security.py' containing 'create_access_token'.
  → reasoning: "The user needs to update JWT generation. Found 'create_access_token' in the security module of 'org/backend-service'."
  → target_repo: "org/backend-service"
  → Complexity: Complex → route to PLANNING

Example 2: User says "What is the weather today?"
  → Thought: Not related to any org repo
  → reasoning: "User is asking about weather which is off-topic."
  → rejection_message: "I appreciate your question, but our engineering system is designed to work on tasks related to our organization's repositories. I'm unable to help with general queries."
  → Return FINISH
"""

def _load_supervisor_prompt() -> str:
    """Loads the supervisor system prompt from the YAML persona file."""
    persona = load_agent_persona("supervisor")
    # Injected into the template via supervisor_node.ainvoke
    prompt_template = persona.get("system_prompt", "")
    
    # We pre-fill the few_shot_examples since they are static within a session
    # but keep {org_summary} as a placeholder for the real-time graph lookup.
    return prompt_template.replace("{few_shot_examples}", FEW_SHOT_EXAMPLES)

# Exported for use in src/core/supervisor.py
SUPERVISOR_SYSTEM_PROMPT = _load_supervisor_prompt()
