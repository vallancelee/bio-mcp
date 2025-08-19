"""
Corpus checkpoint tools for Bio-MCP server.
Phase 4B.3: Corpus Checkpoint Management - MCP tool implementations.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from mcp.types import TextContent

from ..config.logging_config import get_logger
from ..services.services import CorpusCheckpointService

logger = get_logger(__name__)


@dataclass
class CheckpointResult:
    """Result of a checkpoint operation."""

    checkpoint_id: str
    operation: str  # "create", "get", "delete"
    success: bool
    execution_time_ms: float
    checkpoint_data: dict[str, Any] | None = None
    error_message: str | None = None

    def to_mcp_response(self) -> str:
        """Convert to MCP response format."""
        if not self.success:
            return f"""❌ Checkpoint {self.operation} failed: {self.checkpoint_id}

Error: {self.error_message}

Execution time: {self.execution_time_ms:.1f}ms"""

        if self.operation == "create":
            data = self.checkpoint_data or {}
            return f"""✅ Corpus checkpoint created successfully

**Checkpoint ID:** {self.checkpoint_id}
**Name:** {data.get('name', 'N/A')}
**Description:** {data.get('description', 'None')}
**Total Documents:** {data.get('total_documents', '0')}
**Last Sync EDAT:** {data.get('last_sync_edat', 'None')}
**Version:** {data.get('version', '1.0')}

Execution time: {self.execution_time_ms:.1f}ms"""

        elif self.operation == "get":
            if not self.checkpoint_data:
                return f"""❌ Checkpoint not found: {self.checkpoint_id}

The requested checkpoint does not exist in the database.

Execution time: {self.execution_time_ms:.1f}ms"""

            data = self.checkpoint_data
            return f"""📋 Corpus Checkpoint Details

**Checkpoint ID:** {self.checkpoint_id}
**Name:** {data.get('name', 'N/A')}
**Description:** {data.get('description', 'None')}

**Corpus Statistics:**
- Total Documents: {data.get('total_documents', '0')}
- Total Vectors: {data.get('total_vectors', '0')}
- Last Sync EDAT: {data.get('last_sync_edat', 'None')}

**Metadata:**
- Version: {data.get('version', '1.0')}
- Parent Checkpoint: {data.get('parent_checkpoint_id', 'None')}
- Created: {data.get('created_at', 'N/A')}

**Primary Queries:** {', '.join(data.get('primary_queries', []))}

Execution time: {self.execution_time_ms:.1f}ms"""

        elif self.operation == "delete":
            return f"""🗑️ Checkpoint deleted: {self.checkpoint_id}

The checkpoint has been permanently removed from the database.

Execution time: {self.execution_time_ms:.1f}ms"""

        return f"Unknown operation: {self.operation}"


@dataclass 
class CheckpointListResult:
    """Result of a checkpoint list operation."""

    total_found: int
    checkpoints: list[dict[str, Any]]
    execution_time_ms: float
    limit: int
    offset: int

    def to_mcp_response(self) -> str:
        """Convert to MCP response format."""
        if self.total_found == 0:
            return f"""📋 No corpus checkpoints found

No checkpoints are currently stored in the database.
Use the corpus.checkpoint.create tool to create your first checkpoint.

Execution time: {self.execution_time_ms:.1f}ms"""

        # Format checkpoint list
        checkpoints_text = []
        for i, checkpoint in enumerate(self.checkpoints, 1):
            parent_info = f" (parent: {checkpoint.get('parent_checkpoint_id', 'none')})" if checkpoint.get('parent_checkpoint_id') else ""
            
            checkpoint_text = f"""**{i}. {checkpoint.get('name', 'Unnamed')}**
📋 ID: {checkpoint.get('checkpoint_id', 'N/A')}
📊 Documents: {checkpoint.get('total_documents', '0')}
📅 Created: {checkpoint.get('created_at', 'N/A')[:19] if checkpoint.get('created_at') else 'N/A'}
🏷️ Version: {checkpoint.get('version', '1.0')}{parent_info}
📝 Description: {checkpoint.get('description', 'No description')}"""
            
            checkpoints_text.append(checkpoint_text)

        response = f"""📋 **Corpus Checkpoints**

