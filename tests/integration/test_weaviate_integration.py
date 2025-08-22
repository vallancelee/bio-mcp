"""
Integration tests for Weaviate client with real Weaviate instance.

Tests the WeaviateClient against a real Weaviate vector database instance using
testcontainers to validate end-to-end functionality including:
- Schema creation and management
- Document storage with vector embeddings
- Vector similarity search (semantic)
- BM25 keyword search
- Hybrid search combining vectors and keywords
- Document retrieval and filtering
"""

import asyncio
from typing import Any

import pytest
import pytest_asyncio
from testcontainers.compose import DockerCompose

from bio_mcp.shared.clients.weaviate_client import WeaviateClient


class WeaviateTestHelpers:
    """Helper utilities for Weaviate integration testing."""

    @classmethod
    def generate_test_documents(cls) -> list[dict[str, Any]]:
        """Generate realistic biomedical test documents for Weaviate."""
        return [
            {
                "pmid": "12345001",
                "title": "CRISPR-Cas9 Gene Editing in Cancer Immunotherapy",
                "abstract": "This study demonstrates the application of CRISPR-Cas9 gene editing technology to enhance T-cell responses against cancer cells. We modified T-cells to express chimeric antigen receptors targeting tumor-specific antigens.",
                "authors": ["Smith JA", "Johnson KL", "Williams MR"],
                "journal": "Nature Biotechnology",
                "publication_date": "2023-06-15",
                "doi": "10.1038/nbt.2023.001",
                "keywords": [
                    "CRISPR",
                    "gene editing",
                    "immunotherapy",
                    "cancer",
                    "CAR-T",
                ],
            },
            {
                "pmid": "12345002",
                "title": "Machine Learning Applications in Drug Discovery",
                "abstract": "We present a comprehensive machine learning framework for identifying potential drug compounds using molecular fingerprints and neural networks. The approach significantly reduces the time required for lead compound identification.",
                "authors": ["Chen LM", "Rodriguez AP", "Park SH"],
                "journal": "Science Translational Medicine",
                "publication_date": "2023-05-20",
                "doi": "10.1126/scitranslmed.2023.002",
                "keywords": [
                    "machine learning",
                    "drug discovery",
                    "neural networks",
                    "pharmaceutical",
                ],
            },
            {
                "pmid": "12345003",
                "title": "Alzheimer's Disease Biomarkers in Cerebrospinal Fluid",
                "abstract": "Analysis of tau protein and amyloid-beta concentrations in cerebrospinal fluid provides early diagnostic markers for Alzheimer's disease progression. We analyzed samples from 500 patients over 5 years.",
                "authors": ["Brown DK", "Taylor RE", "Anderson MJ"],
                "journal": "The Lancet Neurology",
                "publication_date": "2023-04-10",
                "doi": "10.1016/S1474-4422(23)001",
                "keywords": [
                    "Alzheimer",
                    "biomarkers",
                    "tau protein",
                    "amyloid",
                    "cerebrospinal fluid",
                ],
            },
            {
                "pmid": "12345004",
                "title": "COVID-19 Vaccine Effectiveness Against Omicron Variants",
                "abstract": "Real-world effectiveness study of mRNA vaccines against Omicron BA.4 and BA.5 variants. Analysis of hospitalization rates and breakthrough infections in vaccinated populations across multiple healthcare systems.",
                "authors": ["Garcia MR", "Kim SY", "Thompson AW"],
                "journal": "New England Journal of Medicine",
                "publication_date": "2023-03-25",
                "doi": "10.1056/NEJMoa2301234",
                "keywords": ["COVID-19", "vaccine", "Omicron", "effectiveness", "mRNA"],
            },
            {
                "pmid": "12345005",
                "title": "Precision Medicine in Cardiovascular Disease Treatment",
                "abstract": "Genomic profiling enables personalized treatment approaches for cardiovascular disease. We demonstrate improved outcomes using genetic risk scores to guide therapy selection in coronary artery disease patients.",
                "authors": ["Liu XH", "Jones PM", "Davis CR"],
                "journal": "Circulation",
                "publication_date": "2023-02-14",
                "doi": "10.1161/CIRCULATIONAHA.123.001",
                "keywords": [
                    "precision medicine",
                    "cardiovascular",
                    "genomics",
                    "personalized therapy",
                ],
            },
        ]

    @classmethod
    def validate_search_result(cls, result: dict[str, Any]) -> None:
        """Validate the structure of a search result."""
        assert "uuid" in result
        assert "pmid" in result
        assert "title" in result
        assert isinstance(result["title"], str)
        assert len(result["title"]) > 0

        # Score or distance should be present
        assert "score" in result or "distance" in result

        # Basic document properties
        assert "abstract" in result
        assert "authors" in result
        assert isinstance(result["authors"], list)


