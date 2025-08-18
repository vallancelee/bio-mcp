# Bio-MCP CLI Client

A command-line client for testing the Bio-MCP server using JSON-RPC calls over stdio.

## Quick Start

1. **Start the server** in one terminal:
   ```bash
   python src/bio_mcp/main.py
   ```

2. **Use the CLI client** in another terminal:
   ```bash
   # Test basic connectivity
   python clients/cli.py ping --message "hello server"
   
   # List all available tools
   python clients/cli.py list-tools
   
   # Test PubMed tools
   python clients/cli.py pubmed.search --term "CRISPR" --limit 5
   python clients/cli.py pubmed.get --pmid "12345678"
   python clients/cli.py pubmed.sync --query "weight loss" --limit 3
   ```

## Available Commands

### Basic Commands
- `ping` - Test server connectivity
- `list-tools` - List all available tools on the server

### PubMed Tools
- `pubmed.search` - Search PubMed for documents
- `pubmed.get` - Get a specific PubMed document by PMID
- `pubmed.sync` - Search PubMed and sync documents to database

### Future RAG/Corpus Tools (not yet implemented)
- `rag.search` - Search the RAG corpus for relevant documents
- `rag.get` - Get a specific document from the RAG corpus
- `corpus.checkpoint.get` - Get corpus checkpoint for a query key

## Configuration Options

The CLI client automatically detects the project root and server location, but you can override:

```bash
# Use custom server command
python clients/cli.py --server-cmd "python3 -m bio_mcp.main" ping

# Use custom working directory
python clients/cli.py --working-dir /path/to/project ping

# Combine both
python clients/cli.py --server-cmd "uv run python src/bio_mcp/main.py" --working-dir /custom/path ping
```

## Examples

### Testing PubMed Integration

```bash
# Search for recent COVID-19 research
python clients/cli.py pubmed.search --term "COVID-19 vaccine efficacy" --limit 10

# Get details for a specific paper
python clients/cli.py pubmed.get --pmid "34529645"

# Sync diabetes research to local database
python clients/cli.py pubmed.sync --query "diabetes treatment" --limit 20
```

### Debugging Server Issues

```bash
# List what tools are actually available
python clients/cli.py list-tools

# Test basic connectivity
python clients/cli.py ping --message "debug test"
```

## Output Format

The CLI uses rich formatting for clean, readable output:
- ✅ Successful responses are shown in green panels
- ❌ Errors are shown in red panels with error details
- 📊 Tool lists are displayed in formatted tables
- 🔍 JSON responses are syntax-highlighted

## Technical Details

- Uses JSON-RPC 2.0 over stdio to communicate with the MCP server
- Automatically handles MCP initialization protocol
- Spawns server as subprocess and manages lifecycle
- Graceful shutdown with timeout handling
- Rich console output with error formatting