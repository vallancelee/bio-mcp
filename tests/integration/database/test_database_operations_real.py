"""
Database operations integration tests using real PostgreSQL via TestContainers.

This file replaces the failing async-mocked tests with real database tests,
eliminating all async mocking complexity.
"""

import asyncio

import pytest
from sqlalchemy import text

from bio_mcp.shared.clients.database import (
    DatabaseHealthCheck,
    ValidationError,
)


class TestDatabaseManagerOperations:
    """Test DatabaseManager core operations with real PostgreSQL."""

    @pytest.mark.asyncio
    async def test_initialization_and_cleanup_lifecycle(self, clean_db):
        """Test database initialization and cleanup lifecycle."""
        # No mocking needed - this is a real database manager
        assert clean_db.engine is not None
        assert clean_db.session_factory is not None
        assert clean_db.config.url is not None

        # Test that we can create a session
        session = clean_db.get_session()
        assert session is not None

        # Test we can execute simple query
        async with session as s:
            result = await s.execute(text("SELECT 1"))
            assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_transaction_handling_and_rollbacks(self, clean_db):
        """Test transaction management, commits, rollbacks."""
        # Test successful transaction
        doc_data = {
            "pmid": "TRANS_001",
            "title": "Transaction Test Document",
            "abstract": "Testing transaction handling",
        }

        created_doc = await clean_db.create_document(doc_data)
        assert created_doc.pmid == "TRANS_001"

        # Verify it was committed
        retrieved_doc = await clean_db.get_document_by_pmid("TRANS_001")
        assert retrieved_doc is not None
        assert retrieved_doc.pmid == "TRANS_001"

        # Test rollback on constraint violation
        with pytest.raises(ValidationError, match="already exists"):
            await clean_db.create_document(doc_data)  # Duplicate PMID

        # Verify original document still exists
        retrieved_doc = await clean_db.get_document_by_pmid("TRANS_001")
        assert retrieved_doc is not None

    @pytest.mark.asyncio
    async def test_crud_operations_comprehensive(self, clean_db):
        """Test Create, Read, Update, Delete operations comprehensively."""
        # CREATE
        doc_data = {
            "pmid": "CRUD_TEST_001",
            "title": "Comprehensive CRUD Test",
            "abstract": "Testing all CRUD operations with real database",
            "authors": ["Test, Author", "Researcher, Primary"],
            "journal": "Real Database Journal",
            "keywords": ["crud", "testing", "postgresql", "real"],
        }

        created_doc = await clean_db.create_document(doc_data)
        assert created_doc.pmid == "CRUD_TEST_001"
        assert len(created_doc.authors) == 2
        assert len(created_doc.keywords) == 4

        # READ
        retrieved_doc = await clean_db.get_document_by_pmid("CRUD_TEST_001")
        assert retrieved_doc is not None
        assert retrieved_doc.title == "Comprehensive CRUD Test"
        assert retrieved_doc.authors == ["Test, Author", "Researcher, Primary"]

        # READ non-existent
        not_found = await clean_db.get_document_by_pmid("NONEXISTENT")
        assert not_found is None

        # UPDATE
        updates = {
            "title": "Updated CRUD Test",
            "abstract": "Updated abstract content",
            "keywords": ["updated", "crud", "testing"],
        }

        updated_doc = await clean_db.update_document("CRUD_TEST_001", updates)
        assert updated_doc.title == "Updated CRUD Test"
        assert updated_doc.abstract == "Updated abstract content"
        assert len(updated_doc.keywords) == 3
        assert updated_doc.updated_at > updated_doc.created_at

        # UPDATE non-existent
        no_update = await clean_db.update_document(
            "NONEXISTENT", {"title": "Won't work"}
        )
        assert no_update is None

        # DELETE
        deleted = await clean_db.delete_document("CRUD_TEST_001")
        assert deleted is True

        # Verify deletion
        after_delete = await clean_db.get_document_by_pmid("CRUD_TEST_001")
        assert after_delete is None

        # DELETE non-existent
        not_deleted = await clean_db.delete_document("NONEXISTENT")
        assert not_deleted is False

    @pytest.mark.asyncio
    async def test_bulk_operations_and_performance(self, clean_db):
        """Test bulk document operations with performance validation."""
        import time

        # Prepare bulk data
        docs_data = [
            {
                "pmid": f"BULK_{i:05d}",
                "title": f"Bulk Document {i}",
                "abstract": f"Bulk abstract {i}" if i % 2 == 0 else None,
                "authors": [f"Author{i}"] if i % 3 == 0 else [],
                "keywords": ["bulk", "test", f"group_{i % 5}"],
            }
            for i in range(50)  # 50 documents for reasonable test time
        ]

        # Measure bulk creation
        start_time = time.time()
        created_docs = await clean_db.bulk_create_documents(docs_data)
        elapsed = time.time() - start_time

        assert len(created_docs) == 50
        assert elapsed < 10.0  # Should complete within 10 seconds

        # Verify all were created
        all_docs = await clean_db.list_documents(limit=100)
        assert len(all_docs) == 50

        # Test pagination
        page1 = await clean_db.list_documents(limit=20, offset=0)
        page2 = await clean_db.list_documents(limit=20, offset=20)
        page3 = await clean_db.list_documents(limit=20, offset=40)

        assert len(page1) == 20
        assert len(page2) == 20
        assert len(page3) == 10  # Remaining documents

        # Verify no overlap
        page1_ids = {doc.pmid for doc in page1}
        page2_ids = {doc.pmid for doc in page2}
        page3_ids = {doc.pmid for doc in page3}

        assert page1_ids.isdisjoint(page2_ids)
        assert page1_ids.isdisjoint(page3_ids)
        assert page2_ids.isdisjoint(page3_ids)

    @pytest.mark.asyncio
    async def test_document_existence_and_search(self, clean_db):
        """Test document existence checking and search functionality."""
        # Create test documents
        test_docs = [
            {"pmid": "SEARCH_001", "title": "Cancer Research Paper"},
            {"pmid": "SEARCH_002", "title": "Cancer Treatment Methods"},
            {"pmid": "SEARCH_003", "title": "Diabetes Management Study"},
            {"pmid": "SEARCH_004", "title": "Machine Learning in Medicine"},
        ]

        for doc_data in test_docs:
            await clean_db.create_document(doc_data)

        # Test existence checks
        assert await clean_db.document_exists("SEARCH_001") is True
        assert await clean_db.document_exists("SEARCH_999") is False

        # Test search by title
        cancer_docs = await clean_db.search_documents_by_title("cancer")
        assert len(cancer_docs) == 2

        study_docs = await clean_db.search_documents_by_title("study")
        assert len(study_docs) == 1
        assert study_docs[0].pmid == "SEARCH_003"

        no_results = await clean_db.search_documents_by_title("nonexistent")
        assert len(no_results) == 0

    @pytest.mark.asyncio
    async def test_sync_watermark_operations(self, clean_db):
        """Test sync watermark CRUD operations for incremental sync."""
        # Create initial watermark
        watermark = await clean_db.create_or_update_sync_watermark(
            query_key="test_sync_query",
            last_edat="2024/01/01",
            total_synced="100",
            last_sync_count="100",
        )

        assert watermark.query_key == "test_sync_query"
        assert watermark.last_edat == "2024/01/01"
        assert watermark.total_synced == "100"
        assert watermark.last_sync_count == "100"

        # Retrieve watermark
        retrieved = await clean_db.get_sync_watermark("test_sync_query")
        assert retrieved is not None
        assert retrieved.query_key == "test_sync_query"
        assert retrieved.total_synced == "100"

        # Update watermark (incremental sync)
        updated = await clean_db.create_or_update_sync_watermark(
            query_key="test_sync_query",
            last_edat="2024/01/02",
            total_synced="150",
            last_sync_count="50",
        )

        assert updated.last_edat == "2024/01/02"
        assert updated.total_synced == "150"
        assert updated.last_sync_count == "50"

        # Verify update persistence
        final_check = await clean_db.get_sync_watermark("test_sync_query")
        assert final_check.total_synced == "150"

        # Test non-existent watermark
        none_result = await clean_db.get_sync_watermark("nonexistent_query")
        assert none_result is None

    @pytest.mark.asyncio
    async def test_corpus_checkpoint_management(self, clean_db):
        """Test corpus checkpoint creation and management."""
        # Create some documents first
        for i in range(5):
            await clean_db.create_document(
                {"pmid": f"CHECKPOINT_{i:03d}", "title": f"Checkpoint Document {i}"}
            )

        # Create sync watermarks
        await clean_db.create_or_update_sync_watermark(
            query_key="checkpoint_query_1", last_edat="2024/01/01", total_synced="3"
        )
        await clean_db.create_or_update_sync_watermark(
            query_key="checkpoint_query_2", last_edat="2024/01/02", total_synced="2"
        )

        # Create checkpoint
        checkpoint = await clean_db.create_corpus_checkpoint(
            checkpoint_id="test_checkpoint_001",
            name="Test Checkpoint",
            description="Testing checkpoint creation",
            primary_queries=["checkpoint_query_1", "checkpoint_query_2"],
        )

        assert checkpoint.checkpoint_id == "test_checkpoint_001"
        assert checkpoint.name == "Test Checkpoint"
        assert checkpoint.total_documents == "5"  # 5 documents created
        assert len(checkpoint.primary_queries) == 2
        assert "checkpoint_query_1" in checkpoint.sync_watermarks
        assert "checkpoint_query_2" in checkpoint.sync_watermarks

        # Retrieve checkpoint
        retrieved = await clean_db.get_corpus_checkpoint("test_checkpoint_001")
        assert retrieved is not None
        assert retrieved.total_documents == "5"

        # Create child checkpoint
        child = await clean_db.create_corpus_checkpoint(
            checkpoint_id="test_checkpoint_002",
            name="Child Checkpoint",
            description="Child of test_checkpoint_001",
            parent_checkpoint_id="test_checkpoint_001",
        )

        assert child.parent_checkpoint_id == "test_checkpoint_001"

        # List checkpoints
        all_checkpoints = await clean_db.list_corpus_checkpoints()
        assert len(all_checkpoints) == 2

        # Test checkpoint deletion
        deleted = await clean_db.delete_corpus_checkpoint("test_checkpoint_002")
        assert deleted is True

        remaining = await clean_db.list_corpus_checkpoints()
        assert len(remaining) == 1
        assert remaining[0].checkpoint_id == "test_checkpoint_001"

    @pytest.mark.asyncio
    async def test_concurrent_operations_safety(self, clean_db):
        """Test concurrent database operations with real PostgreSQL."""

        async def create_document_task(doc_id: int):
            """Create a document with unique ID."""
            return await clean_db.create_document(
                {
                    "pmid": f"CONCURRENT_{doc_id:04d}",
                    "title": f"Concurrent Document {doc_id}",
                    "abstract": f"Created concurrently {doc_id}",
                }
            )

        async def check_document_task(doc_id: int):
            """Check if a document exists."""
            return await clean_db.document_exists(f"CONCURRENT_{doc_id:04d}")

        # Create 10 documents concurrently
        create_tasks = [create_document_task(i) for i in range(10)]
        created_docs = await asyncio.gather(*create_tasks, return_exceptions=True)

        # All should succeed
        successful_docs = [
            doc for doc in created_docs if not isinstance(doc, Exception)
        ]
        assert len(successful_docs) == 10

        # Check existence concurrently
        check_tasks = [check_document_task(i) for i in range(10)]
        existence_results = await asyncio.gather(*check_tasks)

        # All should exist
        assert all(exists for exists in existence_results)

        # Verify total count
        all_docs = await clean_db.list_documents(limit=20)
        assert len(all_docs) == 10


