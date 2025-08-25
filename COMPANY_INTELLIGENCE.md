Awesome—here’s a tight, build-ready **Company Intelligence domain model** you can drop into your repo. It’s aligned with your existing `Document`/`Trial` models and optimized for joins, checkpoints, and MCP tools.

---

# 1) ER-style diagram (ASCII)

```
                        ┌────────────────────┐
                        │      Company       │
                        │ company_id (pk)    │
                        │ name               │
                        │ country_code       │
                        │ cik (nullable)     │
                        └─────────┬──────────┘
     ┌────────────────────────────┼─────────────────────────────┐
     │                            │                             │
┌────▼─────┐                ┌─────▼─────┐                 ┌─────▼─────┐
│ Ticker   │                │ Alias     │                 │ Subsidiary │
│ ticker   │                │ alias     │                 │ child_id   │
│ exchange │                │ kind enum │                 │ relation   │
└──────────┘                └───────────┘                 └────────────┘

                        ┌────────────────────┐
                        │       Drug         │
                        │ drug_id (pk)       │
                        │ name               │
                        │ modality enum      │
                        │ target (nullable)  │
                        └─────────┬──────────┘
                                  │  many-to-many via role
                            ┌─────▼──────────────────────┐
                            │ CompanyDrug                │
                            │ company_id (fk)            │
                            │ drug_id (fk)               │
                            │ role enum                  │
                            │ since, until (nullable)    │
                            └────────────────────────────┘

                        ┌────────────────────┐
                        │       Trial        │
                        │ nct_id (pk)        │
                        │ phase enum         │
                        │ status enum        │
                        │ condition[]        │
                        │ primary_completion │
                        └─────────┬──────────┘
                                  │ many-to-many w/ roles
                            ┌─────▼──────────────────────┐
                            │ CompanyTrial               │
                            │ company_id (fk)            │
                            │ nct_id (fk)                │
                            │ role enum (sponsor,collab) │
                            └────────────────────────────┘
                                  │
                                  │  one-to-many
                            ┌─────▼──────────────────────┐
                            │ TrialPublication           │
                            │ nct_id (fk)                │
                            │ pmid (fk)                  │
                            │ link_type enum (SI,kw)     │
                            └────────────────────────────┘

                        ┌────────────────────┐
                        │   Publication      │
                        │ pmid (pk)          │
                        │ journal_tier enum  │
                        │ published_at       │
                        │ mesh_major[]       │
                        └─────────┬──────────┘
                                  │ many-to-many
                            ┌─────▼──────────────────────┐
                            │ CompanyPublication         │
                            │ company_id (fk)            │
                            │ pmid (fk)                  │
                            │ evidence enum (AD,CN,kw)   │
                            │ confidence 0..100          │
                            └────────────────────────────┘

                        ┌────────────────────┐
                        │      Event         │
                        │ event_id (pk)      │
                        │ type enum          │
                        │ occurs_on          │
                        │ provenance         │
                        └─────────┬──────────┘
                                  │ many-to-many
                            ┌─────▼──────────────────────┐
                            │ CompanyEvent               │
                            │ company_id (fk)            │
                            │ event_id (fk)              │
                            │ confidence 0..100          │
                            └────────────────────────────┘
```

---

# 2) Core entities (Pydantic models)

```python
from pydantic import BaseModel, Field, constr, conint
from typing import List, Optional, Literal
from datetime import date

CompanyRole = Literal["owner","developer","licensee","partner"]
TrialRole   = Literal["sponsor","collaborator","principal_investigator"]
Evidence    = Literal["AD","CN","SI","keyword"]  # Affiliation, CorpAuthor, SecondaryId, Keyword
JournalTier = Literal["top","high","mid","longtail","unknown"]
Modality    = Literal["small_molecule","biologic","gene_therapy","cell_therapy","oligo","vaccine","diagnostic","other"]
Phase       = Literal["0","1","1/2","2","2/3","3","4","na"]
TrialStatus = Literal["not_yet_recruiting","recruiting","active","completed","terminated","suspended","withdrawn","unknown"]

class Company(BaseModel):
    company_id: str
    name: str
    country_code: Optional[constr(min_length=2, max_length=2)] = None
    cik: Optional[str] = None

class Ticker(BaseModel):
    company_id: str
    ticker: str
    exchange: Optional[str] = None
    isin: Optional[str] = None

class Alias(BaseModel):
    company_id: str
    alias: str
    kind: Literal["legal","brand","former","abbrev"]

class Drug(BaseModel):
    drug_id: str
    name: str
    modality: Optional[Modality] = None
    target: Optional[str] = None
    synonyms: List[str] = []

class CompanyDrug(BaseModel):
    company_id: str
    drug_id: str
    role: CompanyRole
    since: Optional[date] = None
    until: Optional[date] = None

class Trial(BaseModel):
    nct_id: str
    phase: Phase
    status: TrialStatus
    conditions: List[str] = []
    primary_completion: Optional[date] = None

class CompanyTrial(BaseModel):
    company_id: str
    nct_id: str
    role: TrialRole

class Publication(BaseModel):
    pmid: str
    journal_tier: JournalTier = "unknown"
    published_at: Optional[date] = None
    mesh_major: List[str] = []

class CompanyPublication(BaseModel):
    company_id: str
    pmid: str
    evidence: Evidence
    confidence: conint(ge=0, le=100)

class TrialPublication(BaseModel):
    nct_id: str
    pmid: str
    link_type: Literal["SI","keyword","registry_match"]
```

> All `*_id` values should be **deterministic slugs** (UUIDv5 or normalized strings) for reproducibility.

