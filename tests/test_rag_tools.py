"""
Tests for RAG tools.
Phase 4A: Basic RAG Tools - Test document chunking and embedding functionality.
"""

from unittest.mock import AsyncMock, patch

import pytest

from bio_mcp.mcp.rag_tools import RAGToolsManager, rag_get_tool, rag_search_tool
from bio_mcp.shared.core.embeddings import (
    AbstractChunker,
    DocumentChunk,
)


class TestAbstractChunker:
    """Test the abstract chunking functionality."""

    def test_normalize_text(self):
        """Test text normalization."""
        chunker = AbstractChunker()

        # Test basic normalization
        text = "This is  a   test\nwith   multiple spaces"
        normalized = chunker.normalize_text(text)
        assert normalized == "This is a test\nwith multiple spaces"

        # Test hyphenated line breaks
        text = "hyphen-\nated word"
        normalized = chunker.normalize_text(text)
        assert normalized == "hyphenated word"  # Hyphenated words get joined correctly

    def test_detect_structure_structured(self):
        """Test detection of structured abstracts."""
        chunker = AbstractChunker()

        abstract = """Background: This is the background section.
        Methods: This describes the methodology used.
        Results: Here are the key findings.
        Conclusions: This summarizes the conclusions."""

        sections = chunker.detect_structure(abstract)
        assert sections is not None
        assert len(sections) == 4
        assert sections[0][0] == "Background"
        assert sections[1][0] == "Methods"
        assert sections[2][0] == "Results"
        assert sections[3][0] == "Conclusions"

    def test_detect_structure_unstructured(self):
        """Test detection of unstructured abstracts."""
        chunker = AbstractChunker()

        abstract = "This is a simple unstructured abstract without any section headers."

        sections = chunker.detect_structure(abstract)
        assert sections is None

    def test_split_sentences(self):
        """Test sentence splitting."""
        chunker = AbstractChunker()

        text = "This is sentence one. This is sentence two! This is sentence three?"
        sentences = chunker.split_sentences(text)
        assert len(sentences) == 3
        assert sentences[0] == "This is sentence one."
        assert sentences[1] == "This is sentence two!"
        assert sentences[2] == "This is sentence three?"

        # Test that numbers are not split incorrectly
        text = "The result was 1.5 mg/kg vs. 2.3 mg/kg (p=0.05)."
        sentences = chunker.split_sentences(text)
        assert len(sentences) == 1

    def test_chunk_short_abstract(self):
        """Test chunking of very short abstracts."""
        chunker = AbstractChunker()

        pmid = "12345"
        title = "Short Title"
        abstract = "Very short abstract."

        chunks = chunker.chunk_abstract(pmid, title, abstract)

        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.pmid == pmid
        assert chunk.chunk_id == "0"  # New format uses numeric chunk index
        assert chunk.section == "Text"  # New format uses "Text" for short content
        assert title in chunk.text
        assert abstract in chunk.text

    def test_chunk_no_abstract(self):
        """Test chunking when there's no abstract."""
        chunker = AbstractChunker()

        pmid = "12345"
        title = "Title Only"
        abstract = ""

        chunks = chunker.chunk_abstract(pmid, title, abstract)

        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.pmid == pmid
        assert chunk.chunk_id == "title"  # Legacy chunk ID preserved in conversion
        assert chunk.section == "Title Only"
        assert "No content available" in chunk.text

    def test_chunk_structured_abstract(self):
        """Test chunking of structured abstracts."""
        chunker = AbstractChunker()

        pmid = "12345"
        title = "Structured Study"
        abstract = """Background: Type 2 diabetes affects millions worldwide.
        Methods: We conducted a randomized controlled trial.
        Results: Treatment showed 12% improvement vs placebo (p<0.001).
        Conclusions: The new treatment is effective for diabetes."""

        chunks = chunker.chunk_abstract(pmid, title, abstract)

        # Should create chunks for each section
        assert len(chunks) >= 1

        # First chunk should have title prefix
        first_chunk = chunks[0]
        assert title in first_chunk.text
        assert f"(pubmed:{pmid})" in first_chunk.text  # New format uses (pubmed:PMID)

        # Each chunk should have section information
        for chunk in chunks:
            assert "[Section]" in chunk.text
            # Note: detection might treat this as unstructured if sections aren't clearly separated
            assert chunk.section in [
                "Background",
                "Methods",
                "Results",
                "Conclusions",
                "Unstructured",
            ]

    def test_chunk_stable_uuids(self):
        """Test that chunk UUIDs are stable for same content."""
        chunker = AbstractChunker()

        pmid = "12345"
        title = "Test Title"
        abstract = "Test abstract content."

        chunks1 = chunker.chunk_abstract(pmid, title, abstract)
        chunks2 = chunker.chunk_abstract(pmid, title, abstract)

        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.uuid == c2.uuid
            assert c1.chunk_id == c2.chunk_id


