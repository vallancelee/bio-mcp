# RAG Step 5: Data Re-ingestion Workflow

**Objective:** Implement comprehensive data re-ingestion workflow for migrating existing PubMed data to DocumentChunk_v2 collection with proper batching, error handling, and progress tracking.

**Success Criteria:**
- Safe migration of existing PubMed data without data loss
- Batched processing with proper memory management
- Comprehensive error handling and retry logic
- Progress tracking and monitoring capabilities
- Rollback mechanism for failed migrations
- Performance meets requirements (>500 docs/minute)

---

## 1. Migration Architecture

### 1.1 Migration Strategy Overview

```
Existing Data (S3 + DB) → Document Model → Chunking → DocumentChunk_v2
                       ↓
               Progress Tracking & Error Handling
                       ↓
               Validation & Quality Assurance
```

**Key Principles:**
- Idempotent operations (deterministic UUIDs)
- Fail-fast with detailed error reporting
- Gradual rollout with validation checkpoints
- Preserve data provenance and audit trail

### 1.2 Migration Job Types

1. **Full Re-ingestion**: Complete data migration from scratch
2. **Incremental Update**: Process only new/changed documents
3. **Repair Mode**: Re-process failed documents
4. **Validation Mode**: Verify existing chunks without modification

---

## 2. Core Migration Services

### 2.1 Re-ingestion Service
**File:** `src/bio_mcp/services/reingest_service.py`

