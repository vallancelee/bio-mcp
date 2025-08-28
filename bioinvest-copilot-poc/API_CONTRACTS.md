# BioInvest AI Copilot POC - API Contracts

This document defines the complete API contracts between all components in the BioInvest AI Copilot system, including component boundaries, versioning, and error handling.

## Contract Versioning

**Current Version**: v4.0 (M0-M4 Complete)
- **v1.0**: Basic MCP integration
- **v2.0**: Enhanced tool integration (M2) 
- **v3.0**: Advanced state management (M3)
- **v4.0**: Advanced synthesis and checkpoints (M4)

**Versioning Strategy**: Semantic versioning with backward compatibility guarantees.

---

## Component Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React         │────│   FastAPI        │────│   LangGraph     │────│   Bio-MCP       │
│   Frontend      │    │   Backend        │    │   Orchestrator  │    │   Server        │
│                 │    │                  │    │                 │    │                 │
│ • Query Input   │    │ • API Gateway    │    │ • Workflow Mgmt │    │ • Data Sources  │
│ • Real-time UI  │────│ • SSE Streaming  │────│ • State Mgmt    │────│ • Tool Registry │
│ • Results View  │ SSE│ • Orchestration  │    │ • Middleware    │    │ • Quality Ctrl  │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼
   HTTP/WebSocket          JSON/Streaming           Python Classes           JSON-RPC/MCP
```

---

## 1. Frontend ↔ Backend Contract

### Base URL
- **Development**: `http://localhost:8002`
- **API Prefix**: `/api`

### 1.1 Enhanced Query Submission

**POST** `/api/research/query`

#### Request Schema
```typescript
interface EnhancedOrchestrationRequest {
  query: string;
  sources: string[];  // ["pubmed", "clinical_trials", "rag"]
  options: {
    // Basic Options
    max_results_per_source: number;        // Default: 50
    include_synthesis: boolean;            // Default: true
    priority: "speed" | "comprehensive" | "balanced";  // Default: "balanced"
    
    // M3 Advanced State Management
    budget_ms?: number;                    // Execution time budget in milliseconds
    enable_partial_results?: boolean;     // Return partial results on timeout (default: true)
    retry_strategy?: "exponential" | "linear" | "none";  // Default: "exponential"
    parallel_execution?: boolean;          // Enable parallel searches (default: true)
    
    // M4 Synthesis Options  
    citation_format?: "pmid" | "full" | "inline";  // Default: "full"
    quality_threshold?: number;            // Minimum quality score 0-1 (default: 0.5)
    checkpoint_enabled?: boolean;          // Enable session checkpointing (default: true)
  };
}
```

#### Response Schema
```typescript
interface EnhancedOrchestrationResponse {
  query_id: string;
  status: "initiated" | "processing" | "completed" | "failed" | "partial";
  estimated_completion_time: number;
  
  // Standard Progress
  progress: {
    pubmed: "pending" | "processing" | "completed" | "failed";
    clinical_trials: "pending" | "processing" | "completed" | "failed";
    rag: "pending" | "processing" | "completed" | "failed";
  };
  
  // M3 State Management Status
  budget_status?: {
    allocated_ms: number;
    consumed_ms: number;
    remaining_ms: number;
    utilization: number;  // 0.0-1.0
  };
  
  middleware_active?: {
    budget_enforcement: boolean;
    error_recovery: boolean; 
    partial_results_enabled: boolean;
  };
  
  // M4 Synthesis Metadata
  checkpoint_id?: string;                  // Deterministic checkpoint ID
  synthesis_metrics?: {
    citation_count: number;
    quality_score: number;                 // 0.0-1.0
    answer_type: "comprehensive" | "partial" | "minimal" | "empty";
  };
  
  // Stream Information
  stream_url: string;
  created_at: string;
}
```

### 1.2 Advanced Server-Sent Events

**GET** `/api/research/stream/{query_id}`

#### Event Types & Data Schemas

##### Standard Events
```typescript
// Connection established
interface ConnectedEvent {
  event: "connected";
  data: {
    query_id: string;
    timestamp: string;
    capabilities: string[];  // List of enabled features
  };
}

// Query progress update
interface ProgressEvent {
  event: "progress";
  data: {
    query_id: string;
    timestamp: string;
    source: string;
    status: string;
    progress_percent: number;  // 0-100
  };
}
```

