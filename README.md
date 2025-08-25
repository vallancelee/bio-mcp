# Bio-MCP: Biomedical Intelligence for Investment Research

**A Model Context Protocol (MCP) server that provides AI assistants with curated access to biomedical literature focused on biotech and pharmaceutical investment research.**

## 🧬 What is Bio-MCP?

Bio-MCP maintains a **curated corpus of PubMed abstracts** specifically selected for biotech and pharmaceutical investment analysis. It provides AI assistants with intelligent access to:

- **Investment-Relevant Literature**: Curated PubMed abstracts focused on drug development, clinical trials, and biotech innovations
- **Market Intelligence**: Research data scoped to publicly traded biotech companies and emerging therapies
- **Due Diligence Support**: Structured access to scientific literature for investment decision-making
- **Real-time Research Monitoring**: Track new publications relevant to biotech investment opportunities

## 🎯 Who is this for?

- **Investment Analysts** researching biotech and pharmaceutical companies
- **Financial AI Systems** providing biotech investment insights
- **Portfolio Managers** conducting due diligence on life sciences investments
- **Research Firms** building biotech-focused intelligence platforms

## 🏗️ High-Level Architecture

### Curated Corpus Focus

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Investment AI   │    │  Analyst Tools  │    │ Portfolio Mgmt  │
│   Assistant     │    │                 │    │    Platform     │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                          ┌─────────────┐
                          │  Bio-MCP    │ ← MCP Protocol Interface
                          │   Server    │
                          └─────┬───────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
    ┌─────────▼───────┐ ┌───────▼───────┐ ┌───────▼───────┐
    │ Curated Corpus  │ │ Investment    │ │ Intelligence  │
    │ Management      │ │ Checkpoints   │ │ Search        │
    │                 │ │               │ │               │
    │ • Biotech Focus │ │ • Research    │ │ • Semantic    │
    │ • Stock-Relevant│ │   Snapshots   │ │   Discovery   │
    │ • Clinical Data │ │ • Due Diligence│ │ • Relevance   │
    │ • Drug Pipeline │ │   Archives    │ │   Ranking     │
    └─────────────────┘ └───────────────┘ └───────────────┘
```

### Investment-Focused Capabilities

1. **📈 Biotech Corpus Curation**
   - **Targeted Content**: PubMed abstracts filtered for biotech/pharma investment relevance
   - **Company Focus**: Literature mapped to publicly traded biotech companies
   - **Pipeline Intelligence**: Clinical trial data, drug development milestones
   - **Market Timing**: Real-time updates on investment-relevant research

2. **🔬 Research Intelligence** 
   - **Due Diligence Snapshots**: Versioned research corpus for investment analysis
   - **Competitive Intelligence**: Track competitor research and development
   - **Risk Assessment**: Scientific literature analysis for investment risk evaluation

3. **🤖 AI Investment Support**
   - **Smart Queries**: Investment-focused search across curated biomedical content
   - **Relevance Scoring**: Rank research by investment significance
   - **Trend Analysis**: Identify emerging biotech investment opportunities

4. **🏢 Investment-Grade Features**
   - **Reproducible Research**: Checkpoint management for audit trails
   - **Real-time Monitoring**: Track corpus health and research pipeline updates
   - **Scalable Architecture**: Enterprise deployment for investment firms

## 💼 Use Cases

### 1. **Biotech Investment Analysis**
```
AI Assistant Query: "What are the latest developments in Moderna's mRNA technology?"
→ Bio-MCP searches curated corpus for Moderna-relevant research
→ Returns ranked abstracts with investment implications
→ Provides context on competitive landscape and pipeline status
```

### 2. **Due Diligence Research**
```
Portfolio Manager: "Create research snapshot for Q3 biotech review"
→ Bio-MCP creates versioned checkpoint of current corpus state
→ Generates investment-focused literature summary
→ Provides reproducible research baseline for decision tracking
```

### 3. **Market Intelligence**
```
Research Firm: "Monitor emerging CAR-T therapy companies"
→ Bio-MCP tracks new publications in CAR-T space
→ Identifies potential investment targets from research activity
→ Alerts on significant clinical trial results or breakthroughs
```

## 🎯 Corpus Scope

The Bio-MCP corpus is specifically curated for:

- **Public Biotech Companies**: Research relevant to NYSE/NASDAQ-listed biotech firms
- **Drug Development Pipeline**: Clinical trials, FDA approvals, regulatory milestones
- **Therapeutic Areas**: High-value treatment areas with investment potential
- **Competitive Intelligence**: Research landscape analysis for investment positioning
- **Market Catalysts**: Scientific developments that could impact stock performance

## 🚀 Quick Start

### For Investment Analysts

```bash
# 1. Set up Bio-MCP with investment focus
git clone https://github.com/vallancelee/bio-mcp.git
cd bio-mcp && make dev-setup

