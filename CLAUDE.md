# Bio-MCP Project Context

## Project Overview
Bio-MCP is a biomedical Model Context Protocol (MCP) server that provides PubMed search, RAG (Retrieval-Augmented Generation), and corpus management tools for biomedical research.

## Project Structure
This is a UV-managed Python project with the following structure:
- `src/bio_mcp/` - Main package directory
- `src/bio_mcp/main.py` - Main application entry point
- `src/bio_mcp/__init__.py` - Package initialization
- `pyproject.toml` - Project configuration and dependencies
- `contracts.md` - API contracts and specifications

## Key Features
Based on the contracts, this MCP server provides:
- **PubMed Sync**: Incremental sync of PubMed records with delta processing
- **RAG Search**: Hybrid search with quality-based reranking using Weaviate
- **Document Retrieval**: Fetch normalized document metadata and quality scores
- **Corpus Management**: Checkpoint management for query watermarks

## Development Guidelines
- Use UV for all Python operations: `uv run python script.py`
- Add dependencies: `uv add <package>` (not pip install)
- Install development dependencies: `uv sync --dev`
- Run scripts: `uv run <command>` instead of direct python execution
- Main entry point: `uv run bio-mcp` command (defined in pyproject.toml)
- Python 3.12+ required

## Dependencies
Core dependencies include:
- MCP framework for protocol implementation
- Weaviate client for vector search
- OpenAI for embeddings
- BioPython for biomedical data processing
- SQLAlchemy for metadata storage
- Pydantic for data validation

## Development Tools
- **Linting & Formatting**: `uv run ruff check` and `uv run ruff format` for fast Python linting and formatting
- **Type Checking**: `uv run mypy .` for static type analysis
- **Testing**: `uv run pytest` with async support
- **Pre-commit**: Automated code quality checks

## Testing
- Run tests: `uv run pytest`
- Test directory: `tests/`
- Async test support enabled

## Code Standards
- Line length: 88 characters
- Target Python version: 3.12
- Strict typing with MyPy
- Follow contracts defined in `contracts.md`

## API Contracts
All tool contracts are defined in `contracts.md` with JSON schemas for:
- Request/response validation
- Error handling patterns
- Versioning policy (semver)
- Internal adapter boundaries