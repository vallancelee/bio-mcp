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
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from bio_mcp.config.logging_config import get_logger
from bio_mcp.models.document import Chunk, Document, MetadataBuilder

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
    section_boosts: dict[str, float] = None
    
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
        try:
            from transformers import AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        except Exception as e:
            logger.warning(f"Failed to load HuggingFace tokenizer {model_name}: {e}")
            raise
        
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
    sentences: list[str] # Sentences in this window
    tokens: int         # Token count


class SectionDetector:
    """Detects sections in biomedical abstracts."""
    
    # Common section headings in PubMed abstracts
    SECTION_PATTERNS: ClassVar[list[str]] = [
        # Standard IMRAD sections
        r'^\s*(Background|Introduction|Rationale)\s*[:\-]',
        r'^\s*(Objective|Aim|Purpose|Goal)s?\s*[:\-]',
        r'^\s*(Methods?|Materials?|Design|Setting|Participants?)\s*[:\-]',
        r'^\s*(Interventions?|Main Outcome Measures?)\s*[:\-]',
        r'^\s*(Results?|Findings?|Outcomes?)\s*[:\-]',
        r'^\s*(Conclusions?|Interpretation|Implications?)\s*[:\-]',
        r'^\s*(Limitations?|Study Limitations?)\s*[:\-]',
    ]
    
    def detect_sections(self, text: str) -> list[Section]:
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
            section_content = re.sub(r'^\s*[^:\-]*[:\-]\s*', '', section_content, flags=re.MULTILINE)
            
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
        clean = re.sub(r'[:\-\s]+', '', heading).strip()
        
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
        # Try to load spacy model
        self.nlp = None
        try:
            import spacy
            self.nlp = spacy.load("en_core_web_sm")
            logger.debug("Loaded spaCy model for sentence splitting")
        except Exception as e:
            logger.warning(f"spaCy model not available ({e}), using fallback sentence splitter")
    
    def split_sentences(self, text: str) -> list[str]:
        """Split text into sentences, handling biomedical patterns."""
        if self.nlp:
            return self._spacy_split(text)
        else:
            return self._fallback_split(text)
    
    def _spacy_split(self, text: str) -> list[str]:
        """Use spaCy for sentence splitting."""
        doc = self.nlp(text)
        sentences = []
        
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if sent_text:
                sentences.append(sent_text)
        
        return sentences
    
    def _fallback_split(self, text: str) -> list[str]:
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
    def needs_expansion(sentences: list[str], split_idx: int) -> bool:
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
            r'Δ\s*=\s*[-]?\d+\.\d+',        # delta changes
        ]
        
        current_has_stats = any(re.search(pattern, current_sent, re.IGNORECASE) 
                              for pattern in stat_patterns)
        next_has_context = any(word in next_sent.lower() 
                             for word in ['compared', 'versus', 'vs', 'control', 'placebo', 'baseline', 'group'])
        
        # Also check if current sentence has numerical values and next has comparison context
        has_numbers = re.search(r'\d+\.\d+', current_sent)
        has_comparison_context = any(word in next_sent.lower() for word in ['compared', 'versus', 'vs', 'control', 'group', 'months'])
        
        return (current_has_stats and next_has_context) or (has_numbers and has_comparison_context)
    
    @staticmethod 
    def expand_window(sentences: list[str], start_idx: int, end_idx: int, tokenizer: BaseTokenizer, max_tokens: int) -> tuple[int, int]:
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
            from bio_mcp.config.config import config
            # Use BioBERT model for tokenization to match vectorizer
            return HuggingFaceTokenizer(config.biobert_model_name)
        except Exception as e:
            logger.warning(f"Failed to load HF tokenizer: {e}, using fallback")
            return FallbackTokenizer()
    
    def chunk_document(self, document: Document) -> list[Chunk]:
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
        
        # Join hyphenated line breaks (but preserve other line breaks)
        normalized = re.sub(r'-\s*\n\s*', '', normalized)
        
        # Collapse multiple spaces within lines (but preserve single line breaks)
        normalized = re.sub(r'[ \t]+', ' ', normalized)
        
        # Normalize line breaks but don't completely remove them
        normalized = re.sub(r'\n\s*\n', '\n', normalized)  # Remove empty lines
        
        # Clean up common patterns
        normalized = re.sub(r'\s+([.!?])', r'\1', normalized)  # Space before punctuation
        
        return normalized.strip()
    
    def _chunk_section(self, document: Document, section: Section, section_idx: int, start_chunk_idx: int) -> list[Chunk]:
        """Chunk a single section."""
        # Split into sentences
        sentences = self.sentence_splitter.split_sentences(section.content)
        
        if not sentences:
            return []
        
        # Check if entire section fits in one chunk
        section_tokens = self.tokenizer.count_tokens(section.content)
        
        if section_tokens <= self.config.max_tokens:
            # Single chunk for this section  
            all_sections = self.section_detector.detect_sections(document.text)
            chunk_id = f"s{section_idx}" if len(all_sections) > 1 else "w0"
            
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
    
    def _create_windows(self, document: Document, section: Section, sentences: list[str], 
                       section_idx: int, start_chunk_idx: int) -> list[Chunk]:
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
    
    def _find_window_end(self, sentences: list[str], start: int, target_tokens: int, max_tokens: int) -> int:
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
    
    def _calculate_overlap_start(self, sentences: list[str], window_end: int, overlap_tokens: int) -> int:
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
                     text: str, section: Section, sentences: list[str], tokens: int) -> Chunk:
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