##### M3 State Management Events
```typescript
// Budget and middleware status
interface MiddlewareStatusEvent {
  event: "middleware_status";
  data: {
    query_id: string;
    timestamp: string;
    budget?: {
      consumed_ms: number;
      remaining_ms: number;
      in_danger_zone: boolean;  // >80% consumed
    };
    error_recovery?: {
      active_retries: number;
      retry_strategy: string;
      last_error?: string;
    };
    partial_results?: {
      available: boolean;
      sources_with_data: string[];
    };
  };
}

// Retry attempt notification
interface RetryAttemptEvent {
  event: "retry_attempt";
  data: {
    query_id: string;
    timestamp: string;
    node: string;
    attempt: number;
    max_attempts: number;
    delay_ms: number;
    error: string;
  };
}

// Partial results available
interface PartialResultsEvent {
  event: "partial_results";
  data: {
    query_id: string;
    timestamp: string;
    reason: "timeout" | "error" | "budget_exhausted";
    completion_percentage: number;  // 0.0-1.0
    available_sources: string[];
    total_results: number;
  };
}
```

##### M4 Synthesis Events
```typescript
// Synthesis progress
interface SynthesisProgressEvent {
  event: "synthesis_progress";
  data: {
    query_id: string;
    timestamp: string;
    stage: "citation_extraction" | "quality_scoring" | "template_rendering";
    progress_percent: number;
    citations_found?: number;
    quality_score?: number;
  };
}

// Synthesis completed
interface SynthesisCompletedEvent {
  event: "synthesis_completed";
  data: {
    query_id: string;
    timestamp: string;
    checkpoint_id: string;
    synthesis_time_ms: number;
    metrics: {
      total_sources: number;
      successful_sources: number;
      citation_count: number;
      quality_score: number;
      answer_type: string;
    };
    answer: string;  // Formatted markdown answer
  };
}
```

### 1.3 New Advanced Endpoints

#### GET /api/langgraph/capabilities
```typescript
interface CapabilitiesResponse {
  orchestration: {
    version: string;          // "4.0" (M0-M4 complete)
    features: string[];       // ["parallel_execution", "budget_enforcement", ...]
    nodes: string[];         // Available LangGraph nodes
    middleware: string[];    // Available middleware types
  };
  performance: {
    parallel_speedup: number;      // Expected speedup factor
    middleware_overhead: number;   // Overhead multiplier
    average_latencies: {
      pubmed_search: number;
      clinical_trials: number;
      rag_search: number;
      synthesis: number;
    };
  };
  limits: {
    max_budget_ms: number;         // 30000
    max_parallel_nodes: number;    // 5
    max_retry_attempts: number;    // 3
  };
}
```

#### GET /api/langgraph/middleware-status
```typescript
interface MiddlewareStatusResponse {
  active_middleware: {
    budget_enforcement: {
      enabled: boolean;
      default_budget_ms: number;
      active_queries: number;
    };
    error_recovery: {
      enabled: boolean;
      retry_strategy: string;
      success_rate: number;
    };
    partial_results: {
      enabled: boolean;
      extraction_rate: number;  // Percentage of timeouts with useful partial data
    };
  };
  performance_metrics: {
    average_execution_time: number;
    timeout_rate: number;
    retry_rate: number;
    partial_results_rate: number;
  };
}
```

---

## 2. Backend ↔ LangGraph Orchestrator Contract

### 2.1 Orchestrator Configuration
```python
@dataclass
class OrchestratorConfig:
    # Basic Configuration
    default_budget_ms: int = 5000
    max_budget_ms: int = 30000
    node_timeout_ms: int = 2000
    max_parallel_nodes: int = 5
    
    # M3 State Management
    enable_budget_enforcement: bool = True
    enable_error_recovery: bool = True
    enable_partial_results: bool = True
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0
    
    # M4 Synthesis
    checkpoint_enabled: bool = True
    citation_extraction: bool = True
    quality_scoring: bool = True
```

