import sys
import os
import argparse

# Add project root to path
sys.path.append(os.getcwd())

from src.core.tracing import get_langfuse_client
from src.utils.config_loader import load_agent_persona, build_system_prompt
from src.prompts.supervisor import SUPERVISOR_SYSTEM_PROMPT
from src.prompts.subtasks import PLANNING_SLUG_EXTRACTOR, PLANNING_FINAL_PLAN, OPS_DIAGNOSTIC_REPORT

def sync_prompts(promote: bool = False):
    """
    Syncs local prompts to Langfuse.
    """
    lf = get_langfuse_client()
    
    # Define mapping of Langfuse name to local content resolver
    prompts_to_sync = {
        "supervisor-system": lambda: SUPERVISOR_SYSTEM_PROMPT,
        "planning-system": lambda: build_system_prompt(load_agent_persona("planning")),
        "planning-slug-extractor": lambda: PLANNING_SLUG_EXTRACTOR,
        "planning-final-plan": lambda: PLANNING_FINAL_PLAN,
        "coder-system": lambda: build_system_prompt(load_agent_persona("coder")),
        "ops-system": lambda: build_system_prompt(load_agent_persona("ops")),
        "ops-diagnostic-report": lambda: OPS_DIAGNOSTIC_REPORT,
    }

    labels = ["latest"]
    if promote:
        labels.append("production")

    print(f"🔄 Syncing prompts to Langfuse (labels: {labels})...")

    for name, resolver in prompts_to_sync.items():
        try:
            content = resolver()
            lf.create_prompt(
                name=name,
                prompt=content,
                labels=labels
            )
            print(f"✅ Synced: {name}")
        except Exception as e:
            print(f"❌ Failed to sync {name}: {e}")

    print("\n✨ Sync complete. View your prompts at: https://cloud.langfuse.com")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync local prompts to Langfuse.")
    parser.add_argument("--promote", action="store_true", help="Automatically promote synced prompts to 'production' label.")
    args = parser.parse_args()
    
    sync_prompts(promote=args.promote)
