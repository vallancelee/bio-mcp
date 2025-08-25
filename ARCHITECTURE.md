# Bio-MCP Software Architecture Document

## Executive Summary

Bio-MCP is a biomedical Model Context Protocol (MCP) server that provides AI assistants with curated access to PubMed literature for biotech and pharmaceutical investment research. The system implements a sophisticated RAG (Retrieval-Augmented Generation) architecture combining traditional database storage with vector search capabilities, optimized for biomedical content discovery and analysis.

**Version**: 0.1.0  
**Last Updated**: August 2025  
**Target Audience**: Software architects, senior developers, and technical leads

---

## 1. Project Vision & Goals

### Primary Goals
1. **Investment Research Focus**: Curate PubMed abstracts specifically for biotech/pharma investment analysis
2. **AI Assistant Integration**: Provide structured access via MCP protocol for seamless AI integration
3. **Research Reproducibility**: Enable checkpoint management for audit trails and due diligence
4. **Real-time Monitoring**: Track new publications and research pipeline updates
5. **Production Quality**: Enterprise-ready deployment with comprehensive monitoring

### Target Users
- **Investment Analysts** researching biotech companies
- **Portfolio Managers** conducting due diligence
- **AI Systems** providing biotech investment insights
- **Research Firms** building biotech intelligence platforms

### Success Metrics
- Research query response time < 200ms
- 99.9% uptime for production deployments
- Comprehensive test coverage (>90%)
- Support for 100K+ PubMed documents
- Real-time incremental updates

---

## 2. System Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Assistant Layer                       │
│                   (Claude, GPT, Custom AIs)                    │
└─────────────────────┬───────────────────────────────────────────┘
                      │ MCP Protocol
┌─────────────────────▼───────────────────────────────────────────┐
│                     Bio-MCP Server                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │ MCP Tools   │  │ Resources   │  │ HTTP API    │           │
│  │ - PubMed    │  │ - Status    │  │ - Health    │           │
│  │ - RAG       │  │ - Metrics   │  │ - Jobs      │           │
│  │ - Corpus    │  │ - Logs      │  │ - Admin     │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                  Business Logic Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │ PubMed      │  │ RAG Tools   │  │ Corpus      │           │
│  │ Service     │  │ Manager     │  │ Management  │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                   Data Layer                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │ PostgreSQL  │  │ Weaviate    │  │ PubMed API  │           │
│  │ (Metadata)  │  │ (Vectors)   │  │ (Source)    │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

1. **MCP Interface Layer**: Protocol-compliant tools and resources
2. **Business Logic Layer**: Domain-specific services and managers
3. **Data Layer**: Multiple storage systems for different data types
4. **External Integration Layer**: PubMed API and other biomedical sources

---

## 3. Technology Stack & Dependencies

### Core Technologies
- **Language**: Python 3.12+
- **Framework**: MCP (Model Context Protocol) 1.0+
- **Package Manager**: UV (modern Python package management)
- **Async Runtime**: asyncio with uvloop optimization

### Database Technologies
- **Metadata Storage**: PostgreSQL 14+ with asyncpg driver
- **Vector Database**: Weaviate 1.24+ with hybrid search
- **Caching**: Built-in Python caching (no Redis dependency)

### AI/ML Technologies
- **Embeddings**: OpenAI text-embedding-ada-002
- **Vector Search**: Weaviate hybrid (BM25 + semantic)
- **Text Processing**: spaCy for biomedical NLP
- **Chunking**: Custom section-aware chunking (250-350 tokens)

### Infrastructure
- **Containerization**: Docker with multi-stage builds
- **Orchestration**: Docker Compose for development
- **Process Management**: Structured logging with structlog
- **Monitoring**: Custom metrics with Prometheus compatibility

### Key Dependencies
```python
# Core MCP and database
mcp>=1.0.0
weaviate-client>=4.0.0
asyncpg>=0.29.0
sqlalchemy>=2.0.0

# AI/ML stack  
openai>=1.0.0
transformers>=4.35.0
spacy>=3.8.0
tiktoken>=0.5.0

# Biomedical processing
biopython>=1.80
xmltodict>=0.13.0

# HTTP and utilities
fastapi>=0.116.1
httpx>=0.27.0
pydantic>=2.0.0
structlog>=25.4.0
```

---

## 4. Core Design Decisions & Rationale

### 4.1 Architecture Patterns

**Pattern: Hybrid Storage Architecture**
- **Metadata in PostgreSQL**: Fast queries, ACID compliance, mature tooling
- **Vectors in Weaviate**: Optimized vector operations, hybrid search, scalability
- **Rationale**: Each storage system optimized for its data type and access patterns

