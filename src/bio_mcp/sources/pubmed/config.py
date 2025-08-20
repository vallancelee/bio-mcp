"""
PubMed-specific configuration.
"""

import os
from dataclasses import dataclass


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
            api_key=os.getenv("NCBI_API_KEY"),
            base_url=os.getenv("PUBMED_BASE_URL", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"),
            timeout=float(os.getenv("PUBMED_TIMEOUT", "30.0")),
            retries=int(os.getenv("PUBMED_RETRIES", "3"))
        )