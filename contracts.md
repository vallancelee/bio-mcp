This document defines the public contracts between MCP clients and the bio-mcp server, plus internal adapter boundaries. All request/response bodies are JSON. Changes follow semver; breaking changes bump the major version.

# MCP API (Public)
## Tool: pubmed.sync_delta

Purpose: Incrementally sync PubMed records for a query using EDAT windowing, upsert metadata, chunk+embed, and push to Weaviate.

Request
{
  "type": "object",
  "required": ["query_key", "term"],
  "properties": {
    "query_key": { "type": "string", "minLength": 1 },
    "term": { "type": "string", "minLength": 1 },
    "overlap_days": { "type": "integer", "minimum": 0, "default": 5 }
  },
  "additionalProperties": false
}


Response
{
  "type": "object",
  "required": ["job_id", "inserted", "updated", "skipped", "pmids_processed"],
  "properties": {
    "job_id": { "type": "string" },
    "inserted": { "type": "integer", "minimum": 0 },
    "updated": { "type": "integer", "minimum": 0 },
    "skipped": { "type": "integer", "minimum": 0 },
    "pmids_processed": { "type": "integer", "minimum": 0 },
    "max_edat_seen": { "type": ["string","null"], "description": "ISO8601 UTC timestamp or null" },
    "warnings": {
      "type": "array",
      "items": { "type": "string" }
    }
  },
  "additionalProperties": false
}


Notes / Guarantees

Idempotent: safe to replay; watermark uses EDAT with overlap.

Version bumps on content change or LR advance.

## Tool: rag.search

Purpose: Retrieve top-K chunks from Weaviate using hybrid search, optionally reranked by quality.

Request
{
  "type": "object",
  "required": ["query"],
  "properties": {
    "query": { "type": "string", "minLength": 1 },
    "top_k": { "type": "integer", "minimum": 1, "maximum": 100, "default": 20 },
    "quality_bias": { "type": "boolean", "default": true }
  },
  "additionalProperties": false
}


Response
{
  "type": "object",
  "required": ["results"],
  "properties": {
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["doc_id", "uuid", "score"],
        "properties": {
          "doc_id": { "type": "string", "pattern": "^pmid:[0-9]+$" },
          "uuid": { "type": "string", "minLength": 10 },
          "sim": { "type": ["number","null"] },
          "bm25": { "type": ["number","null"] },
          "quality": { "type": ["number","null"] },
          "score": { "type": "number" }
        },
        "additionalProperties": false
      }
    }
  },
  "additionalProperties": false
}


Notes / Guarantees

score is the final rerank key (quality-weighted if enabled).

doc_id is the stable key for rag.get / resource lookup.

## Tool: rag.get

Purpose: Fetch the normalized document metadata and quality scores for a doc_id.

Request
{
  "type": "object",
  "required": ["doc_id"],
  "properties": {
    "doc_id": { "type": "string", "pattern": "^pmid:[0-9]+$" }
  },
  "additionalProperties": false
}


Response
{
  "type": "object",
  "required": ["doc_id", "title", "journal", "pub_types", "quality", "version"],
  "properties": {
    "doc_id": { "type": "string" },
    "title": { "type": ["string","null"] },
    "abstract": { "type": ["string","null"] },
    "journal": { "type": ["string","null"] },
    "pub_types": { "type": "array", "items": { "type": "string" } },
    "pdat": { "type": ["string","null"] },
    "edat": { "type": ["string","null"] },
    "lr": { "type": ["string","null"] },
    "pmcid": { "type": ["string","null"] },
    "quality": {
      "type": "object",
      "required": ["total"],
      "properties": {
        "design": { "type": ["integer","null"] },
        "recency": { "type": ["integer","null"] },
        "journal": { "type": ["integer","null"] },
        "human": { "type": ["integer","null"] },
        "total": { "type": "integer" }
      },
      "additionalProperties": false
    },
    "version": { "type": "integer", "minimum": 1 }
  },
  "additionalProperties": false
}

## Tools: corpus.checkpoint.get / corpus.checkpoint.set

Get Request
{
  "type": "object",
  "required": ["query_key"],
  "properties": { "query_key": { "type": "string", "minLength": 1 } },
  "additionalProperties": false
}


Get Response
{
  "type": "object",
  "required": ["query_key"],
  "properties": {
    "query_key": { "type": "string" },
    "last_edat": { "type": ["string","null"], "description": "ISO8601 UTC or null" }
  },
  "additionalProperties": false
}


Set Request

{
  "type": "object",
  "required": ["query_key", "last_edat"],
  "properties": {
    "query_key": { "type": "string" },
    "last_edat": { "type": "string", "description": "ISO8601 UTC" }
  },
  "additionalProperties": false
}


Set Response
{
  "type": "object",
  "required": ["ok"],
  "properties": { "ok": { "type": "boolean" } },
  "additionalProperties": false
}


Notes / Guarantees

Server enforces monotonic watermarks on automatic advancement; manual set may move backward for backfills (audited).