---

# 3) PostgreSQL tables (DDL sketch)

```sql
-- Companies
CREATE TABLE company (
  company_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  country_code CHAR(2),
  cik TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE company_ticker (
  company_id TEXT REFERENCES company(company_id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  exchange TEXT,
  isin TEXT,
  PRIMARY KEY (company_id, ticker)
);

CREATE TABLE company_alias (
  company_id TEXT REFERENCES company(company_id) ON DELETE CASCADE,
  alias TEXT NOT NULL,
  kind TEXT CHECK (kind IN ('legal','brand','former','abbrev')),
  PRIMARY KEY (company_id, alias)
);

-- Drugs
CREATE TABLE drug (
  drug_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  modality TEXT,
  target TEXT
);

CREATE TABLE company_drug (
  company_id TEXT REFERENCES company(company_id) ON DELETE CASCADE,
  drug_id TEXT REFERENCES drug(drug_id) ON DELETE CASCADE,
  role TEXT CHECK (role IN ('owner','developer','licensee','partner')),
  since DATE,
  until DATE,
  PRIMARY KEY (company_id, drug_id, role)
);

-- Trials
CREATE TABLE trial (
  nct_id TEXT PRIMARY KEY,
  phase TEXT,
  status TEXT,
  primary_completion DATE
);

CREATE TABLE company_trial (
  company_id TEXT REFERENCES company(company_id) ON DELETE CASCADE,
  nct_id TEXT REFERENCES trial(nct_id) ON DELETE CASCADE,
  role TEXT CHECK (role IN ('sponsor','collaborator','principal_investigator')),
  PRIMARY KEY (company_id, nct_id, role)
);

-- Publications (you already have documents/pmid; mirror or FK to your doc table)
CREATE TABLE publication (
  pmid TEXT PRIMARY KEY,
  journal_tier TEXT,
  published_at DATE
);

CREATE TABLE company_publication (
  company_id TEXT REFERENCES company(company_id) ON DELETE CASCADE,
  pmid TEXT REFERENCES publication(pmid) ON DELETE CASCADE,
  evidence TEXT CHECK (evidence IN ('AD','CN','SI','keyword')),
  confidence SMALLINT CHECK (confidence BETWEEN 0 AND 100),
  PRIMARY KEY (company_id, pmid, evidence)
);

CREATE TABLE trial_publication (
  nct_id TEXT REFERENCES trial(nct_id) ON DELETE CASCADE,
  pmid TEXT REFERENCES publication(pmid) ON DELETE CASCADE,
  link_type TEXT CHECK (link_type IN ('SI','keyword','registry_match')),
  PRIMARY KEY (nct_id, pmid, link_type)
);

-- Events (catalysts)
CREATE TABLE company_event (
  event_id TEXT PRIMARY KEY,
  type TEXT CHECK (type IN ('trial_readout','pdufa','adcom','financing','partnership','guidance')),
  occurs_on DATE,
  provenance JSONB,  -- pointers to ctgov/pubmed/sec
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE company_event_link (
  company_id TEXT REFERENCES company(company_id) ON DELETE CASCADE,
  event_id TEXT REFERENCES company_event(event_id) ON DELETE CASCADE,
  confidence SMALLINT CHECK (confidence BETWEEN 0 AND 100),
  PRIMARY KEY (company_id, event_id)
);

-- Helpful indexes
CREATE INDEX ON company_alias USING gin (to_tsvector('simple', alias));
CREATE INDEX ON company_ticker(ticker);
CREATE INDEX ON company_drug(drug_id);
CREATE INDEX ON company_trial(nct_id);
CREATE INDEX ON company_publication(pmid);
```

---

# 4) How MCP tools use it (read paths)

* `company.resolve`

  * **Reads**: `company_ticker`, `company_alias`, `company` (fuzzy on alias, exact on ticker).
* `company.pipeline.list({company_id})`

  * **Reads**: `company_drug` → `drug`; `company_trial` → `trial`; join to produce a unified pipeline view.
* `company.publications.search({company_id, window})`

  * **Reads**: `company_publication` → `publication`; optional hydrate to your `Document` table.
* `company.events.upcoming({company_id, horizon_days})`

  * **Reads**: `company_event_link` → `company_event`; also cross-check `trial.primary_completion`.
* `signals.*` (e.g., `competition_density`, `readout_risk`)

  * **Reads**: joins across `trial`, `company_trial`, `publication`, `trial_publication`.

---

# 5) Ingestion notes (linking logic)

* **Company ↔ Trial**: primary from CT.gov `sponsor/collaborator` → `company_trial.role`.
* **Company ↔ Publication**: derive from PubMed:

  * `[AD]` affiliation hit → `evidence='AD'` with string match + org lexicon → `confidence` based on exact/fuzzy rules.
  * `[CN]` corporate author → `evidence='CN'`.
  * `Secondary Source ID` contains NCT → link via trial → `evidence='SI'` (often high confidence).
* **Company ↔ Drug**: seed from curated mapping or SEC/press; keep as **role’d** edges (owner, developer, licensee).
* **Events**: materialize from rules:

  * upcoming `trial.primary_completion` within horizon → `type='trial_readout'`.
  * FDA calendar (if ingested) → `type='pdufa'` / `adcom`.

---

# 6) Why this shape works

* **Relational, role-based edges** model ambiguity without data duplication.
* **Confidence + evidence** fields make noisy affiliation linking usable.
* Clean joins to your existing **`Document`/`Trial`** models; reproducible IDs; easy to checkpoint.

---