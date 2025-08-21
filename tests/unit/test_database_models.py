"""
Unit tests for database models.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bio_mcp.shared.models.database_models import (
    Base,
    CorpusCheckpoint,
    SyncWatermark,
    UniversalDocument,
)


class TestUniversalDocument:
    """Test UniversalDocument model."""
    
    def test_model_creation(self):
        """Test creating a UniversalDocument instance."""
        doc = UniversalDocument(
            id="pubmed:12345",
            source="pubmed",
            source_id="12345",
            title="Test Document"
        )
        
        assert doc.id == "pubmed:12345"
        assert doc.source == "pubmed"
        assert doc.source_id == "12345"
        assert doc.title == "Test Document"
        assert doc.abstract is None
        assert doc.content is None
        assert doc.authors is None
        assert doc.publication_date is None
        assert doc.source_metadata is None
        # quality_score default is set by SQLAlchemy, not Python
        # In pure model creation (not DB), it may be None
        assert doc.quality_score in (0, None)
        assert doc.last_updated is None
        # created_at and updated_at should be set by SQLAlchemy defaults
        assert hasattr(doc, 'created_at')
        assert hasattr(doc, 'updated_at')
    
    def test_model_with_all_fields(self):
        """Test creating a document with all fields populated."""
        pub_date = datetime(2023, 6, 15, 12, 30, 0)
        updated_date = datetime(2023, 7, 1, 10, 0, 0)
        
        doc = UniversalDocument(
            id="pubmed:67890",
            source="pubmed",
            source_id="67890",
            title="Comprehensive Test Document",
            abstract="This is a test abstract",
            content="Full searchable content here",
            authors=["Author A", "Author B", "Author C"],
            publication_date=pub_date,
            source_metadata={
                "journal": "Nature",
                "doi": "10.1038/s41586-023-12345-6",
                "impact_factor": 42.778,
                "mesh_terms": ["Biomarkers", "Therapeutics"]
            },
            quality_score=85,
            last_updated=updated_date
        )
        
        assert doc.id == "pubmed:67890"
        assert doc.source == "pubmed"
        assert doc.source_id == "67890"
        assert doc.title == "Comprehensive Test Document"
        assert doc.abstract == "This is a test abstract"
        assert doc.content == "Full searchable content here"
        assert doc.authors == ["Author A", "Author B", "Author C"]
        assert doc.publication_date == pub_date
        assert doc.source_metadata["journal"] == "Nature"
        assert doc.source_metadata["impact_factor"] == 42.778
        assert doc.quality_score == 85
        assert doc.last_updated == updated_date
    
    def test_clinicaltrials_document(self):
        """Test creating a ClinicalTrials.gov document."""
        doc = UniversalDocument(
            id="clinicaltrials:NCT05123456",
            source="clinicaltrials",
            source_id="NCT05123456",
            title="Phase II Clinical Trial for Novel Cancer Therapy",
            abstract="A randomized controlled trial evaluating efficacy",
            source_metadata={
                "phase": "Phase 2",
                "status": "Recruiting",
                "conditions": ["Non-small cell lung cancer"],
                "sponsors": ["Biotech Corp"],
                "enrollment": 200
            },
            quality_score=75
        )
        
        assert doc.source == "clinicaltrials"
        assert doc.source_id == "NCT05123456"
        assert doc.id == "clinicaltrials:NCT05123456"
        assert doc.source_metadata["phase"] == "Phase 2"
        assert doc.source_metadata["enrollment"] == 200
    
    def test_table_name(self):
        """Test that table name is correctly set."""
        assert UniversalDocument.__tablename__ == 'documents_universal'
    
    def test_primary_key(self):
        """Test primary key configuration."""
        assert UniversalDocument.id.primary_key is True
        assert UniversalDocument.id.type.length == 255


class TestSyncWatermark:
    """Test SyncWatermark model."""
    
    def test_model_creation(self):
        """Test creating a SyncWatermark instance."""
        timestamp = datetime(2023, 8, 15, 14, 30, 0)
        
        watermark = SyncWatermark(
            source="pubmed",
            query_key="cancer_biomarkers",
            last_sync=timestamp
        )
        
        assert watermark.source == "pubmed"
        assert watermark.query_key == "cancer_biomarkers"
        assert watermark.last_sync == timestamp
        assert hasattr(watermark, 'created_at')
        assert hasattr(watermark, 'updated_at')
    
    def test_different_sources(self):
        """Test watermarks for different sources."""
        timestamp = datetime(2023, 8, 15, 14, 30, 0)
        
        pubmed_wm = SyncWatermark(
            source="pubmed",
            query_key="immunotherapy",
            last_sync=timestamp
        )
        
        ct_wm = SyncWatermark(
            source="clinicaltrials",
            query_key="immunotherapy",
            last_sync=timestamp
        )
        
        assert pubmed_wm.source == "pubmed"
        assert ct_wm.source == "clinicaltrials"
        assert pubmed_wm.query_key == ct_wm.query_key == "immunotherapy"
    
    def test_table_name(self):
        """Test that table name is correctly set."""
        assert SyncWatermark.__tablename__ == 'sync_watermarks'
    
    def test_primary_key_autoincrement(self):
        """Test primary key configuration."""
        assert SyncWatermark.id.primary_key is True
        assert SyncWatermark.id.autoincrement is True
    
    def test_table_args_configuration(self):
        """Test table args configuration."""
        assert hasattr(SyncWatermark, '__table_args__')
        # __table_args__ is a tuple with dict as last element
        if isinstance(SyncWatermark.__table_args__, tuple):
            table_config = SyncWatermark.__table_args__[-1] if SyncWatermark.__table_args__ else {}
        else:
            table_config = SyncWatermark.__table_args__
        assert isinstance(table_config, dict)
        assert table_config.get('mysql_engine') == 'InnoDB'


class TestCorpusCheckpoint:
    """Test CorpusCheckpoint model."""
    
    def test_model_creation(self):
        """Test creating a CorpusCheckpoint instance."""
        checkpoint = CorpusCheckpoint(
            checkpoint_id="checkpoint_20230815_v1",
            name="Cancer Research Corpus - August 2023",
            description="Comprehensive cancer research corpus including latest trials",
            version="1.0",
            document_count="15000",
            total_documents="15000",
            total_vectors="15000"
        )
        
        assert checkpoint.checkpoint_id == "checkpoint_20230815_v1"
        assert checkpoint.name == "Cancer Research Corpus - August 2023"
        assert checkpoint.description == "Comprehensive cancer research corpus including latest trials"
        assert checkpoint.version == "1.0"
        assert checkpoint.document_count == "15000"
        assert checkpoint.total_documents == "15000"
        assert checkpoint.total_vectors == "15000"
        assert hasattr(checkpoint, 'created_at')
        assert hasattr(checkpoint, 'updated_at')
    
    def test_checkpoint_with_parent(self):
        """Test checkpoint with parent relationship."""
        checkpoint = CorpusCheckpoint(
            checkpoint_id="checkpoint_20230901_v2",
            name="Cancer Research Corpus - September 2023",
            version="2.0",
            parent_checkpoint_id="checkpoint_20230815_v1",
            document_count="18000",
            last_sync_edat="2023-09-01",
            primary_queries=["cancer", "immunotherapy", "clinical trial"],
            total_documents="18000",
            total_vectors="18000"
        )
        
        assert checkpoint.parent_checkpoint_id == "checkpoint_20230815_v1"
        assert checkpoint.last_sync_edat == "2023-09-01"
        assert checkpoint.primary_queries == ["cancer", "immunotherapy", "clinical trial"]
    
    def test_empty_optional_fields(self):
        """Test checkpoint with minimal required fields."""
        checkpoint = CorpusCheckpoint(
            checkpoint_id="minimal_checkpoint",
            name="Minimal Checkpoint"
        )
        
        assert checkpoint.checkpoint_id == "minimal_checkpoint"
        assert checkpoint.name == "Minimal Checkpoint"
        assert checkpoint.description is None
        assert checkpoint.version is None
        assert checkpoint.parent_checkpoint_id is None
        assert checkpoint.document_count is None
        assert checkpoint.last_sync_edat is None
        assert checkpoint.primary_queries is None
        assert checkpoint.total_documents is None
        assert checkpoint.total_vectors is None
    
    def test_complex_queries_json(self):
        """Test checkpoint with complex primary queries."""
        complex_queries = [
            "cancer AND biomarkers",
            "immunotherapy OR checkpoint inhibitors", 
            "clinical trial AND phase 2",
            "precision medicine"
        ]
        
        checkpoint = CorpusCheckpoint(
            checkpoint_id="complex_queries_checkpoint",
            name="Complex Queries Checkpoint",
            primary_queries=complex_queries,
            document_count="25000"
        )
        
        assert checkpoint.primary_queries == complex_queries
        assert len(checkpoint.primary_queries) == 4
        assert "cancer AND biomarkers" in checkpoint.primary_queries
    
    def test_table_name(self):
        """Test that table name is correctly set."""
        assert CorpusCheckpoint.__tablename__ == 'corpus_checkpoints'
    
    def test_primary_key(self):
        """Test primary key configuration."""
        assert CorpusCheckpoint.checkpoint_id.primary_key is True
        assert CorpusCheckpoint.checkpoint_id.type.length == 255


class TestDatabaseIntegration:
    """Test model integration with PostgreSQL via testcontainers."""
    
    @pytest.mark.asyncio
    async def test_postgresql_database_creation(self):
        """Test creating models in PostgreSQL database."""
        from testcontainers.postgres import PostgresContainer
        import asyncpg
        from sqlalchemy.ext.asyncio import create_async_engine
        
        # Use testcontainer PostgreSQL instead of SQLite
        with PostgresContainer("postgres:13") as postgres:
            # Convert psycopg2 URL to asyncpg URL
            database_url = postgres.get_connection_url()
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
            database_url = database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
            engine = create_async_engine(database_url)
            
            # Create all tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            # Verify tables were created by checking metadata
            assert 'documents_universal' in Base.metadata.tables
            assert 'sync_watermarks' in Base.metadata.tables
            assert 'corpus_checkpoints' in Base.metadata.tables
            assert 'jobs' in Base.metadata.tables
            
            await engine.dispose()
    
    @pytest.mark.asyncio
    async def test_model_relationships(self):
        """Test that models can coexist in PostgreSQL database."""
        from testcontainers.postgres import PostgresContainer
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        
        # Use testcontainer PostgreSQL
        with PostgresContainer("postgres:13") as postgres:
            # Convert psycopg2 URL to asyncpg URL
            database_url = postgres.get_connection_url()
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
            database_url = database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
            engine = create_async_engine(database_url)
            
            # Create all tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            # Create async session
            session_factory = sessionmaker(bind=engine, class_=AsyncSession)
            session = session_factory()
            
            try:
                # Create instances of each model
                doc = UniversalDocument(
                    id="test:123",
                    source="test",
                    source_id="123",
                    title="Test Document"
                )
                
                watermark = SyncWatermark(
                    source="test",
                    query_key="test_query",
                    last_sync=datetime.now()
                )
                
                checkpoint = CorpusCheckpoint(
                    checkpoint_id="test_checkpoint",
                    name="Test Checkpoint"
                )
                
                # Add to session and commit
                session.add(doc)
                session.add(watermark)
                session.add(checkpoint)
                await session.commit()
                
                # Verify they were saved using async queries
                from sqlalchemy import select, func
                
                doc_count = await session.scalar(select(func.count(UniversalDocument.id)))
                watermark_count = await session.scalar(select(func.count(SyncWatermark.id)))
                checkpoint_count = await session.scalar(select(func.count(CorpusCheckpoint.checkpoint_id)))
                
                assert doc_count == 1
                assert watermark_count == 1
                assert checkpoint_count == 1
                
                # Verify data integrity
                saved_doc = await session.scalar(select(UniversalDocument))
                assert saved_doc.id == "test:123"
                assert saved_doc.source == "test"
                
                saved_watermark = await session.scalar(select(SyncWatermark))
                assert saved_watermark.source == "test"
                assert saved_watermark.query_key == "test_query"
                
                saved_checkpoint = await session.scalar(select(CorpusCheckpoint))
                assert saved_checkpoint.checkpoint_id == "test_checkpoint"
                assert saved_checkpoint.name == "Test Checkpoint"
                
            finally:
                await session.close()
                await engine.dispose()


# Mark as unit tests
pytestmark = pytest.mark.unit