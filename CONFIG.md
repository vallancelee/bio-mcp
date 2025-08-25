# Bio-MCP Configuration Guide

This guide explains how to configure Bio-MCP with your API keys, database settings, and performance tuning parameters.

## Quick Setup

### Option 1: Automatic Setup (Recommended)
```bash
# Copy the example configuration
cp .env.example .env

# Edit with your favorite editor
nano .env
# or
code .env
```

### Option 2: Environment Variables Only
```bash
# Set directly in environment (useful for production)
export OPENAI_API_KEY="sk-your-key-here"
export BIO_MCP_OPENAI_API_KEY="sk-your-key-here"
export BIO_MCP_DATABASE_URL="postgresql://user:pass@localhost:5432/biomcp"
export BIO_MCP_WEAVIATE_URL="http://localhost:8080"
```

## Required Configuration

### Core API Keys
```bash
# OpenAI API key for embeddings and semantic search (REQUIRED for RAG)
# Both variables needed for different parts of the system
OPENAI_API_KEY="sk-your-openai-api-key-here"
BIO_MCP_OPENAI_API_KEY="sk-your-openai-api-key-here"

# Database connection (defaults to in-memory SQLite)
BIO_MCP_DATABASE_URL="postgresql://postgres:postgres@localhost:5433/postgres"

# Weaviate vector database (defaults to localhost:8080)
BIO_MCP_WEAVIATE_URL="http://localhost:8080"
```

### Optional API Keys
```bash
# NCBI API key for higher PubMed rate limits (recommended for production)
BIO_MCP_PUBMED_API_KEY="your-ncbi-api-key-here"
```

## Server Configuration

### Basic Server Settings
```bash
# Server identification
BIO_MCP_SERVER_NAME="bio-mcp"

# Logging level: DEBUG, INFO, WARNING, ERROR
BIO_MCP_LOG_LEVEL="INFO"

# JSON structured logging (recommended for production)
BIO_MCP_JSON_LOGS="false"
```

### HTTP API Server (Optional)
```bash
# API Server Configuration
BIO_MCP_API_HOST="0.0.0.0"
BIO_MCP_API_PORT="8000"

# Job Queue Configuration
BIO_MCP_JOBS_ENABLED="true"
BIO_MCP_JOBS_POLL_INTERVAL="5"
BIO_MCP_WORKER_CONCURRENCY="2"
```

## Model & Processing Configuration

### Chunking Configuration
```bash
# Chunking strategy parameters
BIO_MCP_CHUNKER_TARGET_TOKENS="325"  # Target tokens per chunk
BIO_MCP_CHUNKER_MAX_TOKENS="450"     # Hard maximum tokens
BIO_MCP_CHUNKER_MIN_TOKENS="120"     # Minimum section size before chunking
BIO_MCP_CHUNKER_OVERLAP_TOKENS="50"  # Token overlap for long sections
BIO_MCP_CHUNKER_VERSION="v1.2.0"     # Chunker version identifier
```

### Embedding Configuration
```bash
# OpenAI embedding model (text-embedding-3-small or text-embedding-3-large)
OPENAI_EMBEDDING_MODEL="text-embedding-3-small"

# OpenAI embedding dimensions (256, 512, 1024, 1536, or 3072 for large model)
# Lower dimensions = lower cost but potentially lower quality
OPENAI_EMBEDDING_DIMENSIONS="1536"

# Weaviate collection for document chunks
BIO_MCP_WEAVIATE_COLLECTION_V2="DocumentChunk_v2"
```

### UUID Configuration
```bash
# UUID namespace for deterministic chunk IDs (set once, never change)
BIO_MCP_UUID_NAMESPACE="1b2c3d4e-0000-0000-0000-000000000000"

# Document schema version
BIO_MCP_DOCUMENT_SCHEMA_VERSION="1"
```

## Search Tuning Configuration

### Section Boost Weights
```bash
# Section boost weights (0.0-1.0) - higher values boost these sections in search results
BIO_MCP_BOOST_RESULTS_SECTION="0.15"      # Results sections get highest boost
BIO_MCP_BOOST_CONCLUSIONS_SECTION="0.12"  # Conclusions sections  
BIO_MCP_BOOST_METHODS_SECTION="0.05"      # Methods sections
BIO_MCP_BOOST_BACKGROUND_SECTION="0.02"   # Background sections
```

