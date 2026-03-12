import os
from typing import Optional

from src.core.memory import LongTermMemory
from src.utils.logger import configure_logging

logger = configure_logging()


class WorkspaceManager:
    """
    Manages the repository contexts and helps agents identify which repo to act on.
    Utilizes LongTermMemory for semantic discovery of repositories.
    """

    def __init__(self, context_dir: str = ".context"):
        self.context_dir = context_dir
        self.memory = LongTermMemory(collection_name="workspace_context")

    def index_repositories(self):
        """
        Scans the .context directory and indexes README files into LongTermMemory.
        """
        if not os.path.exists(self.context_dir):
            logger.warning("Context directory %s not found.", self.context_dir)
            return

        for repo_name in os.listdir(self.context_dir):
            repo_path = os.path.join(self.context_dir, repo_name)
            if os.path.isdir(repo_path):
                readme_path = os.path.join(repo_path, "README.md")
                if os.path.exists(readme_path):
                    with open(readme_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        # Index the content with metadata
                        self.memory.store_memory(
                            content=content,
                            metadata={
                                "repo_name": repo_name,
                                "type": "workspace_context",
                            },
                        )
                    logger.info("Indexed workspace context for: %s", repo_name)

    def identify_repository(self, task_description: str) -> Optional[str]:
        """
        Identifies the most relevant repository for a given task description.
        Prioritizes explicit keywords and repository names before falling back to semantic search.
        """
        desc_lower = task_description.lower()

        # 1. Deterministic Keywords
        # If the user mentions "Agentic Team", route to the testing sandbox
        if "agentic team" in desc_lower or "agent team" in desc_lower:
            logger.info(
                "🎯 Routing to 'testing_agentic_engineering_team' via explicit keyword."
            )
            return "testing_agentic_engineering_team"

        # 2. Exact Repo Name Matching
        # If any folder name in .context is mentioned exactly, pick it.
        if os.path.exists(self.context_dir):
            for repo_name in os.listdir(self.context_dir):
                if repo_name.lower() in desc_lower:
                    logger.info(
                        "🎯 Routing to '%s' via exact folder name match.", repo_name
                    )
                    return repo_name

        # 3. Semantic Fallback
        results = self.memory.retrieve_relevant_memories(task_description, k=1)
        if results:
            # Our new CompatibilityDoc stores metadata as a dict
            repo_name = (
                results[0].metadata.get("source_id")
                if hasattr(results[0].metadata, "get")
                else None
            )
            if not repo_name:
                repo_name = results[0].metadata.get("repo_name")

            logger.info(
                "Identified relevant repository: %s for task: %s",
                repo_name,
                task_description[:50],
            )
            return repo_name

        logger.warning(
            "Could not identify a relevant repository for task: %s",
            task_description[:50],
        )
        return None


if __name__ == "__main__":
    # Test indexing and discovery
    wm = WorkspaceManager()
    wm.index_repositories()

    test_tasks = [
        "Fix the login button in the mobile app",
        "Update the S3 upload logic for predicted results",
        "Add a new VPC subnet in AWS",
        "Refactor the LSTM model for better accuracy",
    ]

    for task in test_tasks:
        repo = wm.identify_repository(task)
        print(f"Task: '{task}' -> Repo: {repo}")
