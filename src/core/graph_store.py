import logging
import os
from typing import Any, List

import kuzu

from src.core.config import settings
from src.schemas.ingestion import IdentifiedSource
from src.smart_chunker.schemas import Chunk

logger = logging.getLogger(__name__)


class GraphStore:
    """
    Wrapper for Kùzu Graph Database to store structural relationships.
    """

    def __init__(self, db_path: str = settings.KUZU_DB_PATH):
        # Ensure the parent directory exists
        parent_dir = os.path.dirname(db_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self._initialize_schema()

    def _initialize_schema(self):
        """Initializes the graph schema (Node and Rel tables)."""
        # We cast to Any to satisfy Pyright as Kuzu's return types are dynamic
        res: Any = self.conn.execute("CALL SHOW_TABLES() RETURN name")
        if isinstance(res, list):
            res = res[0]

        tables = []
        while res.has_next():
            row = res.get_next()
            if isinstance(row, list) and len(row) > 0:
                tables.append(row[0])
            elif isinstance(row, dict):
                # Handle dict if returned
                tables.append(row.get("name"))

        # Node Tables
        if "Source" not in tables:
            self.conn.execute(
                "CREATE NODE TABLE Source(id STRING, type STRING, PRIMARY KEY(id))"
            )
        if "Document" not in tables:
            self.conn.execute(
                "CREATE NODE TABLE Document(path STRING, language STRING, PRIMARY KEY(path))"
            )
        if "Chunk" not in tables:
            self.conn.execute(
                "CREATE NODE TABLE Chunk(chunk_id STRING, symbol_name STRING, chunk_type STRING, PRIMARY KEY(chunk_id))"
            )

        # Rel Tables
        if "CONTAINS" not in tables:
            # First hops
            self.conn.execute(
                "CREATE REL TABLE CONTAINS(FROM Source TO Document, FROM Document TO Chunk, FROM Chunk TO Chunk)"
            )
        if "INHERITS" not in tables:
            self.conn.execute("CREATE REL TABLE INHERITS(FROM Chunk TO Chunk)")
        if "USES" not in tables:
            self.conn.execute("CREATE REL TABLE USES(FROM Chunk TO Chunk)")

    def upsert_source(self, source: IdentifiedSource):
        """Idempotently adds a Source node."""
        query = "MERGE (s:Source {id: $id}) SET s.type = $type"
        self.conn.execute(
            query, {"id": source.identifier, "type": source.source_type.value}
        )

    def upsert_chunks(self, source: IdentifiedSource, chunks: List[Chunk]):
        """
        Idempotently adds Document and Chunk nodes and their relationships.
        Uses a two-pass approach to ensure all target nodes exist before creating reference edges.
        """
        # Pass 1: Create all nodes and structural relationships (CONTAINS)
        for chunk in chunks:
            doc_path = chunk.metadata.source_id
            lang = chunk.metadata.language or "unknown"

            # Ensure Document node exists
            self.conn.execute(
                "MERGE (d:Document {path: $path}) SET d.language = $lang",
                {"path": doc_path, "lang": lang},
            )

            # Link Source to Document
            self.conn.execute(
                "MATCH (s:Source {id: $src_id}), (d:Document {path: $doc_path}) "
                "MERGE (s)-[:CONTAINS]->(d)",
                {"src_id": source.identifier, "doc_path": doc_path},
            )

            # Create Chunk node
            chunk_id = f"{doc_path}#{chunk.metadata.chunk_index}"
            self.conn.execute(
                "MERGE (c:Chunk {chunk_id: $id}) "
                "SET c.symbol_name = $name, c.chunk_type = $type",
                {
                    "id": chunk_id,
                    "name": chunk.metadata.symbol_name or "unknown",
                    "type": chunk.chunk_type.value,
                },
            )

            # Link Document/Parent to Chunk
            self.conn.execute(
                "MATCH (d:Document {path: $doc_path}), (c:Chunk {chunk_id: $chunk_id}) "
                "MERGE (d)-[:CONTAINS]->(c)",
                {"doc_path": doc_path, "chunk_id": chunk_id},
            )

        # Pass 2: Create reference relationships (INHERITS, USES)
        for chunk in chunks:
            doc_path = chunk.metadata.source_id
            chunk_id = f"{doc_path}#{chunk.metadata.chunk_index}"

            if chunk.metadata.parent_symbol:
                # Heuristic: look for symbol in the same file or across the whole source
                self.conn.execute(
                    "MATCH (c:Chunk {chunk_id: $id}), (parent:Chunk {symbol_name: $parent_name}) "
                    "WHERE parent.chunk_id STARTS WITH $prefix "
                    "MERGE (c)-[:INHERITS]->(parent)",
                    {
                        "id": chunk_id,
                        "parent_name": chunk.metadata.parent_symbol,
                        "prefix": source.identifier,
                    },
                )

            for dep in chunk.metadata.dependencies:
                self.conn.execute(
                    "MATCH (c:Chunk {chunk_id: $id}), (target:Chunk {symbol_name: $dep_name}) "
                    "WHERE target.chunk_id STARTS WITH $prefix "
                    "MERGE (c)-[:USES]->(target)",
                    {"id": chunk_id, "dep_name": dep, "prefix": source.identifier},
                )

    # ── Query / Traversal Methods ──────────────────────────────────────

    def get_related_chunks(self, chunk_id: str, max_hops: int = 1) -> List[dict]:
        """
        Finds chunks related to the given chunk_id via USES, INHERITS, or CONTAINS edges.
        Returns a list of dicts with chunk_id, symbol_name, chunk_type, and depth.
        """
        results: List[dict] = []
        try:
            query = (
                "MATCH (start:Chunk {chunk_id: $id})-[r:USES|INHERITS|CONTAINS*1.."
                + str(max_hops)
                + "]->(neighbor:Chunk) "
                "RETURN DISTINCT neighbor.chunk_id, neighbor.symbol_name, neighbor.chunk_type"
            )
            res: Any = self.conn.execute(query, {"id": chunk_id})
            if isinstance(res, list):
                res = res[0]
            while res.has_next():
                row = res.get_next()
                if isinstance(row, list) and len(row) >= 3:
                    results.append(
                        {
                            "chunk_id": row[0],
                            "symbol_name": row[1],
                            "chunk_type": row[2],
                        }
                    )
        except Exception as e:
            logger.warning("Graph traversal failed for %s: %s", chunk_id, e)
        return results

    def get_file_siblings(self, chunk_id: str) -> List[dict]:
        """
        Finds all chunks that belong to the same Document as the given chunk.
        """
        results: List[dict] = []
        try:
            query = (
                "MATCH (d:Document)-[:CONTAINS]->(sibling:Chunk), "
                "(d)-[:CONTAINS]->(target:Chunk {chunk_id: $id}) "
                "WHERE sibling.chunk_id <> $id "
                "RETURN DISTINCT sibling.chunk_id, sibling.symbol_name, sibling.chunk_type"
            )
            res: Any = self.conn.execute(query, {"id": chunk_id})
            if isinstance(res, list):
                res = res[0]
            while res.has_next():
                row = res.get_next()
                if isinstance(row, list) and len(row) >= 3:
                    results.append(
                        {
                            "chunk_id": row[0],
                            "symbol_name": row[1],
                            "chunk_type": row[2],
                        }
                    )
        except Exception as e:
            logger.warning("File sibling query failed for %s: %s", chunk_id, e)
        return results

    def get_source_tree(self, source_id: str) -> List[dict]:
        """
        Returns all Documents and Chunks under a given Source.
        """
        results: List[dict] = []
        try:
            query = (
                "MATCH (s:Source {id: $id})-[:CONTAINS]->(d:Document)-[:CONTAINS]->(c:Chunk) "
                "RETURN d.path, c.chunk_id, c.symbol_name, c.chunk_type"
            )
            res: Any = self.conn.execute(query, {"id": source_id})
            if isinstance(res, list):
                res = res[0]
            while res.has_next():
                row = res.get_next()
                if isinstance(row, list) and len(row) >= 4:
                    results.append(
                        {
                            "document_path": row[0],
                            "chunk_id": row[1],
                            "symbol_name": row[2],
                            "chunk_type": row[3],
                        }
                    )
        except Exception as e:
            logger.warning("Source tree query failed for %s: %s", source_id, e)
        return results

    def get_schema(self) -> str:
        """
        Returns a detailed structural schema of the graph,
        including node/rel tables, properties, and relationship connections.
        """
        try:
            # 1. Get all table names and types
            res: Any = self.conn.execute("CALL SHOW_TABLES() RETURN name, type")
            if isinstance(res, list):
                res = res[0]

            node_tables = []
            rel_tables = []
            while res.has_next():
                row = res.get_next()
                if row[1].upper() == "NODE":
                    node_tables.append(row[0])
                else:
                    rel_tables.append(row[0])

            output = ["### Kùzu Knowledge Graph Schema ###\n"]

            # 2. Node Tables
            output.append("## NODE TABLES")
            for table in node_tables:
                output.append(f"### {table}")
                try:
                    info_res: Any = self.conn.execute(
                        f"CALL TABLE_INFO('{table}') RETURN *"
                    )
                    if isinstance(info_res, list):
                        info_res = info_res[0]

                    col_names = []
                    try:
                        col_names = [c.lower() for c in info_res.get_column_names()]
                    except Exception:
                        pass

                    while info_res.has_next():
                        row = info_res.get_next()
                        p_name, p_type, is_pk = "unknown", "unknown", False

                        if col_names:
                            if "name" in col_names:
                                p_name = row[col_names.index("name")]
                            if "type" in col_names:
                                p_type = row[col_names.index("type")]
                            # In some 0.11.x, the column name might be 'is_primary_key' or 'primary_key'
                            pk_idx = next(
                                (i for i, c in enumerate(col_names) if "primary" in c),
                                -1,
                            )
                            if pk_idx != -1:
                                is_pk = row[pk_idx] is True
                        else:
                            # SDK Source confirms: row[1] is name, row[2] is type, row[4] is PK
                            if len(row) > 1:
                                p_name = row[1]
                            if len(row) > 2:
                                p_type = row[2]
                            if len(row) > 4:
                                is_pk = row[4] is True

                        pk_str = " (PRIMARY KEY)" if is_pk else ""
                        output.append(f"  - {p_name}: {p_type}{pk_str}")
                except Exception as e:
                    output.append(f"  - (Error fetching table info: {e})")
                output.append("")

            # 3. Relationship Tables
            output.append("## RELATIONSHIP TABLES")
            for table in rel_tables:
                output.append(f"### {table}")

                # Get properties
                try:
                    info_res: Any = self.conn.execute(
                        f"CALL TABLE_INFO('{table}') RETURN *"
                    )
                    if isinstance(info_res, list):
                        info_res = info_res[0]
                    while info_res.has_next():
                        row = info_res.get_next()
                        output.append(f"  - {row[1]}: {row[2]}")
                except Exception:
                    pass

                # Get connections (FROM/TO) using show_connection('table')
                try:
                    conn_res: Any = self.conn.execute(
                        f"CALL SHOW_CONNECTION('{table}') RETURN *"
                    )
                    if isinstance(conn_res, list):
                        conn_res = conn_res[0]

                    while conn_res.has_next():
                        c_row = conn_res.get_next()
                        # SDK Source confirms: row[0] is src, row[1] is dst
                        if len(c_row) >= 2:
                            output.append(
                                f"  - CONNECTION: ({c_row[0]}) -> ({c_row[1]})"
                            )
                except Exception as e:
                    logger.warning(
                        "Could not retrieve connection info for %s: %s", table, e
                    )
                    output.append(f"  - (Connection info unavailable: {e})")
                output.append("")

            return "\n".join(output)
        except Exception as e:
            logger.error("Failed to retrieve graph schema: %s", e)
            return f"Error retrieving detailed schema: {str(e)}"