```python
from __future__ import annotations
import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime, timedelta
from enum import Enum
import json

from bio_mcp.config.config import Config
from bio_mcp.models.document import Document
from bio_mcp.services.embedding_service_v2 import EmbeddingServiceV2
from bio_mcp.sources.pubmed.normalizer import PubMedNormalizer
from bio_mcp.shared.models.database_models import JobStatus
from bio_mcp.services.s3_service import S3Service
from bio_mcp.services.db_service import DatabaseService

logger = logging.getLogger(__name__)

class ReingestionMode(Enum):
    FULL = "full"
    INCREMENTAL = "incremental"  
    REPAIR = "repair"
    VALIDATION = "validation"

class ReingestionStats:
    """Track re-ingestion progress and statistics."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.documents_processed = 0
        self.documents_failed = 0
        self.chunks_created = 0
        self.chunks_updated = 0
        self.bytes_processed = 0
        self.errors: List[Dict[str, Any]] = []
    
    def add_success(self, doc_uid: str, chunks_count: int, doc_size: int):
        self.documents_processed += 1
        self.chunks_created += chunks_count
        self.bytes_processed += doc_size
    
    def add_failure(self, doc_uid: str, error: str, context: Dict[str, Any] = None):
        self.documents_failed += 1
        self.errors.append({
            "doc_uid": doc_uid,
            "error": error,
            "context": context or {},
            "timestamp": datetime.now().isoformat()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        elapsed = datetime.now() - self.start_time
        total_docs = self.documents_processed + self.documents_failed
        
        return {
            "elapsed_seconds": elapsed.total_seconds(),
            "total_documents": total_docs,
            "documents_processed": self.documents_processed,
            "documents_failed": self.documents_failed,
            "success_rate": self.documents_processed / total_docs if total_docs > 0 else 0,
            "chunks_created": self.chunks_created,
            "chunks_updated": self.chunks_updated,
            "bytes_processed": self.bytes_processed,
            "docs_per_minute": (total_docs / elapsed.total_seconds() * 60) if elapsed.total_seconds() > 0 else 0,
            "errors_sample": self.errors[:10]  # First 10 errors for troubleshooting
        }

class ReingestionService:
    """Service for re-ingesting PubMed data into DocumentChunk_v2."""
    
    def __init__(self, config: Config):
        self.config = config
        self.embedding_service = EmbeddingServiceV2(config)
        self.normalizer = PubMedNormalizer()
        self.s3_service = S3Service(config)
        self.db_service = DatabaseService(config)
        
        # Batch processing configuration
        self.batch_size = int(config.get("BIO_MCP_REINGEST_BATCH_SIZE", "100"))
        self.max_concurrent = int(config.get("BIO_MCP_REINGEST_CONCURRENCY", "10"))
        self.retry_attempts = int(config.get("BIO_MCP_REINGEST_RETRY_ATTEMPTS", "3"))
        self.retry_delay = int(config.get("BIO_MCP_REINGEST_RETRY_DELAY", "5"))
    
    async def start_reingest_job(
        self,
        mode: ReingestionMode,
        source_filter: Optional[str] = None,
        date_filter: Optional[tuple[datetime, datetime]] = None,
        pmid_list: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> str:
        """Start a re-ingestion job and return job ID."""
        
        job_params = {
            "mode": mode.value,
            "source_filter": source_filter,
            "date_filter": [d.isoformat() if d else None for d in (date_filter or (None, None))],
            "pmid_list": pmid_list,
            "dry_run": dry_run,
            "batch_size": self.batch_size,
            "max_concurrent": self.max_concurrent
        }
        
        # Create job record
        job_id = await self.db_service.create_job(
            operation="reingest",
            parameters=job_params,
            status=JobStatus.QUEUED
        )
        
        logger.info(f"Created re-ingestion job {job_id} with mode {mode.value}")
        return job_id
    
    async def execute_reingest_job(self, job_id: str) -> Dict[str, Any]:
        """Execute a re-ingestion job with comprehensive error handling."""
        
        stats = ReingestionStats()
        
        try:
            # Update job status
            await self.db_service.update_job_status(job_id, JobStatus.RUNNING)
            
            # Get job parameters
            job = await self.db_service.get_job(job_id)
            params = job.parameters
            mode = ReingestionMode(params["mode"])
            
            logger.info(f"Starting re-ingestion job {job_id} in {mode.value} mode")
            
            # Initialize services
            await self.embedding_service.connect()
            await self.s3_service.connect()
            
            # Get document list based on mode and filters
            document_refs = await self._get_document_list(
                mode=mode,
                source_filter=params.get("source_filter"),
                date_filter=params.get("date_filter"),
                pmid_list=params.get("pmid_list")
            )
            
            logger.info(f"Found {len(document_refs)} documents to process")
            
            # Process documents in batches
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            async def process_batch(batch_refs: List[Dict[str, Any]]):
                """Process a batch of documents."""
                tasks = []
                for doc_ref in batch_refs:
                    task = self._process_document_with_semaphore(
                        semaphore, doc_ref, stats, params.get("dry_run", False)
                    )
                    tasks.append(task)
                
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process in batches to manage memory
            for i in range(0, len(document_refs), self.batch_size):
                batch = document_refs[i:i + self.batch_size]
                await process_batch(batch)
                
                # Update job progress
                progress = min(100, int((i + len(batch)) / len(document_refs) * 100))
                await self._update_job_progress(job_id, progress, stats)
                
                logger.info(f"Processed batch {i//self.batch_size + 1}, progress: {progress}%")
            
            # Final statistics
            final_stats = stats.get_summary()
            
            # Determine final status
            if stats.documents_failed == 0:
                final_status = JobStatus.COMPLETED
            elif stats.documents_processed > 0:
                final_status = JobStatus.COMPLETED_WITH_ERRORS
            else:
                final_status = JobStatus.FAILED
            
            await self.db_service.update_job_status(
                job_id, 
                final_status,
                result=final_stats
            )
            
            logger.info(f"Re-ingestion job {job_id} completed: {final_stats}")
            return final_stats
            
        except Exception as e:
            logger.error(f"Re-ingestion job {job_id} failed: {e}")
            stats.add_failure("job_level", str(e))
            
            await self.db_service.update_job_status(
                job_id,
                JobStatus.FAILED,
                result=stats.get_summary()
            )
            raise
        
        finally:
            await self.embedding_service.disconnect()
            await self.s3_service.disconnect()
    
    async def _process_document_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        doc_ref: Dict[str, Any],
        stats: ReingestionStats,
        dry_run: bool
    ):
        """Process a single document with concurrency control."""
        async with semaphore:
            await self._process_single_document(doc_ref, stats, dry_run)
    
    async def _process_single_document(
        self,
        doc_ref: Dict[str, Any], 
        stats: ReingestionStats,
        dry_run: bool
    ):
        """Process a single document with retry logic."""
        doc_uid = doc_ref.get("uid", "unknown")
        
        for attempt in range(self.retry_attempts):
            try:
                # Load document from S3
                raw_data = await self.s3_service.load_document(doc_ref["s3_key"])
                if not raw_data:
                    raise ValueError(f"Failed to load document from S3: {doc_ref['s3_key']}")
                
                # Normalize to Document model
                normalized = await self.normalizer.normalize(raw_data)
                document = Document(
                    uid=normalized["uid"],
                    source=normalized["source"],
                    source_id=normalized["source_id"],
                    title=normalized.get("title"),
                    text=normalized.get("text", ""),
                    published_at=normalized.get("published_at"),
                    fetched_at=normalized.get("fetched_at"),
                    authors=normalized.get("authors", []),
                    identifiers=normalized.get("identifiers", {}),
                    provenance=normalized.get("provenance", {}),
                    detail=normalized.get("detail", {})
                )
                
                if dry_run:
                    # Validate only, don't store
                    chunk_count = await self._validate_document_chunks(document)
                    stats.add_success(doc_uid, chunk_count, len(json.dumps(raw_data)))
                else:
                    # Store chunks
                    chunk_uuids = await self.embedding_service.store_document_chunks(
                        document=document,
                        quality_score=normalized.get("quality_score")
                    )
                    stats.add_success(doc_uid, len(chunk_uuids), len(json.dumps(raw_data)))
                
                logger.debug(f"Successfully processed document {doc_uid}")
                return
                
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    # Final attempt failed
                    stats.add_failure(doc_uid, str(e), {
                        "s3_key": doc_ref.get("s3_key"),
                        "attempts": attempt + 1
                    })
                    logger.error(f"Failed to process document {doc_uid} after {attempt + 1} attempts: {e}")
                else:
                    # Retry
                    logger.warning(f"Retrying document {doc_uid} (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(self.retry_delay)
    
    async def _validate_document_chunks(self, document: Document) -> int:
        """Validate document chunking without storing (for dry run)."""
        chunks = await self.embedding_service.chunking_service.chunk_document(document)
        return len(chunks)
    
    async def _get_document_list(
        self,
        mode: ReingestionMode,
        source_filter: Optional[str],
        date_filter: Optional[List[str]],
        pmid_list: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Get list of documents to process based on mode and filters."""
        
        if mode == ReingestionMode.FULL:
            # Get all documents from database
            return await self.db_service.get_all_document_refs(source_filter)
        
        elif mode == ReingestionMode.INCREMENTAL:
            # Get documents modified since last successful ingestion
            last_run = await self.db_service.get_last_successful_reingest()
            since_date = last_run or datetime.now() - timedelta(days=7)
            return await self.db_service.get_document_refs_since(since_date, source_filter)
        
        elif mode == ReingestionMode.REPAIR:
            # Get documents that failed in previous runs
            return await self.db_service.get_failed_document_refs(source_filter)
        
        elif mode == ReingestionMode.VALIDATION:
            # Use same logic as full but for validation only
            return await self.db_service.get_all_document_refs(source_filter)
        
        else:
            raise ValueError(f"Unknown reingest mode: {mode}")
    
    async def _update_job_progress(
        self, 
        job_id: str, 
        progress: int, 
        stats: ReingestionStats
    ):
        """Update job progress and statistics."""
        await self.db_service.update_job_progress(
            job_id,
            progress,
            stats.get_summary()
        )
    
    async def get_reingest_status(self, job_id: str) -> Dict[str, Any]:
        """Get status and progress of a re-ingestion job."""
        job = await self.db_service.get_job(job_id)
        
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        return {
            "job_id": job_id,
            "status": job.status.value,
            "progress": job.progress,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "parameters": job.parameters,
            "result": job.result or {}
        }
    
    async def cancel_reingest_job(self, job_id: str) -> bool:
        """Cancel a running re-ingestion job."""
        job = await self.db_service.get_job(job_id)
        
        if not job:
            return False
        
        if job.status not in [JobStatus.QUEUED, JobStatus.RUNNING]:
            return False
        
        await self.db_service.update_job_status(job_id, JobStatus.CANCELLED)
        logger.info(f"Cancelled re-ingestion job {job_id}")
        return True
```

