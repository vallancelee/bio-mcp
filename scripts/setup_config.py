#!/usr/bin/env python3
"""
Bio-MCP Configuration Setup Script
Creates .env file with API keys for local development.
"""

import sys
from pathlib import Path


def main():
    print("🔧 Bio-MCP Configuration Setup")
    print("=" * 32)

    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    example_file = project_root / ".env.example"

    if env_file.exists():
        print(f"⚠️  Configuration file already exists: {env_file}")
        response = input("Do you want to overwrite it? (y/N): ").strip().lower()
        if response not in ["y", "yes"]:
            print("📝 Edit your existing .env file manually or delete it first.")
            print(f"   Example: {example_file}")
            return

    print("📋 Creating configuration file from template...")

    # Read template
    with open(example_file) as f:
        config_content = f.read()

    print("\n🔑 Please provide your API keys (press Enter to skip optional ones):\n")

    # OpenAI API Key (required for RAG)
    openai_key = input("OpenAI API Key (required for RAG): ").strip()
    if openai_key:
        config_content = config_content.replace("your-openai-api-key-here", openai_key)

    # PubMed API Key (optional)
    print()
    pubmed_key = input(
        "NCBI/PubMed API Key (optional, for enhanced rate limits): "
    ).strip()
    if pubmed_key:
        config_content = config_content.replace("your-ncbi-api-key-here", pubmed_key)

    # Custom Weaviate URL (optional)
    print()
    weaviate_url = input(
        "Weaviate URL (optional, default: http://localhost:8080): "
    ).strip()
    if weaviate_url:
        config_content = config_content.replace("http://localhost:8080", weaviate_url)

    # Write config file
    with open(env_file, "w") as f:
        f.write(config_content)

    print(f"\n✅ Configuration saved to: {env_file}")
    print("\n🚀 You can now test the Bio-MCP server:")
    print("   uv run python clients/cli.py ping")
    print("\n🧪 Test RAG functionality:")
    print(
        '   uv run python clients/cli.py pubmed.sync --query "diabetes treatment" --limit 3'
    )
    print(
        '   uv run python clients/cli.py rag.search --query "diabetes management" --top-k 3'
    )
    print(f"\n📝 To edit configuration later: {env_file}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        sys.exit(1)
