# Multi-Source Biomedical Data Refactoring Plan

## Overview

This document outlines the refactoring plan to transform the current PubMed-focused Bio-MCP server into a multi-source biomedical research platform supporting PubMed, ClinicalTrials.gov, and future data sources with different update schedules and data models.

## Current Architecture Analysis

**Current Structure (PubMed-focused)**:
```
src/bio_mcp/
├── clients/
│   ├── pubmed_client.py      # PubMed-specific HTTP client
│   ├── weaviate_client.py    # Vector store client (shared)
│   └── database.py           # Database operations (shared)
├── mcp/
│   ├── pubmed_tools.py       # PubMed MCP tools
│   ├── rag_tools.py          # RAG tools (PubMed-specific)
│   └── corpus_tools.py       # Corpus management (PubMed-specific)
├── services/
│   └── services.py           # PubMedService, DocumentService
├── core/
│   ├── embeddings.py         # Embedding logic (shared)
│   └── quality_scoring.py    # PubMed quality metrics
```

**Architecture Issues**:
- PubMed-specific logic scattered across multiple directories
- Tight coupling between shared infrastructure and PubMed specifics
- No clear abstraction for different data sources with varying update patterns
- Difficult to add new sources without modifying existing code

## Target Multi-Source Architecture

**New Structure (Multi-source)**:
```
src/bio_mcp/
├── shared/                   # 🆕 Common infrastructure
│   ├── clients/
│   │   ├── weaviate_client.py
│   │   ├── database.py
│   │   └── http_client.py    # 🆕 Base HTTP client
│   ├── core/
│   │   ├── embeddings.py
│   │   ├── text_processing.py # 🆕 Chunking, normalization
│   │   ├── error_handling.py
│   │   └── quality_base.py   # 🆕 Abstract quality scoring
│   ├── models/
│   │   ├── base_models.py    # 🆕 Abstract base classes
│   │   └── database_models.py # 🆕 Universal document schema
│   ├── services/
│   │   ├── base_service.py   # 🆕 Abstract service class
│   │   ├── document_service.py
│   │   ├── rag_service.py    # 🆕 Source-agnostic RAG
│   │   └── sync_orchestrator.py # 🆕 Multi-source sync
│   └── utils/
│       ├── checkpoints.py    # 🆕 Watermark management
│       └── text_utils.py     # 🆕 Common text processing
├── sources/                  # 🆕 Source-specific implementations
│   ├── pubmed/
│   │   ├── client.py         # PubMed API client
│   │   ├── models.py         # PubMed data models
│   │   ├── service.py        # PubMedService
│   │   ├── tools.py          # MCP tools
│   │   ├── quality.py        # PubMed quality scoring
│   │   ├── sync_strategy.py  # EDAT-based sync
│   │   └── config.py         # PubMed configuration
│   ├── clinicaltrials/       # 🆕 ClinicalTrials.gov
│   │   ├── client.py         # CT.gov API client
│   │   ├── models.py         # Clinical trial models
│   │   ├── service.py        # ClinicalTrialsService
│   │   ├── tools.py          # MCP tools
│   │   ├── quality.py        # Trial quality metrics
│   │   ├── sync_strategy.py  # last_update_posted sync
│   │   └── config.py         # CT.gov configuration
│   └── __init__.py
├── mcp/
│   ├── registry.py           # 🆕 Tool registration system
│   ├── resources.py          # Enhanced with multi-source
│   └── tool_definitions.py   # Enhanced schemas
└── main.py                   # Enhanced with source loading
```

## Abstract Base Classes for Multi-Source Support

### Base Document Model
```python
# shared/models/base_models.py
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from datetime import datetime
from dataclasses import dataclass

@dataclass
class BaseDocument(ABC):
    """Abstract base for all document types across data sources."""
    id: str                          # Universal ID format: {source}:{source_id}
    source_id: str                   # Original ID from source (PMID, NCT ID, etc.)
    source: str                      # Source identifier
    title: str
    abstract: str | None = None
    content: str | None = None       # Full searchable content
    authors: list[str] = None
    publication_date: datetime | None = None
    metadata: dict[str, Any] = None  # Source-specific fields
    quality_score: int = 0           # Normalized 0-100 score
    last_updated: datetime = None    # For sync watermarks
    
    @abstractmethod
    def get_search_content(self) -> str:
        """Return text content for embedding and search."""
        pass
    
    @abstractmethod
    def get_display_title(self) -> str:
        """Return formatted title for display."""
        pass

T = TypeVar('T', bound=BaseDocument)
```