### 2.2 Database Extensions
**File:** `src/bio_mcp/services/db_service.py` (additions)

```python
from typing import List, Dict, Any, Optional
from datetime import datetime

class DatabaseService:
    # ... existing methods ...
    
    async def get_all_document_refs(
        self, 
        source_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all document references for re-ingestion."""
        query = """
        SELECT 
            uid,
            source,
            source_id,
            s3_key,
            content_hash,
            created_at,
            updated_at
        FROM documents 
        WHERE s3_key IS NOT NULL
        """
        params = []
        
        if source_filter:
            query += " AND source = $1"
            params.append(source_filter)
        
        query += " ORDER BY created_at ASC"
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def get_document_refs_since(
        self,
        since_date: datetime,
        source_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get document references modified since a specific date."""
        query = """
        SELECT 
            uid,
            source,
            source_id,
            s3_key,
            content_hash,
            created_at,
            updated_at
        FROM documents 
        WHERE s3_key IS NOT NULL 
        AND updated_at >= $1
        """
        params = [since_date]
        
        if source_filter:
            query += " AND source = $2"
            params.append(source_filter)
        
        query += " ORDER BY updated_at ASC"
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def get_failed_document_refs(
        self,
        source_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get documents that failed in previous ingestion attempts."""
        # This would query a failed_ingestions table or similar
        # Implementation depends on how failures are tracked
        query = """
        SELECT DISTINCT
            d.uid,
            d.source,
            d.source_id,
            d.s3_key,
            d.content_hash,
            d.created_at,
            d.updated_at
        FROM documents d
        LEFT JOIN ingestion_failures f ON d.uid = f.document_uid
        WHERE d.s3_key IS NOT NULL
        AND f.document_uid IS NOT NULL
        """
        params = []
        
        if source_filter:
            query += " AND d.source = $1"
            params.append(source_filter)
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def get_last_successful_reingest(self) -> Optional[datetime]:
        """Get timestamp of last successful full re-ingestion."""
        query = """
        SELECT MAX(updated_at)
        FROM jobs
        WHERE operation = 'reingest'
        AND status = 'completed'
        AND parameters->>'mode' = 'full'
        """
        
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query)
            return result
    
    async def update_job_progress(
        self,
        job_id: str,
        progress: int,
        stats: Dict[str, Any]
    ) -> None:
        """Update job progress and intermediate results."""
        query = """
        UPDATE jobs 
        SET 
            progress = $2,
            result = $3,
            updated_at = NOW()
        WHERE id = $1
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, job_id, progress, json.dumps(stats))
```

