import asyncio
import uuid
from datetime import datetime

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.core.config import settings
from src.core.config_manager import app_config
from src.core.graph import build_graph
from src.core.state import EngineeringState
from src.core.tracing import auth_check, flush, get_langfuse_handler
from src.schemas import TriggerContext, TriggerType
from src.utils.logger import configure_logging

logger = configure_logging()


async def main():
    """Application entry point."""
    logger.info("🚀 Starting Agentic Engineering System (Interactive Mode)...")

    if auth_check():
        logger.info("🔗 Langfuse connected successfully.")
    else:
        logger.warning("⚠️ Langfuse keys missing or invalid. Tracing will be disabled.")

    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    try:
        async with AsyncSqliteSaver.from_conn_string(db_path) as memory:
            graph = build_graph(memory)

            while True:
                try:
                    # We use asyncio to run input in a thread to keep the loop responsive
                    user_input = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input("\n👤 User Request (or 'exit'): ")
                    )
                    if user_input.lower() in ["exit", "quit"]:
                        break

                    if not user_input.strip():
                        continue

                    # 1. Create a unique thread ID for this specific task
                    thread_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:4]}"

                    # Initialize Langfuse tracing via CallbackHandler
                    handler = get_langfuse_handler(session_id=thread_id)
                    callbacks: list[BaseCallbackHandler] = [handler] if handler else []

                    config: RunnableConfig = {
                        "configurable": {"thread_id": thread_id},
                        "callbacks": callbacks,
                        "metadata": {
                            "langfuse_session_id": thread_id,
                            "langfuse_user_id": "cli-user",
                            "name": f"AES: {user_input[:50]}...",
                        },
                    }

                    # 2. Initialize state with the dynamic trigger
                    initial_state = EngineeringState(
                        messages=[HumanMessage(content=user_input)],
                        trigger=TriggerContext(
                            type=TriggerType.MANUAL,
                            payload={"description": user_input, "thread_id": thread_id},
                            repo_name=None,
                        ),
                    )

                    logger.info("🧵 Thread ID: %s", thread_id)

                    # 3. Invoke the graph asynchronously
                    # Tracing is handled automatically by the CallbackHandler in 'config'
                    try:
                        async for event in graph.astream(initial_state, config):
                            for node_name, node_state in event.items():
                                if node_state is None:
                                    continue
                                logger.info(f"--- Finished node: {node_name} ---")

                                # Print agent messages for the user to see
                                if "messages" in node_state and node_state["messages"]:
                                    last_msg = node_state["messages"][-1]
                                    if hasattr(last_msg, "content"):
                                        content = last_msg.content
                                        # Truncate if too long (unless it's a planning node) for cleaner CLI output
                                        MAX_DISPLAY = app_config.system.log_snippet_size
                                        if (
                                            len(content) > MAX_DISPLAY
                                            and "PLANNING" not in node_name.upper()
                                        ):
                                            content = (
                                                content[:MAX_DISPLAY]
                                                + f"\n... (truncated to {MAX_DISPLAY} chars, see full logs for details)"
                                            )
                                        print(f"\n🤖 [{node_name}]:\n{content}\n")

                                # We log internal status, but in a real CLI we might filter this
                                if node_state.get("next_action"):
                                    logger.info(
                                        f"Supervisor Decision: {node_state['next_action']}"
                                    )
                    except Exception as graph_err:
                        logger.error("Error during graph execution: %s", str(graph_err))

                    logger.info("✅ Task Processing Complete.")

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    # Truncate extremely long error messages for readability
                    err_str = str(e)
                    if len(err_str) > 1000:
                        err_str = err_str[:1000] + "..."
                    logger.error("Error in main loop: %s", err_str)

    finally:
        flush()
        logger.info("👋 System Shutdown. Traces flushed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
