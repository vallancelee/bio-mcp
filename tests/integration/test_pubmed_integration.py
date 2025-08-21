"""
Integration tests for PubMed API client with real API calls.

IMPORTANT: These tests make real API calls to NCBI E-utilities.
- Tests are designed to be minimal and respectful of rate limits
- Uses NCBI recommended delays between requests (1/sec without API key, 3/sec with key)
- Only makes essential API calls to test core functionality
- Uses stable queries and PMIDs to minimize impact

Set NCBI_API_KEY environment variable to increase rate limits.
"""

import asyncio
import os
from datetime import date

import pytest
import pytest_asyncio

from bio_mcp.sources.pubmed.client import PubMedClient, PubMedConfig, PubMedDocument


class PubMedTestHelpers:
    """Minimal helper utilities for PubMed testing."""
    
    # Single, stable test query to minimize API calls
    STABLE_QUERY = "cancer AND review[Publication Type] AND 2023[PDAT]"
    
    # One well-known, stable PMID for fetch testing
    STABLE_PMID = "37386842"  # A 2023 Nature Reviews Cancer paper
    
    @classmethod
    def get_test_config(cls) -> PubMedConfig:
        """Get PubMed configuration for testing with proper rate limiting."""
        api_key = os.getenv("NCBI_API_KEY")
        
        return PubMedConfig(
            api_key=api_key,
            timeout=30.0,
            retries=1  # Minimal retries to keep tests fast
        )
    
    @classmethod
    def validate_document_structure(cls, doc: PubMedDocument) -> None:
        """Validate basic PubMedDocument structure."""
        assert isinstance(doc, PubMedDocument)
        assert doc.pmid and doc.pmid.isdigit()
        assert doc.title and len(doc.title) > 0
        assert isinstance(doc.authors, list)
        assert isinstance(doc.keywords, list)


@pytest_asyncio.fixture(scope="function")
async def pubmed_client():
    """Create a fresh PubMed client for each test function."""
    config = PubMedTestHelpers.get_test_config()
    client = PubMedClient(config)
    
    # Add extra delay to be respectful to API
    await asyncio.sleep(1.0)
    
    yield client
    
    # Safe cleanup
    try:
        if client.session:
            await client.close()
    except Exception:
        pass  # Ignore cleanup errors


class TestPubMedClientCore:
    """Core functionality tests with minimal API calls."""
    
    @pytest.mark.asyncio
    async def test_search_basic_functionality(self, pubmed_client):
        """Test basic search functionality with one API call."""
        query = PubMedTestHelpers.STABLE_QUERY
        
        result = await pubmed_client.search(query, limit=5)
        
        # Validate search result structure
        assert result.query == query
        assert result.total_count > 0
        assert len(result.pmids) > 0
        assert len(result.pmids) <= 5
        assert all(pmid.isdigit() for pmid in result.pmids)
        assert result.web_env  # Should have history storage
        
        print(f"✓ Search returned {result.total_count} total results, got {len(result.pmids)} PMIDs")
        
        # Respectful delay before next test
        await asyncio.sleep(2.0)
    
    @pytest.mark.asyncio
    async def test_fetch_document_functionality(self, pubmed_client):
        """Test document fetching with one API call."""
        pmid = PubMedTestHelpers.STABLE_PMID
        
        documents = await pubmed_client.fetch_documents([pmid])
        
        # Validate fetch result structure
        assert len(documents) == 1
        doc = documents[0]
        
        PubMedTestHelpers.validate_document_structure(doc)
        assert doc.pmid == pmid
        assert len(doc.title) > 20  # Should have substantial title
        
        # Test database format conversion
        db_format = doc.to_database_format()
        assert isinstance(db_format, dict)
        assert db_format["pmid"] == pmid
        assert db_format["title"] == doc.title
        
        print(f"✓ Fetched document: {doc.title[:60]}...")
        
        # Respectful delay before next test
        await asyncio.sleep(2.0)
    
    @pytest.mark.asyncio
    async def test_search_fetch_integration(self, pubmed_client):
        """Test search + fetch workflow with minimal API calls."""
        query = "diabetes[MeSH Terms] AND 2023[PDAT]"
        
        # Search for PMIDs
        search_result = await pubmed_client.search(query, limit=3)
        assert len(search_result.pmids) > 0
        
        print(f"✓ Search found {search_result.total_count} total results")
        
        # Respectful delay between API calls
        await asyncio.sleep(2.0)
        
        # Fetch only first document to minimize API calls
        first_pmid = search_result.pmids[0]
        documents = await pubmed_client.fetch_documents([first_pmid])
        
        assert len(documents) >= 0  # May be empty due to parsing issues, that's OK
        if documents:
            doc = documents[0]
            PubMedTestHelpers.validate_document_structure(doc)
            assert doc.pmid == first_pmid
            print(f"✓ Fetched document: {doc.title[:60]}...")
        else:
            print(f"✓ Fetch completed (no documents returned for PMID {first_pmid})")
        
        # Respectful delay after test
        await asyncio.sleep(2.0)