### Base Client Interface
```python
class BaseClient(ABC, Generic[T]):
    """Abstract base for all external API clients."""
    
    @abstractmethod
    async def search(self, query: str, **kwargs) -> list[str]:
        """Return list of document IDs matching query."""
        pass
        
    @abstractmethod
    async def get_document(self, doc_id: str) -> T:
        """Fetch single document by source ID."""
        pass
        
    @abstractmethod
    async def get_documents(self, doc_ids: list[str]) -> list[T]:
        """Fetch multiple documents efficiently."""
        pass
    
    @abstractmethod
    async def get_updates_since(self, timestamp: datetime, limit: int = 100) -> list[T]:
        """Get documents updated since timestamp (for incremental sync)."""
        pass
```

### Base Sync Strategy
```python
class BaseSyncStrategy(ABC):
    """Abstract base for source-specific sync strategies."""
    
    @abstractmethod
    async def get_sync_watermark(self, query_key: str) -> datetime | None:
        """Get last sync timestamp for a query."""
        pass
    
    @abstractmethod
    async def set_sync_watermark(self, query_key: str, timestamp: datetime) -> None:
        """Update sync watermark for a query."""
        pass
    
    @abstractmethod
    async def sync_incremental(self, query: str, query_key: str, limit: int) -> dict:
        """Perform incremental sync based on watermark."""
        pass
```

## Source-Specific Implementations

### PubMed Source (Refactored)
```python
# sources/pubmed/models.py
from dataclasses import dataclass
from datetime import datetime
from ..shared.models.base_models import BaseDocument

@dataclass
class PubMedDocument(BaseDocument):
    """PubMed-specific document model."""
    pmid: str
    journal: str | None = None
    doi: str | None = None
    mesh_terms: list[str] = None
    keywords: list[str] = None
    impact_factor: float | None = None
    citation_count: int = 0
    
    def __post_init__(self):
        self.source = "pubmed"
        self.source_id = self.pmid
        self.id = f"pubmed:{self.pmid}"
    
    def get_search_content(self) -> str:
        parts = [self.title]
        if self.abstract:
            parts.append(self.abstract)
        if self.mesh_terms:
            parts.append(" ".join(self.mesh_terms))
        return " ".join(parts)
    
    def get_display_title(self) -> str:
        journal_info = f" ({self.journal})" if self.journal else ""
        return f"{self.title}{journal_info}"

# sources/pubmed/sync_strategy.py
from datetime import datetime, timedelta
from ..shared.services.base_service import BaseSyncStrategy

class PubMedSyncStrategy(BaseSyncStrategy):
    """EDAT-based incremental sync for PubMed."""
    
    async def sync_incremental(self, query: str, query_key: str, limit: int) -> dict:
        """Sync using EDAT (entry date) watermarks with overlap."""
        last_sync = await self.get_sync_watermark(query_key)
        
        if last_sync:
            # Add 1-day overlap to catch late updates
            start_date = last_sync - timedelta(days=1)
            query_with_date = f"{query} AND {start_date.strftime('%Y/%m/%d')}[EDAT]:{datetime.now().strftime('%Y/%m/%d')}[EDAT]"
        else:
            # First sync - use query as-is
            query_with_date = query
        
        # Perform sync...
        return {"synced": 0, "new": 0, "updated": 0}
```

