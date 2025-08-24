#!/usr/bin/env python3
"""Validate migration results and data integrity."""

import asyncio
from typing import Any

import click

from bio_mcp.config.config import Config
from bio_mcp.services.db_service import DatabaseService
from bio_mcp.services.document_chunk_service import DocumentChunkService


async def validate_chunk_counts(
    document_chunk_service: DocumentChunkService,
    db_service: DatabaseService
) -> dict[str, Any]:
    """Validate that chunk counts match expected values."""
    
    # Get collection stats from DocumentChunkService
    collection_stats = await document_chunk_service.get_collection_stats()
    
    # Get database document counts
    db_stats = await db_service.get_document_stats()
    
    return {
        "weaviate_chunks": collection_stats.get("total_chunks", 0),
        "database_documents": db_stats.get("total_documents", 0),
        "source_breakdown": collection_stats.get("source_breakdown", {}),
        "avg_chunks_per_doc": (
            collection_stats.get("total_chunks", 0) / 
            db_stats.get("total_documents", 1)
        )
    }

async def validate_sample_documents(
    document_chunk_service: DocumentChunkService,
    sample_size: int = 10
) -> dict[str, Any]:
    """Validate a sample of documents for data integrity."""
    
    results = {
        "sample_size": sample_size,
        "valid_documents": 0,
        "invalid_documents": 0,
        "issues": []
    }
    
    # Get random sample of chunks
    search_results = await document_chunk_service.search_chunks(
        query="test",
        limit=sample_size * 5  # Get more to ensure variety
    )
    
    # Group by parent document
    docs_seen = set()
    for result in search_results:
        parent_uid = result["parent_uid"]
        if parent_uid in docs_seen:
            continue
        docs_seen.add(parent_uid)
        
        if len(docs_seen) >= sample_size:
            break
        
        # Validate document
        try:
            # Check that title exists and is not duplicated in text
            if result["title"] and result["title"] in result["text"]:
                results["issues"].append({
                    "doc_uid": parent_uid,
                    "issue": "Title duplicated in chunk text",
                    "chunk_uuid": result["uuid"]
                })
            
            # Check that metadata exists
            if not result.get("meta"):
                results["issues"].append({
                    "doc_uid": parent_uid,
                    "issue": "Missing metadata",
                    "chunk_uuid": result["uuid"]
                })
            
            # Check token count reasonableness
            text_len = len(result["text"])
            token_count = result.get("tokens", 0)
            if token_count < text_len / 10 or token_count > text_len / 2:
                results["issues"].append({
                    "doc_uid": parent_uid,
                    "issue": f"Suspicious token count: {token_count} for {text_len} chars",
                    "chunk_uuid": result["uuid"]
                })
            
            results["valid_documents"] += 1
            
        except Exception as e:
            results["invalid_documents"] += 1
            results["issues"].append({
                "doc_uid": parent_uid,
                "issue": f"Validation error: {e!s}",
                "chunk_uuid": result.get("uuid")
            })
    
    return results

@click.command()
@click.option("--sample-size", type=int, default=100, help="Number of documents to sample for validation")
def main(sample_size):
    """Validate migration results."""
    async def _main():
        config = Config()
        document_chunk_service = DocumentChunkService()
        db_service = DatabaseService(config)
        
        try:
            await document_chunk_service.connect()
            await db_service.connect()
            
            click.echo("Validating chunk counts...")
            count_validation = await validate_chunk_counts(document_chunk_service, db_service)
            
            click.echo(f"Weaviate chunks: {count_validation['weaviate_chunks']}")
            click.echo(f"Database documents: {count_validation['database_documents']}")
            click.echo(f"Average chunks per document: {count_validation['avg_chunks_per_doc']:.1f}")
            
            click.echo(f"\nValidating sample of {sample_size} documents...")
            sample_validation = await validate_sample_documents(document_chunk_service, sample_size)
            
            click.echo(f"Valid documents: {sample_validation['valid_documents']}")
            click.echo(f"Invalid documents: {sample_validation['invalid_documents']}")
            
            if sample_validation['issues']:
                click.echo(f"\nIssues found ({len(sample_validation['issues'])}):") 
                for issue in sample_validation['issues'][:10]:  # Show first 10
                    click.echo(f"  {issue['doc_uid']}: {issue['issue']}")
            else:
                click.echo("\n✅ No issues found in sample validation")
            
            # Overall assessment
            total_issues = len(sample_validation['issues'])
            if total_issues == 0:
                click.echo("\n✅ Migration validation PASSED")
            elif total_issues <= sample_size * 0.1:  # Less than 10% issues
                click.echo(f"\n⚠️  Migration validation PASSED with minor issues ({total_issues} issues)")
            else:
                click.echo(f"\n❌ Migration validation FAILED with significant issues ({total_issues} issues)")
        
        finally:
            await document_chunk_service.disconnect()
            await db_service.disconnect()

    asyncio.run(_main())

if __name__ == "__main__":
    main()