#!/usr/bin/env python3
"""
Benchmark chunking performance.

Tests chunking speed, memory usage, and scalability with different document sizes
and configurations.
"""

import argparse
import gc
import time
from datetime import datetime
from statistics import mean, stdev
from typing import Any

import psutil

from bio_mcp.models.document import Document
from bio_mcp.services.chunking import AbstractChunker, ChunkingConfig


def generate_synthetic_documents(count: int, size: str = "medium") -> list[Document]:
    """Generate synthetic documents for benchmarking."""
    
    base_texts = {
        "small": "This is a small document for testing. " * 20,  # ~120 words
        "medium": "This is a medium-sized document for performance testing. " * 100,  # ~600 words  
        "large": "This is a large document for comprehensive performance testing. " * 500,  # ~3000 words
        "xlarge": "This is an extra large document for stress testing performance. " * 1000,  # ~6000 words
    }
    
    structured_template = """Background: {base_text}
Objective: To evaluate the performance characteristics of the chunking system under various loads.
Methods: {base_text}
Results: {base_text} 
Conclusions: {base_text}"""
    
    documents = []
    base_text = base_texts.get(size, base_texts["medium"])
    
    for i in range(count):
        # Mix structured and unstructured
        if i % 3 == 0:
            text = structured_template.format(base_text=base_text)
            title = f"Structured Document {i+1}: Performance Analysis"
        else:
            text = base_text
            title = f"Unstructured Document {i+1}: Benchmark Test"
            
        doc = Document(
            uid=f"benchmark:{i+1}",
            source="benchmark",
            source_id=str(i+1),
            title=title,
            text=text,
            published_at=datetime(2024, 1, 1),
            detail={"synthetic": True, "size": size}
        )
        documents.append(doc)
    
    return documents


def measure_memory_usage():
    """Get current memory usage in MB."""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


def benchmark_chunking_speed(documents: list[Document], config: ChunkingConfig, iterations: int = 3) -> dict[str, Any]:
    """Benchmark chunking speed with multiple iterations."""
    
    chunker = AbstractChunker(config)
    times = []
    chunk_counts = []
    
    print(f"   🔄 Running {iterations} iterations...")
    
    for i in range(iterations):
        gc.collect()  # Clear memory before each run
        start_memory = measure_memory_usage()
        start_time = time.perf_counter()
        
        total_chunks = 0
        for doc in documents:
            chunks = chunker.chunk_document(doc)
            total_chunks += len(chunks)
        
        end_time = time.perf_counter()
        end_memory = measure_memory_usage()
        
        elapsed = end_time - start_time
        times.append(elapsed)
        chunk_counts.append(total_chunks)
        
        print(f"      Iteration {i+1}: {elapsed:.3f}s, {total_chunks} chunks, {end_memory - start_memory:.1f}MB memory delta")
    
    return {
        "document_count": len(documents),
        "iterations": iterations,
        "times": times,
        "avg_time": mean(times),
        "stdev_time": stdev(times) if len(times) > 1 else 0,
        "min_time": min(times),
        "max_time": max(times),
        "total_chunks": mean(chunk_counts),
        "docs_per_second": len(documents) / mean(times),
        "chunks_per_second": mean(chunk_counts) / mean(times)
    }


def benchmark_scalability(iterations: int = 3) -> dict[str, Any]:
    """Test chunking performance with increasing document counts."""
    
    print("📈 Running scalability benchmark...")
    
    config = ChunkingConfig()  # Use default config
    document_counts = [10, 50, 100, 500]
    results = {}
    
    for count in document_counts:
        print(f"\n   📄 Testing with {count} documents...")
        
        documents = generate_synthetic_documents(count, "medium")
        benchmark_result = benchmark_chunking_speed(documents, config, iterations)
        
        results[count] = benchmark_result
        
        print(f"      ⏱️  Avg time: {benchmark_result['avg_time']:.3f}s")
        print(f"      📊 Docs/sec: {benchmark_result['docs_per_second']:.1f}")
        print(f"      🧩 Chunks/sec: {benchmark_result['chunks_per_second']:.1f}")
    
    return results


def benchmark_document_sizes(iterations: int = 3) -> dict[str, Any]:
    """Test chunking performance with different document sizes."""
    
    print("📏 Running document size benchmark...")
    
    config = ChunkingConfig()
    sizes = ["small", "medium", "large", "xlarge"]
    results = {}
    
    for size in sizes:
        print(f"\n   📄 Testing {size} documents...")
        
        documents = generate_synthetic_documents(50, size)  # Fixed count, varying size
        benchmark_result = benchmark_chunking_speed(documents, config, iterations)
        
        # Calculate per-document metrics
        avg_doc_chars = mean(len(doc.text) for doc in documents)
        
        results[size] = {
            **benchmark_result,
            "avg_document_chars": avg_doc_chars,
            "chars_per_second": avg_doc_chars * benchmark_result['docs_per_second'],
        }
        
        print(f"      ⏱️  Avg time: {benchmark_result['avg_time']:.3f}s")
        print(f"      📏 Avg chars: {avg_doc_chars:.0f}")
        print(f"      📊 Chars/sec: {results[size]['chars_per_second']:.0f}")
    
    return results


