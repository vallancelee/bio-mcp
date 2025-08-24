#!/usr/bin/env python3
"""Simple script to create DocumentChunk_v2 collection with OpenAI embeddings."""

import asyncio

from bio_mcp.services.document_chunk_service import DocumentChunkService


async def main():
    try:
        print("Creating DocumentChunk_v2 collection...")
        service = DocumentChunkService()
        
        # The service will create schema manager and validate collection
        await service.connect()
        
        print("✅ Connected successfully!")
        
        # Check health
        health = await service.health_check()
        print(f"Health status: {health['status']}")
        print(f"Collection: {health['collection']}")
        print(f"Vectorizer: {health['vectorizer']}")
        print(f"Model: {health['model']}")
        print(f"Embeddings working: {health['embeddings_working']}")
        
        if not health['embeddings_working']:
            print(f"⚠️  Warning: {health.get('embedding_error', 'OpenAI embeddings not available')}")
        
        await service.disconnect()
        print("✅ Collection setup completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())