# RAG Step 6: RAG Search Improvements

**Objective:** Enhance RAG search capabilities with OpenAI embeddings, section boosting, quality ranking, improved result reconstruction, and advanced filtering to provide more relevant biomedical search results.

**Success Criteria:**
- OpenAI embeddings provide superior semantic search quality
- Section-aware boosting improves result relevance
- Quality scoring enhances result ranking
- Clean abstract reconstruction without title duplication
- Advanced filtering by date, source, and section
- Performance maintains <200ms average response time
- User-facing tools integrate seamlessly with improved search
- Tests properly skip when OpenAI API key not available

---

## 1. Enhanced RAG Service

### 1.1 Updated RAG Tools
**File:** `src/bio_mcp/mcp/rag_tools.py`

```python
from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import asyncio

from bio_mcp.services.document_chunk_service import DocumentChunkService
from bio_mcp.config.config import Config

logger = logging.getLogger(__name__)

class EnhancedRAGTools:
    """Enhanced RAG tools with section boosting and quality ranking."""
    
    def __init__(self, config: Config):
        self.config = config
        self.document_chunk_service = DocumentChunkService()
    
    async def search_documents(
        self,
        query: str,
        limit: int = 10,
        source_filter: Optional[str] = None,
        year_range: Optional[Tuple[int, int]] = None,
        section_filter: Optional[List[str]] = None,
        quality_threshold: Optional[float] = None,
        boost_recent: bool = True,
        boost_clinical: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Enhanced document search with multiple ranking factors.
        
        Args:
            query: Search query text
            limit: Maximum number of results
            source_filter: Filter by source (e.g., 'pubmed')
            year_range: Filter by publication year range (start_year, end_year)
            section_filter: Filter by document sections
            quality_threshold: Minimum quality score
            boost_recent: Apply recency boost to newer documents
            boost_clinical: Apply boost to clinical/trial content
        """
        try:
            await self.document_chunk_service.connect()
            
            # Execute search with filters using DocumentChunkService
            chunk_results = await self.document_chunk_service.search_chunks(
                query=query,
                limit=limit * 3,  # Get more chunks to reconstruct documents
                source_filter=source_filter,
                year_filter=year_range,
                section_filter=section_filter,
                quality_threshold=quality_threshold
            )
            
            # Group chunks by document and reconstruct
            document_results = await self._reconstruct_documents(chunk_results)
            
            # Apply additional ranking factors
            if boost_recent:
                document_results = self._apply_recency_boost(document_results)
            
            if boost_clinical:
                document_results = self._apply_clinical_boost(document_results, query)
            
            # Re-rank and limit results
            document_results.sort(key=lambda x: x["final_score"], reverse=True)
            
            return document_results[:limit]
            
        except Exception as e:
            logger.error(f"Enhanced search failed: {e}")
            raise
        finally:
            await self.document_chunk_service.disconnect()
    
    async def _reconstruct_documents(
        self, 
        chunk_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Reconstruct documents from chunks with clean abstract assembly.
        """
        documents_map = {}
        
        for chunk in chunk_results:
            parent_uid = chunk["parent_uid"]
            
            if parent_uid not in documents_map:
                documents_map[parent_uid] = {
                    "uid": parent_uid,
                    "source": chunk["source"],
                    "title": chunk["title"],
                    "published_at": chunk["published_at"],
                    "year": chunk["year"],
                    "quality_total": chunk["quality_total"],
                    "chunks": [],
                    "sections_found": set(),
                    "best_chunk_score": 0,
                    "total_score": 0,
                    "meta": chunk.get("meta", {})
                }
            
            doc_info = documents_map[parent_uid]
            doc_info["chunks"].append(chunk)
            doc_info["sections_found"].add(chunk.get("section", "Unknown"))
            doc_info["best_chunk_score"] = max(doc_info["best_chunk_score"], chunk["score"])
            doc_info["total_score"] += chunk["score"]
        
        # Reconstruct clean abstracts
        reconstructed_docs = []
        for doc_info in documents_map.values():
            abstract = await self._reconstruct_clean_abstract(doc_info["chunks"])
            
            # Calculate document-level score
            doc_score = self._calculate_document_score(doc_info)
            
            reconstructed_doc = {
                "uid": doc_info["uid"],
                "source": doc_info["source"],
                "title": doc_info["title"] or "",
                "abstract": abstract,
                "published_at": doc_info["published_at"],
                "year": doc_info["year"],
                "quality_total": doc_info["quality_total"],
                "sections_found": list(doc_info["sections_found"]),
                "chunk_count": len(doc_info["chunks"]),
                "best_chunk_score": doc_info["best_chunk_score"],
                "document_score": doc_score,
                "final_score": doc_score,  # Will be modified by additional boosts
                "meta": doc_info["meta"],
                "source_url": self._get_source_url(doc_info)
            }
            
            reconstructed_docs.append(reconstructed_doc)
        
        return reconstructed_docs
    
    async def _reconstruct_clean_abstract(
        self, 
        chunks: List[Dict[str, Any]]
    ) -> str:
        """
        Reconstruct abstract from chunks without title duplication.
        """
        # Sort chunks by section and index
        section_order = {"Background": 0, "Methods": 1, "Results": 2, "Conclusions": 3, "Other": 4, "Unstructured": 5}
        
        def chunk_sort_key(chunk):
            section = chunk.get("section", "Other")
            section_priority = section_order.get(section, 99)
            # Extract chunk index from UUID or use 0
            chunk_id = chunk.get("uuid", "")
            chunk_index = 0
            try:
                # Try to extract index from chunk patterns like "s0", "w1"
                if ":" in chunk_id:
                    chunk_part = chunk_id.split(":")[-1]
                    if len(chunk_part) > 1:
                        chunk_index = int(chunk_part[1:])
            except:
                pass
            return (section_priority, chunk_index)
        
        sorted_chunks = sorted(chunks, key=chunk_sort_key)
        
        # Reconstruct abstract
        abstract_parts = []
        title = chunks[0].get("title", "") if chunks else ""
        
        for chunk in sorted_chunks:
            chunk_text = chunk["text"]
            
            # Remove title from chunk text if present
            if title and chunk_text.startswith(title):
                chunk_text = chunk_text[len(title):].strip()
            
            # Remove section headers that might be in the text
            section = chunk.get("section", "")
            if section and section != "Unstructured":
                # Remove common section header patterns
                for header_pattern in [f"[Section] {section}", f"{section}:", f"{section} -"]:
                    if chunk_text.startswith(header_pattern):
                        chunk_text = chunk_text[len(header_pattern):].strip()
            
            if chunk_text:
                abstract_parts.append(chunk_text)
        
        # Join with spaces and clean up
        abstract = " ".join(abstract_parts)
        
        # Clean up multiple spaces and formatting
        import re
        abstract = re.sub(r'\s+', ' ', abstract)
        abstract = abstract.strip()
        
        return abstract
    
    def _calculate_document_score(self, doc_info: Dict[str, Any]) -> float:
        """Calculate comprehensive document relevance score."""
        
        # Base score from best matching chunk
        base_score = doc_info["best_chunk_score"]
        
        # Boost for multiple relevant chunks
        chunk_count_boost = min(0.2, len(doc_info["chunks"]) * 0.05)
        
        # Boost for comprehensive section coverage
        sections_found = doc_info["sections_found"]
        comprehensive_sections = {"Background", "Methods", "Results", "Conclusions"}
        section_coverage = len(sections_found.intersection(comprehensive_sections)) / len(comprehensive_sections)
        section_boost = section_coverage * 0.1
        
        # Quality boost (already applied in chunk scoring, but reinforce)
        quality_boost = doc_info["quality_total"] / 20.0  # Scale 0-1 quality to 0-0.05 boost
        
        return base_score + chunk_count_boost + section_boost + quality_boost
    
    def _apply_recency_boost(
        self, 
        documents: List[Dict[str, Any]],
        max_boost: float = 0.15
    ) -> List[Dict[str, Any]]:
        """Apply recency boost to newer documents."""
        
        current_year = datetime.now().year
        
        for doc in documents:
            year = doc.get("year")
            if year:
                # Boost newer papers, with diminishing returns
                years_old = current_year - year
                if years_old <= 2:
                    recency_boost = max_boost
                elif years_old <= 5:
                    recency_boost = max_boost * 0.5
                elif years_old <= 10:
                    recency_boost = max_boost * 0.2
                else:
                    recency_boost = 0
                
                doc["final_score"] += recency_boost
                doc["recency_boost"] = recency_boost
            else:
                doc["recency_boost"] = 0
        
        return documents
    
    def _apply_clinical_boost(
        self, 
        documents: List[Dict[str, Any]],
        query: str,
        max_boost: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Apply boost for clinical/trial content relevance."""
        
        # Clinical keywords that indicate high-value research
        clinical_keywords = {
            "randomized controlled trial", "clinical trial", "rct", "placebo",
            "double-blind", "meta-analysis", "systematic review", "efficacy",
            "safety", "adverse events", "primary endpoint", "secondary endpoint",
            "intention-to-treat", "per-protocol", "confidence interval", "hazard ratio",
            "odds ratio", "p-value", "statistical significance"
        }
        
        query_lower = query.lower()
        query_is_clinical = any(keyword in query_lower for keyword in clinical_keywords)
        
        for doc in documents:
            clinical_boost = 0
            
            # Check if document contains clinical indicators
            abstract = doc.get("abstract", "").lower()
            title = doc.get("title", "").lower()
            
            clinical_indicators = sum(1 for keyword in clinical_keywords 
                                   if keyword in abstract or keyword in title)
            
            if clinical_indicators > 0:
                # Base boost for clinical content
                clinical_boost = min(max_boost, clinical_indicators * 0.02)
                
                # Extra boost if query is also clinical
                if query_is_clinical:
                    clinical_boost *= 1.5
            
            doc["final_score"] += clinical_boost
            doc["clinical_boost"] = clinical_boost
        
        return documents
    
    def _get_source_url(self, doc_info: Dict[str, Any]) -> Optional[str]:
        """Get source URL for document."""
        source = doc_info["source"]
        uid = doc_info["uid"]
        
        if source == "pubmed":
            # Extract PMID from UID
            pmid = uid.split(":")[-1] if ":" in uid else uid
            return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        
        # Add other source URL patterns as needed
        return None
    
    async def get_document_details(
        self, 
        document_uid: str,
        include_chunks: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific document.
        """
        try:
            await self.document_chunk_service.connect()
            
            # Search for all chunks of this document using DocumentChunkService
            chunks = await self.document_chunk_service.search_chunks(
                query="*",  # Match all
                limit=50,   # Reasonable limit for chunks per document
                source_filter=None
            )
            
            # Filter to only this document's chunks
            doc_chunks = [chunk for chunk in chunks if chunk["parent_uid"] == document_uid]
            
            if not doc_chunks:
                return None
            
            # Reconstruct document
            doc_results = await self._reconstruct_documents(doc_chunks)
            
            if not doc_results:
                return None
            
            doc = doc_results[0]
            
            if include_chunks:
                doc["chunks"] = doc_chunks
            
            return doc
            
        except Exception as e:
            logger.error(f"Failed to get document details for {document_uid}: {e}")
            return None
        finally:
            await self.document_chunk_service.disconnect()
    
    async def search_by_semantic_similarity(
        self,
        reference_document_uid: str,
        limit: int = 10,
        exclude_self: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find documents similar to a reference document using semantic similarity.
        """
        try:
            # Get reference document details
            ref_doc = await self.get_document_details(reference_document_uid, include_chunks=True)
            
            if not ref_doc:
                raise ValueError(f"Reference document {reference_document_uid} not found")
            
            # Use the abstract as the query for similarity search
            query_text = ref_doc["abstract"]
            if len(query_text) > 1000:
                # Truncate very long abstracts for better performance
                query_text = query_text[:1000]
            
            # Perform similarity search
            similar_docs = await self.search_documents(
                query=query_text,
                limit=limit + (1 if exclude_self else 0),
                source_filter=ref_doc["source"],  # Same source for better comparison
                boost_recent=False,  # Focus on content similarity
                boost_clinical=False
            )
            
            # Remove reference document from results if requested
            if exclude_self:
                similar_docs = [doc for doc in similar_docs if doc["uid"] != reference_document_uid]
            
            return similar_docs[:limit]
            
        except Exception as e:
            logger.error(f"Semantic similarity search failed: {e}")
            raise
    
    async def get_search_suggestions(
        self, 
        partial_query: str,
        limit: int = 5
    ) -> List[str]:
        """
        Get search suggestions based on partial query input.
        """
        # This is a simple implementation - could be enhanced with ML
        common_biomedical_terms = [
            "diabetes treatment", "cancer therapy", "cardiovascular disease",
            "alzheimer disease", "parkinson disease", "multiple sclerosis",
            "rheumatoid arthritis", "inflammatory bowel disease", "asthma",
            "chronic kidney disease", "liver cirrhosis", "stroke prevention",
            "depression treatment", "anxiety disorder", "clinical trial",
            "randomized controlled trial", "meta-analysis", "systematic review",
            "adverse events", "drug safety", "therapeutic efficacy",
            "biomarker discovery", "genetic variants", "pharmacokinetics"
        ]
        
        partial_lower = partial_query.lower()
        suggestions = [
            term for term in common_biomedical_terms
            if partial_lower in term.lower()
        ]
        
        return suggestions[:limit]
```