**Pattern: MCP-First Design**
- **Protocol Compliance**: Native MCP tools and resources
- **AI Integration**: Seamless connection to AI assistants
- **Rationale**: Future-proofs integration with emerging AI systems

**Pattern: Domain-Driven Design**
- **Clear Boundaries**: PubMed, RAG, Corpus domains
- **Service Layer**: Business logic isolated from infrastructure
- **Rationale**: Maintainability and testability at scale

### 4.2 Data Processing Decisions

**Section-Aware Chunking**
- **Target Size**: 250-350 tokens with 50-token overlap
- **Section Detection**: Regex-based parsing of PubMed abstracts
- **Rationale**: Preserves biomedical context while fitting LLM context windows

**Quality-Based Ranking**
- **Multi-Factor Scoring**: Study design, recency, journal impact, human studies
- **Investment Focus**: Boosts clinical trial and biotech-relevant content  
- **Rationale**: Surfaces most valuable research for investment decisions

**Incremental Updates**
- **EDAT Watermarks**: Uses PubMed's Entry Date for incremental sync
- **Idempotent Operations**: Safe to replay sync operations
- **Rationale**: Efficient real-time updates without full reprocessing

### 4.3 Performance Decisions

**Async-First Architecture**
- **I/O Bound Operations**: Database, API calls, vector operations
- **Concurrent Processing**: Multiple documents processed simultaneously
- **Rationale**: Maximizes throughput for I/O heavy workloads

**Connection Pooling**
- **PostgreSQL**: Managed connection pools via asyncpg
- **Weaviate**: HTTP connection reuse with httpx
- **Rationale**: Reduces connection overhead and improves response times

---

## 5. Domain Model & Data Flow

### 5.1 Core Domain Models

```python
# Document Model (Primary entity)
@dataclass
class Document:
    uid: str                    # e.g., "pubmed:12345678"
    source: str                 # "pubmed"
    source_id: str             # PMID
    title: Optional[str]        # Article title
    text: str                  # Abstract content
    published_at: Optional[datetime]
    authors: Optional[List[str]]
    identifiers: Dict[str, str] # DOI, PMCID, etc.
    detail: Dict[str, Any]      # Source-specific metadata

# Chunk Model (Processing unit)
@dataclass 
class Chunk:
    chunk_id: str              # "s0", "s1" (section-based)
    uuid: str                  # UUIDv5 deterministic ID
    parent_uid: str            # Links to Document
    text: str                  # Chunk content
    section: Optional[str]     # Background/Methods/Results/Conclusions
    tokens: Optional[int]      # Token count
    published_at: Optional[datetime]
    meta: Dict[str, Any]       # Chunker metadata
```

### 5.2 Data Flow Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   PubMed    │───▶│ Normalization│───▶│  Document   │
│   E-Utils   │    │   Service    │    │   Storage   │
│    API      │    │              │    │ PostgreSQL  │
└─────────────┘    └─────────────┘    └─────────────┘
                                              │
┌─────────────┐    ┌─────────────┐    ┌──────▼──────┐
│ RAG Search  │◀───│   Weaviate  │◀───│   Chunking  │
│   Results   │    │   Vector    │    │   Service   │
│             │    │   Database  │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 5.3 Processing Pipeline

1. **Ingestion**: PubMed XML → Normalized Document model
2. **Quality Scoring**: Multi-factor algorithm based on publication metadata
3. **Chunking**: Section-aware splitting with overlap and token limits
4. **Embedding**: OpenAI text-embedding-ada-002 generation
5. **Storage**: Parallel write to PostgreSQL (metadata) and Weaviate (vectors)
6. **Search**: Hybrid retrieval with quality-based reranking

---

## 6. API Contracts & Tool Catalog

### 6.1 MCP Tools (Public Interface)

**Literature Search & Analysis**
```
pubmed.search        - Search PubMed with advanced filters
pubmed.get           - Retrieve document by PMID
pubmed.sync          - Batch sync documents to database  
pubmed.sync.incremental - Incremental updates via EDAT watermarks
```

**Intelligence Search**
```
rag.search           - Hybrid BM25 + vector search with quality ranking
  Parameters:
  - query: string (required)
  - top_k: int (1-50, default 10)
  - search_mode: enum [hybrid, semantic, bm25]
  - alpha: float (0.0-1.0, hybrid weighting)
  - enhance_query: boolean (biomedical term expansion)
  - return_chunks: boolean (chunks vs documents)
  - rerank_by_quality: boolean (quality boost)
  - filters: object (date ranges, journals)

rag.get             - Retrieve document with full context
```