### ClinicalTrials.gov Source (New)
```python
# sources/clinicaltrials/models.py
from dataclasses import dataclass
from datetime import datetime
from ..shared.models.base_models import BaseDocument

@dataclass 
class ClinicalTrialDocument(BaseDocument):
    """ClinicalTrials.gov document model."""
    nct_id: str
    brief_title: str
    official_title: str | None = None
    brief_summary: str | None = None  
    detailed_description: str | None = None
    study_type: str | None = None     # "Interventional", "Observational"
    phase: str | None = None          # "Phase 1", "Phase 2", etc.
    status: str | None = None         # "Recruiting", "Completed", etc.
    conditions: list[str] = None      # Medical conditions
    interventions: list[str] = None   # Treatments/drugs
    locations: list[dict] = None      # Study locations
    sponsors: list[str] = None        # Study sponsors
    enrollment: int | None = None     # Target participant count
    start_date: datetime | None = None
    completion_date: datetime | None = None
    last_update_posted: datetime | None = None  # For sync watermarks
    
    def __post_init__(self):
        self.source = "clinicaltrials" 
        self.source_id = self.nct_id
        self.id = f"clinicaltrials:{self.nct_id}"
        self.title = self.brief_title
        self.abstract = self.brief_summary
        
    def get_search_content(self) -> str:
        parts = [self.brief_title]
        if self.brief_summary:
            parts.append(self.brief_summary)
        if self.conditions:
            parts.append(" ".join(self.conditions))
        if self.interventions:
            parts.append(" ".join(self.interventions))
        return " ".join(parts)
    
    def get_display_title(self) -> str:
        phase_info = f" ({self.phase})" if self.phase else ""
        status_info = f" [{self.status}]" if self.status else ""
        return f"{self.brief_title}{phase_info}{status_info}"

# sources/clinicaltrials/client.py
from datetime import datetime
from typing import list
from ..shared.models.base_models import BaseClient
from .models import ClinicalTrialDocument

class ClinicalTrialsClient(BaseClient[ClinicalTrialDocument]):
    """Client for ClinicalTrials.gov API v2."""
    
    BASE_URL = "https://clinicaltrials.gov/api/v2/"
    
    async def search(self, query: str, **kwargs) -> list[str]:
        """Search studies using ClinicalTrials.gov API."""
        # Use studies endpoint with query parameter
        # https://clinicaltrials.gov/api/v2/studies?query.term=cancer
        pass
        
    async def get_updates_since(self, timestamp: datetime, limit: int = 100) -> list[ClinicalTrialDocument]:
        """Get trials updated since timestamp using last_update_posted."""
        # https://clinicaltrials.gov/api/v2/studies?filter.lastUpdatePosted.from=2024-01-01
        pass

# sources/clinicaltrials/sync_strategy.py
class ClinicalTrialsSyncStrategy(BaseSyncStrategy):
    """last_update_posted-based sync for ClinicalTrials.gov."""
    
    async def sync_incremental(self, query: str, query_key: str, limit: int) -> dict:
        """Sync using last_update_posted timestamps."""
        last_sync = await self.get_sync_watermark(query_key)
        
        if last_sync:
            # CT.gov allows filtering by last update date
            trials = await self.client.get_updates_since(last_sync, limit)
        else:
            # First sync
            trial_ids = await self.client.search(query, limit=limit)
            trials = await self.client.get_documents(trial_ids)
        
        # Process and store trials...
        return {"synced": len(trials), "new": 0, "updated": 0}
```

## Universal Database Schema

### Multi-Source Document Table
```sql
-- Migration: Transform existing documents table for multi-source
CREATE TABLE documents_universal (
    id VARCHAR(255) PRIMARY KEY,           -- "pubmed:12345", "clinicaltrials:NCT01234"
    source VARCHAR(50) NOT NULL,           -- "pubmed", "clinicaltrials"
    source_id VARCHAR(100) NOT NULL,       -- Original ID (PMID, NCT ID)
    title TEXT NOT NULL,
    abstract TEXT,
    content TEXT,                          -- Full searchable content
    authors JSONB,
    publication_date TIMESTAMP,
    metadata JSONB,                        -- Source-specific fields
    quality_score INTEGER DEFAULT 0,
    last_updated TIMESTAMP,               -- For sync watermarking
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Indexes for multi-source queries
    CONSTRAINT unique_source_doc UNIQUE(source, source_id)
);

CREATE INDEX idx_documents_source ON documents_universal(source);
CREATE INDEX idx_documents_source_date ON documents_universal(source, publication_date);
CREATE INDEX idx_documents_quality_source ON documents_universal(quality_score DESC, source);
CREATE INDEX idx_documents_last_updated ON documents_universal(source, last_updated);

-- Sync watermarks table
CREATE TABLE sync_watermarks (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    query_key VARCHAR(255) NOT NULL,
    last_sync TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_source_query UNIQUE(source, query_key)
);
```