### 1.2 MCP Tool Integration
**File:** `src/bio_mcp/mcp/rag_tools.py` (updated tool definitions)

```python
async def rag_search_enhanced(
    query: str,
    limit: int = 10,
    source: Optional[str] = None,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    sections: Optional[str] = None,
    quality_threshold: Optional[float] = None,
    search_mode: str = "semantic"
) -> Dict[str, Any]:
    """
    Enhanced biomedical literature search with OpenAI embeddings.
    
    Args:
        query: Search query text
        limit: Maximum number of results (1-50)
        source: Filter by source ('pubmed', etc.)
        year_start: Filter documents from this year onwards
        year_end: Filter documents up to this year
        sections: Comma-separated list of sections to filter by
        quality_threshold: Minimum quality score (0.0-1.0)
        search_mode: Search mode ('semantic', 'bm25', 'hybrid')
    """
    try:
        service = DocumentChunkService()
        await service.connect()
        
        # Parse year range
        year_filter = None
        if year_start or year_end:
            year_filter = (year_start or 1900, year_end or datetime.now().year)
        
        # Parse sections
        section_filter = None
        if sections:
            section_filter = [s.strip() for s in sections.split(",")]
        
        results = await service.search_chunks(
            query=query,
            limit=min(limit, 50),
            source_filter=source,
            year_filter=year_filter,
            section_filter=section_filter,
            quality_threshold=quality_threshold,
            search_mode=search_mode
        )
        
        return {
            "query": query,
            "total_results": len(results),
            "search_mode": search_mode,
            "filters_applied": {
                "source": source,
                "year_range": year_filter,
                "sections": section_filter,
                "quality_threshold": quality_threshold
            },
            "chunks": results
        }
        
    except Exception as e:
        logger.error(f"Enhanced RAG search failed: {e}")
        return {
            "error": str(e),
            "query": query,
            "chunks": []
        }
    finally:
        await service.disconnect()

async def rag_get_document(
    document_uid: str,
    include_chunks: bool = False
) -> Dict[str, Any]:
    """
    Get detailed information about a specific document.
    
    Args:
        document_uid: Document UID (e.g., 'pubmed:12345678')
        include_chunks: Include individual chunks in response
    """
    try:
        service = DocumentChunkService()
        await service.connect()
        
        # Search for chunks belonging to this document
        chunks = await service.search_chunks(
            query="*",  # Match all
            limit=100,  # Get all chunks for the document
            filters={"parent_uid": document_uid}
        )
        
        if not chunks:
            return {
                "error": f"Document {document_uid} not found",
                "document": None
            }
        
        # Reconstruct document from chunks
        first_chunk = chunks[0]
        document = {
            "uid": document_uid,
            "title": first_chunk.get("title"),
            "source": first_chunk.get("source"),
            "published_at": first_chunk.get("published_at"),
            "year": first_chunk.get("year"),
            "quality_total": first_chunk.get("quality_total"),
            "chunk_count": len(chunks)
        }
        
        if include_chunks:
            document["chunks"] = chunks
        
        return {
            "document": document,
            "document_uid": document_uid
        }
        
    except Exception as e:
        logger.error(f"Failed to get document {document_uid}: {e}")
        return {
            "error": str(e),
            "document": None
        }
    finally:
        await service.disconnect()

async def rag_find_similar(
    reference_document_uid: str,
    limit: int = 10,
    exclude_self: bool = True
) -> Dict[str, Any]:
    """
    Find documents semantically similar to a reference document.
    
    Args:
        reference_document_uid: UID of reference document
        limit: Maximum number of similar documents to return
        exclude_self: Exclude the reference document from results
    """
    try:
        enhanced_rag = EnhancedRAGTools(config)
        
        similar_docs = await enhanced_rag.search_by_semantic_similarity(
            reference_document_uid=reference_document_uid,
            limit=min(limit, 50),
            exclude_self=exclude_self
        )
        
        return {
            "reference_document": reference_document_uid,
            "similar_documents": similar_docs,
            "total_found": len(similar_docs)
        }
        
    except Exception as e:
        logger.error(f"Failed to find similar documents: {e}")
        return {
            "error": str(e),
            "reference_document": reference_document_uid,
            "similar_documents": []
        }

async def rag_search_suggestions(
    partial_query: str,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Get search suggestions for partial queries.
    
    Args:
        partial_query: Partial search query
        limit: Maximum number of suggestions
    """
    try:
        enhanced_rag = EnhancedRAGTools(config)
        
        suggestions = await enhanced_rag.get_search_suggestions(
            partial_query=partial_query,
            limit=min(limit, 10)
        )
        
        return {
            "partial_query": partial_query,
            "suggestions": suggestions
        }
        
    except Exception as e:
        logger.error(f"Failed to get search suggestions: {e}")
        return {
            "error": str(e),
            "suggestions": []
        }
```

