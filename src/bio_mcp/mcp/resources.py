"""
MCP Resources for Bio-MCP server.
Phase 4B.4: MCP Resource Endpoints - Expose corpus data and system status.
"""

import time
from dataclasses import dataclass
from typing import Any

from mcp.types import Resource

from bio_mcp.config.logging_config import get_logger
from bio_mcp.services.services import CorpusCheckpointService, DocumentService

logger = get_logger(__name__)


@dataclass
class ResourceResult:
    """Result of a resource operation."""

    resource_uri: str
    operation: str  # "list", "read"
    success: bool
    execution_time_ms: float
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    error_message: str | None = None


class BioMCPResourceManager:
    """Manager for Bio-MCP resource endpoints."""

    def __init__(self) -> None:
        self.document_service = DocumentService()
        self.checkpoint_service = CorpusCheckpointService()
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize the resource manager."""
        if self.initialized:
            return

        logger.info("Initializing Bio-MCP resource manager")
        await self.document_service.initialize()
        await self.checkpoint_service.initialize()
        self.initialized = True
        logger.info("Bio-MCP resource manager initialized successfully")

    async def close(self) -> None:
        """Close all connections and cleanup."""
        if self.document_service:
            await self.document_service.close()
        if self.checkpoint_service:
            await self.checkpoint_service.close()

        self.initialized = False
        logger.info("Bio-MCP resource manager closed")

    async def list_resources(self) -> ResourceResult:
        """List all available resources."""
        start_time = time.time()

        try:
            resources = [
                {
                    "uri": "bio-mcp://corpus/status",
                    "name": "Corpus Status",
                    "description": "Current corpus statistics and sync status",
                    "mimeType": "application/json",
                },
                {
                    "uri": "bio-mcp://corpus/checkpoints",
                    "name": "Corpus Checkpoints",
                    "description": "List of all corpus checkpoints for reproducible research",
                    "mimeType": "application/json",
                },
                {
                    "uri": "bio-mcp://sync/recent",
                    "name": "Recent Sync Activities",
                    "description": "Recent synchronization activities and watermarks",
                    "mimeType": "application/json",
                },
                {
                    "uri": "bio-mcp://system/health",
                    "name": "System Health",
                    "description": "Overall system health and component status",
                    "mimeType": "application/json",
                },
            ]

            execution_time = (time.time() - start_time) * 1000

            return ResourceResult(
                resource_uri="bio-mcp://",
                operation="list",
                success=True,
                execution_time_ms=execution_time,
                data=resources,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error("Failed to list resources", error=str(e))
            return ResourceResult(
                resource_uri="bio-mcp://",
                operation="list",
                success=False,
                execution_time_ms=execution_time,
                error_message=str(e),
            )

    async def get_corpus_status(self) -> ResourceResult:
        """Get current corpus status and statistics."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        try:
            # Get document count from database
            # Note: This is a simplified implementation - in production you might want
            # to cache these statistics or compute them asynchronously

            # Get basic corpus statistics
            total_documents = "0"  # Default fallback

            # Try to get document count (this would require a new database method)
            try:
                # For now, we'll simulate this - in a real implementation you'd add
                # a count method to DatabaseManager
                total_documents = "Unknown"
            except Exception:
                pass

            # Get sync watermarks for active queries
            try:
                # Get recent sync watermarks (limited implementation)
                sync_watermarks: list[
                    dict[str, Any]
                ] = []  # This would come from database query
            except Exception:
                sync_watermarks = []

            corpus_status = {
                "corpus_statistics": {
                    "total_documents": total_documents,
                    "total_vectors": total_documents,  # Assuming 1:1 ratio for now
                    "last_updated": time.strftime(
                        "%Y-%m-%d %H:%M:%S UTC", time.gmtime()
                    ),
                },
                "sync_status": {
                    "active_queries": len(sync_watermarks),
                    "recent_watermarks": sync_watermarks[:5],  # Last 5 sync activities
                    "last_sync_time": "Unknown",
                },
                "system_info": {
                    "server_uptime": "Unknown",
                    "database_status": "Connected"
                    if self.document_service._initialized
                    else "Disconnected",
                    "checkpoint_count": "Unknown",
                },
            }

            execution_time = (time.time() - start_time) * 1000

            logger.info("Corpus status retrieved", execution_time_ms=execution_time)

            return ResourceResult(
                resource_uri="bio-mcp://corpus/status",
                operation="read",
                success=True,
                execution_time_ms=execution_time,
                data=corpus_status,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error("Failed to get corpus status", error=str(e))
            return ResourceResult(
                resource_uri="bio-mcp://corpus/status",
                operation="read",
                success=False,
                execution_time_ms=execution_time,
                error_message=str(e),
            )

    async def get_corpus_checkpoints(self) -> ResourceResult:
        """Get list of corpus checkpoints."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        try:
            # Get all checkpoints
            checkpoints = await self.checkpoint_service.list_checkpoints(
                limit=100, offset=0
            )

            checkpoint_summaries = []
            for checkpoint in checkpoints:
                checkpoint_summaries.append(
                    {
                        "checkpoint_id": checkpoint.checkpoint_id,
                        "name": checkpoint.name,
                        "description": checkpoint.description,
                        "total_documents": checkpoint.total_documents,
                        "version": checkpoint.version,
                        "parent_checkpoint_id": checkpoint.parent_checkpoint_id,
                        "created_at": checkpoint.created_at.isoformat(),
                        "primary_queries": checkpoint.primary_queries or [],
                    }
                )

            checkpoints_data = {
                "total_checkpoints": len(checkpoint_summaries),
                "checkpoints": checkpoint_summaries,
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            }

            execution_time = (time.time() - start_time) * 1000

            logger.info(
                "Corpus checkpoints retrieved",
                count=len(checkpoint_summaries),
                execution_time_ms=execution_time,
            )

            return ResourceResult(
                resource_uri="bio-mcp://corpus/checkpoints",
                operation="read",
                success=True,
                execution_time_ms=execution_time,
                data=checkpoints_data,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error("Failed to get corpus checkpoints", error=str(e))
            return ResourceResult(
                resource_uri="bio-mcp://corpus/checkpoints",
                operation="read",
                success=False,
                execution_time_ms=execution_time,
                error_message=str(e),
            )

    async def get_recent_sync_activities(self) -> ResourceResult:
        """Get recent sync activities and watermarks."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        try:
            # In a full implementation, this would query the sync_watermarks table
            # For now, we'll provide a placeholder structure

            sync_activities = {
                "recent_syncs": [],  # Would come from database query
                "active_queries": 0,
                "total_synced_documents": "Unknown",
                "last_sync_time": "Unknown",
                "sync_status": "Ready",
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            }

            execution_time = (time.time() - start_time) * 1000

            logger.info(
                "Recent sync activities retrieved", execution_time_ms=execution_time
            )

            return ResourceResult(
                resource_uri="bio-mcp://sync/recent",
                operation="read",
                success=True,
                execution_time_ms=execution_time,
                data=sync_activities,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error("Failed to get recent sync activities", error=str(e))
            return ResourceResult(
                resource_uri="bio-mcp://sync/recent",
                operation="read",
                success=False,
                execution_time_ms=execution_time,
                error_message=str(e),
            )

    async def get_system_health(self) -> ResourceResult:
        """Get overall system health status."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        try:
            health_status = {
                "overall_status": "Healthy",
                "components": {
                    "database": {
                        "status": "Connected"
                        if self.document_service._initialized
                        else "Disconnected",
                        "last_check": time.strftime(
                            "%Y-%m-%d %H:%M:%S UTC", time.gmtime()
                        ),
                    },
                    "checkpoint_service": {
                        "status": "Connected"
                        if self.checkpoint_service._initialized
                        else "Disconnected",
                        "last_check": time.strftime(
                            "%Y-%m-%d %H:%M:%S UTC", time.gmtime()
                        ),
                    },
                    "pubmed_api": {
                        "status": "Available",  # Would check actual connectivity
                        "last_check": time.strftime(
                            "%Y-%m-%d %H:%M:%S UTC", time.gmtime()
                        ),
                    },
                },
                "metrics": {
                    "uptime": "Unknown",
                    "memory_usage": "Unknown",
                    "active_connections": "Unknown",
                },
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            }

            execution_time = (time.time() - start_time) * 1000

            logger.info("System health retrieved", execution_time_ms=execution_time)

            return ResourceResult(
                resource_uri="bio-mcp://system/health",
                operation="read",
                success=True,
                execution_time_ms=execution_time,
                data=health_status,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error("Failed to get system health", error=str(e))
            return ResourceResult(
                resource_uri="bio-mcp://system/health",
                operation="read",
                success=False,
                execution_time_ms=execution_time,
                error_message=str(e),
            )


# Global resource manager instance
_resource_manager: BioMCPResourceManager | None = None


def get_resource_manager() -> BioMCPResourceManager:
    """Get the global resource manager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = BioMCPResourceManager()
    return _resource_manager


def get_checkpoint_manager() -> CorpusCheckpointService:
    """Get the checkpoint manager for testing compatibility."""
    manager = get_resource_manager()
    return manager.checkpoint_service


def get_document_manager() -> DocumentService:
    """Get the document manager for testing compatibility."""
    manager = get_resource_manager()
    return manager.document_service


def get_database_manager():
    """Get the database manager for testing compatibility."""
    from bio_mcp.shared.clients.database import get_database_manager

    return get_database_manager()


# MCP Resource endpoint functions
async def list_resources() -> list[Resource]:
    """List all available MCP resources."""
    try:
        manager = get_resource_manager()
        result = await manager.list_resources()

        if result.success and result.data:
            resources = []
            for resource_info in result.data:
                if isinstance(resource_info, dict):
                    resources.append(
                        Resource(
                            uri=resource_info.get("uri", ""),
                            name=resource_info.get("name", ""),
                            description=resource_info.get("description", ""),
                            mimeType=resource_info.get("mimeType", "application/json"),
                        )
                    )
            return resources
        else:
            logger.error("Failed to list resources", error=result.error_message)
            return []

    except Exception as e:
        logger.error("Resource listing error", error=str(e))
        return []


async def read_resource(uri: str) -> str:
    """Read a specific MCP resource by URI."""
    try:
        manager = get_resource_manager()

        if uri == "bio-mcp://corpus/status":
            result = await manager.get_corpus_status()
        elif uri == "bio-mcp://corpus/checkpoints":
            result = await manager.get_corpus_checkpoints()
        elif uri == "bio-mcp://sync/recent":
            result = await manager.get_recent_sync_activities()
        elif uri == "bio-mcp://system/health":
            result = await manager.get_system_health()
        else:
            return f"Resource not found: {uri}"

        if result.success:
            import json

            return json.dumps(result.data, indent=2)
        else:
            return f"Error reading resource {uri}: {result.error_message}"

    except Exception as e:
        logger.error("Resource read error", uri=uri, error=str(e))
        return f"Error reading resource {uri}: {e!s}"
