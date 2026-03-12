import sys
import os
from typing import Any
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.pipeline import IngestionPipeline

def run_test():
    pipeline = IngestionPipeline()
    
    # Test with a local PDF first as it's easiest to verify
    test_pdf = os.path.abspath("tests/data/sample.pdf")
    if not os.path.exists(test_pdf):
        print(f"❌ Test PDF not found at {test_pdf}. Skipping PDF test.")
    else:
        print(f"🎬 Processing PDF: {test_pdf}")
        chunks = pipeline.process(test_pdf)
        print(f"✅ Generated {len(chunks)} chunks.")

    # 2. Verify Graph Data
    print("\n🔍 Verifying Kùzu Graph Data...")
    res: Any = pipeline.graph_store.conn.execute("MATCH (n) RETURN COUNT(*)")
    if isinstance(res, list):
        res = res[0]
        
    row = res.get_next()
    count = row[0] if isinstance(row, list) else 0
    print(f"Nodes in Graph: {count}")

    if count > 0:
        print("\n--- Node Samples ---")
        res = pipeline.graph_store.conn.execute("MATCH (n) RETURN labels(n), n.* LIMIT 5")
        if isinstance(res, list):
            res = res[0]
            
        while res.has_next():
            print(res.get_next())

        print("\n--- Relationship Sample (CONTAINS) ---")
        res = pipeline.graph_store.conn.execute("MATCH (a)-[r:CONTAINS]->(b) RETURN labels(a), labels(b) LIMIT 5")
        if isinstance(res, list):
            res = res[0]
            
        while res.has_next():
            print(res.get_next())

if __name__ == "__main__":
    run_test()
