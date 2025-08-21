"""
Integration tests for Bio-MCP services with real testcontainers.

Tests the complete service orchestration including:
- SyncOrchestrator end-to-end workflows
- PubMed API integration (mocked)
- Database operations with PostgreSQL
- Vector operations with Weaviate
- Error handling and partial failures
"""

from datetime import UTC, datetime
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from testcontainers.compose import DockerCompose
from testcontainers.postgres import PostgresContainer

from bio_mcp.services.services import (
    DocumentService,
    PubMedService,
    SyncOrchestrator,
    VectorService,
)
from bio_mcp.shared.clients.database import DatabaseConfig, init_database
from bio_mcp.shared.clients.weaviate_client import WeaviateClient
from bio_mcp.sources.pubmed.client import PubMedDocument, PubMedSearchResult


class MockPubMedData:
    """Generator for realistic mock PubMed API responses."""
    
    SAMPLE_DOCUMENTS: ClassVar[list[dict[str, Any]]] = [
        {
            "pmid": "37123456",
            "title": "CRISPR-Cas9 Gene Editing in Cancer Immunotherapy: A Comprehensive Review",
            "abstract": "This comprehensive review examines the application of CRISPR-Cas9 gene editing technology in cancer immunotherapy. We discuss recent advances in T-cell engineering, CAR-T cell therapy, and immune checkpoint modulation using CRISPR tools.",
            "authors": ["Smith JA", "Johnson KL", "Williams MR", "Brown DK"],
            "journal": "Nature Biotechnology",
            "publication_date": "2023-08-15",
            "doi": "10.1038/nbt.2023.12345",
            "keywords": ["CRISPR", "gene editing", "cancer", "immunotherapy", "CAR-T"],
            "mesh_terms": ["Neoplasms", "Immunotherapy", "Gene Editing", "CRISPR-Cas Systems"]
        },
        {
            "pmid": "37123457", 
            "title": "Machine Learning Applications in Drug Discovery and Development",
            "abstract": "We present a comprehensive framework for applying machine learning to drug discovery, including molecular property prediction, compound screening, and clinical trial optimization.",
            "authors": ["Chen LM", "Rodriguez AP", "Park SH"],
            "journal": "Science Translational Medicine",
            "publication_date": "2023-07-22",
            "doi": "10.1126/scitranslmed.2023.67890",
            "keywords": ["machine learning", "drug discovery", "pharmaceutical", "AI"],
            "mesh_terms": ["Drug Discovery", "Machine Learning", "Pharmaceutical Preparations"]
        },
        {
            "pmid": "37123458",
            "title": "Alzheimer's Disease Biomarkers: Early Detection and Therapeutic Targets",
            "abstract": "Analysis of tau protein, amyloid-beta, and neuroinflammatory markers provides insights into Alzheimer's disease progression and potential therapeutic interventions.",
            "authors": ["Taylor RE", "Anderson MJ", "Wilson CK"],
            "journal": "The Lancet Neurology",
            "publication_date": "2023-06-10",
            "doi": "10.1016/S1474-4422(23)00234-5",
            "keywords": ["Alzheimer", "biomarkers", "tau protein", "amyloid"],
            "mesh_terms": ["Alzheimer Disease", "Biomarkers", "Tau Proteins", "Amyloid beta-Peptides"]
        },
        {
            "pmid": "37123459",
            "title": "Novel Cancer Therapeutics: Targeting Metastatic Pathways",
            "abstract": "This study investigates novel therapeutic approaches for treating metastatic cancer, focusing on pathway inhibition and combination therapies to improve patient outcomes.",
            "authors": ["Garcia MR", "Kim SY", "Thompson AW"],
            "journal": "Cancer Research",
            "publication_date": "2023-05-18",
            "doi": "10.1158/0008-5472.CAN-23-1234",
            "keywords": ["cancer", "metastasis", "therapeutics", "pathway inhibition"],
            "mesh_terms": ["Neoplasms", "Neoplasm Metastasis", "Therapeutics", "Signal Transduction"]
        },
        {
            "pmid": "37123460",
            "title": "Precision Medicine in Cancer Treatment: Genomic Biomarkers and Personalized Therapy",
            "abstract": "We review the current state of precision medicine in cancer treatment, highlighting the role of genomic biomarkers in guiding personalized therapeutic strategies.",
            "authors": ["Liu XH", "Jones PM", "Davis CR"],
            "journal": "Nature Medicine",
            "publication_date": "2023-04-25",
            "doi": "10.1038/s41591-023-2345-6",
            "keywords": ["precision medicine", "cancer", "genomics", "biomarkers", "personalized therapy"],
            "mesh_terms": ["Precision Medicine", "Neoplasms", "Genomics", "Biomarkers"]
        },
        {
            "pmid": "37123461",
            "title": "COVID-19 Drug Repurposing: Machine Learning Approaches for Rapid Discovery",
            "abstract": "This research applies machine learning algorithms to identify existing drugs that can be repurposed for COVID-19 treatment, accelerating the discovery process.",
            "authors": ["Brown DK", "Lee SJ", "Wang YL"],
            "journal": "Nature Communications",
            "publication_date": "2023-03-12",
            "doi": "10.1038/s41467-023-3456-7",
            "keywords": ["COVID-19", "drug repurposing", "machine learning", "drug discovery"],
            "mesh_terms": ["COVID-19", "Drug Repositioning", "Machine Learning", "Drug Discovery"]
        }
    ]
    
    @classmethod
    def create_search_result(cls, query: str, limit: int = 10) -> PubMedSearchResult:
        """Create a mock PubMed search result."""
        # Select documents based on query (simple keyword matching)
        query_lower = query.lower()
        matching_docs = []
        
        for doc in cls.SAMPLE_DOCUMENTS:
            # Check if any query words match title, abstract, or keywords
            doc_text = f"{doc['title'].lower()} {doc['abstract'].lower()} {' '.join(doc['keywords']).lower()}"
            query_words = query_lower.split()
            
            if any(word in doc_text for word in query_words):
                matching_docs.append(doc)
        
        # Limit results
        selected_docs = matching_docs[:limit]
        pmids = [doc["pmid"] for doc in selected_docs]
        
        return PubMedSearchResult(
            query=query,
            total_count=len(matching_docs),
            pmids=pmids,
            retstart=0,
            retmax=limit
        )
    
    @classmethod
    def create_documents(cls, pmids: list[str]) -> list[PubMedDocument]:
        """Create mock PubMed documents for given PMIDs."""
        documents = []
        
        for pmid in pmids:
            # Find matching document data
            doc_data = next((doc for doc in cls.SAMPLE_DOCUMENTS if doc["pmid"] == pmid), None)
            
            if doc_data:
                documents.append(PubMedDocument(
                    pmid=doc_data["pmid"],
                    title=doc_data["title"],
                    abstract=doc_data["abstract"],
                    authors=doc_data["authors"],
                    journal=doc_data["journal"],
                    publication_date=datetime.fromisoformat(doc_data["publication_date"]).date(),
                    doi=doc_data["doi"],
                    keywords=doc_data["keywords"],
                    mesh_terms=doc_data["mesh_terms"]
                ))
        
        return documents


