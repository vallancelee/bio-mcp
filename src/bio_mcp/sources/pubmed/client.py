"""
PubMed API client for Bio-MCP server.
Phase 3A: Basic Biomedical Tools - PubMed integration with E-utilities API.
"""

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx
import xmltodict

from bio_mcp.config.logging_config import get_logger

logger = get_logger(__name__)


# Custom exceptions
class PubMedAPIError(Exception):
    """Base exception for PubMed API errors."""

    pass


class RateLimitError(PubMedAPIError):
    """Exception for rate limiting errors."""

    pass


@dataclass
class PubMedConfig:
    """Configuration for PubMed API client."""

    api_key: str | None = None
    base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    rate_limit_per_second: int | None = None
    timeout: float = 30.0
    retries: int = 3

    def __post_init__(self) -> None:
        """Set rate limit based on API key availability."""
        if self.rate_limit_per_second is None:
            # NCBI recommends different rates with/without API key
            self.rate_limit_per_second = 3 if self.api_key else 1

    @classmethod
    def from_env(cls) -> "PubMedConfig":
        """Create configuration from environment variables."""
        return cls(
            api_key=os.getenv("BIO_MCP_PUBMED_API_KEY"),
            rate_limit_per_second=int(os.getenv("BIO_MCP_PUBMED_RATE_LIMIT", "0"))
            or None,
            timeout=float(os.getenv("BIO_MCP_PUBMED_TIMEOUT", "30.0")),
        )


@dataclass
class PubMedDocument:
    """Represents a PubMed document."""

    pmid: str
    title: str
    abstract: str | None = None
    authors: list[str] = None
    journal: str | None = None
    publication_date: date | None = None
    doi: str | None = None
    keywords: list[str] = None
    mesh_terms: list[str] = None

    def __post_init__(self) -> None:
        """Initialize empty lists for optional fields."""
        if self.authors is None:
            self.authors = []
        if self.keywords is None:
            self.keywords = []
        if self.mesh_terms is None:
            self.mesh_terms = []

    @classmethod
    def from_api_data(cls, data: dict[str, Any]) -> "PubMedDocument":
        """Create PubMedDocument from API response data."""
        # Parse publication date
        pub_date = None
        if data.get("publication_date"):
            try:
                pub_date = datetime.strptime(
                    data["publication_date"], "%Y-%m-%d"
                ).date()
            except (ValueError, TypeError):
                pass

        return cls(
            pmid=data["pmid"],
            title=data["title"],
            abstract=data.get("abstract"),
            authors=data.get("authors", []),
            journal=data.get("journal"),
            publication_date=pub_date,
            doi=data.get("doi"),
            keywords=data.get("keywords", []),
            mesh_terms=data.get("mesh_terms", []),
        )

    def to_database_format(self) -> dict[str, Any]:
        """Convert to format suitable for database storage."""
        return {
            "pmid": self.pmid,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "journal": self.journal,
            "publication_date": self.publication_date,
            "doi": self.doi,
            "keywords": self.keywords,
            # Note: mesh_terms not included in database format for now
        }


@dataclass
class PubMedSearchResult:
    """Represents a PubMed search result."""

    query: str
    total_count: int
    pmids: list[str]
    web_env: str = ""
    query_key: str = ""
    retstart: int = 0
    retmax: int = 20

    def has_more_results(self) -> bool:
        """Check if there are more results available."""
        return (self.retstart + self.retmax) < self.total_count


