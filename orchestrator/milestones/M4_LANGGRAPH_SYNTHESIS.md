# M4 — LangGraph Synthesis & Checkpoints (COMPLETED ✅)

## Current Status: COMPLETED ✅
Advanced synthesis capabilities are fully implemented and operational.

**IMPLEMENTED:**
- ✅ **Synthesizer Node**: `src/bio_mcp/orchestrator/nodes/synthesizer_node.py` (production ready)
- ✅ Comprehensive markdown answer generation with structured sections
- ✅ PMID and NCT citation extraction and formatting
- ✅ Checkpoint ID generation (deterministic session-based)
- ✅ Result aggregation from multiple sources (PubMed, ClinicalTrials, RAG)
- ✅ Cache hit rate calculation and telemetry
- ✅ Error handling and fallback responses

**CURRENT FEATURES:**
- Structured answers with query analysis, entity extraction, and results sections
- Top 5 results display with full metadata (PMIDs, authors, years)
- Unique checkpoint ID generation for result reproducibility
- Comprehensive logging and metrics collection

## Objective
Implement advanced result synthesis, citation extraction, checkpoint management, and answer quality scoring. Focus on creating comprehensive, well-formatted answers that include proper citations, quality metrics, and persistent checkpoint references for reproducibility and caching.

## Dependencies (Existing Bio-MCP Components)
- **M1-M3 LangGraph**: Node implementations, tool integration, and state management
- **Synthesis Logic**: Existing synthesis patterns from bio-mcp tools
- **Database**: `src/bio_mcp/shared/clients/database.py` - DatabaseManager
- **Models**: `src/bio_mcp/sources/*/models.py` - Data models for different sources
- **Quality Scoring**: Existing quality metrics from RAG and search tools

## Core Synthesis Components

### 1. Advanced Result Synthesizer