---

## 3. Management Scripts

### 3.1 Re-ingestion CLI
**File:** `scripts/reingest_data.py`

```python
#!/usr/bin/env python3
"""CLI tool for managing data re-ingestion."""

import asyncio
import click
from datetime import datetime, timedelta
from typing import Optional

from bio_mcp.config.config import Config
from bio_mcp.services.reingest_service import ReingestionService, ReingestionMode

@click.group()
def cli():
    """Bio-MCP Data Re-ingestion Management."""
    pass

@cli.command()
@click.option("--mode", type=click.Choice(["full", "incremental", "repair", "validation"]), required=True)
@click.option("--source", help="Filter by source (e.g., 'pubmed')")
@click.option("--since-days", type=int, help="Process documents from N days ago")
@click.option("--pmids", help="Comma-separated list of PMIDs to process")
@click.option("--dry-run", is_flag=True, help="Validate without storing")
@click.option("--batch-size", type=int, default=100, help="Batch size for processing")
@click.option("--concurrency", type=int, default=10, help="Max concurrent operations")
async def start(mode, source, since_days, pmids, dry_run, batch_size, concurrency):
    """Start a re-ingestion job."""
    config = Config()
    config.BIO_MCP_REINGEST_BATCH_SIZE = str(batch_size)
    config.BIO_MCP_REINGEST_CONCURRENCY = str(concurrency)
    
    service = ReingestionService(config)
    
    # Parse date filter
    date_filter = None
    if since_days:
        start_date = datetime.now() - timedelta(days=since_days)
        date_filter = (start_date, datetime.now())
    
    # Parse PMID list
    pmid_list = None
    if pmids:
        pmid_list = [p.strip() for p in pmids.split(",")]
    
    try:
        job_id = await service.start_reingest_job(
            mode=ReingestionMode(mode),
            source_filter=source,
            date_filter=date_filter,
            pmid_list=pmid_list,
            dry_run=dry_run
        )
        
        click.echo(f"Started re-ingestion job: {job_id}")
        
        if click.confirm("Run job immediately?"):
            click.echo("Running job...")
            result = await service.execute_reingest_job(job_id)
            
            click.echo(f"\nJob completed!")
            click.echo(f"Documents processed: {result['documents_processed']}")
            click.echo(f"Documents failed: {result['documents_failed']}")
            click.echo(f"Chunks created: {result['chunks_created']}")
            click.echo(f"Success rate: {result['success_rate']:.1%}")
            click.echo(f"Processing rate: {result['docs_per_minute']:.1f} docs/min")
            
            if result['documents_failed'] > 0:
                click.echo(f"\nFirst few errors:")
                for error in result['errors_sample']:
                    click.echo(f"  {error['doc_uid']}: {error['error']}")
    
    except Exception as e:
        click.echo(f"Error: {e}")
        raise click.Abort()

@cli.command()
@click.argument("job_id")
async def status(job_id):
    """Get status of a re-ingestion job."""
    config = Config()
    service = ReingestionService(config)
    
    try:
        status_info = await service.get_reingest_status(job_id)
        
        click.echo(f"Job ID: {status_info['job_id']}")
        click.echo(f"Status: {status_info['status']}")
        click.echo(f"Progress: {status_info['progress']}%")
        click.echo(f"Created: {status_info['created_at']}")
        click.echo(f"Updated: {status_info['updated_at']}")
        
        if status_info['result']:
            result = status_info['result']
            click.echo(f"\nResults:")
            click.echo(f"  Documents processed: {result.get('documents_processed', 0)}")
            click.echo(f"  Documents failed: {result.get('documents_failed', 0)}")
            click.echo(f"  Success rate: {result.get('success_rate', 0):.1%}")
    
    except Exception as e:
        click.echo(f"Error: {e}")
        raise click.Abort()

@cli.command()
@click.argument("job_id")
async def cancel(job_id):
    """Cancel a running re-ingestion job."""
    config = Config()
    service = ReingestionService(config)
    
    try:
        success = await service.cancel_reingest_job(job_id)
        
        if success:
            click.echo(f"Job {job_id} cancelled successfully")
        else:
            click.echo(f"Could not cancel job {job_id} (may not exist or already completed)")
    
    except Exception as e:
        click.echo(f"Error: {e}")
        raise click.Abort()

@cli.command()
async def list_jobs():
    """List recent re-ingestion jobs."""
    config = Config()
    service = ReingestionService(config)
    
    # This would need a method to list jobs
    click.echo("Recent re-ingestion jobs:")
    click.echo("(Implementation needed in database service)")

if __name__ == "__main__":
    asyncio.run(cli())
```

