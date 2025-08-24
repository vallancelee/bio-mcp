#!/usr/bin/env python3
"""
Simple micro-benchmark for EmbeddingServiceV2 using timeit.

This benchmark uses Python's timeit module for precise timing measurements
with automatic warm-up and statistical analysis.
"""

import os
import warnings

# Suppress transformers warning about missing PyTorch/TensorFlow
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
warnings.filterwarnings("ignore", message=".*PyTorch.*TensorFlow.*Flax.*", category=UserWarning)

import asyncio
import gc
import json
import sys
import timeit
from datetime import datetime

from bio_mcp.config.config import Config
from bio_mcp.models.document import Document
from bio_mcp.services.embedding_service_v2 import EmbeddingServiceV2


class SimpleBenchmark:
    """Simple benchmark using timeit for precise measurements."""
    
    def __init__(self, config: Config = None):
        self.config = config or Config.from_env()
        # Use dedicated test collection
        self.config.weaviate_collection_v2 = "DocumentChunk_v2_benchsimple"
        self.service = None
        self.test_documents = None
        self.test_queries = None
    
    async def setup(self):
        """Initialize service and test data."""
        print("🚀 Setting up benchmark...")
        
        # Initialize service
        self.service = EmbeddingServiceV2(collection_name=self.config.weaviate_collection_v2)
        self.service.config = self.config
        await self.service.connect()
        
        # Clean up existing data
        await self._cleanup()
        
        # Generate test data
        self.test_documents = self._generate_test_documents(20)
        self.test_queries = [
            "biomedical research therapeutic approaches",
            "randomized controlled trial methodology", 
            "statistical analysis experimental design",
            "clinical implementation validation studies",
            "therapeutic efficacy safety profiles"
        ]
        
        # Pre-populate some data for search tests
        print("📋 Pre-populating test data...")
        for i, doc in enumerate(self.test_documents[:10]):
            await self.service.store_document_chunks(doc, quality_score=0.5 + i * 0.05)
        
        print("✅ Setup complete")
    
    async def cleanup(self):
        """Clean up test data and connections."""
        if self.service:
            await self._cleanup()
            await self.service.disconnect()
    
    async def _cleanup(self):
        """Remove test data from collection."""
        for i in range(100):  # Conservative cleanup
            try:
                deleted = await self.service.delete_document_chunks(f"benchsimple:{i}")
                if deleted == 0:
                    break
            except Exception:
                break
    
    def _generate_test_documents(self, count: int) -> list[Document]:
        """Generate test documents."""
        documents = []
        
        base_text = """
        Background: This biomedical research study investigates novel therapeutic approaches 
        for treating complex diseases using advanced methodologies and statistical analysis.
        
        Methods: We conducted a comprehensive randomized controlled trial with rigorous 
        experimental design and data collection protocols to ensure scientific validity.
        
        Results: The experimental intervention demonstrated significant therapeutic efficacy
        with excellent safety profiles and meaningful clinical improvements across endpoints.
        
        Conclusions: This research provides strong evidence supporting the therapeutic approach
        and suggests potential for broader clinical implementation in healthcare settings.
        """
        
        for i in range(count):
            doc = Document(
                uid=f"benchsimple:{i}",
                source="benchsimple",
                source_id=str(i),
                title=f"Benchmark Test Document {i}",
                text=base_text + f" Document ID: {i}.",
                published_at=datetime(2024, 1, 1),
                authors=["Test, A.", "Benchmark, B."],
                identifiers={"doi": f"10.1234/bench.{i}"},
                detail={"journal": "Benchmark Journal", "mesh_terms": ["testing", "benchmark"]}
            )
            documents.append(doc)
        
        return documents
    
    
    async def benchmark_storage(self, iterations: int = 10) -> dict:
        """Benchmark storage operations using precise timing."""
        print(f"📊 Benchmarking storage ({iterations} iterations)...")
        
        measurements = []
        
        for i in range(iterations):
            # Force garbage collection before each measurement
            gc.collect()
            
            doc = self.test_documents[i % len(self.test_documents)]
            
            # Clean state
            await self.service.delete_document_chunks(doc.uid)
            
            # Measure storage operation
            start = timeit.default_timer()
            await self.service.store_document_chunks(doc, quality_score=0.7)
            end = timeit.default_timer()
            
            # Clean up
            await self.service.delete_document_chunks(doc.uid)
            
            time_ms = (end - start) * 1000
            measurements.append(time_ms)
            
            if (i + 1) % 5 == 0:
                print(f"   Completed {i + 1}/{iterations} measurements")
        
        # Calculate statistics
        mean_ms = sum(measurements) / len(measurements)
        min_ms = min(measurements)
        max_ms = max(measurements)
        
        # Calculate operations per second
        ops_per_sec = 1000 / mean_ms
        
        result = {
            "iterations": iterations,
            "mean_ms": mean_ms,
            "min_ms": min_ms, 
            "max_ms": max_ms,
            "ops_per_sec": ops_per_sec,
            "measurements": measurements
        }
        
        print(f"   📈 Storage: {mean_ms:.1f}ms avg, {ops_per_sec:.1f} ops/sec")
        return result
    
    async def benchmark_search(self, iterations: int = 50) -> dict:
        """Benchmark search operations using precise timing."""
        print(f"🔍 Benchmarking search ({iterations} iterations)...")
        
        measurements = []
        
        for i in range(iterations):
            gc.collect()
            
            query = self.test_queries[i % len(self.test_queries)]
            
            # Measure search operation
            start = timeit.default_timer()
            await self.service.search_chunks(query, limit=10)
            end = timeit.default_timer()
            
            time_ms = (end - start) * 1000
            measurements.append(time_ms)
            
            if (i + 1) % 10 == 0:
                print(f"   Completed {i + 1}/{iterations} measurements")
        
        mean_ms = sum(measurements) / len(measurements)
        min_ms = min(measurements)
        max_ms = max(measurements)
        queries_per_sec = 1000 / mean_ms
        
        result = {
            "iterations": iterations,
            "mean_ms": mean_ms,
            "min_ms": min_ms,
            "max_ms": max_ms, 
            "queries_per_sec": queries_per_sec,
            "measurements": measurements
        }
        
        print(f"   📈 Search: {mean_ms:.1f}ms avg, {queries_per_sec:.1f} queries/sec")
        return result
    
    async def benchmark_filtered_search(self, iterations: int = 30) -> dict:
        """Benchmark filtered search operations using precise timing."""
        print(f"🎯 Benchmarking filtered search ({iterations} iterations)...")
        
        measurements = []
        
        filters = [
            {"source_filter": "benchsimple"},
            {"quality_threshold": 0.6},
            {"year_filter": (2024, 2024)},
        ]
        
        for i in range(iterations):
            gc.collect()
            
            query = self.test_queries[i % len(self.test_queries)]
            filter_params = filters[i % len(filters)]
            
            # Measure filtered search operation
            start = timeit.default_timer()
            await self.service.search_chunks(query, limit=10, **filter_params)
            end = timeit.default_timer()
            
            time_ms = (end - start) * 1000
            measurements.append(time_ms)
            
            if (i + 1) % 10 == 0:
                print(f"   Completed {i + 1}/{iterations} measurements")
        
        mean_ms = sum(measurements) / len(measurements) 
        min_ms = min(measurements)
        max_ms = max(measurements)
        queries_per_sec = 1000 / mean_ms
        
        result = {
            "iterations": iterations,
            "mean_ms": mean_ms,
            "min_ms": min_ms,
            "max_ms": max_ms,
            "queries_per_sec": queries_per_sec,
            "measurements": measurements
        }
        
        print(f"   📈 Filtered Search: {mean_ms:.1f}ms avg, {queries_per_sec:.1f} queries/sec")
        return result
    
    def print_summary(self, storage_result: dict, search_result: dict, filtered_result: dict):
        """Print benchmark summary and requirements check."""
        print("\n" + "="*60)
        print("📊 BENCHMARK SUMMARY")
        print("="*60)
        
        # Storage results
        print("📦 STORAGE:")
        print(f"   Average: {storage_result['mean_ms']:.1f} ms")
        print(f"   Rate: {storage_result['ops_per_sec']:.1f} operations/sec")
        storage_pass = storage_result['ops_per_sec'] > 100
        print(f"   Requirement (>100 ops/sec): {'✅ PASS' if storage_pass else '❌ FAIL'}")
        
        # Search results  
        print("\n🔍 SEARCH:")
        print(f"   Average: {search_result['mean_ms']:.1f} ms")
        print(f"   Rate: {search_result['queries_per_sec']:.1f} queries/sec")
        search_rate_pass = search_result['queries_per_sec'] > 10
        search_latency_pass = search_result['mean_ms'] < 100
        print(f"   Requirement (>10 queries/sec): {'✅ PASS' if search_rate_pass else '❌ FAIL'}")
        print(f"   Requirement (<100ms latency): {'✅ PASS' if search_latency_pass else '❌ FAIL'}")
        
        # Filtered search results
        print("\n🎯 FILTERED SEARCH:")
        print(f"   Average: {filtered_result['mean_ms']:.1f} ms") 
        print(f"   Rate: {filtered_result['queries_per_sec']:.1f} queries/sec")
        
        # Overall assessment
        all_requirements_met = storage_pass and search_rate_pass and search_latency_pass
        print(f"\n🎯 OVERALL: {'✅ ALL REQUIREMENTS MET' if all_requirements_met else '❌ SOME REQUIREMENTS FAILED'}")
        
        return all_requirements_met


async def main():
    """Run simple benchmark suite."""
    print("🧪 BioBERT Embedding Service V2 Simple Benchmark")
    print("Using Python timeit for precise measurements")
    print("=" * 60)
    
    benchmark = SimpleBenchmark()
    
    try:
        await benchmark.setup()
        
        # Run benchmarks with precise timing
        storage_result = await benchmark.benchmark_storage(iterations=10)
        search_result = await benchmark.benchmark_search(iterations=50) 
        filtered_result = await benchmark.benchmark_filtered_search(iterations=30)
        
        # Print summary
        all_pass = benchmark.print_summary(storage_result, search_result, filtered_result)
        
        # Save results
        results = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "biobert_model": benchmark.config.biobert_model_name,
                "collection": benchmark.config.weaviate_collection_v2
            },
            "results": {
                "storage": storage_result,
                "search": search_result,
                "filtered_search": filtered_result
            },
            "requirements_met": all_pass
        }
        
        results_file = f"simple_benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Results saved to: {results_file}")
        
        # Exit with appropriate code
        sys.exit(0 if all_pass else 1)
        
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        await benchmark.cleanup()


if __name__ == "__main__":
    asyncio.run(main())