@pytest.fixture(scope="session")
def weaviate_container():
    """Provide a Weaviate testcontainer instance with transformers support."""
    from pathlib import Path

    # Get the path to the compose file (use the MCP integration tests version)
    compose_file = Path(__file__).parent / "mcp" / "docker-compose-weaviate.yml"

    # Use Docker Compose to start Weaviate with transformers
    with DockerCompose(
        str(compose_file.parent), compose_file_name="docker-compose-weaviate.yml"
    ) as compose:
        # Wait for services to be ready
        weaviate_url = compose.get_service_host("weaviate", 8080)  # Use internal port
        weaviate_port = compose.get_service_port("weaviate", 8080)  # Gets external port
        grpc_port = compose.get_service_port("weaviate", 50051)  # Get gRPC port

        url = f"http://{weaviate_url}:{weaviate_port}"

        print(
            f"✓ Weaviate with transformers started at {url} (gRPC: {weaviate_url}:{grpc_port})"
        )

        # Wait a bit for transformers service to be ready
        import time

        time.sleep(10)

        # Return connection info
        yield {
            "http_url": url,
            "grpc_host": weaviate_url,
            "grpc_port": grpc_port,
            "secure": False,
        }


@pytest_asyncio.fixture(scope="function")
async def weaviate_client(weaviate_container):
    """Create a fresh Weaviate client for each test function."""
    container_info = weaviate_container
    url = container_info["http_url"]
    client = WeaviateClient(url=url)

    # Pass gRPC info to client for dynamic connection
    client._grpc_host = container_info["grpc_host"]
    client._grpc_port = container_info["grpc_port"]

    # Initialize and clean up any existing data
    await client.initialize()

    # Clean up collection if it exists (for fresh state)
    if client.client and client.client.collections.exists(client.collection_name):
        try:
            collection = client.client.collections.get(client.collection_name)
            collection.data.delete_many()  # Clear all data
        except Exception:
            pass  # Ignore cleanup errors

    yield client

    # Clean up after test
    try:
        if client.client and client.client.collections.exists(client.collection_name):
            collection = client.client.collections.get(client.collection_name)
            collection.data.delete_many()
        await client.close()
    except Exception:
        pass  # Ignore cleanup errors


class TestWeaviateClientInitialization:
    """Test Weaviate client initialization and schema management."""

    @pytest.mark.asyncio
    async def test_client_initialization(self, weaviate_client):
        """Test basic client initialization."""
        client = weaviate_client

        # Should be initialized from fixture
        assert client._initialized is True
        assert client.client is not None

        # Collection should exist
        assert client.client.collections.exists(client.collection_name)

        print(
            f"✓ Weaviate client initialized with collection: {client.collection_name}"
        )

    @pytest.mark.asyncio
    async def test_health_check(self, weaviate_client):
        """Test health check functionality."""
        client = weaviate_client

        health = await client.health_check()

        assert health["status"] == "healthy"
        assert health["ready"] is True
        assert health["collection_exists"] is True
        assert "url" in health

        print(f"✓ Health check passed: {health}")

    @pytest.mark.asyncio
    async def test_multiple_initialization_calls(self, weaviate_client):
        """Test that multiple initialization calls are safe."""
        client = weaviate_client

        # Should not raise errors
        await client.initialize()
        await client.initialize()

        # Should still be functional
        health = await client.health_check()
        assert health["status"] == "healthy"

        print("✓ Multiple initialization calls handled safely")


