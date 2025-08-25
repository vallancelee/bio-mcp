#!/usr/bin/env python3
"""
Validation script for chunking strategy.

Tests the new chunking system on sample PubMed abstracts to validate quality,
token budgets, and section detection accuracy.
"""

import argparse
import time
from datetime import datetime
from typing import Any

from bio_mcp.models.document import Document
from bio_mcp.services.chunking import AbstractChunker, ChunkingConfig


def create_sample_documents() -> list[Document]:
    """Create sample documents for validation."""

    samples = [
        # Structured abstract
        Document(
            uid="pubmed:sample1",
            source="pubmed",
            source_id="sample1",
            title="COVID-19 Vaccine Effectiveness: A Systematic Review",
            text="""Background: COVID-19 vaccines have been deployed globally to control the pandemic.
Objective: To assess the real-world effectiveness of COVID-19 vaccines against infection and severe disease.
Methods: We conducted a systematic review of observational studies published from January 2021 to December 2023. Studies were included if they reported vaccine effectiveness against COVID-19 outcomes.
Results: Vaccine effectiveness against infection ranged from 60-95% for mRNA vaccines and 50-80% for viral vector vaccines. Effectiveness against hospitalization was consistently high (85-95%) across all vaccine types. Booster doses increased effectiveness by 15-25 percentage points.
Conclusions: COVID-19 vaccines demonstrate high effectiveness against severe disease and moderate effectiveness against infection. Booster doses are important for maintaining protection.""",
            published_at=datetime(2024, 1, 15),
            detail={
                "journal": "The Lancet",
                "mesh_terms": ["COVID-19", "Vaccines", "Effectiveness"],
            },
        ),
        # Unstructured abstract
        Document(
            uid="pubmed:sample2",
            source="pubmed",
            source_id="sample2",
            title="Machine Learning in Drug Discovery",
            text="""Machine learning approaches are increasingly being applied to drug discovery and development processes. This review examines recent advances in artificial intelligence applications for molecular design, target identification, and clinical trial optimization. Deep learning models show promise for predicting drug-target interactions and identifying novel therapeutic compounds. However, challenges remain in data quality, model interpretability, and regulatory acceptance.""",
            published_at=datetime(2023, 6, 10),
            detail={
                "journal": "Nature Reviews Drug Discovery",
                "mesh_terms": [
                    "Machine Learning",
                    "Drug Discovery",
                    "Artificial Intelligence",
                ],
            },
        ),
        # Abstract with statistical claims (tests numeric safety)
        Document(
            uid="pubmed:sample3",
            source="pubmed",
            source_id="sample3",
            title="Statin Therapy in Cardiovascular Disease Prevention",
            text="""Background: Statins are widely prescribed for cardiovascular disease prevention.
Methods: We analyzed data from 50,000 patients across 15 randomized controlled trials.
Results: Statin therapy reduced major cardiovascular events by 25% (HR 0.75, 95% CI 0.68-0.82, p<0.001). Low-density lipoprotein cholesterol decreased by an average of 38.5 mg/dL compared to placebo (p<0.001). The number needed to treat was 67 for primary prevention and 39 for secondary prevention.
Conclusions: Statin therapy provides significant cardiovascular benefits with an acceptable safety profile.""",
            published_at=datetime(2023, 9, 20),
            detail={
                "journal": "Circulation",
                "mesh_terms": ["Statins", "Cardiovascular Disease", "Prevention"],
            },
        ),
        # Long abstract (tests chunking)
        Document(
            uid="pubmed:sample4",
            source="pubmed",
            source_id="sample4",
            title="Comprehensive Analysis of Cancer Genomics Data",
            text="""Background: Cancer is a complex disease characterized by genomic instability and heterogeneity. Understanding the genomic landscape of different cancer types is crucial for developing personalized treatment strategies.
Objective: To perform a comprehensive analysis of genomic alterations across multiple cancer types and identify potential therapeutic targets.
Methods: We analyzed whole-genome sequencing data from 10,000 tumor samples representing 33 cancer types from The Cancer Genome Atlas (TCGA). Mutations, copy number alterations, and structural variants were identified using standardized bioinformatics pipelines. Pathway enrichment analysis was performed to identify dysregulated biological processes. Machine learning models were developed to predict treatment response based on genomic features.
Results: We identified 2.8 million somatic mutations across all samples, with an average mutation burden of 280 mutations per tumor. The most frequently mutated genes were TP53 (54% of samples), PIK3CA (16%), and KRAS (15%). Copy number alterations affected an average of 25% of the genome per sample. Pathway analysis revealed dysregulation of cell cycle control, DNA repair, and PI3K/AKT signaling across most cancer types. Our machine learning models achieved 78% accuracy in predicting treatment response to targeted therapies.
Conclusions: This comprehensive genomic analysis provides insights into the molecular basis of cancer and identifies potential targets for therapeutic intervention. The high frequency of TP53 mutations highlights the importance of targeting p53 pathway dysfunction in cancer treatment.""",
            published_at=datetime(2024, 3, 5),
            detail={
                "journal": "Nature Genetics",
                "mesh_terms": [
                    "Cancer",
                    "Genomics",
                    "Personalized Medicine",
                    "Machine Learning",
                ],
            },
        ),
    ]

    return samples