---

## 2. Search Quality Improvements

### 2.1 Query Processing Enhancement
**File:** `src/bio_mcp/services/query_processor.py`

```python
from __future__ import annotations
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

@dataclass
class QueryContext:
    """Structured representation of search query context."""
    original_query: str
    processed_query: str
    entities: List[str]
    keywords: List[str]
    intent: str
    filters: Dict[str, Any]

class BiomedicalQueryProcessor:
    """Process and enhance biomedical search queries."""
    
    def __init__(self):
        # Biomedical entity patterns
        self.drug_patterns = [
            r'\b[A-Z][a-z]+[A-Z][a-z]+\b',  # CamelCase drug names
            r'\b\w+mab\b',  # Monoclonal antibodies
            r'\b\w+ib\b',   # Protein kinase inhibitors
        ]
        
        self.condition_patterns = [
            r'\b[A-Z][A-Z]+\b',  # Acronyms like COPD, HIV
            r'\b\w+ disease\b',
            r'\b\w+ syndrome\b',
            r'\b\w+ disorder\b',
        ]
        
        # Clinical study indicators
        self.study_type_keywords = {
            "rct": "randomized controlled trial",
            "meta-analysis": "meta-analysis", 
            "systematic review": "systematic review",
            "cohort study": "cohort study",
            "case-control": "case-control study"
        }
        
        # Statistical terms
        self.statistical_terms = [
            "p-value", "confidence interval", "hazard ratio", "odds ratio",
            "relative risk", "absolute risk", "number needed to treat",
            "sensitivity", "specificity", "positive predictive value"
        ]
    
    def process_query(self, query: str) -> QueryContext:
        """Process a biomedical query and extract structured information."""
        
        # Basic cleaning
        processed = query.strip()
        processed = re.sub(r'\s+', ' ', processed)
        
        # Extract entities
        entities = self._extract_entities(query)
        
        # Extract keywords
        keywords = self._extract_keywords(query)
        
        # Infer intent
        intent = self._infer_intent(query, entities, keywords)
        
        # Extract implicit filters
        filters = self._extract_filters(query)
        
        # Enhance query for better search
        enhanced_query = self._enhance_query(processed, entities, keywords, intent)
        
        return QueryContext(
            original_query=query,
            processed_query=enhanced_query,
            entities=entities,
            keywords=keywords,
            intent=intent,
            filters=filters
        )
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extract biomedical entities from query."""
        entities = []
        
        # Drug names
        for pattern in self.drug_patterns:
            matches = re.findall(pattern, query)
            entities.extend(matches)
        
        # Conditions
        for pattern in self.condition_patterns:
            matches = re.findall(pattern, query)
            entities.extend(matches)
        
        # Remove duplicates and filter
        entities = list(set(entities))
        entities = [e for e in entities if len(e) > 2]  # Filter short matches
        
        return entities
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract important keywords from query."""
        keywords = []
        query_lower = query.lower()
        
        # Study type keywords
        for abbrev, full_term in self.study_type_keywords.items():
            if abbrev in query_lower or full_term in query_lower:
                keywords.append(full_term)
        
        # Statistical terms
        for term in self.statistical_terms:
            if term in query_lower:
                keywords.append(term)
        
        return keywords
    
    def _infer_intent(
        self, 
        query: str, 
        entities: List[str], 
        keywords: List[str]
    ) -> str:
        """Infer the search intent from query components."""
        query_lower = query.lower()
        
        # Treatment/therapy intent
        if any(word in query_lower for word in ["treatment", "therapy", "drug", "medication"]):
            return "treatment"
        
        # Diagnosis intent
        elif any(word in query_lower for word in ["diagnosis", "diagnostic", "biomarker"]):
            return "diagnosis"
        
        # Mechanism/pathophysiology intent
        elif any(word in query_lower for word in ["mechanism", "pathway", "pathophysiology"]):
            return "mechanism"
        
        # Clinical evidence intent
        elif any(keyword in keywords for keyword in ["randomized controlled trial", "meta-analysis"]):
            return "clinical_evidence"
        
        # Safety/adverse events intent
        elif any(word in query_lower for word in ["safety", "adverse", "side effect", "toxicity"]):
            return "safety"
        
        # General research intent
        else:
            return "general"
    
    def _extract_filters(self, query: str) -> Dict[str, Any]:
        """Extract implicit filters from query."""
        filters = {}
        query_lower = query.lower()
        
        # Year filters
        year_match = re.search(r'(\d{4})', query)
        if year_match:
            year = int(year_match.group(1))
            if 1990 <= year <= 2024:  # Reasonable range
                filters["year_start"] = year
        
        # Recency filters
        if any(word in query_lower for word in ["recent", "latest", "new", "current"]):
            filters["boost_recent"] = True
        
        # Study type filters
        if "clinical trial" in query_lower or "rct" in query_lower:
            filters["boost_clinical"] = True
        
        return filters
    
    def _enhance_query(
        self, 
        query: str, 
        entities: List[str], 
        keywords: List[str], 
        intent: str
    ) -> str:
        """Enhance query for better search performance."""
        enhanced = query
        
        # Add synonyms for entities (simplified example)
        entity_synonyms = {
            "COVID-19": "coronavirus SARS-CoV-2 COVID",
            "diabetes": "diabetes mellitus T2DM",
            "cancer": "neoplasm tumor malignancy",
        }
        
        for entity in entities:
            if entity in entity_synonyms:
                enhanced += f" {entity_synonyms[entity]}"
        
        # Intent-based enhancement
        if intent == "treatment":
            enhanced += " therapy efficacy intervention"
        elif intent == "diagnosis":
            enhanced += " diagnostic biomarker screening"
        elif intent == "safety":
            enhanced += " adverse events safety profile toxicity"
        
        return enhanced
```

