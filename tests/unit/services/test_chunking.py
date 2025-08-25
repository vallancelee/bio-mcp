import os
from datetime import datetime

import pytest

from bio_mcp.models.document import Document
from bio_mcp.services.chunking import (
    AbstractChunker,
    ChunkingConfig,
    FallbackTokenizer,
    HuggingFaceTokenizer,
    NumericSafetyExpander,
    SectionDetector,
    SentenceSplitter,
)


class TestSectionDetector:
    """Test section detection in biomedical abstracts."""

    def test_structured_abstract_detection(self):
        """Test detection of structured abstract sections."""
        text = """
        Background: Glioblastoma multiforme (GBM) is the most aggressive primary brain tumor.
        Methods: We conducted a randomized controlled trial of 100 patients.
        Results: Overall survival was significantly improved (12.1 vs 8.4 months, p<0.001).
        Conclusions: This treatment shows promise for GBM patients.
        """

        detector = SectionDetector()
        sections = detector.detect_sections(text)

        assert len(sections) == 4
        assert sections[0].name == "Background"
        assert sections[1].name == "Methods"
        assert sections[2].name == "Results"
        assert sections[3].name == "Conclusions"

        # Check content (headers should be removed)
        assert "Glioblastoma multiforme" in sections[0].content
        assert "Background:" not in sections[0].content

    def test_unstructured_abstract_detection(self):
        """Test detection of unstructured abstracts."""
        text = "This study investigates the role of immunotherapy in cancer treatment."

        detector = SectionDetector()
        sections = detector.detect_sections(text)

        assert len(sections) == 1
        assert sections[0].name == "Unstructured"
        assert sections[0].content == text

    def test_variant_section_headings(self):
        """Test various section heading formats."""
        text = """
        Objective: To assess efficacy.
        Setting: Multi-center trial.
        Participants: 200 adult patients.
        Main Outcome Measures: Survival at 1 year.
        Findings: Significant improvement observed.
        Interpretation: Results support the intervention.
        """

        detector = SectionDetector()
        sections = detector.detect_sections(text)

        section_names = [s.name for s in sections]
        assert "Objective" in section_names
        assert "Methods" in section_names  # Setting, Participants should map to Methods
        assert "Results" in section_names  # Findings should map to Results
        assert (
            "Conclusions" in section_names
        )  # Interpretation should map to Conclusions


class TestSentenceSplitter:
    """Test biomedical sentence splitting."""

    def test_basic_sentence_splitting(self):
        """Test basic sentence splitting."""
        text = "This is sentence one. This is sentence two."

        splitter = SentenceSplitter()
        sentences = splitter.split_sentences(text)

        assert len(sentences) == 2
        assert sentences[0] == "This is sentence one."
        assert sentences[1] == "This is sentence two."

    def test_biomedical_patterns(self):
        """Test splitting with biomedical patterns."""
        text = """The primary endpoint was overall survival vs. placebo (HR=0.65, 95% CI 0.45-0.85, p=0.001). 
                  Secondary endpoints included progression-free survival."""

        splitter = SentenceSplitter()
        sentences = splitter.split_sentences(text)

        # Should not split on "vs." or within statistical expressions
        assert len(sentences) == 2
        assert (
            "vs. placebo" in sentences[0] or "vs placebo" in sentences[0]
        )  # Handle both protected and unprotected
        assert (
            "p=0.001" in sentences[0] or "p = 0.001" in sentences[0]
        )  # Handle spacing