**Found:** {self.total_found} checkpoints (showing {len(self.checkpoints)})
**Range:** Items {self.offset + 1}-{self.offset + len(self.checkpoints)}

{chr(10).join(checkpoints_text)}

Execution time: {self.execution_time_ms:.1f}ms"""

        return response


class CorpusCheckpointManager:
    """Manager for corpus checkpoint operations."""

    def __init__(self) -> None:
        self.checkpoint_service = CorpusCheckpointService()
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize the checkpoint manager."""
        if self.initialized:
            return

        logger.info("Initializing corpus checkpoint manager")
        await self.checkpoint_service.initialize()
        self.initialized = True
        logger.info("Corpus checkpoint manager initialized successfully")

    async def close(self) -> None:
        """Close all connections and cleanup."""
        if self.checkpoint_service:
            await self.checkpoint_service.close()
        
        self.initialized = False
        logger.info("Corpus checkpoint manager closed")

    async def create_checkpoint(
        self, 
        checkpoint_id: str, 
        name: str,
        description: str | None = None,
        primary_queries: list[str] | None = None,
        parent_checkpoint_id: str | None = None
    ) -> CheckpointResult:
        """Create a new corpus checkpoint."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()
        
        logger.info("Creating corpus checkpoint", checkpoint_id=checkpoint_id, name=name)

        try:
            checkpoint = await self.checkpoint_service.create_checkpoint(
                checkpoint_id=checkpoint_id,
                name=name,
                description=description,
                primary_queries=primary_queries,
                parent_checkpoint_id=parent_checkpoint_id
            )

            execution_time = (time.time() - start_time) * 1000

            checkpoint_data = {
                "checkpoint_id": checkpoint.checkpoint_id,
                "name": checkpoint.name,
                "description": checkpoint.description,
                "total_documents": checkpoint.total_documents,
                "total_vectors": checkpoint.total_vectors,
                "last_sync_edat": checkpoint.last_sync_edat,
                "version": checkpoint.version,
                "parent_checkpoint_id": checkpoint.parent_checkpoint_id,
                "created_at": checkpoint.created_at.isoformat(),
                "primary_queries": checkpoint.primary_queries
            }

            result = CheckpointResult(
                checkpoint_id=checkpoint_id,
                operation="create",
                success=True,
                execution_time_ms=execution_time,
                checkpoint_data=checkpoint_data
            )

            logger.info(
                "Corpus checkpoint created successfully",
                checkpoint_id=checkpoint_id,
                total_documents=checkpoint.total_documents,
                execution_time_ms=execution_time,
            )

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "Corpus checkpoint creation failed",
                checkpoint_id=checkpoint_id,
                error=str(e),
                execution_time_ms=execution_time,
            )
            return CheckpointResult(
                checkpoint_id=checkpoint_id,
                operation="create",
                success=False,
                execution_time_ms=execution_time,
                error_message=str(e)
            )

    async def get_checkpoint(self, checkpoint_id: str) -> CheckpointResult:
        """Get a corpus checkpoint by ID."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()
        
        logger.info("Getting corpus checkpoint", checkpoint_id=checkpoint_id)

        try:
            checkpoint = await self.checkpoint_service.get_checkpoint(checkpoint_id)
            execution_time = (time.time() - start_time) * 1000

            if checkpoint:
                checkpoint_data = {
                    "checkpoint_id": checkpoint.checkpoint_id,
                    "name": checkpoint.name,
                    "description": checkpoint.description,
                    "total_documents": checkpoint.total_documents,
                    "total_vectors": checkpoint.total_vectors,
                    "last_sync_edat": checkpoint.last_sync_edat,
                    "version": checkpoint.version,
                    "parent_checkpoint_id": checkpoint.parent_checkpoint_id,
                    "created_at": checkpoint.created_at.isoformat(),
                    "updated_at": checkpoint.updated_at.isoformat(),
                    "primary_queries": checkpoint.primary_queries,
                    "sync_watermarks": checkpoint.sync_watermarks
                }

                logger.info(
                    "Corpus checkpoint retrieved successfully",
                    checkpoint_id=checkpoint_id,
                    execution_time_ms=execution_time,
                )

                return CheckpointResult(
                    checkpoint_id=checkpoint_id,
                    operation="get",
                    success=True,
                    execution_time_ms=execution_time,
                    checkpoint_data=checkpoint_data
                )
            else:
                logger.info(
                    "Corpus checkpoint not found",
                    checkpoint_id=checkpoint_id,
                    execution_time_ms=execution_time,
                )

                return CheckpointResult(
                    checkpoint_id=checkpoint_id,
                    operation="get",
                    success=True,
                    execution_time_ms=execution_time,
                    checkpoint_data=None
                )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "Failed to get corpus checkpoint",
                checkpoint_id=checkpoint_id,
                error=str(e),
                execution_time_ms=execution_time,
            )
            return CheckpointResult(
                checkpoint_id=checkpoint_id,
                operation="get",
                success=False,
                execution_time_ms=execution_time,
                error_message=str(e)
            )

    async def list_checkpoints(self, limit: int = 20, offset: int = 0) -> CheckpointListResult:
        """List all corpus checkpoints."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()
        
        logger.info("Listing corpus checkpoints", limit=limit, offset=offset)

        try:
            checkpoints = await self.checkpoint_service.list_checkpoints(limit=limit, offset=offset)
            execution_time = (time.time() - start_time) * 1000

            checkpoint_data = []
            for checkpoint in checkpoints:
                checkpoint_data.append({
                    "checkpoint_id": checkpoint.checkpoint_id,
                    "name": checkpoint.name,
                    "description": checkpoint.description,
                    "total_documents": checkpoint.total_documents,
                    "total_vectors": checkpoint.total_vectors,
                    "version": checkpoint.version,
                    "parent_checkpoint_id": checkpoint.parent_checkpoint_id,
                    "created_at": checkpoint.created_at.isoformat(),
                })

            result = CheckpointListResult(
                total_found=len(checkpoints),
                checkpoints=checkpoint_data,
                execution_time_ms=execution_time,
                limit=limit,
                offset=offset
            )

            logger.info(
                "Corpus checkpoints listed successfully",
                count=len(checkpoints),
                execution_time_ms=execution_time,
            )

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "Failed to list corpus checkpoints",
                error=str(e),
                execution_time_ms=execution_time,
            )
            return CheckpointListResult(
                total_found=0,
                checkpoints=[],
                execution_time_ms=execution_time,
                limit=limit,
                offset=offset
            )

    async def delete_checkpoint(self, checkpoint_id: str) -> CheckpointResult:
        """Delete a corpus checkpoint."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()
        
        logger.info("Deleting corpus checkpoint", checkpoint_id=checkpoint_id)

        try:
            deleted = await self.checkpoint_service.delete_checkpoint(checkpoint_id)
            execution_time = (time.time() - start_time) * 1000

            if deleted:
                logger.info(
                    "Corpus checkpoint deleted successfully",
                    checkpoint_id=checkpoint_id,
                    execution_time_ms=execution_time,
                )

                return CheckpointResult(
                    checkpoint_id=checkpoint_id,
                    operation="delete",
                    success=True,
                    execution_time_ms=execution_time
                )
            else:
                return CheckpointResult(
                    checkpoint_id=checkpoint_id,
                    operation="delete",
                    success=False,
                    execution_time_ms=execution_time,
                    error_message="Checkpoint not found"
                )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "Failed to delete corpus checkpoint",
                checkpoint_id=checkpoint_id,
                error=str(e),
                execution_time_ms=execution_time,
            )
            return CheckpointResult(
                checkpoint_id=checkpoint_id,
                operation="delete",
                success=False,
                execution_time_ms=execution_time,
                error_message=str(e)
            )