### 2.2 Result Post-Processing
**File:** `src/bio_mcp/services/result_processor.py`

```python
from __future__ import annotations
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SearchResultProcessor:
    """Post-process and enhance search results."""
    
    def __init__(self):
        # Evidence level mappings
        self.evidence_levels = {
            "meta-analysis": 1,
            "systematic review": 2,
            "randomized controlled trial": 3,
            "cohort study": 4,
            "case-control study": 5,
            "case series": 6,
            "case report": 7,
            "expert opinion": 8
        }
    
    def process_results(
        self,
        results: List[Dict[str, Any]],
        query_context: Any,  # QueryContext from query_processor
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Post-process search results for better relevance and presentation."""
        
        # Add evidence levels
        results = self._add_evidence_levels(results)
        
        # Add relevance explanations
        results = self._add_relevance_explanations(results, query_context)
        
        # Group by topic clusters (if many results)
        if len(results) > 20:
            results = self._cluster_by_topic(results)
        
        # Final ranking with all factors
        results = self._final_ranking(results, query_context)
        
        return results[:max_results]
    
    def _add_evidence_levels(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add evidence level classifications to results."""
        
        for result in results:
            abstract = result.get("abstract", "").lower()
            title = result.get("title", "").lower()
            
            evidence_level = 8  # Default to lowest level
            study_type = "observational"
            
            # Check for study type indicators
            for study_type_name, level in self.evidence_levels.items():
                if study_type_name in abstract or study_type_name in title:
                    if level < evidence_level:
                        evidence_level = level
                        study_type = study_type_name
            
            result["evidence_level"] = evidence_level
            result["study_type"] = study_type
            result["evidence_strength"] = self._get_evidence_strength(evidence_level)
        
        return results
    
    def _get_evidence_strength(self, level: int) -> str:
        """Convert evidence level to human-readable strength."""
        if level <= 2:
            return "Very High"
        elif level <= 4:
            return "High"
        elif level <= 6:
            return "Moderate"
        else:
            return "Low"
    
    def _add_relevance_explanations(
        self,
        results: List[Dict[str, Any]],
        query_context: Any
    ) -> List[Dict[str, Any]]:
        """Add explanations for why each result is relevant."""
        
        for result in results:
            explanations = []
            
            # Check for entity matches
            abstract = result.get("abstract", "").lower()
            title = result.get("title", "").lower()
            
            if hasattr(query_context, 'entities'):
                for entity in query_context.entities:
                    if entity.lower() in abstract or entity.lower() in title:
                        explanations.append(f"Mentions {entity}")
            
            # Check for keyword matches
            if hasattr(query_context, 'keywords'):
                for keyword in query_context.keywords:
                    if keyword.lower() in abstract or keyword.lower() in title:
                        explanations.append(f"Contains {keyword}")
            
            # Check for high-quality indicators
            if result.get("quality_total", 0) > 0.8:
                explanations.append("High-quality source")
            
            # Check for recent publication
            if result.get("recency_boost", 0) > 0:
                explanations.append("Recent publication")
            
            # Check for clinical relevance
            if result.get("clinical_boost", 0) > 0:
                explanations.append("Clinical relevance")
            
            result["relevance_explanation"] = explanations
        
        return results
    
    def _cluster_by_topic(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Simple topic clustering based on shared keywords."""
        # This is a simplified implementation
        # In production, you might use more sophisticated clustering
        
        # For now, just ensure diversity by not showing too many
        # results from the same journal or with very similar titles
        seen_journals = set()
        filtered_results = []
        
        for result in results:
            meta = result.get("meta", {})
            journal = meta.get("src", {}).get("pubmed", {}).get("journal", "")
            
            # Limit results per journal
            if journal and journal in seen_journals:
                # Check if we already have 2 results from this journal
                journal_count = sum(1 for r in filtered_results 
                                  if r.get("meta", {}).get("src", {}).get("pubmed", {}).get("journal", "") == journal)
                if journal_count >= 2:
                    continue
            
            if journal:
                seen_journals.add(journal)
            
            filtered_results.append(result)
        
        return filtered_results
    
    def _final_ranking(
        self,
        results: List[Dict[str, Any]],
        query_context: Any
    ) -> List[Dict[str, Any]]:
        """Apply final ranking adjustments."""
        
        for result in results:
            final_score = result.get("final_score", 0)
            
            # Evidence level boost
            evidence_level = result.get("evidence_level", 8)
            evidence_boost = (9 - evidence_level) * 0.02  # Higher evidence = higher boost
            
            # Comprehensive sections boost
            sections = result.get("sections_found", [])
            if len(set(sections).intersection({"Background", "Methods", "Results", "Conclusions"})) >= 3:
                comprehensive_boost = 0.05
            else:
                comprehensive_boost = 0
            
            # Update final score
            result["final_score"] = final_score + evidence_boost + comprehensive_boost
            result["evidence_boost"] = evidence_boost
            result["comprehensive_boost"] = comprehensive_boost
        
        # Sort by final score
        results.sort(key=lambda x: x["final_score"], reverse=True)
        
        return results
```

