# RAG Step 2: Section-Aware Chunking Strategy

**Objective:** Implement advanced section-aware chunking with token budgets, overlap, numeric safety, and deterministic chunk IDs optimized for PubMed abstracts.

**Success Criteria:**
- Section detection (Background/Methods/Results/Conclusions)
- Token budgets: 250-350 target, 450 max, 50-token overlap
- Numeric safety expansion for statistical claims  
- Deterministic chunk IDs (s0, s1, w0, w1)
- Sentence-aware splitting with proper boundaries
- 100% test coverage with golden datasets

---

## 1. Core Chunking Implementation

### 1.1 Advanced Chunker Class
**File:** `src/bio_mcp/services/chunking.py`

```python
"""
Section-aware chunking service optimized for PubMed abstracts.

Implements the chunking strategy from CHUNKING_STRATEGY.md with:
- Section detection (Background/Methods/Results/Conclusions)  
- Token budgets with overlap
- Numeric safety expansion
- Deterministic chunk IDs
"""

import re
import unicodedata
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

import spacy
from transformers import AutoTokenizer

from bio_mcp.models.document import Document, Chunk, MetadataBuilder
from bio_mcp.config.logging_config import get_logger

logger = get_logger(__name__)

@dataclass 
class ChunkingConfig:
    """Configuration for chunking parameters."""
    target_tokens: int = 325  # Target tokens per chunk
    max_tokens: int = 450     # Hard maximum tokens
    min_tokens: int = 120     # Minimum section size before chunking
    overlap_tokens: int = 50  # Overlap for long sections
    chunker_version: str = "v1.2.0"
    
    # Section boost weights for search
    section_boosts: Dict[str, float] = None
    
    def __post_init__(self):
        if self.section_boosts is None:
            self.section_boosts = {
                "Results": 0.1,
                "Conclusions": 0.05,
                "Background": 0.0,
                "Methods": 0.0,
                "Objective": 0.0,
                "Unstructured": 0.0
            }

class BaseTokenizer(ABC):
    """Abstract tokenizer interface."""
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        pass
    
    @abstractmethod
    def get_identifier(self) -> str:
        """Get tokenizer identifier for metadata."""
        pass

class HuggingFaceTokenizer(BaseTokenizer):
    """Tokenizer using HuggingFace transformers."""
    
    def __init__(self, model_name: str = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"):
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        
    def count_tokens(self, text: str) -> int:
        """Count tokens using HF tokenizer."""
        return len(self.tokenizer.encode(text, add_special_tokens=False))
    
    def get_identifier(self) -> str:
        """Get tokenizer identifier."""
        return f"hf:{self.model_name}"

class FallbackTokenizer(BaseTokenizer):
    """Simple fallback tokenizer for testing."""
    
    def count_tokens(self, text: str) -> int:
        """Rough token count approximation."""
        return len(text.split())
    
    def get_identifier(self) -> str:
        """Get tokenizer identifier."""
        return "fallback:whitespace"

@dataclass
class Section:
    """Detected section in abstract."""
    name: str           # "Background", "Methods", etc.
    content: str        # Section text content
    start_pos: int      # Character start position
    end_pos: int        # Character end position

@dataclass
class TextWindow:
    """Text window for chunking."""
    content: str        # Window text
    start_pos: int      # Start position in original text
    end_pos: int        # End position in original text  
    sentences: List[str] # Sentences in this window
    tokens: int         # Token count

class SectionDetector:
    """Detects sections in biomedical abstracts."""
    
    # Common section headings in PubMed abstracts
    SECTION_PATTERNS = [
        # Standard IMRAD sections
        r'^\s*(Background|Introduction|Rationale)\s*[:\-–]',
        r'^\s*(Objective|Aim|Purpose|Goal)s?\s*[:\-–]',
        r'^\s*(Methods?|Materials?|Design|Setting|Participants?)\s*[:\-–]',
        r'^\s*(Interventions?|Main Outcome Measures?)\s*[:\-–]',
        r'^\s*(Results?|Findings?|Outcomes?)\s*[:\-–]',
        r'^\s*(Conclusions?|Interpretation|Implications?)\s*[:\-–]',
        r'^\s*(Limitations?|Study Limitations?)\s*[:\-–]',
    ]
    
    def detect_sections(self, text: str) -> List[Section]:
        """Detect sections in abstract text."""
        sections = []
        
        # Combine all patterns for detection
        combined_pattern = '|'.join(f'({pattern})' for pattern in self.SECTION_PATTERNS)
        
        matches = list(re.finditer(combined_pattern, text, re.MULTILINE | re.IGNORECASE))
        
        if not matches:
            # Unstructured abstract
            return [Section(
                name="Unstructured",
                content=text.strip(),
                start_pos=0,
                end_pos=len(text)
            )]
        
        # Extract sections between matches
        for i, match in enumerate(matches):
            section_start = match.start()
            section_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            
            # Extract section name from match
            section_name = self._extract_section_name(match.group(0))
            section_content = text[section_start:section_end].strip()
            
            # Remove the heading from content
            section_content = re.sub(r'^\s*[^:\-–]*[:\-–]\s*', '', section_content, flags=re.MULTILINE)
            
            if section_content:  # Only add non-empty sections
                sections.append(Section(
                    name=section_name,
                    content=section_content,
                    start_pos=section_start,
                    end_pos=section_end
                ))
        
        return sections
    
    def _extract_section_name(self, heading: str) -> str:
        """Extract clean section name from heading."""
        # Remove punctuation and whitespace
        clean = re.sub(r'[:\-–\s]+', '', heading).strip()
        
        # Normalize common variations
        name_mapping = {
            'background': 'Background',
            'introduction': 'Background', 
            'rationale': 'Background',
            'objective': 'Objective',
            'objectives': 'Objective',
            'aim': 'Objective',
            'aims': 'Objective', 
            'purpose': 'Objective',
            'goal': 'Objective',
            'goals': 'Objective',
            'methods': 'Methods',
            'method': 'Methods',
            'materials': 'Methods',
            'design': 'Methods',
            'setting': 'Methods',
            'participants': 'Methods',
            'participant': 'Methods',
            'interventions': 'Methods',
            'intervention': 'Methods',
            'measures': 'Methods',
            'results': 'Results',
            'result': 'Results',
            'findings': 'Results',
            'finding': 'Results',
            'outcomes': 'Results',
            'outcome': 'Results',
            'conclusions': 'Conclusions',
            'conclusion': 'Conclusions',
            'interpretation': 'Conclusions',
            'implications': 'Conclusions',
            'implication': 'Conclusions',
            'limitations': 'Conclusions',
            'limitation': 'Conclusions'
        }
        
        return name_mapping.get(clean.lower(), clean.title())

class SentenceSplitter:
    """Sentence splitter optimized for biomedical text."""
    
    def __init__(self):
        # Load spacy model for sentence splitting
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model not found, using fallback sentence splitter")
            self.nlp = None
    
    def split_sentences(self, text: str) -> List[str]:
        """Split text into sentences, handling biomedical patterns."""
        if self.nlp:
            return self._spacy_split(text)
        else:
            return self._fallback_split(text)
    
    def _spacy_split(self, text: str) -> List[str]:
        """Use spaCy for sentence splitting."""
        doc = self.nlp(text)
        sentences = []
        
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if sent_text:
                sentences.append(sent_text)
        
        return sentences
    
    def _fallback_split(self, text: str) -> List[str]:
        """Fallback sentence splitter for biomedical text."""
        # Simple regex-based splitting with biomedical awareness
        
        # Protect common abbreviations and numbers
        protected = text
        
        # Protect decimal numbers, percentages, p-values
        protected = re.sub(r'(\d+\.\d+)', r'__DECIMAL__\1__', protected)
        protected = re.sub(r'(p\s*[=<>]\s*0\.\d+)', r'__PVALUE__\1__', protected)
        protected = re.sub(r'(\d+\s*mg/kg)', r'__DOSE__\1__', protected)
        protected = re.sub(r'(vs\.|vs)', r'__VS__', protected)
        
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', protected)
        
        # Restore protected patterns
        restored_sentences = []
        for sent in sentences:
            restored = sent
            restored = re.sub(r'__DECIMAL__([^_]+)__', r'\1', restored)
            restored = re.sub(r'__PVALUE__([^_]+)__', r'\1', restored)  
            restored = re.sub(r'__DOSE__([^_]+)__', r'\1', restored)
            restored = re.sub(r'__VS__', r'vs', restored)
            
            if restored.strip():
                restored_sentences.append(restored.strip())
        
        return restored_sentences

class NumericSafetyExpander:
    """Expands chunks to preserve numerical claims and comparisons."""
    
    @staticmethod
    def needs_expansion(sentences: List[str], split_idx: int) -> bool:
        """Check if split would separate important numeric claims."""
        if split_idx >= len(sentences):
            return False
            
        # Check if split would separate statistics from context
        current_sent = sentences[split_idx - 1] if split_idx > 0 else ""
        next_sent = sentences[split_idx] if split_idx < len(sentences) else ""
        
        # Patterns that indicate statistical content
        stat_patterns = [
            r'p\s*[=<>]\s*0\.\d+',           # p-values
            r'\d+\.\d+%',                     # percentages
            r'\d+\.\d+\s*mg/kg',             # dosages
            r'CI\s*[=:]\s*\d+\.\d+',         # confidence intervals
            r'vs\.?\s+\d+\.\d+',             # versus comparisons
            r'compared\s+to\s+\d+\.\d+',     # comparisons
            r'Δ\s*=\s*[−-]?\d+\.\d+',        # delta changes
        ]
        
        current_has_stats = any(re.search(pattern, current_sent, re.IGNORECASE) 
                              for pattern in stat_patterns)
        next_has_context = any(word in next_sent.lower() 
                             for word in ['compared', 'versus', 'vs', 'control', 'placebo', 'baseline'])
        
        return current_has_stats and next_has_context
    
    @staticmethod 
    def expand_window(sentences: List[str], start_idx: int, end_idx: int, tokenizer: BaseTokenizer, max_tokens: int) -> Tuple[int, int]:
        """Expand window boundaries to preserve numeric claims."""
        expanded_start = start_idx
        expanded_end = end_idx
        
        # Try expanding forward first (more important for Results/Conclusions)
        if expanded_end < len(sentences):
            test_window = sentences[expanded_start:expanded_end + 1]
            test_text = " ".join(test_window)
            
            if (tokenizer.count_tokens(test_text) <= max_tokens and 
                NumericSafetyExpander.needs_expansion(sentences, expanded_end)):
                expanded_end += 1
        
        # Try expanding backward if still room
        if expanded_start > 0:
            test_window = sentences[expanded_start - 1:expanded_end]  
            test_text = " ".join(test_window)
            
            if (tokenizer.count_tokens(test_text) <= max_tokens and
                NumericSafetyExpander.needs_expansion(sentences, expanded_start)):
                expanded_start -= 1
        
        return expanded_start, expanded_end

class AbstractChunker:
    """Main chunking service for biomedical abstracts."""
    
    def __init__(self, config: ChunkingConfig = None, tokenizer: BaseTokenizer = None):
        self.config = config or ChunkingConfig()
        self.tokenizer = tokenizer or self._create_default_tokenizer()
        self.section_detector = SectionDetector()
        self.sentence_splitter = SentenceSplitter()
        self.safety_expander = NumericSafetyExpander()
    
    def _create_default_tokenizer(self) -> BaseTokenizer:
        """Create default tokenizer."""
        try:
            return HuggingFaceTokenizer()
        except Exception as e:
            logger.warning(f"Failed to load HF tokenizer: {e}, using fallback")
            return FallbackTokenizer()
    
    def chunk_document(self, document: Document) -> List[Chunk]:
        """Chunk a document into optimized chunks."""
        logger.info("Chunking document", document_uid=document.uid)
        
        # Normalize text
        normalized_text = self._normalize_text(document.text)
        
        # Detect sections
        sections = self.section_detector.detect_sections(normalized_text)
        logger.debug(f"Detected {len(sections)} sections", 
                    sections=[s.name for s in sections])
        
        # Generate chunks
        chunks = []
        chunk_idx = 0
        
        for section_idx, section in enumerate(sections):
            section_chunks = self._chunk_section(
                document, section, section_idx, chunk_idx
            )
            chunks.extend(section_chunks)
            chunk_idx += len(section_chunks)
        
        # Add title prefix to first chunk only
        if chunks:
            chunks[0] = self._add_title_prefix(document, chunks[0])
        
        logger.info(f"Generated {len(chunks)} chunks", 
                   document_uid=document.uid, 
                   avg_tokens=sum(c.tokens or 0 for c in chunks) / len(chunks) if chunks else 0)
        
        return chunks
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent processing."""
        # Unicode normalization
        normalized = unicodedata.normalize('NFKC', text)
        
        # Collapse multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Join hyphenated line breaks
        normalized = re.sub(r'-\s*\n\s*', '', normalized)
        
        # Clean up common patterns
        normalized = re.sub(r'\s+([.!?])', r'\1', normalized)  # Space before punctuation
        
        return normalized.strip()
    
    def _chunk_section(self, document: Document, section: Section, section_idx: int, start_chunk_idx: int) -> List[Chunk]:
        """Chunk a single section."""
        # Split into sentences
        sentences = self.sentence_splitter.split_sentences(section.content)
        
        if not sentences:
            return []
        
        # Check if entire section fits in one chunk
        section_tokens = self.tokenizer.count_tokens(section.content)
        
        if section_tokens <= self.config.max_tokens:
            # Single chunk for this section
            chunk_id = f"s{section_idx}" if len(self.section_detector.detect_sections(document.text)) > 1 else "w0"
            
            return [self._create_chunk(
                document=document,
                chunk_id=chunk_id,
                chunk_idx=start_chunk_idx,
                text=section.content,
                section=section,
                sentences=sentences,
                tokens=section_tokens
            )]
        
        # Multi-chunk section - use windowing
        return self._create_windows(document, section, sentences, section_idx, start_chunk_idx)
    
    def _create_windows(self, document: Document, section: Section, sentences: List[str], 
                       section_idx: int, start_chunk_idx: int) -> List[Chunk]:
        """Create overlapping windows from sentences."""
        windows = []
        current_start = 0
        window_idx = 0
        
        while current_start < len(sentences):
            # Find optimal window end
            window_end = self._find_window_end(
                sentences, current_start, self.config.target_tokens, self.config.max_tokens
            )
            
            # Apply numeric safety expansion
            expanded_start, expanded_end = self.safety_expander.expand_window(
                sentences, current_start, window_end, self.tokenizer, self.config.max_tokens
            )
            
            # Create window text
            window_sentences = sentences[expanded_start:expanded_end]
            window_text = " ".join(window_sentences)
            window_tokens = self.tokenizer.count_tokens(window_text)
            
            # Generate chunk ID
            if len(self.section_detector.detect_sections(document.text)) > 1:
                chunk_id = f"s{section_idx}_{window_idx}"
            else:
                chunk_id = f"w{window_idx}"
            
            # Create chunk
            chunk = self._create_chunk(
                document=document,
                chunk_id=chunk_id,
                chunk_idx=start_chunk_idx + window_idx,
                text=window_text,
                section=section,
                sentences=window_sentences,
                tokens=window_tokens
            )
            windows.append(chunk)
            
            # Calculate next start with overlap
            next_start = self._calculate_overlap_start(
                sentences, expanded_end, self.config.overlap_tokens
            )
            
            if next_start <= current_start:  # Prevent infinite loop
                break
                
            current_start = next_start
            window_idx += 1
        
        return windows
    
    def _find_window_end(self, sentences: List[str], start: int, target_tokens: int, max_tokens: int) -> int:
        """Find optimal end position for a window."""
        current_tokens = 0
        end_idx = start
        
        for i in range(start, len(sentences)):
            sentence_tokens = self.tokenizer.count_tokens(sentences[i])
            
            if current_tokens + sentence_tokens > max_tokens:
                break
                
            current_tokens += sentence_tokens
            end_idx = i + 1
            
            if current_tokens >= target_tokens:
                break
        
        return end_idx
    
    def _calculate_overlap_start(self, sentences: List[str], window_end: int, overlap_tokens: int) -> int:
        """Calculate start position for next window with overlap."""
        if overlap_tokens <= 0 or window_end >= len(sentences):
            return window_end
        
        # Find sentences that fit in overlap
        overlap_token_count = 0
        overlap_start = window_end
        
        for i in range(window_end - 1, -1, -1):
            sentence_tokens = self.tokenizer.count_tokens(sentences[i])
            
            if overlap_token_count + sentence_tokens > overlap_tokens:
                break
            
            overlap_token_count += sentence_tokens
            overlap_start = i
        
        return overlap_start
    
    def _create_chunk(self, document: Document, chunk_id: str, chunk_idx: int, 
                     text: str, section: Section, sentences: List[str], tokens: int) -> Chunk:
        """Create a Chunk instance."""
        
        # Build metadata
        meta = MetadataBuilder.build_chunk_metadata(
            chunker_version=self.config.chunker_version,
            tokenizer=self.tokenizer.get_identifier(), 
            source_specific=document.detail,
            source=document.source
        )
        
        # Add chunking-specific metadata
        meta.update({
            "n_sentences": len(sentences),
            "section_boost": self.config.section_boosts.get(section.name, 0.0)
        })
        
        return Chunk(
            chunk_id=chunk_id,
            uuid=Chunk.generate_uuid(document.uid, chunk_id),
            parent_uid=document.uid,
            source=document.source,
            chunk_idx=chunk_idx,
            text=text,
            title=document.title,
            section=section.name,
            published_at=document.published_at,
            tokens=tokens,
            n_sentences=len(sentences),
            meta=meta
        )
    
    def _add_title_prefix(self, document: Document, first_chunk: Chunk) -> Chunk:
        """Add title prefix to first chunk only."""
        if not document.title:
            return first_chunk
        
        # Create formatted text with title and section
        title_prefix = f"[Title] {document.title}"
        if first_chunk.section and first_chunk.section != "Unstructured":
            title_prefix += f"\n[Section] {first_chunk.section}"
        
        prefixed_text = f"{title_prefix}\n[Text] {first_chunk.text}"
        
        # Recompute tokens
        new_tokens = self.tokenizer.count_tokens(prefixed_text)
        
        # Create new chunk with updated text and token count
        return Chunk(
            chunk_id=first_chunk.chunk_id,
            uuid=first_chunk.uuid,
            parent_uid=first_chunk.parent_uid,
            source=first_chunk.source,
            chunk_idx=first_chunk.chunk_idx,
            text=prefixed_text,
            title=first_chunk.title,
            section=first_chunk.section,
            published_at=first_chunk.published_at,
            tokens=new_tokens,
            n_sentences=first_chunk.n_sentences,
            meta=first_chunk.meta
        )
```

