"""
TestContainers configuration for MCP integration tests.

This provides fixtures for testing MCP tools with real PostgreSQL containers,
eliminating complex mocking and ensuring reliable integration testing.
"""

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from testcontainers.compose import DockerCompose

from bio_mcp.mcp.corpus_tools import CorpusCheckpointManager
from bio_mcp.mcp.rag_tools import RAGToolsManager
from bio_mcp.mcp.resources import BioMCPResourceManager
from bio_mcp.services.services import (
    CorpusCheckpointService,
    DocumentService,
    PubMedService,
)
from bio_mcp.shared.clients.database import DatabaseManager

# Import shared fixtures directly


@pytest.fixture(scope="session")
def weaviate_service():
    """Provide a Weaviate service with transformers using docker-compose."""
    from pathlib import Path

    # Get the directory of this conftest.py file
    current_dir = Path(__file__).parent
    compose_file = current_dir / "docker-compose-weaviate.yml"

    with DockerCompose(
        str(current_dir), compose_file_name="docker-compose-weaviate.yml"
    ) as compose:
        # Wait for services to be ready
        weaviate_url = compose.get_service_host("weaviate", 8080)
        weaviate_port = compose.get_service_port("weaviate", 8080)

        transformers_url = compose.get_service_host("t2v-transformers", 8080)
        transformers_port = compose.get_service_port("t2v-transformers", 8080)

        # Wait for both services to be ready
        import time

        import requests
        from requests.exceptions import RequestException

        weaviate_full_url = f"http://{weaviate_url}:{weaviate_port}"
        transformers_full_url = f"http://{transformers_url}:{transformers_port}"

        print(f"\nWaiting for Weaviate at {weaviate_full_url}")
        print(f"Waiting for Transformers at {transformers_full_url}")

        # Wait for transformers service first
        max_attempts = 120  # Wait up to 2 minutes (transformers take longer to load)
        for attempt in range(max_attempts):
            try:
                response = requests.get(
                    f"{transformers_full_url}/.well-known/ready", timeout=5
                )
                if response.status_code == 200:
                    print(f"Transformers ready at {transformers_full_url}")
                    break
            except RequestException:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Transformers service failed to start within 2 minutes")

        # Wait for Weaviate to be ready
        for attempt in range(60):  # Wait up to 60 seconds for Weaviate
            try:
                response = requests.get(
                    f"{weaviate_full_url}/v1/.well-known/ready", timeout=5
                )
                if response.status_code == 200:
                    print(f"Weaviate ready at {weaviate_full_url}")
                    break
            except RequestException:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Weaviate failed to start within 60 seconds")

        yield weaviate_full_url


@pytest_asyncio.fixture(scope="function")
async def checkpoint_service(
    clean_db: DatabaseManager,
) -> AsyncGenerator[CorpusCheckpointService, None]:
    """Provide a CorpusCheckpointService with real database."""
    service = CorpusCheckpointService()
    # Override the database manager with our test instance
    service._db_manager = clean_db
    service._initialized = True

    yield service

    await service.close()


@pytest_asyncio.fixture(scope="function")
async def document_service(
    clean_db: DatabaseManager,
) -> AsyncGenerator[DocumentService, None]:
    """Provide a DocumentService with real database."""
    service = DocumentService()
    # Override the database manager with our test instance
    service._db_manager = clean_db
    service._initialized = True

    yield service

    await service.close()


@pytest_asyncio.fixture(scope="function")
async def pubmed_service() -> AsyncGenerator[PubMedService, None]:
    """Provide a PubMedService for testing."""
    # Set test configuration to avoid real PubMed API calls
    os.environ["BIO_MCP_PUBMED_API_KEY"] = "test_key"

    service = PubMedService()
    service._initialized = True  # Skip real initialization

    yield service

    await service.close()