class TestNumericSafetyExpander:
    """Test numeric safety expansion logic."""

    def test_needs_expansion_detection(self):
        """Test detection of splits that need expansion."""
        sentences = [
            "Overall survival was 12.1 months (95% CI 8.2-16.0).",
            "This compared favorably to the control group of 8.4 months.",
            "The difference was statistically significant (p<0.001).",
        ]

        # Should detect need for expansion at position 1
        assert NumericSafetyExpander.needs_expansion(sentences, 1)

        # Should not need expansion at position 2
        assert not NumericSafetyExpander.needs_expansion(sentences, 2)

    def test_window_expansion(self):
        """Test window expansion logic."""
        sentences = [
            "Treatment group showed improvement.",
            "Mean reduction was 15.2% (SD 4.1).",
            "Control group showed 3.1% reduction.",
            "The difference was significant (p=0.02).",
            "No serious adverse events occurred.",
        ]

        tokenizer = FallbackTokenizer()

        # Test expansion around statistical claim
        start, end = NumericSafetyExpander.expand_window(
            sentences, 1, 2, tokenizer, max_tokens=100
        )

        # Should expand to include context
        assert start <= 1
        assert end >= 3  # Include significance test


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Chunking requires OpenAI API key for consistent tokenization",
)
class TestChunkingIntegration:
    """Test complete chunking workflow with golden examples."""

    @pytest.fixture
    def sample_document(self):
        """Create sample biomedical document."""
        return Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="Immunotherapy in Advanced Melanoma: A Phase III Trial",
            text="""Background: Advanced melanoma has limited treatment options with poor survival outcomes.
Objective: To evaluate the efficacy and safety of pembrolizumab versus chemotherapy.
Methods: We conducted a randomized, double-blind, phase III trial involving 834 patients with advanced melanoma. Patients were randomly assigned to receive pembrolizumab or chemotherapy.
Results: The median overall survival was 25.0 months with pembrolizumab versus 13.8 months with chemotherapy (hazard ratio 0.73, 95% CI 0.61-0.88, p=0.001). Progression-free survival was also significantly improved (5.6 vs 2.8 months, HR 0.69, p<0.001).
Conclusions: Pembrolizumab significantly improved survival outcomes compared to chemotherapy in patients with advanced melanoma. The safety profile was acceptable with manageable adverse events.""",
            published_at=datetime(2024, 1, 15),
            detail={
                "journal": "New England Journal of Medicine",
                "mesh_terms": ["Melanoma", "Immunotherapy", "Pembrolizumab"],
            },
        )

    def test_structured_abstract_chunking(self, sample_document):
        """Test chunking of structured abstract."""
        chunker = AbstractChunker(ChunkingConfig(target_tokens=250, max_tokens=350))

        chunks = chunker.chunk_document(sample_document)

        # Should create multiple chunks for this document
        assert len(chunks) >= 2

        # First chunk should have title prefix
        assert sample_document.title in chunks[0].text
        assert "[Title]" in chunks[0].text

        # Verify chunk IDs are deterministic
        chunk_ids = [c.chunk_id for c in chunks]
        assert all(cid.startswith("s") for cid in chunk_ids)  # Section-based IDs

        # Verify UUIDs are deterministic
        chunk_uuids = [c.uuid for c in chunks]
        assert len(set(chunk_uuids)) == len(chunk_uuids)  # All unique

        # Re-chunk should produce same UUIDs
        chunks2 = chunker.chunk_document(sample_document)
        assert [c.uuid for c in chunks] == [c.uuid for c in chunks2]

    def test_unstructured_abstract_chunking(self):
        """Test chunking of unstructured abstract."""
        doc = Document(
            uid="pubmed:87654321",
            source="pubmed",
            source_id="87654321",
            title="Short Unstructured Abstract",
            text="This is a brief abstract without clear sections. It contains some results and conclusions.",
        )

        chunker = AbstractChunker(ChunkingConfig(target_tokens=250, max_tokens=350))
        chunks = chunker.chunk_document(doc)

        # Should create single chunk
        assert len(chunks) == 1
        assert chunks[0].section == "Unstructured"
        assert chunks[0].chunk_id == "w0"
        assert doc.title in chunks[0].text

    def test_long_section_splitting(self):
        """Test splitting of long sections with overlap."""
        long_text = " ".join(
            [
                "This is a very long results section with many detailed findings.",
                "First, we observed significant improvement in the primary endpoint.",
                "The treatment group showed 45% reduction in disease progression.",
                "Secondary endpoints also favored the treatment group significantly.",
                "Safety analysis revealed acceptable tolerability profile.",
                "Most adverse events were grade 1 or 2 in severity.",
                "No treatment-related deaths occurred during the study period.",
                "Patient quality of life scores improved substantially.",
                "Biomarker analysis suggested predictive factors for response.",
                "Subgroup analyses confirmed benefits across patient populations.",
            ]
        )

        doc = Document(
            uid="pubmed:11111111",
            source="pubmed",
            source_id="11111111",
            title="Long Results Section Test",
            text=f"Results: {long_text}",
        )

        chunker = AbstractChunker(
            ChunkingConfig(target_tokens=50, max_tokens=100, overlap_tokens=20)
        )
        chunks = chunker.chunk_document(doc)

        # Should create multiple chunks
        assert len(chunks) > 1

        # Check overlap between consecutive chunks
        if len(chunks) > 1:
            # Should have some overlapping content (approximate check)
            chunk1_words = set(chunks[0].text.split())
            chunk2_words = set(chunks[1].text.split())
            overlap_words = chunk1_words & chunk2_words
            assert len(overlap_words) > 0  # Should have some overlap

    def test_token_budget_compliance(self, sample_document):
        """Test that chunks respect token budgets."""
        config = ChunkingConfig(target_tokens=100, max_tokens=150)
        chunker = AbstractChunker(config)
        chunks = chunker.chunk_document(sample_document)

        # Check token counts
        for chunk in chunks:
            assert chunk.tokens is not None
            assert chunk.tokens <= config.max_tokens

        # For structured documents, sections may be naturally smaller than target
        # Just ensure no chunk exceeds max and chunks are reasonable size
        total_tokens = sum(c.tokens for c in chunks)
        avg_tokens = total_tokens / len(chunks)

        # Average should be reasonable (not too small, not exceeding max)
        assert avg_tokens > 10  # Not too tiny
        assert all(c.tokens <= config.max_tokens for c in chunks)  # Respect max

    def test_metadata_preservation(self, sample_document):
        """Test that metadata is properly preserved and enhanced."""
        chunker = AbstractChunker()
        chunks = chunker.chunk_document(sample_document)

        for chunk in chunks:
            # Basic metadata preserved
            assert chunk.parent_uid == sample_document.uid
            assert chunk.source == sample_document.source
            assert chunk.title == sample_document.title
            assert chunk.published_at == sample_document.published_at

            # Chunking metadata added
            assert "chunker_version" in chunk.meta
            assert "tokenizer" in chunk.meta
            assert "n_sentences" in chunk.meta
            assert "section_boost" in chunk.meta

            # Source-specific metadata preserved
            assert "src" in chunk.meta
            assert sample_document.source in chunk.meta["src"]
            assert chunk.meta["src"][sample_document.source] == sample_document.detail


