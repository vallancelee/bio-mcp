"""
Configuration objects for search and tool parameters.
Centralizes magic numbers and configuration values for better maintainability.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchConfig:
    """Configuration for search tool parameters."""

    # Search result limits
    DEFAULT_TOP_K: int = 10
    MIN_TOP_K: int = 1
    MAX_TOP_K: int = 50

    # PubMed search limits
    PUBMED_DEFAULT_LIMIT: int = 10
    PUBMED_MIN_LIMIT: int = 1
    PUBMED_MAX_LIMIT: int = 100

    # Hybrid search parameters
    DEFAULT_ALPHA: float = (
        0.5  # Balanced hybrid search (0.0=pure BM25, 1.0=pure vector)
    )
    MIN_ALPHA: float = 0.0
    MAX_ALPHA: float = 1.0


@dataclass(frozen=True)
class ResponseConfig:
    """Configuration for response formatting and content limits."""

    # Content truncation
    MAX_CONTENT_PREVIEW_LENGTH: int = 500
    CONTENT_TRUNCATION_SUFFIX: str = "..."

    # Response formatting
    MAX_PMIDS_DISPLAY: int = 5  # Maximum PMIDs to show in search results
    PMIDS_TRUNCATION_SUFFIX: str = " ... ({total} total)"


@dataclass(frozen=True)
class PerformanceConfig:
    """Configuration for performance-related parameters."""

    # Response time targets
    SEARCH_RESPONSE_TIME_TARGET_MS: int = 200
    SYNC_RESPONSE_TIME_TARGET_MS: int = 5000

    # Batch processing
    DEFAULT_BATCH_SIZE: int = 100
    MAX_BATCH_SIZE: int = 1000


# Global configuration instances
SEARCH_CONFIG = SearchConfig()
RESPONSE_CONFIG = ResponseConfig()
PERFORMANCE_CONFIG = PerformanceConfig()