class TestWeaviateClientDocumentOperations:
    """Test document storage and retrieval operations."""

    @pytest.mark.asyncio
    async def test_store_and_retrieve_document(self, weaviate_client):
        """Test storing and retrieving a single document."""
        client = weaviate_client
        test_docs = WeaviateTestHelpers.generate_test_documents()
        doc = test_docs[0]

        # Store document
        uuid = await client.store_document(**doc)

        assert uuid is not None
        assert len(uuid) > 0

        print(f"✓ Document stored with UUID: {uuid}")

        # Retrieve by PMID
        retrieved = await client.get_document_by_pmid(doc["pmid"])

        assert retrieved is not None
        assert retrieved["pmid"] == doc["pmid"]
        assert retrieved["title"] == doc["title"]
        assert retrieved["abstract"] == doc["abstract"]
        assert retrieved["authors"] == doc["authors"]
        assert retrieved["journal"] == doc["journal"]
        assert retrieved["doi"] == doc["doi"]
        assert retrieved["keywords"] == doc["keywords"]

        print(f"✓ Document retrieved: {retrieved['title'][:50]}...")

    @pytest.mark.asyncio
    async def test_document_exists_check(self, weaviate_client):
        """Test document existence checking."""
        client = weaviate_client

        # Use a truly unique document to avoid clashes with other tests
        import uuid

        unique_pmid = f"99{uuid.uuid4().hex[:6]}"  # Generate truly unique PMID
        unique_doc = {
            "pmid": unique_pmid,  # Unique PMID that won't clash with test data
            "title": "Unique Test Document for Existence Check",
            "abstract": "This is a unique test document specifically for testing document existence functionality.",
            "authors": ["TestAuthor A", "TestAuthor B"],
            "journal": "Test Journal of Integration Testing",
            "publication_date": "2023-08-21",
            "doi": "10.9999/test.existence.001",
            "keywords": ["test", "existence", "unique"],
        }
        doc = unique_doc

        # Should not exist initially
        exists_before = await client.document_exists(doc["pmid"])
        assert exists_before is False

        # Store document
        await client.store_document(**doc)

        # Should exist now
        exists_after = await client.document_exists(doc["pmid"])
        assert exists_after is True

        # Non-existent document should not exist
        exists_fake = await client.document_exists("99999999")
        assert exists_fake is False

        print("✓ Document existence checking working correctly")

    @pytest.mark.asyncio
    async def test_store_multiple_documents(self, weaviate_client):
        """Test storing multiple documents."""
        client = weaviate_client
        test_docs = WeaviateTestHelpers.generate_test_documents()

        stored_uuids = []

        # Store all test documents
        for doc in test_docs:
            uuid = await client.store_document(**doc)
            stored_uuids.append(uuid)

            # Small delay to avoid overwhelming the system
            await asyncio.sleep(0.1)

        assert len(stored_uuids) == len(test_docs)
        assert all(uuid for uuid in stored_uuids)

        print(f"✓ Stored {len(test_docs)} documents successfully")

        # Verify all documents can be retrieved
        for doc in test_docs:
            retrieved = await client.get_document_by_pmid(doc["pmid"])
            assert retrieved is not None
            assert retrieved["pmid"] == doc["pmid"]

        print("✓ All documents verified retrievable")