---

## 2. Testing Implementation  

### 2.1 Golden Dataset Tests
**File:** `tests/unit/services/test_chunking.py`

```python
import pytest
from datetime import datetime
from bio_mcp.services.chunking import (
    AbstractChunker, ChunkingConfig, SectionDetector, 
    SentenceSplitter, NumericSafetyExpander, HuggingFaceTokenizer, FallbackTokenizer
)
from bio_mcp.models.document import Document

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
        assert "Conclusions" in section_names  # Interpretation should map to Conclusions

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
        assert "vs. placebo" in sentences[0]
        assert "p=0.001" in sentences[0]

class TestNumericSafetyExpander:
    """Test numeric safety expansion logic."""
    
    def test_needs_expansion_detection(self):
        """Test detection of splits that need expansion."""
        sentences = [
            "Overall survival was 12.1 months (95% CI 8.2-16.0).",
            "This compared favorably to the control group of 8.4 months.",
            "The difference was statistically significant (p<0.001)."
        ]
        
        # Should detect need for expansion at position 1
        assert NumericSafetyExpander.needs_expansion(sentences, 1) == True
        
        # Should not need expansion at position 2 
        assert NumericSafetyExpander.needs_expansion(sentences, 2) == False
    
    def test_window_expansion(self):
        """Test window expansion logic."""
        sentences = [
            "Treatment group showed improvement.",
            "Mean reduction was 15.2% (SD 4.1).", 
            "Control group showed 3.1% reduction.",
            "The difference was significant (p=0.02).",
            "No serious adverse events occurred."
        ]
        
        tokenizer = FallbackTokenizer()
        
        # Test expansion around statistical claim
        start, end = NumericSafetyExpander.expand_window(
            sentences, 1, 2, tokenizer, max_tokens=100
        )
        
        # Should expand to include context
        assert start <= 1
        assert end >= 3  # Include significance test

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
            text="""
            Background: Advanced melanoma has limited treatment options with poor survival outcomes.
            Objective: To evaluate the efficacy and safety of pembrolizumab versus chemotherapy.
            Methods: We conducted a randomized, double-blind, phase III trial involving 834 patients with advanced melanoma. Patients were randomly assigned to receive pembrolizumab or chemotherapy.
            Results: The median overall survival was 25.0 months with pembrolizumab versus 13.8 months with chemotherapy (hazard ratio 0.73, 95% CI 0.61-0.88, p=0.001). Progression-free survival was also significantly improved (5.6 vs 2.8 months, HR 0.69, p<0.001).
            Conclusions: Pembrolizumab significantly improved survival outcomes compared to chemotherapy in patients with advanced melanoma. The safety profile was acceptable with manageable adverse events.
            """,
            published_at=datetime(2024, 1, 15),
            detail={
                "journal": "New England Journal of Medicine",
                "mesh_terms": ["Melanoma", "Immunotherapy", "Pembrolizumab"]
            }
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
        assert all(cid.startswith('s') for cid in chunk_ids)  # Section-based IDs
        
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
        long_text = " ".join([
            "This is a very long results section with many detailed findings.",
            "First, we observed significant improvement in the primary endpoint.",
            "The treatment group showed 45% reduction in disease progression.",
            "Secondary endpoints also favored the treatment group significantly.",
            "Safety analysis revealed acceptable tolerability profile.",
            "Most adverse events were grade 1 or 2 in severity.",
            "No treatment-related deaths occurred during the study period.",
            "Patient quality of life scores improved substantially.",
            "Biomarker analysis suggested predictive factors for response.",
            "Subgroup analyses confirmed benefits across patient populations."
        ])
        
        doc = Document(
            uid="pubmed:11111111",
            source="pubmed",
            source_id="11111111", 
            title="Long Results Section Test",
            text=f"Results: {long_text}",
        )
        
        chunker = AbstractChunker(ChunkingConfig(target_tokens=50, max_tokens=100, overlap_tokens=20))
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
        
        # Most chunks should be near target (except possibly last)
        target_compliant = sum(1 for c in chunks[:-1] if c.tokens >= config.target_tokens * 0.8)
        assert target_compliant >= len(chunks) // 2  # At least half should be near target
    
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
            tokenizer = HuggingFaceTokenizer("pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb")
            
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
```