### Quality & Recency Boosting
```bash
# Quality boost factor (0.0-0.2) - multiplier for document quality scores
BIO_MCP_QUALITY_BOOST_FACTOR="0.1"

# Recency boost thresholds (years) - newer papers get boosted
BIO_MCP_RECENCY_RECENT_YEARS="2"    # Papers ≤2 years old
BIO_MCP_RECENCY_MODERATE_YEARS="5"  # Papers ≤5 years old  
BIO_MCP_RECENCY_OLD_YEARS="10"      # Papers ≤10 years old
```

### Search Behavior
```bash
# Default search configuration
BIO_MCP_SEARCH_DEFAULT_LIMIT="10"    # Default number of results
BIO_MCP_SEARCH_MAX_LIMIT="100"       # Maximum results allowed
BIO_MCP_SEARCH_DEFAULT_MODE="hybrid" # Default search mode: hybrid, semantic, bm25
BIO_MCP_SEARCH_HYBRID_ALPHA="0.5"    # Hybrid search weighting (0.0=BM25, 1.0=semantic)
```

## Performance Tuning

### Database Performance
```bash
# Database connection pool settings
BIO_MCP_DB_POOL_SIZE="5"         # Number of connections in pool
BIO_MCP_DB_MAX_OVERFLOW="10"     # Additional connections when pool full
BIO_MCP_DB_POOL_TIMEOUT="30.0"   # Seconds to wait for connection
BIO_MCP_DB_ECHO="false"          # Log all SQL queries (debug only)
```

### PubMed API Settings
```bash
# PubMed API rate limiting and timeouts
BIO_MCP_PUBMED_RATE_LIMIT="3"    # Requests per second
BIO_MCP_PUBMED_TIMEOUT="30.0"    # Request timeout in seconds
```

## S3/Object Storage Configuration

### S3-Compatible Storage
```bash
# S3-compatible storage (MinIO for local development, AWS S3 for production)
BIO_MCP_S3_ENDPOINT="http://localhost:9000"  # MinIO default
BIO_MCP_S3_ACCESS_KEY="minioadmin"
BIO_MCP_S3_SECRET_KEY="minioadmin" 
BIO_MCP_S3_BUCKET="bio-mcp-data"
BIO_MCP_S3_REGION="us-east-1"

# Archive configuration for raw data storage
BIO_MCP_ARCHIVE_BUCKET="bio-mcp-archive"
BIO_MCP_ARCHIVE_PREFIX="pubmed"
BIO_MCP_ARCHIVE_COMPRESSION="zstd"
```

## Getting API Keys

### OpenAI API Key (Required for RAG)
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign in or create account
3. Navigate to API Keys section
4. Create new secret key
5. Copy the key (starts with `sk-...`)
6. Set both `OPENAI_API_KEY` and `BIO_MCP_OPENAI_API_KEY`

