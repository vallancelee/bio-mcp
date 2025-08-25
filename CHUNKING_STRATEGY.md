# Bio-MCP Chunking Strategy

**Implementation**: `src/bio_mcp/services/chunking.py`

This document outlines the section-aware chunking strategy optimized for PubMed abstracts, designed to maximize retrieval effectiveness for biomedical research.

## Goals

* Maximize chance a single chunk contains the **claim + number + comparator**.
* Preserve section semantics (Background/Methods/Results/Conclusions).
* Keep **stable chunk IDs** for idempotent upserts.
* Support deterministic UUIDv5-based chunk identifiers.

## Implementation Parameters

**Current Configuration (ChunkingConfig):**
* **Target tokens per chunk:** 325 (configurable via `BIO_MCP_CHUNKER_TARGET_TOKENS`)
* **Max tokens:** 450 (hard cap, configurable via `BIO_MCP_CHUNKER_MAX_TOKENS`)
* **Min tokens:** 120 (minimum section size, configurable via `BIO_MCP_CHUNKER_MIN_TOKENS`)
* **Overlap:** 50 tokens (configurable via `BIO_MCP_CHUNKER_OVERLAP_TOKENS`)
* **Chunker version:** v1.2.0 (configurable via `BIO_MCP_CHUNKER_VERSION`)

**Supported Tokenizers:**
* **TikToken (OpenAI):** `cl100k_base` encoding (aligned with OpenAI embeddings)
* **HuggingFace:** BioBERT tokenizer (`pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb`)

---

## Step 1 — Normalize

1. Unicode NFKC normalize, collapse multiple spaces, strip HTML.
2. Join hyphenated line breaks (`e.g.\n` → `e.g.`).
3. Keep units/symbols as-is (mg, %, CI, p=, Δ).
4. Keep the **title**; you’ll prepend it to the **first** chunk as context.

---

## Step 2 — Detect structure

The implementation supports both structured and unstructured abstracts:

* **Structured**: headings like *Background, Methods, Results, Conclusions*
* **Unstructured**: continuous text without explicit sections

**Section Detection Pattern:**
```python
r'^\s*([A-Za-z\s&/-]+?)\s*[:：\-–—]\s*(.*?)(?=^\s*[A-Za-z\s&/-]+?\s*[:：\-–—]|$)'
```

**Section Name Normalization:**
The implementation maps various section heading variations to standardized names:
- `background`, `introduction`, `rationale` → `Background`
- `objective`, `objectives`, `aim`, `aims`, `purpose`, `goal`, `goals` → `Objective`  
- `methods`, `method`, `materials`, `design`, `setting`, `participants`, `interventions`, `measures` → `Methods`
- `results`, `result`, `findings`, `outcomes` → `Results`
- `conclusions`, `conclusion`, `interpretation`, `implications`, `limitations` → `Conclusions`

---

## Step 3 — Section-aware chunking

### A) Structured abstracts

* Treat each section as a **micro-chunk candidate**.
* Merge adjacent small sections so each final chunk is **≥120 tokens** and **≤450 tokens**.
* If a section exceeds 450 tokens, split it on **sentence boundaries** with **50-token overlap**.
* Always keep **Results** and **Conclusions** together if they’re short; they carry the claims.

### B) Unstructured abstracts

* Split by sentences into windows of **250–350 tokens**, **50-token overlap** if needed.
* If the whole abstract ≤ 450 tokens → **single chunk**.

**Sentence boundaries:** use a robust splitter (e.g., spaCy) to avoid breaking “1.5 mg/kg” or “p = 0.03”.

---

## Step 4 — Enrich each chunk

Include lightweight headers so retrieval understands where it came from:

```
[Title] Once-weekly XYZ vs placebo in obesity (pmid:12345)
[Section] Results
[Text] Mean weight change at 48 weeks was −12.4% vs −2.1% (Δ=−10.3 pp; p<0.001)...
```

This header text counts toward tokens but dramatically helps BM25/hybrid.

---

## Step 5 — Metadata & IDs (Implementation)

The implementation generates chunks with comprehensive metadata using the `Chunk` model:

```python
@dataclass 
class Chunk(BaseModel):
    chunk_id: str           # stable: "s0", "w1" format 
    uuid: str               # UUIDv5: uuid5(namespace, f"{parent_uid}:{chunk_id}")
    parent_uid: str         # e.g., "pubmed:12345678"
    source: str            # "pubmed"
    chunk_idx: int         # 0, 1, 2, ...
    text: str              # actual chunk content
    title: str | None      # document title
    section: str | None    # Background/Methods/Results/Conclusions/Unstructured
    tokens: int | None     # token count via tokenizer
    n_sentences: int | None # sentence count
    published_at: datetime | None
    meta: dict[str, Any]   # additional metadata including chunker_version
```

**Deterministic UUIDs**: Uses UUIDv5 with a fixed namespace (`BIO_MCP_UUID_NAMESPACE`) ensuring idempotent re-upserts:
```python
chunk.uuid = uuid5(CHUNK_UUID_NAMESPACE, f"{parent_uid}:{chunk_id}")
```