### 2.2 Performance Tests
**File:** `tests/performance/test_chunking_performance.py`

```python
import time
import pytest
from bio_mcp.services.chunking import AbstractChunker, ChunkingConfig
from bio_mcp.models.document import Document

class TestChunkingPerformance:
    """Test chunking performance requirements."""
    
    @pytest.fixture
    def large_document(self):
        """Create a large document for performance testing."""
        # Generate ~2000 word abstract
        content = " ".join([
            f"This is sentence {i} in a long biomedical abstract containing detailed methodology and results."
            for i in range(200)
        ])
        
        return Document(
            uid="pubmed:99999999",
            source="pubmed",
            source_id="99999999",
            title="Large Performance Test Document",
            text=content
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
```

---

## 3. Integration with Document Pipeline

### 3.1 Chunking Service Integration
**File:** `src/bio_mcp/services/services.py` (additions)

```python
from bio_mcp.services.chunking import AbstractChunker, ChunkingConfig

class VectorService:
    """Enhanced VectorService with new chunking."""
    
    def __init__(self, chunking_config: ChunkingConfig = None):
        self.embedding_service = EmbeddingService()
        self.chunker = AbstractChunker(chunking_config)
        self._initialized = False
    
    async def store_document_chunks(self, document: Document) -> list[str]:
        """Store document using advanced chunking strategy."""
        if not self._initialized:
            await self.initialize()
        
        logger.info("Processing document with advanced chunking", document_uid=document.uid)
        
        # Use new chunker
        chunks = self.chunker.chunk_document(document)
        
        if not chunks:
            logger.warning("No chunks generated", document_uid=document.uid)
            return []
        
        # Store chunks using embedding service
        chunk_uuids = await self.embedding_service.store_chunks(chunks)
        
        logger.info("Document chunked and stored", 
                   document_uid=document.uid,
                   chunk_count=len(chunks),
                   avg_tokens=sum(c.tokens or 0 for c in chunks) / len(chunks))
        
        return chunk_uuids
```

