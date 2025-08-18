Here’s a pragmatic chunking recipe tuned for **PubMed abstracts** that keeps retrieval strong and simple:

# Goals

* Maximize chance a single chunk contains the **claim + number + comparator**.
* Preserve section semantics (Background/Methods/Results/Conclusions).
* Keep **stable chunk ids** for idempotent upserts.

# Defaults (good starting points)

* **Target tokens per chunk:** 250–350 (≈ 1,000–1,400 chars).
* **Max tokens:** 450 (hard cap).
* **Overlap:** 50 tokens (only when an abstract is unusually long).
* **Tokenizer:** same family as your embedding model (or tiktoken for OpenAI).

---

## Step 1 — Normalize

1. Unicode NFKC normalize, collapse multiple spaces, strip HTML.
2. Join hyphenated line breaks (`e.g.\n` → `e.g.`).
3. Keep units/symbols as-is (mg, %, CI, p=, Δ).
4. Keep the **title**; you’ll prepend it to the **first** chunk as context.

---

## Step 2 — Detect structure

Most PubMed abstracts are either:

* **Structured**: headings like *Background, Methods, Results, Conclusions* (or *Objective, Design, Setting, Participants, Interventions, Main Outcome Measures, Results, Conclusions*).
* **Unstructured**: one or two paragraphs.

Detection: look for heading prefixes `^\s*(Background|Objective|Methods?|Results?|Conclusions?|Interpretation|Limitations)\s*[:\-–]`.

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

## Step 5 — Metadata & IDs

For every chunk produce:

```json
{
  "pmid": "12345",
  "chunk_id": "s0"          // stable: sN for section index, or wN for window index
  "title": "...",
  "section": "Results",     // or "Unstructured"
  "text": "...",            // the actual chunk text
  "n_sentences": 6,
  "token_count": 285,
  "quality_total": 8,       // inherit from document-level score
  "year": 2024,
  "edat": "2024-06-02T00:00:00Z",
  "lr": "2024-06-15T00:00:00Z",
  "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345/"
}
```

**Stable UUID** for Weaviate: `uuid5(namespace, f"{pmid}:{chunk_id}")`.
This guarantees idempotent re-upserts even if you re-run chunking.

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

## Step 9 — Quality-aware retrieval

* Store `quality_total` on every chunk (inherit from the doc).
* At query-time: `final_score = sim * (1 + quality_total/10)`.
* Optionally **boost** sections: `Results: +0.1`, `Conclusions: +0.05`.

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

If you want, I can turn this into a ready-to-drop `lib/chunking.py` with a tiny spaCy-based splitter and a tiktoken counter that matches your embedding model.
