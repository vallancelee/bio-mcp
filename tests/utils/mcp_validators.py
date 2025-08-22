"""
MCP response validation utilities for testing Bio-MCP tools.

Provides validation helpers for MCP TextContent responses and structured
data extraction from tool outputs.
"""

import re
from typing import Any

from mcp.types import TextContent


class MCPResponseValidator:
    """Validate MCP responses against expected formats and content."""

    def validate_text_content(self, response: TextContent) -> bool:
        """
        Validate TextContent response structure.

        Args:
            response: MCP TextContent response to validate

        Returns:
            True if response is valid TextContent

        Raises:
            AssertionError: If response format is invalid
        """
        assert hasattr(response, "type"), "Response missing 'type' attribute"
        assert response.type == "text", f"Expected type 'text', got '{response.type}'"
        assert hasattr(response, "text"), "Response missing 'text' attribute"
        assert isinstance(response.text, str), (
            f"Expected string text, got {type(response.text)}"
        )
        assert len(response.text) > 0, "Response text is empty"
        return True

    def validate_search_results(self, response_text: str) -> dict[str, Any]:
        """
        Parse and validate search result structure from MCP response.

        Args:
            response_text: Text content from MCP search response

        Returns:
            Dictionary with extracted search metadata

        Raises:
            AssertionError: If required search elements are missing
        """
        # Check for required search result elements
        assert "Query:" in response_text, "Search response missing query information"
        assert "Results:" in response_text or "Found" in response_text, (
            "Search response missing results count"
        )

        # Extract query
        query_match = re.search(r"Query:\s*([^\n]+)", response_text)
        query = query_match.group(1).strip() if query_match else ""

        # Extract total results count
        results_match = re.search(r"(?:Found|Results:)\s*(\d+)", response_text)
        total_results = int(results_match.group(1)) if results_match else 0

        # Extract execution time if present
        time_match = re.search(r"(\d+\.?\d*)\s*ms", response_text)
        execution_time_ms = float(time_match.group(1)) if time_match else None

        # Extract PMIDs from results
        pmid_matches = re.findall(r"PMID:\s*(\d+)", response_text)
        pmids = list(set(pmid_matches))  # Remove duplicates

        # Extract search mode if present
        mode_match = re.search(r"🔀|🧠|📝", response_text)
        if mode_match:
            mode_icon = mode_match.group(0)
            search_mode = {"🔀": "hybrid", "🧠": "semantic", "📝": "bm25"}.get(
                mode_icon, "unknown"
            )
        else:
            search_mode = "unknown"

        return {
            "query": query,
            "total_results": total_results,
            "pmids": pmids,
            "execution_time_ms": execution_time_ms,
            "search_mode": search_mode,
            "has_quality_info": "Quality boosting:" in response_text,
            "has_performance_info": "Performance:" in response_text,
        }

    def validate_error_response(self, response_text: str) -> bool:
        """
        Validate error response format and helpful messages.

        Args:
            response_text: Text content from MCP error response

        Returns:
            True if error response is well-formatted

        Raises:
            AssertionError: If error response format is invalid
        """
        assert "❌ Error:" in response_text or "Error" in response_text, (
            "Error response missing error indicator"
        )
        assert len(response_text) < 500, (
            f"Error response too verbose ({len(response_text)} chars, max 500)"
        )
        assert len(response_text) > 10, "Error response too brief to be helpful"

        # Check that error doesn't expose internal details
        sensitive_patterns = [
            r"Traceback",
            r"File \"/.*\"",
            r"raise \w+Error",
            r"__.*__",
            r"postgresql://.*:.*@",
            r"api_key=\w+",
        ]

        for pattern in sensitive_patterns:
            assert not re.search(pattern, response_text), (
                f"Error response exposes sensitive information: {pattern}"
            )

        return True

    def validate_document_details(self, response_text: str) -> dict[str, Any]:
        """
        Parse and validate document details response.

        Args:
            response_text: Text content from document retrieval response

        Returns:
            Dictionary with extracted document metadata
        """
        assert "📄 **Document Details**" in response_text, (
            "Document response missing details header"
        )

        # Extract PMID
        pmid_match = re.search(r"PMID:\s*(\d+)", response_text)
        pmid = pmid_match.group(1) if pmid_match else ""

        # Extract title
        title_match = re.search(r"\*\*Title:\*\*\s*([^\n]+)", response_text)
        title = title_match.group(1).strip() if title_match else ""

        # Extract journal
        journal_match = re.search(r"\*\*Journal:\*\*\s*([^\n]+)", response_text)
        journal = journal_match.group(1).strip() if journal_match else ""

        # Extract authors
        authors_match = re.search(r"\*\*Authors:\*\*\s*([^\n]+)", response_text)
        authors = authors_match.group(1).strip() if authors_match else ""

        # Check for quality score
        quality_match = re.search(r"Quality Score:\s*(\d+)", response_text)
        quality_score = int(quality_match.group(1)) if quality_match else None

        return {
            "pmid": pmid,
            "title": title,
            "journal": journal,
            "authors": authors,
            "quality_score": quality_score,
            "has_abstract": "**Abstract:**" in response_text,
            "has_mesh_terms": "**MeSH Terms:**" in response_text,
        }

    def validate_checkpoint_response(
        self, response_text: str, operation: str
    ) -> dict[str, Any]:
        """
        Parse and validate checkpoint operation response.

        Args:
            response_text: Text content from checkpoint operation
            operation: Expected operation (create, get, list, delete)

        Returns:
            Dictionary with extracted checkpoint information
        """
        operation_indicators = {
            "create": "✅ Corpus checkpoint created successfully",
            "get": "📋 **Checkpoint Details**",
            "list": "📚 **Available Checkpoints**",
            "delete": "✅ Checkpoint deleted successfully",
        }

        expected_indicator = operation_indicators.get(operation)
        if expected_indicator:
            assert expected_indicator in response_text, (
                f"Checkpoint {operation} response missing expected indicator"
            )

        # Extract checkpoint ID if present
        id_match = re.search(r"Checkpoint ID:\s*([^\n]+)", response_text)
        checkpoint_id = id_match.group(1).strip() if id_match else ""

        # Extract execution time
        time_match = re.search(r"(\d+\.?\d*)\s*ms", response_text)
        execution_time_ms = float(time_match.group(1)) if time_match else None

        # For list operations, extract checkpoint count
        if operation == "list":
            checkpoint_matches = re.findall(r"📁\s*\*\*([^*]+)\*\*", response_text)
            checkpoint_count = len(checkpoint_matches)
        else:
            checkpoint_count = None

        return {
            "checkpoint_id": checkpoint_id,
            "execution_time_ms": execution_time_ms,
            "checkpoint_count": checkpoint_count,
            "has_metadata": "Created:" in response_text
            or "Description:" in response_text,
        }

    def extract_performance_metrics(self, response_text: str) -> dict[str, Any]:
        """
        Extract performance metrics from MCP tool responses.

        Args:
            response_text: Text content from tool response

        Returns:
            Dictionary with performance metrics
        """
        # Extract execution time
        time_match = re.search(r"(\d+\.?\d*)\s*ms", response_text)
        execution_time_ms = float(time_match.group(1)) if time_match else None

        # Check performance indicators
        performance_indicators = {
            "fast": "✅ Performance:" in response_text,
            "slow": "⚠️ Performance:" in response_text
            or "❌ Performance:" in response_text,
            "target_met": execution_time_ms and execution_time_ms < 200
            if execution_time_ms
            else None,
        }

        # Extract target time if mentioned
        target_match = re.search(r"target:\s*<(\d+)ms", response_text)
        target_time_ms = float(target_match.group(1)) if target_match else None

        return {
            "execution_time_ms": execution_time_ms,
            "target_time_ms": target_time_ms,
            "performance_indicators": performance_indicators,
            "meets_target": execution_time_ms < target_time_ms
            if execution_time_ms and target_time_ms
            else None,
        }

    def validate_resource_content(
        self, response_text: str, resource_type: str
    ) -> dict[str, Any]:
        """
        Validate MCP resource content format.

        Args:
            response_text: Text content from resource response
            resource_type: Expected resource type (corpus, checkpoint, system)

        Returns:
            Dictionary with resource validation results
        """
        # Check for resource content structure
        has_header = any(header in response_text for header in ["📊", "📋", "🔧", "**"])
        assert has_header, "Resource response missing header structure"

        # Type-specific validation
        if resource_type == "corpus":
            assert (
                "Total Documents:" in response_text or "Documents:" in response_text
            ), "Corpus resource missing document count"

        elif resource_type == "checkpoint":
            assert "Checkpoint" in response_text, (
                "Checkpoint resource missing checkpoint information"
            )

        elif resource_type == "system":
            assert "Status:" in response_text or "Health:" in response_text, (
                "System resource missing status information"
            )

        # Extract metadata
        metadata = {}
        if "Documents:" in response_text:
            doc_match = re.search(r"Documents:\s*(\d+)", response_text)
            metadata["document_count"] = int(doc_match.group(1)) if doc_match else None

        if "Last Sync:" in response_text:
            sync_match = re.search(r"Last Sync:\s*([^\n]+)", response_text)
            metadata["last_sync"] = sync_match.group(1).strip() if sync_match else None

        return {
            "resource_type": resource_type,
            "has_header": has_header,
            "metadata": metadata,
            "content_length": len(response_text),
        }