**Corpus Management**
```
corpus.checkpoint.create  - Create reproducible research snapshots
corpus.checkpoint.get     - Retrieve checkpoint details
corpus.checkpoint.list    - Browse checkpoints with pagination
corpus.checkpoint.delete  - Remove checkpoints permanently
```

**System Monitoring**
```
ping                - Connectivity test
MCP Resources       - Real-time corpus health and metrics
```

### 6.2 HTTP API (Administrative)

```
GET /health         - System health status
GET /ready          - Readiness probe
GET /metrics        - Prometheus metrics
POST /jobs          - Job management
GET /status         - Detailed system status
```

---

## 7. Development Practices & Standards

### 7.1 Code Organization

```
src/bio_mcp/
├── main.py              # MCP server entry point
├── mcp/                 # MCP protocol implementation
│   ├── tool_definitions.py  # Tool schemas
│   ├── rag_tools.py         # RAG implementations
│   └── corpus_tools.py      # Corpus management
├── services/            # Business logic layer
│   ├── document_chunk_service.py
│   └── reingest_service.py
├── sources/             # External data sources
│   └── pubmed/             # PubMed integration
├── shared/              # Common utilities
│   ├── clients/            # Database/API clients
│   └── core/               # Core utilities
└── config/              # Configuration management
```

### 7.2 Coding Standards

**Type Safety**
- Strict MyPy configuration with no type: ignore
- Pydantic models for data validation
- Type hints required for all public APIs

**Error Handling**
- Custom exception hierarchy with error codes
- Structured error responses via error_boundary decorator
- Comprehensive logging with correlation IDs

**Testing Standards**
- TDD methodology with test-first development
- Minimum 90% code coverage requirement
- Integration tests with testcontainers (real databases)
- Contract tests for all MCP tools

### 7.3 Quality Gates

```bash
# Pre-commit hooks
uv run ruff check       # Linting (fast)
uv run mypy .          # Type checking
uv run pytest         # Test execution
```

**Commit Standards**
- Conventional commits (feat:, fix:, docs:, test:)
- Each commit must pass all quality gates
- PR reviews required for all changes

---

## 8. Testing Strategy

### 8.1 Test Architecture

```
tests/
├── unit/                 # Fast, isolated tests
│   ├── test_chunking.py     # Business logic
│   └── test_quality.py      # Algorithms
├── integration/          # Real system tests
│   ├── database/           # PostgreSQL via testcontainers  
│   ├── test_rag_quality.py # End-to-end RAG pipeline (Docker Compose Weaviate)
│   └── conftest.py         # Test fixtures and populated data
└── e2e/                  # Full system tests
    └── test_mcp_protocol.py # MCP compliance
```

### 8.2 Testing Principles

**Zero Mocking for Integration Tests**
- Real PostgreSQL via testcontainers
- Real Weaviate via Docker Compose (shared development environment)
- Real OpenAI API calls (with test API keys)
- Rationale: Catches integration issues that mocks miss

**Fixture-Based Test Data**
- Standardized biomedical test documents
- Session-scoped fixtures for performance
- Cleanup after each test session
- Rationale: Consistent, reliable test data

**Performance Testing** 
- Search response time validation (<200ms target)
- Memory usage monitoring during bulk operations
- Concurrent request testing
- Rationale: Ensures production performance requirements

### 8.3 Current Test Coverage

- **Total Tests**: 45+ tests across all levels
- **Coverage**: ~95% (target: >90%)
- **Integration**: 8 RAG quality tests with real data
- **Unit**: 25+ focused business logic tests
- **Contract**: All MCP tools validated against schemas

---

## 9. Deployment Architecture

### 9.1 Container Architecture

**Multi-Stage Docker Build**
```dockerfile
# Stage 1: Dependencies
FROM python:3.12-slim as deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Stage 2: Application  
FROM python:3.12-slim as app
COPY --from=deps /app/.venv /app/.venv
COPY src/ /app/src/
EXPOSE 8080
CMD ["uv", "run", "bio-mcp"]
```

**Docker Compose Stack**
```yaml
services:
  bio-mcp:
    build: .
    environment:
      - BIO_MCP_DATABASE_URL=postgresql://postgres:password@db:5432/bio_mcp
      - BIO_MCP_WEAVIATE_URL=http://weaviate:8080
  
  db:
    image: postgres:14
    environment:
      POSTGRES_DB: bio_mcp
  
  weaviate:
    image: semitechnologies/weaviate:1.24.0
    environment:
      ENABLE_MODULES: 'text2vec-transformers'
```

### 9.2 Production Configuration