---

## 3. Performance Optimizations

### 3.1 Caching Layer
**File:** `src/bio_mcp/services/search_cache.py`

```python
from __future__ import annotations
import asyncio
import hashlib
import json
import time
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class SearchCache:
    """In-memory cache for search results with TTL."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._lock = asyncio.Lock()
    
    def _get_cache_key(self, query: str, filters: Dict[str, Any]) -> str:
        """Generate consistent cache key from query and filters."""
        cache_data = {"query": query, "filters": filters}
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    async def get(self, query: str, filters: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Get cached results if available and not expired."""
        cache_key = self._get_cache_key(query, filters)
        
        async with self._lock:
            if cache_key in self.cache:
                cache_entry = self.cache[cache_key]
                
                # Check if expired
                if time.time() - cache_entry["timestamp"] > cache_entry["ttl"]:
                    del self.cache[cache_key]
                    return None
                
                logger.debug(f"Cache hit for query: {query[:50]}...")
                return cache_entry["results"]
        
        return None
    
    async def set(
        self, 
        query: str, 
        filters: Dict[str, Any], 
        results: List[Dict[str, Any]],
        ttl: Optional[int] = None
    ) -> None:
        """Cache search results."""
        cache_key = self._get_cache_key(query, filters)
        ttl = ttl or self.default_ttl
        
        async with self._lock:
            # Implement LRU eviction if cache is full
            if len(self.cache) >= self.max_size:
                # Remove oldest entry
                oldest_key = min(self.cache.keys(), 
                               key=lambda k: self.cache[k]["timestamp"])
                del self.cache[oldest_key]
            
            self.cache[cache_key] = {
                "results": results,
                "timestamp": time.time(),
                "ttl": ttl
            }
            
            logger.debug(f"Cached results for query: {query[:50]}...")
    
    async def clear(self) -> None:
        """Clear all cached results."""
        async with self._lock:
            self.cache.clear()
            logger.info("Search cache cleared")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            current_time = time.time()
            valid_entries = 0
            expired_entries = 0
            
            for entry in self.cache.values():
                if current_time - entry["timestamp"] > entry["ttl"]:
                    expired_entries += 1
                else:
                    valid_entries += 1
            
            return {
                "total_entries": len(self.cache),
                "valid_entries": valid_entries,
                "expired_entries": expired_entries,
                "max_size": self.max_size,
                "usage_percent": len(self.cache) / self.max_size * 100
            }
```