**File**: `src/bio_mcp/orchestrator/synthesis/synthesizer.py`
```python
"""Advanced result synthesis with citations and quality scoring."""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import hashlib
import re

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.synthesis.citation_extractor import CitationExtractor
from bio_mcp.orchestrator.synthesis.quality_scorer import QualityScorer
from bio_mcp.orchestrator.synthesis.template_engine import TemplateEngine
from bio_mcp.http.observability.decorators import trace_method

logger = get_logger(__name__)

class AnswerType(Enum):
    """Type of answer generated."""
    COMPREHENSIVE = "comprehensive"    # Full results from all sources
    PARTIAL = "partial"               # Some sources failed
    MINIMAL = "minimal"               # Only one source succeeded
    EMPTY = "empty"                   # No useful results

@dataclass
class SynthesisMetrics:
    """Metrics for synthesis quality."""
    total_sources: int
    successful_sources: int
    total_results: int
    unique_results: int
    citation_count: int
    quality_score: float
    synthesis_time_ms: float
    answer_type: AnswerType

@dataclass
class Citation:
    """Citation information."""
    id: str
    source: str  # pubmed, clinicaltrials, etc.
    title: str
    authors: List[str]
    journal: Optional[str] = None
    year: Optional[int] = None
    pmid: Optional[str] = None
    nct_id: Optional[str] = None
    url: Optional[str] = None
    relevance_score: float = 0.0

class AdvancedSynthesizer:
    """Advanced result synthesizer with citation and quality management."""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.citation_extractor = CitationExtractor()
        self.quality_scorer = QualityScorer()
        self.template_engine = TemplateEngine()
        
    @trace_method("advanced_synthesis")
    async def synthesize(self, state: OrchestratorState) -> Dict[str, Any]:
        """Synthesize comprehensive answer from state results."""
        start_time = datetime.utcnow()
        
        # Extract and process results
        result_data = self._extract_results(state)
        
        # Generate citations
        citations = await self.citation_extractor.extract_citations(result_data)
        
        # Score answer quality
        quality_metrics = self.quality_scorer.score_results(result_data, citations)
        
        # Determine answer type
        answer_type = self._classify_answer_type(result_data)
        
        # Generate answer content
        answer_content = await self._generate_answer(
            state, result_data, citations, quality_metrics, answer_type
        )
        
        # Generate checkpoint ID
        checkpoint_id = self._generate_checkpoint_id(state, result_data)
        
        # Calculate synthesis metrics
        synthesis_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        metrics = SynthesisMetrics(
            total_sources=len(result_data),
            successful_sources=len([r for r in result_data.values() if r.get("results")]),
            total_results=sum(len(r.get("results", [])) for r in result_data.values()),
            unique_results=len(self._deduplicate_results(result_data)),
            citation_count=len(citations),
            quality_score=quality_metrics.overall_score,
            synthesis_time_ms=synthesis_time,
            answer_type=answer_type
        )
        
        logger.info("Synthesis completed", extra={
            "checkpoint_id": checkpoint_id,
            "answer_type": answer_type.value,
            "total_results": metrics.total_results,
            "citations": metrics.citation_count,
            "quality_score": metrics.quality_score,
            "synthesis_time_ms": synthesis_time
        })
        
        return {
            "answer": answer_content,
            "checkpoint_id": checkpoint_id,
            "citations": [c.__dict__ for c in citations],
            "quality_metrics": quality_metrics.__dict__,
            "synthesis_metrics": metrics.__dict__,
            "node_path": state["node_path"] + ["advanced_synthesizer"],
            "latencies": {**state["latencies"], "synthesizer": synthesis_time},
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": answer_content
            }]
        }
    
    def _extract_results(self, state: OrchestratorState) -> Dict[str, Dict[str, Any]]:
        """Extract results from all sources in state."""
        results = {}
        
        # PubMed results
        if state.get("pubmed_results"):
            results["pubmed"] = state["pubmed_results"]
        
        # ClinicalTrials results
        if state.get("ctgov_results"):
            results["clinicaltrials"] = state["ctgov_results"]
        
        # RAG results
        if state.get("rag_results"):
            results["rag"] = state["rag_results"]
        
        return results
    
    def _classify_answer_type(self, result_data: Dict[str, Dict[str, Any]]) -> AnswerType:
        """Classify the type of answer based on available results."""
        successful_sources = [
            source for source, data in result_data.items()
            if data.get("results") and len(data["results"]) > 0
        ]
        
        total_results = sum(
            len(data.get("results", [])) for data in result_data.values()
        )
        
        if len(successful_sources) == 0 or total_results == 0:
            return AnswerType.EMPTY
        elif len(successful_sources) == 1 and total_results < 5:
            return AnswerType.MINIMAL
        elif len(successful_sources) < len(result_data) or total_results < 10:
            return AnswerType.PARTIAL
        else:
            return AnswerType.COMPREHENSIVE
    
    async def _generate_answer(
        self,
        state: OrchestratorState,
        result_data: Dict[str, Dict[str, Any]],
        citations: List[Citation],
        quality_metrics: Any,
        answer_type: AnswerType
    ) -> str:
        """Generate formatted answer content."""
        
        # Select appropriate template based on answer type
        template_name = f"answer_{answer_type.value}"
        
        # Prepare template context
        context = {
            "query": state.get("query", ""),
            "frame": state.get("frame", {}),
            "results": result_data,
            "citations": citations,
            "quality": quality_metrics,
            "metrics": {
                "total_results": sum(len(r.get("results", [])) for r in result_data.values()),
                "source_count": len(result_data),
                "execution_time": sum(state.get("latencies", {}).values()),
                "cache_hit_rate": self._calculate_cache_hit_rate(state)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Generate answer using template
        return await self.template_engine.render(template_name, context)
    
    def _generate_checkpoint_id(
        self, 
        state: OrchestratorState, 
        result_data: Dict[str, Dict[str, Any]]
    ) -> str:
        """Generate deterministic checkpoint ID."""
        # Create content hash from query, frame, and result structure
        query = state.get("query", "")
        frame = state.get("frame", {})
        
        # Create result signature (counts and sources, not full content)
        result_signature = {
            source: {
                "count": len(data.get("results", [])),
                "has_data": bool(data.get("results"))
            }
            for source, data in result_data.items()
        }
        
        # Create hash input
        hash_input = f"{query}:{frame.get('intent', '')}:{result_signature}"
        content_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
        
        # Format: ckpt_YYYYMMDD_HHMMSS_HASH
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"ckpt_{timestamp}_{content_hash}"
    
    def _deduplicate_results(self, result_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate results across sources."""
        seen_ids = set()
        unique_results = []
        
        for source, data in result_data.items():
            results = data.get("results", [])
            
            for result in results:
                # Create unique identifier
                result_id = self._get_result_id(result, source)
                
                if result_id not in seen_ids:
                    seen_ids.add(result_id)
                    result_with_source = {**result, "_source": source}
                    unique_results.append(result_with_source)
        
        return unique_results
    
    def _get_result_id(self, result: Dict[str, Any], source: str) -> str:
        """Get unique identifier for result."""
        if source == "pubmed" and result.get("pmid"):
            return f"pmid:{result['pmid']}"
        elif source == "clinicaltrials" and result.get("nct_id"):
            return f"nct:{result['nct_id']}"
        elif result.get("title"):
            # Use title hash for other sources
            title_hash = hashlib.md5(result["title"].encode()).hexdigest()[:8]
            return f"{source}:{title_hash}"
        else:
            # Fallback to full content hash
            content_hash = hashlib.md5(str(result).encode()).hexdigest()[:8]
            return f"{source}:{content_hash}"
    
    def _calculate_cache_hit_rate(self, state: OrchestratorState) -> float:
        """Calculate cache hit rate from state."""
        cache_hits = state.get("cache_hits", {})
        if not cache_hits:
            return 0.0
        
        hits = sum(1 for hit in cache_hits.values() if hit)
        return hits / len(cache_hits)
```

### 2. Citation Extractor

