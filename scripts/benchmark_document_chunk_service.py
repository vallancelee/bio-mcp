#!/usr/bin/env python3
"""
Simple microbenchmark for DocumentChunkService with OpenAI embeddings.
Includes warmup and basic timing measurements.
"""

import asyncio
import json
import time
from datetime import datetime

from bio_mcp.config.config import Config
from bio_mcp.models.document import Document
from bio_mcp.services.document_chunk_service import DocumentChunkService


class DocumentChunkBenchmark:
    """Simple benchmark for DocumentChunkService."""

    def __init__(self):
        self.config = Config.from_env()
        # Use test collection
        self.collection_name = "DocumentChunk_benchmark_" + datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        self.service = DocumentChunkService(collection_name=self.collection_name)
        self.service.config = self.config

    async def setup(self):
        """Initialize service."""
        print(f"🚀 Setting up benchmark with collection: {self.collection_name}")
        await self.service.connect()
        print("✅ Connected to Weaviate")

    async def cleanup(self):
        """Clean up test data."""
        print("🧹 Cleaning up...")
        try:
            # Delete test collection if possible
            if hasattr(self.service.schema_manager, "drop_collection"):
                await self.service.schema_manager.drop_collection(self.collection_name)
        except Exception as e:
            print(f"Note: Cleanup warning: {e}")
        await self.service.disconnect()

    def create_test_documents(self, count: int = 5):
        """Create test documents."""
        documents = []
        for i in range(count):
            doc = Document(
                uid=f"benchmark:{i:04d}",
                source="benchmark",
                source_id=f"{i:04d}",
                title=f"Biomedical Research Study {i + 1}",
                text=f"Background: This comprehensive study investigates molecular mechanisms in diabetes treatment. "
                f"Methods: We used randomized controlled trials with {100 + i * 50} patients. "
                f"Results: Treatment showed {85 + i}% efficacy with significant p-values (p<0.001). "
                f"Conclusions: This research provides evidence for clinical applications.",
            )
            documents.append(doc)
        return documents

    async def warmup(self):
        """Warmup the service with a few operations."""
        print("🔥 Warming up...")
        warmup_doc = Document(
            uid="warmup:001",
            source="warmup",
            source_id="001",
            title="Warmup Document",
            text="This is a warmup document to initialize connections and caches.",
        )

        # Warmup storage
        await self.service.store_document_chunks(warmup_doc)

        # Warmup search
        await self.service.search_chunks("warmup", limit=5)

        print("✅ Warmup complete")

    async def benchmark_storage(self, documents):
        """Benchmark document storage."""
        print(f"\n📊 Benchmarking storage of {len(documents)} documents...")

        start_time = time.time()
        total_chunks = 0

        for i, doc in enumerate(documents):
            doc_start = time.time()
            chunk_ids = await self.service.store_document_chunks(doc, quality_score=0.8)
            doc_time = time.time() - doc_start
            total_chunks += len(chunk_ids)
            print(f"  Doc {i + 1}: {len(chunk_ids)} chunks in {doc_time:.3f}s")

        total_time = time.time() - start_time

        return {
            "documents": len(documents),
            "chunks": total_chunks,
            "total_time": total_time,
            "chunks_per_sec": total_chunks / total_time,
            "docs_per_sec": len(documents) / total_time,
        }

    async def benchmark_search(self, queries):
        """Benchmark search performance."""
        print(f"\n🔍 Benchmarking {len(queries)} search queries...")

        start_time = time.time()

        for i, query in enumerate(queries):
            query_start = time.time()
            results = await self.service.search_chunks(
                query, limit=10, search_mode="hybrid"
            )
            query_time = time.time() - query_start
            print(
                f"  Query {i + 1}: '{query}' -> {len(results)} results in {query_time:.3f}s"
            )

        total_time = time.time() - start_time

        return {
            "queries": len(queries),
            "total_time": total_time,
            "queries_per_sec": len(queries) / total_time,
        }

    async def run_benchmark(self):
        """Run complete benchmark."""
        try:
            await self.setup()
            await self.warmup()

            # Test with small document count for reasonable API costs
            documents = self.create_test_documents(5)  # 5 docs ≈ $0.005

            # Storage benchmark
            storage_results = await self.benchmark_storage(documents)

            # Search benchmark
            queries = [
                "diabetes treatment",
                "molecular mechanisms",
                "clinical trials",
                "randomized controlled",
                "significant efficacy",
            ]
            search_results = await self.benchmark_search(queries)

            # Print results
            print("\n" + "=" * 50)
            print("📈 BENCHMARK RESULTS")
            print("=" * 50)
            print(f"Model: {self.config.openai_embedding_model}")
            print(f"Storage: {storage_results['chunks_per_sec']:.1f} chunks/sec")
            print(f"Search: {search_results['queries_per_sec']:.1f} queries/sec")
            print(f"Total chunks: {storage_results['chunks']}")

            # Save results
            results = {
                "timestamp": datetime.now().isoformat(),
                "model": self.config.openai_embedding_model,
                "storage": storage_results,
                "search": search_results,
            }

            filename = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, "w") as f:
                json.dump(results, f, indent=2)
            print(f"📁 Results saved to: {filename}")

        finally:
            await self.cleanup()


async def main():
    """Run the benchmark."""
    benchmark = DocumentChunkBenchmark()
    await benchmark.run_benchmark()


if __name__ == "__main__":
    asyncio.run(main())