### 3.2 Validation Script
**File:** `scripts/validate_migration.py`

```python
#!/usr/bin/env python3
"""Validate migration results and data integrity."""

import asyncio
import click
from typing import Dict, Any

from bio_mcp.config.config import Config
from bio_mcp.services.embedding_service_v2 import EmbeddingServiceV2
from bio_mcp.services.db_service import DatabaseService

async def validate_chunk_counts(
    embedding_service: EmbeddingServiceV2,
    db_service: DatabaseService
) -> Dict[str, Any]:
    """Validate that chunk counts match expected values."""
    
    # Get collection stats
    collection_stats = await embedding_service.get_collection_stats()
    
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
    embedding_service: EmbeddingServiceV2,
    sample_size: int = 10
) -> Dict[str, Any]:
    """Validate a sample of documents for data integrity."""
    
    results = {
        "sample_size": sample_size,
        "valid_documents": 0,
        "invalid_documents": 0,
        "issues": []
    }
    
    # Get random sample of chunks
    search_results = await embedding_service.search_chunks(
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
                "issue": f"Validation error: {str(e)}",
                "chunk_uuid": result.get("uuid")
            })
    
    return results

@click.command()
@click.option("--sample-size", type=int, default=100, help="Number of documents to sample for validation")
async def main(sample_size):
    """Validate migration results."""
    config = Config()
    embedding_service = EmbeddingServiceV2(config)
    db_service = DatabaseService(config)
    
    try:
        await embedding_service.connect()
        await db_service.connect()
        
        click.echo("Validating chunk counts...")
        count_validation = await validate_chunk_counts(embedding_service, db_service)
        
        click.echo(f"Weaviate chunks: {count_validation['weaviate_chunks']}")
        click.echo(f"Database documents: {count_validation['database_documents']}")
        click.echo(f"Average chunks per document: {count_validation['avg_chunks_per_doc']:.1f}")
        
        click.echo(f"\nValidating sample of {sample_size} documents...")
        sample_validation = await validate_sample_documents(embedding_service, sample_size)
        
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
        await embedding_service.disconnect()
        await db_service.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. Makefile Integration

### 4.1 Make Targets
**File:** `Makefile` (additions)

```makefile
# Re-ingestion targets
reingest-full:
	uv run python scripts/reingest_data.py start --mode full