# Shared fixtures for database and Weaviate containers
@pytest.fixture(scope="session")
def postgres_container():
    """Provide a PostgreSQL testcontainer for the test session."""
    container = PostgresContainer("postgres:15")
    container.with_env("POSTGRES_DB", "bio_mcp_test")
    container.with_env("POSTGRES_USER", "test_user")
    container.with_env("POSTGRES_PASSWORD", "test_password")
    container.start()
    
    yield container
    
    container.stop()


@pytest.fixture(scope="session")
def weaviate_container():
    """Provide a Weaviate testcontainer with transformers support."""
    from pathlib import Path
    
    # Get the path to the compose file
    compose_file = Path(__file__).parent / "docker-compose-weaviate.yml"
    
    # Use Docker Compose to start Weaviate with transformers
    with DockerCompose(str(compose_file.parent), compose_file_name="docker-compose-weaviate.yml") as compose:
        # Wait for services to be ready
        weaviate_url = compose.get_service_host("weaviate", 8080)
        weaviate_port = compose.get_service_port("weaviate", 8080)
        grpc_port = compose.get_service_port("weaviate", 50051)
        
        url = f"http://{weaviate_url}:{weaviate_port}"
        
        print(f"✓ Weaviate with transformers started at {url}")
        
        # Wait for transformers service to be ready
        import time
        time.sleep(10)
        
        yield {"http_url": url, "grpc_host": weaviate_url, "grpc_port": grpc_port}


