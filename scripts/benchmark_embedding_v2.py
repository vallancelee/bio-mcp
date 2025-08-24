#!/usr/bin/env python3
"""
Benchmark EmbeddingServiceV2 performance with BioBERT.

This script validates the performance requirements:
- Storage: >100 chunks/second
- Search: >10 queries/second with quality boosting
- Memory: <500MB peak usage for embedding service
- Latency: <100ms average search response time
"""

import asyncio
import gc
import json
import statistics
import sys
import time
from datetime import datetime

import psutil

from bio_mcp.config.config import Config
from bio_mcp.models.document import Document
from bio_mcp.services.embedding_service_v2 import EmbeddingServiceV2


class PerformanceBenchmark:
    """Performance benchmark for EmbeddingServiceV2."""
    
    def __init__(self, config: Config = None):
        self.config = config or Config.from_env()
        # Use a dedicated test collection
        self.config.weaviate_collection_v2 = "DocumentChunk_v2_benchmark"
        
        self.service = None
        self.process = psutil.Process()
        self.initial_memory = None
        
    async def initialize(self):
        """Initialize the embedding service for benchmarking."""
        print("🚀 Initializing EmbeddingServiceV2 for benchmarking...")
        
        # Record initial memory
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        self.service = EmbeddingServiceV2(collection_name=self.config.weaviate_collection_v2)
        self.service.config = self.config
        
        await self.service.connect()
        print(f"✅ Connected to Weaviate collection: {self.service.collection_name}")
        
        # Clean up any existing benchmark data
        try:
            await self._cleanup_benchmark_data()
        except Exception as e:
            print(f"⚠️  Warning during cleanup: {e}")
    
    async def cleanup(self):
        """Cleanup benchmark resources."""
        if self.service:
            try:
                await self._cleanup_benchmark_data()
            except Exception as e:
                print(f"⚠️  Warning during final cleanup: {e}")
            
            await self.service.disconnect()
    
    async def _cleanup_benchmark_data(self):
        """Remove all benchmark test data."""
        print("🧹 Cleaning up benchmark data...")
        
        # Delete all test documents
        for i in range(100):  # Conservative upper limit
            try:
                deleted = await self.service.delete_document_chunks(f"benchmark:{i}")
                if deleted > 0:
                    print(f"   Deleted {deleted} chunks for document {i}")
            except Exception:
                break  # No more documents to delete
    
    def generate_test_documents(self, count: int) -> list[Document]:
        """Generate test documents for benchmarking."""
        documents = []
        
        # Template texts with different characteristics
        templates = [
            {
                "title": "Efficacy of Novel Biomarker {i} in Cancer Detection",
                "text": "Background: Cancer remains a leading cause of mortality worldwide, necessitating improved diagnostic approaches. This study investigates biomarker {i} for early detection. Methods: We conducted a multi-center randomized controlled trial with 1,000 participants across different demographics. Results: The biomarker showed 95% sensitivity and 92% specificity (p<0.001). Diagnostic accuracy was significantly improved compared to standard methods. Conclusions: Biomarker {i} represents a promising advance in cancer screening protocols.",
                "journal": "Cancer Research",
                "mesh_terms": ["biomarkers", "cancer", "diagnosis", "screening"]
            },
            {
                "title": "Therapeutic Intervention {i} for Cardiovascular Disease",
                "text": "Background: Cardiovascular disease affects millions globally, requiring innovative treatment approaches. We evaluated intervention {i} in clinical settings. Methods: Double-blind placebo-controlled trial enrolled 2,500 patients with established cardiovascular risk factors. Treatment duration was 12 months with comprehensive monitoring. Results: Primary endpoint reduction of 35% was observed (HR 0.65, CI 0.52-0.81, p<0.001). Secondary endpoints also showed significant improvement. Conclusions: Intervention {i} demonstrates substantial clinical benefit for cardiovascular protection.",
                "journal": "Circulation",
                "mesh_terms": ["cardiovascular", "therapy", "clinical trial", "intervention"]
            },
            {
                "title": "Machine Learning Model {i} for Drug Discovery",
                "text": "Background: Artificial intelligence is transforming pharmaceutical research through advanced computational approaches. We developed model {i} for accelerated drug discovery. Methods: Training dataset included 50,000 molecular structures with known biological activities. Deep learning architecture employed graph neural networks. Results: Prediction accuracy reached 89% on validation set with 78% improvement over traditional methods (p<0.001). Processing time reduced from weeks to hours. Conclusions: Model {i} offers significant potential for streamlining drug development pipelines.",
                "journal": "Nature Biotechnology",
                "mesh_terms": ["machine learning", "drug discovery", "artificial intelligence", "pharmaceuticals"]
            }
        ]
        
        for i in range(count):
            template = templates[i % len(templates)]
            
            doc = Document(
                uid=f"benchmark:{i}",
                source="benchmark",
                source_id=str(i),
                title=template["title"].format(i=i),
                text=template["text"].format(i=i),
                published_at=datetime(2024, 1, 1 + (i % 30)),  # Spread across month
                authors=[f"Author_{i%10}, A.", f"Researcher_{i%7}, B."],
                identifiers={"doi": f"10.1234/benchmark.{i}"},
                detail={
                    "journal": template["journal"],
                    "mesh_terms": template["mesh_terms"]
                }
            )
            documents.append(doc)
        
        return documents
    
    async def benchmark_storage(self, documents: list[Document]) -> dict:
        """Benchmark document storage performance."""
        print(f"\n📊 Benchmarking storage performance ({len(documents)} documents)...")
        
        start_time = time.time()
        start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        total_chunks = 0
        storage_times = []
        
        for i, doc in enumerate(documents):
            doc_start = time.time()
            
            # Add quality score variation
            quality_score = 0.5 + (i % 5) * 0.1  # Vary between 0.5-0.9
            
            chunk_uuids = await self.service.store_document_chunks(doc, quality_score)
            
            doc_end = time.time()
            storage_times.append(doc_end - doc_start)
            total_chunks += len(chunk_uuids)
            
            if (i + 1) % 10 == 0:
                print(f"   Processed {i+1}/{len(documents)} documents...")
        
        end_time = time.time()
        end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        elapsed = end_time - start_time
        
        # Force garbage collection and get peak memory
        gc.collect()
        peak_memory = max(end_memory, self.process.memory_info().rss / 1024 / 1024)
        
        result = {
            "documents_processed": len(documents),
            "total_chunks": total_chunks,
            "elapsed_seconds": elapsed,
            "docs_per_second": len(documents) / elapsed,
            "chunks_per_second": total_chunks / elapsed,
            "avg_chunks_per_doc": total_chunks / len(documents),
            "avg_storage_time_ms": statistics.mean(storage_times) * 1000,
            "median_storage_time_ms": statistics.median(storage_times) * 1000,
            "memory_start_mb": start_memory,
            "memory_end_mb": end_memory,
            "memory_peak_mb": peak_memory,
            "memory_increase_mb": end_memory - start_memory
        }
        
        return result
    
    async def benchmark_search(self, queries: list[str], iterations: int = 5) -> dict:
        """Benchmark search performance with multiple iterations."""
        print(f"\n🔍 Benchmarking search performance ({len(queries)} queries, {iterations} iterations each)...")
        
        all_search_times = []
        all_results_count = []
        query_results = {}
        
        for iteration in range(iterations):
            print(f"   Iteration {iteration + 1}/{iterations}...")
            
            for query in queries:
                search_start = time.time()
                
                # Test with various filter combinations
                if iteration % 3 == 0:
                    results = await self.service.search_chunks(query, limit=10)
                elif iteration % 3 == 1:
                    results = await self.service.search_chunks(
                        query, limit=10, source_filter="benchmark"
                    )
                else:
                    results = await self.service.search_chunks(
                        query, limit=10, quality_threshold=0.6
                    )
                
                search_end = time.time()
                search_time = search_end - search_start
                
                all_search_times.append(search_time)
                all_results_count.append(len(results))
                
                if query not in query_results:
                    query_results[query] = []
                query_results[query].append(search_time)
        
        total_queries = len(queries) * iterations
        total_time = sum(all_search_times)
        
        result = {
            "total_queries": total_queries,
            "total_results": sum(all_results_count),
            "elapsed_seconds": total_time,
            "queries_per_second": total_queries / total_time,
            "avg_latency_ms": statistics.mean(all_search_times) * 1000,
            "median_latency_ms": statistics.median(all_search_times) * 1000,
            "p95_latency_ms": sorted(all_search_times)[int(len(all_search_times) * 0.95)] * 1000,
            "p99_latency_ms": sorted(all_search_times)[int(len(all_search_times) * 0.99)] * 1000,
            "avg_results_per_query": statistics.mean(all_results_count),
            "query_breakdown": {
                query: {
                    "avg_latency_ms": statistics.mean(times) * 1000,
                    "min_latency_ms": min(times) * 1000,
                    "max_latency_ms": max(times) * 1000
                }
                for query, times in query_results.items()
            }
        }
        
        return result
    
    async def benchmark_quality_boosting(self) -> dict:
        """Benchmark quality-based scoring and ranking."""
        print("\n⭐ Benchmarking quality boosting performance...")
        
        # Search for content that should match documents with different quality scores
        test_queries = [
            "biomarker cancer detection",
            "cardiovascular intervention therapy",
            "machine learning drug discovery"
        ]
        
        quality_results = []
        
        for query in test_queries:
            results = await self.service.search_chunks(query, limit=20)
            
            if results:
                # Analyze score distribution by quality
                quality_groups = {}
                for result in results:
                    quality = result.get("quality_total", 0.0)
                    quality_bucket = round(quality * 10) / 10  # Round to 0.1
                    
                    if quality_bucket not in quality_groups:
                        quality_groups[quality_bucket] = []
                    
                    quality_groups[quality_bucket].append({
                        "score": result["score"],
                        "base_score": result["base_score"],
                        "quality_boost": result["quality_boost"]
                    })
                
                quality_results.append({
                    "query": query,
                    "quality_groups": quality_groups,
                    "total_results": len(results)
                })
        
        return {
            "queries_tested": len(test_queries),
            "quality_analysis": quality_results
        }
    
    def check_requirements(self, storage_result: dict, search_result: dict) -> dict:
        """Check if performance meets requirements."""
        requirements = {
            "storage_chunks_per_sec": {
                "requirement": "> 100 chunks/sec",
                "actual": storage_result["chunks_per_second"],
                "passed": storage_result["chunks_per_second"] > 100
            },
            "search_queries_per_sec": {
                "requirement": "> 10 queries/sec",
                "actual": search_result["queries_per_second"],
                "passed": search_result["queries_per_second"] > 10
            },
            "memory_peak_usage": {
                "requirement": "< 500MB peak",
                "actual": storage_result["memory_peak_mb"],
                "passed": storage_result["memory_peak_mb"] < 500
            },
            "search_avg_latency": {
                "requirement": "< 100ms average",
                "actual": search_result["avg_latency_ms"],
                "passed": search_result["avg_latency_ms"] < 100
            }
        }
        
        all_passed = all(req["passed"] for req in requirements.values())
        
        return {
            "all_requirements_met": all_passed,
            "requirements": requirements
        }
    
    def print_results(self, storage_result: dict, search_result: dict, quality_result: dict, requirements: dict):
        """Print comprehensive benchmark results."""
        print("\n" + "="*80)
        print("🎯 BIOBERT EMBEDDING SERVICE V2 BENCHMARK RESULTS")
        print("="*80)
        
        # Storage Performance
        print("\n📦 STORAGE PERFORMANCE:")
        print(f"   Documents processed: {storage_result['documents_processed']:,}")
        print(f"   Total chunks: {storage_result['total_chunks']:,}")
        print(f"   Avg chunks/doc: {storage_result['avg_chunks_per_doc']:.1f}")
        print(f"   Processing time: {storage_result['elapsed_seconds']:.2f}s")
        print(f"   👉 Storage rate: {storage_result['chunks_per_second']:.1f} chunks/sec")
        print(f"   Avg storage time: {storage_result['avg_storage_time_ms']:.1f}ms/doc")
        
        # Memory Usage
        print("\n💾 MEMORY USAGE:")
        print(f"   Initial memory: {storage_result['memory_start_mb']:.1f} MB")
        print(f"   Final memory: {storage_result['memory_end_mb']:.1f} MB")
        print(f"   👉 Peak memory: {storage_result['memory_peak_mb']:.1f} MB")
        print(f"   Memory increase: {storage_result['memory_increase_mb']:.1f} MB")
        
        # Search Performance
        print("\n🔍 SEARCH PERFORMANCE:")
        print(f"   Total queries: {search_result['total_queries']:,}")
        print(f"   Total time: {search_result['elapsed_seconds']:.2f}s")
        print(f"   👉 Search rate: {search_result['queries_per_second']:.1f} queries/sec")
        print(f"   👉 Avg latency: {search_result['avg_latency_ms']:.1f}ms")
        print(f"   Median latency: {search_result['median_latency_ms']:.1f}ms")
        print(f"   P95 latency: {search_result['p95_latency_ms']:.1f}ms")
        print(f"   P99 latency: {search_result['p99_latency_ms']:.1f}ms")
        print(f"   Avg results/query: {search_result['avg_results_per_query']:.1f}")
        
        # Quality Boosting
        print("\n⭐ QUALITY BOOSTING:")
        print(f"   Queries analyzed: {quality_result['queries_tested']}")
        for analysis in quality_result['quality_analysis']:
            print(f"   '{analysis['query']}': {analysis['total_results']} results")
        
        # Requirements Check
        print("\n✅ REQUIREMENTS VALIDATION:")
        for name, req in requirements['requirements'].items():
            status = "✅ PASS" if req['passed'] else "❌ FAIL"
            print(f"   {status} {name}: {req['requirement']} (actual: {req['actual']:.1f})")
        
        overall_status = "✅ ALL REQUIREMENTS MET" if requirements['all_requirements_met'] else "❌ SOME REQUIREMENTS FAILED"
        print(f"\n🎯 OVERALL: {overall_status}")