@pytest_asyncio.fixture(scope="function")
async def corpus_checkpoint_manager(
    checkpoint_service: CorpusCheckpointService,
) -> AsyncGenerator[CorpusCheckpointManager, None]:
    """Provide a CorpusCheckpointManager with real database."""
    manager = CorpusCheckpointManager()
    # Override the service with our test instance
    manager.checkpoint_service = checkpoint_service
    manager.initialized = True

    yield manager

    await manager.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_services_config(postgres_container, request):
    """Auto-setup all service configurations for MCP integration tests."""
    # Get the test database URL
    connection_url = postgres_container.get_connection_url()
    async_url = connection_url.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )

    # Check if test requires Weaviate
    needs_weaviate = not (
        hasattr(request, "node")
        and "no_weaviate" in [mark.name for mark in request.node.iter_markers()]
    )

    # Set all environment variables
    import os

    original_vars = {}
    test_vars = {
        "BIO_MCP_DATABASE_URL": async_url,
        "BIO_MCP_WEAVIATE_URL": "http://localhost:8080",  # Default URL for non-Weaviate tests
        "BIO_MCP_OPENAI_API_KEY": "test_key",  # Still using fake key for OpenAI
    }

    # Only start Weaviate if needed
    if needs_weaviate:
        try:
            weaviate_service = request.getfixturevalue("weaviate_service")
            test_vars["BIO_MCP_WEAVIATE_URL"] = weaviate_service
        except Exception:
            # If Weaviate can't start, use default URL and let tests handle gracefully
            pass

    # Store original values and set test values
    for key, value in test_vars.items():
        original_vars[key] = os.environ.get(key)
        os.environ[key] = value

    # Reset global instances to None so they get recreated with test config
    from bio_mcp.mcp import corpus_tools, rag_tools, resources
    from bio_mcp.shared.clients import database

    corpus_tools._checkpoint_manager = None
    rag_tools._rag_manager = None
    resources._resource_manager = None
    database._database_manager = None

    yield

    # Restore original configuration
    for key, original_value in original_vars.items():
        if original_value is not None:
            os.environ[key] = original_value
        else:
            os.environ.pop(key, None)

    # Reset global instances again
    corpus_tools._checkpoint_manager = None
    rag_tools._rag_manager = None
    resources._resource_manager = None
    database._database_manager = None


@pytest_asyncio.fixture(scope="function")
async def rag_tools_manager(
    clean_db: DatabaseManager, weaviate_service
) -> AsyncGenerator[RAGToolsManager, None]:
    """Provide a RAGToolsManager with real database and Weaviate."""
    # The environment variables are already set by setup_test_services_config
    manager = RAGToolsManager()

    # Override database manager with our test instance
    manager.db_manager = clean_db
    manager.initialized = True

    # Weaviate client will be created with real connection from env var
    # OpenAI client will use fake key but that's OK for testing basic functionality

    yield manager

    await manager.close()


@pytest_asyncio.fixture(scope="function")
async def resource_manager(
    clean_db: DatabaseManager,
) -> AsyncGenerator[BioMCPResourceManager, None]:
    """Provide a BioMCPResourceManager with real database."""
    manager = BioMCPResourceManager()
    # Override services with test instances
    manager.document_service._db_manager = clean_db
    manager.document_service._initialized = True
    manager.checkpoint_service._db_manager = clean_db
    manager.checkpoint_service._initialized = True
    manager.initialized = True

    yield manager

    await manager.close()


@pytest_asyncio.fixture(scope="function")
async def sample_documents(clean_db: DatabaseManager) -> list:
    """Create sample documents for testing."""
    documents_data = [
        {
            "pmid": "12345678",
            "title": "Cancer Research Paper",
            "abstract": "This paper studies cancer treatment approaches.",
            "authors": ["Smith, J.", "Doe, A."],
            "journal": "Nature Medicine",
            "keywords": ["cancer", "treatment", "therapy"],
        },
        {
            "pmid": "87654321",
            "title": "AI in Medicine",
            "abstract": "Machine learning applications in medical diagnosis.",
            "authors": ["Johnson, B.", "Lee, C."],
            "journal": "Nature AI",
            "keywords": ["ai", "machine learning", "diagnosis"],
        },
    ]

    created_docs = []
    for doc_data in documents_data:
        doc = await clean_db.create_document(doc_data)
        created_docs.append(doc)

    return created_docs


@pytest_asyncio.fixture(scope="function")
async def sample_checkpoint(clean_db: DatabaseManager, sample_documents) -> str:
    """Create a sample checkpoint for testing."""
    checkpoint_id = "test_checkpoint_001"

    await clean_db.create_corpus_checkpoint(
        checkpoint_id=checkpoint_id,
        name="Test Checkpoint",
        description="A test checkpoint for integration testing",
        primary_queries=["cancer", "ai medicine"],
    )

    return checkpoint_id