**Environment Variables**
```bash
# Core service
BIO_MCP_DATABASE_URL=postgresql://user:pass@host:5432/db
BIO_MCP_WEAVIATE_URL=http://weaviate:8080
BIO_MCP_OPENAI_API_KEY=sk-...

# Monitoring & observability
BIO_MCP_LOG_LEVEL=INFO
BIO_MCP_JSON_LOGS=true
BIO_MCP_ENABLE_METRICS=true

# Performance tuning
BIO_MCP_MAX_CONNECTIONS=20
BIO_MCP_CONNECTION_TIMEOUT=30
BIO_MCP_BATCH_SIZE=100
```

### 9.3 Scaling Considerations

**Horizontal Scaling**
- Stateless application servers
- Shared database and vector store
- Load balancer with health checks

**Database Scaling** 
- PostgreSQL read replicas for metadata queries
- Weaviate clustering for vector operations
- Connection pooling and query optimization

---

## 10. Performance & Scalability

### 10.1 Performance Targets

| Operation | Target | Current |
|-----------|---------|---------|
| RAG Search | <200ms | ~150ms |
| Document Retrieval | <50ms | ~30ms |
| Bulk Sync | >100 docs/min | ~150 docs/min |
| Concurrent Users | 50+ | Tested to 100 |

### 10.2 Optimization Strategies

**Search Optimization**
- Weaviate index optimization for biomedical content
- Query result caching for popular searches  
- Batch processing for multiple queries
- Section boosting for Results/Conclusions

**Database Optimization**
- PostgreSQL query optimization with proper indexes
- Connection pooling (20 connections per instance)
- Async query processing
- Prepared statement reuse

**Memory Management**
- Streaming processing for large documents
- Chunk-based embeddings processing
- Python GC tuning for long-running processes

### 10.3 Monitoring & Metrics

**Application Metrics**
```python
# Key performance indicators
search_latency_histogram      # Search response times
document_processing_counter   # Documents processed
embedding_generation_timer    # Embedding performance
database_connection_gauge     # Connection pool usage
```

**Infrastructure Metrics**
- CPU, memory, disk utilization
- Database connection counts
- Weaviate query performance
- Network I/O patterns

---

## 11. Security Considerations

### 11.1 Security Architecture

**API Security**
- API key authentication for external access
- Rate limiting per client
- Input validation and sanitization
- SQL injection prevention via parameterized queries

**Data Security** 
- Encrypted connections (TLS) for all external communications
- Database credentials via environment variables
- No sensitive data in logs or error messages
- PII handling compliance for research data

**Infrastructure Security**
- Container security scanning
- Minimal base images (Python 3.12-slim)
- Non-root container execution
- Network segmentation between services

### 11.2 Compliance

**Data Handling**
- PubMed data usage complies with NCBI terms
- No personal health information (PHI) storage
- Research data anonymization where applicable
- GDPR compliance for European users

---

## 12. Monitoring & Observability

### 12.1 Logging Strategy

**Structured Logging**
```python
logger.info(
    "RAG search completed",
    query=query,
    results_count=len(results),
    search_time_ms=elapsed_time,
    correlation_id=trace_id
)
```

**Log Levels**
- ERROR: System failures, exceptions
- WARN: Performance issues, deprecated usage
- INFO: Business events, user actions  
- DEBUG: Detailed technical information

### 12.2 Health Monitoring

**Health Check Endpoints**
```python
/health     # Basic liveness probe
/ready      # Readiness probe with dependency checks
/metrics    # Prometheus-compatible metrics
```

**Dependency Health**
- PostgreSQL connection verification
- Weaviate cluster status
- OpenAI API accessibility
- PubMed E-utilities availability

### 12.3 Alerting Strategy

**Critical Alerts**
- Service downtime (>1 minute)
- Database connection failures
- Search performance degradation (>500ms)
- High error rates (>5%)

**Warning Alerts**
- Memory usage >80%
- Disk space <20%  
- API rate limit approaching
- Test failures in CI/CD

---

## 13. Known Technical Debt & Issues

### 13.1 Current Technical Debt

**Configuration Management**
- Environment variable configuration needs centralization
- Configuration validation at startup
- Configuration hot-reloading capability

**Testing Infrastructure**  
- Need more comprehensive performance tests
- Load testing framework implementation
- Chaos engineering for resilience testing

**Documentation**
- API documentation automation
- Deployment runbooks
- Operational procedures documentation

### 13.2 Planned Improvements

**Phase 5 Improvements**
- Company intelligence mapping (biotech stock tickers)
- Competitive analysis tools
- Market catalyst detection algorithms
- Enhanced biomedical NLP processing