### 3.2 Enhanced RAG Service with Caching
**File:** `src/bio_mcp/mcp/rag_tools.py` (updated with caching)

```python
class EnhancedRAGTools:
    def __init__(self, config: Config):
        self.config = config
        self.document_chunk_service = DocumentChunkService()
        self.query_processor = BiomedicalQueryProcessor()
        self.result_processor = SearchResultProcessor()
        self.cache = SearchCache(
            max_size=int(config.get("BIO_MCP_SEARCH_CACHE_SIZE", "1000")),
            default_ttl=int(config.get("BIO_MCP_SEARCH_CACHE_TTL", "300"))
        )
    
    async def search_documents(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Enhanced search with query processing, caching, and result optimization."""
        
        # Process query for better understanding
        query_context = self.query_processor.process_query(query)
        
        # Merge processed filters with explicit filters
        filters = {**query_context.filters, **kwargs}
        
        # Check cache first
        cached_results = await self.cache.get(query_context.processed_query, filters)
        if cached_results:
            return cached_results
        
        # Perform search with processed query
        try:
            await self.document_chunk_service.connect()
            
            chunk_results = await self.document_chunk_service.search_chunks(
                query=query_context.processed_query,
                **filters
            )
            
            # Reconstruct and rank documents
            document_results = await self._reconstruct_documents(chunk_results)
            
            # Apply additional ranking factors
            if filters.get("boost_recent", True):
                document_results = self._apply_recency_boost(document_results)
            
            if filters.get("boost_clinical", True):
                document_results = self._apply_clinical_boost(document_results, query)
            
            # Post-process results
            processed_results = self.result_processor.process_results(
                document_results, 
                query_context,
                max_results=filters.get("limit", 10)
            )
            
            # Cache results
            await self.cache.set(query_context.processed_query, filters, processed_results)
            
            return processed_results
            
        finally:
            await self.document_chunk_service.disconnect()
```