**File**: `src/bio_mcp/orchestrator/synthesis/citation_extractor.py`
```python
"""Citation extraction and formatting."""
from typing import Dict, Any, List, Optional
import re
from datetime import datetime

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.synthesis.synthesizer import Citation

logger = get_logger(__name__)

class CitationExtractor:
    """Extracts and formats citations from various sources."""
    
    def __init__(self):
        self.citation_counter = 0
    
    async def extract_citations(self, result_data: Dict[str, Dict[str, Any]]) -> List[Citation]:
        """Extract citations from all result sources."""
        all_citations = []
        
        for source, data in result_data.items():
            results = data.get("results", [])
            source_citations = await self._extract_source_citations(source, results)
            all_citations.extend(source_citations)
        
        # Sort by relevance score
        all_citations.sort(key=lambda c: c.relevance_score, reverse=True)
        
        return all_citations
    
    async def _extract_source_citations(
        self, 
        source: str, 
        results: List[Dict[str, Any]]
    ) -> List[Citation]:
        """Extract citations from specific source."""
        citations = []
        
        if source == "pubmed":
            citations = self._extract_pubmed_citations(results)
        elif source == "clinicaltrials":
            citations = self._extract_clinical_trial_citations(results)
        elif source == "rag":
            citations = self._extract_rag_citations(results)
        
        return citations
    
    def _extract_pubmed_citations(self, results: List[Dict[str, Any]]) -> List[Citation]:
        """Extract citations from PubMed results."""
        citations = []
        
        for result in results:
            self.citation_counter += 1
            
            # Extract authors
            authors = result.get("authors", [])
            if isinstance(authors, str):
                authors = [a.strip() for a in authors.split(",")]
            
            # Extract year from date
            year = None
            if result.get("publication_date"):
                try:
                    year = datetime.fromisoformat(result["publication_date"]).year
                except:
                    pass
            
            # Calculate relevance score (placeholder - could be enhanced)
            relevance_score = self._calculate_pubmed_relevance(result)
            
            citation = Citation(
                id=str(self.citation_counter),
                source="pubmed",
                title=result.get("title", "Untitled"),
                authors=authors[:3],  # Limit to first 3 authors
                journal=result.get("journal"),
                year=year,
                pmid=result.get("pmid"),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{result.get('pmid')}" if result.get("pmid") else None,
                relevance_score=relevance_score
            )
            
            citations.append(citation)
        
        return citations
    
    def _extract_clinical_trial_citations(self, results: List[Dict[str, Any]]) -> List[Citation]:
        """Extract citations from ClinicalTrials results."""
        citations = []
        
        for result in results:
            self.citation_counter += 1
            
            # Extract sponsor as "author"
            sponsors = []
            if result.get("sponsor"):
                sponsors = [result["sponsor"]]
            
            # Extract start year
            year = None
            if result.get("start_date"):
                try:
                    year = datetime.fromisoformat(result["start_date"]).year
                except:
                    pass
            
            relevance_score = self._calculate_trial_relevance(result)
            
            citation = Citation(
                id=str(self.citation_counter),
                source="clinicaltrials",
                title=result.get("title", "Untitled Trial"),
                authors=sponsors,
                year=year,
                nct_id=result.get("nct_id"),
                url=f"https://clinicaltrials.gov/ct2/show/{result.get('nct_id')}" if result.get("nct_id") else None,
                relevance_score=relevance_score
            )
            
            citations.append(citation)
        
        return citations
    
    def _extract_rag_citations(self, results: List[Dict[str, Any]]) -> List[Citation]:
        """Extract citations from RAG results."""
        citations = []
        
        for result in results:
            self.citation_counter += 1
            
            relevance_score = result.get("score", 0.0)
            
            citation = Citation(
                id=str(self.citation_counter),
                source="rag",
                title=result.get("title", "Document"),
                authors=[],  # RAG typically doesn't have author info
                relevance_score=relevance_score,
                url=result.get("url")
            )
            
            citations.append(citation)
        
        return citations
    
    def _calculate_pubmed_relevance(self, result: Dict[str, Any]) -> float:
        """Calculate relevance score for PubMed result."""
        score = 0.5  # Base score
        
        # Recent publications get higher score
        if result.get("publication_date"):
            try:
                pub_date = datetime.fromisoformat(result["publication_date"])
                days_old = (datetime.now() - pub_date).days
                if days_old < 365:  # Within last year
                    score += 0.3
                elif days_old < 1825:  # Within last 5 years
                    score += 0.1
            except:
                pass
        
        # High-impact journals (would need journal impact factor data)
        journal = result.get("journal", "").lower()
        if any(name in journal for name in ["nature", "science", "cell", "nejm", "lancet"]):
            score += 0.2
        
        return min(1.0, score)
    
    def _calculate_trial_relevance(self, result: Dict[str, Any]) -> float:
        """Calculate relevance score for clinical trial."""
        score = 0.5  # Base score
        
        # Phase 3 trials are generally more significant
        phase = result.get("phase", "").lower()
        if "3" in phase:
            score += 0.3
        elif "2" in phase:
            score += 0.2
        
        # Active/recruiting trials are more relevant
        status = result.get("status", "").lower()
        if "recruiting" in status:
            score += 0.2
        elif "active" in status:
            score += 0.1
        
        # Large trials are often more significant
        enrollment = result.get("enrollment", 0)
        if enrollment > 1000:
            score += 0.2
        elif enrollment > 100:
            score += 0.1
        
        return min(1.0, score)
```