reingest-incremental:
	uv run python scripts/reingest_data.py start --mode incremental

reingest-sample:
	uv run python scripts/reingest_data.py start --mode full --pmids "12345678,87654321" --dry-run

validate-migration:
	uv run python scripts/validate_migration.py --sample-size 100

# Quick status check
reingest-status:
	@echo "Recent re-ingestion jobs:"
	uv run python scripts/reingest_data.py list-jobs
```

---

## 5. Testing Implementation

### 5.1 Integration Tests
**File:** `tests/integration/services/test_reingest_integration.py`

```python
import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from bio_mcp.services.reingest_service import ReingestionService, ReingestionMode, ReingestionStats
from bio_mcp.config.config import Config

@pytest.mark.integration
class TestReingestionIntegration:
    """Integration tests for re-ingestion service."""
    
    @pytest.fixture
    def config(self):
        return Config(
            BIO_MCP_REINGEST_BATCH_SIZE="10",
            BIO_MCP_REINGEST_CONCURRENCY="2"
        )
    
    @pytest.mark.asyncio
    async def test_full_reingest_workflow(self, config, test_database, test_s3, test_weaviate):
        """Test complete re-ingestion workflow."""
        service = ReingestionService(config)
        
        # Create test job
        job_id = await service.start_reingest_job(
            mode=ReingestionMode.VALIDATION,
            dry_run=True
        )
        
        assert job_id is not None
        
        # Execute job
        result = await service.execute_reingest_job(job_id)
        
        assert result["documents_processed"] >= 0
        assert result["success_rate"] >= 0
        
        # Check job status
        status = await service.get_reingest_status(job_id)
        assert status["status"] in ["completed", "completed_with_errors"]
    
    @pytest.mark.asyncio
    async def test_reingest_error_handling(self, config):
        """Test error handling and retry logic."""
        stats = ReingestionStats()
        
        # Test adding failures
        stats.add_failure("test:123", "Connection error", {"retry": 1})
        stats.add_failure("test:456", "Timeout error")
        
        summary = stats.get_summary()
        assert summary["documents_failed"] == 2
        assert len(summary["errors_sample"]) == 2
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, config):
        """Test batched document processing."""
        service = ReingestionService(config)
        
        # Mock document list
        service._get_document_list = AsyncMock(return_value=[
            {"uid": f"test:{i}", "s3_key": f"test/{i}.json"}
            for i in range(25)  # More than one batch
        ])
        
        # Mock document processing
        service._process_single_document = AsyncMock()
        
        # Mock services
        service.embedding_service.connect = AsyncMock()
        service.embedding_service.disconnect = AsyncMock()
        service.s3_service.connect = AsyncMock()
        service.s3_service.disconnect = AsyncMock()
        service.db_service.update_job_status = AsyncMock()
        service.db_service.get_job = AsyncMock(return_value=Mock(parameters={"mode": "validation", "dry_run": True}))
        service._update_job_progress = AsyncMock()
        
        result = await service.execute_reingest_job("test-job-id")
        
        # Should have processed all documents
        assert service._process_single_document.call_count == 25
        
        # Should have updated progress multiple times (batches)
        assert service._update_job_progress.call_count >= 2
```

---

## 6. Success Validation

### 6.1 Checklist
- [ ] Re-ingestion service handles all modes (full, incremental, repair, validation)
- [ ] Batch processing with proper memory management
- [ ] Comprehensive error handling and retry logic
- [ ] Progress tracking and job status updates
- [ ] Idempotent operations (no duplicate chunks)
- [ ] Performance meets requirements (>500 docs/minute)
- [ ] Validation scripts detect data integrity issues
- [ ] CLI tools provide good developer experience
- [ ] Integration tests cover error scenarios

### 6.2 Performance Requirements
- **Throughput**: >500 documents/minute for full re-ingestion
- **Memory**: <2GB peak usage during large batch processing
- **Error Rate**: <1% failure rate under normal conditions
- **Recovery**: Ability to resume from failures within 5 minutes

---

## Next Steps

After completing this step:
1. Proceed to **RAG_STEP_6_RAG_TWEAKS.md** for RAG search improvements
2. Run validation migration on sample data
3. Schedule incremental re-ingestion job

**Estimated Time:** 2-3 days
**Dependencies:** RAG_STEP_4_EMBEDDING.md
**Risk Level:** Medium (data migration complexity, performance requirements)