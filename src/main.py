"""
Entry point for the Agentic Engineering System.
"""

from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver

from src.core.config import settings
from src.core.graph import build_graph
from src.core.state import EngineeringState
from src.schemas import TriggerContext, TriggerType
from src.utils.logger import configure_logging

logger = configure_logging()


import uuid
from datetime import datetime
from src.core.workspace import WorkspaceManager

def main():
    """Application entry point."""
    logger.info("🚀 Starting Agentic Engineering System (Interactive Mode)...")

    # Initialize WorkspaceManager forrepo discovery
    wm = WorkspaceManager()

    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    with SqliteSaver.from_conn_string(db_path) as memory:
        graph = build_graph(memory)

        while True:
            try:
                user_input = input("\n👤 User Request (or 'exit'): ")
                if user_input.lower() in ["exit", "quit"]:
                    break
                
                if not user_input.strip():
                    continue

                # 1. Identify the repository from the query
                repo = wm.identify_repository(user_input)
                
                # 2. Create a unique thread ID for this specific task
                thread_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:4]}"
                config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

                # 3. Initialize state with the dynamic trigger and identified repo
                initial_state = EngineeringState(
                    messages=[],
                    trigger=TriggerContext(
                        type=TriggerType.MANUAL,
                        payload={"description": user_input},
                        repo_name=repo
                    )
                )

                logger.info("🧵 Thread ID: %s", thread_id)
                logger.info("🔍 Target Repo: %s", repo if repo else "General/Multiple")

                # 4. Invoke the graph
                for event in graph.stream(initial_state, config):
                    for node_name, node_state in event.items():
                        logger.info(f"--- Finished node: {node_name} ---")
                        # We log internal status, but in a real CLI we might filter this
                        if "next_action" in node_state:
                            logger.info(f"Supervisor Decision: {node_state['next_action']}")

                logger.info("✅ Task Processing Complete.")

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("Error in main loop: %s", str(e))

    logger.info("👋 System Shutdown.")


if __name__ == "__main__":
    main()