class RateLimiter:
    """Simple rate limiter for API requests."""

    def __init__(self, rate_per_second: int):
        self.rate_per_second = rate_per_second
        self.min_interval = 1.0 / rate_per_second
        self.last_request_time = 0.0

    async def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limit."""
        now = time.time()
        time_since_last = now - self.last_request_time

        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()


class PubMedClient:
    """HTTP client for PubMed E-utilities API."""

    def __init__(self, config: PubMedConfig):
        self.config = config
        self.session: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter(config.rate_limit_per_second)
        self.last_request_time = 0.0

        # Initialize session
        self._init_session()

    def _init_session(self) -> None:
        """Initialize HTTP session."""
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            headers={"User-Agent": "Bio-MCP/1.0 (contact: bio-mcp@example.com)"},
        )

    async def close(self) -> None:
        """Close HTTP session and cleanup resources."""
        if self.session:
            await self.session.aclose()
            self.session = None

    async def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting between API requests."""
        await self._rate_limiter.wait_if_needed()

    async def _make_request(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        """Make HTTP request with rate limiting and error handling."""
        if not self.session:
            self._init_session()

        # Apply rate limiting
        await self._rate_limiter.wait_if_needed()

        # Add API key if available
        if self.config.api_key:
            params["api_key"] = self.config.api_key

        # Add common parameters
        params["format"] = "json"

        try:
            logger.debug("Making PubMed API request", url=url, params=params)

            response = await self.session.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            logger.debug("PubMed API response received", status=response.status_code)

            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("PubMed API rate limit exceeded")
                raise RateLimitError("Rate limit exceeded")
            else:
                logger.error(
                    "PubMed API HTTP error", status=e.response.status_code, error=str(e)
                )
                raise PubMedAPIError(f"HTTP {e.response.status_code}: {e}")
        except Exception as e:
            logger.error("PubMed API request failed", error=str(e))
            raise PubMedAPIError(f"Request failed: {e}")

    async def _make_xml_request(
        self, url: str, params: dict[str, str]
    ) -> dict[str, Any]:
        """Make request that returns XML, convert to dict for parsing."""
        try:
            await self._enforce_rate_limit()

            if self.config.api_key:
                params = {**params, "api_key": self.config.api_key}

            logger.debug("Making PubMed XML API request", url=url, params=params)

            response = await self.session.get(url, params=params)
            response.raise_for_status()

            # Convert XML response to dict for parsing
            xml_text = response.text
            try:
                # Parse XML to dict
                data = xmltodict.parse(xml_text)
                logger.debug(
                    "PubMed XML API response received and parsed",
                    status=response.status_code,
                )
                return data
            except Exception as xml_error:
                logger.error(
                    "Failed to parse XML response",
                    error=str(xml_error),
                    xml_snippet=xml_text[:200],
                )
                # Return empty dict to fail gracefully
                return {}

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("PubMed API rate limit exceeded")
                raise RateLimitError("Rate limit exceeded")
            else:
                logger.error(
                    "PubMed API HTTP error", status=e.response.status_code, error=str(e)
                )
                raise PubMedAPIError(f"HTTP {e.response.status_code}: {e}")
        except Exception as e:
            logger.error("PubMed API request failed", error=str(e))
            raise PubMedAPIError(f"Request failed: {e}")

    async def search(
        self, query: str, limit: int = 20, offset: int = 0, retries: int | None = None
    ) -> PubMedSearchResult:
        """Search PubMed and return PMIDs."""
        if retries is None:
            retries = self.config.retries

        url = f"{self.config.base_url}esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": str(limit),
            "retstart": str(offset),
            "usehistory": "y",  # Store results on server for potential follow-up
        }

        logger.info("Searching PubMed", query=query, limit=limit, offset=offset)

        for attempt in range(retries + 1):
            try:
                response_data = await self._make_request(url, params)
                result = parse_esearch_response(response_data, query)

                logger.info(
                    "PubMed search completed",
                    query=query,
                    total_count=result.total_count,
                    returned_count=len(result.pmids),
                )

                return result

            except (PubMedAPIError, RateLimitError):
                # Re-raise PubMed specific errors immediately
                raise
            except Exception as e:
                if attempt == retries:
                    # Convert generic exception to PubMedAPIError on final attempt
                    raise PubMedAPIError(f"Search failed: {e}")

                wait_time = 2**attempt  # Exponential backoff
                logger.warning(
                    "PubMed search attempt failed, retrying",
                    attempt=attempt + 1,
                    wait_time=wait_time,
                    error=str(e),
                )
                await asyncio.sleep(wait_time)

        # Should not reach here
        raise PubMedAPIError("All retry attempts failed")

    async def search_incremental(
        self,
        query: str,
        last_edat: str | None = None,
        limit: int = 20,
        offset: int = 0,
        retries: int | None = None,
    ) -> PubMedSearchResult:
        """Search PubMed with EDAT (Entry Date) filtering for incremental sync.

        Args:
            query: Base search query
            last_edat: Last Entry Date in YYYY/MM/DD format (e.g., "2024/01/15")
            limit: Maximum number of results to return
            offset: Starting offset for pagination
            retries: Number of retry attempts

        Returns:
            PubMedSearchResult with PMIDs of documents newer than last_edat
        """
        if retries is None:
            retries = self.config.retries

        # Build incremental query with EDAT filter
        incremental_query = query
        if last_edat:
            # Add EDAT filter to find documents entered after the last sync
            # EDAT (Entry Date) tracks when documents were added to PubMed
            incremental_query = f"({query}) AND (EDAT[{last_edat}:3000/12/31])"
            logger.info(
                "Using incremental search with EDAT filter",
                base_query=query,
                last_edat=last_edat,
                full_query=incremental_query,
            )
        else:
            logger.info("Using full search (no EDAT filter)", query=query)

        url = f"{self.config.base_url}esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": incremental_query,
            "retmax": str(limit),
            "retstart": str(offset),
            "usehistory": "y",
            "sort": "date",  # Sort by date to get newest entries first
        }

        logger.info(
            "Searching PubMed incrementally",
            query=incremental_query,
            limit=limit,
            offset=offset,
            last_edat=last_edat,
        )

        for attempt in range(retries + 1):
            try:
                response_data = await self._make_request(url, params)
                result = parse_esearch_response(response_data, incremental_query)

                logger.info(
                    "PubMed incremental search completed",
                    base_query=query,
                    last_edat=last_edat,
                    total_count=result.total_count,
                    returned_count=len(result.pmids),
                )

                return result

            except (PubMedAPIError, RateLimitError):
                # Re-raise PubMed specific errors immediately
                raise
            except Exception as e:
                if attempt == retries:
                    # Convert generic exception to PubMedAPIError on final attempt
                    raise PubMedAPIError(f"Incremental search failed: {e}")

                wait_time = 2**attempt  # Exponential backoff
                logger.warning(
                    "PubMed incremental search attempt failed, retrying",
                    attempt=attempt + 1,
                    wait_time=wait_time,
                    error=str(e),
                )
                await asyncio.sleep(wait_time)

        # Should not reach here
        raise PubMedAPIError("All incremental search retry attempts failed")

    async def fetch_documents(self, pmids: list[str]) -> list[PubMedDocument]:
        """Fetch full document details by PMIDs."""
        if not pmids:
            return []

        url = f"{self.config.base_url}efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }

        logger.info("Fetching PubMed documents", pmid_count=len(pmids))

        try:
            response_data = await self._make_xml_request(url, params)
            documents = parse_efetch_response(response_data)

            logger.info(
                "PubMed documents fetched",
                requested_count=len(pmids),
                returned_count=len(documents),
            )

            return documents

        except Exception as e:
            logger.error("Failed to fetch PubMed documents", pmids=pmids, error=str(e))
            raise


