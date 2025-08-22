"""
Example integration tests using TestContainers with PostgreSQL.

These tests demonstrate how to test database operations with a real PostgreSQL
instance, completely avoiding async mocking issues.

Prerequisites:
1. Install testcontainers: uv add --dev testcontainers[postgres]
2. Ensure Docker is running
3. Rename conftest_testcontainers.py to conftest.py
"""

import pytest
from sqlalchemy import text

from bio_mcp.shared.clients.database import (
    ValidationError,
)


class TestDatabaseOperationsWithRealPostgres:
    """Test database operations using real PostgreSQL container."""

    @pytest.mark.asyncio
    async def test_document_crud_operations(self, clean_db):
        """Test Create, Read, Update, Delete operations with real database."""
        # CREATE
        doc_data = {
            "pmid": "TC_001",
            "title": "TestContainers Test Document",
            "abstract": "This document is stored in a real PostgreSQL database",
            "authors": ["Smith, J.", "Doe, A."],
            "journal": "TestContainers Journal",
            "keywords": ["testing", "postgresql", "testcontainers"],
        }

        created_doc = await clean_db.create_document(doc_data)
        assert created_doc.pmid == "TC_001"
        assert created_doc.title == "TestContainers Test Document"
        assert len(created_doc.authors) == 2

        # READ
        retrieved_doc = await clean_db.get_document_by_pmid("TC_001")
        assert retrieved_doc is not None
        assert retrieved_doc.pmid == created_doc.pmid
        assert retrieved_doc.abstract == created_doc.abstract

        # UPDATE
        updates = {
            "title": "Updated TestContainers Document",
            "keywords": ["testing", "updated", "postgresql"],
        }
        updated_doc = await clean_db.update_document("TC_001", updates)
        assert updated_doc.title == "Updated TestContainers Document"
        assert "updated" in updated_doc.keywords

        # DELETE
        deleted = await clean_db.delete_document("TC_001")
        assert deleted is True

        # Verify deletion
        deleted_doc = await clean_db.get_document_by_pmid("TC_001")
        assert deleted_doc is None

    @pytest.mark.asyncio
    async def test_transaction_integrity(self, clean_db):
        """Test transaction rollback on constraint violations."""
        # Create initial document
        doc1 = await clean_db.create_document(
            {"pmid": "UNIQUE_123", "title": "Original Document"}
        )

        # Attempt to create duplicate - should fail and rollback
        with pytest.raises(ValidationError) as exc_info:
            await clean_db.create_document(
                {"pmid": "UNIQUE_123", "title": "Duplicate Document"}
            )

        assert "already exists" in str(exc_info.value)

        # Verify only original document exists
        docs = await clean_db.list_documents()
        assert len(docs) == 1
        assert docs[0].title == "Original Document"

    @pytest.mark.asyncio
    async def test_bulk_operations_performance(self, clean_db):
        """Test bulk document creation with real database."""
        import time

        # Prepare bulk data
        docs_data = [
            {
                "pmid": f"BULK_{i:05d}",
                "title": f"Bulk Document {i}",
                "abstract": f"Abstract for document {i}" if i % 2 == 0 else None,
                "authors": [f"Author{i}A", f"Author{i}B"] if i % 3 == 0 else [],
                "keywords": [f"keyword{i % 10}", "bulk", "test"],
            }
            for i in range(100)
        ]

        # Measure bulk creation time
        start_time = time.time()
        created_docs = await clean_db.bulk_create_documents(docs_data)
        elapsed = time.time() - start_time

        assert len(created_docs) == 100
        assert elapsed < 5.0  # Should complete within 5 seconds

        # Verify all documents were created
        all_docs = await clean_db.list_documents(limit=200)
        assert len(all_docs) == 100

    @pytest.mark.asyncio
    async def test_search_functionality(self, db_with_sample_data):
        """Test document search with sample data."""
        db_manager, sample_data = db_with_sample_data

        # Search by title
        cancer_docs = await db_manager.search_documents_by_title("Sample")
        assert len(cancer_docs) == 10  # All sample docs have "Sample" in title

        # Search with no results
        no_results = await db_manager.search_documents_by_title("NonExistent")
        assert len(no_results) == 0

    @pytest.mark.asyncio
    async def test_sync_watermark_workflow(self, clean_db):
        """Test incremental sync watermark functionality."""
        # Initial sync
        watermark = await clean_db.create_or_update_sync_watermark(
            query_key="cancer AND therapy",
            last_edat="2024/01/01",
            total_synced="100",
            last_sync_count="100",
        )

        assert watermark.query_key == "cancer AND therapy"
        assert watermark.total_synced == "100"

        # Incremental sync
        updated_watermark = await clean_db.create_or_update_sync_watermark(
            query_key="cancer AND therapy",
            last_edat="2024/01/02",
            total_synced="150",
            last_sync_count="50",
        )

        assert updated_watermark.total_synced == "150"
        assert updated_watermark.last_sync_count == "50"
        assert updated_watermark.last_edat == "2024/01/02"

        # Retrieve watermark
        retrieved = await clean_db.get_sync_watermark("cancer AND therapy")
        assert retrieved.total_synced == "150"

    @pytest.mark.asyncio
    async def test_corpus_checkpoint_management(self, db_with_sample_data):
        """Test corpus checkpoint creation and retrieval."""
        db_manager, sample_data = db_with_sample_data

        # Checkpoint should capture current state
        checkpoint = sample_data["checkpoints"][0]
        assert checkpoint.checkpoint_id == "test_checkpoint_001"
        assert checkpoint.total_documents == "10"  # 10 sample documents

        # Create child checkpoint
        child_checkpoint = await db_manager.create_corpus_checkpoint(
            checkpoint_id="test_checkpoint_002",
            name="Child Checkpoint",
            description="Derived from test_checkpoint_001",
            parent_checkpoint_id="test_checkpoint_001",
        )

        assert child_checkpoint.parent_checkpoint_id == "test_checkpoint_001"

        # List checkpoints
        all_checkpoints = await db_manager.list_corpus_checkpoints()
        assert len(all_checkpoints) == 2

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, clean_db):
        """Test concurrent database operations."""
        import asyncio

        async def create_document(pmid: str):
            """Helper to create a document."""
            return await clean_db.create_document(
                {"pmid": pmid, "title": f"Concurrent Document {pmid}"}
            )

        # Create 20 documents concurrently
        tasks = [create_document(f"CONCURRENT_{i:03d}") for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 20

        # Verify all were created
        all_docs = await clean_db.list_documents(limit=50)
        assert len(all_docs) == 20

    @pytest.mark.asyncio
    async def test_pagination(self, db_with_sample_data):
        """Test pagination with real database."""
        db_manager, _ = db_with_sample_data

        # First page
        page1 = await db_manager.list_documents(limit=5, offset=0)
        assert len(page1) == 5

        # Second page
        page2 = await db_manager.list_documents(limit=5, offset=5)
        assert len(page2) == 5

        # Verify no overlap
        page1_ids = {doc.pmid for doc in page1}
        page2_ids = {doc.pmid for doc in page2}
        assert page1_ids.isdisjoint(page2_ids)

        # Third page (partial)
        page3 = await db_manager.list_documents(limit=5, offset=10)
        assert len(page3) == 0  # Only 10 documents total

    @pytest.mark.asyncio
    async def test_data_integrity_constraints(self, clean_db):
        """Test database constraints and data integrity."""
        # Test required fields
        with pytest.raises(ValidationError) as exc_info:
            await clean_db.create_document({"pmid": None, "title": "Test"})
        assert "PMID is required" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            await clean_db.create_document({"pmid": "123", "title": None})
        assert "Title is required" in str(exc_info.value)

        # Test checkpoint constraints
        with pytest.raises(ValidationError) as exc_info:
            await clean_db.create_corpus_checkpoint(
                checkpoint_id=None, name="Test Checkpoint"
            )
        assert "Checkpoint ID is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_json_field_handling(self, clean_db):
        """Test JSON fields with real PostgreSQL."""
        # Create document with complex JSON fields
        doc = await clean_db.create_document(
            {
                "pmid": "JSON_TEST",
                "title": "JSON Field Test",
                "authors": ["Smith, J.", "Doe, A.", "Johnson, B."],
                "keywords": ["test", "json", "postgresql", "nested", "data"],
            }
        )

        # Retrieve and verify JSON fields
        retrieved = await clean_db.get_document_by_pmid("JSON_TEST")
        assert isinstance(retrieved.authors, list)
        assert len(retrieved.authors) == 3
        assert isinstance(retrieved.keywords, list)
        assert len(retrieved.keywords) == 5

        # Update JSON fields
        updated = await clean_db.update_document(
            "JSON_TEST",
            {"authors": ["New Author"], "keywords": ["updated", "keywords"]},
        )

        assert len(updated.authors) == 1
        assert updated.authors[0] == "New Author"
        assert len(updated.keywords) == 2


class TestDatabaseHealthChecks:
    """Test database health monitoring with real PostgreSQL."""

    @pytest.mark.asyncio
    async def test_health_check(self, db_manager):
        """Test database health check functionality."""
        from bio_mcp.shared.clients.database import DatabaseHealthCheck

        health_checker = DatabaseHealthCheck(db_manager)
        health_status = await health_checker.check_health()

        assert health_status["status"] == "healthy"
        assert "database_connection" in health_status["checks"]
        assert health_status["checks"]["database_connection"]["status"] == "healthy"
        assert "response_time_ms" in health_status["checks"]["database_connection"]

    @pytest.mark.asyncio
    async def test_connection_pool_monitoring(self, db_manager):
        """Test connection pool behavior with real database."""
        import asyncio

        # Create multiple concurrent connections
        async def use_connection():
            async with db_manager.get_session() as session:
                await session.execute(text("SELECT 1"))
                await asyncio.sleep(0.1)  # Hold connection briefly

        # Use pool connections concurrently
        tasks = [use_connection() for _ in range(10)]
        await asyncio.gather(*tasks)

        # All connections should complete successfully
        # Pool should handle concurrent requests


class TestIsolatedSchemas:
    """Test using isolated schemas for parallel test execution."""

    @pytest.mark.asyncio
    async def test_isolated_schema_creation(self, isolated_db_manager):
        """Test that isolated schema provides clean environment."""
        # Create document in isolated schema
        doc = await isolated_db_manager.create_document(
            {"pmid": "ISOLATED_001", "title": "Isolated Schema Test"}
        )

        assert doc.pmid == "ISOLATED_001"

        # This document only exists in this schema
        docs = await isolated_db_manager.list_documents()
        assert len(docs) == 1

    @pytest.mark.asyncio
    async def test_parallel_schema_isolation(self, postgres_container):
        """Test that parallel schemas don't interfere."""
        import asyncio

        import asyncpg

        async def create_and_test_schema(schema_id: int):
            """Create isolated schema and test it."""
            schema_name = f"parallel_test_{schema_id}"

            # Create schema
            conn_url = postgres_container.get_connection_url()
            conn = await asyncpg.connect(conn_url)
            await conn.execute(f"CREATE SCHEMA {schema_name}")
            await conn.close()

            # Use schema
            from bio_mcp.shared.clients.database import DatabaseConfig, DatabaseManager

            async_url = conn_url.replace("postgresql://", "postgresql+asyncpg://")
            config = DatabaseConfig(
                url=f"{async_url}?options=-csearch_path={schema_name}"
            )

            manager = DatabaseManager(config)
            await manager.initialize()

            # Create document unique to this schema
            doc = await manager.create_document(
                {
                    "pmid": f"SCHEMA_{schema_id}_DOC",
                    "title": f"Document in schema {schema_id}",
                }
            )

            # Verify isolation
            docs = await manager.list_documents()
            assert len(docs) == 1
            assert docs[0].pmid == f"SCHEMA_{schema_id}_DOC"

            # Cleanup
            await manager.close()
            conn = await asyncpg.connect(conn_url)
            await conn.execute(f"DROP SCHEMA {schema_name} CASCADE")
            await conn.close()

            return schema_id

        # Run tests in parallel schemas
        tasks = [create_and_test_schema(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert results == [0, 1, 2, 3, 4]


# Marker for TestContainer tests
pytestmark = pytest.mark.testcontainers
