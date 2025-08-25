import time

import pytest

from bio_mcp.models.document import Document
from bio_mcp.services.chunking import AbstractChunker


class TestChunkingPerformance:
    """Test chunking performance requirements."""

    @pytest.fixture
    def large_document(self):
        """Create a large document for performance testing."""
        # Generate ~2000 word abstract
        content = " ".join(
            [
                f"This is sentence {i} in a long biomedical abstract containing detailed methodology and results."
                for i in range(200)
            ]
        )

        return Document(
            uid="pubmed:99999999",
            source="pubmed",
            source_id="99999999",
            title="Large Performance Test Document",
            text=content,
        )

    def test_chunking_speed(self, large_document):
        """Test that chunking meets speed requirements."""
        chunker = AbstractChunker()

        start_time = time.time()
        chunks = chunker.chunk_document(large_document)
        end_time = time.time()

        chunking_time = end_time - start_time

        # Should chunk large document in under 1 second
        assert chunking_time < 1.0
        assert len(chunks) > 0

    def test_uuid_generation_speed(self, large_document):
        """Test UUID generation speed."""
        chunker = AbstractChunker()
        chunks = chunker.chunk_document(large_document)

        start_time = time.time()
        for chunk in chunks:
            # Regenerate UUID to test speed
            new_uuid = chunk.generate_uuid(chunk.parent_uid, chunk.chunk_id)
            assert new_uuid == chunk.uuid
        end_time = time.time()

        uuid_time = end_time - start_time
        per_uuid_time = uuid_time / len(chunks)

        # Should generate UUID in under 0.1ms per chunk
        assert per_uuid_time < 0.0001

    def test_section_detection_speed(self):
        """Test section detection performance."""
        from bio_mcp.services.chunking import SectionDetector

        # Large structured abstract
        large_structured_text = (
            """
        Background: """
            + " ".join([f"Background sentence {i}." for i in range(50)])
            + """
        Methods: """
            + " ".join([f"Methods sentence {i}." for i in range(50)])
            + """
        Results: """
            + " ".join([f"Results sentence {i}." for i in range(100)])
            + """
        Conclusions: """
            + " ".join([f"Conclusions sentence {i}." for i in range(30)])
        )

        detector = SectionDetector()

        start_time = time.time()
        sections = detector.detect_sections(large_structured_text)
        end_time = time.time()

        detection_time = end_time - start_time

        # Should detect sections quickly
        assert detection_time < 0.1  # Under 100ms
        assert len(sections) == 4

    def test_sentence_splitting_speed(self):
        """Test sentence splitting performance."""
        from bio_mcp.services.chunking import SentenceSplitter

        # Large text with many sentences
        large_text = (
            ". ".join(
                [
                    f"This is sentence {i} with some biomedical content"
                    for i in range(500)
                ]
            )
            + "."
        )

        splitter = SentenceSplitter()

        start_time = time.time()
        sentences = splitter.split_sentences(large_text)
        end_time = time.time()

        splitting_time = end_time - start_time

        # Should split sentences quickly
        assert (
            splitting_time < 0.6
        )  # Under 600ms (slightly relaxed for spaCy model loading)
        assert len(sentences) == 500