def validate_chunking_quality(
    chunks: list[Any], document: Document, config: ChunkingConfig
) -> dict[str, Any]:
    """Validate chunking quality metrics."""

    results = {
        "document_uid": document.uid,
        "chunk_count": len(chunks),
        "total_tokens": sum(c.tokens or 0 for c in chunks),
        "avg_tokens": sum(c.tokens or 0 for c in chunks) / len(chunks) if chunks else 0,
        "token_budget_compliance": True,
        "deterministic_ids": True,
        "section_detection": "N/A",
        "numeric_safety": True,
        "issues": [],
    }

    # Check token budget compliance
    for i, chunk in enumerate(chunks):
        if not chunk.tokens:
            results["issues"].append(f"Chunk {i}: Missing token count")
            continue

        if chunk.tokens > config.max_tokens:
            results["token_budget_compliance"] = False
            results["issues"].append(
                f"Chunk {i}: Exceeds max tokens ({chunk.tokens} > {config.max_tokens})"
            )

    # Check deterministic IDs
    chunk_ids = [c.chunk_id for c in chunks]
    chunk_uuids = [c.uuid for c in chunks]

    if len(set(chunk_ids)) != len(chunk_ids):
        results["deterministic_ids"] = False
        results["issues"].append("Duplicate chunk IDs found")

    if len(set(chunk_uuids)) != len(chunk_uuids):
        results["deterministic_ids"] = False
        results["issues"].append("Duplicate UUIDs found")

    # Check section detection for structured abstracts
    if any(
        section in document.text
        for section in ["Background:", "Methods:", "Results:", "Conclusions:"]
    ):
        section_chunks = [c for c in chunks if c.section != "Unstructured"]
        if section_chunks:
            results["section_detection"] = (
                f"Detected {len(set(c.section for c in section_chunks))} sections"
            )
        else:
            results["section_detection"] = "Failed to detect structured sections"
            results["issues"].append("Structured abstract not properly parsed")

    # Check numeric safety (simplified check)
    for chunk in chunks:
        # Look for statistical patterns that might be split
        import re

        if re.search(r"\d+\.\d+%.*\(.*p[<=]", chunk.text):
            # Has statistical claim, check if complete
            if not re.search(r"p[<=]\d+\.\d+", chunk.text):
                results["numeric_safety"] = False
                results["issues"].append(
                    f"Potential incomplete statistical claim in chunk {chunk.chunk_id}"
                )

    return results