async def main():
    """Run the complete benchmark suite."""
    print("🧪 BioBERT Embedding Service V2 Performance Benchmark")
    print("=" * 60)
    
    benchmark = PerformanceBenchmark()
    
    try:
        await benchmark.initialize()
        
        # Generate test data
        test_documents = benchmark.generate_test_documents(10)  # Small test size for now
        test_queries = [
            "biomarker cancer detection sensitivity",
            "cardiovascular intervention clinical trial",
            "machine learning drug discovery model",
            "therapeutic efficacy randomized controlled",
            "diagnostic accuracy screening protocol",
            "pharmaceutical artificial intelligence",
            "molecular structure biological activity",
            "clinical benefit cardiovascular protection",
            "computational approach drug development",
            "biomedical research innovative treatment"
        ]
        
        # Run benchmarks
        storage_result = await benchmark.benchmark_storage(test_documents)
        search_result = await benchmark.benchmark_search(test_queries, iterations=3)
        quality_result = await benchmark.benchmark_quality_boosting()
        
        # Check requirements
        requirements = benchmark.check_requirements(storage_result, search_result)
        
        # Print results
        benchmark.print_results(storage_result, search_result, quality_result, requirements)
        
        # Save detailed results
        detailed_results = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "biobert_model": benchmark.config.biobert_model_name,
                "collection": benchmark.config.weaviate_collection_v2,
                "test_documents": len(test_documents),
                "test_queries": len(test_queries)
            },
            "storage": storage_result,
            "search": search_result,
            "quality": quality_result,
            "requirements": requirements
        }
        
        # Save to file
        results_file = f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(detailed_results, f, indent=2, default=str)
        
        print(f"\n💾 Detailed results saved to: {results_file}")
        
        # Exit with appropriate code
        sys.exit(0 if requirements['all_requirements_met'] else 1)
        
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        await benchmark.cleanup()


if __name__ == "__main__":
    asyncio.run(main())