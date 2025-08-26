"""LangGraph orchestrator configuration."""

from pydantic import BaseModel, Field

from bio_mcp.config.config import Config


class LangGraphConfig(BaseModel):
    """LangGraph-specific configuration."""
    
    # Graph execution
    debug_mode: bool = Field(default=False, description="Enable graph debugging")
    max_iterations: int = Field(default=50, description="Max graph iterations")
    recursion_limit: int = Field(default=100, description="Recursion depth limit")
    
    # Checkpointing
    checkpoint_db_path: str = Field(default=":memory:", description="SQLite checkpoint DB path")
    checkpoint_ttl: int = Field(default=3600, description="Checkpoint TTL in seconds")
    
    # LangSmith integration
    langsmith_project: str | None = Field(default="bio-mcp-orchestrator")
    langsmith_api_key: str | None = Field(default=None, description="LangSmith API key")
    enable_tracing: bool = Field(default=True, description="Enable LangSmith tracing")


class OrchestratorConfig(BaseModel):
    """Enhanced orchestrator configuration for LangGraph."""
    
    # Timing & Performance
    default_budget_ms: int = Field(default=5000, description="Default time budget")
    max_budget_ms: int = Field(default=30000, description="Maximum allowed budget")
    node_timeout_ms: int = Field(default=2000, description="Default node timeout")
    
    # Concurrency
    max_parallel_nodes: int = Field(default=5, description="Max parallel node execution")
    
    # Rate Limiting
    pubmed_rps: float = Field(default=2.0, description="PubMed requests per second")
    ctgov_rps: float = Field(default=2.0, description="ClinicalTrials.gov requests per second")
    rag_rps: float = Field(default=3.0, description="RAG search requests per second")
    
    # Cache Policy
    default_fetch_policy: str = Field(default="cache_then_network")
    cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")
    
    # Features
    enable_streaming: bool = Field(default=True, description="Enable streaming results")
    enable_partial_results: bool = Field(default=True, description="Return partial results on timeout")
    
    # LangGraph settings
    langgraph: LangGraphConfig = Field(default_factory=LangGraphConfig)
    
    @classmethod
    def from_main_config(cls, config: Config) -> "OrchestratorConfig":
        """Create from main bio-mcp configuration."""
        return cls(
            # Map relevant settings from main config
            default_budget_ms=getattr(config, 'default_timeout_ms', 5000),
            enable_streaming=getattr(config, 'enable_streaming', True),
        )