# 2. Configure for biotech research
export BIO_MCP_CORPUS_FOCUS=biotech_investment
export BIO_MCP_COMPANY_TRACKING=true

# 3. Start the server
make run

# 4. Query investment-relevant research
# Use your AI assistant with Bio-MCP integration:
# "Search for recent Gilead clinical trial results"
# "Create checkpoint for current CRISPR research landscape"
```

### For AI Developers

```python
# Example: Integrating Bio-MCP with your AI system
import mcp

# Connect to Bio-MCP server
client = mcp.connect("bio-mcp://localhost:3000")

# Investment-focused queries
results = client.call_tool("pubmed.search", {
    "term": "biotech IPO drug development",
    "limit": 10
})

# Create research snapshots
checkpoint = client.call_tool("corpus.checkpoint.create", {
    "checkpoint_id": "q4_2024_biotech_review",
    "name": "Q4 2024 Biotech Investment Analysis",
    "description": "Research corpus for quarterly biotech review"
})
```

### For Portfolio Managers

```bash
# 1. Deploy Bio-MCP in production
make docker-build && make docker-deploy

# 2. Set up monitoring for investment research
make monitoring-setup

# 3. Configure company tracking
# Add companies to watch list for automatic research monitoring

# 4. Generate due diligence reports
# Use Bio-MCP to create reproducible research snapshots
# for investment committee presentations
```

## 🔧 Available Tools

### Literature Search & Analysis
- **`pubmed.search`**: Search PubMed for documents with advanced filters
- **`pubmed.get`**: Retrieve specific research papers by PMID
- **`pubmed.sync`**: Batch sync documents to database
- **`pubmed.sync.incremental`**: Incremental updates using EDAT watermarks

### Corpus Management
- **`corpus.checkpoint.create`**: Create research snapshots for reproducibility
- **`corpus.checkpoint.get`**: Retrieve checkpoint details by ID
- **`corpus.checkpoint.list`**: Browse available snapshots with pagination
- **`corpus.checkpoint.delete`**: Delete checkpoints permanently

### Intelligence Search
- **`rag.search`**: Advanced hybrid search (BM25 + vector similarity) with quality ranking
- **`rag.get`**: Retrieve documents with full context and metadata

### System Monitoring
- **`ping`**: Simple connectivity test
- **MCP Resources**: Real-time corpus health and metrics
- **Health Checks**: Investment-grade monitoring

## 🛠️ Technical Setup

### Prerequisites
- Python 3.12+
- [UV package manager](https://docs.astral.sh/uv/)
- Docker (optional, for production deployment)
- PostgreSQL (for corpus management)
- Weaviate (for semantic search)

### Installation

```bash
# Clone and setup
git clone https://github.com/vallancelee/bio-mcp.git
cd bio-mcp

# Development environment
make dev-setup

# Production deployment
make docker-up && make deploy
```

### Configuration

Configure for investment research via environment variables:

```bash
# Investment Research Settings
export BIO_MCP_CORPUS_FOCUS=biotech_investment
export BIO_MCP_COMPANY_TRACKING=true
export BIO_MCP_MARKET_FOCUS=nasdaq_biotech

# Database & Search
export BIO_MCP_DATABASE_URL=postgresql://localhost:5433/bio_mcp
export BIO_MCP_WEAVIATE_URL=http://localhost:8080

# API Access
export BIO_MCP_PUBMED_API_KEY=your_ncbi_key
export BIO_MCP_OPENAI_API_KEY=your_openai_key