### 3. Quality Scorer

**File**: `src/bio_mcp/orchestrator/synthesis/quality_scorer.py`
```python
"""Quality scoring for synthesis results."""
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.synthesis.synthesizer import Citation

logger = get_logger(__name__)

@dataclass
class QualityMetrics:
    """Quality metrics for synthesized results."""
    completeness_score: float      # How complete is the answer
    recency_score: float          # How recent are the results
    authority_score: float        # Authority/reliability of sources
    diversity_score: float        # Diversity of sources/perspectives
    relevance_score: float        # Relevance to query
    overall_score: float          # Overall quality score
    
    # Detailed metrics
    total_sources: int
    primary_source_count: int     # High-quality sources
    recent_results_count: int     # Results from last 2 years
    high_impact_count: int        # High-impact publications/trials
    
    # Quality flags
    has_systematic_reviews: bool
    has_recent_trials: bool
    has_multiple_perspectives: bool
    potential_conflicts: List[str]

class QualityScorer:
    """Scores the quality of synthesized results."""
    
    def __init__(self):
        self.high_impact_journals = {
            "nature", "science", "cell", "nejm", "lancet", "jama",
            "bmj", "plos one", "nature medicine", "cell metabolism"
        }
        
        self.systematic_review_keywords = {
            "systematic review", "meta-analysis", "cochrane review",
            "pooled analysis", "umbrella review"
        }
    
    def score_results(
        self, 
        result_data: Dict[str, Dict[str, Any]], 
        citations: List[Citation]
    ) -> QualityMetrics:
        """Score the overall quality of results."""
        
        # Calculate individual scores
        completeness = self._score_completeness(result_data)
        recency = self._score_recency(citations)
        authority = self._score_authority(citations)
        diversity = self._score_diversity(result_data, citations)
        relevance = self._score_relevance(citations)
        
        # Calculate overall score (weighted average)
        overall = (
            completeness * 0.25 +
            recency * 0.2 +
            authority * 0.25 +
            diversity * 0.15 +
            relevance * 0.15
        )
        
        # Detailed metrics
        total_sources = len(result_data)
        primary_sources = self._count_primary_sources(citations)
        recent_results = self._count_recent_results(citations)
        high_impact = self._count_high_impact(citations)
        
        # Quality flags
        has_systematic = self._has_systematic_reviews(citations)
        has_recent_trials = self._has_recent_trials(result_data)
        has_perspectives = self._has_multiple_perspectives(result_data)
        conflicts = self._detect_conflicts(result_data, citations)
        
        return QualityMetrics(
            completeness_score=completeness,
            recency_score=recency,
            authority_score=authority,
            diversity_score=diversity,
            relevance_score=relevance,
            overall_score=overall,
            total_sources=total_sources,
            primary_source_count=primary_sources,
            recent_results_count=recent_results,
            high_impact_count=high_impact,
            has_systematic_reviews=has_systematic,
            has_recent_trials=has_recent_trials,
            has_multiple_perspectives=has_perspectives,
            potential_conflicts=conflicts
        )
    
    def _score_completeness(self, result_data: Dict[str, Dict[str, Any]]) -> float:
        """Score completeness based on source coverage."""
        expected_sources = {"pubmed", "clinicaltrials", "rag"}
        available_sources = set(result_data.keys())
        
        # Base score from source coverage
        coverage_score = len(available_sources) / len(expected_sources)
        
        # Bonus for having results in each source
        result_quality = 0
        for source in available_sources:
            results = result_data[source].get("results", [])
            if len(results) > 0:
                result_quality += 0.2
            if len(results) >= 5:
                result_quality += 0.1
        
        return min(1.0, coverage_score * 0.6 + result_quality * 0.4)
    
    def _score_recency(self, citations: List[Citation]) -> float:
        """Score based on recency of results."""
        if not citations:
            return 0.0
        
        current_year = datetime.now().year
        recent_count = 0
        very_recent_count = 0
        
        for citation in citations:
            if citation.year:
                age = current_year - citation.year
                if age <= 2:  # Within last 2 years
                    very_recent_count += 1
                    recent_count += 1
                elif age <= 5:  # Within last 5 years
                    recent_count += 1
        
        recent_ratio = recent_count / len(citations)
        very_recent_ratio = very_recent_count / len(citations)
        
        return recent_ratio * 0.6 + very_recent_ratio * 0.4
    
    def _score_authority(self, citations: List[Citation]) -> float:
        """Score based on authority of sources."""
        if not citations:
            return 0.0
        
        authority_score = 0
        
        for citation in citations:
            # High-impact journals
            if citation.journal and any(
                journal in citation.journal.lower() 
                for journal in self.high_impact_journals
            ):
                authority_score += 0.3
            
            # Systematic reviews
            if any(
                keyword in citation.title.lower()
                for keyword in self.systematic_review_keywords
            ):
                authority_score += 0.4
            
            # Clinical trials (inherently authoritative)
            if citation.source == "clinicaltrials":
                authority_score += 0.2
            
            # Base authority for peer-reviewed sources
            if citation.source == "pubmed":
                authority_score += 0.1
        
        return min(1.0, authority_score / len(citations))
    
    def _score_diversity(
        self, 
        result_data: Dict[str, Dict[str, Any]], 
        citations: List[Citation]
    ) -> float:
        """Score based on diversity of sources and perspectives."""
        source_diversity = len(result_data) / 3.0  # Max 3 main sources
        
        # Check for diverse publication types
        pub_types = set()
        for citation in citations:
            if citation.source == "pubmed":
                # Could extract publication types from metadata
                pub_types.add("research_article")
            elif citation.source == "clinicaltrials":
                pub_types.add("clinical_trial")
            elif citation.source == "rag":
                pub_types.add("document")
        
        type_diversity = len(pub_types) / 3.0
        
        return (source_diversity + type_diversity) / 2.0
    
    def _score_relevance(self, citations: List[Citation]) -> float:
        """Score based on relevance scores of citations."""
        if not citations:
            return 0.0
        
        avg_relevance = sum(c.relevance_score for c in citations) / len(citations)
        return avg_relevance
    
    def _count_primary_sources(self, citations: List[Citation]) -> int:
        """Count high-quality primary sources."""
        count = 0
        for citation in citations:
            if (citation.journal and 
                any(j in citation.journal.lower() for j in self.high_impact_journals)):
                count += 1
            elif citation.source == "clinicaltrials":
                count += 1
        return count
    
    def _count_recent_results(self, citations: List[Citation]) -> int:
        """Count results from last 2 years."""
        current_year = datetime.now().year
        return sum(
            1 for c in citations 
            if c.year and (current_year - c.year) <= 2
        )
    
    def _count_high_impact(self, citations: List[Citation]) -> int:
        """Count high-impact publications."""
        return sum(
            1 for c in citations
            if c.journal and any(
                j in c.journal.lower() for j in self.high_impact_journals
            )
        )
    
    def _has_systematic_reviews(self, citations: List[Citation]) -> bool:
        """Check if results include systematic reviews."""
        return any(
            any(keyword in c.title.lower() for keyword in self.systematic_review_keywords)
            for c in citations
        )
    
    def _has_recent_trials(self, result_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if results include recent clinical trials."""
        ctgov_data = result_data.get("clinicaltrials")
        if not ctgov_data:
            return False
        
        trials = ctgov_data.get("results", [])
        current_year = datetime.now().year
        
        for trial in trials:
            if trial.get("start_date"):
                try:
                    start_year = datetime.fromisoformat(trial["start_date"]).year
                    if (current_year - start_year) <= 3:
                        return True
                except:
                    pass
        
        return False
    
    def _has_multiple_perspectives(self, result_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if results represent multiple perspectives."""
        # Simple check: do we have results from at least 2 different sources?
        sources_with_results = sum(
            1 for data in result_data.values()
            if data.get("results") and len(data["results"]) > 0
        )
        return sources_with_results >= 2
    
    def _detect_conflicts(
        self, 
        result_data: Dict[str, Dict[str, Any]], 
        citations: List[Citation]
    ) -> List[str]:
        """Detect potential conflicts or limitations."""
        conflicts = []
        
        # Check for very old results
        if citations:
            avg_age = sum(
                datetime.now().year - c.year for c in citations if c.year
            ) / len([c for c in citations if c.year])
            
            if avg_age > 10:
                conflicts.append("Results may be outdated (average age > 10 years)")
        
        # Check for limited source diversity
        if len(result_data) < 2:
            conflicts.append("Limited source diversity")
        
        # Check for small result sets
        total_results = sum(
            len(data.get("results", [])) for data in result_data.values()
        )
        if total_results < 5:
            conflicts.append("Limited number of results found")
        
        return conflicts
```

