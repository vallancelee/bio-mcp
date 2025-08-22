"""
Simplified integration tests for corpus tools MCP interface.

Tests MCP tools with real PostgreSQL database using TestContainers,
focusing on core functionality without complex mocking.
"""

import pytest

from bio_mcp.mcp.corpus_tools import (
    corpus_checkpoint_create_tool,
    corpus_checkpoint_delete_tool,
    corpus_checkpoint_get_tool,
    corpus_checkpoint_list_tool,
)
from tests.utils.mcp_validators import MCPResponseValidator

# Mark all tests to not use weaviate by default
pytestmark = pytest.mark.no_weaviate


class TestCorpusToolsIntegrationSimplified:
    """Simplified integration tests for corpus checkpoint tools."""

    def setup_method(self):
        """Setup test fixtures."""
        self.validator = MCPResponseValidator()

    @pytest.mark.asyncio
    async def test_checkpoint_create_success(self, sample_documents):
        """Test successful checkpoint creation with real database."""
        result = await corpus_checkpoint_create_tool(
            "corpus.checkpoint.create",
            {
                "checkpoint_id": "integration_test_checkpoint",
                "name": "Integration Test Checkpoint",
                "description": "Created during integration testing",
            },
        )

        assert len(result) == 1
        self.validator.validate_text_content(result[0])

        response_text = result[0].text
        assert "✅" in response_text or "successfully" in response_text.lower()
        assert "integration_test_checkpoint" in response_text
        assert "Integration Test Checkpoint" in response_text
        assert "ms" in response_text  # Execution time

    @pytest.mark.asyncio
    async def test_checkpoint_create_validation_errors(self):
        """Test argument validation failures."""
        # Test missing checkpoint_id
        result = await corpus_checkpoint_create_tool(
            "corpus.checkpoint.create", {"name": "Test Checkpoint"}
        )

        assert len(result) == 1
        assert "❌" in result[0].text
        assert "checkpoint_id" in result[0].text.lower()

        # Test missing name
        result = await corpus_checkpoint_create_tool(
            "corpus.checkpoint.create", {"checkpoint_id": "test_checkpoint"}
        )

        assert len(result) == 1
        assert "❌" in result[0].text
        assert "name" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_checkpoint_get_success(self, sample_checkpoint):
        """Test successful checkpoint retrieval."""
        result = await corpus_checkpoint_get_tool(
            "corpus.checkpoint.get", {"checkpoint_id": sample_checkpoint}
        )

        assert len(result) == 1
        self.validator.validate_text_content(result[0])

        response_text = result[0].text
        assert sample_checkpoint in response_text
        assert "Test Checkpoint" in response_text  # Name from fixture
        assert "ms" in response_text

    @pytest.mark.asyncio
    async def test_checkpoint_get_not_found(self):
        """Test checkpoint retrieval with non-existent ID."""
        result = await corpus_checkpoint_get_tool(
            "corpus.checkpoint.get", {"checkpoint_id": "nonexistent_checkpoint_12345"}
        )

        assert len(result) == 1
        response_text = result[0].text
        assert "❌" in response_text or "not found" in response_text.lower()

    @pytest.mark.asyncio
    async def test_checkpoint_get_validation_errors(self):
        """Test checkpoint get validation errors."""
        result = await corpus_checkpoint_get_tool("corpus.checkpoint.get", {})

        assert len(result) == 1
        assert "❌" in result[0].text
        assert "checkpoint_id" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_checkpoint_list_success(self, sample_checkpoint):
        """Test successful checkpoint listing."""
        result = await corpus_checkpoint_list_tool(
            "corpus.checkpoint.list", {"limit": 20, "offset": 0}
        )

        assert len(result) == 1
        self.validator.validate_text_content(result[0])

        response_text = result[0].text
        # Should contain our sample checkpoint
        assert sample_checkpoint in response_text or "Test Checkpoint" in response_text
        assert "ms" in response_text

    @pytest.mark.asyncio
    async def test_checkpoint_list_empty(self, clean_db):
        """Test checkpoint listing when no checkpoints exist."""
        # clean_db fixture ensures empty database
        result = await corpus_checkpoint_list_tool("corpus.checkpoint.list", {})

        assert len(result) == 1
        response_text = result[0].text
        assert "No corpus checkpoints found" in response_text or "0" in response_text
        assert "ms" in response_text

    @pytest.mark.asyncio
    async def test_checkpoint_delete_success(self, sample_documents):
        """Test successful checkpoint deletion."""
        # First create a checkpoint to delete
        create_result = await corpus_checkpoint_create_tool(
            "corpus.checkpoint.create",
            {
                "checkpoint_id": "delete_test_checkpoint",
                "name": "Checkpoint to Delete",
                "description": "Will be deleted in test",
            },
        )
        assert "✅" in create_result[0].text

        # Now delete it
        result = await corpus_checkpoint_delete_tool(
            "corpus.checkpoint.delete", {"checkpoint_id": "delete_test_checkpoint"}
        )

        assert len(result) == 1
        response_text = result[0].text
        assert "✅" in response_text or "deleted" in response_text.lower()
        assert "delete_test_checkpoint" in response_text
        assert "ms" in response_text

    @pytest.mark.asyncio
    async def test_checkpoint_delete_not_found(self):
        """Test checkpoint deletion with non-existent ID."""
        result = await corpus_checkpoint_delete_tool(
            "corpus.checkpoint.delete", {"checkpoint_id": "nonexistent_delete_12345"}
        )

        assert len(result) == 1
        response_text = result[0].text
        assert "❌" in response_text or "not found" in response_text.lower()

    @pytest.mark.asyncio
    async def test_checkpoint_delete_validation_errors(self):
        """Test checkpoint delete validation errors."""
        result = await corpus_checkpoint_delete_tool("corpus.checkpoint.delete", {})

        assert len(result) == 1
        assert "❌" in result[0].text
        assert "checkpoint_id" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_checkpoint_workflow_end_to_end(self, sample_documents):
        """Test complete checkpoint workflow: create -> get -> list -> delete."""
        checkpoint_id = "workflow_test_checkpoint"

        # 1. Create checkpoint
        create_result = await corpus_checkpoint_create_tool(
            "corpus.checkpoint.create",
            {
                "checkpoint_id": checkpoint_id,
                "name": "Workflow Test Checkpoint",
                "description": "End-to-end workflow test",
            },
        )
        assert "✅" in create_result[0].text
        assert checkpoint_id in create_result[0].text

        # 2. Get checkpoint
        get_result = await corpus_checkpoint_get_tool(
            "corpus.checkpoint.get", {"checkpoint_id": checkpoint_id}
        )
        assert checkpoint_id in get_result[0].text
        assert "Workflow Test Checkpoint" in get_result[0].text

        # 3. List checkpoints (should include our new one)
        list_result = await corpus_checkpoint_list_tool("corpus.checkpoint.list", {})
        assert (
            checkpoint_id in list_result[0].text
            or "Workflow Test Checkpoint" in list_result[0].text
        )

        # 4. Delete checkpoint
        delete_result = await corpus_checkpoint_delete_tool(
            "corpus.checkpoint.delete", {"checkpoint_id": checkpoint_id}
        )
        assert (
            "✅" in delete_result[0].text or "deleted" in delete_result[0].text.lower()
        )

        # 5. Verify deletion - get should now fail
        verify_result = await corpus_checkpoint_get_tool(
            "corpus.checkpoint.get", {"checkpoint_id": checkpoint_id}
        )
        assert (
            "❌" in verify_result[0].text
            or "not found" in verify_result[0].text.lower()
        )
