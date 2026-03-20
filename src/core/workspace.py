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

    def __init__(self):
        from src.core.config import settings
        from src.core.graph_store import GraphStore

        self.memory = LongTermMemory(collection_name="workspace_context")
        self.graph_store = GraphStore()
        self.dynamic_enabled = settings.DYNAMIC_WORKSPACE_ENABLED

    def get_org_summary(self) -> str:
        """
        Retrieves a hierarchical summary of all repositories in the organization,
        including key documents and symbols from the Graph DB.
        This provides high-level structural context to the Supervisor agent.
        """
        logger.info("Retrieving hierarchical org summary from GraphStore...")
        try:
            results = self.graph_store.execute_query("MATCH (r:Repository) RETURN r.name, r.type")
            if not results:
                return "No repositories found in organization."
            
            summary_lines = []
            for r in results:
                name, rtype = r[0], r[1]
                if rtype and rtype != "Unknown":
                    summary_lines.append(f"📂 {name} ({rtype})")
                else:
                    summary_lines.append(f"📂 {name}")
                
                # Fetch the doc/symbol structure for this repo
                structure = self.graph_store.get_repo_structure(name)
                
                if structure:
                    # Sort by number of symbols descending, keep top 10
                    structure.sort(key=lambda x: len(x.get("symbols", [])), reverse=True)
                    top_docs = structure[:10]
                    
                    for doc in top_docs:
                        doc_path = doc["document_path"]
                        # Just show the basename for brevity to save tokens
                        basename = doc_path.split("/")[-1] if "/" in doc_path else doc_path
                        
                        # Extract unique symbol names, ignore "unknown", limit to 5
                        symbols = []
                        for s in doc.get("symbols", []):
                            s_name = s.get("name")
                            if s_name and s_name.lower() != "unknown" and s_name not in symbols:
                                symbols.append(s_name)
                        
                        symbol_str = ""
                        if symbols:
                            display_symbols = symbols[:5]
                            if len(symbols) > 5:
                                display_symbols.append("...")
                            symbol_str = f" — [{', '.join(display_symbols)}]"
                            
                        summary_lines.append(f"  📄 {basename}{symbol_str}")
                    
                    if len(structure) > 10:
                        summary_lines.append(f"  ... and {len(structure) - 10} more files. (Use codebase_tools for deep inspection)")
                summary_lines.append("") # Empty line between repos
            
            return "\n".join(summary_lines).strip()
        except Exception as e:
            logger.error("Failed to retrieve org summary: %s", e)
            return "Organization repositories currently unavailable."

    async def identify_repository(self, task_description: str) -> Optional[str]:
        """
        Identifies the most relevant repository for a given task description.
        Prioritizes:
        1. Semantic Search (Vector)
        2. Graph Lookup (multi-keyword structural metadata)
        3. Dynamic String Match (all repos queried from GraphStore)
        """
        logger.info("🔍 Identifying repository for task: %s", task_description[:50])
        
        # 1. Semantic Discovery via memory (includes remote repos if indexed)
        results = self.memory.retrieve_relevant_memories(task_description, k=5)
        
        # Debug logging of top results
        for i, res in enumerate(results):
            logger.debug("Vector Match %d (score unknown): %s - Content: %s...", i+1, res.metadata.get('repo_name'), res.page_content[:50])

        for res in results:
            repo_name = res.metadata.get("repo_name")
            if repo_name:
                logger.info("🎯 Identified repository (Vector): %s", repo_name)
                return repo_name

        # 2. Graph Lookup (Search for nodes labeled 'Repository' matching terms in task)
        logger.info("Searching GraphStore for repository matches...")
        
        # Extract keywords (ignore short words)
        keywords = [w.lower() for w in task_description.split() if len(w) > 3]
        
        for term in keywords:
            graph_results = self.graph_store.execute_query(
                "MATCH (r:Repository) WHERE r.name CONTAINS $term RETURN r.name",
                {"term": term}
            )
            if graph_results:
                repo_name = graph_results[0][0]
                logger.info("🎯 Identified repository (Graph match on '%s'): %s", term, repo_name)
                return repo_name

        # 3. Exact Match Fallback
        # Dynamically list all repos from graph if vector/keyword failed
        all_repos = self.graph_store.execute_query("MATCH (r:Repository) RETURN r.name")
        repo_list = [r[0] for r in all_repos] if all_repos else []
        
        for r in repo_list:
            if r.lower() in task_description.lower():
                logger.info("🎯 Identified repository (String Match): %s", r)
                return r

        logger.warning("Could not identify a relevant repository for task.")
        return None


if __name__ == "__main__":
    # Test discovery
    import asyncio
    wm = WorkspaceManager()

    test_tasks = [
        "Fix the login button in the mobile app",
        "Update the S3 upload logic for predicted results",
        "Add a new VPC subnet in AWS",
        "Refactor the LSTM model for better accuracy",
    ]

    async def run_tests():
        for task in test_tasks:
            repo = await wm.identify_repository(task)
            print(f"Task: '{task}' -> Repo: {repo}")

    asyncio.run(run_tests())
