# BioInvest AI Copilot - Proof of Concept

A proof-of-concept UI that demonstrates end-to-end integration with the Bio-MCP backend, showcasing intelligent biotech investment research workflows.

## Overview

This POC demonstrates the core research workflow of the BioInvest AI Copilot:

1. **Natural Language Query**: Enter research questions in plain English
2. **Bio-MCP Orchestration**: Automatically searches PubMed, ClinicalTrials.gov, and internal RAG
3. **Real-time Streaming**: Watch results populate live as they're found
4. **AI Synthesis**: Get intelligent insights and competitive analysis
5. **Interactive Visualization**: Explore results through charts and filters

## Demo Scenarios

### 🔬 Competitive Analysis
**Query**: "What are the competitive risks for Novo Nordisk's GLP-1 pipeline?"
- Real-time search across biomedical literature
- Clinical trial comparisons and competitive threats
- AI-generated risk assessment and recommendations

### 📊 Clinical Trial Prediction
**Query**: "Predict success probability for Biogen's Alzheimer's Phase 3 trial"
- Historical trial analysis and precedent matching
- Risk factor identification and impact scoring
- Success probability with confidence intervals

### 💰 Investment Opportunity Discovery
**Query**: "Emerging biotech companies in CAR-T cell therapy"
- Company discovery and pipeline analysis
- Market opportunity sizing and competitive positioning
- Investment attractiveness scoring

## Architecture & Component Interactions

### High-Level System Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BioInvest AI Copilot POC                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  Frontend Layer (React/TypeScript)                                         │
│  ┌─────────────────┐    HTTP/SSE    ┌──────────────────┐                  │
│  │   React UI      │◄───────────────►│ FastAPI Backend  │                  │
│  │   Port 5173     │                 │   Port 8002      │                  │
│  └─────────────────┘                 └──────────────────┘                  │
├─────────────────────────────────────────┬───────────────────────────────────┤
│  Application Layer                      │                                   │
│                                         ▼                                   │
│                               ┌─────────────────┐                          │
│                               │  Bio-MCP Server │                          │
│                               │     (stdio)     │                          │
│                               └─────────────────┘                          │
├─────────────────────────────────────────┬───────────────────────────────────┤
│  Data Layer (Docker Containers)        │                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │   PostgreSQL    │  │    Weaviate     │  │     MinIO       │            │
│  │   Port 5433     │  │   Port 8080     │  │  Ports 9000/1   │            │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Component Interaction Flow

#### **Query Submission & Processing**
```
[User Types Query] 
       ↓
1. React QueryBuilder Component
   • Validates input
   • Builds request payload
   • Shows loading state
       ↓ POST /api/research/query
2. FastAPI Backend (/api/research/query endpoint)
   • Generates query_id 
   • Creates background task
   • Returns SSE stream URL
   • Stores query in active_queries dict
       ↓ subprocess.Popen()
3. Bio-MCP Server Process
   • Receives JSON-RPC request via stdin
   • Routes to appropriate tools (pubmed.search, clinicaltrials.search, rag.search)
   • Executes searches in parallel
       ↓ SQL/HTTP queries
4. Data Sources
   • PostgreSQL: Document metadata, sync watermarks
   • Weaviate: Vector similarity search
   • External APIs: PubMed, ClinicalTrials.gov (simulated in POC)
       ↓ Results aggregation
5. Bio-MCP Server Response
   • Collects all source results
   • Returns structured JSON via stdout
       ↓ JSON parsing
6. FastAPI Backend Processing
   • Receives Bio-MCP results
   • Triggers AI Synthesis Service
   • Broadcasts events via SSE
       ↓ Server-Sent Events
7. React Frontend Updates
   • EventSource receives SSE messages
   • Updates UI components in real-time
   • Shows progress, partial results, final synthesis
```