## Multi-Source RAG System

### Source-Agnostic RAG Service
```python
# shared/services/rag_service.py
class MultiSourceRAGService:
    """RAG service supporting multiple biomedical data sources."""
    
    def __init__(self):
        self.weaviate_client = get_weaviate_client()
        self.source_services = {}
        
    def register_source(self, source_name: str, service):
        """Register a data source service."""
        self.source_services[source_name] = service
        
    async def search(
        self, 
        query: str,
        sources: list[str] = None,          # Filter to specific sources
        search_mode: str = "hybrid",        # "vector", "bm25", "hybrid"
        filters: dict = None,               # Cross-source filters
        date_range: dict = None,            # Date filtering
        quality_threshold: int = 50,        # Minimum quality score
        top_k: int = 10
    ) -> dict:
        """Multi-source hybrid search with unified ranking."""
        
        # Build source filter
        if sources:
            source_filter = {"source": {"valueText": sources}}
        else:
            source_filter = {}
        
        # Build date filter
        date_filter = {}
        if date_range:
            if "start" in date_range:
                date_filter["publication_date"] = {"valueDate": f">={date_range['start']}"}
            if "end" in date_range:
                date_filter["publication_date"] = {"valueDate": f"<={date_range['end']}"}
        
        # Combine all filters
        combined_filters = {
            **source_filter,
            **date_filter,
            **(filters or {}),
            "quality_score": {"valueInt": f">={quality_threshold}"}
        }
        
        # Execute search across all sources
        if search_mode == "hybrid":
            results = await self._hybrid_search(query, combined_filters, top_k)
        elif search_mode == "vector":
            results = await self._vector_search(query, combined_filters, top_k)
        elif search_mode == "bm25":
            results = await self._bm25_search(query, combined_filters, top_k)
        
        # Re-rank with cross-source quality normalization
        reranked = await self._rerank_cross_source(results)
        
        return {
            "query": query,
            "sources_searched": sources or list(self.source_services.keys()),
            "search_mode": search_mode,
            "total_results": len(reranked),
            "results": reranked[:top_k]
        }
    
    async def _rerank_cross_source(self, results: list) -> list:
        """Apply cross-source quality normalization and re-ranking."""
        # Normalize quality scores across different source types
        for result in results:
            source = result.get("source")
            if source == "pubmed":
                # PubMed uses citation-based scoring (0-100)
                pass
            elif source == "clinicaltrials":
                # Clinical trials use phase/enrollment-based scoring
                # Boost clinical trials slightly for treatment queries
                result["quality_score"] *= 1.1
        
        # Sort by normalized quality score
        return sorted(results, key=lambda x: x["quality_score"], reverse=True)
```

## MCP Tool Registration System

### Dynamic Multi-Source Tools
```python
# mcp/registry.py
from typing import Dict, Callable
from mcp.types import Tool

class MultiSourceToolRegistry:
    """Registry for MCP tools from multiple data sources."""
    
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.tool_definitions: Dict[str, Tool] = {}
        self.source_services = {}
        
    def register_source_tools(self, source_name: str, tools_module):
        """Auto-register tools from a source module."""
        for attr_name in dir(tools_module):
            if attr_name.endswith('_tool') and callable(getattr(tools_module, attr_name)):
                tool_func = getattr(tools_module, attr_name)
                # Create tool name: {source}.{operation}
                operation = attr_name[:-5]  # Remove '_tool' suffix
                tool_name = f"{source_name}.{operation}"
                self.tools[tool_name] = tool_func
                logger.info(f"Registered tool: {tool_name}")
    
    def register_cross_source_tools(self, tools_module):
        """Register tools that work across multiple sources."""
        for attr_name in dir(tools_module):
            if attr_name.endswith('_tool') and callable(getattr(tools_module, attr_name)):
                tool_func = getattr(tools_module, attr_name)
                tool_name = attr_name[:-5]  # Remove '_tool' suffix
                self.tools[tool_name] = tool_func
                logger.info(f"Registered cross-source tool: {tool_name}")

# Enhanced main.py
from .sources.pubmed import tools as pubmed_tools
from .sources.clinicaltrials import tools as ct_tools
from .mcp import cross_source_tools

async def main():
    registry = MultiSourceToolRegistry()
    
    # Register source-specific tools
    registry.register_source_tools("pubmed", pubmed_tools)
    registry.register_source_tools("clinicaltrials", ct_tools)
    
    # Register cross-source tools (rag.search, corpus.sync, etc.)
    registry.register_cross_source_tools(cross_source_tools)
    
    # Start MCP server
    server = Server("bio-mcp-multi")
    
    for tool_name, tool_func in registry.tools.items():
        server.add_tool(tool_name, tool_func)
```