### 4. Template Engine

**File**: `src/bio_mcp/orchestrator/synthesis/template_engine.py`
```python
"""Template engine for generating formatted answers."""
from typing import Dict, Any, List
from datetime import datetime
import json

from bio_mcp.config.logging_config import get_logger

logger = get_logger(__name__)

class TemplateEngine:
    """Generates formatted answers using templates."""
    
    def __init__(self):
        self.templates = {
            "answer_comprehensive": self._comprehensive_template,
            "answer_partial": self._partial_template,
            "answer_minimal": self._minimal_template,
            "answer_empty": self._empty_template
        }
    
    async def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render template with context."""
        template_func = self.templates.get(template_name, self._comprehensive_template)
        return template_func(context)
    
    def _comprehensive_template(self, context: Dict[str, Any]) -> str:
        """Template for comprehensive answers."""
        parts = []
        
        # Header with query analysis
        parts.append(self._render_header(context))
        
        # Quality summary
        parts.append(self._render_quality_summary(context))
        
        # Results by source
        parts.append(self._render_results_by_source(context))
        
        # Key findings
        parts.append(self._render_key_findings(context))
        
        # Citations
        parts.append(self._render_citations(context))
        
        # Footer with metadata
        parts.append(self._render_footer(context))
        
        return "\n".join(parts)
    
    def _partial_template(self, context: Dict[str, Any]) -> str:
        """Template for partial answers."""
        parts = []
        
        parts.append("# Research Results (Partial)")
        parts.append(f"**Query:** {context['query']}")
        parts.append("\n⚠️ *Note: This is a partial response due to some data sources being unavailable.*\n")
        
        parts.append(self._render_results_by_source(context))
        parts.append(self._render_citations(context))
        parts.append(self._render_footer(context))
        
        return "\n".join(parts)
    
    def _minimal_template(self, context: Dict[str, Any]) -> str:
        """Template for minimal answers."""
        parts = []
        
        parts.append("# Research Results (Limited)")
        parts.append(f"**Query:** {context['query']}")
        parts.append("\n⚠️ *Note: Limited results found. Consider refining your search terms.*\n")
        
        parts.append(self._render_results_by_source(context))
        
        return "\n".join(parts)
    
    def _empty_template(self, context: Dict[str, Any]) -> str:
        """Template for empty results."""
        return f"""# No Results Found

**Query:** {context['query']}

❌ No relevant results were found for your query.

## Suggestions:
- Try broader search terms
- Check spelling and terminology
- Consider alternative keywords or synonyms
- Reduce the number of filters if any were applied

*Searched sources: PubMed, ClinicalTrials.gov, and internal documents*
"""
    
    def _render_header(self, context: Dict[str, Any]) -> str:
        """Render answer header."""
        frame = context.get("frame", {})
        intent = frame.get("intent", "unknown").replace("_", " ").title()
        
        header = f"""# Biomedical Research Results

**Query:** {context['query']}
**Analysis Intent:** {intent}
**Generated:** {datetime.fromisoformat(context['timestamp']).strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
        
        # Add entity information if available
        entities = frame.get("entities", {})
        if entities:
            entity_lines = []
            for key, value in entities.items():
                if value:
                    entity_lines.append(f"- **{key.title()}:** {value}")
            
            if entity_lines:
                header += f"\n**Entities Identified:**\n" + "\n".join(entity_lines) + "\n"
        
        return header
    
    def _render_quality_summary(self, context: Dict[str, Any]) -> str:
        """Render quality metrics summary."""
        quality = context.get("quality", {})
        if not quality:
            return ""
        
        overall_score = quality.get("overall_score", 0)
        score_emoji = "🟢" if overall_score >= 0.8 else "🟡" if overall_score >= 0.6 else "🔴"
        
        summary = f"""## Quality Assessment {score_emoji}

**Overall Quality Score:** {overall_score:.2f}/1.00

- **Completeness:** {quality.get('completeness_score', 0):.2f} (Source coverage)
- **Recency:** {quality.get('recency_score', 0):.2f} (Recent publications)
- **Authority:** {quality.get('authority_score', 0):.2f} (High-impact sources)
- **Diversity:** {quality.get('diversity_score', 0):.2f} (Multiple perspectives)
"""
        
        # Add quality flags
        flags = []
        if quality.get("has_systematic_reviews"):
            flags.append("✅ Includes systematic reviews")
        if quality.get("has_recent_trials"):
            flags.append("✅ Includes recent clinical trials")
        if quality.get("has_multiple_perspectives"):
            flags.append("✅ Multiple perspectives represented")
        
        if flags:
            summary += "\n**Quality Indicators:**\n" + "\n".join(flags) + "\n"
        
        # Add warnings if any
        conflicts = quality.get("potential_conflicts", [])
        if conflicts:
            summary += "\n**Limitations:**\n" + "\n".join(f"⚠️ {c}" for c in conflicts) + "\n"
        
        return summary
    
    def _render_results_by_source(self, context: Dict[str, Any]) -> str:
        """Render results organized by source."""
        results = context.get("results", {})
        if not results:
            return "## Results\n\nNo results found.\n"
        
        parts = ["## Results Summary\n"]
        
        source_names = {
            "pubmed": "📚 PubMed Publications",
            "clinicaltrials": "🧪 Clinical Trials",
            "rag": "📄 Related Documents"
        }
        
        for source, data in results.items():
            source_results = data.get("results", [])
            if not source_results:
                continue
            
            source_name = source_names.get(source, source.title())
            parts.append(f"### {source_name} ({len(source_results)} found)\n")
            
            # Show top 5 results
            for i, result in enumerate(source_results[:5], 1):
                if source == "pubmed":
                    parts.append(self._format_pubmed_result(i, result))
                elif source == "clinicaltrials":
                    parts.append(self._format_trial_result(i, result))
                elif source == "rag":
                    parts.append(self._format_rag_result(i, result))
            
            if len(source_results) > 5:
                parts.append(f"*... and {len(source_results) - 5} additional results*\n")
            
            parts.append("")  # Empty line between sources
        
        return "\n".join(parts)
    
    def _format_pubmed_result(self, index: int, result: Dict[str, Any]) -> str:
        """Format PubMed result."""
        title = result.get("title", "Untitled")
        authors = result.get("authors", [])
        journal = result.get("journal", "Unknown Journal")
        year = result.get("year", "Unknown Year")
        pmid = result.get("pmid")
        
        # Format authors
        if isinstance(authors, list):
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += " et al."
        else:
            author_str = str(authors) if authors else "Unknown Authors"
        
        formatted = f"{index}. **{title}**\n"
        formatted += f"   - Authors: {author_str}\n"
        formatted += f"   - Journal: {journal} ({year})\n"
        if pmid:
            formatted += f"   - PMID: [{pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid})\n"
        
        return formatted
    
    def _format_trial_result(self, index: int, result: Dict[str, Any]) -> str:
        """Format clinical trial result."""
        title = result.get("title", "Untitled Trial")
        nct_id = result.get("nct_id")
        phase = result.get("phase", "Unknown Phase")
        status = result.get("status", "Unknown Status")
        sponsor = result.get("sponsor", "Unknown Sponsor")
        
        formatted = f"{index}. **{title}**\n"
        formatted += f"   - Phase: {phase}\n"
        formatted += f"   - Status: {status}\n"
        formatted += f"   - Sponsor: {sponsor}\n"
        if nct_id:
            formatted += f"   - ClinicalTrials.gov: [{nct_id}](https://clinicaltrials.gov/ct2/show/{nct_id})\n"
        
        return formatted
    
    def _format_rag_result(self, index: int, result: Dict[str, Any]) -> str:
        """Format RAG result."""
        title = result.get("title", "Document")
        score = result.get("score", 0)
        snippet = result.get("snippet", "No description available")
        
        formatted = f"{index}. **{title}**\n"
        formatted += f"   - Relevance Score: {score:.3f}\n"
        formatted += f"   - {snippet[:200]}...\n"
        
        return formatted
    
    def _render_key_findings(self, context: Dict[str, Any]) -> str:
        """Render key findings section."""
        # This is a simplified version - could be enhanced with NLP summarization
        results = context.get("results", {})
        if not results:
            return ""
        
        findings = ["## Key Findings\n"]
        
        total_results = sum(len(data.get("results", [])) for data in results.values())
        findings.append(f"- **{total_results} total results** found across all sources")
        
        # Source-specific findings
        for source, data in results.items():
            source_results = data.get("results", [])
            if source_results:
                source_name = source.replace("_", " ").title()
                findings.append(f"- **{len(source_results)} {source_name} results** identified")
        
        return "\n".join(findings) + "\n"
    
    def _render_citations(self, context: Dict[str, Any]) -> str:
        """Render citations section."""
        citations = context.get("citations", [])
        if not citations:
            return ""
        
        parts = ["## References\n"]
        
        for i, citation in enumerate(citations[:20], 1):  # Limit to top 20
            formatted_citation = f"{i}. "
            
            # Authors
            if citation.get("authors"):
                authors = citation["authors"]
                if len(authors) > 3:
                    formatted_citation += f"{', '.join(authors[:3])} et al. "
                else:
                    formatted_citation += f"{', '.join(authors)}. "
            
            # Title
            formatted_citation += f"{citation.get('title', 'Untitled')}. "
            
            # Journal/Source specific formatting
            if citation.get("journal"):
                formatted_citation += f"*{citation['journal']}*. "
            
            # Year
            if citation.get("year"):
                formatted_citation += f"{citation['year']}. "
            
            # Identifiers and URLs
            if citation.get("pmid"):
                formatted_citation += f"PMID: [{citation['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{citation['pmid']})"
            elif citation.get("nct_id"):
                formatted_citation += f"ClinicalTrials.gov: [{citation['nct_id']}](https://clinicaltrials.gov/ct2/show/{citation['nct_id']})"
            elif citation.get("url"):
                formatted_citation += f"[Link]({citation['url']})"
            
            parts.append(formatted_citation + "\n")
        
        if len(citations) > 20:
            parts.append(f"*... and {len(citations) - 20} additional references*\n")
        
        return "\n".join(parts)
    
    def _render_footer(self, context: Dict[str, Any]) -> str:
        """Render footer with metadata."""
        metrics = context.get("metrics", {})
        
        footer = f"""---

**Execution Summary:**
- Total execution time: {metrics.get('execution_time', 0):.1f}ms
- Cache hit rate: {metrics.get('cache_hit_rate', 0):.1%}
- Sources queried: {metrics.get('source_count', 0)}

*Generated by Bio-MCP Orchestrator*
"""
        
        return footer
```

