# NEW\_MULTI\_SOURCE\_SCHEMA.md

A compact, production-ready schema and query guide for a **single Weaviate collection** that supports multiple sources (PubMed now; ArXiv/CTGov/Web later) while avoiding:

* Python client `bm25()` **no filters** gap (use `hybrid(alpha=1.0)` or raw GraphQL)
* Filtering on `object` types (only filter on **scalars** or **references**)

---

## Goals

* One primary class for all documents
* Cross-source filters remain simple & fast (scalars)
* Source-specific facets are flattened (scalars) or normalized via references
* PubMed works **today**; other sources slot in without schema churn

---

## Design Decisions (TL;DR)

* **No `object` properties** for anything you plan to filter on
* Keep hot filters as **scalar** fields on the main class (`Document`)
* Use **references** for high-cardinality entities (Authors, Terms), and keep parallel denormalized string arrays when you need speed
* For BM25 + filters:

  * Use `hybrid(alpha=1.0)` in Python client (practical), **or**
  * Use raw GraphQL with `bm25` and `where`

---

## Classes

### `Document` (primary)

```json
{
  "class": "Document",
  "vectorizer": "text2vec-transformers",
  "moduleConfig": { "text2vec-transformers": { "vectorizeClassName": false } },
  "properties": [
    { "name": "doc_id",        "dataType": ["text"],   "indexInverted": true, "tokenization": "field" },
    { "name": "source",        "dataType": ["text"],   "indexInverted": true },   // e.g. "pubmed","arxiv","ctgov","web"
    { "name": "title",         "dataType": ["text"],   "indexInverted": true },
    { "name": "text",          "dataType": ["text"],   "indexInverted": true },   // full body
    { "name": "language",      "dataType": ["text"],   "indexInverted": true },
    { "name": "publishedDate", "dataType": ["date"],   "indexInverted": true },
    { "name": "publishedYear", "dataType": ["int"],    "indexInverted": true },

    // Cross-source, unified facets (filterable scalars)
    { "name": "venue",         "dataType": ["text"],   "indexInverted": true },   // journal/conference/site
    { "name": "keywords",      "dataType": ["text[]"], "indexInverted": true },   // tags/categories
    { "name": "identifiers",   "dataType": ["text[]"], "indexInverted": true },   // doi/pmid/arxiv_id/NCT...

    // Source-specific flattened facets (safe to filter)
    { "name": "pubmedJournal",   "dataType": ["text"],   "indexInverted": true },
    { "name": "pubmedMesh",      "dataType": ["text[]"], "indexInverted": true },
    { "name": "arxivPrimaryCat", "dataType": ["text"],   "indexInverted": true },
    { "name": "ctgovPhase",      "dataType": ["text"],   "indexInverted": true },
    { "name": "ctgovStatus",     "dataType": ["text"],   "indexInverted": true },

    // Optional normalized relations (enable join-like filters)
    { "name": "authors",       "dataType": ["Author"], "indexInverted": true },
    { "name": "terms",         "dataType": ["Term"],   "indexInverted": true }
  ]
}
```

### `Author`

```json
{
  "class": "Author",
  "properties": [
    { "name": "name",        "dataType": ["text"], "indexInverted": true },
    { "name": "affiliation", "dataType": ["text"], "indexInverted": true }
  ]
}
```

### `Term`

```json
{
  "class": "Term",
  "properties": [
    { "name": "scheme", "dataType": ["text"], "indexInverted": true },  // e.g. "MESH","ACM","Custom"
    { "name": "term",   "dataType": ["text"], "indexInverted": true }
  ]
}
```

---

## Ingestion Mapping (Current: **PubMed**)

* `source = "pubmed"`
* `venue = journal`
* `pubmedJournal = journal`
* `publishedDate` / `publishedYear` from PubDate (fallbacks: ArticleDate, ELocationID year)
* `identifiers += ["pmid:<PMID>"]` (+ `doi:<DOI>` if present)
* `pubmedMesh = [ "<MESH_TERM_1>", "<MESH_TERM_2>", ... ]`
* `keywords` can mirror MESH or PubMed keywords list
* Authors:

  * Create/merge `Author` nodes, link via `authors` ref
  * Optionally also denormalize into `keywords` (e.g., for quick filters)