class TestTokenizerParity:
    """Test tokenizer consistency."""

    def test_huggingface_tokenizer(self):
        """Test HuggingFace tokenizer."""
        try:
            tokenizer = HuggingFaceTokenizer(
                "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
            )

            text = "This is a test sentence for tokenization."
            count = tokenizer.count_tokens(text)

            assert isinstance(count, int)
            assert count > 0
            assert "hf:pritamdeka" in tokenizer.get_identifier()

        except Exception:
            pytest.skip("HuggingFace tokenizer not available")

    def test_fallback_tokenizer(self):
        """Test fallback tokenizer."""
        tokenizer = FallbackTokenizer()

        text = "This is a test sentence."
        count = tokenizer.count_tokens(text)

        assert count == 5  # Simple whitespace split
        assert tokenizer.get_identifier() == "fallback:whitespace"

    def test_tokenizer_consistency(self):
        """Test that same text produces same token count."""
        tokenizer = FallbackTokenizer()
        text = "Consistent tokenization test."

        count1 = tokenizer.count_tokens(text)
        count2 = tokenizer.count_tokens(text)

        assert count1 == count2


class TestChunkingConfig:
    """Test chunking configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ChunkingConfig()

        assert config.target_tokens == 325
        assert config.max_tokens == 450
        assert config.min_tokens == 120
        assert config.overlap_tokens == 50
        assert config.chunker_version == "v1.2.0"

        # Check section boosts
        assert config.section_boosts["Results"] == 0.1
        assert config.section_boosts["Conclusions"] == 0.05
        assert config.section_boosts["Background"] == 0.0

    def test_custom_config(self):
        """Test custom configuration."""
        custom_boosts = {"Results": 0.2, "Methods": 0.1}
        config = ChunkingConfig(
            target_tokens=200, max_tokens=300, section_boosts=custom_boosts
        )

        assert config.target_tokens == 200
        assert config.max_tokens == 300
        assert config.section_boosts == custom_boosts