---

## Step 6 — Special rules for numbers (important)

* If a sentence contains **primary endpoint numbers** (e.g., effect size, CI, p-value), **ensure** the same chunk also includes the comparator/control phrase. If splitting would separate them, **expand** that chunk boundary to include the adjacent sentence (even if it exceeds target by \~10–15%).
* Don’t split inside parentheses containing statistics.

---

## Step 7 — Title handling

* **Prefix title only on the first chunk** (or include it as a separate small chunk `chunk_id="title"` if you want it retrievable).
* Avoid repeating title on every chunk—it wastes tokens and can bias ranking.

---

## Step 8 — Very short abstracts / no abstract

* If `< 80 tokens`:

  * Create **one** chunk with title + abstract.
  * Optionally add MeSH terms as a short suffix: `"[MeSH] Obesity; GLP-1 Receptor; Randomized Controlled Trial"`.
* If **no abstract** (some editorials or corrections):

  * Skip chunking; store metadata only with a tiny “metadata-only” chunk so results can still cite the paper.

---

## Step 9 — Quality-aware retrieval (Implementation)

The implementation provides configurable section boosting via search configuration:

**Section Boost Weights** (configurable via environment variables):
- `Results`: +0.15 (configurable via `BIO_MCP_BOOST_RESULTS_SECTION`)
- `Conclusions`: +0.12 (configurable via `BIO_MCP_BOOST_CONCLUSIONS_SECTION`) 
- `Methods`: +0.05 (configurable via `BIO_MCP_BOOST_METHODS_SECTION`)
- `Background`: +0.02 (configurable via `BIO_MCP_BOOST_BACKGROUND_SECTION`)

**Quality Boost Factor**: +0.1 (configurable via `BIO_MCP_QUALITY_BOOST_FACTOR`)

**Recency Boosting** (configurable via environment variables):
- Recent (≤2 years): Enhanced boost
- Moderate (≤5 years): Medium boost  
- Older (≤10 years): Minimal boost

---

## Step 10 — Evaluation knobs to tune later

* Try **no overlap** vs **50-token** overlap; check hit-rate on a small gold set.
* Try **350 vs 500** token targets for oncology (often longer) vs metabolic (often shorter).
* Measure **Recall\@K of numeric claims** (does the top-5 contain the sentence with Δ and p?).

---

## Pseudocode (compact)

```python
def chunk_abstract(pmid, title, abstract, sections=None, tgt=325, max_tok=450, ovlp=50):
    text_blocks = []
    if sections:  # structured
        for i, (name, body) in enumerate(sections):
            sents = split_sentences(body)
            blocks = window_by_tokens(sents, max_tokens=max_tok, min_tokens=120, overlap=ovlp)
            for j, blk in enumerate(blocks):
                text_blocks.append((f"s{i}_{j}", name, blk))
    else:  # unstructured
        sents = split_sentences(abstract)
        if tokens(abstract) <= max_tok:
            text_blocks.append(("w0", "Unstructured", abstract))
        else:
            windows = sliding_windows_by_tokens(sents, target=tgt, overlap=ovlp, hard_max=max_tok)
            for j, blk in enumerate(windows):
                text_blocks.append((f"w{j}", "Unstructured", blk))

    # Numeric safety: expand window if stats/comparator split
    text_blocks = expand_around_stats(text_blocks)

    # Prefix title on first chunk only
    out = []
    for k, (cid, sec, body) in enumerate(text_blocks):
        txt = body if k else f"{title}\n[Section] {sec}\n{body}"
        out.append({
            "pmid": pmid,
            "chunk_id": cid,
            "section": sec,
            "text": txt.strip(),
            "token_count": tokens(txt),
        })
    return out
```

---

### Why this works for PubMed

* Most abstracts are already short → **one chunk** wins; the strategy degrades gracefully for long, structured ones.
* Section-awareness improves precision (especially for queries like “primary endpoint”, “adverse events”).
* Numeric-guard rule reduces the classic failure where the **effect size** is separated from the **comparator**.

---

## Implementation Reference

The complete implementation is available in:
- **Main chunking service**: `src/bio_mcp/services/chunking.py`
- **Document models**: `src/bio_mcp/models/document.py`
- **Configuration**: `src/bio_mcp/config/config.py`

**Key Classes:**
- `ChunkingConfig`: Configuration parameters
- `HuggingFaceTokenizer` / `TikTokenTokenizer`: Tokenizer implementations
- `SectionDetector`: Section parsing with normalization
- `SentenceSplitter`: spaCy and fallback sentence splitting
- `AbstractChunker`: Main chunking orchestration

**Usage Example:**
```python
from bio_mcp.services.chunking import AbstractChunker, ChunkingConfig
from bio_mcp.models.document import Document

config = ChunkingConfig(target_tokens=325, max_tokens=450)
chunker = AbstractChunker(config)

document = Document(
    uid="pubmed:12345678",
    source="pubmed", 
    source_id="12345678",
    title="Study Title",
    text="Background: ... Methods: ... Results: ... Conclusions: ..."
)

chunks = chunker.chunk_document(document)
```