@pytest_asyncio.fixture(scope="function")
async def database_manager(postgres_container):
    """Create database manager for each test function."""
    from sqlalchemy import text
    
    connection_url = postgres_container.get_connection_url()
    async_url = connection_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    
    config = DatabaseConfig(url=async_url, echo=False, pool_size=2, max_overflow=1)
    manager = await init_database(config)
    
    # Clean up any existing data
    async with manager.get_session() as session:
        try:
            await session.execute(text("TRUNCATE TABLE corpus_checkpoints, sync_watermarks, pubmed_documents CASCADE"))
            await session.commit()
        except Exception:
            await session.rollback()
    
    yield manager
    
    # Clean up after test
    async with manager.get_session() as session:
        try:
            await session.execute(text("TRUNCATE TABLE corpus_checkpoints, sync_watermarks, pubmed_documents CASCADE"))
            await session.commit()
        except Exception:
            await session.rollback()
    
    await manager.close()


@pytest_asyncio.fixture(scope="function")
async def weaviate_client(weaviate_container):
    """Create a fresh Weaviate client for each test function."""
    container_info = weaviate_container
    url = container_info["http_url"]
    client = WeaviateClient(url=url)
    
    # Pass gRPC info to client for dynamic connection
    client._grpc_host = container_info["grpc_host"]
    client._grpc_port = container_info["grpc_port"]
    
    await client.initialize()
    
    # Clean up collection if it exists
    if client.client and client.client.collections.exists(client.collection_name):
        try:
            collection = client.client.collections.get(client.collection_name)
            collection.data.delete_many()
        except Exception:
            pass
    
    yield client
    
    # Clean up after test
    try:
        if client.client and client.client.collections.exists(client.collection_name):
            collection = client.client.collections.get(client.collection_name)
            collection.data.delete_many()
        await client.close()
    except Exception:
        pass