**Infrastructure Improvements**
- Kubernetes deployment manifests
- Automated CI/CD pipeline improvements
- Enhanced monitoring dashboards
- Performance optimization profiling

---

## 14. Future Roadmap & Direction

### 14.1 Near-term (Next 3 months)

**Phase 5: Company Intelligence**
- Link research to specific biotech companies
- Stock ticker mapping for public companies
- Pipeline tracking for drug development stages
- Competitive intelligence across companies

**Infrastructure Maturity**
- Kubernetes deployment support
- Advanced monitoring and alerting
- Automated performance testing
- Security audit and hardening

### 14.2 Medium-term (3-12 months)

**Phase 6: Investment Signals** 
- Automated risk assessment from research trends
- Investment opportunity detection algorithms
- Portfolio management system integration
- Regulatory milestone tracking (FDA approvals)

**AI/ML Enhancements**
- Advanced biomedical NLP models
- Custom embedding models for biotech content
- Multi-modal data processing (patents, clinical data)
- Real-time sentiment analysis of research trends

### 14.3 Long-term Vision

**Enterprise Platform**
- Multi-tenant architecture
- White-label deployment options
- Advanced analytics and reporting
- Integration with major investment platforms

**AI-Native Features**
- Automated research synthesis
- Predictive investment modeling
- Natural language query processing
- Autonomous due diligence workflows

---

## 15. Quick Start Guide for New Developers

### 15.1 Development Setup

```bash
# 1. Clone and setup
git clone https://github.com/vallancelee/bio-mcp.git
cd bio-mcp

# 2. Environment setup
uv sync --dev                    # Install dependencies
cp .env.example .env            # Configure environment
docker-compose up -d            # Start dependencies

# 3. Development workflow
uv run bio-mcp                  # Start MCP server
uv run pytest                  # Run tests
uv run ruff check              # Lint code
```

### 15.2 Key Development Commands

```bash
# Testing
uv run pytest tests/unit/                 # Fast unit tests
uv run pytest tests/integration/          # Integration tests
uv run pytest --cov=src/bio_mcp          # Coverage report

# Code quality
uv run ruff check --fix                   # Auto-fix linting
uv run mypy .                            # Type checking
uv run python scripts/coverage.py        # Detailed coverage

# MCP testing  
uv run python clients/cli.py list-tools  # Test MCP server
uv run python clients/cli.py rag.search "diabetes treatment"
```

### 15.3 Architecture Deep Dive

**Essential Reading Order**
1. `contracts.md` - API contracts and tool specifications
2. `src/bio_mcp/main.py` - MCP server entry point
3. `src/bio_mcp/mcp/rag_tools.py` - Core search functionality
4. `tests/integration/test_rag_quality.py` - End-to-end examples
5. `src/bio_mcp/services/document_chunk_service.py` - Data processing

**Key Concepts to Understand**
- MCP protocol implementation patterns
- Hybrid search architecture (BM25 + vector)
- Section-aware document chunking
- Quality-based result ranking
- Async/await patterns throughout codebase

### 15.4 Common Development Tasks

**Adding a New MCP Tool**
1. Define schema in `src/bio_mcp/mcp/tool_definitions.py`
2. Implement handler in appropriate `*_tools.py` file
3. Register in `src/bio_mcp/main.py`
4. Add tests in `tests/unit/` and `tests/integration/`
5. Update `contracts.md` with API documentation

**Modifying Search Behavior**
1. Update `DocumentChunkService` in `src/bio_mcp/services/`
2. Modify quality scoring in `src/bio_mcp/sources/pubmed/quality.py`
3. Add integration tests in `tests/integration/test_rag_quality.py`
4. Validate performance against targets

**Database Schema Changes**
1. Create migration in `src/bio_mcp/shared/clients/migrations.py`
2. Update models in `src/bio_mcp/shared/models/`
3. Test migration with testcontainers
4. Update API contracts if needed

---

## Conclusion

Bio-MCP represents a sophisticated biomedical intelligence platform built on modern Python architecture patterns. The system successfully combines traditional database storage with advanced vector search capabilities, providing AI assistants with powerful tools for biotech investment research.

Key architectural strengths include:
- **Protocol-First Design**: Native MCP compliance for seamless AI integration
- **Hybrid Storage**: Optimized data placement across PostgreSQL and Weaviate
- **Quality-Focused**: Biomedical content optimization with investment relevance
- **Production-Ready**: Comprehensive testing, monitoring, and deployment practices

The architecture is designed for extensibility and scalability, with clear domain boundaries and well-defined interfaces that support both current requirements and future enhancements in biomedical AI applications.

For questions or contributions, see the project repository at https://github.com/vallancelee/bio-mcp.
