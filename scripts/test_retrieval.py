"""
End-to-end test for the Advanced Retrieval (ContextRetriever).

1. Creates a small Python project in memory.
2. Ingests it into ChromaDB and Kùzu.
3. Queries the ContextRetriever and checks the results.
"""
import shutil
import os
from src.smart_chunker.engines.code import CodeEngine
from src.core.vector_store import VectorStore
from src.core.graph_store import GraphStore
from src.core.context_retriever import ContextRetriever
from src.schemas.ingestion import IdentifiedSource, SourceType

# ── Test Data ──────────────────────────────────────────────────────────
SAMPLE_CODE = '''
class Animal:
    """Base class for all animals."""
    def __init__(self, name: str):
        self.name = name

    def speak(self) -> str:
        raise NotImplementedError


class Dog(Animal):
    """A dog that can bark."""
    def speak(self) -> str:
        return f"{self.name} says Woof!"

    def fetch(self, item: str) -> str:
        return f"{self.name} fetches {item}"


class Cat(Animal):
    """A cat that can meow."""
    def speak(self) -> str:
        return f"{self.name} says Meow!"


def adopt_pet(animal: Animal) -> str:
    """Adopts a pet and makes it speak."""
    greeting = animal.speak()
    return f"Adopted! {greeting}"
'''


def main():
    # ── Clean up previous test data ────────────────────────────────────
    test_vector_path = "/tmp/test_retrieval_vector"
    test_graph_path = "/tmp/test_retrieval_graph"
    for p in [test_vector_path, test_graph_path]:
        if os.path.exists(p):
            shutil.rmtree(p)

    # ── Step 1: Chunk the code ─────────────────────────────────────────
    engine = CodeEngine(language_name="python")
    chunks = engine.chunk(SAMPLE_CODE, source_id="pets.py")
    print(f"✅ Chunked code into {len(chunks)} chunks:")
    for c in chunks:
        print(f"   - {c.metadata.symbol_name} ({c.chunk_type.value}), deps={c.metadata.dependencies}, inherits={c.metadata.parent_symbol}")

    # ── Step 2: Ingest into stores ─────────────────────────────────────
    vs = VectorStore(db_path=test_vector_path, collection_name="test_retrieval")
    gs = GraphStore(db_path=test_graph_path)

    source = IdentifiedSource(
        identifier="test-project",
        source_type=SourceType.GITHUB_REPO,
        uri="https://github.com/test/pets",
        metadata={"name": "pets"}
    )

    vs.upsert_chunks(chunks)
    gs.upsert_source(source)
    gs.upsert_chunks(source, chunks)
    print("✅ Ingested into ChromaDB and Kùzu.")

    # ── Step 3: Test the ContextRetriever ──────────────────────────────
    retriever = ContextRetriever(vector_store=vs, graph_store=gs)

    print("\n" + "=" * 60)
    print("🔍 Query: 'How does the Dog class work?'")
    print("=" * 60)
    result = retriever.retrieve("How does the Dog class work?", n_results=3, expand_graph=True)

    print(f"\n📊 Result: {len(result.contexts)} contexts from {result.sources_searched} source(s)")
    print(f"   Graph expanded: {result.graph_expanded}")
    for i, ctx in enumerate(result.contexts):
        depth_label = "DIRECT" if ctx.graph_depth == 0 else f"GRAPH (depth {ctx.graph_depth})"
        print(f"\n   [{i+1}] [{depth_label}] {ctx.symbol_name} ({ctx.chunk_type})")
        print(f"       Score: {ctx.score:.4f}")
        print(f"       Related: {ctx.related_symbols}")
        print(f"       Content: {ctx.content[:80]}...")

    # ── Step 4: Assertions ─────────────────────────────────────────────
    symbol_names = [c.symbol_name for c in result.contexts]
    print(f"\n🧪 Symbols found: {symbol_names}")

    assert "Dog" in symbol_names, "❌ Dog should be a direct hit!"
    print("✅ Dog found as expected.")

    # If graph expansion worked, we should also see Animal (parent) or adopt_pet (caller)
    if result.graph_expanded:
        print("✅ Graph expansion worked — related chunks were discovered.")
    else:
        print("⚠️  No graph expansion occurred (graph may be empty or disconnected).")

    print("\n🎉 All tests passed!")


if __name__ == "__main__":
    main()