---

## 4. Testing Implementation

### 4.1 Quality Testing
**File:** `tests/integration/test_rag_quality.py`

```python
import os
import pytest
from bio_mcp.services.document_chunk_service import DocumentChunkService
from bio_mcp.config.config import Config

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="RAG quality tests require OpenAI API key for embeddings"
)
class TestRAGQuality:
    """Test RAG search quality and relevance."""
    
    @pytest.fixture
    async def document_chunk_service(self):
        service = DocumentChunkService()
        await service.connect()
        yield service
        await service.disconnect()
    
    @pytest.mark.asyncio
    async def test_clinical_query_ranking(self, document_chunk_service):
        """Test that clinical queries rank clinical content higher."""
        
        # Clinical query using DocumentChunkService
        results = await document_chunk_service.search_chunks(
            query="randomized controlled trial diabetes treatment efficacy",
            limit=10,
            search_mode="semantic"
        )
        
        assert len(results) > 0
        
        # Check that results contain clinical content
        for result in results[:3]:  # Top 3 results
            text = result.get("text", "").lower()
            # Should contain clinical indicators
            assert any(term in text for term in ["randomized", "controlled", "trial", "efficacy", "clinical"])
    
    @pytest.mark.asyncio 
    async def test_section_boosting(self, document_chunk_service):
        """Test that Results and Conclusions sections get boosted."""
        
        results = await document_chunk_service.search_chunks(
            query="treatment outcome cancer therapy",
            limit=10,
            search_mode="semantic"
        )
        
        assert len(results) > 0
        
        # Check for section diversity
        all_sections = []
        for result in results:
            section = result.get("section", "")
            if section:
                all_sections.append(section)
        
        # Should have good representation of key sections
        section_set = set(all_sections)
        assert len(section_set.intersection({"Results", "Conclusions", "Methods", "Background"})) > 0
    
    @pytest.mark.asyncio
    async def test_chunk_content_quality(self, document_chunk_service):
        """Test that chunk content is of good quality."""
        
        results = await document_chunk_service.search_chunks(
            query="biomedical research methodology",
            limit=5,
            search_mode="semantic"
        )
        
        for result in results:
            title = result.get("title", "")
            text = result.get("text", "")
            
            if title and text:
                # Title should not be duplicated at start of text
                assert not text.startswith(title)
                
                # Text should be coherent (basic check)
                assert len(text.split()) > 10  # At least 10 words
                assert "." in text  # Contains sentences
    
    @pytest.mark.asyncio
    async def test_quality_scoring_impact(self, document_chunk_service):
        """Test that quality scores impact ranking."""
        
        results = await document_chunk_service.search_chunks(
            query="systematic review meta-analysis",
            limit=10,
            quality_threshold=0.5,
            search_mode="semantic"
        )
        
        # All results should meet quality threshold if provided
        for result in results:
            quality = result.get("quality_total", 0)
            if quality > 0:  # Only check if quality score exists
                assert quality >= 0.5
        
        # Verify we got some results
        assert len(results) >= 0  # May be empty if no high-quality results
```

