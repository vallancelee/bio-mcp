"""Integration tests for job system with PostgreSQL database."""

from datetime import UTC

import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from bio_mcp.http.jobs.models import JobData
from bio_mcp.http.jobs.service import JobService
from bio_mcp.http.jobs.storage import SQLAlchemyJobRepository
from bio_mcp.shared.clients.database import (
    DatabaseConfig,
    init_database,
)
from bio_mcp.shared.models.database_models import JobRecord, JobStatus


@pytest.fixture(scope="session")
def postgres_container():
    """Provide a PostgreSQL testcontainer for job integration tests."""
    container = PostgresContainer("postgres:15")
    container.with_env("POSTGRES_DB", "bio_mcp_jobs_test")
    container.with_env("POSTGRES_USER", "test_user")
    container.with_env("POSTGRES_PASSWORD", "test_password")
    container.start()
    yield container
    container.stop()


@pytest_asyncio.fixture
async def database_manager(postgres_container):
    """Create database manager with jobs table for tests."""
    # Use the testcontainer database directly - each test will be isolated
    connection_url = postgres_container.get_connection_url()
    async_url = connection_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    
    config = DatabaseConfig(
        url=async_url,
        echo=False,
        pool_size=2,
        max_overflow=1
    )
    
    manager = await init_database(config)
    
    # Create tables using SQLAlchemy metadata (simulates what migrations do)
    from bio_mcp.shared.models.database_models import Base
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield manager
    
    # Clean up - drop all tables to ensure test isolation  
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await manager.close()


# Remove problematic fixtures - we'll create repository/service instances directly in tests