class TestRAGTools:
    """Test RAG tool functionality."""

    @pytest.mark.asyncio
    async def test_rag_search_tool_missing_query(self):
        """Test RAG search tool with missing query."""
        result = await rag_search_tool("rag.search", {})

        assert len(result) == 1
        assert "Query parameter is required" in result[0].text

    @pytest.mark.asyncio
    async def test_rag_get_tool_missing_doc_id(self):
        """Test RAG get tool with missing doc_id."""
        result = await rag_get_tool("rag.get", {})

        assert len(result) == 1
        assert "doc_id parameter is required" in result[0].text

    @pytest.mark.asyncio
    @patch("bio_mcp.mcp.rag_tools.get_rag_manager")
    async def test_rag_search_tool_no_results(self, mock_get_manager):
        """Test RAG search tool when no results found."""
        # Mock manager
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager

        # Mock search result with no documents
        from bio_mcp.mcp.rag_tools import RAGSearchResult

        mock_result = RAGSearchResult(
            query="test query", total_results=0, documents=[], search_type="semantic"
        )
        mock_manager.search_documents.return_value = mock_result

        result = await rag_search_tool("rag.search", {"query": "test query"})

        assert len(result) == 1
        response_text = result[0].text
        assert '"total_results": 0' in response_text
        assert '"results": []' in response_text
        assert "test query" in response_text

    @pytest.mark.asyncio
    @patch("bio_mcp.mcp.rag_tools.get_rag_manager")
    async def test_rag_get_tool_document_not_found(self, mock_get_manager):
        """Test RAG get tool when document is not found."""
        # Mock manager
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager

        # Mock get result with document not found
        from bio_mcp.mcp.rag_tools import RAGGetResult

        mock_result = RAGGetResult(doc_id="pmid:123", found=False)
        mock_manager.get_document.return_value = mock_result

        result = await rag_get_tool("rag.get", {"doc_id": "pmid:123"})

        assert len(result) == 1
        assert "Document not found" in result[0].text
        assert "pmid:123" in result[0].text

    @pytest.mark.asyncio
    async def test_rag_tools_manager_search_no_weaviate(self):
        """Test RAG manager behavior when Weaviate is not available."""
        # This tests the error handling when Weaviate is down
        manager = RAGToolsManager()

        # Mock Weaviate initialization failure
        with patch.object(
            manager.embedding_service,
            "search_chunks",
            side_effect=Exception("Connection failed"),
        ):
            result = await manager.search_documents("test query")

            assert result.total_results == 0
            assert result.documents == []
            assert "test query" in result.query


class TestDocumentChunk:
    """Test DocumentChunk functionality."""

    def test_document_chunk_creation(self):
        """Test DocumentChunk creation and UUID generation."""
        chunk = DocumentChunk(
            pmid="12345",
            chunk_id="s0",
            title="Test Title",
            section="Background",
            text="Test content",
            token_count=10,
        )

        assert chunk.pmid == "12345"
        assert chunk.chunk_id == "s0"
        assert chunk.uuid is not None
        assert str(chunk.uuid)  # Should be convertible to string

    def test_document_chunk_stable_uuid(self):
        """Test that UUIDs are stable for same content."""
        chunk1 = DocumentChunk("123", "s0", "Title", "Section", "Text", 10)
        chunk2 = DocumentChunk("123", "s0", "Title", "Section", "Text", 10)

        assert chunk1.uuid == chunk2.uuid

    def test_document_chunk_to_dict(self):
        """Test chunk serialization to dictionary."""
        chunk = DocumentChunk(
            pmid="12345",
            chunk_id="s0",
            title="Test Title",
            section="Background",
            text="Test content",
            token_count=10,
            year=2024,
        )

        data = chunk.to_dict()

        assert data["pmid"] == "12345"
        assert data["chunk_id"] == "s0"
        assert data["title"] == "Test Title"
        assert data["section"] == "Background"
        assert data["text"] == "Test content"
        assert data["token_count"] == 10
        assert data["year"] == 2024
        assert "uuid" in data
