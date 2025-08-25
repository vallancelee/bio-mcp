# RAG Step 6: RAG Search Improvements (Simplified)

**Objective:** Enhance RAG search capabilities with section boosting, quality ranking, and improved result reconstruction while maintaining simplicity and working within existing patterns.

**Success Criteria:**
- Section-aware boosting improves Results/Conclusions ranking
- Quality scoring enhances result ranking  
- Clean abstract reconstruction without title duplication
- Simple biomedical query enhancement
- Tests properly skip when OpenAI API key not available
- Maintains existing DocumentChunkService patterns

---

## 1. Enhanced DocumentChunkService Search

### 1.1 Add Ranking Enhancements to DocumentChunkService
**File:** `src/bio_mcp/services/document_chunk_service.py`

Add these methods to the existing DocumentChunkService class:

```python
def _apply_section_boost(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply boost to Results and Conclusions sections."""
    section_weights = {
        "Results": 0.15,
        "Conclusions": 0.12,
        "Methods": 0.05,
        "Background": 0.02,
        "Unstructured": 0.0
    }
    
    for chunk in chunks:
        section = chunk.get("section", "Unstructured")
        boost = section_weights.get(section, 0.0)
        
        # Apply boost to score if present
        if "score" in chunk:
            chunk["score"] = chunk["score"] + boost
            chunk["section_boost"] = boost
    
    return chunks

def _apply_quality_boost(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply boost based on quality_total score."""
    for chunk in chunks:
        quality = chunk.get("quality_total", 0.0)
        
        # Scale quality from 0-1 to 0-0.1 boost
        quality_boost = quality * 0.1
        
        if "score" in chunk:
            chunk["score"] = chunk["score"] + quality_boost
            chunk["quality_boost"] = quality_boost
    
    return chunks

def _apply_recency_boost(self, chunks: list[dict[str, Any]], boost_recent: bool = True) -> list[dict[str, Any]]:
    """Apply boost to recent documents."""
    if not boost_recent:
        return chunks
        
    from datetime import datetime
    current_year = datetime.now().year
    
    for chunk in chunks:
        year = chunk.get("year")
        if year and isinstance(year, int):
            years_old = current_year - year
            
            if years_old <= 2:
                recency_boost = 0.1
            elif years_old <= 5:
                recency_boost = 0.05
            elif years_old <= 10:
                recency_boost = 0.02
            else:
                recency_boost = 0
            
            if "score" in chunk and recency_boost > 0:
                chunk["score"] = chunk["score"] + recency_boost
                chunk["recency_boost"] = recency_boost
    
    return chunks
```

Update the `search_chunks` method to apply these boosts:

```python
async def search_chunks(
    self,
    query: str,
    limit: int = 10,
    search_mode: str = "hybrid",
    alpha: float = 0.5,
    filters: dict | None = None,
    apply_boosts: bool = True,  # New parameter
    boost_recent: bool = True,   # New parameter
    # ... existing parameters ...
) -> list[dict[str, Any]]:
    """
    Search chunks using different search modes with filtering and quality boosting.
    
    Args:
        ... existing args ...
        apply_boosts: Apply section and quality boosts (default True)
        boost_recent: Apply recency boost (default True)
    """
    # ... existing search logic ...
    
    # After getting results from Weaviate, apply boosts
    if results and apply_boosts:
        results = self._apply_section_boost(results)
        results = self._apply_quality_boost(results)
        results = self._apply_recency_boost(results, boost_recent)
        
        # Re-sort by boosted scores
        if all("score" in r for r in results):
            results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return results[:limit]
```

---

## 2. Fix Abstract Reconstruction in RAG Tools

### 2.1 Update RAGToolsManager for Clean Document Reconstruction
**File:** `src/bio_mcp/mcp/rag_tools.py`

Add document reconstruction methods to the existing RAGToolsManager:

```python
def _reconstruct_documents(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Group chunks by parent document and reconstruct clean abstracts.
    """
    from collections import defaultdict
    
    # Group chunks by parent_uid
    doc_chunks = defaultdict(list)
    for chunk in chunks:
        parent_uid = chunk.get("parent_uid")
        if parent_uid:
            doc_chunks[parent_uid].append(chunk)
    
    # Reconstruct each document
    documents = []
    for parent_uid, chunks_list in doc_chunks.items():
        if not chunks_list:
            continue
            
        # Use first chunk for metadata
        first_chunk = chunks_list[0]
        
        # Reconstruct abstract without title duplication
        abstract = self._reconstruct_abstract(chunks_list)
        
        document = {
            "uid": parent_uid,
            "source": first_chunk.get("source", ""),
            "title": first_chunk.get("title", ""),
            "abstract": abstract,
            "published_at": first_chunk.get("published_at"),
            "year": first_chunk.get("year"),
            "quality_total": first_chunk.get("quality_total", 0.0),
            "chunk_count": len(chunks_list),
            "sections_found": list(set(c.get("section", "Unstructured") for c in chunks_list)),
            "best_score": max((c.get("score", 0) for c in chunks_list), default=0),
            "avg_score": sum(c.get("score", 0) for c in chunks_list) / len(chunks_list) if chunks_list else 0,
            "meta": first_chunk.get("meta", {})
        }
        
        # Add source URL if PubMed
        if document["source"] == "pubmed" and ":" in parent_uid:
            pmid = parent_uid.split(":")[-1]
            document["source_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        
        documents.append(document)
    
    # Sort by best chunk score
    documents.sort(key=lambda x: x.get("best_score", 0), reverse=True)
    
    return documents

def _reconstruct_abstract(self, chunks: list[dict[str, Any]]) -> str:
    """
    Reconstruct abstract from chunks without title duplication.
    """
    if not chunks:
        return ""
    
    # Sort chunks by section order and chunk index
    section_order = {
        "Background": 0,
        "Methods": 1, 
        "Results": 2,
        "Conclusions": 3,
        "Other": 4,
        "Unstructured": 5
    }
    
    def chunk_sort_key(chunk):
        section = chunk.get("section", "Unstructured")
        section_priority = section_order.get(section, 99)
        
        # Try to extract chunk index from UUID pattern
        uuid = chunk.get("uuid", "")
        chunk_idx = 0
        if ":" in uuid:
            try:
                # Pattern like "pubmed:12345678:s0" or "pubmed:12345678:w1"
                parts = uuid.split(":")
                if len(parts) > 2 and parts[-1]:
                    idx_part = parts[-1][1:]  # Remove 's' or 'w' prefix
                    if idx_part.isdigit():
                        chunk_idx = int(idx_part)
            except:
                pass
        
        return (section_priority, chunk_idx)
    
    sorted_chunks = sorted(chunks, key=chunk_sort_key)
    
    # Get title to avoid duplication
    title = chunks[0].get("title", "") if chunks else ""
    
    # Reconstruct text
    text_parts = []
    for chunk in sorted_chunks:
        text = chunk.get("text", "").strip()
        
        # Remove title if it appears at the start of chunk text
        if title and text.startswith(title):
            text = text[len(title):].strip()
        
        # Remove section headers if present
        section = chunk.get("section", "")
        if section and section != "Unstructured":
            # Common header patterns to remove
            headers = [
                f"[Section] {section}",
                f"{section}:",
                f"{section} -",
                f"{section}.",
                section
            ]
            for header in headers:
                if text.startswith(header):
                    text = text[len(header):].strip()
                    break
        
        if text:
            text_parts.append(text)
    
    # Join with single space and clean up
    abstract = " ".join(text_parts)
    
    # Clean up multiple spaces
    import re
    abstract = re.sub(r'\s+', ' ', abstract)
    abstract = abstract.strip()
    
    return abstract
```

Update the `search_documents` method to use reconstruction:

```python
async def search_documents(
    self,
    query: str,
    top_k: int = 5,
    search_mode: str = "hybrid",
    filters: dict | None = None,
    rerank_by_quality: bool = True,
    alpha: float = 0.5,
    return_chunks: bool = False,  # New parameter
) -> RAGSearchResult:
    """
    Search documents using hybrid, semantic, or BM25 search with document reconstruction.
    """
    logger.info(
        "RAG hybrid search",
        query=query[:50],
        top_k=top_k,
        mode=search_mode,
        alpha=alpha,
    )

    try:
        await self.document_chunk_service.connect()

        # Search with boosts enabled
        chunk_results = await self.document_chunk_service.search_chunks(
            query=query,
            limit=top_k * 3 if not return_chunks else top_k,  # Get more chunks for document reconstruction
            search_mode=search_mode,
            alpha=alpha,
            filters=filters,
            apply_boosts=rerank_by_quality,
            boost_recent=True
        )

        if return_chunks:
            # Return raw chunks
            return RAGSearchResult(
                query=query,
                total_results=len(chunk_results),
                documents=chunk_results,
                search_type=search_mode
            )
        else:
            # Reconstruct documents from chunks
            documents = self._reconstruct_documents(chunk_results)
            
            return RAGSearchResult(
                query=query,
                total_results=len(documents),
                documents=documents[:top_k],
                search_type=search_mode
            )

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise
    finally:
        await self.document_chunk_service.disconnect()
```