### 2.2 State Object Contract
```python
class OrchestratorState(TypedDict):
    # Core State
    query: str
    config: OrchestratorConfig
    frame: dict[str, Any]
    routing_decision: str
    
    # Result Storage
    pubmed_results: Optional[dict[str, Any]]
    ctgov_results: Optional[dict[str, Any]]
    rag_results: Optional[dict[str, Any]]
    
    # M3 State Management
    budget_tracker: Optional[BudgetTracker]
    error_recovery: Optional[dict[str, Any]]
    partial_results: Optional[dict[str, Any]]
    
    # M4 Synthesis
    checkpoint_id: Optional[str]
    synthesis_metrics: Optional[dict[str, Any]]
    
    # Execution Metadata
    tool_calls_made: list[str]
    cache_hits: dict[str, bool]
    latencies: dict[str, float]
    node_path: list[str]
    messages: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    
    # Output
    answer: Optional[str]
    session_id: Optional[str]
```

### 2.3 Node Factory Contract
```python
from typing import Protocol

class NodeFactory(Protocol):
    def __call__(self, config: OrchestratorConfig, db_manager: Any = None) -> Callable: ...

class NodeRegistration:
    name: str                    # e.g., "pubmed_search", "parallel_search"
    factory: NodeFactory         # Factory function to create node
    dependencies: list[str]      # Other nodes this depends on
    metadata: dict[str, Any]     # Version, type, capabilities, middleware support

class BaseNodeRegistry(Protocol):
    def register(self, registration: NodeRegistration) -> None: ...
    def get_factory(self, name: str) -> NodeFactory: ...
    def list_nodes(self) -> list[str]: ...
```

### 2.4 Middleware Contract
```python
class MiddlewareWrapper(Protocol):
    """Contract for middleware wrappers around LangGraph nodes."""
    
    def __call__(self, state: OrchestratorState) -> dict[str, Any]: ...
    def __getattr__(self, name: str) -> Any: ...  # LangGraph delegation
    
    # Middleware-specific methods
    @property
    def middleware_type(self) -> str: ...  # "budget", "error_recovery", etc.
    
    @property  
    def is_active(self) -> bool: ...       # Whether middleware is currently active

# Budget Enforcement Middleware
class BudgetAwareNodeWrapper(MiddlewareWrapper):
    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        # Budget checking, timeout enforcement, partial results extraction
        ...

# Error Recovery Middleware  
class ErrorRecoveryWrapper(MiddlewareWrapper):
    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        # Retry logic, exponential backoff, graceful degradation
        ...
```

---

## 3. LangGraph Orchestrator ↔ Bio-MCP Contract

### 3.1 JSON-RPC Request/Response
```python
# Request to Bio-MCP Server
class MCPRequest:
    jsonrpc: str = "2.0"
    id: int
    method: str = "tools/call"
    params: dict[str, Any]

# Example tool calls with enhanced parameters
ENHANCED_TOOL_CALLS = {
    "pubmed.sync.incremental": {
        "query": str,
        "limit": int,
        "quality_threshold": float,  # M4: Quality filtering
        "include_metadata": bool     # M4: Enhanced metadata
    },
    "rag.search": {
        "query": str,
        "top_k": int,
        "search_mode": str,
        "alpha": float,
        "rerank_by_quality": bool,   # M2/M4: Quality reranking
        "return_chunks": bool,
        "enhance_query": bool,
        "filters": dict
    },
    "clinicaltrials.sync": {
        "query": str,
        "limit": int, 
        "quality_scoring": bool,     # M4: Quality scoring
        "filter_low_quality": bool   # M4: Quality filtering
    }
}

# Response from Bio-MCP Server
class MCPResponse:
    jsonrpc: str = "2.0"
    id: int
    result: dict[str, Any]
    error?: dict[str, Any]
```

### 3.2 Tool Result Schemas

#### Enhanced PubMed Results (M4 Quality Scoring)
```python
class PubMedResult:
    pmid: str
    title: str
    authors: list[str]
    journal: str
    year: int
    abstract: str
    
    # M4 Quality Enhancements
    quality_score: float         # 0.0-1.0 composite quality
    citation_count: Optional[int]
    journal_impact_factor: Optional[float]
    investment_relevance: float  # Bio-investment specific relevance
    
    # M4 Citation Support
    formatted_citation: str      # Ready-to-use citation
    citation_style: str         # "pmid", "full", "inline"
```

#### Enhanced Clinical Trials Results (M4 Quality Scoring)
```python
class ClinicalTrialResult:
    nct_id: str
    title: str
    status: str
    phase: str
    conditions: list[str]
    interventions: list[str]
    
    # M4 Quality Enhancements
    quality_score: float         # 0.0-1.0 composite quality
    completion_probability: Optional[float]
    investment_risk_score: float
    competitive_threat_level: str
    
    # M4 Citation Support
    formatted_citation: str
    study_url: str
```

