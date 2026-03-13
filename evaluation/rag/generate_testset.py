import os
import json
import asyncio
from typing import List

# Add src to path
import sys
sys.path.append(os.getcwd())

from ragas.testset import TestsetGenerator
from ragas.testset.synthesizers import default_query_distribution
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from src.core.vector_store import VectorStore

async def generate_testset():
    print("🧠 Initializing Ragas Testset Generator (v0.4.x)...")
    
    # Load documents from our isolated evaluation collection
    from src.core.config import settings
    vector_store = VectorStore(
        db_path=settings.EVAL_CHROMA_DB_PATH,
        collection_name=settings.EVAL_CHROMA_COLLECTION_NAME
    )
    results = vector_store.collection.get(include=["documents", "metadatas"])
    
    if not results or not results["documents"]:
        print("❌ No documents found in ChromaDB collection 'eval_rag_chunks'.")
        return

    # Convert to LangChain Document format for Ragas
    from langchain_core.documents import Document as LCDocument
    documents = []
    
    # Explicitly handle metadatas to satisfy Pyright
    raw_metadatas = results.get("metadatas")
    # Use a list of empty dicts if metadatas is None
    metadatas_list = raw_metadatas if raw_metadatas is not None else [{} for _ in results["documents"]]
    
    for content, metadata in zip(results["documents"], metadatas_list):
        # Filter out empty content
        if content and content.strip():
            documents.append(LCDocument(page_content=content, metadata=metadata or {}))
    
    print(f"📄 Loaded {len(documents)} document chunks for generation.")

    # 2. Setup LLMs (using gpt-4o-mini as requested)
    from src.core.config import settings
    
    if not settings.OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY not found in settings. Please check your .env file.")
        return

    from pydantic import SecretStr
    generator_llm = ChatOpenAI(
        model="gpt-4o-mini", 
        api_key=SecretStr(settings.OPENAI_API_KEY)
    )
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small", 
        api_key=SecretStr(settings.OPENAI_API_KEY)
    )

    # 3. Create Generator
    generator = TestsetGenerator.from_langchain(
        llm=generator_llm,
        embedding_model=embeddings
    )

    # 4. Generate
    print("⚡ Generating testset (this may take a few minutes)...")
    result = generator.generate_with_langchain_docs(
        documents=documents,
        testset_size=10
    )

    # In 0.4.x, generate_with_langchain_docs returns Testset | Executor
    from ragas.testset.synthesizers.testset_schema import Testset
    from typing import cast
    
    if isinstance(result, Testset):
        testset = result
    else:
        # If it's an executor, we need to gather samples and wrap them
        print("⏳ Waiting for executor to finish...")
        samples = result.results()
        testset = Testset(samples=samples)

    # 5. Save results
    output_path = "evaluation/data/rag_testset.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Ragas 0.4.x Testset object can be converted to pandas
    test_df = testset.to_pandas()
    test_df.to_json(output_path, orient="records", indent=4)
    
    print(f"✅ Testset generated and saved to {output_path}")

if __name__ == "__main__":
    asyncio.run(generate_testset())