#### **Real-Time Streaming Architecture**
```
FastAPI Backend                React Frontend
┌─────────────────┐           ┌─────────────────┐
│ Query Processor │           │ useStreamingHook│
│       │         │           │       │         │
│       ▼         │           │       ▼         │
│ Background Task │◄──────────┤ EventSource API │
│       │         │    SSE    │       │         │
│       ▼         │◄──────────┤       ▼         │
│ Event Emitter   │  Events   │ State Updates   │
│       │         │           │       │         │
│       ▼         │           │       ▼         │
│ SSE Endpoint    │           │ UI Components   │
└─────────────────┘           └─────────────────┘

Event Types Streamed:
• source_started     → Show "Starting PubMed search..."
• source_completed   → Update "PubMed: 15 results found"
• source_failed      → Show error message
• synthesis_started  → Show "Generating AI insights..."
• synthesis_completed→ Display full synthesis results
• query_completed    → Mark query as finished
```

### Component Responsibility Matrix

| Component | Responsibilities | Dependencies | Outputs |
|-----------|-----------------|--------------|---------|
| **React Frontend** | UI rendering, user interaction, SSE consumption | FastAPI Backend (port 8002) | Browser display, user events |
| **FastAPI Backend** | API routing, query orchestration, SSE streaming | Bio-MCP Server (subprocess) | HTTP responses, SSE events |
| **Bio-MCP Server** | Tool execution, data source integration | PostgreSQL, Weaviate | JSON-RPC responses |
| **PostgreSQL** | Document storage, metadata persistence | None | SQL query results |
| **Weaviate** | Vector search, semantic similarity | Transformers model | Search results |
| **MinIO** | Object storage (future use) | None | S3-compatible storage |
| **Transformers** | Local embedding generation | None | Vector embeddings |

### Process Communication Protocols

#### **Frontend ↔ Backend (HTTP/SSE)**
```
HTTP POST /api/research/query
{
  "query": "string",
  "sources": ["pubmed", "clinical_trials", "rag"],
  "options": {
    "max_results_per_source": 50,
    "include_synthesis": true,
    "priority": "balanced"
  }
}
Response: { "query_id": "uuid", "stream_url": "/api/research/stream/uuid" }

SSE GET /api/research/stream/{query_id}
event: source_started
data: {"source": "pubmed", "timestamp": "2024-01-01T00:00:00Z"}

event: source_completed  
data: {"source": "pubmed", "results_count": 15, "processing_time_ms": 2000}

event: synthesis_completed
data: {"insights_count": 5, "competitive_analysis": {...}}
```

#### **Backend ↔ Bio-MCP (JSON-RPC over stdio)**
```
Request (via stdin):
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "pubmed.search",
    "arguments": {"query": "GLP-1", "limit": 50}
  }
}

Response (via stdout):
{
  "jsonrpc": "2.0", 
  "id": 1,
  "result": {
    "content": [{
      "type": "text",
      "text": "{\"results\": [...], \"total_results\": 15}"
    }]
  }
}
```

#### **Bio-MCP ↔ Data Sources (SQL/HTTP)**
```
PostgreSQL Queries:
• SELECT * FROM pubmed_documents WHERE title ILIKE '%GLP-1%'
• INSERT INTO sync_watermarks (query_key, last_edat) VALUES (...)

Weaviate Queries:  
• Hybrid search combining BM25 + vector similarity
• Filter by metadata (date ranges, journals, etc.)

External API Calls (simulated in POC):
• PubMed E-utilities API for literature search
• ClinicalTrials.gov API for trial data
```

## 🚀 Quick Start

From the project root directory:

```bash
# 1. Setup development environment
make poc-dev

# 2. Start all services (PostgreSQL, Weaviate, Bio-MCP, Backend)
make poc-up

# 3. Start frontend (in a new terminal)
make poc-frontend
```