class TestSyncOrchestrator:
    """Test SyncOrchestrator end-to-end workflows."""
    
    @pytest.mark.asyncio
    async def test_sync_documents_basic_workflow(self, database_manager, weaviate_client):
        """Test basic document sync workflow from PubMed to database and vector store."""
        # Create services with real containers
        document_service = DocumentService()
        document_service.manager = database_manager
        document_service._initialized = True
        
        vector_service = VectorService()
        vector_service.client = weaviate_client
        vector_service._initialized = True
        
        # Mock PubMed service
        pubmed_service = MagicMock(spec=PubMedService)
        pubmed_service._initialized = True
        
        # Configure mock responses - use broader query to get multiple matches
        search_result = MockPubMedData.create_search_result("cancer", limit=2)
        documents = MockPubMedData.create_documents(search_result.pmids)
        
        pubmed_service.search = AsyncMock(return_value=search_result)
        pubmed_service.fetch_documents = AsyncMock(return_value=documents)
        
        # Create orchestrator with real and mock services
        orchestrator = SyncOrchestrator(
            pubmed_service=pubmed_service,
            document_service=document_service,
            vector_service=vector_service
        )
        orchestrator._initialized = True
        
        # Execute sync
        result = await orchestrator.sync_documents("cancer", limit=2)
        
        # Verify result structure
        assert isinstance(result, dict)
        assert "total_requested" in result
        assert "successfully_synced" in result
        assert "already_existed" in result
        assert "failed" in result
        assert "pmids_synced" in result
        assert "pmids_failed" in result
        
        # Verify sync worked
        assert result["total_requested"] == 2
        assert result["successfully_synced"] == 2
        assert result["already_existed"] == 0
        assert result["failed"] == 0
        assert len(result["pmids_synced"]) == 2
        assert len(result["pmids_failed"]) == 0
        
        # Verify documents exist in database
        for pmid in search_result.pmids:
            exists = await document_service.document_exists(pmid)
            assert exists is True
            
            doc = await document_service.get_document_by_pmid(pmid)
            assert doc is not None
            assert doc.pmid == pmid
        
        # Verify documents exist in vector store
        for pmid in search_result.pmids:
            exists = await vector_service.client.document_exists(pmid)
            assert exists is True
        
        print(f"✓ Successfully synced {result['successfully_synced']} documents")
    
    @pytest.mark.asyncio
    async def test_sync_documents_with_existing_documents(self, database_manager, weaviate_client):
        """Test sync workflow when some documents already exist."""
        # Pre-populate database with one document
        doc_data = MockPubMedData.SAMPLE_DOCUMENTS[0]
        existing_doc = {
            "pmid": doc_data["pmid"],
            "title": doc_data["title"],
            "abstract": doc_data["abstract"],
            "authors": doc_data["authors"],
            "journal": doc_data["journal"],
            "publication_date": datetime.fromisoformat(doc_data["publication_date"]).replace(tzinfo=UTC),
            "doi": doc_data["doi"],
            "keywords": doc_data["keywords"]
        }
        await database_manager.create_document(existing_doc)
        
        # Create services
        document_service = DocumentService()
        document_service.manager = database_manager
        document_service._initialized = True
        
        vector_service = VectorService()
        vector_service.client = weaviate_client
        vector_service._initialized = True
        
        # Mock PubMed service with 2 documents (1 existing, 1 new)
        pubmed_service = MagicMock(spec=PubMedService)
        pubmed_service._initialized = True
        
        search_result = MockPubMedData.create_search_result("cancer", limit=2)
        documents = MockPubMedData.create_documents(search_result.pmids)
        
        pubmed_service.search = AsyncMock(return_value=search_result)
        pubmed_service.fetch_documents = AsyncMock(return_value=documents)
        
        # Create orchestrator
        orchestrator = SyncOrchestrator(
            pubmed_service=pubmed_service,
            document_service=document_service,
            vector_service=vector_service
        )
        orchestrator._initialized = True
        
        # Execute sync
        result = await orchestrator.sync_documents("cancer", limit=2)
        
        # Verify behavior with existing documents
        assert result["total_requested"] == 2
        assert result["already_existed"] >= 1  # At least one should exist
        assert result["successfully_synced"] >= 1  # At least one should be new
        assert result["failed"] == 0
        
        print(f"✓ Handled existing documents: {result['already_existed']} existing, {result['successfully_synced']} new")
    
    @pytest.mark.asyncio
    async def test_sync_documents_error_handling(self, database_manager, weaviate_client):
        """Test sync workflow error handling when services fail."""
        # Create services
        document_service = DocumentService()
        document_service.manager = database_manager
        document_service._initialized = True
        
        vector_service = VectorService()
        vector_service.client = weaviate_client
        vector_service._initialized = True
        
        # Mock PubMed service that fails during fetch
        pubmed_service = MagicMock(spec=PubMedService)
        pubmed_service._initialized = True
        
        search_result = MockPubMedData.create_search_result("machine learning", limit=1)
        
        pubmed_service.search = AsyncMock(return_value=search_result)
        pubmed_service.fetch_documents = AsyncMock(side_effect=Exception("PubMed API error"))
        
        # Create orchestrator
        orchestrator = SyncOrchestrator(
            pubmed_service=pubmed_service,
            document_service=document_service,
            vector_service=vector_service
        )
        orchestrator._initialized = True
        
        # Execute sync (should handle errors gracefully)
        result = await orchestrator.sync_documents("machine learning", limit=1)
        
        # Verify error handling
        assert result["total_requested"] == 1
        assert result["successfully_synced"] == 0
        assert result["failed"] == 1
        assert len(result["pmids_failed"]) == 1
        
        print("✓ Error handling working correctly")
    
    @pytest.mark.asyncio
    async def test_sync_documents_no_results(self, database_manager, weaviate_client):
        """Test sync workflow when PubMed search returns no results."""
        # Create services
        document_service = DocumentService()
        document_service.manager = database_manager
        document_service._initialized = True
        
        vector_service = VectorService()
        vector_service.client = weaviate_client
        vector_service._initialized = True
        
        # Mock PubMed service with no results
        pubmed_service = MagicMock(spec=PubMedService)
        pubmed_service._initialized = True
        
        empty_result = PubMedSearchResult(
            query="nonexistent topic zzxxyy",
            total_count=0,
            pmids=[],
            retstart=0,
            retmax=10
        )
        
        pubmed_service.search = AsyncMock(return_value=empty_result)
        
        # Create orchestrator
        orchestrator = SyncOrchestrator(
            pubmed_service=pubmed_service,
            document_service=document_service,
            vector_service=vector_service
        )
        orchestrator._initialized = True
        
        # Execute sync
        result = await orchestrator.sync_documents("nonexistent topic", limit=10)
        
        # Verify empty result handling
        assert result["total_requested"] == 0
        assert result["successfully_synced"] == 0
        assert result["already_existed"] == 0
        assert result["failed"] == 0
        assert result["pmids_synced"] == []
        assert result["pmids_failed"] == []
        
        print("✓ Empty result handling working correctly")