## Tool Interface Design

### Multi-Source Tool Naming
```python
# Source-specific tools
pubmed.search(query, limit=20, sort_by="relevance")
pubmed.get(pmid) 
pubmed.sync(query, query_key, limit=100)
pubmed.sync_delta(query_key, max_docs=1000)

clinicaltrials.search(query, study_type=None, phase=None)
clinicaltrials.get(nct_id)
clinicaltrials.sync(query, query_key, limit=100) 
clinicaltrials.sync_delta(query_key, max_docs=500)

# Cross-source tools
rag.search(query, sources=["pubmed", "clinicaltrials"], search_mode="hybrid")
rag.get(universal_id)  # "pubmed:12345" or "clinicaltrials:NCT01234"
corpus.sync_all(query_keys, sources=["pubmed", "clinicaltrials"])
corpus.status()  # Show sync status for all sources
```

### Enhanced Multi-Source RAG Tool
```python
async def rag_search_tool(
    query: str,
    sources: list[str] = ["pubmed", "clinicaltrials"],
    search_mode: str = "hybrid",           # "vector", "bm25", "hybrid"  
    filters: dict = None,                  # {"pubmed": {"journal": "Nature"}}
    date_range: dict = None,               # {"start": "2020-01-01", "end": "2024-01-01"}
    quality_threshold: int = 50,           # Minimum quality score
    boost_clinical_trials: bool = False,   # Boost trials for treatment queries
    top_k: int = 10
) -> dict:
    """
    Search across multiple biomedical data sources with unified ranking.
    
    Returns results with source attribution and cross-source quality scores.
    """
    rag_service = MultiSourceRAGService()
    
    # Apply treatment-specific boosting
    if boost_clinical_trials:
        # Boost clinical trials for treatment-related queries
        query_boost = {"clinicaltrials": 1.2}
    else:
        query_boost = {}
    
    results = await rag_service.search(
        query=query,
        sources=sources,
        search_mode=search_mode,
        filters=filters,
        date_range=date_range,
        quality_threshold=quality_threshold,
        top_k=top_k
    )
    
    return results
```

## Configuration Management

### Multi-Source Configuration
```python
# shared/config/multi_source_config.py
from dataclasses import dataclass, field
from .sources.pubmed.config import PubMedConfig
from .sources.clinicaltrials.config import ClinicalTrialsConfig

@dataclass
class MultiSourceConfig:
    """Configuration for all biomedical data sources."""
    
    # Source-specific configurations
    pubmed: PubMedConfig = field(default_factory=PubMedConfig)
    clinicaltrials: ClinicalTrialsConfig = field(default_factory=ClinicalTrialsConfig)
    
    # RAG configuration
    default_sources: list[str] = field(default_factory=lambda: ["pubmed", "clinicaltrials"])
    enable_cross_source_dedup: bool = True
    quality_normalization: bool = True
    
    # Sync configuration
    max_concurrent_syncs: int = 2
    sync_batch_size: int = 100
    default_overlap_days: int = 1
    
    # Search configuration
    default_search_mode: str = "hybrid"
    default_top_k: int = 10
    min_quality_threshold: int = 30

# Configuration YAML files
# config/pubmed_queries.yaml
pubmed_queries:
  cancer_research: "cancer[MeSH] AND research[Title/Abstract]"
  immunotherapy: "immunotherapy[MeSH] AND clinical trial[Publication Type]"
  crispr: "CRISPR[Title/Abstract] AND gene editing[MeSH]"

# config/clinicaltrials_queries.yaml  
clinicaltrials_queries:
  cancer_trials: "cancer AND interventional"
  immunotherapy_trials: "immunotherapy AND phase 2 OR phase 3"
  rare_disease: "rare disease AND recruiting"
```

