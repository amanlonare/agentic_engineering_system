import hashlib
from typing import List

from tree_sitter_languages import get_language, get_parser

from src.smart_chunker.base import BaseEngine
from src.smart_chunker.schemas import Chunk, ChunkMetadata, ChunkType


class CodeEngine(BaseEngine):
    """
    Code chunking engine using Tree-sitter.
    Extracts classes and functions as atomic chunks with rich metadata.
    Supported: Python, Java, Kotlin.
    TODO: Add Swift, Dart (Archetype application is in Dart).
    """

    def __init__(self, language_name: str = "python"):
        self.language_name = language_name
        self.language = get_language(language_name)
        self.parser = get_parser(language_name)

    def chunk(self, content: str, source_id: str, **_kwargs) -> List[Chunk]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node

        chunks = []
        # Query for classes and functions
        if self.language_name == "python":
            query_scm = """
            (class_definition 
                name: (identifier) @name
                superclasses: (argument_list)? @inherits
            ) @class
            (function_definition 
                name: (identifier) @name
            ) @func
            """
        elif self.language_name == "java":
            query_scm = """
            (class_declaration 
                name: (identifier) @name
            ) @class
            (method_declaration 
                name: (identifier) @name
            ) @func
            """
        elif self.language_name == "kotlin":
            query_scm = """
            (class_declaration 
                (type_identifier) @name
            ) @class
            (function_declaration 
                (simple_identifier) @name
            ) @func
            """
        else:
            # Fallback/Generic
            query_scm = """
            (class_definition name: (identifier) @name) @class
            (function_definition name: (identifier) @name) @func
            """

        query = self.language.query(query_scm)
        captures = query.captures(root_node)

        # Sort captures by start byte to process top-level items properly
        # Note: tree-sitter captures can be nested. We want to identify the "atoms".

        processed_nodes = set()
        chunk_idx = 0

        for node, tag in captures:
            if tag in ["class", "func"] and node.id not in processed_nodes:
                # Basic extraction
                start_byte = node.start_byte
                end_byte = node.end_byte
                chunk_content = content[start_byte:end_byte]

                # Metadata extraction
                name_node = node.child_by_field_name(
                    "name"
                ) or node.child_by_field_name("identifier")
                symbol_name = self._get_node_text(name_node, content)

                # Signature extraction
                signature_end = content.find("\n", start_byte)
                if signature_end == -1 or signature_end > end_byte:
                    signature_end = end_byte
                signature = content[start_byte:signature_end].strip()

                # Extract local dependencies (imports used in this node)
                dependencies = self._extract_dependencies(node, content, symbol_name)

                # Check for inheritance (for classes)
                inherits = []
                if tag == "class":
                    arg_list = node.child_by_field_name(
                        "superclasses"
                    ) or node.child_by_field_name("interfaces")
                    if arg_list:
                        inherits = [
                            self._get_node_text(n, content)
                            for n in arg_list.children
                            if n.type in ["identifier", "type_identifier"]
                        ]

                metadata = ChunkMetadata(
                    source_id=source_id,
                    chunk_index=str(chunk_idx),
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    symbol_name=symbol_name,
                    signature=signature,
                    language=self.language_name,
                    parent_symbol=", ".join(inherits) if inherits else None,
                    dependencies=dependencies,
                )

                # Handle large chunks via recursive splitting
                limit = _kwargs.get("max_chars", 1500)
                if len(chunk_content) > limit:
                    sub_chunks = self._recursive_split(
                        chunk_content,
                        symbol_name,
                        signature,
                        metadata,
                        limit,
                        ChunkType.CLASS if tag == "class" else ChunkType.FUNCTION,
                    )
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(
                        Chunk(
                            content=chunk_content,
                            chunk_type=(
                                ChunkType.CLASS
                                if tag == "class"
                                else ChunkType.FUNCTION
                            ),
                            metadata=metadata,
                            hash=hashlib.md5(chunk_content.encode()).hexdigest(),
                        )
                    )

                chunk_idx += 1
                processed_nodes.add(node.id)

        return chunks

    def _recursive_split(
        self,
        content: str,
        name: str,
        signature: str,
        base_metadata: ChunkMetadata,
        max_chars: int,
        chunk_type: ChunkType,
    ) -> List[Chunk]:
        """Splits a large chunk into smaller ones, prepending the signature for context."""
        lines = content.split("\n")
        sub_chunks = []
        current_batch = [signature, "# ... (continued)"]
        current_len = len(signature) + len("# ... (continued)")

        sub_idx = 0
        for line in lines[1:]:  # Skip the first line as it's handled by signature
            if current_len + len(line) > max_chars and len(current_batch) > 2:
                sub_content = "\n".join(current_batch)
                meta = base_metadata.model_copy(deep=True)
                meta.chunk_index = f"{base_metadata.chunk_index}.{sub_idx}"
                sub_chunks.append(
                    Chunk(
                        content=sub_content,
                        chunk_type=chunk_type,
                        metadata=meta,
                        hash=hashlib.md5(sub_content.encode()).hexdigest(),
                    )
                )
                sub_idx += 1
                current_batch = [signature, f"# ... (continued from {name})", line]
                current_len = len(signature) + len(line) + 20
            else:
                current_batch.append(line)
                current_len += len(line) + 1

        # Final batch
        if len(current_batch) > 2:
            sub_content = "\n".join(current_batch)
            meta = base_metadata.model_copy(deep=True)
            meta.chunk_index = f"{base_metadata.chunk_index}.{sub_idx}"
            sub_chunks.append(
                Chunk(
                    content=sub_content,
                    chunk_type=chunk_type,
                    metadata=meta,
                    hash=hashlib.md5(sub_content.encode()).hexdigest(),
                )
            )

        return sub_chunks

    def _extract_dependencies(self, node, content: str, self_name: str) -> List[str]:
        """
        Extracts identifiers that look like dependencies (CamelCase or calls) within the node.
        """
        if self.language_name == "python":
            query_scm = """
            (call function: (identifier) @call)
            (attribute attribute: (identifier) @attr)
            (identifier) @id
            """
        elif self.language_name == "java":
            query_scm = """
            (method_invocation name: (identifier) @call)
            (field_access field: (identifier) @attr)
            (identifier) @id
            """
        elif self.language_name == "kotlin":
            query_scm = """
            (call_expression (simple_identifier) @call)
            (navigation_expression (simple_identifier) @attr)
            (simple_identifier) @id
            """
        else:
            query_scm = "(identifier) @id"

        query = self.language.query(query_scm)
        captures = query.captures(node)

        deps = set()
        for n, tag in captures:
            text = self._get_node_text(n, content)
            if not text or text == self_name:
                continue

            if text[0].isupper() and len(text) > 1:
                deps.add(text)
            elif tag == "call":
                deps.add(text)

        return sorted(list(deps))

    def _get_node_text(self, node, content: str) -> str:
        if not node:
            return ""
        return content[node.start_byte : node.end_byte]
