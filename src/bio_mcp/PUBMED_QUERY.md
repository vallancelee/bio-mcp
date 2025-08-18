# Evidence Ingestion & Querying Approach (Clinical + Basic Science)

This document outlines how to **fetch, tag, index, and retrieve** PubMed abstracts covering both **clinical trials** and the **basic science** that underpins them. It’s written for the MCP-only repo (Weaviate + SQL metadata + pluggable embeddings).

---

## Goals

* Pull **two evidence tiers**:

  * **Tier A: Clinical** — Phase I–III, RCTs, human studies.
  * **Tier B: Basic/Preclinical** — mechanism-of-action, animal models, in-vitro, target biology.
* Make the pipeline **incremental, idempotent, and auditable**.
* Enable retrieval that **prioritizes higher-quality clinical evidence** while **surfacing basic science** as context.

---

## 1) Query Strategy (PubMed)

Use PubMed’s fielded syntax with **EDAT windowing** in E-utilities. Keep a **3–7 day overlap** and dedupe by PMID downstream.

### 1.1 Building blocks

* Fields:
  `"[tiab]"` (title+abstract), `"[mh]"` (MeSH), `"[pt]"` (publication type)
* Humans-only filter:
  `NOT (animals[mh] NOT humans[mh])`
* Exclude opinion pieces (optional):
  `NOT (Review[pt] OR Editorial[pt] OR Letter[pt])`

### 1.2 Clinical evidence (Tier A)

```text
(<INDICATION>[mh] OR <INDICATION>[tiab])
AND ("Clinical Trial"[pt] OR "Randomized Controlled Trial"[pt] OR
     "Clinical Trial, Phase I"[pt] OR "Clinical Trial, Phase II"[pt] OR "Clinical Trial, Phase III"[pt])
AND (humans[mh] OR humans[tiab])
NOT (animals[mh] NOT humans[mh])
NOT (Review[pt] OR Editorial[pt] OR Letter[pt])
```

### 1.3 Basic/preclinical evidence (Tier B)

```text
(<TARGET>[tiab] OR <TARGET_MESH>[mh] OR <DRUG_NAME>[tiab])
AND (<INDICATION>[mh] OR <INDICATION>[tiab])
AND (mechanism[tiab] OR "molecular mechanism"[tiab] OR "signal transduction"[mh] OR
     "pharmacology"[sh] OR "pharmacodynamics"[tiab] OR "pharmacokinetics"[tiab] OR
     "in vitro"[tiab] OR "animal model"[tiab] OR mouse[tiab] OR rat[tiab] OR "preclinical"[tiab])
NOT (Review[pt] OR Editorial[pt] OR Letter[pt])
```

### 1.4 Combined “one-shot” query (both tiers)

```text
(<TARGET>[tiab] OR <TARGET_MESH>[mh] OR <DRUG_NAME>[tiab])
AND (<INDICATION>[mh] OR <INDICATION>[tiab])
AND (
  "Clinical Trial"[pt] OR "Randomized Controlled Trial"[pt] OR
  "Clinical Trial, Phase I"[pt] OR "Clinical Trial, Phase II"[pt] OR "Clinical Trial, Phase III"[pt] OR
  mechanism[tiab] OR "molecular mechanism"[tiab] OR "in vitro"[tiab] OR "animal model"[tiab] OR preclinical[tiab]
)
AND (humans[mh] OR humans[tiab] OR NOT animals[mh])   -- allows preclinical when intended
NOT (Review[pt] OR Editorial[pt] OR Letter[pt])
```

> Keep discrete **`query_key`s** per topic (e.g., `kras_nsclc_v1`, `glp1_obesity_v1`) so watermarks are tracked independently.

---

## 2) Incremental Sync

* Use **`datetype=edat`** with **`mindate = last_edat - overlap_days`**, **`maxdate = today`**.
* Batch-fetch details with `esummary` + `efetch` (efetch for abstracts).
* **Idempotent upsert** by PMID:

  * Insert new PMIDs.
  * Update (bump `version`) if `content_hash` changes or `LR` (LastRevised) advances.