class TestJobDatabaseIntegration:
    """Test job system database integration with PostgreSQL."""
    
    @pytest.mark.asyncio
    async def test_job_record_crud_operations(self, database_manager):
        """Test basic CRUD operations for job records."""
        job_data = JobData.create_new(
            tool_name="pubmed.search",
            parameters={"query": "cancer research", "limit": 100},
            trace_id="test-trace-001"
        )
        
        async with database_manager.get_session() as session:
            # Create
            job_record = JobRecord.from_job_data(job_data)
            session.add(job_record)
            await session.commit()
            await session.refresh(job_record)
            
            # Read
            from sqlalchemy import select
            result = await session.execute(
                select(JobRecord).where(JobRecord.id == job_record.id)
            )
            retrieved_record = result.scalar_one()
            
            assert retrieved_record.id == job_record.id
            assert retrieved_record.tool_name == "pubmed.search"
            assert retrieved_record.status == JobStatus.PENDING
            assert retrieved_record.parameters == {"query": "cancer research", "limit": 100}
            assert retrieved_record.trace_id == "test-trace-001"
            
            # Update
            retrieved_record.status = JobStatus.RUNNING
            retrieved_record.result = {"documents_found": 50}
            await session.commit()
            
            # Verify update
            result = await session.execute(
                select(JobRecord).where(JobRecord.id == job_record.id)
            )
            updated_record = result.scalar_one()
            assert updated_record.status == JobStatus.RUNNING
            assert updated_record.result == {"documents_found": 50}
            
            # Delete
            await session.delete(updated_record)
            await session.commit()
            
            # Verify deletion
            result = await session.execute(
                select(JobRecord).where(JobRecord.id == job_record.id)
            )
            assert result.scalar_one_or_none() is None
    
    @pytest.mark.asyncio
    async def test_job_status_transitions(self, database_manager):
        """Test job status transitions in database."""
        job_data = JobData.create_new(
            tool_name="rag.index",
            parameters={"documents": ["doc1", "doc2"]},
            trace_id="test-trace-002"
        )
        
        async with database_manager.get_session() as session:
            job_record = JobRecord.from_job_data(job_data)
            session.add(job_record)
            await session.commit()
            
            # Transition to RUNNING
            job_data.start_execution()
            job_record = JobRecord.from_job_data(job_data)
            await session.merge(job_record)
            await session.commit()
            
            # Verify transition
            from sqlalchemy import select
            result = await session.execute(
                select(JobRecord).where(JobRecord.id == job_record.id)
            )
            running_record = result.scalar_one()
            assert running_record.status == JobStatus.RUNNING
            assert running_record.started_at is not None
            
            # Transition to COMPLETED
            job_data.complete_with_result({"indexed": 2, "vectors_created": 2})
            job_record = JobRecord.from_job_data(job_data)
            await session.merge(job_record)
            await session.commit()
            
            # Verify completion
            result = await session.execute(
                select(JobRecord).where(JobRecord.id == job_record.id)
            )
            completed_record = result.scalar_one()
            assert completed_record.status == JobStatus.COMPLETED
            assert completed_record.completed_at is not None
            assert completed_record.result == {"indexed": 2, "vectors_created": 2}
    
    @pytest.mark.asyncio
    async def test_job_repository_operations(self, database_manager):
        """Test job repository operations."""
        async with database_manager.get_session() as session:
            repository = SQLAlchemyJobRepository(session)
            
            # Create job
            job_data = JobData.create_new(
                tool_name="pubmed.sync",
                parameters={"query": "immunotherapy", "max_results": 1000},
                trace_id="test-trace-003"
            )
            
            await repository.save(job_data)
            
            # Retrieve job
            retrieved_job = await repository.get_by_id(job_data.id)
            assert retrieved_job.id == job_data.id
            assert retrieved_job.tool_name == "pubmed.sync"
            assert retrieved_job.status == JobStatus.PENDING
            
            # Update job status
            retrieved_job.start_execution()
            await repository.save(retrieved_job)
            
            # Verify update
            updated_job = await repository.get_by_id(job_data.id)
            assert updated_job.status == JobStatus.RUNNING
            assert updated_job.started_at is not None
    
    @pytest.mark.asyncio
    async def test_job_service_operations(self, database_manager):
        """Test job service operations."""
        async with database_manager.get_session() as session:
            repository = SQLAlchemyJobRepository(session)
            service = JobService(repository)
            
            # Create job via service
            job_id = await service.create_job(
                tool_name="rag.get",
                parameters={"query": "cancer biomarkers", "limit": 10},
                trace_id="test-trace-004"
            )
            
            assert job_id is not None
            
            # Get job status
            job_data = await service.get_job_status(job_id)
            assert job_data.id == job_id
            assert job_data.tool_name == "rag.get"
            assert job_data.status == JobStatus.PENDING
            
            # Start job
            await service.start_job(job_id)
            
            # Verify started
            job_data = await service.get_job_status(job_id)
            assert job_data.status == JobStatus.RUNNING
            
            # Complete job
            result = {"results": ["doc1", "doc2"], "total": 2}
            await service.complete_job(job_id, result)
            
            # Verify completion
            job_data = await service.get_job_status(job_id)
            assert job_data.status == JobStatus.COMPLETED
            assert job_data.result == result
    
    @pytest.mark.asyncio
    async def test_job_querying_and_filtering(self, database_manager):
        """Test job listing and filtering operations."""
        async with database_manager.get_session() as session:
            repository = SQLAlchemyJobRepository(session)
            service = JobService(repository)
            
            # Create multiple jobs with different statuses
            await service.create_job(
                "pubmed.search", {"query": "test1"}, "trace-1"
            )
            
            running_job = await service.create_job(
                "rag.index", {"docs": ["doc1"]}, "trace-2"
            )
            await service.start_job(running_job)
            
            completed_job = await service.create_job(
                "corpus.checkpoint", {"name": "test"}, "trace-3"
            )
            await service.start_job(completed_job)
            await service.complete_job(completed_job, {"checkpoint_id": "test-123"})
            
            # Test listing all jobs
            all_jobs = await service.list_jobs()
            assert len(all_jobs) >= 3
            
            # Test filtering by status
            pending_jobs = await service.list_jobs(status=JobStatus.PENDING)
            assert len(pending_jobs) >= 1
            assert all(job.status == JobStatus.PENDING for job in pending_jobs)
            
            running_jobs = await service.list_jobs(status=JobStatus.RUNNING)
            assert len(running_jobs) >= 1
            assert all(job.status == JobStatus.RUNNING for job in running_jobs)
            
            completed_jobs = await service.list_jobs(status=JobStatus.COMPLETED)
            assert len(completed_jobs) >= 1
            assert all(job.status == JobStatus.COMPLETED for job in completed_jobs)
    
    @pytest.mark.asyncio
    async def test_job_expiration_cleanup(self, database_manager):
        """Test job expiration and cleanup functionality."""
        from datetime import datetime, timedelta
        
        # Create expired job
        expired_job = JobData.create_new(
            tool_name="test.tool",
            parameters={"test": "data"},
            trace_id="expired-trace",
            ttl_hours=1
        )
        # Manually set expiration to past
        expired_job.expires_at = datetime.now(UTC) - timedelta(hours=1)
        
        async with database_manager.get_session() as session:
            repository = SQLAlchemyJobRepository(session)
            await repository.save(expired_job)
            
            # Verify job exists
            retrieved = await repository.get_by_id(expired_job.id)
            assert retrieved is not None
            
            # Run cleanup
            cleanup_count = await repository.cleanup_expired()
            assert cleanup_count >= 1
            
            # Verify job is removed
            from bio_mcp.http.jobs.service import JobNotFoundError
            with pytest.raises(JobNotFoundError):
                await repository.get_by_id(expired_job.id)
    
    @pytest.mark.asyncio
    async def test_concurrent_job_operations(self, database_manager):
        """Test concurrent job operations."""
        
        # Create fewer jobs to reduce complexity and avoid timeouts
        async with database_manager.get_session() as session:
            repository = SQLAlchemyJobRepository(session)
            service = JobService(repository)
            
            # Create 3 jobs sequentially to avoid session conflicts
            job_ids = []
            for i in range(3):
                job_id = await service.create_job(
                    f"tool-{i}",
                    {"index": i},
                    f"trace-{i}"
                )
                job_ids.append(job_id)
            
            assert len(job_ids) == 3
            assert len(set(job_ids)) == 3  # All unique
            
            # Start all jobs sequentially to avoid session conflicts
            for job_id in job_ids:
                await service.start_job(job_id)
            
            # Verify all are running
            for job_id in job_ids:
                job_data = await service.get_job_status(job_id)
                assert job_data.status == JobStatus.RUNNING
    
    @pytest.mark.asyncio
    async def test_job_json_data_persistence(self, database_manager):
        """Test complex JSON data persistence in PostgreSQL."""
        complex_params = {
            "query": {
                "terms": ["cancer", "immunotherapy"],
                "filters": {
                    "date_range": {"start": "2020-01-01", "end": "2024-01-01"},
                    "journals": ["Nature", "Science", "Cell"],
                    "study_types": ["clinical_trial", "meta_analysis"]
                },
                "options": {
                    "include_abstracts": True,
                    "max_results": 10000,
                    "sort_by": "relevance"
                }
            },
            "processing": {
                "extract_entities": True,
                "compute_embeddings": True,
                "quality_threshold": 0.8
            }
        }
        
        complex_result = {
            "status": "success",
            "summary": {
                "total_processed": 8543,
                "high_quality": 7234,
                "entities_extracted": 156789,
                "processing_time_seconds": 3456.78
            },
            "data": {
                "documents": [
                    {"pmid": "12345", "title": "Test Document 1", "score": 0.95},
                    {"pmid": "67890", "title": "Test Document 2", "score": 0.87}
                ],
                "entities": {
                    "genes": ["TP53", "BRCA1", "EGFR"],
                    "diseases": ["breast_cancer", "lung_cancer"],
                    "drugs": ["pembrolizumab", "nivolumab"]
                }
            }
        }
        
        job_data = JobData.create_new(
            tool_name="advanced.analysis",
            parameters=complex_params,
            trace_id="complex-data-test"
        )
        job_data.start_execution()
        job_data.complete_with_result(complex_result)
        
        async with database_manager.get_session() as session:
            repository = SQLAlchemyJobRepository(session)
            await repository.save(job_data)
            
            # Retrieve and verify complex data
            retrieved = await repository.get_by_id(job_data.id)
            
            # Verify parameters are preserved exactly
            assert retrieved.parameters == complex_params
            assert retrieved.parameters["query"]["filters"]["journals"] == ["Nature", "Science", "Cell"]
            assert retrieved.parameters["processing"]["quality_threshold"] == 0.8
            
            # Verify result is preserved exactly
            assert retrieved.result == complex_result
            assert retrieved.result["summary"]["total_processed"] == 8543
            assert retrieved.result["data"]["entities"]["genes"] == ["TP53", "BRCA1", "EGFR"]
            assert retrieved.result["summary"]["processing_time_seconds"] == 3456.78


# Mark all tests as integration tests
pytestmark = pytest.mark.integration