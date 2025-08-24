import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from bio_mcp.config.config import Config
from bio_mcp.services.reingest_service import (
    ReingestionMode,
    ReingestionService,
    ReingestionStats,
)
from bio_mcp.shared.models.database_models import JobStatus


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Re-ingestion requires OpenAI API key for embeddings"
)
class TestReingestionIntegration:
    """Integration tests for re-ingestion service."""
    
    @pytest.fixture
    def config(self):
        config = Config()
        # Mock the configuration values
        config.BIO_MCP_REINGEST_BATCH_SIZE = "10"
        config.BIO_MCP_REINGEST_CONCURRENCY = "2"
        return config
    
    @pytest.mark.asyncio
    async def test_reingest_stats_tracking(self, config):
        """Test re-ingestion statistics tracking."""
        stats = ReingestionStats()
        
        # Test adding successes
        stats.add_success("test:123", 5, 1000)
        stats.add_success("test:456", 3, 800)
        
        # Test adding failures
        stats.add_failure("test:789", "Connection error", {"retry": 1})
        
        summary = stats.get_summary()
        assert summary["documents_processed"] == 2
        assert summary["documents_failed"] == 1
        assert summary["chunks_created"] == 8
        assert summary["bytes_processed"] == 1800
        assert len(summary["errors_sample"]) == 1
        
        # Test success rate calculation
        assert summary["success_rate"] == 2/3  # 2 success out of 3 total
    
    @pytest.mark.asyncio
    async def test_reingest_service_initialization(self, config):
        """Test re-ingestion service initialization."""
        service = ReingestionService(config)
        
        assert service.batch_size == 10
        assert service.max_concurrent == 2
        assert service.retry_attempts == 3  # default
        assert service.retry_delay == 5  # default
    
    @pytest.mark.asyncio
    async def test_job_lifecycle_validation_mode(self, config):
        """Test complete job lifecycle in validation mode."""
        service = ReingestionService(config)
        
        # Mock all the services to avoid external dependencies
        with patch.object(service.db_service, 'create_job', return_value="test-job-id") as mock_create, \
             patch.object(service.db_service, 'get_job') as mock_get_job, \
             patch.object(service.db_service, 'update_job_status') as mock_update_status, \
             patch.object(service.db_service, 'connect'), \
             patch.object(service.db_service, 'disconnect'), \
             patch.object(service.document_chunk_service, 'connect') as mock_weaviate_connect, \
             patch.object(service.document_chunk_service, 'disconnect') as mock_weaviate_disconnect, \
             patch.object(service, '_get_document_list', return_value=[]), \
             patch.object(service, '_update_job_progress'):
            
            # Setup job mock
            job_mock = Mock()
            job_mock.parameters = {"mode": "validation", "dry_run": True}
            mock_get_job.return_value = job_mock
            
            # Test job creation
            job_id = await service.start_reingest_job(
                mode=ReingestionMode.VALIDATION,
                dry_run=True
            )
            
            assert job_id == "test-job-id"
            mock_create.assert_called_once()
            
            # Test job execution
            result = await service.execute_reingest_job(job_id)
            
            # Verify weaviate connection was made (db_service may use its own connection logic)
            mock_weaviate_connect.assert_called_once() 
            
            # Verify status was updated to running and completed
            assert mock_update_status.call_count >= 2
            
            # Verify weaviate connection was closed
            mock_weaviate_disconnect.assert_called_once()
            
            # Verify result structure
            assert "documents_processed" in result
            assert "documents_failed" in result
            assert "success_rate" in result
    
    @pytest.mark.asyncio
    async def test_error_handling_and_retry_logic(self, config):
        """Test error handling and retry logic."""
        stats = ReingestionStats()
        
        # Test adding failures with context
        stats.add_failure("test:123", "Timeout error", {"s3_key": "test.json", "attempts": 3})
        stats.add_failure("test:456", "Connection error")
        
        summary = stats.get_summary()
        assert summary["documents_failed"] == 2
        assert len(summary["errors_sample"]) == 2
        assert summary["errors_sample"][0]["context"]["attempts"] == 3
    
    @pytest.mark.asyncio
    async def test_batch_processing_logic(self, config):
        """Test batched document processing logic."""
        service = ReingestionService(config)
        
        # Mock document processing
        mock_docs = [
            {"uid": f"test:{i}", "s3_key": f"test/{i}.json"}
            for i in range(25)  # More than one batch (batch_size=10)
        ]
        
        with patch.object(service.db_service, 'create_job', return_value="test-job-id"), \
             patch.object(service.db_service, 'get_job') as mock_get_job, \
             patch.object(service.db_service, 'update_job_status'), \
             patch.object(service.db_service, 'connect'), \
             patch.object(service.db_service, 'disconnect'), \
             patch.object(service.document_chunk_service, 'connect'), \
             patch.object(service.document_chunk_service, 'disconnect'), \
             patch.object(service, '_get_document_list', return_value=mock_docs), \
             patch.object(service, '_process_single_document', new_callable=AsyncMock) as mock_process, \
             patch.object(service, '_update_job_progress', new_callable=AsyncMock) as mock_update_progress:
            
            # Setup job mock
            job_mock = Mock()
            job_mock.parameters = {"mode": "validation", "dry_run": True}
            mock_get_job.return_value = job_mock
            
            await service.execute_reingest_job("test-job-id")
            
            # Should have processed all documents
            assert mock_process.call_count == 25
            
            # Should have updated progress multiple times (for each batch)
            # We expect at least 3 calls for 25 documents with batch_size=10
            assert mock_update_progress.call_count >= 3
    
    @pytest.mark.asyncio 
    async def test_job_cancellation(self, config):
        """Test job cancellation functionality."""
        service = ReingestionService(config)
        
        with patch.object(service.db_service, 'get_job') as mock_get_job, \
             patch.object(service.db_service, 'update_job_status') as mock_update_status:
            
            # Test cancelling a running job
            running_job = Mock()
            running_job.status = JobStatus.RUNNING
            mock_get_job.return_value = running_job
            
            result = await service.cancel_reingest_job("test-job-id")
            
            assert result is True
            mock_update_status.assert_called_once_with("test-job-id", JobStatus.CANCELLED)
            
            # Test cancelling a completed job (should fail)
            completed_job = Mock()
            completed_job.status = JobStatus.COMPLETED
            mock_get_job.return_value = completed_job
            
            result = await service.cancel_reingest_job("test-job-id")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_reingest_status(self, config):
        """Test getting re-ingestion job status."""
        service = ReingestionService(config)
        
        with patch.object(service.db_service, 'get_job') as mock_get_job:
            
            # Mock job with status
            job_mock = Mock()
            job_mock.status.value = "completed"
            job_mock.progress = 100
            job_mock.created_at.isoformat.return_value = "2023-01-01T00:00:00"
            job_mock.updated_at.isoformat.return_value = "2023-01-01T01:00:00"
            job_mock.parameters = {"mode": "full", "dry_run": False}
            job_mock.result = {"documents_processed": 100}
            mock_get_job.return_value = job_mock
            
            status = await service.get_reingest_status("test-job-id")
            
            assert status["job_id"] == "test-job-id"
            assert status["status"] == "completed"
            assert status["progress"] == 100
            assert status["parameters"]["mode"] == "full"
            assert status["result"]["documents_processed"] == 100