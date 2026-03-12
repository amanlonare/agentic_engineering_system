"""
Advanced Retrieval: Graph-Augmented RAG.

Combines ChromaDB semantic search with Kùzu graph traversal to provide
richer, more relevant context to agents.
"""

import logging
from typing import Any, Dict, List, Optional

from src.core.graph_store import GraphStore
from src.core.vector_store import VectorStore
from src.schemas.retrieval import RetrievalResult, RetrievedContext

logger = logging.getLogger(__name__)


class ContextRetriever:
    """
    Hybrid retrieval engine.

    Flow:
      1. Vector Search (ChromaDB) → find semantically similar chunks.
      2. Graph Expansion (Kùzu)   → follow edges to discover related chunks.
      3. Merge & Re-rank          → deduplicate, score, and assemble context.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        graph_store: Optional[GraphStore] = None,
    ):
        self.vector_store = vector_store or VectorStore()
        self.graph_store = graph_store or GraphStore()

    # ── Public API ─────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        n_results: int = 5,
        expand_graph: bool = True,
        max_hops: int = 1,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        """
        Main entry point.

        Args:
            query:        Natural-language query.
            n_results:    Number of initial vector hits.
            expand_graph: Whether to follow graph edges for extra context.
            max_hops:     How many relationship hops to follow.
            filters:      Optional ChromaDB metadata filters.

        Returns:
            A RetrievalResult with ranked contexts.
        """
        # Step 1 ─ Vector Search
        if filters:
            raw = self.vector_store.search_chunks_filtered(query, filters, n_results)
        else:
            raw = self.vector_store.search_chunks(query, n_results)

        direct_contexts = self._parse_vector_results(raw)
        logger.info("Vector search returned %d direct hits.", len(direct_contexts))

        # Step 2 ─ Graph Expansion
        graph_contexts: List[RetrievedContext] = []
        if expand_graph and direct_contexts:
            seen_ids = {c.chunk_id for c in direct_contexts}
            for ctx in direct_contexts:
                if not ctx.chunk_id:
                    continue
                # Related via USES / INHERITS / CONTAINS
                neighbors = self.graph_store.get_related_chunks(ctx.chunk_id, max_hops)
                for nb in neighbors:
                    nb_id = nb["chunk_id"]
                    if nb_id not in seen_ids:
                        seen_ids.add(nb_id)
                        expanded = self._fetch_chunk_content(nb_id, nb, graph_depth=1)
                        if expanded:
                            # Record which direct-hit symbol led us here
                            expanded.related_symbols.append(ctx.symbol_name)
                            graph_contexts.append(expanded)

                # Siblings in the same file
                siblings = self.graph_store.get_file_siblings(ctx.chunk_id)
                for sib in siblings:
                    sib_id = sib["chunk_id"]
                    if sib_id not in seen_ids:
                        seen_ids.add(sib_id)
                        expanded = self._fetch_chunk_content(sib_id, sib, graph_depth=1)
                        if expanded:
                            expanded.related_symbols.append(ctx.symbol_name)
                            graph_contexts.append(expanded)

            logger.info("Graph expansion added %d extra contexts.", len(graph_contexts))

        # Step 3 ─ Merge & Re-rank
        all_contexts = direct_contexts + graph_contexts
        all_contexts.sort(key=lambda c: c.score)

        unique_sources = {c.source_id for c in all_contexts}

        return RetrievalResult(
            query=query,
            contexts=all_contexts,
            sources_searched=len(unique_sources),
            graph_expanded=expand_graph and len(graph_contexts) > 0,
        )

    # ── Internal helpers ───────────────────────────────────────────────

    def _parse_vector_results(self, raw: Any) -> List[RetrievedContext]:
        """Converts raw ChromaDB query results into RetrievedContext objects."""
        contexts: List[RetrievedContext] = []
        if not raw or "documents" not in raw or not raw["documents"]:
            return contexts

        documents = raw["documents"][0]
        metadatas = (
            raw["metadatas"][0] if raw.get("metadatas") else [{}] * len(documents)
        )
        distances = (
            raw["distances"][0] if raw.get("distances") else [0.0] * len(documents)
        )
        ids = raw["ids"][0] if raw.get("ids") else [""] * len(documents)

        for i, doc in enumerate(documents):
            meta = metadatas[i] if i < len(metadatas) else {}
            ctx = RetrievedContext(
                content=doc,
                source_id=meta.get("source_id", ""),
                chunk_id=ids[i] if i < len(ids) else "",
                symbol_name=meta.get("symbol_name", ""),
                chunk_type=meta.get("chunk_type", ""),
                language=meta.get("language", "unknown"),
                score=distances[i] if i < len(distances) else 0.0,
                graph_depth=0,
            )
            contexts.append(ctx)

        return contexts

    def _fetch_chunk_content(
        self, chunk_id: str, graph_info: dict, graph_depth: int
    ) -> Optional[RetrievedContext]:
        """Looks up a chunk's full content from ChromaDB given its graph-discovered ID."""
        result = self.vector_store.get_chunk_by_id(chunk_id)
        if not result:
            return None

        meta = result.get("metadata", {})
        return RetrievedContext(
            content=result.get("content", ""),
            source_id=meta.get("source_id", ""),
            chunk_id=chunk_id,
            symbol_name=graph_info.get("symbol_name", meta.get("symbol_name", "")),
            chunk_type=graph_info.get("chunk_type", meta.get("chunk_type", "")),
            language=meta.get("language", "unknown"),
            score=1.0,  # Graph-discovered items get a neutral score
            graph_depth=graph_depth,
        )