* Advance checkpoint to **max EDAT observed** after successful index.

---

## 3) Evidence Tagging (at ingest)

Derive a normalized `evidence_type`:

* `clinical` if **any** of:

  * PublicationType contains `Randomized Controlled Trial`, `Clinical Trial`, `Phase I/II/III`.
  * MeSH contains **Humans** and publication type indicates trial.
* `preclinical` if **any** of:

  * Title/abstract contains: `preclinical`, `in vitro`, `animal model`, `mouse`, `rat`.
  * MeSH suggests animal-only and **not** humans.
* `basic` (fallback) for mechanistic/biology papers not clearly trials nor animal-only.
* Optional flags: `has_numbers` (regex for effect sizes, CIs, p-values), `has_biomarker`.

Store in SQL (`pubmed_docs.evidence_type`) and also copy `evidence_type` to each Weaviate chunk.

---

## 4) Chunking Policy (abstracts)

* Target **250–350 tokens**, max **450**, overlap **\~50** when needed.
* Section-aware: keep **Results/Conclusions** intact if short.
* **Numeric guard**: ensure a chunk containing a primary numeric claim also includes its comparator (expand boundary if needed).
* Stable `chunk_id`: `s<i>_<j>` for structured sections; `w<k>` for unstructured.

Each chunk properties (for Weaviate):

```
pmid, chunk_id, text, section, year, evidence_type, quality_total, edat, lr, source_url
```

UUID = `uuid5(ns, f"{pmid}:{chunk_id}")`.

---

## 5) Quality Scoring (document-level)

Heuristic 0–10 score (stored in SQL and copied to chunks as `quality_total`):

* **Design**: RCT/Meta > non-randomized > preclinical (0–3)
* **Recency**: ≤5y=2, ≤10y=1 (0–2)
* **Journal tier**: whitelist Tier-1 (+2) (0–2)
* **Human vs animal**: human +2, animal +1 (0–2)
* **Sample size (if parseable)**: >500=+2, 100–500=+1 (0–2)

Tune weights per domain if needed (oncology vs metabolic, etc.).

---

## 6) Embeddings & Indexing

* Embeddings via provider adapter (`openai` or `hf`); normalize vectors; assert `len==dim`.
* Weaviate class `PubMedChunk` with **client-supplied vectors** (vectorizer=none).
* Upsert chunks in batches (idempotent UUID).

---

## 7) Retrieval & Reranking

* Query Weaviate **Hybrid** (BM25 + vector). Oversample (e.g., `limit = top_k * 2`).
* Compute final score:

```
final = similarity * (1 + quality_total/10) * (1 + section_boost) * (1 + tier_weight)
```

* Suggested boosts:

  * `section_boost`: `Results` +0.10, `Conclusions` +0.05
  * `tier_weight` by `evidence_type`:

    * For **predictive** questions (“likelihood of success”): `clinical` +0.20, `preclinical` +0.05
    * For **mechanism** questions: `preclinical` +0.20, `basic` +0.10

* `rag.search` returns `{doc_id, uuid, sim, bm25, quality, evidence_type, score}`.

---

## 8) Synthesis Guardrails (downstream LLM)

When generating answers (outside MCP), enforce:

* **Citations-per-claim**: any numeric claim must include ≥1 citation pointing to a chunk with `has_numbers=true`.
* **Mix of evidence**: require at least one `clinical` and one `preclinical/basic` citation for mechanism-plus-efficacy questions.
* **Recency check**: prefer `year >= cutoff` unless older paper is uniquely relevant.

---

## 9) Data Model (SQL, minimal)

`pubmed_docs`:

* `pmid` (PK), `title`, `abstract`, `journal`, `pub_types[]`, `mesh[]`,
  `pdat`, `edat`, `lr`, `pmcid`,
  `evidence_type` (enum: clinical|preclinical|basic|other),
  `quality_json` (breakdown + total),
  `content_hash`, `version`, `last_seen_at`.

`checkpoints`:

* `query_key` (PK), `last_edat`, `last_scan_at`.

---

## 10) MCP Tools (signatures)