def benchmark_configurations(iterations: int = 3) -> dict[str, Any]:
    """Test performance with different chunking configurations."""
    
    print("⚙️  Running configuration benchmark...")
    
    configs = {
        "small_chunks": ChunkingConfig(target_tokens=150, max_tokens=200, overlap_tokens=25),
        "default": ChunkingConfig(),
        "large_chunks": ChunkingConfig(target_tokens=450, max_tokens=600, overlap_tokens=75),
        "no_overlap": ChunkingConfig(overlap_tokens=0),
    }
    
    documents = generate_synthetic_documents(100, "medium")  # Fixed test set
    results = {}
    
    for config_name, config in configs.items():
        print(f"\n   ⚙️  Testing {config_name} configuration...")
        print(f"      Target/Max: {config.target_tokens}/{config.max_tokens}, Overlap: {config.overlap_tokens}")
        
        benchmark_result = benchmark_chunking_speed(documents, config, iterations)
        results[config_name] = benchmark_result
        
        print(f"      ⏱️  Avg time: {benchmark_result['avg_time']:.3f}s")
        print(f"      🧩 Avg chunks: {benchmark_result['total_chunks']:.1f}")
        print(f"      📊 Chunks/sec: {benchmark_result['chunks_per_second']:.1f}")
    
    return results


def print_benchmark_summary(scalability_results: dict[str, Any], 
                           size_results: dict[str, Any], 
                           config_results: dict[str, Any]):
    """Print comprehensive benchmark summary."""
    
    print("\n" + "="*80)
    print("⚡ CHUNKING PERFORMANCE BENCHMARK SUMMARY")
    print("="*80)
    
    # Scalability summary
    print("\n📈 SCALABILITY (documents processed vs time)")
    print("-" * 40)
    for count, results in scalability_results.items():
        efficiency = results['docs_per_second']
        stability = results['stdev_time'] / results['avg_time'] * 100  # CV%
        print(f"   {count:3d} docs: {results['avg_time']:6.3f}s ({efficiency:5.1f} docs/sec, {stability:4.1f}% variance)")
    
    # Size performance
    print("\n📏 DOCUMENT SIZE PERFORMANCE")
    print("-" * 40)
    for size, results in size_results.items():
        chars = results['avg_document_chars']
        throughput = results['chars_per_second']
        print(f"   {size:6s}: {chars:6.0f} chars/doc ({throughput:8.0f} chars/sec)")
    
    # Configuration comparison  
    print("\n⚙️  CONFIGURATION COMPARISON")
    print("-" * 40)
    for config_name, results in config_results.items():
        chunks_per_doc = results['total_chunks'] / results['document_count']
        print(f"   {config_name:12s}: {results['avg_time']:6.3f}s ({chunks_per_doc:4.1f} chunks/doc, {results['chunks_per_second']:5.1f} chunks/sec)")
    
    # Performance targets validation
    print("\n🎯 PERFORMANCE TARGETS")
    print("-" * 40)
    
    # Check if we meet the 1s per large document target
    large_doc_time = size_results.get('large', {}).get('avg_time', 0) / 50  # Per document
    print(f"   Large doc processing: {large_doc_time:.3f}s per doc (target: <1.0s) {'✅' if large_doc_time < 1.0 else '❌'}")
    
    # Check UUID generation speed
    best_chunks_per_sec = max(r['chunks_per_second'] for r in config_results.values())
    uuid_time_per_chunk = 1.0 / best_chunks_per_sec * 1000  # ms per chunk
    print(f"   UUID generation: {uuid_time_per_chunk:.3f}ms per chunk (target: <0.1ms) {'✅' if uuid_time_per_chunk < 0.1 else '❌'}")
    
    # Overall throughput
    best_throughput = max(r['docs_per_second'] for r in scalability_results.values())
    print(f"   Peak throughput: {best_throughput:.1f} docs/sec")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-" * 40)
    
    fastest_config = min(config_results.items(), key=lambda x: x[1]['avg_time'])
    print(f"   • Fastest config: {fastest_config[0]} ({fastest_config[1]['avg_time']:.3f}s)")
    
    most_efficient = max(config_results.items(), key=lambda x: x[1]['chunks_per_second'])
    print(f"   • Most efficient: {most_efficient[0]} ({most_efficient[1]['chunks_per_second']:.1f} chunks/sec)")
    
    # Memory and stability notes
    largest_test = max(scalability_results.keys())
    stability = scalability_results[largest_test]['stdev_time'] / scalability_results[largest_test]['avg_time']
    if stability < 0.1:
        print(f"   • Performance is stable (variance: {stability*100:.1f}%)")
    else:
        print(f"   • Performance shows some variance (variance: {stability*100:.1f}%)")


def main():
    """Main benchmark script."""
    
    parser = argparse.ArgumentParser(description="Benchmark chunking performance")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations per test")
    parser.add_argument("--skip-scalability", action="store_true", help="Skip scalability tests")
    parser.add_argument("--skip-sizes", action="store_true", help="Skip document size tests") 
    parser.add_argument("--skip-configs", action="store_true", help="Skip configuration tests")
    
    args = parser.parse_args()
    
    print("🚀 Starting chunking performance benchmark...")
    print(f"   System: {psutil.cpu_count()} CPUs, {psutil.virtual_memory().total / (1024**3):.1f}GB RAM")
    
    try:
        results = {}
        
        if not args.skip_scalability:
            results['scalability'] = benchmark_scalability(args.iterations)
            
        if not args.skip_sizes:
            results['sizes'] = benchmark_document_sizes(args.iterations)
            
        if not args.skip_configs:
            results['configs'] = benchmark_configurations(args.iterations)
        
        # Print summary
        if all(key in results for key in ['scalability', 'sizes', 'configs']):
            print_benchmark_summary(results['scalability'], results['sizes'], results['configs'])
        else:
            print("\n✅ Partial benchmark completed")
            for test_type, test_results in results.items():
                print(f"   {test_type}: {len(test_results)} tests run")
        
        return 0
        
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())