import logging

from ..server import mcp, retriever

logger = logging.getLogger(__name__)


@mcp.tool()
async def query_knowledge_base(query: str, n_results: int = 5) -> str:
    """
    Search the knowledge base for semantic and structural context.
    Returns ranked chunks and their graph relationships.
    """
    try:
        result = retriever.retrieve(query, n_results=n_results)

        if not result.contexts:
            return f"No relevant context found for: {query}"

        output = [f"Found {len(result.contexts)} relevant context chunks:\n"]
        for i, ctx in enumerate(result.contexts, 1):
            source = ctx.source_id.split("/")[-1]
            output.append(f"[{i}] {ctx.symbol_name or 'Text'} (Source: {source})")
            if ctx.related_symbols:
                output.append(f"    └── Related to: {', '.join(ctx.related_symbols)}")
            output.append(f"    {ctx.content[:300]}...\n")

        return "\n".join(output)
    except Exception as e:
        logger.error("Failed to query knowledge base: %s", e)
        return f"Error querying knowledge base: {str(e)}"


@mcp.tool()
async def get_file_context(file_path: str) -> str:
    """
    Retrieve all context and relationships for a specific file.
    Useful for understanding a file's role in the architecture.
    """
    try:
        # Note: retriever.graph_store is initialized in ContextRetriever
        siblings = retriever.graph_store.get_file_siblings(file_path)
        if not siblings:
            return f"No context found for file: {file_path}. Has it been indexed?"

        output = [f"Context for {file_path}:\n"]
        for sib in siblings:
            output.append(f"- {sib['symbol_name']} ({sib['chunk_type']})")

        return "\n".join(output)
    except Exception as e:
        logger.error("Failed to get file context: %s", e)
        return f"Error retrieving file context: {str(e)}"


@mcp.tool()
async def summarize_graph_cluster(source_id: str) -> str:
    """
    Provide a high-level overview of a source (repo or doc) using the graph.
    Shows the distribution of symbols and their types.
    """
    try:
        tree = retriever.graph_store.get_source_tree(source_id)
        if not tree:
            return f"No graph data found for source: {source_id}"

        # Group by type
        stats = {}
        files = set()
        for item in tree:
            t = item["chunk_type"]
            stats[t] = stats.get(t, 0) + 1
            files.add(item["document_path"])

        summary = [f"Source Summary for {source_id}:"]
        summary.append(f"- Total Files: {len(files)}")
        summary.append("- Component Distribution:")
        for t, count in stats.items():
            summary.append(f"  └── {t}: {count}")

        return "\n".join(summary)
    except Exception as e:
        logger.error("Failed to summarize graph cluster: %s", e)
        return f"Error summarizing graph: {str(e)}"
