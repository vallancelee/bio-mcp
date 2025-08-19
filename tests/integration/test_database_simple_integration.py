"""
Simple integration test for database with testcontainers.
Focuses on verifying the TDD implementation works with real PostgreSQL.
"""

from datetime import date

import pytest
from testcontainers.postgres import PostgresContainer

from bio_mcp.database import DatabaseConfig, DatabaseManager


class TestDatabaseBasicIntegration:
    """Test basic database operations with real PostgreSQL."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_database_workflow(self):
        """Test complete database workflow with testcontainer."""
        
        # Start PostgreSQL container
        with PostgresContainer(
            image="postgres:15-alpine",
            port=5432,
            username="testuser",
            password="testpass", 
            dbname="testdb"
        ) as postgres:
            # Get async connection URL
            sync_url = postgres.get_connection_url()
            # Replace any postgresql driver with asyncpg
            async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
            async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")
            
            # Create database manager
            config = DatabaseConfig(url=async_url, echo=False)
            manager = DatabaseManager(config)
            
            try:
                # Initialize database
                await manager.initialize()
                
                # Verify initialization
                assert manager.engine is not None
                assert manager.session_factory is not None
                
                # Test basic CRUD operations
                
                # 1. Create a document
                doc_data = {
                    "pmid": "12345678",
                    "title": "Test CRISPR Article",
                    "abstract": "Testing database operations.",
                    "authors": ["Scientist, A.", "Researcher, B."],
                    "publication_date": date(2023, 6, 15),
                    "journal": "Test Journal",
                    "keywords": ["CRISPR", "testing"]
                }
                
                created_doc = await manager.create_document(doc_data)
                assert created_doc.pmid == "12345678"
                assert created_doc.title == "Test CRISPR Article"
                
                # 2. Retrieve the document
                retrieved_doc = await manager.get_document_by_pmid("12345678")
                assert retrieved_doc is not None
                assert retrieved_doc.title == "Test CRISPR Article"
                assert len(retrieved_doc.authors) == 2
                
                # 3. Update the document
                updates = {"abstract": "Updated abstract content."}
                updated_doc = await manager.update_document("12345678", updates)
                assert updated_doc.abstract == "Updated abstract content."
                
                # 4. Search documents
                search_results = await manager.search_documents_by_title("CRISPR")
                assert len(search_results) == 1
                assert search_results[0].pmid == "12345678"
                
                # 5. Check document exists
                exists = await manager.document_exists("12345678")
                assert exists is True
                
                not_exists = await manager.document_exists("99999999")
                assert not_exists is False
                
                # 6. Delete document
                deleted = await manager.delete_document("12345678")
                assert deleted is True
                
                # 7. Verify deletion
                deleted_doc = await manager.get_document_by_pmid("12345678")
                assert deleted_doc is None
                
                print("✅ All database operations completed successfully!")
                
            finally:
                # Clean up
                await manager.close()
    
    @pytest.mark.asyncio 
    async def test_database_health_check_integration(self):
        """Test database health check with real database."""
        
        with PostgresContainer(
            image="postgres:15-alpine",
            port=5432,
            username="testuser",
            password="testpass", 
            dbname="testdb"
        ) as postgres:
            sync_url = postgres.get_connection_url()
            # Replace any postgresql driver with asyncpg
            async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
            async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")
            
            config = DatabaseConfig(url=async_url)
            manager = DatabaseManager(config)
            
            try:
                await manager.initialize()
                
                # Test health check
                from bio_mcp.database import DatabaseHealthCheck
                health_checker = DatabaseHealthCheck(manager)
                
                health_result = await health_checker.check_health()
                
                # Verify health check results
                assert health_result["status"] == "healthy"
                assert "database_connection" in health_result["checks"]
                assert "table_accessibility" in health_result["checks"]
                
                db_check = health_result["checks"]["database_connection"]
                assert db_check["status"] == "healthy"
                assert "response_time_ms" in db_check
                
                table_check = health_result["checks"]["table_accessibility"]
                assert table_check["status"] == "healthy"
                
                print("✅ Database health check passed!")
                
            finally:
                await manager.close()
    
    @pytest.mark.asyncio
    async def test_bulk_operations_integration(self):
        """Test bulk operations with real database."""
        
        with PostgresContainer(
            image="postgres:15-alpine",
            port=5432,
            username="testuser",
            password="testpass", 
            dbname="testdb"
        ) as postgres:
            sync_url = postgres.get_connection_url()
            # Replace any postgresql driver with asyncpg
            async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
            async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")
            
            config = DatabaseConfig(url=async_url)
            manager = DatabaseManager(config)
            
            try:
                await manager.initialize()
                
                # Prepare bulk data
                docs_data = [
                    {
                        "pmid": f"1111111{i}",
                        "title": f"Bulk Document {i}",
                        "abstract": f"Abstract for document {i}."
                    }
                    for i in range(5)
                ]
                
                # Bulk create
                created_docs = await manager.bulk_create_documents(docs_data)
                assert len(created_docs) == 5
                
                # Test listing with pagination
                page1 = await manager.list_documents(limit=3, offset=0)
                assert len(page1) == 3
                
                page2 = await manager.list_documents(limit=3, offset=3)
                assert len(page2) == 2
                
                print("✅ Bulk operations completed successfully!")
                
            finally:
                await manager.close()