#!/usr/bin/env python3
"""
Script to get information about Weaviate collections.

Usage:
    uv run python -m scripts.weaviate_info [--collection NAME] [--validate]
"""

import argparse
import json
import sys
from urllib.parse import urlparse

import weaviate

from bio_mcp.config.config import config
from bio_mcp.config.logging_config import get_logger
from bio_mcp.services.weaviate_schema import WeaviateSchemaManager

logger = get_logger(__name__)


def get_collection_info(collection_name: str | None = None) -> dict:
    """Get information about Weaviate collections."""
    
    try:
        # Parse Weaviate URL
        parsed_url = urlparse(config.weaviate_url)
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or 8080
        secure = parsed_url.scheme == "https"
        
        # Connect to Weaviate
        client = weaviate.connect_to_custom(
            http_host=host,
            http_port=port,
            http_secure=secure
        )
        
        # Test connection
        if not client.is_ready():
            return {"error": "Weaviate is not ready"}
        
        schema_manager = WeaviateSchemaManager(client)
        
        if collection_name:
            # Get info for specific collection
            info = schema_manager.get_collection_info(collection_name)
            validation = schema_manager.validate_collection_schema(collection_name)
            
            result = {
                "collection": info,
                "validation": validation
            }
        else:
            # Get info for all collections
            try:
                meta = client.get_meta()
                all_collections = client.collections.list_all()
                
                result = {
                    "weaviate_meta": {
                        "version": meta.get("version", "unknown"),
                        "hostname": meta.get("hostname", "unknown")
                    },
                    "collections": {}
                }
                
                for collection_name in all_collections:
                    info = schema_manager.get_collection_info(collection_name)
                    result["collections"][collection_name] = info
            except Exception as e:
                logger.warning(f"Could not get all collections info: {e}")
                result = {
                    "weaviate_meta": {"version": "unknown"},
                    "collections": {},
                    "warning": f"Could not list all collections: {e}"
                }
        
        client.close()
        return result
    
    except Exception as e:
        logger.error(f"Failed to get collection info: {e}")
        return {"error": str(e)}


def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(description="Get Weaviate collection information")
    
    parser.add_argument(
        "--collection",
        help="Specific collection to inspect"
    )
    parser.add_argument(
        "--validate", 
        action="store_true",
        help="Validate collection schema"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    
    args = parser.parse_args()
    
    # Get collection info
    info = get_collection_info(args.collection)
    
    if args.json:
        print(json.dumps(info, indent=2, default=str))
    else:
        # Pretty print info
        if "error" in info:
            print(f"❌ Error: {info['error']}")
            sys.exit(1)
        
        if args.collection:
            # Single collection info
            collection_info = info["collection"]
            validation_info = info["validation"]
            
            print(f"📊 Collection: {collection_info['name']}")
            print(f"   Exists: {'✅' if collection_info['exists'] else '❌'}")
            
            if collection_info["exists"]:
                print(f"   Documents: {collection_info['total_documents']:,}")
                
                if args.validate:
                    print(f"   Schema Valid: {'✅' if validation_info['valid'] else '❌'}")
                    if validation_info["issues"]:
                        for issue in validation_info["issues"]:
                            print(f"     ⚠️  {issue}")
                    
                    print(f"   Properties Found: {len(validation_info['properties_found'])}")
                    for prop in sorted(validation_info["properties_found"]):
                        print(f"     - {prop}")
        else:
            # All collections info
            meta = info.get("weaviate_meta", {})
            print(f"🔌 Weaviate Version: {meta.get('version', 'unknown')}")
            print(f"   Hostname: {meta.get('hostname', 'unknown')}")
            print(f"   Collections: {len(info.get('collections', {}))}")
            
            if "warning" in info:
                print(f"⚠️  {info['warning']}")
            
            print()
            
            for name, collection_info in info.get("collections", {}).items():
                status = "✅" if collection_info["exists"] else "❌"
                docs = f"{collection_info.get('total_documents', 0):,}" if collection_info["exists"] else "N/A"
                print(f"{status} {name:<25} Documents: {docs}")


if __name__ == "__main__":
    main()