def parse_esearch_response(
    response_data: dict[str, Any], query: str
) -> PubMedSearchResult:
    """Parse esearch API response."""
    try:
        esearch_result = response_data["esearchresult"]

        return PubMedSearchResult(
            query=query,
            total_count=int(esearch_result.get("count", "0")),
            pmids=esearch_result.get("idlist", []),
            web_env=esearch_result.get("webenv", ""),
            query_key=esearch_result.get("querykey", ""),
            retstart=int(esearch_result.get("retstart", "0")),
            retmax=int(esearch_result.get("retmax", "20")),
        )

    except (KeyError, ValueError, TypeError) as e:
        raise PubMedAPIError(f"Invalid esearch response format: {e}")


def parse_efetch_response(response_data: dict[str, Any]) -> list[PubMedDocument]:
    """Parse efetch API response."""
    documents = []

    try:
        # Handle XML response converted to JSON structure
        pubmed_article_set = response_data.get("PubmedArticleSet", {})
        pubmed_articles = pubmed_article_set.get("PubmedArticle", [])

        # Ensure it's a list
        if not isinstance(pubmed_articles, list):
            pubmed_articles = [pubmed_articles]

        for article_data in pubmed_articles:
            doc = _parse_single_article(article_data)
            if doc:
                documents.append(doc)

        return documents

    except Exception as e:
        logger.error("Failed to parse efetch response", error=str(e))
        raise PubMedAPIError(f"Invalid efetch response format: {e}")


