import sys
from src.ingestion.pipeline import IngestionPipeline

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_pipeline.py <url_or_path>")
        sys.exit(1)
        
    source = sys.argv[1]
    pipeline = IngestionPipeline()
    
    print(f"🎬 Starting processing for: {source}")
    try:
        chunks = pipeline.process(source)
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
    main()
