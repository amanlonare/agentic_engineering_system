import asyncio

from src.core.config import settings
from src.ingestion.pipeline import IngestionPipeline


async def main():
    pipeline = IngestionPipeline()
    sources = IngestionPipeline.load_sources_from_yaml(settings.INGESTION_SOURCES_FILE)

    print(f"Loaded {len(sources)} sources from config.")
    for source in sources:
        print(f"Processing: {source}")
        try:
            chunks = await pipeline.process(source)
            print(f"Successfully indexed {len(chunks)} chunks for {source}\n")
        except Exception as e:
            print(f"Failed to process {source}: {e}\n")

    await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())
