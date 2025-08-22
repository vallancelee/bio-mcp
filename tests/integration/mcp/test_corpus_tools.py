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

        # Should return successful JSON response
        import json

        assert "```json" in response_text
        json_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])

        assert json_data["success"] is True
        assert json_data["operation"] == "corpus.checkpoint.create"
        assert json_data["data"]["checkpoint_id"] == "integration_test_checkpoint"
        assert json_data["data"]["name"] == "Integration Test Checkpoint"
        assert "execution_time_ms" in json_data["metadata"]

    @pytest.mark.asyncio
    async def test_checkpoint_create_validation_errors(self):
        """Test argument validation failures."""
        import json

        # Test missing checkpoint_id
        result = await corpus_checkpoint_create_tool(
            "corpus.checkpoint.create", {"name": "Test Checkpoint"}
        )

        assert len(result) == 1
        response_text = result[0].text

        # Should return JSON error format
        assert "```json" in response_text
        json_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])

        assert json_data["success"] is False
        assert json_data["operation"] == "corpus.checkpoint.create"
        assert json_data["error"]["code"] == "MISSING_PARAMETER"
        assert "checkpoint_id" in json_data["error"]["message"].lower()

        # Test missing name
        result = await corpus_checkpoint_create_tool(
            "corpus.checkpoint.create", {"checkpoint_id": "test_checkpoint"}
        )

        assert len(result) == 1
        response_text = result[0].text

        # Should return JSON error format
        assert "```json" in response_text
        json_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])

        assert json_data["success"] is False
        assert json_data["operation"] == "corpus.checkpoint.create"
        assert json_data["error"]["code"] == "MISSING_PARAMETER"
        assert "name" in json_data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_checkpoint_get_success(self, sample_checkpoint):
        """Test successful checkpoint retrieval."""
        result = await corpus_checkpoint_get_tool(
            "corpus.checkpoint.get", {"checkpoint_id": sample_checkpoint}
        )

        assert len(result) == 1
        self.validator.validate_text_content(result[0])

        response_text = result[0].text

        # Should return JSON response
        if "```json" in response_text:
            import json

            json_data = json.loads(
                response_text.split("```json\n")[1].split("\n```")[0]
            )

            assert json_data["success"] is True
            assert json_data["operation"] == "corpus.checkpoint.get"
            assert json_data["data"]["checkpoint_id"] == sample_checkpoint
            assert "Test Checkpoint" in json_data["data"].get("name", "")
            assert "execution_time_ms" in json_data["metadata"]
        else:
            # Fallback to text validation for backward compatibility
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

        # Should return JSON error response
        if "```json" in response_text:
            import json

            json_data = json.loads(
                response_text.split("```json\n")[1].split("\n```")[0]
            )

            assert json_data["success"] is False
            assert json_data["operation"] == "corpus.checkpoint.get"
            assert json_data["error"]["code"] == "NOT_FOUND"
            assert "nonexistent_checkpoint_12345" in json_data["error"]["message"]
        else:
            # Fallback to text validation
            assert "❌" in response_text or "not found" in response_text.lower()

    @pytest.mark.asyncio
    async def test_checkpoint_get_validation_errors(self):
        """Test checkpoint get validation errors."""
        result = await corpus_checkpoint_get_tool("corpus.checkpoint.get", {})

        assert len(result) == 1
        response_text = result[0].text

        # Should return JSON error response
        if "```json" in response_text:
            import json

            json_data = json.loads(
                response_text.split("```json\n")[1].split("\n```")[0]
            )

            assert json_data["success"] is False
            assert json_data["operation"] == "corpus.checkpoint.get"
            assert json_data["error"]["code"] == "MISSING_PARAMETER"
            assert "checkpoint_id" in json_data["error"]["message"].lower()
        else:
            # Fallback to text validation
            assert "❌" in response_text
            assert "checkpoint_id" in response_text.lower()

    @pytest.mark.asyncio
    async def test_checkpoint_list_success(self, sample_checkpoint):
        """Test successful checkpoint listing."""
        result = await corpus_checkpoint_list_tool(
            "corpus.checkpoint.list", {"limit": 20, "offset": 0}
        )

        assert len(result) == 1
        self.validator.validate_text_content(result[0])

        response_text = result[0].text

        # Should return successful JSON response
        import json

        assert "```json" in response_text
        json_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])

        assert json_data["success"] is True
        assert json_data["operation"] == "corpus.checkpoint.list"
        assert "checkpoints" in json_data["data"]
        assert "execution_time_ms" in json_data["metadata"]

        # Should contain our sample checkpoint
        checkpoints = json_data["data"]["checkpoints"]
        checkpoint_ids = [cp.get("checkpoint_id", "") for cp in checkpoints]
        assert sample_checkpoint in checkpoint_ids or any(
            "Test Checkpoint" in str(cp) for cp in checkpoints
        )

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
        import json

        # First create a checkpoint to delete
        create_result = await corpus_checkpoint_create_tool(
            "corpus.checkpoint.create",
            {
                "checkpoint_id": "delete_test_checkpoint",
                "name": "Checkpoint to Delete",
                "description": "Will be deleted in test",
            },
        )

        # Verify create was successful (JSON format)
        create_text = create_result[0].text
        assert "```json" in create_text
        create_json = json.loads(create_text.split("```json\n")[1].split("\n```")[0])
        assert create_json["success"] is True

        # Now delete it
        result = await corpus_checkpoint_delete_tool(
            "corpus.checkpoint.delete", {"checkpoint_id": "delete_test_checkpoint"}
        )

        assert len(result) == 1
        response_text = result[0].text

        # Should return successful JSON response
        assert "```json" in response_text
        json_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])

        assert json_data["success"] is True
        assert json_data["operation"] == "corpus.checkpoint.delete"
        assert json_data["data"]["checkpoint_id"] == "delete_test_checkpoint"
        assert json_data["data"]["deleted"] is True
        assert "execution_time_ms" in json_data["metadata"]

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
        response_text = result[0].text

        # Should return JSON error format
        import json

        assert "```json" in response_text
        json_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])

        assert json_data["success"] is False
        assert json_data["operation"] == "corpus.checkpoint.delete"
        assert json_data["error"]["code"] == "MISSING_PARAMETER"
        assert "checkpoint_id" in json_data["error"]["message"].lower()

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

        # Verify create success (JSON format)
        import json

        create_text = create_result[0].text
        assert "```json" in create_text
        create_json = json.loads(create_text.split("```json\n")[1].split("\n```")[0])
        assert create_json["success"] is True
        assert create_json["data"]["checkpoint_id"] == checkpoint_id

        # 2. Get checkpoint - JSON format
        get_result = await corpus_checkpoint_get_tool(
            "corpus.checkpoint.get", {"checkpoint_id": checkpoint_id}
        )
        get_text = get_result[0].text
        if "```json" in get_text:
            get_json = json.loads(get_text.split("```json\n")[1].split("\n```")[0])
            assert get_json["success"] is True
            assert get_json["data"]["checkpoint_id"] == checkpoint_id
            assert "Workflow Test Checkpoint" in get_json["data"].get("name", "")
        else:
            # Fallback to text search
            assert checkpoint_id in get_text
            assert "Workflow Test Checkpoint" in get_text

        # 3. List checkpoints (should include our new one) - JSON format
        list_result = await corpus_checkpoint_list_tool("corpus.checkpoint.list", {})
        list_text = list_result[0].text
        if "```json" in list_text:
            list_json = json.loads(list_text.split("```json\n")[1].split("\n```")[0])
            assert list_json["success"] is True
            checkpoint_ids = [
                cp.get("checkpoint_id", "") for cp in list_json["data"]["checkpoints"]
            ]
            assert (
                checkpoint_id in checkpoint_ids
                or "Workflow Test Checkpoint" in list_text
            )
        else:
            # Fallback to text search
            assert checkpoint_id in list_text or "Workflow Test Checkpoint" in list_text

        # 4. Delete checkpoint - JSON format
        delete_result = await corpus_checkpoint_delete_tool(
            "corpus.checkpoint.delete", {"checkpoint_id": checkpoint_id}
        )
        delete_text = delete_result[0].text
        if "```json" in delete_text:
            delete_json = json.loads(
                delete_text.split("```json\n")[1].split("\n```")[0]
            )
            assert delete_json["success"] is True
            assert delete_json["data"]["checkpoint_id"] == checkpoint_id
            assert delete_json["data"]["deleted"] is True
        else:
            # Fallback to text search
            assert "✅" in delete_text or "deleted" in delete_text.lower()

        # 5. Verify deletion - get should now fail
        verify_result = await corpus_checkpoint_get_tool(
            "corpus.checkpoint.get", {"checkpoint_id": checkpoint_id}
        )
        assert (
            "❌" in verify_result[0].text
            or "not found" in verify_result[0].text.lower()
        )
