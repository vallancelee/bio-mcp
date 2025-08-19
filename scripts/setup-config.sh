#!/bin/bash
set -e

echo "🔧 Bio-MCP Configuration Setup"
echo "================================"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
EXAMPLE_FILE="$PROJECT_ROOT/.env.example"

if [ -f "$ENV_FILE" ]; then
    echo "⚠️  Configuration file already exists: $ENV_FILE"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "📝 Edit your existing .env file manually or delete it first."
        echo "   Example: $EXAMPLE_FILE"
        exit 0
    fi
fi

echo "📋 Creating configuration file from template..."
cp "$EXAMPLE_FILE" "$ENV_FILE"

echo ""
echo "🔑 Please provide your API keys (press Enter to skip optional ones):"
echo ""

# OpenAI API Key (required for RAG)
read -p "OpenAI API Key (required for RAG): " OPENAI_KEY
if [ ! -z "$OPENAI_KEY" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/your-openai-api-key-here/$OPENAI_KEY/" "$ENV_FILE"
    else
        sed -i "s/your-openai-api-key-here/$OPENAI_KEY/" "$ENV_FILE"
    fi
fi

# PubMed API Key (optional)
echo ""
read -p "NCBI/PubMed API Key (optional, for enhanced rate limits): " PUBMED_KEY
if [ ! -z "$PUBMED_KEY" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/your-ncbi-api-key-here/$PUBMED_KEY/" "$ENV_FILE"
    else
        sed -i "s/your-ncbi-api-key-here/$PUBMED_KEY/" "$ENV_FILE"
    fi
fi

echo ""
echo "✅ Configuration saved to: $ENV_FILE"
echo ""
echo "🚀 You can now test the Bio-MCP server:"
echo "   uv run python clients/cli.py ping"
echo ""
echo "🧪 Test RAG functionality:"
echo "   uv run python clients/cli.py pubmed.sync --query \"diabetes treatment\" --limit 3"
echo "   uv run python clients/cli.py rag.search --query \"diabetes management\" --top-k 3"
echo ""
echo "📝 To edit configuration later: $ENV_FILE"