# Monitoring
export BIO_MCP_LOG_LEVEL=INFO
export BIO_MCP_JSON_LOGS=true
```

### Project Structure

```
bio-mcp/
├── src/bio_mcp/          # Core application
│   ├── main.py           # MCP server implementation
│   ├── clients/          # External service integrations
│   │   ├── database.py   # Corpus storage & checkpoints
│   │   ├── pubmed_client.py  # PubMed integration
│   │   └── weaviate_client.py  # Vector search
│   ├── services/         # Business logic
│   │   └── services.py   # Investment research orchestration
│   ├── mcp/              # MCP protocol tools
│   │   ├── pubmed_tools.py   # Literature search tools
│   │   ├── corpus_tools.py   # Checkpoint management
│   │   ├── rag_tools.py      # Intelligence search
│   │   └── resources.py      # Real-time monitoring
│   └── core/             # Domain logic
├── tests/                # Comprehensive test suite (39 tests)
├── docker-compose.yml    # Development environment
└── Dockerfile           # Production container
```

## 🧪 Testing

Comprehensive test coverage for investment-grade reliability:

```bash
# Full test suite (39 tests covering all functionality)
make test-all

# Investment research workflow tests
make test-corpus        # Corpus management (14 tests)
make test-incremental   # Real-time updates (8 tests)  
make test-resources     # Monitoring (17 tests)

# Production readiness
make test-integration   # Docker & deployment
make test-performance   # Load testing
```

## 📊 Monitoring & Observability

### Health Monitoring

```bash
# Check system health
curl http://localhost:3000/health

# Response: Investment-grade health metrics
{
  "status": "healthy",
  "corpus_stats": {
    "total_documents": "15,432",
    "companies_tracked": "847",
    "last_update": "2024-08-19T10:30:00Z"
  },
  "investment_metrics": {
    "active_checkpoints": 12,
    "recent_updates": 156,
    "pipeline_coverage": "94%"
  }
}
```

### Real-time Resources

Bio-MCP exposes real-time data through MCP resources:

- **`bio-mcp://corpus/status`**: Current corpus statistics
- **`bio-mcp://corpus/checkpoints`**: Available research snapshots  
- **`bio-mcp://sync/recent`**: Latest research updates
- **`bio-mcp://system/health`**: Overall system status

### Logging

Investment-focused structured logging:

```json
{
  "@timestamp": "2024-08-19T10:30:00Z",
  "level": "INFO", 
  "message": "Investment research query completed",
  "query": "Moderna mRNA pipeline",
  "results_count": 47,
  "companies_mentioned": ["MRNA", "BNTX", "CureVac"],
  "investment_relevance_score": 0.89
}
```

## 📈 Investment Research Roadmap

### ✅ Phase 4B: Advanced Corpus Management (Complete)
- [x] **Curated Corpus**: PubMed abstracts focused on biotech investment
- [x] **Research Checkpoints**: Versioned snapshots for due diligence
- [x] **Incremental Updates**: Real-time research monitoring with EDAT watermarks
- [x] **MCP Resources**: Live monitoring of corpus health and research activity
- [x] **Production Ready**: 39 comprehensive tests, type checking, enterprise monitoring

### 🔄 Phase 5: Company Intelligence (Next)
- [ ] **Company Mapping**: Link research to specific biotech stock tickers
- [ ] **Pipeline Tracking**: Automated monitoring of drug development stages  
- [ ] **Competitive Analysis**: Cross-company research comparison tools
- [ ] **Market Catalyst Detection**: Alert system for investment-relevant research

### 📋 Phase 6: Investment Signals (Future)
- [ ] **Risk Scoring**: Automated investment risk assessment from research trends
- [ ] **Opportunity Detection**: AI-powered identification of emerging investment themes
- [ ] **Portfolio Integration**: Direct connection to portfolio management systems
- [ ] **Regulatory Intelligence**: FDA approval tracking and regulatory milestone monitoring

## 🤝 Contributing

We welcome contributions focused on investment research applications:

1. **Fork** the repository
2. **Create** feature branch: `git checkout -b feature/investment-intelligence`
3. **Test** thoroughly: `make test-all` (ensure all 39 tests pass)
4. **Commit** with clear message: `git commit -m 'Add biotech company mapping'`
5. **Push** and create Pull Request

### Priority Areas
- **Company Research Mapping**: Link literature to stock tickers
- **Investment Relevance Scoring**: Improve research ranking for investment decisions
- **Market Intelligence**: Add competitive analysis and market timing features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/vallancelee/bio-mcp/issues)
- **Investment Focus**: Questions about biotech investment research applications
- **Technical Support**: Development and deployment assistance
- **Feature Requests**: Investment research tool suggestions

---

**Bio-MCP** - Intelligent biomedical research infrastructure for investment analysis 📈🧬🚀

*Empowering AI assistants with curated biotech intelligence for smarter investment decisions*