---

## 4. Error Handling Contracts

### 4.1 Standard Error Response
```typescript
interface StandardError {
  error: {
    code: string;              // "BUDGET_EXHAUSTED", "RETRY_FAILED", etc.
    message: string;
    details?: any;
    timestamp: string;
    
    // M3 Error Recovery Context
    recovery_attempted?: boolean;
    retry_count?: number;
    fallback_applied?: string;
    
    // M4 Quality Context  
    partial_synthesis?: boolean;
    checkpoint_saved?: string;
  };
}
```

### 4.2 Error Classification
```python
class ErrorType(Enum):
    # Network/API Errors (Recoverable)
    RATE_LIMIT = "rate_limit"
    NETWORK_TIMEOUT = "network_timeout"
    SERVICE_UNAVAILABLE = "service_unavailable"
    
    # System Errors (Potentially Recoverable)
    DATABASE_ERROR = "database_error"
    
    # Validation Errors (Non-recoverable)
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    
    # M3 Budget/State Errors
    BUDGET_EXHAUSTED = "budget_exhausted"
    PARTIAL_RESULTS_ONLY = "partial_results_only"
    
    # M4 Synthesis Errors
    SYNTHESIS_FAILED = "synthesis_failed"
    CHECKPOINT_ERROR = "checkpoint_error"

class RecoveryAction(Enum):
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    SKIP_AND_CONTINUE = "skip_and_continue"
    PARTIAL_RESULTS = "partial_results"
    FAIL_PERMANENTLY = "fail_permanently"
```

---

## 5. Performance Contracts

### 5.1 Latency Guarantees
```python
PERFORMANCE_TARGETS = {
    # Basic Operations
    "health_check": 100,           # ms
    "query_acceptance": 500,       # ms
    "first_result_streaming": 2000, # ms
    
    # M3 Advanced Operations
    "parallel_search": 0.6,        # Ratio of sequential time
    "budget_enforcement": 1.2,     # Overhead multiplier
    "error_recovery": 2.0,         # Max retry delay multiplier
    
    # M4 Synthesis
    "citation_extraction": 500,    # ms
    "quality_scoring": 300,        # ms
    "synthesis_generation": 1000,  # ms
    "checkpoint_creation": 200,    # ms
}
```

### 5.2 Availability Guarantees
```python
AVAILABILITY_TARGETS = {
    "overall_uptime": 0.99,        # 99% uptime
    "error_recovery_rate": 0.95,   # 95% of errors recovered
    "partial_results_rate": 0.80,  # 80% of timeouts yield partial results
    "synthesis_success_rate": 0.98, # 98% of queries get synthesis
}
```

---

## 6. Backward Compatibility

### 6.1 Version Support Matrix
| API Version | Supported Features | Deprecation Date |
|-------------|-------------------|------------------|
| v4.0 | Full M0-M4 features | Current |
| v3.0 | M0-M3 features | 2025-06-01 |
| v2.0 | M0-M2 features | 2025-03-01 |
| v1.0 | Basic features | **DEPRECATED** |

### 6.2 Breaking Changes Policy
- **Major versions**: Can introduce breaking changes with 6-month notice
- **Minor versions**: Only additive changes, fully backward compatible
- **Patch versions**: Bug fixes only, no API changes

### 6.3 Migration Guide
```typescript
// v3.0 to v4.0 Migration
interface v3Request {
  query: string;
  sources: string[];
  options: BasicOptions;
}

interface v4Request extends v3Request {
  options: BasicOptions & {
    // New M4 synthesis options - all optional
    citation_format?: "pmid" | "full" | "inline";
    quality_threshold?: number;
    checkpoint_enabled?: boolean;
  };
}
```

---

## 7. Security Considerations

### 7.1 Rate Limiting
```python
RATE_LIMITS = {
    "per_client": 100,    # requests per minute
    "per_query": 1,       # concurrent queries per client
    "budget_max": 30000,  # max budget per query (ms)
}
```

### 7.2 Data Privacy
- No PII stored in checkpoints
- Query logs anonymized after 24 hours
- Citations include only public identifiers (PMIDs, NCT IDs)

---

This contract ensures clear boundaries between all components while showcasing the advanced capabilities of the M0-M4 implementation. All components must implement these contracts for proper integration.