---

## 4. Configuration and Deployment

### 4.1 Configuration Updates
**File:** `.env.example` (additions)

```bash
# Chunking configuration
BIO_MCP_CHUNKER_TARGET_TOKENS=325
BIO_MCP_CHUNKER_MAX_TOKENS=450  
BIO_MCP_CHUNKER_MIN_TOKENS=120
BIO_MCP_CHUNKER_OVERLAP_TOKENS=50
BIO_MCP_CHUNKER_VERSION=v1.2.0

# Tokenizer configuration
BIO_MCP_TOKENIZER_MODEL=pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb
BIO_MCP_TOKENIZER_FALLBACK=true
```

### 4.2 Make Targets
**File:** `Makefile` (additions)

```makefile
# Chunking tests and validation
test-chunking:  ## Run chunking-specific tests
	$(UV) run pytest tests/unit/services/test_chunking.py -v

test-chunking-perf:  ## Run chunking performance tests  
	$(UV) run pytest tests/performance/test_chunking_performance.py -v

validate-chunking:  ## Validate chunking on sample data
	$(UV) run python -m scripts.validate_chunking --sample-size 10

benchmark-chunking:  ## Benchmark chunking performance
	$(UV) run python -m scripts.benchmark_chunking --iterations 100
```

---

## 5. Success Validation

### 5.1 Validation Checklist
- [ ] Section detection works for structured and unstructured abstracts
- [ ] Token budgets are respected (target 250-350, max 450)
- [ ] Overlap functionality works for long sections
- [ ] Numeric safety expansion prevents claim separation
- [ ] Deterministic chunk IDs generated consistently
- [ ] UUIDs are stable across re-runs
- [ ] Metadata preservation and enhancement works
- [ ] Performance targets met (<1s for large documents)
- [ ] Tokenizer parity with embedding model
- [ ] 100% test coverage achieved

### 5.2 Quality Metrics
- Average chunk size: 250-350 tokens
- Overlap coverage: 50 tokens for multi-chunk sections  
- Section detection accuracy: >95% on structured abstracts
- Numeric claim preservation: 100% (no separated statistics)
- UUID generation: <0.1ms per chunk
- End-to-end chunking: <1s per document

---

## Next Steps

After completing this step:
1. Proceed to **RAG_STEP_3_WEAVIATE.md** for new collection schema
2. Update embedding pipeline to use new chunking
3. Validate chunking quality on representative PubMed sample

**Estimated Time:** 2-3 days  
**Dependencies:** RAG_STEP_1_MODELS.md completed
**Risk Level:** Medium (complex logic, but well-tested)