## Error Envelope (all tools/resources)

On failure, responses adopt this envelope:

{
  "type": "object",
  "required": ["error"],
  "properties": {
    "error": {
      "type": "object",
      "required": ["code", "message"],
      "properties": {
        "code": {
          "type": "string",
          "enum": [
            "RATE_LIMIT","UPSTREAM","VALIDATION","NOT_FOUND",
            "INVARIANT_FAILURE","STORE","EMBEDDINGS","WEAVIATE","ENTREZ","UNKNOWN"
          ]
        },
        "message": { "type": "string" },
        "details": { "type": ["object","array","string","null"] }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}

# MCP Resources
## resource://pubmed/paper/{pmid}

Path params: {pmid} (digits)

Payload schema: identical to rag.get response (document metadata).
Guarantees: read-only; consistent with metadata store.

# Internal Adapter Contracts (Non-public but stable)
## Weaviate Adapter

Class name: configurable (WEAVIATE_CLASS, default PubMedChunk)

Required props on upsert:

pmid:string, chunk_id:string, text:string, vector:number[]

Optional props:

journal?:string, pub_types?:string[], year?:number,

quality_total?:number, edat?:string(ISO8601), lr?:string(ISO8601), source_url?:string

Functions:

ensure_schema() -> None

upsert_chunks(chunks: Iterable[dict]) -> BatchResult

hybrid_search(query:str, limit:int) -> List[{uuid, pmid, sim?, bm25?, quality?}]

Invariants:

Stable UUID: uuid5(ns, f"{pmid}:{chunk_id}")

len(vector) == Embeddings.dim; normalized vectors.

## Embeddings Adapter
{
  "interface": "Embeddings",
  "methods": {
    "dim": { "type": "integer", "description": "embedding dimensionality" },
    "embed": {
      "args": ["texts: Iterable<string>"],
      "returns": "List<List<number>>"
    }
  },
  "providers": ["openai", "hf"]
}


Guarantees: one vector per input; batched; errors surfaced as typed exceptions; vectors normalized.

## Entrez (PubMed) Client

esearch_delta(term, mindate, maxdate, datetype="edat") -> List[str(pmids)]

esummary_batch(pmids) -> List[DocSummary]

DocSummary = { pmid, title?, journal?, pub_types[], pdat?, edat?, lr?, pmcid?, authors?, abstract? }

Rate limits: ≤ ~3 rps with API key; exponential backoff on 429/5xx.

## Metadata Store (SQL)

upsert_pubmed_docs(docs) -> {inserted, updated, skipped, max_edat_seen?}

get_pubmed_doc(pmid) -> Doc

get_checkpoint(query_key) -> {last_edat?}

set_checkpoint(query_key, last_edat) -> None

Invariants: pmid unique; version increments on content_hash change or lr advance.

# Versioning Policy

MCP tool/request/response changes:

Additive fields → minor version.

Field removal/rename/semantics change → major version.

Weaviate/DB schema: additive only without bump; breaking changes require migration + major bump.

# Examples
pubmed.sync_delta → request
{ "query_key": "glp1_obesity_v1", "term": "(GLP-1 receptor agonist) AND obesity", "overlap_days": 5 }

pubmed.sync_delta → response
{
  "job_id": "sync_2025-08-17T16:02:10Z",
  "inserted": 37,
  "updated": 12,
  "skipped": 441,
  "pmids_processed": 490,
  "max_edat_seen": "2025-08-17T15:59:02Z",
  "warnings": []
}

rag.search → request
{ "query": "phase 2 weight loss vs placebo", "top_k": 10, "quality_bias": true }

rag.search → response
{
  "results": [
    { "doc_id": "pmid:384001", "uuid": "7d5c...", "sim": 0.72, "bm25": 14.2, "quality": 9, "score": 1.37 },
    { "doc_id": "pmid:383912", "uuid": "a1b2...", "sim": 0.69, "bm25": 13.1, "quality": 8, "score": 1.25 }
  ]
}

rag.get → request
{ "doc_id": "pmid:384001" }

rag.get → response
{
  "doc_id": "pmid:384001",
  "title": "Once-weekly XYZ shows weight reduction vs placebo...",
  "abstract": "Background: ... Methods: ... Results: ...",
  "journal": "The New England Journal of Medicine",
  "pub_types": ["Randomized Controlled Trial"],
  "pdat": "2024-05-11",
  "edat": "2024-06-02T00:00:00Z",
  "lr": "2024-06-15T00:00:00Z",
  "pmcid": "PMC1234567",
  "quality": { "design": 2, "recency": 2, "journal": 2, "human": 2, "total": 8 },
  "version": 2
}

# Validation & Testing

Contract tests: validate all tool inputs/outputs against the JSON Schemas above.

Golden tests: a tiny set of PMIDs with fixed metadata to assert scoring, versioning, and Weaviate UUID stability.

Smoke tests: start local Weaviate via Compose, run pubmed.sync_delta on a narrow term, then rag.search and rag.get.