class TestIndividualServices:
    """Test individual service operations."""
    
    @pytest.mark.asyncio
    async def test_document_service_operations(self, database_manager):
        """Test DocumentService operations."""
        service = DocumentService()
        service.manager = database_manager
        service._initialized = True
        
        # Test document creation and retrieval
        doc_data = MockPubMedData.SAMPLE_DOCUMENTS[0]
        document_data = {
            "pmid": doc_data["pmid"],
            "title": doc_data["title"],
            "abstract": doc_data["abstract"],
            "authors": doc_data["authors"],
            "journal": doc_data["journal"],
            "publication_date": datetime.fromisoformat(doc_data["publication_date"]).replace(tzinfo=UTC),
            "doi": doc_data["doi"],
            "keywords": doc_data["keywords"]
        }
        
        # Create document
        await service.create_document(document_data)
        
        # Test existence check
        exists = await service.document_exists(doc_data["pmid"])
        assert exists is True
        
        # Test retrieval
        retrieved = await service.get_document_by_pmid(doc_data["pmid"])
        assert retrieved is not None
        assert retrieved.pmid == doc_data["pmid"]
        assert retrieved.title == doc_data["title"]
        
        print("✓ DocumentService operations working correctly")
    
    @pytest.mark.asyncio
    async def test_vector_service_operations(self, weaviate_client):
        """Test VectorService operations."""
        service = VectorService()
        service.client = weaviate_client
        service._initialized = True
        
        # Test document storage
        doc_data = MockPubMedData.SAMPLE_DOCUMENTS[0]
        
        uuid = await service.store_document(
            pmid=doc_data["pmid"],
            title=doc_data["title"],
            abstract=doc_data["abstract"],
            authors=doc_data["authors"],
            journal=doc_data["journal"],
            publication_date=doc_data["publication_date"],
            doi=doc_data["doi"],
            keywords=doc_data["keywords"]
        )
        
        assert uuid is not None
        assert len(uuid) > 0
        
        # Test document existence
        exists = await service.client.document_exists(doc_data["pmid"])
        assert exists is True
        
        print("✓ VectorService operations working correctly")


# Mark all tests as integration tests
pytestmark = pytest.mark.integration