* `pubmed.sync_delta({ query_key, term, overlap_days }) -> { job_id, inserted, updated, skipped, pmids_processed, max_edat_seen }`
* `rag.search({ query, top_k, quality_bias }) -> { results: [...] }`
* `rag.get({ doc_id }) -> normalized document with quality + evidence_type`
* `corpus.checkpoint.get/set` for watermarks

(See `contracts.md` for JSON Schemas.)

---

## 11) Example Queries (drop-in)

**GLP-1 agonists for obesity — clinical + basic:**

```text
("GLP-1 receptor"[mh] OR "GLP-1 receptor agonist"[tiab] OR semaglutide[tiab] OR tirzepatide[tiab])
AND (Obesity[mh] OR obesity[tiab])
AND (
  "Clinical Trial"[pt] OR "Randomized Controlled Trial"[pt] OR
  "Clinical Trial, Phase I"[pt] OR "Clinical Trial, Phase II"[pt] OR "Clinical Trial, Phase III"[pt] OR
  mechanism[tiab] OR "pharmacodynamics"[tiab] OR "in vitro"[tiab] OR "animal model"[tiab] OR preclinical[tiab]
)
NOT (Review[pt] OR Editorial[pt] OR Letter[pt])
```

**KRAS G12C in NSCLC — clinical + basic:**

```text
("KRAS G12C"[tiab] OR "KRAS protein"[mh] OR sotorasib[tiab] OR adagrasib[tiab])
AND ("Carcinoma, Non-Small-Cell Lung"[mh] OR "non-small cell lung cancer"[tiab] OR NSCLC[tiab])
AND (
  "Clinical Trial"[pt] OR "Randomized Controlled Trial"[pt] OR
  "Clinical Trial, Phase II"[pt] OR "Clinical Trial, Phase III"[pt] OR
  mechanism[tiab] OR "signal transduction"[mh] OR "in vitro"[tiab] OR "animal model"[tiab]
)
NOT (Review[pt] OR Editorial[pt] OR Letter[pt])
```

---

## 12) Evaluation (fast sanity loop)

* Maintain 10–20 **gold questions** per topic (mechanism, efficacy, safety).
* Metrics:

  * **Recall\@K** of chunks containing primary numeric claims.
  * **Clinical-vs-basic balance** in citations.
  * **Answer pass rate** against a JSON schema (citations present, length bounds).
* Adjust: chunk size/overlap, evidence boosts, quality weights.

---

## 13) Ops Notes

* Rate-limit Entrez (\~3 rps with key); exponential backoff on 429/5xx.
* Watermarks are **monotonic**; overlap prevents gaps.
* Weaviate/EKS or WCS; nightly S3 backups.
* Errors returned with codes: `ENTREZ`, `EMBEDDINGS`, `WEAVIATE`, `STORE`.

---

## 14) Minimal Pseudocode (sync path)

```python
def sync_delta(query_key, term, overlap_days=5):
    last = get_checkpoint(query_key)  # SQL
    window = (last - overlap_days, now())

    pmids = esearch_delta(term, *window)            # Entrez
    docs  = fetch_and_normalize(pmids)              # esummary + efetch
    for d in docs:
        d["evidence_type"] = classify_evidence(d)   # clinical / preclinical / basic
        d["quality"] = score_pubmed(d)              # 0–10 + breakdown
    inserted, updated, skipped, max_edat = upsert_pubmed_docs(docs)  # SQL

    chunks = []
    for d in docs:
        for c in chunk_abstract(d):                 # section-aware, numeric guard
            c["quality_total"] = d["quality"]["total"]
            c["evidence_type"] = d["evidence_type"]
            chunks.append(c)

    vectors = embeddings.embed([c["text"] for c in chunks])
    attach_vectors(chunks, vectors)
    weaviate_upsert(chunks)

    set_checkpoint(query_key, max_edat)
    return report(inserted, updated, skipped, len(pmids), max_edat)
```

---

**That’s it.** This keeps your corpus small, fresh, and useful: **clinical** abstracts anchor the claims; **basic science** explains *why* those claims might hold.