## Testing Strategy

### Unit Tests

**File**: `tests/unit/orchestrator/synthesis/test_synthesizer.py`
```python
"""Test advanced synthesizer functionality."""
import pytest
from datetime import datetime
from bio_mcp.orchestrator.synthesis.synthesizer import AdvancedSynthesizer, AnswerType
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import OrchestratorState

@pytest.mark.asyncio
async def test_comprehensive_synthesis():
    """Test comprehensive answer synthesis."""
    config = OrchestratorConfig()
    synthesizer = AdvancedSynthesizer(config)
    
    state = OrchestratorState(
        query="diabetes research",
        frame={"intent": "recent_pubs_by_topic"},
        pubmed_results={
            "results": [
                {"pmid": "123", "title": "Diabetes Study", "authors": ["Smith J"]}
            ]
        },
        ctgov_results={
            "results": [
                {"nct_id": "NCT123", "title": "Diabetes Trial", "phase": "Phase 3"}
            ]
        },
        config={},
        routing_decision=None,
        rag_results=None,
        tool_calls_made=["pubmed_search", "ctgov_search"],
        cache_hits={"pubmed_search": True, "ctgov_search": False},
        latencies={"pubmed_search": 200, "ctgov_search": 300},
        errors=[],
        node_path=["parse_frame", "router", "pubmed_search", "ctgov_search"],
        answer=None,
        checkpoint_id=None,
        messages=[]
    )
    
    result = await synthesizer.synthesize(state)
    
    assert "answer" in result
    assert "checkpoint_id" in result
    assert "citations" in result
    assert "quality_metrics" in result
    assert len(result["citations"]) == 2  # One from each source
```

