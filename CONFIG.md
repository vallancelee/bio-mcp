# Bio-MCP Configuration Guide

This guide explains how to configure Bio-MCP with your API keys and settings.

## Quick Setup

### Option 1: Automatic Setup (Recommended)
```bash
# Run the setup script
uv run python scripts/setup_config.py

# Or use bash version
./scripts/setup-config.sh
```

### Option 2: Manual Setup
```bash
# Copy the example configuration
cp .env.example .env

# Edit with your favorite editor
nano .env
# or
code .env
```

## Configuration Options

### Required for RAG Features
```bash
# OpenAI API key for embeddings and semantic search
OPENAI_API_KEY=your-new-openai-api-key-here
```

### Optional Enhancements
```bash
# NCBI API key for higher PubMed rate limits
PUBMED_API_KEY=your-ncbi-api-key-here

# Custom Weaviate instance URL
WEAVIATE_URL=http://localhost:8080

# Custom database (default: in-memory SQLite)
DATABASE_URL=postgresql://user:pass@localhost:5432/biomcp

# Server settings
BIO_MCP_SERVER_NAME=bio-mcp
BIO_MCP_LOG_LEVEL=INFO
```

## Getting API Keys

### OpenAI API Key (Required for RAG)
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign in or create account
3. Navigate to API Keys section
4. Create new secret key
5. Copy the key (starts with `sk-...`)

### NCBI API Key (Optional)
1. Go to [NCBI Account Settings](https://www.ncbi.nlm.nih.gov/account/settings/)
2. Create account if needed
3. Generate API key
4. Provides higher rate limits for PubMed queries

## Testing Your Configuration

### Basic Server Test
```bash
uv run python clients/cli.py ping --message "Config test"
```

### Test PubMed Features
```bash
# Search PubMed (works without Weaviate)
uv run python clients/cli.py pubmed.search --term "diabetes treatment" --limit 3

# Get specific document (requires valid PMID)
uv run python clients/cli.py pubmed.get --pmid "12345678"
```

### Test RAG Features (requires OpenAI key + Weaviate)
```bash
# Test RAG search (will show "no documents" without Weaviate)
uv run python clients/cli.py rag.search --query "blood sugar management" --top-k 3

# Sync documents to vector store (requires Weaviate running)
uv run python clients/cli.py pubmed.sync --query "diabetes treatment" --limit 3
```

### Start Weaviate for Full RAG Testing
```bash
# Option 1: Docker (recommended)
docker run -d \
  --name weaviate \
  -p 8080:8080 \
  cr.weaviate.io/semitechnologies/weaviate:1.25.0

# Option 2: Docker Compose (included in project)
docker-compose up -d weaviate

# Then test full workflow
uv run python clients/cli.py pubmed.sync --query "diabetes treatment" --limit 3
uv run python clients/cli.py rag.search --query "glucose control" --top-k 3
```

### Expected Output
✅ With valid OpenAI key:
- `rag.search` returns semantic search results
- `pubmed.sync` populates vector database
- Server status shows "OpenAI API: configured"

❌ Without valid OpenAI key:
- `rag.search` fails with API key error
- Server status shows "OpenAI API: not configured"

## Security Notes

- ✅ `.env` file is in `.gitignore` - won't be committed
- ✅ Use `.env.example` as template for team setup
- ⚠️  Never commit actual API keys to version control
- ⚠️  Rotate keys if accidentally exposed

## Troubleshooting

### "python-dotenv not available"
The server works with environment variables only. To get .env file loading:
```bash
# dotenv is already in dependencies, but ensure it's installed
uv add python-dotenv
```

### "No .env file found"
This is normal if you prefer environment variables:
```bash
export OPENAI_API_KEY="your-key-here"
export PUBMED_API_KEY="your-key-here"
```

### Configuration Not Loading
1. Check `.env` file is in project root (same directory as `pyproject.toml`)
2. Check file permissions are readable
3. Check for syntax errors in `.env` file
4. Restart the server after changes

### API Key Issues
```bash
# Test OpenAI key directly
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models

# Test NCBI/PubMed access
curl "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=diabetes&retmode=json&api_key=$PUBMED_API_KEY"
```

## Development vs Production

### Development (.env file)
- ✅ Good for local development
- ✅ Easy to manage multiple configurations
- ✅ Keeps secrets out of code

### Production (Environment Variables)
- ✅ Works with Docker, Kubernetes
- ✅ Better security practices
- ✅ CI/CD friendly

Both approaches are supported - the server automatically detects which is available.