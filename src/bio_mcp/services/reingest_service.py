from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from bio_mcp.config.config import Config
from bio_mcp.models.document import Document
from bio_mcp.services.db_service import DatabaseService
from bio_mcp.services.document_chunk_service import DocumentChunkService
from bio_mcp.services.normalization.pubmed import PubMedNormalizer

# from bio_mcp.services.s3_service import S3Service  # TODO: Implement S3Service
from bio_mcp.shared.models.database_models import JobStatus

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
        self.errors: list[dict[str, Any]] = []
    
    def add_success(self, doc_uid: str, chunks_count: int, doc_size: int):
        self.documents_processed += 1
        self.chunks_created += chunks_count
        self.bytes_processed += doc_size
    
    def add_failure(self, doc_uid: str, error: str, context: dict[str, Any] | None = None):
        self.documents_failed += 1
        self.errors.append({
            "doc_uid": doc_uid,
            "error": error,
            "context": context or {},
            "timestamp": datetime.now().isoformat()
        })
    
    def get_summary(self) -> dict[str, Any]:
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
        self.document_chunk_service = DocumentChunkService()
        # self.s3_service = S3Service(config)  # TODO: Implement S3Service
        self.s3_service = None
        self.db_service = DatabaseService(config)
        
        # Batch processing configuration
        self.batch_size = int(getattr(config, "BIO_MCP_REINGEST_BATCH_SIZE", "100"))
        self.max_concurrent = int(getattr(config, "BIO_MCP_REINGEST_CONCURRENCY", "10"))
        self.retry_attempts = int(getattr(config, "BIO_MCP_REINGEST_RETRY_ATTEMPTS", "3"))
        self.retry_delay = int(getattr(config, "BIO_MCP_REINGEST_RETRY_DELAY", "5"))
    
    async def start_reingest_job(
        self,
        mode: ReingestionMode,
        source_filter: str | None = None,
        date_filter: tuple[datetime, datetime] | None = None,
        pmid_list: list[str] | None = None,
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
            status=JobStatus.PENDING
        )
        
        logger.info(f"Created re-ingestion job {job_id} with mode {mode.value}")
        return job_id
    
    async def execute_reingest_job(self, job_id: str) -> dict[str, Any]:
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
            await self.document_chunk_service.connect()
            # Note: OpenAI API key required for embeddings
            if not self.config.openai_api_key:
                logger.warning("No OpenAI API key configured - embeddings will use fallback")
            # await self.s3_service.connect()  # TODO: Implement S3Service
            
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
            
            async def process_batch(batch_refs: list[dict[str, Any]]):
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
            await self.document_chunk_service.disconnect()
            # await self.s3_service.disconnect()  # TODO: Implement S3Service
    
    async def _process_document_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        doc_ref: dict[str, Any],
        stats: ReingestionStats,
        dry_run: bool
    ):
        """Process a single document with concurrency control."""
        async with semaphore:
            await self._process_single_document(doc_ref, stats, dry_run)
    
    async def _process_single_document(
        self,
        doc_ref: dict[str, Any], 
        stats: ReingestionStats,
        dry_run: bool
    ):
        """Process a single document with retry logic."""
        doc_uid = doc_ref.get("uid", "unknown")
        
        for attempt in range(self.retry_attempts):
            try:
                # Load document from S3 (TODO: implement S3Service)
                # raw_data = await self.s3_service.load_document(doc_ref["s3_key"])
                # For now, create mock data for testing
                raw_data = {
                    "pmid": doc_ref.get("source_id", "unknown"),
                    "title": "Mock title for testing",
                    "abstract": "Mock abstract for testing re-ingestion",
                    "authors": [],
                    "publication_date": None,
                    "journal": None,
                    "doi": None,
                    "keywords": []
                }
                
                # Normalize to Document model
                document = PubMedNormalizer.from_raw_dict(
                    raw_data,
                    s3_raw_uri=doc_ref.get("s3_key", "unknown"),
                    content_hash=doc_ref.get("content_hash", "unknown")
                )
                
                if dry_run:
                    # Validate only, don't store
                    chunk_count = await self._validate_document_chunks(document)
                    stats.add_success(doc_uid, chunk_count, len(json.dumps(raw_data)))
                else:
                    # Store chunks using DocumentChunkService
                    chunk_uuids = await self.document_chunk_service.store_document_chunks(
                        document=document,
                        quality_score=0.5  # Default quality score for testing
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
        # Use the chunking service from DocumentChunkService
        chunks = self.document_chunk_service.chunking_service.chunk_document(document)
        return len(chunks)
    
    async def _get_document_list(
        self,
        mode: ReingestionMode,
        source_filter: str | None,
        date_filter: list[str] | None,
        pmid_list: list[str] | None
    ) -> list[dict[str, Any]]:
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
    
    async def get_reingest_status(self, job_id: str) -> dict[str, Any]:
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
        
        if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
            return False
        
        await self.db_service.update_job_status(job_id, JobStatus.CANCELLED)
        logger.info(f"Cancelled re-ingestion job {job_id}")
        return True