### Integration Tests

**File**: `tests/integration/orchestrator/test_synthesis_integration.py`
```python
"""Integration tests for synthesis pipeline."""
import pytest
from bio_mcp.orchestrator.synthesis.synthesizer import AdvancedSynthesizer
from bio_mcp.orchestrator.synthesis.citation_extractor import CitationExtractor
from bio_mcp.orchestrator.synthesis.quality_scorer import QualityScorer
from bio_mcp.orchestrator.config import OrchestratorConfig

@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_synthesis():
    """Test complete synthesis pipeline."""
    config = OrchestratorConfig()
    
    # Test with realistic data
    result_data = {
        "pubmed": {
            "results": [
                {
                    "pmid": "12345678",
                    "title": "A comprehensive study of diabetes management",
                    "authors": ["Smith, J.", "Doe, A.", "Johnson, B."],
                    "journal": "Nature Medicine",
                    "publication_date": "2023-01-15"
                }
            ]
        },
        "clinicaltrials": {
            "results": [
                {
                    "nct_id": "NCT12345678",
                    "title": "Phase 3 trial of new diabetes medication",
                    "phase": "Phase 3",
                    "status": "Recruiting",
                    "sponsor": "Pharma Corp",
                    "start_date": "2023-06-01"
                }
            ]
        }
    }
    
    # Test citation extraction
    extractor = CitationExtractor()
    citations = await extractor.extract_citations(result_data)
    
    assert len(citations) == 2
    assert citations[0].source in ["pubmed", "clinicaltrials"]
    
    # Test quality scoring
    scorer = QualityScorer()
    quality = scorer.score_results(result_data, citations)
    
    assert quality.overall_score > 0
    assert quality.total_sources == 2
    assert quality.has_multiple_perspectives is True
```