Open [http://localhost:5173](http://localhost:5173) to access the BioInvest AI Copilot interface.

## 🛠️ Development Commands & Component Activation

### Stage-by-Stage Component Activation

#### **Stage 1: `make poc-dev` - Environment Setup**
**Components Active:** None (setup only)
**What Happens:**
- Creates `logs/` and `data/` directories
- Installs Python dependencies via `uv sync --dev`
- Sets up POC backend dependencies via `uv sync` in backend/
- Installs frontend Node.js dependencies via `npm install`

**Result:** Ready development environment with all dependencies installed

---

#### **Stage 2: `make poc-up` - Core Services Launch**
**Components Active:**
```
🐳 Docker Infrastructure:
  ├── PostgreSQL (port 5433) - Database for Bio-MCP
  ├── Weaviate (port 8080) - Vector search engine
  ├── MinIO (port 9000/9001) - S3-compatible storage
  └── Transformers (internal) - Local embedding model

🐍 Bio-MCP Server (background process):
  ├── MCP Protocol Handler - Stdio-based JSON-RPC
  ├── Database Client - PostgreSQL connection
  ├── Tool Registry - pubmed.*, clinicaltrials.*, rag.*, corpus.*
  └── Logging - Output to logs/bio-mcp.log

🚀 FastAPI Backend (port 8002, background process):
  ├── REST API Server - /api/research/* endpoints
  ├── Bio-MCP Client - Subprocess communication
  ├── SSE Streaming - Real-time event broadcasting
  ├── AI Synthesis Service - Simulated GPT-4 analysis
  └── Logging - Output to logs/poc-backend.log
```

**Component Connections:**
```
PostgreSQL ←→ Bio-MCP Server ←→ FastAPI Backend
     ↕              ↕               ↕
  Weaviate    Tool Execution    Process Manager
                    ↕
               Query Results
```

**Health Check Results After `poc-up`:**
- ✅ PostgreSQL ready (port 5433)
- ✅ Weaviate ready (port 8080) 
- ✅ MinIO ready (ports 9000/9001)
- ✅ Bio-MCP Server running (PID tracked)
- ✅ POC Backend API ready (port 8002)

---

#### **Stage 3: `make poc-frontend` - UI Launch**
**Components Active:** All previous + React Frontend
```
⚛️ React Frontend (port 5173):
  ├── Vite Dev Server - Hot module replacement
  ├── API Client - Axios HTTP client to port 8002
  ├── SSE Client - EventSource for streaming
  ├── UI Components - Query builder, results display
  └── State Management - TanStack Query
```

**Complete Data Flow:**
```
User Input (Browser) 
    ↓
React UI (port 5173)
    ↓ HTTP POST /api/research/query
FastAPI Backend (port 8002)
    ↓ Subprocess call
Bio-MCP Server (stdio)
    ↓ Database queries
PostgreSQL (port 5433) + Weaviate (port 8080)
    ↓ Results return
Bio-MCP Server → FastAPI Backend
    ↓ SSE streaming
React UI (real-time updates)
    ↓ 
User sees live results
```

---

### Command Reference with Component Details

| Command | Active Components | Network Ports | Process Management |
|---------|------------------|---------------|-------------------|
| `make poc-dev` | None | None | Dependency installation only |
| `make poc-up` | PostgreSQL, Weaviate, MinIO, Bio-MCP, Backend | 5433, 8080, 9000/9001, 8002 | Background processes with PID tracking |
| `make poc-frontend` | All above + React | All above + 5173 | Foreground Vite dev server |
| `make poc-backend` | Backend only | 8002 | Foreground FastAPI with auto-reload |
| `make poc-status` | Checker only | None | Process health verification |
| `make poc-logs` | Log aggregator | None | Tail log files |
| `make poc-test` | All services | All ports | E2E functionality testing |
| `make poc-demo` | All + auto-browser | All ports | Full stack + browser automation |
| `make poc-down` | None (stops all) | Releases all ports | Graceful process termination |
| `make poc-reset` | None (cleanup) | Releases all ports | Data deletion + process cleanup |

### Manual Setup (Alternative)

If you prefer manual setup (requires UV package manager):

1. **Setup the environment:**
```bash
cd /Users/vallancelee/git/bio-mcp/bioinvest-copilot-poc
```

2. **Start infrastructure services:**
```bash
cd .. && make up  # Starts PostgreSQL, Weaviate, MinIO
```

3. **Start Bio-MCP server:**
```bash
cd /Users/vallancelee/git/bio-mcp
uv run bio-mcp
```

4. **Start the backend:**
```bash
cd bioinvest-copilot-poc/backend
uv sync --no-install-project
uv run python main.py
```

5. **Start the frontend:**
```bash
cd bioinvest-copilot-poc/frontend
npm install
npm run dev
```

## API Endpoints

### Research API

**Submit Query:**
```http
POST /api/research/query
Content-Type: application/json

{
  "query": "GLP-1 competitive landscape for Novo Nordisk",
  "sources": ["pubmed", "clinical_trials", "rag"],
  "max_results": 50,
  "analysis_options": {
    "include_competitive_analysis": true,
    "include_risk_assessment": true,
    "generate_synthesis": true
  }
}
```

**Stream Results:**
```http
GET /api/research/stream/{query_id}
Accept: text/event-stream

# Returns Server-Sent Events:
# event: progress
# event: partial_result
# event: synthesis
# event: completed
```

**Get Synthesis:**
```http
GET /api/research/synthesis/{query_id}

{
  "summary": "AI-generated research summary",
  "key_insights": ["Insight 1", "Insight 2"],
  "risk_assessment": {...},
  "recommendations": [...]
}
```

## Technology Stack

### Backend
- **FastAPI**: High-performance API framework
- **LangGraph**: Intelligent query orchestration and routing
- **Bio-MCP Client**: Integration with biomedical data sources
- **Server-Sent Events**: Real-time result streaming
- **OpenAI/Anthropic**: AI-powered synthesis and analysis
- **Pydantic**: Data validation and serialization
- **UV**: Fast Python package manager (10-100x faster than pip)

### Frontend
- **React 18**: Modern UI framework with TypeScript
- **Vite**: Fast build tooling and development server
- **Tailwind CSS**: Utility-first CSS framework
- **shadcn/ui**: Beautiful and accessible component library
- **TanStack Query**: Data fetching and caching
- **Recharts**: Data visualization and charting
- **EventSource API**: SSE client for real-time updates

## Project Structure

```
bioinvest-copilot-poc/
├── backend/                 # FastAPI orchestrator service
│   ├── src/
│   │   ├── api/            # API route handlers
│   │   ├── orchestrator/   # Bio-MCP integration
│   │   ├── models/         # Pydantic data models
│   │   └── services/       # Business logic services
│   ├── main.py            # Application entry point
│   └── requirements.txt   # Python dependencies
├── frontend/               # React application
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── hooks/         # Custom React hooks
│   │   ├── services/      # API client services
│   │   ├── types/         # TypeScript type definitions
│   │   └── styles/        # CSS and styling
│   ├── package.json       # Node.js dependencies
│   └── vite.config.ts     # Vite configuration
├── docker-compose.yml     # Docker development setup
├── .env.example          # Environment variable template
└── README.md             # This file
```

## Key Features Demonstrated

### 🔍 **Intelligent Query Processing**
- Natural language understanding with entity extraction
- Automatic query optimization and source routing
- Real-time query validation and suggestions

### 📡 **Real-time Data Streaming**
- Live results streaming via Server-Sent Events
- Progressive result loading with status updates
- Connection resilience with automatic reconnection

### 🤖 **AI-Powered Analysis**
- Competitive landscape analysis
- Risk assessment and factor identification
- Investment opportunity scoring
- Natural language synthesis of findings

### 📊 **Interactive Visualizations**
- Dynamic charts and graphs for trends
- Interactive filters and result exploration
- Citation tracking and source verification
- Export capabilities for further analysis

## Environment Variables

Create `.env` files in both `backend/` and `frontend/` directories:

**Backend `.env`:**
```bash
BIO_MCP_URL=http://localhost:8000
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
CORS_ORIGINS=http://localhost:5173
LOG_LEVEL=INFO
```

**Frontend `.env`:**
```bash
VITE_API_BASE_URL=http://localhost:8002
VITE_ENABLE_DEBUG=true
```

## Development Workflow

### Testing a Research Query

1. **Start all services** (Bio-MCP, Backend, Frontend)
2. **Open the application** at http://localhost:5173
3. **Enter a research query** like:
   - "What are the competitive risks for Novo Nordisk's GLP-1 pipeline?"
   - "Predict success for CAR-T cell therapy trials in 2024"
   - "Find emerging biotech companies in gene therapy"
4. **Watch real-time results** stream from multiple sources
5. **Explore the synthesis** and interactive visualizations
6. **Verify citations** and source accuracy

### Monitoring and Debugging

- **Backend logs**: Check FastAPI console for orchestration details
- **Frontend dev tools**: Use browser developer tools for UI debugging
- **Bio-MCP logs**: Monitor Bio-MCP server for data source interactions
- **Network requests**: Inspect SSE connections and API calls

## Performance Expectations

- **Initial Response**: <2 seconds for query acceptance
- **First Results**: <5 seconds for initial PubMed/ClinicalTrials data
- **Complete Analysis**: <30 seconds for full synthesis
- **Real-time Updates**: <100ms latency for streaming updates

## Limitations (POC Scope)

This POC focuses on demonstrating core functionality. Production features not included:
- User authentication and authorization
- Data persistence and caching
- Advanced portfolio management
- Team collaboration features
- Enterprise security and compliance
- Comprehensive error handling and recovery

## Next Steps

After validating the POC:
1. **Expand data sources** (FDA, patents, financial data)
2. **Add user management** and authentication
3. **Implement caching** and performance optimization
4. **Build collaboration** features
5. **Add portfolio** management capabilities
6. **Deploy to staging** environment for user testing

## 🚨 Troubleshooting & Component Dependencies

### Component Health Verification

Use `make poc-status` to check the health of each component:

```bash
$ make poc-status

Infrastructure Services:
  ✅ PostgreSQL (healthy)      # Port 5433 responding
  ✅ Weaviate (healthy)        # Port 8080 responding  
  ✅ MinIO (healthy)           # Ports 9000/9001 responding

Application Services:
  ✅ Bio-MCP Server (PID: 1234)  # Process running, logs active
  ✅ POC Backend (PID: 5678)     # FastAPI server responding

Service Health:
  ✅ POC Backend Health         # GET /health returns 200
  ✅ Weaviate Ready            # Vector search operational
```

### Common Issues & Component Dependencies

#### **Frontend Won't Load (Port 5173 Unreachable)**
**Root Cause:** React dev server not started or crashed
```bash
# Check if Vite is running
lsof -i :5173

# Restart frontend
make poc-frontend

# Check frontend logs in terminal
```
**Dependencies:** None (frontend can run standalone)

---

#### **API Calls Fail (Backend Unreachable)**
**Root Cause:** FastAPI backend not running or port 8002 blocked
```bash
# Test backend directly
curl http://localhost:8002/health

# Check if process is running
make poc-status

# Restart backend
cd bioinvest-copilot-poc/backend
uv run python main.py
```
**Dependencies:** Bio-MCP Server (for tool calls)

---

#### **SSE Stream Connection Fails**
**Root Cause:** EventSource can't establish connection
```bash
# Test SSE endpoint directly
curl -H "Accept: text/event-stream" http://localhost:8002/api/research/stream/test-id

# Check browser developer tools Network tab
# Look for EventSource connection errors
```
**Component Chain:** React EventSource → FastAPI SSE endpoint → Query processing
**Fix:** Ensure CORS is configured for http://localhost:5173

---

#### **Query Fails to Process (Bio-MCP Integration Issue)**
**Root Cause:** Bio-MCP server not running or subprocess communication failed
```bash
# Test Bio-MCP directly
uv run python clients/cli.py ping --message "test"

# Check Bio-MCP logs
make poc-logs | grep bio-mcp

# Verify subprocess communication
ps aux | grep bio-mcp
```
**Component Chain:** FastAPI subprocess → Bio-MCP stdin/stdout → Tool execution
**Fix:** Restart Bio-MCP server: `make poc-down && make poc-up`

---

#### **Database Connection Failures**
**Root Cause:** PostgreSQL container not running or connection refused
```bash
# Check PostgreSQL container
docker ps | grep postgres

# Test connection directly
psql -h localhost -p 5433 -U postgres -d postgres

# Restart database
docker-compose restart postgres
```
**Component Chain:** Bio-MCP Server → PostgreSQL (port 5433)
**Impact:** Document storage, sync watermarks fail

---

#### **Vector Search Failures**
**Root Cause:** Weaviate not responding or schema issues
```bash
# Check Weaviate health
curl http://localhost:8080/v1/.well-known/ready

# Check collections
curl http://localhost:8080/v1/meta

# Restart Weaviate
docker-compose restart weaviate
```
**Component Chain:** Bio-MCP RAG tools → Weaviate (port 8080)
**Impact:** Semantic search, RAG queries fail

---

### Startup Dependency Order

Components must start in specific order due to dependencies:

```bash
1. Infrastructure (make poc-up starts these automatically):
   PostgreSQL (5433) → Weaviate (8080) → MinIO (9000/9001)
   
2. Application Layer:
   Bio-MCP Server (depends on PostgreSQL + Weaviate)
   
3. API Layer:
   FastAPI Backend (depends on Bio-MCP Server)
   
4. Presentation Layer:
   React Frontend (depends on FastAPI Backend)
```

**Critical Path:** PostgreSQL + Weaviate → Bio-MCP → FastAPI → React

### Log File Locations

```bash
# Application logs
logs/bio-mcp.log          # Bio-MCP server output
logs/poc-backend.log      # FastAPI backend output  
logs/frontend.log         # React dev server output (if using poc-demo)

# Docker container logs
docker-compose logs postgres    # PostgreSQL logs
docker-compose logs weaviate    # Weaviate logs
docker-compose logs minio       # MinIO logs

# View all logs
make poc-logs-follow
```

### Process Management

Components are managed as follows:

| Component | Management | PID Tracking | Auto-restart |
|-----------|------------|--------------|--------------|
| PostgreSQL | Docker Compose | Container ID | Yes (Docker) |
| Weaviate | Docker Compose | Container ID | Yes (Docker) |
| Bio-MCP | Background Process | .bio-mcp.pid | No |
| Backend | Background Process | .poc-backend.pid | No |
| Frontend | Foreground Process | Terminal PID | No |

```bash
# Kill individual processes
kill $(cat .bio-mcp.pid)      # Stop Bio-MCP
kill $(cat .poc-backend.pid)  # Stop Backend

# Restart everything cleanly
make poc-down && make poc-up
```

### Performance Debugging

If queries are slow, check each component:

```bash
# 1. Check database performance
docker stats bio-mcp-postgres

# 2. Check Bio-MCP tool execution time
make poc-logs | grep "Tool execution"

# 3. Check network latency
curl -w "@curl-format.txt" http://localhost:8002/health

# 4. Monitor SSE connection stability
# Browser DevTools → Network → EventSource connections
```

## Support

For issues or questions:
- Use `make poc-status` to verify all components are healthy
- Check `make poc-logs` for error messages across all services
- Verify component startup order and dependencies above
- Test individual components using direct API calls
- Review the Bio-MCP CLI tool for debugging: `uv run python clients/cli.py --help`

## License

This POC is part of the BioInvest AI Copilot project and follows the same licensing terms.