class TestDatabaseHealthAndMonitoring:
    """Test database health checking and monitoring features."""

    @pytest.mark.asyncio
    async def test_database_health_check(self, db_manager):
        """Test database health check functionality."""
        health_checker = DatabaseHealthCheck(db_manager)
        health_status = await health_checker.check_health()

        assert health_status["status"] == "healthy"
        assert "checks" in health_status

        # Connection check
        connection_check = health_status["checks"]["database_connection"]
        assert connection_check["status"] == "healthy"
        assert "response_time_ms" in connection_check
        assert connection_check["response_time_ms"] > 0

        # Table accessibility check
        table_check = health_status["checks"]["table_accessibility"]
        assert table_check["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_connection_pool_behavior(self, db_manager):
        """Test connection pool handling with concurrent requests."""

        async def use_connection_briefly():
            """Use a database connection briefly."""
            async with db_manager.get_session() as session:
                result = await session.execute(
                    text("SELECT COUNT(*) FROM pubmed_documents")
                )
                count = result.scalar()
                await asyncio.sleep(0.1)  # Brief hold
                return count

        # Create many concurrent connection requests
        tasks = [use_connection_briefly() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # All should complete successfully
        assert len(results) == 20
        assert all(isinstance(result, int) for result in results)


class TestDatabaseErrorHandling:
    """Test database error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_constraint_violation_handling(self, clean_db):
        """Test handling of database constraint violations."""
        # Create initial document
        doc_data = {"pmid": "CONSTRAINT_TEST", "title": "Original Document"}
        await clean_db.create_document(doc_data)

        # Attempt duplicate creation
        with pytest.raises(ValidationError) as exc_info:
            await clean_db.create_document(doc_data)

        assert "already exists" in str(exc_info.value)
        assert "CONSTRAINT_TEST" in str(exc_info.value)

        # Verify original document is unaffected
        original = await clean_db.get_document_by_pmid("CONSTRAINT_TEST")
        assert original is not None
        assert original.title == "Original Document"

    @pytest.mark.asyncio
    async def test_invalid_data_handling(self, clean_db):
        """Test handling of invalid data."""
        # Test missing required fields
        with pytest.raises(ValidationError, match="PMID is required"):
            await clean_db.create_document({"pmid": None, "title": "Test"})

        with pytest.raises(ValidationError, match="PMID is required"):
            await clean_db.create_document({"pmid": "", "title": "Test"})

        with pytest.raises(ValidationError, match="Title is required"):
            await clean_db.create_document({"pmid": "123", "title": None})

        with pytest.raises(ValidationError, match="Title is required"):
            await clean_db.create_document({"pmid": "123", "title": ""})

    @pytest.mark.asyncio
    async def test_checkpoint_constraint_handling(self, clean_db):
        """Test corpus checkpoint constraint handling."""
        # Create initial checkpoint
        checkpoint = await clean_db.create_corpus_checkpoint(
            checkpoint_id="UNIQUE_CHECKPOINT", name="Unique Checkpoint"
        )
        assert checkpoint.checkpoint_id == "UNIQUE_CHECKPOINT"

        # Attempt duplicate checkpoint ID
        with pytest.raises(ValidationError, match="already exists"):
            await clean_db.create_corpus_checkpoint(
                checkpoint_id="UNIQUE_CHECKPOINT", name="Duplicate Checkpoint"
            )

        # Verify original checkpoint is unaffected
        original = await clean_db.get_corpus_checkpoint("UNIQUE_CHECKPOINT")
        assert original is not None
        assert original.name == "Unique Checkpoint"


class TestDatabasePerformance:
    """Test database performance characteristics."""

    @pytest.mark.asyncio
    async def test_large_dataset_operations(self, clean_db):
        """Test operations with larger datasets."""
        import time

        # Create 100 documents
        docs_data = [
            {
                "pmid": f"PERF_{i:05d}",
                "title": f"Performance Test Document {i}",
                "abstract": f"Abstract {i} " * 10,  # Larger text
                "authors": [f"Author{i}A", f"Author{i}B", f"Author{i}C"],
                "keywords": [
                    f"keyword{i}",
                    "performance",
                    "test",
                    f"category_{i % 10}",
                ],
            }
            for i in range(100)
        ]

        # Bulk creation timing
        start = time.time()
        created = await clean_db.bulk_create_documents(docs_data)
        bulk_time = time.time() - start

        assert len(created) == 100
        assert bulk_time < 15.0  # Should complete within 15 seconds

        # Search performance
        start = time.time()
        search_results = await clean_db.search_documents_by_title("Performance")
        search_time = time.time() - start

        assert len(search_results) == 100  # All match "Performance"
        assert search_time < 5.0  # Search should be fast

        # Pagination performance
        start = time.time()
        paginated = await clean_db.list_documents(limit=25, offset=50)
        pagination_time = time.time() - start

        assert len(paginated) == 25
        assert pagination_time < 2.0  # Pagination should be fast


# Mark all tests in this file as integration and testcontainers
pytestmark = [pytest.mark.integration, pytest.mark.testcontainers]
