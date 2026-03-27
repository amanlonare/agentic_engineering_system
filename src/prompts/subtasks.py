# src/prompts/subtasks.py

PLANNING_SLUG_EXTRACTOR = """
Extract a concise 2-4 word kebab-case slug from the following task description 
that captures the core technical action. Output ONLY the slug, nothing else. 
Example: 'implement fibonacci' → 'fibonacci-series'. 
Example: 'add user authentication to the backend api' → 'user-auth-api'. 
Task: {task_description}
"""

PLANNING_FINAL_PLAN = """
Please generate the TechnicalPlan now.
IMPORTANT: Do NOT create steps for git branch creation, git commit, or git push — these are handled automatically.
IMPORTANT: For 'target_repo', use the full identifier '{repo}' (owner/repo) for all steps.
"""

OPS_DIAGNOSTIC_REPORT = """
Aider finished the verification task. SUCCESS: {success}
Sandboxed Aider logs (truncated if too long): {logs}

Analyze these results and generate the final structured TestReport. 
Focus on actual test failures or dependency issues. Ignore noise from successful installations. 
If tests failed or critical deps couldn't be installed, succeed should be False.
"""