## Migration Strategy

### Phase 1: Foundation Refactoring (Week 1)
1. **Create directory structure**:
   ```bash
   mkdir -p src/bio_mcp/shared/{clients,core,models,services,utils}
   mkdir -p src/bio_mcp/sources/{pubmed,clinicaltrials}
   ```

2. **Move shared infrastructure**:
   - `clients/weaviate_client.py` → `shared/clients/`
   - `clients/database.py` → `shared/clients/`  
   - `core/embeddings.py` → `shared/core/`
   - `core/error_handling.py` → `shared/core/`

3. **Create base abstractions**:
   - `shared/models/base_models.py`
   - `shared/services/base_service.py`
   - `shared/services/rag_service.py`

### Phase 2: PubMed Extraction (Week 1)
1. **Move PubMed code to source module**:
   - `clients/pubmed_client.py` → `sources/pubmed/client.py`
   - `mcp/pubmed_tools.py` → `sources/pubmed/tools.py`
   - `core/quality_scoring.py` → `sources/pubmed/quality.py`

2. **Create PubMed service wrapper**:
   - `sources/pubmed/service.py`
   - `sources/pubmed/sync_strategy.py`
   - `sources/pubmed/models.py`

### Phase 3: ClinicalTrials Integration (Week 2)
1. **Implement ClinicalTrials.gov client**
2. **Create trial data models and quality scoring**
3. **Implement sync strategy based on last_update_posted**
4. **Create MCP tools for clinical trials**

### Phase 4: Multi-Source RAG (Week 2)
1. **Implement universal database schema**
2. **Create multi-source RAG service**
3. **Implement cross-source search and ranking**
4. **Add source-aware quality normalization**

### Phase 5: Tool Registration & Testing (Week 3)
1. **Implement dynamic tool registration system**
2. **Update main.py with multi-source initialization**  
3. **Comprehensive testing across all sources**
4. **Performance optimization and monitoring**

## Testing Strategy

### Multi-Source Test Structure
```
tests/
├── shared/                    # Shared infrastructure tests
│   ├── test_base_models.py
│   ├── test_rag_service.py
│   ├── test_database.py
│   └── test_sync_orchestrator.py
├── sources/
│   ├── pubmed/
│   │   ├── test_client.py
│   │   ├── test_service.py
│   │   ├── test_sync_strategy.py
│   │   └── test_tools.py
│   └── clinicaltrials/
│       ├── test_client.py
│       ├── test_service.py  
│       ├── test_sync_strategy.py
│       └── test_tools.py
├── integration/
│   ├── test_multi_source_search.py
│   ├── test_cross_source_quality.py
│   └── test_sync_coordination.py
└── e2e/
    ├── test_pubmed_to_ct_workflow.py
    └── test_multi_source_rag.py
```

### Test Coverage Goals
- **Unit Tests**: 95%+ coverage for each source module
- **Integration Tests**: Cross-source functionality
- **E2E Tests**: Complete research workflows
- **Performance Tests**: Multi-source search latency (<300ms)

## Success Metrics

### Refactoring Success Criteria
- ✅ **Backward Compatibility**: All existing PubMed tools work unchanged
- ✅ **Source Isolation**: Each source can be developed independently
- ✅ **Extensibility**: Adding new sources requires <100 lines of integration code
- ✅ **Performance**: Multi-source search <300ms, single-source <200ms  
- ✅ **Quality**: Maintain 100% test pass rate
- ✅ **Cross-Source Search**: Query PubMed + ClinicalTrials with unified ranking

### Implementation Timeline
- **Week 1**: Foundation refactoring + PubMed extraction
- **Week 2**: ClinicalTrials integration + Multi-source RAG
- **Week 3**: Tool registration + Testing + Performance optimization

This refactoring creates a scalable foundation for biomedical research across multiple data sources while preserving all existing PubMed functionality.