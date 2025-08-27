# BioInvest AI Copilot POC - Backend

FastAPI backend orchestrator with LangGraph integration for the BioInvest AI Copilot POC.

## Features

- **LangGraph Orchestration**: Intelligent query routing and execution
- **Real-time Streaming**: Server-Sent Events for live progress updates  
- **Bio-MCP Integration**: Full integration with biomedical data sources
- **Error Reporting**: Fail-fast with clear error messages (no fallbacks)
- **API Documentation**: Automatic OpenAPI/Swagger docs

## Prerequisites

- **Python 3.12+**
- **UV Package Manager**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Bio-MCP Server**: Must be running for orchestration

## Development Setup

### Install Dependencies
```bash
# Install all dependencies (including dev dependencies)
uv sync --no-install-project

# Install only production dependencies  
uv sync --no-install-project --no-dev
```

### Start Development Server
```bash
# Start with hot reload (recommended)
uv run python main.py

# Or run directly with uvicorn
uv run uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

### Alternative: Use Make Commands
```bash
# From project root
make poc-backend    # Start backend only
make poc-up         # Start full POC stack
```

## API Endpoints

### Core Research API
- **POST** `/api/research/query` - Submit research query
- **GET** `/api/research/stream/{query_id}` - Stream real-time results (SSE)
- **GET** `/api/research/query/{query_id}` - Get query status
- **GET** `/api/research/synthesis/{query_id}` - Get AI synthesis

### LangGraph Orchestration
- **GET** `/api/langgraph/status` - Check orchestrator status
- **GET** `/api/langgraph/visualization` - Get workflow diagram

### System
- **GET** `/` - Health check
- **GET** `/health` - Detailed health check
- **GET** `/docs` - API documentation

## Configuration

### Environment Variables
```bash
# Optional - defaults work for local development
BIO_MCP_SERVER_URL=http://localhost:8000
OPENAI_API_KEY=your_key_here
LOG_LEVEL=INFO
```

### Dependencies Management

**Add New Dependencies:**
```bash
uv add fastapi>=0.110.0
uv add --dev pytest>=8.0.0
```

**Update Dependencies:**
```bash
uv sync --upgrade
```

**Lock Dependencies:**
```bash
uv lock
```

## Development Tools

### Code Quality
```bash
# Format code
uv run ruff format

# Lint code  
uv run ruff check

# Type checking
uv run mypy .
```

### Testing
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=. --cov-report=html

# Run specific test file
uv run pytest tests/test_main.py
```

## Error Handling

This POC uses **fail-fast error handling** with no fallback mechanisms:

### Startup Errors
```bash
RuntimeError: POC backend startup failed: LangGraph orchestrator initialization error
```
**Solution**: Check LangGraph dependencies and Bio-MCP server status

### Runtime Errors  
```bash
RuntimeError: LangGraph orchestration failed: [specific error]
```
**Solution**: Check Bio-MCP server connectivity and query parameters

### Dependency Errors
```bash
ImportError: No module named 'langgraph'
```
**Solution**: Run `uv sync` to install missing dependencies

## Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
│   React         │────│   FastAPI    │────│  Bio-MCP    │
│   Frontend      │    │   Backend    │    │  Server     │
│                 │    │              │    │             │
│ • Query Input   │    │ • LangGraph  │    │ • PubMed    │
│ • Real-time UI  │────│   Orchestra. │────│ • Clinical  │
│ • Results View  │ SSE│ • Streaming  │    │ • RAG       │
└─────────────────┘    └──────────────┘    └─────────────┘
```

## Troubleshooting

### Common Issues

**Backend Won't Start:**
- Check UV installation: `uv --version`
- Install dependencies: `uv sync`
- Check port availability: `lsof -i :8002`

**LangGraph Errors:**
- Verify Bio-MCP server is running: `curl http://localhost:8000/health`
- Check orchestrator status: `curl http://localhost:8002/api/langgraph/status`

**Import Errors:**
- Clean and reinstall: `rm -rf .venv && uv sync`
- Check Python version: `python --version` (must be 3.12+)

### Logs

```bash
# View backend logs (if running via make poc-up)
tail -f logs/poc-backend.log

# View all POC logs
make poc-logs
```

## Project Structure

```
backend/
├── pyproject.toml          # UV project configuration
├── main.py                 # FastAPI application
├── src/
│   ├── models/
│   │   └── schemas.py      # Pydantic models
│   ├── orchestrator/
│   │   ├── bio_mcp_client.py    # Bio-MCP client
│   │   └── langgraph_client.py  # LangGraph orchestrator
│   └── services/
│       └── synthesis.py    # AI synthesis service
└── tests/                  # Test files (when added)
```

## Production Deployment

```bash
# Build for production
uv build

# Install in production environment
uv pip install dist/*.whl

# Run production server
uv run bioinvest-poc-backend
```

For production deployment, consider:
- Use a production WSGI/ASGI server (Gunicorn + Uvicorn)
- Configure proper logging and monitoring
- Set up health checks and metrics
- Use environment-specific configuration