> Keep **both** `pubmedMesh` (string array) and `terms` (refs to `Term {scheme="MESH"}`) if you need fast filters **and** normalized joins.

---

## Query Patterns

### 1) **Hybrid + filters** in Python client (works today)

```python
coll = client.collections.get("Document")
res = coll.query.hybrid(
    query="targeted therapy for melanoma",
    alpha=0.75,
    limit=10,
    filters={
        "operator": "And",
        "operands": [
            {"path": ["source"], "operator": "Equal", "valueText": "pubmed"},
            {"path": ["pubmedJournal"], "operator": "Equal", "valueText": "Nature"},
            {"path": ["publishedYear"], "operator": "GreaterThanEqual", "valueInt": 2021}
        ]
    }
)
```

### 2) **BM25 + filters** via raw GraphQL (exact BM25)

```graphql
{
  Get {
    Document(
      bm25: { query: "targeted therapy for melanoma" }
      where: {
        operator: And
        operands: [
          { path: ["source"],        operator: Equal,              valueText: "pubmed" }
          { path: ["pubmedJournal"], operator: Equal,              valueText: "Nature" }
          { path: ["publishedYear"], operator: GreaterThanEqual,   valueInt: 2021 }
        ]
      }
      limit: 10
    ) {
      title
      venue
      publishedYear
      _additional { score }
    }
  }
}
```

### 3) Filters through **references** (authors/terms)

```graphql
{
  Get {
    Document(
      hybrid: { query: "melanoma", alpha: 0.6 }
      where: {
        operator: And
        operands: [
          { path: ["source"], operator: Equal, valueText: "pubmed" },
          { path: ["authors","name"], operator: Equal, valueText: "Alice Smith" },
          { path: ["terms","scheme"], operator: Equal, valueText: "MESH" },
          { path: ["terms","term"],   operator: Equal, valueText: "Neoplasms" }
        ]
      }
    ) {
      title
      authors { ... on Author { name } }
      terms   { ... on Term   { scheme term } }
    }
  }
}
```

---

## Migration Notes (if coming from nested objects)

* **Do not** query/filter nested `object` paths like `meta.src.pubmed.journal`
* Create flattened scalar fields on `Document`:

  * `pubmedJournal` (string)
  * `pubmedMesh` (string array)
  * `venue`, `identifiers`, `keywords`, `publishedYear`
* Backfill from your existing nested metadata into these new fields
* Keep the original nested blob only if you need it for **display/audit**, not filtering

---

## Extending to New Sources (Later)

Add source-specific scalars as needed:

* **ArXiv:** `arxivPrimaryCat`, `venue="arXiv"`, `identifiers+=["arxiv:<id>"]`, categories → `keywords`
* **CTGov:** `ctgovPhase`, `ctgovStatus`, `venue="ClinicalTrials.gov"`, `identifiers+=["NCT:<id>"]`
* **Web:** `venue=<domain>`, `keywords` from page taxonomy

No changes to existing queries; you just add filters on the new scalars.

---

## Operational Tips

* Prefer **`hybrid(alpha=1.0)`** when you need “BM25-like” + filters in Python client
* For **exact BM25** + filters, call **GraphQL** directly
* For high-QPS filters, keep **denormalized string arrays** alongside references
* Avoid `object` for anything filterable—use **scalar** or **reference** only

---

## Checklist (PubMed-only, now)

* [ ] Deploy classes: `Document`, `Author`, `Term`
* [ ] Ingestion maps PubMed → flattened scalars + optional refs
* [ ] Backfill `venue`, `pubmedJournal`, `publishedYear`, `identifiers`, `pubmedMesh`
* [ ] Replace BM25 client calls with:

  * [ ] `hybrid(alpha=1.0)` **or**
  * [ ] Raw GraphQL for BM25 + filters
* [ ] Remove tests that rely on filtering nested `object` paths; replace with scalar filters

---

*End of file.*