### NCBI API Key (Optional, Recommended for Production)
1. Go to [NCBI Account Settings](https://www.ncbi.nlm.nih.gov/account/settings/)
2. Create account if needed
3. Generate API key
4. Provides higher rate limits for PubMed queries (10/second vs 3/second)

## Testing Your Configuration

### Basic Connectivity Test
```bash
# Test server startup and basic functionality
uv run python clients/cli.py ping --message "Config test"
```

### Test API Keys
```bash
# Test OpenAI API key directly
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models

# Test NCBI/PubMed access (if API key configured)  
curl "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=diabetes&retmode=json&api_key=$BIO_MCP_PUBMED_API_KEY"
```

### Test PubMed Features
```bash
# Search PubMed (works without Weaviate)
uv run python clients/cli.py pubmed.search --term "diabetes treatment" --limit 3

# Get specific document by PMID
uv run python clients/cli.py pubmed.get --pmid "12345678"

# Test incremental sync
uv run python clients/cli.py pubmed.sync.incremental --query "diabetes" --limit 5
```

### Test RAG Features (Requires OpenAI + Weaviate)
```bash
# Test RAG search (requires populated Weaviate)
uv run python clients/cli.py rag.search --query "blood sugar management" --top-k 3

# Test with different search modes
uv run python clients/cli.py rag.search --query "diabetes" --search-mode semantic --top-k 5
uv run python clients/cli.py rag.search --query "diabetes" --search-mode hybrid --alpha 0.7
```

### Start Weaviate for Full Testing
```bash
# Option 1: Docker (recommended)
docker run -d \
  --name weaviate \
  -p 8080:8080 \
  -e ENABLE_MODULES=text2vec-openai \
  -e OPENAI_APIKEY=$OPENAI_API_KEY \
  cr.weaviate.io/semitechnologies/weaviate:1.25.0

# Option 2: Docker Compose (included in project)
docker-compose up -d weaviate

# Then test full RAG workflow
uv run python clients/cli.py pubmed.sync --query "diabetes treatment" --limit 5
uv run python clients/cli.py rag.search --query "glucose control" --top-k 3
```

### Test Corpus Management
```bash
# Create a research checkpoint
uv run python clients/cli.py corpus.checkpoint.create \
  --checkpoint_id "diabetes_research_2024" \
  --name "Diabetes Research Snapshot 2024" \
  --description "Research corpus for diabetes studies"

# List checkpoints
uv run python clients/cli.py corpus.checkpoint.list

# Get checkpoint details
uv run python clients/cli.py corpus.checkpoint.get --checkpoint_id "diabetes_research_2024"
```

## Configuration Validation

### Expected Behavior with Valid Configuration
✅ **With OpenAI API key:**
- `rag.search` returns semantic search results
- `pubmed.sync` populates vector database with embeddings
- Server status shows "OpenAI API: configured"

✅ **With NCBI API key:**
- Higher PubMed API rate limits (10 req/sec vs 3 req/sec)
- More reliable large-scale document syncing

✅ **With proper database:**
- Persistent document storage
- Checkpoint management works
- Better performance than in-memory SQLite

### Error Indicators
❌ **Without OpenAI API key:**
- `rag.search` fails with API key error
- `pubmed.sync` fails during embedding generation
- Server status shows "OpenAI API: not configured"

❌ **Without Weaviate:**
- RAG search returns "no documents found"
- Document sync fails at vector storage step

❌ **Database connection issues:**
- Server startup fails with connection errors
- Document storage and retrieval fail

## Development vs Production

### Development Configuration (.env file)
```bash
# Development-friendly settings
BIO_MCP_DATABASE_URL="sqlite:///dev.db"          # Local file-based database
BIO_MCP_WEAVIATE_URL="http://localhost:8080"     # Local Weaviate instance
BIO_MCP_LOG_LEVEL="DEBUG"                        # Verbose logging
BIO_MCP_JSON_LOGS="false"                        # Human-readable logs
BIO_MCP_S3_ENDPOINT="http://localhost:9000"      # Local MinIO
```

### Production Configuration (Environment Variables)
```bash
# Production settings
BIO_MCP_DATABASE_URL="postgresql://user:pass@db-host:5432/biomcp"  # Managed PostgreSQL
BIO_MCP_WEAVIATE_URL="https://weaviate-cluster.example.com"        # Managed Weaviate
BIO_MCP_LOG_LEVEL="INFO"                                           # Production logging
BIO_MCP_JSON_LOGS="true"                                           # Structured logs
BIO_MCP_S3_ENDPOINT="https://s3.amazonaws.com"                     # AWS S3
```

## Troubleshooting

### Configuration Loading Issues
```bash
# Check if .env file is being loaded
ls -la .env  # Should exist in project root

# Test environment variable loading
uv run python -c "import os; print('OpenAI key:', os.getenv('OPENAI_API_KEY', 'NOT SET')[:10] + '...')"
```

### Common Configuration Problems
1. **Mixed line endings in .env file** - Use Unix line endings (LF)
2. **Quotes in environment variables** - Don't quote values in .env files
3. **Whitespace around equals signs** - Use `KEY=value` not `KEY = value`
4. **Missing required dependencies** - Run `uv sync` to install all dependencies

### Performance Tuning Tips
1. **For high-volume processing**: Increase `BIO_MCP_DB_POOL_SIZE` and `BIO_MCP_WORKER_CONCURRENCY`
2. **For faster embeddings**: Use `text-embedding-3-small` with lower dimensions (512 or 1024)
3. **For better search accuracy**: Use `text-embedding-3-large` with higher dimensions (3072)
4. **For memory efficiency**: Reduce `BIO_MCP_CHUNKER_TARGET_TOKENS` and increase `BIO_MCP_CHUNKER_OVERLAP_TOKENS`

## Security Notes

- ✅ `.env` file is in `.gitignore` - won't be committed to version control
- ✅ Use `.env.example` as template for team setup
- ⚠️  Never commit actual API keys to version control  
- ⚠️  Rotate keys immediately if accidentally exposed
- ⚠️  Use different API keys for development and production
- ⚠️  Consider using cloud secret management for production (AWS Secrets Manager, etc.)

---

**Configuration Reference**: For a complete list of all available environment variables, see `.env.example` in the project root.