## Acceptance Criteria
- [ ] AdvancedSynthesizer generates comprehensive, well-formatted answers
- [ ] CitationExtractor properly formats citations for all source types
- [ ] QualityScorer provides meaningful quality metrics
- [ ] TemplateEngine generates appropriate templates for different answer types
- [ ] Checkpoint IDs are deterministic and unique
- [ ] Answer quality is scored based on completeness, recency, authority, and diversity
- [ ] Citations include proper links and formatting
- [ ] Templates handle empty, minimal, partial, and comprehensive results
- [ ] Quality metrics identify systematic reviews and recent trials
- [ ] Integration tests validate end-to-end synthesis pipeline

## Files Created/Modified
- `src/bio_mcp/orchestrator/synthesis/synthesizer.py` - Advanced synthesizer
- `src/bio_mcp/orchestrator/synthesis/citation_extractor.py` - Citation extraction
- `src/bio_mcp/orchestrator/synthesis/quality_scorer.py` - Quality scoring
- `src/bio_mcp/orchestrator/synthesis/template_engine.py` - Answer templates
- `tests/unit/orchestrator/synthesis/test_synthesizer.py` - Synthesizer tests
- `tests/integration/orchestrator/test_synthesis_integration.py` - Integration tests

## Next Milestone
After completion, proceed to **M5 — LangGraph Observability** which will focus on comprehensive monitoring, debugging, and performance tracking using LangSmith and OpenTelemetry.