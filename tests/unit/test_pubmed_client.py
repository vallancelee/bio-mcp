"""
Unit tests for PubMed API client.
Phase 3A: Basic Biomedical Tools - TDD for PubMed integration.
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from bio_mcp.pubmed_client import (
    PubMedAPIError,
    PubMedClient,
    PubMedConfig,
    PubMedDocument,
    PubMedSearchResult,
    RateLimitError,
    parse_efetch_response,
    parse_esearch_response,
)


class TestPubMedConfig:
    """Test PubMed API configuration."""

    def test_config_creation(self):
        """Test PubMed configuration creation."""
        config = PubMedConfig(
            api_key="test_key_123",
            base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
            rate_limit_per_second=3,
            timeout=30.0,
            retries=3,
        )

        assert config.api_key == "test_key_123"
        assert config.base_url == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        assert config.rate_limit_per_second == 3
        assert config.timeout == 30.0
        assert config.retries == 3

    def test_config_defaults(self):
        """Test default configuration values."""
        config = PubMedConfig()

        assert config.api_key is None
        assert config.base_url == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        assert config.rate_limit_per_second == 1  # Default without API key
        assert config.timeout == 30.0
        assert config.retries == 3

    def test_config_rate_limit_without_api_key(self):
        """Test rate limit adjustment when no API key."""
        config = PubMedConfig(api_key=None)

        # Should default to more conservative rate limit without API key
        assert config.rate_limit_per_second == 1

    def test_config_from_env(self):
        """Test configuration from environment variables."""
        test_env = {
            "BIO_MCP_PUBMED_API_KEY": "env_key_456",
            "BIO_MCP_PUBMED_RATE_LIMIT": "5",
            "BIO_MCP_PUBMED_TIMEOUT": "45.0",
        }

        with patch.dict("os.environ", test_env):
            config = PubMedConfig.from_env()

            assert config.api_key == "env_key_456"
            assert config.rate_limit_per_second == 5
            assert config.timeout == 45.0


class TestPubMedDocument:
    """Test PubMed document model."""

    def test_document_creation(self):
        """Test creating PubMed document from API data."""
        doc_data = {
            "pmid": "12345678",
            "title": "CRISPR-Cas9 gene editing in human embryos",
            "abstract": "This study investigates...",
            "authors": ["Smith J", "Doe A", "Johnson B"],
            "journal": "Nature",
            "publication_date": "2023-06-15",
            "doi": "10.1038/nature12345",
            "keywords": ["CRISPR", "gene editing", "embryos"],
            "mesh_terms": ["Gene Editing", "CRISPR-Cas Systems"],
        }

        doc = PubMedDocument.from_api_data(doc_data)

        assert doc.pmid == "12345678"
        assert doc.title == "CRISPR-Cas9 gene editing in human embryos"
        assert doc.abstract == "This study investigates..."
        assert len(doc.authors) == 3
        assert doc.authors[0] == "Smith J"
        assert doc.journal == "Nature"
        assert doc.publication_date == date(2023, 6, 15)
        assert doc.doi == "10.1038/nature12345"
        assert "CRISPR" in doc.keywords
        assert "Gene Editing" in doc.mesh_terms

    def test_document_minimal_data(self):
        """Test document creation with minimal required data."""
        doc_data = {"pmid": "87654321", "title": "Minimal test document"}

        doc = PubMedDocument.from_api_data(doc_data)

        assert doc.pmid == "87654321"
        assert doc.title == "Minimal test document"
        assert doc.abstract is None
        assert doc.authors == []
        assert doc.journal is None
        assert doc.publication_date is None
        assert doc.doi is None
        assert doc.keywords == []
        assert doc.mesh_terms == []

    def test_document_to_database_format(self):
        """Test converting PubMed document to database format."""
        doc = PubMedDocument(
            pmid="12345678",
            title="Test Document",
            abstract="Test abstract",
            authors=["Author A", "Author B"],
            journal="Test Journal",
            publication_date=date(2023, 6, 15),
            doi="10.1000/test.123",
            keywords=["test", "research"],
            mesh_terms=["Test Term"],
        )

        db_data = doc.to_database_format()

        assert db_data["pmid"] == "12345678"
        assert db_data["title"] == "Test Document"
        assert db_data["abstract"] == "Test abstract"
        assert db_data["authors"] == ["Author A", "Author B"]
        assert db_data["journal"] == "Test Journal"
        assert db_data["publication_date"] == date(2023, 6, 15)
        assert db_data["doi"] == "10.1000/test.123"
        assert db_data["keywords"] == ["test", "research"]


class TestPubMedSearchResult:
    """Test PubMed search result model."""

    def test_search_result_creation(self):
        """Test creating search result."""
        result = PubMedSearchResult(
            query="CRISPR gene editing",
            total_count=1250,
            pmids=["12345678", "87654321", "11111111"],
            web_env="test_web_env",
            query_key="1",
        )

        assert result.query == "CRISPR gene editing"
        assert result.total_count == 1250
        assert len(result.pmids) == 3
        assert "12345678" in result.pmids
        assert result.web_env == "test_web_env"
        assert result.query_key == "1"

    def test_search_result_pagination(self):
        """Test search result with pagination info."""
        result = PubMedSearchResult(
            query="COVID-19 vaccines",
            total_count=5000,
            pmids=["1", "2", "3"],
            web_env="env_123",
            query_key="2",
            retstart=0,
            retmax=20,
        )

        assert result.total_count == 5000
        assert result.retstart == 0
        assert result.retmax == 20
        assert result.has_more_results() is True

        # Test when no more results
        result.retstart = 4980
        assert result.has_more_results() is False


class TestPubMedAPIResponseParsing:
    """Test parsing of PubMed API responses."""

    def test_parse_esearch_response(self):
        """Test parsing esearch response."""
        response_data = {
            "esearchresult": {
                "count": "1250",
                "retmax": "20",
                "retstart": "0",
                "idlist": ["12345678", "87654321", "11111111"],
                "webenv": "test_web_env",
                "querykey": "1",
            }
        }

        result = parse_esearch_response(response_data, "CRISPR gene editing")

        assert result.query == "CRISPR gene editing"
        assert result.total_count == 1250
        assert result.retmax == 20
        assert result.retstart == 0
        assert len(result.pmids) == 3
        assert result.pmids[0] == "12345678"
        assert result.web_env == "test_web_env"
        assert result.query_key == "1"

    def test_parse_esearch_response_empty(self):
        """Test parsing empty esearch response."""
        response_data = {
            "esearchresult": {
                "count": "0",
                "retmax": "20",
                "retstart": "0",
                "idlist": [],
                "webenv": "",
                "querykey": "",
            }
        }

        result = parse_esearch_response(response_data, "nonexistent term")

        assert result.total_count == 0
        assert len(result.pmids) == 0
        assert result.web_env == ""

    def test_parse_efetch_response(self):
        """Test parsing efetch response."""
        response_data = {
            "PubmedArticleSet": {
                "PubmedArticle": [
                    {
                        "MedlineCitation": {
                            "PMID": {"#text": "12345678"},
                            "Article": {
                                "ArticleTitle": "Test Article Title",
                                "Abstract": {
                                    "AbstractText": "This is a test abstract."
                                },
                                "AuthorList": {
                                    "Author": [
                                        {"LastName": "Smith", "ForeName": "John"},
                                        {"LastName": "Doe", "ForeName": "Jane"},
                                    ]
                                },
                                "Journal": {"Title": "Test Journal"},
                                "ArticleDate": {
                                    "Year": "2023",
                                    "Month": "06",
                                    "Day": "15",
                                },
                            },
                        },
                        "PubmedData": {
                            "ArticleIdList": {
                                "ArticleId": [
                                    {"@IdType": "doi", "#text": "10.1000/test.123"}
                                ]
                            }
                        },
                    }
                ]
            }
        }

        documents = parse_efetch_response(response_data)

        assert len(documents) == 1
        doc = documents[0]
        assert doc.pmid == "12345678"
        assert doc.title == "Test Article Title"
        assert doc.abstract == "This is a test abstract."
        assert len(doc.authors) == 2
        assert doc.authors[0] == "Smith J"
        assert doc.journal == "Test Journal"
        assert doc.publication_date == date(2023, 6, 15)
        assert doc.doi == "10.1000/test.123"


class TestPubMedClient:
    """Test PubMed API client functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = PubMedConfig(
            api_key="test_key",
            rate_limit_per_second=10,  # Higher for testing
            timeout=30.0,
        )
        self.client = PubMedClient(self.config)

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization."""
        assert self.client.config == self.config
        assert self.client.session is not None
        assert self.client._rate_limiter is not None

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful PubMed search."""
        mock_response = {
            "esearchresult": {
                "count": "100",
                "retmax": "20",
                "retstart": "0",
                "idlist": ["12345678", "87654321"],
                "webenv": "test_web_env",
                "querykey": "1",
            }
        }

        with patch.object(
            self.client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await self.client.search("CRISPR gene editing", limit=20)

            assert result.query == "CRISPR gene editing"
            assert result.total_count == 100
            assert len(result.pmids) == 2
            assert "12345678" in result.pmids

            # Verify API call
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert "esearch.fcgi" in call_args[0][0]
            assert call_args[0][1]["term"] == "CRISPR gene editing"
            assert call_args[0][1]["retmax"] == "20"

    @pytest.mark.asyncio
    async def test_search_pagination(self):
        """Test search with pagination."""
        mock_response = {
            "esearchresult": {
                "count": "1000",
                "retmax": "50",
                "retstart": "100",
                "idlist": ["111", "222", "333"],
                "webenv": "test_web_env",
                "querykey": "1",
            }
        }

        with patch.object(
            self.client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await self.client.search("COVID-19", limit=50, offset=100)

            assert result.retstart == 100
            assert result.retmax == 50

            # Verify pagination parameters
            call_args = mock_request.call_args
            assert call_args[0][1]["retstart"] == "100"
            assert call_args[0][1]["retmax"] == "50"

    @pytest.mark.asyncio
    async def test_fetch_documents_success(self):
        """Test successful document fetching."""
        mock_response = {
            "PubmedArticleSet": {
                "PubmedArticle": [
                    {
                        "MedlineCitation": {
                            "PMID": {"#text": "12345678"},
                            "Article": {
                                "ArticleTitle": "Test Article",
                                "Abstract": {"AbstractText": "Test abstract"},
                                "Journal": {"Title": "Test Journal"},
                            },
                        },
                        "PubmedData": {"ArticleIdList": {"ArticleId": []}},
                    }
                ]
            }
        }

        with patch.object(
            self.client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            documents = await self.client.fetch_documents(["12345678"])

            assert len(documents) == 1
            doc = documents[0]
            assert doc.pmid == "12345678"
            assert doc.title == "Test Article"
            assert doc.abstract == "Test abstract"

            # Verify API call
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert "efetch.fcgi" in call_args[0][0]
            assert call_args[0][1]["id"] == "12345678"

    @pytest.mark.asyncio
    async def test_fetch_documents_batch(self):
        """Test fetching multiple documents in batch."""
        pmids = ["111", "222", "333", "444"]

        with patch.object(
            self.client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"PubmedArticleSet": {"PubmedArticle": []}}

            await self.client.fetch_documents(pmids)

            # Verify batch request
            call_args = mock_request.call_args
            assert call_args[0][1]["id"] == "111,222,333,444"

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting functionality."""
        import time

        with patch.object(
            self.client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"esearchresult": {"count": "0", "idlist": []}}

            start_time = time.time()

            # Make multiple requests that should be rate limited
            await self.client.search("test1")
            await self.client.search("test2")
            await self.client.search("test3")

            elapsed = time.time() - start_time

            # Should take at least some time due to rate limiting
            # (Exact timing depends on rate limit, but should be > 0)
            assert elapsed > 0
            assert mock_request.call_count == 3

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test API error handling."""
        with patch.object(
            self.client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("API connection failed")

            with pytest.raises(PubMedAPIError) as exc_info:
                await self.client.search(
                    "test query", retries=0
                )  # Disable retries for this test

            assert "API connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        """Test rate limit error handling."""
        with patch.object(
            self.client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            # Simulate RateLimitError from _make_request
            mock_request.side_effect = RateLimitError("Rate limit exceeded")

            with pytest.raises(RateLimitError):
                await self.client.search("test query", retries=0)

    @pytest.mark.asyncio
    async def test_retry_logic(self):
        """Test retry logic on transient failures."""
        with patch.object(
            self.client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            # First two calls fail, third succeeds
            mock_request.side_effect = [
                Exception("Temporary failure"),
                Exception("Another failure"),
                {"esearchresult": {"count": "1", "idlist": ["123"]}},
            ]

            result = await self.client.search("test query", retries=3)

            assert result.total_count == 1
            assert mock_request.call_count == 3

    @pytest.mark.asyncio
    async def test_client_cleanup(self):
        """Test client resource cleanup."""
        await self.client.close()

        # After closing, session should be None
        assert self.client.session is None


class TestPubMedClientIntegration:
    """Integration tests for PubMed client (with mocked responses)."""

    @pytest.mark.asyncio
    async def test_search_and_fetch_workflow(self):
        """Test complete search and fetch workflow."""
        config = PubMedConfig(api_key="test_key")
        client = PubMedClient(config)

        # Mock search response
        search_response = {
            "esearchresult": {
                "count": "2",
                "retmax": "20",
                "retstart": "0",
                "idlist": ["12345678", "87654321"],
                "webenv": "test_web_env",
                "querykey": "1",
            }
        }

        # Mock fetch response
        fetch_response = {
            "PubmedArticleSet": {
                "PubmedArticle": [
                    {
                        "MedlineCitation": {
                            "PMID": {"#text": "12345678"},
                            "Article": {
                                "ArticleTitle": "First Article",
                                "Abstract": {"AbstractText": "First abstract"},
                                "Journal": {"Title": "Journal A"},
                            },
                        },
                        "PubmedData": {"ArticleIdList": {"ArticleId": []}},
                    },
                    {
                        "MedlineCitation": {
                            "PMID": {"#text": "87654321"},
                            "Article": {
                                "ArticleTitle": "Second Article",
                                "Abstract": {"AbstractText": "Second abstract"},
                                "Journal": {"Title": "Journal B"},
                            },
                        },
                        "PubmedData": {"ArticleIdList": {"ArticleId": []}},
                    },
                ]
            }
        }

        with patch.object(
            client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            # Return search response first, then fetch response
            mock_request.side_effect = [search_response, fetch_response]

            try:
                # Search for documents
                search_result = await client.search("CRISPR")
                assert search_result.total_count == 2
                assert len(search_result.pmids) == 2

                # Fetch the documents
                documents = await client.fetch_documents(search_result.pmids)
                assert len(documents) == 2
                assert documents[0].pmid == "12345678"
                assert documents[0].title == "First Article"
                assert documents[1].pmid == "87654321"
                assert documents[1].title == "Second Article"

            finally:
                await client.close()