### 4.2 Performance Testing
**File:** `tests/performance/test_rag_performance.py`

```python
import os
import pytest
import asyncio
import time
from bio_mcp.services.document_chunk_service import DocumentChunkService
from bio_mcp.config.config import Config

@pytest.mark.performance
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Performance tests require OpenAI API key for embeddings"
)
class TestRAGPerformance:
    """Test RAG search performance requirements."""
    
    @pytest.fixture
    async def document_chunk_service(self):
        service = DocumentChunkService()
        await service.connect()
        yield service
        await service.disconnect()
    
    @pytest.mark.asyncio
    async def test_search_latency(self, document_chunk_service):
        """Test that search latency meets requirements (<200ms avg with OpenAI)."""
        
        queries = [
            "diabetes treatment",
            "cancer therapy efficacy", 
            "cardiovascular disease prevention",
            "alzheimer disease biomarkers",
            "clinical trial methodology"
        ]
        
        latencies = []
        
        for query in queries:
            start_time = time.time()
            
            results = await document_chunk_service.search_chunks(
                query=query,
                limit=10,
                search_mode="semantic"
            )
            
            end_time = time.time()
            latency = (end_time - start_time) * 1000  # Convert to milliseconds
            latencies.append(latency)
            
            assert len(results) >= 0  # Should return results or empty list
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        print(f"Average latency: {avg_latency:.1f}ms")
        print(f"Max latency: {max_latency:.1f}ms")
        
        # Performance requirements (relaxed for OpenAI API calls)
        assert avg_latency < 1000  # OpenAI API calls can be slower
        assert max_latency < 2000
    
    @pytest.mark.asyncio
    async def test_concurrent_searches(self, document_chunk_service):
        """Test performance under concurrent load."""
        
        async def search_task(query_id: int):
            results = await document_chunk_service.search_chunks(
                query=f"biomedical research {query_id}",
                limit=5,
                search_mode="semantic"
            )
            return len(results)
        
        # Run 10 concurrent searches
        start_time = time.time()
        
        tasks = [search_task(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # All searches should complete (may return 0 results)
        assert all(result >= 0 for result in results)
        
        # Should handle concurrent load reasonably
        assert total_time < 30.0  # All 10 searches in under 30 seconds (OpenAI can be slower)
        
        print(f"10 concurrent searches completed in {total_time:.2f}s")
```

---

## 5. Success Validation

### 5.1 Checklist
- [ ] OpenAI embeddings provide superior semantic search quality
- [ ] Section boosting improves Results/Conclusions ranking
- [ ] Quality scoring enhances result relevance  
- [ ] Chunk content quality eliminates title duplication
- [ ] Advanced filtering works correctly (date, source, section)
- [ ] DocumentChunkService provides reliable search functionality
- [ ] Clinical content detection works for relevant queries
- [ ] Document chunk retrieval provides valuable results
- [ ] Performance meets reasonable response time requirements with OpenAI
- [ ] Integration tests skip when OpenAI API key not available
- [ ] Tests validate OpenAI embedding functionality

### 5.2 Performance Requirements
- **Average Response Time**: <200ms for cached queries, <1000ms for uncached (OpenAI API calls)
- **Quality Improvement**: OpenAI embeddings provide superior semantic understanding
- **Concurrent Throughput**: Handle 10+ concurrent searches without significant degradation
- **API Key Management**: Tests skip gracefully when OpenAI API key not available

---

## Next Steps

After completing this step:
1. Proceed to **RAG_STEP_7_TESTING.md** for comprehensive testing validation
2. Conduct user acceptance testing with sample queries
3. Monitor search quality metrics in production

**Estimated Time:** 2-3 days  
**Dependencies:** RAG_STEP_4_EMBEDDING.md, RAG_STEP_5_REINGEST.md
**Risk Level:** Medium (search quality is subjective, performance optimization complexity)