def run_validation(sample_size: int | None = None) -> dict[str, Any]:
    """Run validation on sample documents."""

    print("🧪 Starting chunking validation...")

    # Create test documents
    documents = create_sample_documents()
    if sample_size:
        documents = documents[:sample_size]

    print(f"📄 Testing {len(documents)} sample documents")

    # Test different configurations
    configs = [
        ("default", ChunkingConfig()),
        ("small_chunks", ChunkingConfig(target_tokens=150, max_tokens=200)),
        ("large_chunks", ChunkingConfig(target_tokens=400, max_tokens=500)),
    ]

    validation_results = {}

    for config_name, config in configs:
        print(f"\n🔧 Testing configuration: {config_name}")
        print(
            f"   Target tokens: {config.target_tokens}, Max tokens: {config.max_tokens}"
        )

        chunker = AbstractChunker(config)
        config_results = []

        start_time = time.time()

        for doc in documents:
            print(f"   📝 Processing: {doc.title}")

            chunks = chunker.chunk_document(doc)
            validation = validate_chunking_quality(chunks, doc, config)
            config_results.append(validation)

            # Print basic stats
            print(
                f"      → {len(chunks)} chunks, {validation['avg_tokens']:.1f} avg tokens"
            )
            if validation["issues"]:
                print(f"      ⚠️  Issues: {len(validation['issues'])}")

        end_time = time.time()

        validation_results[config_name] = {
            "config": {
                "target_tokens": config.target_tokens,
                "max_tokens": config.max_tokens,
                "overlap_tokens": config.overlap_tokens,
            },
            "results": config_results,
            "processing_time": end_time - start_time,
            "avg_chunks_per_doc": sum(r["chunk_count"] for r in config_results)
            / len(config_results),
            "avg_tokens_per_chunk": sum(r["avg_tokens"] for r in config_results)
            / len(config_results),
            "compliance_rate": sum(
                1
                for r in config_results
                if r["token_budget_compliance"] and not r["issues"]
            )
            / len(config_results),
        }

        print(f"   ⏱️  Processing time: {end_time - start_time:.2f}s")
        print(
            f"   ✅ Compliance rate: {validation_results[config_name]['compliance_rate']:.1%}"
        )

    return validation_results


def print_summary(results: dict[str, Any]):
    """Print validation summary."""

    print("\n" + "=" * 60)
    print("📊 CHUNKING VALIDATION SUMMARY")
    print("=" * 60)

    for config_name, config_results in results.items():
        print(f"\n🔧 Configuration: {config_name.upper()}")
        print(
            f"   Target/Max tokens: {config_results['config']['target_tokens']}/{config_results['config']['max_tokens']}"
        )
        print(f"   Avg chunks per doc: {config_results['avg_chunks_per_doc']:.1f}")
        print(f"   Avg tokens per chunk: {config_results['avg_tokens_per_chunk']:.1f}")
        print(f"   Processing time: {config_results['processing_time']:.2f}s")
        print(f"   Compliance rate: {config_results['compliance_rate']:.1%}")

        # Count issues
        all_issues = []
        for result in config_results["results"]:
            all_issues.extend(result["issues"])

        if all_issues:
            print(f"   ⚠️  Total issues: {len(all_issues)}")
        else:
            print("   ✅ No issues found")

    print("\n🎯 RECOMMENDATIONS:")

    # Find best performing config
    best_config = max(results.items(), key=lambda x: x[1]["compliance_rate"])
    print(
        f"   • Best performing config: {best_config[0]} ({best_config[1]['compliance_rate']:.1%} compliance)"
    )

    # Performance recommendations
    fastest_config = min(results.items(), key=lambda x: x[1]["processing_time"])
    print(
        f"   • Fastest processing: {fastest_config[0]} ({fastest_config[1]['processing_time']:.2f}s)"
    )

    print("\n✨ Validation complete!")


def main():
    """Main validation script."""

    parser = argparse.ArgumentParser(
        description="Validate chunking strategy on sample data"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Number of sample documents to test",
    )

    args = parser.parse_args()

    try:
        results = run_validation(args.sample_size)
        print_summary(results)

        return 0

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