# Global manager instance
_checkpoint_manager: CorpusCheckpointManager | None = None


def get_checkpoint_manager() -> CorpusCheckpointManager:
    """Get the global checkpoint manager instance."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CorpusCheckpointManager()
    return _checkpoint_manager


# MCP Tool implementations
async def corpus_checkpoint_create_tool(
    name: str, arguments: dict[str, Any]
) -> Sequence[TextContent]:
    """MCP tool: Create a new corpus checkpoint."""
    try:
        checkpoint_id = arguments.get("checkpoint_id", "")
        checkpoint_name = arguments.get("name", "")
        description = arguments.get("description")
        primary_queries = arguments.get("primary_queries", [])
        parent_checkpoint_id = arguments.get("parent_checkpoint_id")

        if not checkpoint_id:
            return [
                TextContent(
                    type="text",
                    text="❌ Error: 'checkpoint_id' parameter is required",
                )
            ]

        if not checkpoint_name:
            return [
                TextContent(
                    type="text",
                    text="❌ Error: 'name' parameter is required",
                )
            ]

        manager = get_checkpoint_manager()
        result = await manager.create_checkpoint(
            checkpoint_id=checkpoint_id,
            name=checkpoint_name,
            description=description,
            primary_queries=primary_queries,
            parent_checkpoint_id=parent_checkpoint_id
        )

        return [TextContent(type="text", text=result.to_mcp_response())]

    except Exception as e:
        logger.error("Corpus checkpoint create tool error", error=str(e))
        return [TextContent(type="text", text=f"❌ Error creating checkpoint: {e!s}")]


async def corpus_checkpoint_get_tool(
    name: str, arguments: dict[str, Any]
) -> Sequence[TextContent]:
    """MCP tool: Get a corpus checkpoint by ID."""
    try:
        checkpoint_id = arguments.get("checkpoint_id", "")

        if not checkpoint_id:
            return [
                TextContent(
                    type="text",
                    text="❌ Error: 'checkpoint_id' parameter is required",
                )
            ]

        manager = get_checkpoint_manager()
        result = await manager.get_checkpoint(checkpoint_id)

        return [TextContent(type="text", text=result.to_mcp_response())]

    except Exception as e:
        logger.error("Corpus checkpoint get tool error", checkpoint_id=arguments.get("checkpoint_id"), error=str(e))
        return [TextContent(type="text", text=f"❌ Error retrieving checkpoint: {e!s}")]


async def corpus_checkpoint_list_tool(
    name: str, arguments: dict[str, Any]
) -> Sequence[TextContent]:
    """MCP tool: List all corpus checkpoints."""
    try:
        limit = min(max(arguments.get("limit", 20), 1), 100)
        offset = max(arguments.get("offset", 0), 0)

        manager = get_checkpoint_manager()
        result = await manager.list_checkpoints(limit=limit, offset=offset)

        return [TextContent(type="text", text=result.to_mcp_response())]

    except Exception as e:
        logger.error("Corpus checkpoint list tool error", error=str(e))
        return [TextContent(type="text", text=f"❌ Error listing checkpoints: {e!s}")]


async def corpus_checkpoint_delete_tool(
    name: str, arguments: dict[str, Any]
) -> Sequence[TextContent]:
    """MCP tool: Delete a corpus checkpoint."""
    try:
        checkpoint_id = arguments.get("checkpoint_id", "")

        if not checkpoint_id:
            return [
                TextContent(
                    type="text",
                    text="❌ Error: 'checkpoint_id' parameter is required",
                )
            ]

        manager = get_checkpoint_manager()
        result = await manager.delete_checkpoint(checkpoint_id)

        return [TextContent(type="text", text=result.to_mcp_response())]

    except Exception as e:
        logger.error("Corpus checkpoint delete tool error", checkpoint_id=arguments.get("checkpoint_id"), error=str(e))
        return [TextContent(type="text", text=f"❌ Error deleting checkpoint: {e!s}")]


def register_corpus_tools(server) -> None:
    """Register corpus checkpoint tools with the MCP server."""
    # Register the tools with the server
    server.call_tool()(corpus_checkpoint_create_tool)
    server.call_tool()(corpus_checkpoint_get_tool)
    server.call_tool()(corpus_checkpoint_list_tool)
    server.call_tool()(corpus_checkpoint_delete_tool)

    logger.info("Corpus checkpoint tools registered with MCP server")