---

## 3. Add Simple Query Enhancement

### 3.1 Basic Biomedical Query Enhancement
**File:** `src/bio_mcp/mcp/rag_tools.py`

Add simple query enhancement inline (no separate class needed):

```python
def _enhance_biomedical_query(self, query: str) -> str:
    """
    Simple biomedical query enhancement with common synonyms and expansions.
    """
    query_lower = query.lower()
    enhanced = query
    
    # Common biomedical synonyms
    synonyms = {
        "covid-19": "coronavirus SARS-CoV-2 COVID",
        "covid": "COVID-19 coronavirus SARS-CoV-2",
        "diabetes": "diabetes mellitus diabetic",
        "cancer": "neoplasm tumor malignancy carcinoma",
        "heart disease": "cardiovascular disease cardiac",
        "alzheimer": "alzheimer's disease AD dementia",
        "parkinson": "parkinson's disease PD",
    }
    
    # Add synonyms if found
    for term, expansion in synonyms.items():
        if term in query_lower:
            enhanced = f"{enhanced} {expansion}"
    
    # Clinical trial indicators
    if any(term in query_lower for term in ["trial", "rct", "study"]):
        enhanced = f"{enhanced} clinical trial randomized controlled"
    
    # Treatment indicators
    if any(term in query_lower for term in ["treatment", "therapy", "drug"]):
        enhanced = f"{enhanced} therapeutic intervention efficacy"
    
    # Only return enhanced if actually changed
    return enhanced if enhanced != query else query
```

Use enhancement in search:

```python
async def search_documents(self, query: str, ...):
    # Enhance query for biomedical context
    enhanced_query = self._enhance_biomedical_query(query)
    
    # Use enhanced query for search
    chunk_results = await self.document_chunk_service.search_chunks(
        query=enhanced_query,
        ...
    )
```

---

## 4. Integration Tests

### 4.1 Quality Testing
**File:** `tests/integration/test_rag_quality.py`

```python
import os
import pytest
from bio_mcp.mcp.rag_tools import RAGToolsManager

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="RAG quality tests require OpenAI API key for embeddings"
)
class TestRAGQuality:
    """Test RAG search quality improvements."""
    
    @pytest.fixture
    async def rag_tools_manager(self):
        manager = RAGToolsManager()
        yield manager
    
    @pytest.mark.asyncio
    async def test_section_boosting(self, rag_tools_manager):
        """Test that Results and Conclusions sections get boosted."""
        
        results = await rag_tools_manager.search_documents(
            query="treatment efficacy clinical outcomes",
            top_k=10,
            search_mode="hybrid"
        )
        
        # Check that we get results
        assert results.total_results > 0
        
        # Check that documents have section information
        for doc in results.documents[:3]:
            assert "sections_found" in doc
            # High-value sections should appear frequently in top results
            sections = doc.get("sections_found", [])
            assert len(sections) > 0
    
    @pytest.mark.asyncio
    async def test_no_title_duplication(self, rag_tools_manager):
        """Test that abstract reconstruction doesn't duplicate titles."""
        
        results = await rag_tools_manager.search_documents(
            query="diabetes treatment",
            top_k=5,
            search_mode="hybrid"
        )
        
        for doc in results.documents:
            title = doc.get("title", "")
            abstract = doc.get("abstract", "")
            
            if title and abstract:
                # Abstract should not start with the title
                assert not abstract.startswith(title), f"Abstract starts with title: {title[:50]}"
    
    @pytest.mark.asyncio
    async def test_quality_boost_impact(self, rag_tools_manager):
        """Test that quality scores impact ranking."""
        
        # Search with quality boosting enabled (default)
        results_with_boost = await rag_tools_manager.search_documents(
            query="systematic review meta-analysis",
            top_k=10,
            rerank_by_quality=True
        )
        
        # Search without quality boosting
        results_without_boost = await rag_tools_manager.search_documents(
            query="systematic review meta-analysis",
            top_k=10,
            rerank_by_quality=False
        )
        
        # Both should return results
        assert results_with_boost.total_results > 0
        assert results_without_boost.total_results > 0
        
        # Top results with boost should have good quality scores
        if results_with_boost.documents:
            top_doc = results_with_boost.documents[0]
            assert "quality_total" in top_doc
    
    @pytest.mark.asyncio
    async def test_biomedical_query_enhancement(self, rag_tools_manager):
        """Test that biomedical queries get enhanced appropriately."""
        
        # Test COVID-19 query enhancement
        results = await rag_tools_manager.search_documents(
            query="COVID-19 treatment",
            top_k=5
        )
        
        assert results.total_results > 0
        
        # Should find coronavirus-related content
        for doc in results.documents:
            abstract = doc.get("abstract", "").lower()
            # Should match COVID, coronavirus, or SARS-CoV-2
            assert any(term in abstract for term in ["covid", "coronavirus", "sars-cov-2"])
```