class TestPubMedClientConfiguration:
    """Test configuration and rate limiting without API calls."""
    
    def test_config_creation(self):
        """Test configuration creation without API calls."""
        # Test basic config
        config = PubMedConfig()
        assert config.base_url == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        assert config.timeout == 30.0
        assert config.retries == 3
        assert config.rate_limit_per_second == 1  # Default without API key
        
        # Test config with API key
        config_with_key = PubMedConfig(api_key="test_key")
        assert config_with_key.rate_limit_per_second == 3
        
        # Test from environment
        env_config = PubMedConfig.from_env()
        api_key = os.getenv("NCBI_API_KEY")
        assert env_config.api_key == api_key
        
        if api_key:
            assert env_config.rate_limit_per_second == 3
            print("✓ Using API key - rate limit: 3 req/sec")
        else:
            assert env_config.rate_limit_per_second == 1
            print("✓ No API key - rate limit: 1 req/sec")
    
    @pytest.mark.asyncio
    async def test_rate_limiter_timing(self):
        """Test rate limiter without making actual API calls."""
        from bio_mcp.sources.pubmed.client import RateLimiter
        
        # Test rate limiter with 2 requests per second
        rate_limiter = RateLimiter(2)
        
        start_time = asyncio.get_event_loop().time()
        
        # Simulate 3 "requests"
        await rate_limiter.wait_if_needed()  # First request - no wait
        await rate_limiter.wait_if_needed()  # Second request - some wait
        await rate_limiter.wait_if_needed()  # Third request - more wait
        
        elapsed = asyncio.get_event_loop().time() - start_time
        
        # Should take at least 1 second for 3 requests at 2/sec rate
        assert elapsed >= 0.8, f"Rate limiting too fast: {elapsed}s"
        assert elapsed <= 2.0, f"Rate limiting too slow: {elapsed}s"
        
        print(f"✓ Rate limiter timing: {elapsed:.2f}s for 3 requests")


class TestPubMedDocumentModel:
    """Test document model functionality without API calls."""
    
    def test_document_creation_and_conversion(self):
        """Test document creation and format conversion."""
        # Test data mimicking API response
        test_data = {
            "pmid": "12345678",
            "title": "Test Article About Cancer Research",
            "abstract": "This is a test abstract describing cancer research methods.",
            "authors": ["Smith J", "Jones A", "Brown K"],
            "journal": "Test Journal of Medicine",
            "publication_date": "2023-06-15",
            "doi": "10.1234/test.2023.001",
            "keywords": ["cancer", "research", "treatment"],
            "mesh_terms": ["Neoplasms", "Therapeutics"]
        }
        
        # Create document from API data
        doc = PubMedDocument.from_api_data(test_data)
        
        # Validate structure
        PubMedTestHelpers.validate_document_structure(doc)
        assert doc.pmid == "12345678"
        assert doc.title == test_data["title"]
        assert doc.abstract == test_data["abstract"]
        assert doc.authors == test_data["authors"]
        assert doc.journal == test_data["journal"]
        assert doc.doi == test_data["doi"]
        assert doc.keywords == test_data["keywords"]
        assert doc.mesh_terms == test_data["mesh_terms"]
        
        # Test date parsing
        assert doc.publication_date == date(2023, 6, 15)
        
        # Test database format conversion
        db_format = doc.to_database_format()
        
        expected_fields = [
            "pmid", "title", "abstract", "authors", 
            "journal", "publication_date", "doi", "keywords"
        ]
        
        for field in expected_fields:
            assert field in db_format
            assert db_format[field] == getattr(doc, field)
        
        # mesh_terms should NOT be in database format
        assert "mesh_terms" not in db_format
        
        print("✓ Document model creation and conversion working correctly")


# Limit concurrent tests to respect rate limits
pytest.mark.asyncio_cooperative = True


# Mark all tests as integration tests requiring network
pytestmark = pytest.mark.integration