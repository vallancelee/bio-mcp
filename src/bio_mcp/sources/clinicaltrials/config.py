"""
ClinicalTrials.gov-specific configuration.
"""

import os
from dataclasses import dataclass


@dataclass
class ClinicalTrialsConfig:
    """Configuration for ClinicalTrials.gov API client."""

    base_url: str = "https://clinicaltrials.gov/api/v2"
    rate_limit_per_second: int = 5
    timeout: float = 30.0
    retries: int = 3
    page_size: int = 100

    @classmethod
    def from_env(cls) -> "ClinicalTrialsConfig":
        """Create configuration from environment variables."""
        return cls(
            base_url=os.getenv(
                "BIO_MCP_CTGOV_BASE_URL", "https://clinicaltrials.gov/api/v2"
            ),
            rate_limit_per_second=int(os.getenv("BIO_MCP_CTGOV_RATE_LIMIT", "5")),
            timeout=float(os.getenv("BIO_MCP_CTGOV_TIMEOUT", "30.0")),
            retries=int(os.getenv("BIO_MCP_CTGOV_RETRIES", "3")),
            page_size=int(os.getenv("BIO_MCP_CTGOV_PAGE_SIZE", "100")),
        )
