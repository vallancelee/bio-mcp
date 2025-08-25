#!/usr/bin/env python3
"""
Script to create Weaviate DocumentChunk_v2 collection.

Usage:
    uv run python -m scripts.create_weaviate_schema [--collection-name NAME] [--vectorizer TYPE] [--model NAME]
"""

import argparse
import asyncio
import sys
from urllib.parse import urlparse

import weaviate

from bio_mcp.config.config import config
from bio_mcp.config.logging_config import get_logger
from bio_mcp.services.weaviate_schema import (
    CollectionConfig,
    VectorizerType,
    WeaviateSchemaManager,
)

logger = get_logger(__name__)


async def create_collection(
    collection_name: str = "DocumentChunk_v2",
    vectorizer_type: str = "transformers",
    model_name: str = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
    force: bool = False,
) -> bool:
    """Create Weaviate collection with specified configuration."""

    # Map string to enum
    vectorizer_map = {
        "huggingface": VectorizerType.HUGGINGFACE_API,
        "transformers": VectorizerType.TRANSFORMERS_LOCAL,
        "openai": VectorizerType.OPENAI,
    }

    if vectorizer_type not in vectorizer_map:
        logger.error(f"Unknown vectorizer type: {vectorizer_type}")
        return False

    try:
        # Parse Weaviate URL
        parsed_url = urlparse(config.weaviate_url)
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or 8080
        secure = parsed_url.scheme == "https"

        # Connect to Weaviate
        logger.info(
            "Connecting to Weaviate", url=config.weaviate_url, host=host, port=port
        )

        client = weaviate.connect_to_custom(
            http_host=host, http_port=port, http_secure=secure
        )

        # Test connection
        if not client.is_ready():
            logger.error("Weaviate is not ready")
            return False

        # Create schema manager
        collection_config = CollectionConfig(
            name=collection_name,
            vectorizer_type=vectorizer_map[vectorizer_type],
            model_name=model_name,
        )

        schema_manager = WeaviateSchemaManager(client, collection_config)

        # Check if collection exists
        if client.collections.exists(collection_name):
            if not force:
                logger.error(
                    f"Collection {collection_name} already exists. Use --force to recreate."
                )
                return False
            else:
                logger.info(f"Dropping existing collection: {collection_name}")
                await schema_manager.drop_collection(collection_name)

        # Create collection
        success = await schema_manager.create_document_chunk_v2_collection()

        if success:
            # Validate schema
            validation_result = schema_manager.validate_collection_schema(
                collection_name
            )

            if validation_result["valid"]:
                logger.info("Collection created and validated successfully")

                # Print collection info
                info = schema_manager.get_collection_info(collection_name)
                if info:
                    logger.info("Collection info", **info)

            else:
                logger.warning(
                    "Collection created but validation failed",
                    issues=validation_result["issues"],
                )

        client.close()
        return success

    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        return False


def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(
        description="Create Weaviate DocumentChunk_v2 collection"
    )

    parser.add_argument(
        "--collection-name",
        default="DocumentChunk_v2",
        help="Name of collection to create",
    )
    parser.add_argument(
        "--vectorizer",
        choices=["huggingface", "transformers", "openai"],
        default="transformers",
        help="Vectorizer type to use",
    )
    parser.add_argument(
        "--model",
        default="pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
        help="Model name for vectorizer",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force recreate if collection exists"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        import logging

        logging.getLogger().setLevel(logging.DEBUG)

    # Create collection
    success = asyncio.run(
        create_collection(
            collection_name=args.collection_name,
            vectorizer_type=args.vectorizer,
            model_name=args.model,
            force=args.force,
        )
    )

    if success:
        print(f"✅ Collection '{args.collection_name}' created successfully")
    else:
        print(f"❌ Failed to create collection '{args.collection_name}'")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