---

## 5. Configuration Updates

### 5.1 Add Search Tuning Parameters
**File:** Update `.env.example`

```bash
# =============================================================================
# SEARCH TUNING CONFIGURATION
# =============================================================================

# Section boost weights (0.0-1.0)
BIO_MCP_BOOST_RESULTS_SECTION="0.15"
BIO_MCP_BOOST_CONCLUSIONS_SECTION="0.12"
BIO_MCP_BOOST_METHODS_SECTION="0.05"
BIO_MCP_BOOST_BACKGROUND_SECTION="0.02"

# Quality boost factor (0.0-0.2)
BIO_MCP_QUALITY_BOOST_FACTOR="0.1"

# Recency boost thresholds (years)
BIO_MCP_RECENCY_RECENT_YEARS="2"
BIO_MCP_RECENCY_MODERATE_YEARS="5"
BIO_MCP_RECENCY_OLD_YEARS="10"

# Document reconstruction
BIO_MCP_CHUNK_MULTIPLIER="3"  # Get N times more chunks than requested docs
```

---

## 6. Success Validation

### 6.1 Checklist
- [ ] Section boosting improves Results/Conclusions ranking
- [ ] Quality scoring enhances result relevance
- [ ] Clean abstract reconstruction without title duplication
- [ ] Simple biomedical query enhancement works
- [ ] Maintains backward compatibility with existing code
- [ ] Tests skip gracefully when OpenAI API key not available
- [ ] No unnecessary abstractions or over-engineering

### 6.2 Performance Requirements
- **Simplicity**: Minimal code changes within existing patterns
- **Maintainability**: No new complex classes or abstractions
- **Compatibility**: Works with existing DocumentChunkService
- **Testability**: Clear, focused integration tests

---

## What We're NOT Implementing

Based on the actual codebase analysis, we're intentionally NOT implementing:

1. ❌ **EnhancedRAGTools class** - Unnecessary abstraction
2. ❌ **BiomedicalQueryProcessor class** - Over-engineered for current needs
3. ❌ **SearchResultProcessor class** - Premature optimization
4. ❌ **SearchCache class** - Not needed yet
5. ❌ **Complex clustering algorithms** - YAGNI
6. ❌ **Search suggestions endpoint** - Out of scope
7. ❌ **Find similar documents feature** - Can use existing semantic search with document's abstract as query
8. ❌ **Evidence level classification** - Too complex for current phase

Note: Semantic similarity search is ALREADY implemented in DocumentChunkService through the "semantic" and "hybrid" search modes using OpenAI embeddings.

---

## Next Steps

After implementing these improvements:
1. Run integration tests with OpenAI API key
2. Verify section boosting improves relevance
3. Confirm abstract reconstruction is clean
4. Consider performance monitoring in production

**Estimated Time:** 1 day
**Dependencies:** Existing DocumentChunkService and RAGToolsManager
**Risk Level:** Low (minimal changes, maintains existing patterns)