class TestWeaviateClientSearch:
    """Test different search modes and functionality."""

    @pytest.mark.asyncio
    async def test_bm25_keyword_search(self, weaviate_client):
        """Test BM25 keyword search."""
        client = weaviate_client
        test_docs = WeaviateTestHelpers.generate_test_documents()

        # Store test documents
        for doc in test_docs:
            await client.store_document(**doc)
            await asyncio.sleep(0.1)

        await asyncio.sleep(1.0)  # Wait for indexing

        # Test BM25 search for specific keywords
        results = await client.search_documents(
            query="machine learning drug discovery", limit=3, search_mode="bm25"
        )

        assert len(results) > 0
        assert len(results) <= 3

        # Validate result structure
        for result in results:
            WeaviateTestHelpers.validate_search_result(result)

        # The machine learning document should be found
        ml_found = any("Machine Learning" in result["title"] for result in results)
        assert ml_found, "Machine learning document should be found in BM25 search"

        print(f"✓ BM25 search returned {len(results)} results")
        print(f"✓ Top result: {results[0]['title'][:50]}...")

    @pytest.mark.asyncio
    async def test_semantic_search(self, weaviate_client):
        """Test semantic vector search."""
        client = weaviate_client
        test_docs = WeaviateTestHelpers.generate_test_documents()

        # Store test documents first
        for doc in test_docs:
            await client.store_document(**doc)
            await asyncio.sleep(0.1)  # Small delay for indexing

        # Wait for indexing to complete
        await asyncio.sleep(2.0)

        # Test semantic search for gene editing concepts
        results = await client.search_documents(
            query="gene editing CRISPR cancer treatment",
            limit=3,
            search_mode="semantic",
        )

        assert len(results) > 0
        assert len(results) <= 3

        # Validate result structure
        for result in results:
            WeaviateTestHelpers.validate_search_result(result)

        # The CRISPR document should be highly relevant
        crispr_found = any("CRISPR" in result["title"] for result in results)
        assert crispr_found, "CRISPR document should be found in semantic search"

        print(f"✓ Semantic search returned {len(results)} results")
        print(f"✓ Top result: {results[0]['title'][:50]}...")

    @pytest.mark.asyncio
    async def test_search_with_filters(self, weaviate_client):
        """Test search with metadata filters."""
        client = weaviate_client
        test_docs = WeaviateTestHelpers.generate_test_documents()

        # Store test documents
        for doc in test_docs:
            await client.store_document(**doc)
            await asyncio.sleep(0.1)

        await asyncio.sleep(1.0)  # Wait for indexing

        # Test search with date filter
        results = await client.search_documents(
            query="cancer research",
            limit=5,
            search_mode="bm25",
            filters={
                "date_from": "2023-05-01",  # Should find recent documents
                "date_to": "2023-12-31",
            },
        )

        assert len(results) > 0

        # Validate that results match filter criteria
        for result in results:
            WeaviateTestHelpers.validate_search_result(result)
            if result.get("publication_date"):
                # Handle both datetime objects and string formats
                pub_date = result["publication_date"]
                if isinstance(pub_date, str):
                    # String format: YYYY-MM-DDTHH:MM:SSZ
                    pub_date_str = pub_date.split("T")[0]
                else:
                    # Datetime object
                    pub_date_str = pub_date.strftime("%Y-%m-%d")

                assert pub_date_str >= "2023-05-01"
                assert pub_date_str <= "2023-12-31"

        print(f"✓ Filtered search returned {len(results)} results")
        print("✓ Date filter working correctly")

    @pytest.mark.asyncio
    async def test_search_no_results(self, weaviate_client):
        """Test search with query that returns no results."""
        client = weaviate_client

        # Search without storing any documents
        results = await client.search_documents(
            query="nonexistent biomedical topic zzxxyy", limit=5, search_mode="bm25"
        )

        assert results == []

        print("✓ No results query handled correctly")


class TestWeaviateClientErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_operations_before_initialization(self, weaviate_container):
        """Test operations on uninitialized client."""
        container_info = weaviate_container
        url = container_info["http_url"]
        client = WeaviateClient(url=url)

        # Pass gRPC info to client for dynamic connection
        client._grpc_host = container_info["grpc_host"]
        client._grpc_port = container_info["grpc_port"]

        # Operations should auto-initialize
        test_docs = WeaviateTestHelpers.generate_test_documents()
        doc = test_docs[0]

        # This should work (auto-initialization)
        uuid = await client.store_document(**doc)
        assert uuid is not None
        assert client._initialized is True

        await client.close()

        print("✓ Auto-initialization working correctly")

    @pytest.mark.asyncio
    async def test_client_close_and_reuse(self, weaviate_container):
        """Test client behavior after closing."""
        container_info = weaviate_container
        url = container_info["http_url"]
        client = WeaviateClient(url=url)

        # Pass gRPC info to client for dynamic connection
        client._grpc_host = container_info["grpc_host"]
        client._grpc_port = container_info["grpc_port"]

        await client.initialize()
        assert client._initialized is True

        # Close client
        await client.close()
        assert client._initialized is False
        assert client.client is None

        # Should be able to reinitialize and use again
        await client.initialize()
        assert client._initialized is True

        health = await client.health_check()
        assert health["status"] == "healthy"

        await client.close()

        print("✓ Client close and reuse working correctly")


# Mark all tests as integration tests
pytestmark = pytest.mark.integration
