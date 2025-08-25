"""
Integration test fixtures for RAG quality testing with pre-populated data.
"""

import os

import pytest
import pytest_asyncio

from bio_mcp.services.document_chunk_service import DocumentChunkService
from tests.fixtures.rag_test_data import (
    get_biomedical_test_documents,
    get_quality_scores,
)


@pytest_asyncio.fixture(scope="session")
async def populated_weaviate():
    """
    Provide a Weaviate instance pre-populated with biomedical test data.

    This fixture:
    1. Connects to the running Weaviate instance from Docker Compose
    2. Populates it with consistent test documents for RAG quality tests
    3. Cleans up the data after the test session completes

    Requires OPENAI_API_KEY to be set for embeddings.
    """
    # Skip if no OpenAI API key (let individual tests handle this)
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY required for RAG integration tests")

    # Create document chunk service
    service = DocumentChunkService()
    await service.connect()

    # Get test documents and quality scores
    test_documents = get_biomedical_test_documents()
    quality_scores = get_quality_scores()

    print(f"\nPopulating Weaviate with {len(test_documents)} test documents...")

    # Store document UIDs for cleanup
    stored_uids = []
    total_chunks = 0

    try:
        # Add each test document
        for i, (doc, quality_score) in enumerate(
            zip(test_documents, quality_scores), 1
        ):
            try:
                chunk_uuids = await service.store_document_chunks(
                    doc, quality_score=quality_score
                )
                total_chunks += len(chunk_uuids)
                stored_uids.append(doc.uid)
                print(
                    f"  ✓ Added document {i}/{len(test_documents)}: {len(chunk_uuids)} chunks"
                )
            except Exception as e:
                print(f"  ✗ Failed to add document {i}: {e}")

        # Verify data was stored
        stats = await service.get_collection_stats()
        print(f"✓ Weaviate populated: {stats['total_chunks']} total chunks")

        # Yield connection info for tests
        yield {
            "service": service,
            "document_count": len(stored_uids),
            "chunk_count": total_chunks,
            "document_uids": stored_uids,
        }

    finally:
        # Cleanup: remove test documents
        print("\\nCleaning up test data from Weaviate...")
        try:
            for uid in stored_uids:
                deleted_count = await service.delete_document_chunks(uid)
                print(f"  ✓ Deleted {deleted_count} chunks for {uid}")
        except Exception as e:
            print(f"  ✗ Cleanup error: {e}")
        finally:
            await service.disconnect()


@pytest_asyncio.fixture(scope="function")
async def clean_weaviate_session(populated_weaviate):
    """
    Provide access to the populated Weaviate for individual test functions.

    This fixture ensures each test gets a fresh view of the same test data
    without needing to repopulate Weaviate for every test.
    """
    yield populated_weaviate


@pytest_asyncio.fixture(scope="function")
async def rag_service_with_data(clean_weaviate_session):
    """
    Provide a DocumentChunkService connected to the populated test data.

    This fixture is optimized for individual tests that need to search
    the pre-populated test documents.
    """
    weaviate_data = clean_weaviate_session
    service = weaviate_data["service"]

    # Verify service is still connected
    if not service._initialized:
        await service.connect()

    yield service
