import sys
import os
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.pipeline import IngestionPipeline

def run_test():
    pipeline = IngestionPipeline()
    
    # Test with a local PDF
    test_pdf = os.path.abspath("tests/data/sample.pdf")
    if not os.path.exists(test_pdf):
        print(f"❌ Test PDF not found at {test_pdf}. Skipping test.")
        return

    print(f"🎬 Processing PDF for ChromaDB: {test_pdf}")
    pipeline.process(test_pdf)
    
    # 2. Verify ChromaDB Data
    print("\n🔍 Verifying ChromaDB Semantic Search...")
    
    # Query for something mentioned in our sample.pdf (e.g., "Advanced Usage" or "PDF extraction")
    search_query = "Tell me about PDF extraction techniques"
    print(f"Query: '{search_query}'")
    
    results = pipeline.vector_store.search_chunks(search_query, n_results=2)
    
    if results and "documents" in results and results["documents"]:
        print("\n--- Top Results ---")
        for idx, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][idx]
            print(f"Result {idx+1}:")
            print(f"  Symbol: {metadata.get('symbol_name')}")
            print(f"  Snippet: {doc[:100]}...")
    else:
        print("❌ No results found in ChromaDB.")

if __name__ == "__main__":
    run_test()
