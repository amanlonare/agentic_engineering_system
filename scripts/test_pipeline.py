import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.ingestion.pipeline import IngestionPipeline

import asyncio

from src.core.config import settings

async def main():
    source = sys.argv[1] if len(sys.argv) > 1 else settings.DEFAULT_INGESTION_SOURCE
    
    if not source:
        print("Usage: python scripts/test_pipeline.py <url_or_path>")
        sys.exit(1)
        
    pipeline = IngestionPipeline()
    
    print(f"🎬 Starting processing for: {source}")
    try:
        chunks = await pipeline.process(source)
        print(f"\n✅ Processing complete. Generated {len(chunks)} chunks.")
        
        if chunks:
            print("\nPreview of first chunk:")
            print("=" * 60)
            print(f"Metadata: {chunks[0].metadata}")
            print("-" * 60)
            preview = chunks[0].content[:200]
            print(f"{preview}{'...' if len(chunks[0].content) > 200 else ''}")
            print("=" * 60)
            
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