def _parse_single_article(article_data: dict[str, Any]) -> PubMedDocument | None:
    """Parse a single PubMed article from XML/JSON structure."""
    try:
        medline_citation = article_data.get("MedlineCitation", {})
        pubmed_data = article_data.get("PubmedData", {})

        # Extract PMID
        pmid_data = medline_citation.get("PMID", {})
        pmid = (
            pmid_data.get("#text", "")
            if isinstance(pmid_data, dict)
            else str(pmid_data)
        )

        # Extract article info
        article = medline_citation.get("Article", {})
        title = article.get("ArticleTitle", "")

        # Extract abstract
        abstract_data = article.get("Abstract", {})
        abstract_text = abstract_data.get("AbstractText", "")

        def extract_text_from_xml_dict(obj):
            """Recursively extract text content from XML dictionary structure."""
            if isinstance(obj, dict):
                # Handle XML dictionary with #text content
                if "#text" in obj:
                    return str(obj["#text"])
                # Handle simple text content
                elif len(obj) == 1 and isinstance(next(iter(obj.values())), str):
                    return str(next(iter(obj.values())))
                # Recursively extract from nested structures
                else:
                    parts = []
                    for value in obj.values():
                        if isinstance(value, str | dict | list):
                            parts.append(extract_text_from_xml_dict(value))
                    return " ".join(filter(None, parts))
            elif isinstance(obj, list):
                return " ".join(extract_text_from_xml_dict(item) for item in obj)
            else:
                return str(obj) if obj else ""

        if isinstance(abstract_text, dict | list):
            abstract_text = extract_text_from_xml_dict(abstract_text)
        elif isinstance(abstract_text, list):
            abstract_text = " ".join(str(part) for part in abstract_text)

        abstract = abstract_text.strip() if abstract_text else None

        # Extract authors
        authors = []
        author_list = article.get("AuthorList", {})
        if "Author" in author_list:
            author_data = author_list["Author"]
            if not isinstance(author_data, list):
                author_data = [author_data]

            for author in author_data:
                last_name = author.get("LastName", "")
                fore_name = author.get("ForeName", "")
                if last_name:
                    # Format as "LastName F" (first initial)
                    author_name = last_name
                    if fore_name:
                        author_name += f" {fore_name[0]}"
                    authors.append(author_name)

        # Extract journal
        journal_data = article.get("Journal", {})
        journal = journal_data.get("Title", "")

        # Extract publication date
        pub_date = None
        article_date = article.get("ArticleDate", {})
        if article_date:
            try:
                year = int(article_date.get("Year", "0"))
                month = int(article_date.get("Month", "1"))
                day = int(article_date.get("Day", "1"))
                if year > 0:
                    pub_date = date(year, month, day)
            except (ValueError, TypeError):
                pass

        # Extract DOI
        doi = None
        article_ids = pubmed_data.get("ArticleIdList", {}).get("ArticleId", [])
        if not isinstance(article_ids, list):
            article_ids = [article_ids]

        for article_id in article_ids:
            if isinstance(article_id, dict) and article_id.get("@IdType") == "doi":
                doi = article_id.get("#text")
                break

        if not pmid or not title:
            logger.warning("Skipping article with missing PMID or title")
            return None

        return PubMedDocument(
            pmid=pmid,
            title=title,
            abstract=abstract,
            authors=authors,
            journal=journal,
            publication_date=pub_date,
            doi=doi,
            keywords=[],  # Will be populated later if needed
            mesh_terms=[],  # Will be populated later if needed
        )

    except Exception as e:
        logger.error("Failed to parse single article", error=str(e))
        return None
