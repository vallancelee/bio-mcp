# BioInvest AI Copilot - Data Architecture

## Overview

The BioInvest AI Copilot data architecture is designed to handle massive volumes of heterogeneous biomedical, financial, and research data while providing real-time insights and maintaining data quality, security, and governance standards. The architecture supports both batch and streaming data processing with comprehensive lineage tracking and automated quality assurance.

## Data Architecture Principles

### Core Principles
- **Data as a Product**: Each dataset treated as a product with clear ownership and SLAs
- **Schema Evolution**: Forward and backward compatible schema changes
- **Data Lineage**: Complete traceability from source to consumption
- **Quality First**: Automated data quality checks and validation
- **Privacy by Design**: GDPR and compliance requirements embedded from the start
- **Real-time by Default**: Stream-first architecture with batch as supplement

### Quality Attributes
- **Accuracy**: >99.5% data quality across all sources
- **Latency**: <30 seconds for real-time data ingestion
- **Availability**: 99.9% uptime for data services
- **Scalability**: Handle 10TB+ daily data ingestion
- **Security**: End-to-end encryption and access controls

## Data Flow Architecture

### End-to-End Data Pipeline

```mermaid
graph TB
    subgraph "Data Sources"
        EXT_API[External APIs]
        WEB_SCRAPING[Web Scraping]
        FILE_FEEDS[File Feeds]
        USER_INPUT[User Input]
        THIRD_PARTY[Third Party Data]
    end
    
    subgraph "Ingestion Layer"
        API_GATEWAY[API Gateway]
        STREAM_PROC[Stream Processors]
        BATCH_INGEST[Batch Ingestion]
        CHANGE_CAPTURE[Change Data Capture]
    end
    
    subgraph "Raw Data Store"
        DATA_LAKE[Data Lake (S3)]
        LANDING[Landing Zone]
        QUARANTINE[Quarantine Zone]
    end
    
    subgraph "Processing Layer"
        ETL_PIPELINE[ETL Pipelines]
        ML_PIPELINE[ML Pipelines]
        VALIDATION[Data Validation]
        ENRICHMENT[Data Enrichment]
    end
    
    subgraph "Curated Data Store"
        WAREHOUSE[Data Warehouse]
        GRAPH_DB[Knowledge Graph]
        VECTOR_DB[Vector Database]
        FEATURE_STORE[Feature Store]
    end
    
    subgraph "Serving Layer"
        CACHE[Cache Layer]
        SEARCH_INDEX[Search Index]
        APIs[Data APIs]
        ANALYTICS[Analytics Engine]
    end
    
    subgraph "Consumption"
        DASHBOARD[Dashboards]
        ML_MODELS[ML Models]
        REPORTS[Reports]
        ALERTS[Real-time Alerts]
    end
    
    EXT_API --> API_GATEWAY
    WEB_SCRAPING --> STREAM_PROC
    FILE_FEEDS --> BATCH_INGEST
    USER_INPUT --> CHANGE_CAPTURE
    THIRD_PARTY --> API_GATEWAY
    
    API_GATEWAY --> LANDING
    STREAM_PROC --> LANDING
    BATCH_INGEST --> LANDING
    CHANGE_CAPTURE --> LANDING
    
    LANDING --> ETL_PIPELINE
    LANDING --> VALIDATION
    QUARANTINE --> VALIDATION
    
    VALIDATION --> ETL_PIPELINE
    ETL_PIPELINE --> ENRICHMENT
    ENRICHMENT --> ML_PIPELINE
    
    ML_PIPELINE --> WAREHOUSE
    ML_PIPELINE --> GRAPH_DB
    ML_PIPELINE --> VECTOR_DB
    ML_PIPELINE --> FEATURE_STORE
    
    WAREHOUSE --> CACHE
    GRAPH_DB --> SEARCH_INDEX
    VECTOR_DB --> APIs
    FEATURE_STORE --> ANALYTICS
    
    CACHE --> DASHBOARD
    SEARCH_INDEX --> ML_MODELS
    APIs --> REPORTS
    ANALYTICS --> ALERTS
```

## Data Ingestion Architecture

### Real-time Data Ingestion

#### Apache Kafka Streaming Platform
```yaml
# Kafka cluster configuration
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: bioinvest-kafka
spec:
  kafka:
    version: 3.6.0
    replicas: 3
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
      - name: tls
        port: 9093
        type: internal
        tls: true
    config:
      auto.create.topics.enable: false
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      transaction.state.log.min.isr: 2
      default.replication.factor: 3
      min.insync.replicas: 2
    storage:
      type: persistent-claim
      size: 1000Gi
      class: fast-ssd
```

#### Stream Processing with Apache Flink
```python
# Real-time biomedical data processing
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment

def process_pubmed_stream():
    env = StreamExecutionEnvironment.get_execution_environment()
    table_env = StreamTableEnvironment.create(env)
    
    # Define Kafka source
    table_env.execute_sql("""
        CREATE TABLE pubmed_source (
            pmid STRING,
            title STRING,
            abstract STRING,
            authors ARRAY<STRING>,
            publication_date TIMESTAMP(3),
            journal STRING,
            keywords ARRAY<STRING>,
            mesh_terms ARRAY<STRING>,
            processing_time AS PROCTIME()
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'pubmed-updates',
            'properties.bootstrap.servers' = 'kafka-cluster:9092',
            'format' = 'json',
            'scan.startup.mode' = 'latest-offset'
        )
    """)
    
    # Entity extraction and enrichment
    table_env.execute_sql("""
        CREATE TABLE enriched_publications AS
        SELECT 
            pmid,
            title,
            abstract,
            authors,
            publication_date,
            journal,
            extract_entities(abstract) as entities,
            calculate_relevance_score(abstract, keywords) as relevance_score,
            processing_time
        FROM pubmed_source
        WHERE LENGTH(abstract) > 100
        AND publication_date > CURRENT_TIMESTAMP - INTERVAL '30' DAY
    """)
```

#### Bio-MCP Integration Layer
```python
# Bio-MCP orchestrator integration
from bio_mcp import MCPClient
from typing import Dict, Any, List
import asyncio
import json

class BiomedicData:
    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client
        self.data_pipelines = {
            'pubmed': self.pubmed_pipeline,
            'clinical_trials': self.trials_pipeline,
            'patents': self.patents_pipeline,
            'regulatory': self.regulatory_pipeline
        }
    
    async def pubmed_pipeline(self, query: Dict[str, Any]) -> List[Dict]:
        """Process PubMed search requests and enrich data"""
        results = await self.mcp_client.call_tool(
            name="pubmed.search",
            arguments={
                "query": query.get("search_terms"),
                "max_results": query.get("max_results", 100),
                "date_range": query.get("date_range"),
                "filters": query.get("filters", {})
            }
        )
        
        # Enrich with NLP processing
        enriched_results = []
        for article in results.get("results", []):
            enriched = await self.enrich_article(article)
            enriched_results.append(enriched)
            
        return enriched_results
    
    async def enrich_article(self, article: Dict) -> Dict:
        """Enrich article with extracted entities and metadata"""
        # Extract biomedical entities
        entities = await self.extract_entities(article.get("abstract", ""))
        
        # Calculate quality scores
        quality_scores = self.calculate_quality_metrics(article)
        
        # Identify investment relevance
        investment_signals = await self.identify_investment_signals(article)
        
        return {
            **article,
            "entities": entities,
            "quality_scores": quality_scores,
            "investment_signals": investment_signals,
            "processing_timestamp": datetime.utcnow().isoformat()
        }
```

### Batch Data Processing

#### ETL Pipeline with Apache Airflow
```python
# Airflow DAG for daily biomedical data processing
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'bioinvest-data-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'daily_biomedical_etl',
    default_args=default_args,
    description='Daily biomedical data ETL pipeline',
    schedule_interval='@daily',
    catchup=False,
    max_active_runs=1
)

def extract_fda_data(**context):
    """Extract FDA regulatory data"""
    from src.extractors.fda_extractor import FDAExtractor
    
    extractor = FDAExtractor()
    execution_date = context['execution_date']
    
    # Extract previous day's FDA actions
    data = extractor.extract_daily_actions(execution_date)
    
    # Store in staging area
    staging_path = f"s3://bioinvest-data-lake/staging/fda/{execution_date.strftime('%Y-%m-%d')}"
    extractor.save_to_staging(data, staging_path)
    
    return staging_path

def transform_and_load_fda(**context):
    """Transform FDA data and load to warehouse"""
    from src.transformers.fda_transformer import FDATransformer
    from src.loaders.warehouse_loader import WarehouseLoader
    
    staging_path = context['task_instance'].xcom_pull(task_ids='extract_fda_data')
    
    # Transform data
    transformer = FDATransformer()
    transformed_data = transformer.transform_fda_actions(staging_path)
    
    # Data quality validation
    quality_report = transformer.validate_data_quality(transformed_data)
    if not quality_report.is_valid:
        raise ValueError(f"Data quality validation failed: {quality_report.errors}")
    
    # Load to warehouse
    loader = WarehouseLoader()
    loader.load_fda_data(transformed_data)

# Task definitions
extract_fda_task = PythonOperator(
    task_id='extract_fda_data',
    python_callable=extract_fda_data,
    dag=dag
)

transform_load_fda_task = PythonOperator(
    task_id='transform_load_fda',
    python_callable=transform_and_load_fda,
    dag=dag
)

# Task dependencies
extract_fda_task >> transform_load_fda_task
```

## Data Storage Architecture

### Data Lake Architecture (Amazon S3)

#### Storage Organization
```
bioinvest-data-lake/
├── raw/                          # Raw ingested data
│   ├── pubmed/
│   │   └── year=2024/month=01/day=15/
│   ├── clinical-trials/
│   ├── patents/
│   └── financial/
├── processed/                    # Cleaned and transformed data
│   ├── publications/
│   ├── companies/
│   └── market-data/
├── curated/                     # Analysis-ready datasets
│   ├── investment-signals/
│   ├── risk-factors/
│   └── market-intelligence/
├── features/                    # ML feature sets
│   ├── company-features/
│   └── drug-features/
└── models/                      # Trained ML models and artifacts
    ├── prediction-models/
    └── embeddings/
```

#### Data Partitioning Strategy
```python
# Partitioning configuration for optimal query performance
PARTITION_STRATEGIES = {
    'publications': {
        'partition_keys': ['year', 'month', 'journal_category'],
        'sort_keys': ['publication_date', 'citation_count'],
        'compression': 'GZIP',
        'format': 'PARQUET'
    },
    'clinical_trials': {
        'partition_keys': ['year', 'phase', 'status'],
        'sort_keys': ['start_date', 'enrollment_count'],
        'compression': 'SNAPPY',
        'format': 'PARQUET'
    },
    'company_financials': {
        'partition_keys': ['year', 'quarter'],
        'sort_keys': ['report_date', 'market_cap'],
        'compression': 'GZIP',
        'format': 'PARQUET'
    }
}
```

### Data Warehouse (PostgreSQL + Time-series)

#### Core Schema Design
```sql
-- Companies and corporate structure
CREATE SCHEMA companies;

CREATE TABLE companies.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    ticker VARCHAR(10) UNIQUE,
    exchange VARCHAR(50),
    sector VARCHAR(100),
    market_cap BIGINT,
    headquarters JSONB,
    founded_date DATE,
    website VARCHAR(255),
    description TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_companies_ticker ON companies.organizations(ticker);
CREATE INDEX idx_companies_sector ON companies.organizations(sector);
CREATE INDEX idx_companies_market_cap ON companies.organizations(market_cap DESC);

-- Drug pipeline and development
CREATE SCHEMA pipeline;

CREATE TABLE pipeline.drugs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    generic_name VARCHAR(255),
    company_id UUID REFERENCES companies.organizations(id),
    therapeutic_area VARCHAR(100),
    mechanism_of_action TEXT,
    target_indication VARCHAR(255),
    current_phase VARCHAR(20),
    regulatory_status VARCHAR(50),
    first_in_human_date DATE,
    patent_expiry DATE,
    competitive_landscape JSONB,
    clinical_data JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_drugs_company ON pipeline.drugs(company_id);
CREATE INDEX idx_drugs_phase ON pipeline.drugs(current_phase);
CREATE INDEX idx_drugs_indication ON pipeline.drugs(target_indication);

-- Clinical trials
CREATE TABLE pipeline.clinical_trials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nct_id VARCHAR(20) UNIQUE NOT NULL,
    drug_id UUID REFERENCES pipeline.drugs(id),
    title VARCHAR(500),
    phase VARCHAR(20),
    status VARCHAR(50),
    primary_endpoint TEXT,
    secondary_endpoints TEXT[],
    enrollment_target INTEGER,
    enrollment_actual INTEGER,
    start_date DATE,
    completion_date DATE,
    sponsor VARCHAR(255),
    locations JSONB,
    inclusion_criteria TEXT,
    exclusion_criteria TEXT,
    results JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trials_nct ON pipeline.clinical_trials(nct_id);
CREATE INDEX idx_trials_drug ON pipeline.clinical_trials(drug_id);
CREATE INDEX idx_trials_phase ON pipeline.clinical_trials(phase);
CREATE INDEX idx_trials_status ON pipeline.clinical_trials(status);
```

#### Time-series Data (TimescaleDB)
```sql
-- Market data time-series
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE market.stock_prices (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    open DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    close DECIMAL(10,2),
    volume BIGINT,
    adjusted_close DECIMAL(10,2),
    dividend_amount DECIMAL(6,4),
    split_coefficient DECIMAL(6,4)
);

SELECT create_hypertable('market.stock_prices', 'time', 'symbol', 4);

-- Research metrics time-series
CREATE TABLE analytics.research_metrics (
    time TIMESTAMPTZ NOT NULL,
    company_id UUID NOT NULL,
    publication_count INTEGER,
    citation_impact DECIMAL(8,4),
    patent_activity INTEGER,
    clinical_trial_activity INTEGER,
    regulatory_events INTEGER,
    sentiment_score DECIMAL(4,3),
    investment_score DECIMAL(4,3),
    risk_score DECIMAL(4,3)
);

SELECT create_hypertable('analytics.research_metrics', 'time', 'company_id', 4);
```

### Knowledge Graph (Neo4j)

#### Graph Schema Definition
```cypher
// Core entity node labels
CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT drug_id IF NOT EXISTS FOR (d:Drug) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT disease_id IF NOT EXISTS FOR (dis:Disease) REQUIRE dis.id IS UNIQUE;
CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT publication_id IF NOT EXISTS FOR (pub:Publication) REQUIRE pub.pmid IS UNIQUE;

// Relationship types and constraints
CREATE CONSTRAINT develops_unique IF NOT EXISTS FOR ()-[r:DEVELOPS]-() REQUIRE (r.company_id, r.drug_id) IS UNIQUE;
CREATE CONSTRAINT targets_unique IF NOT EXISTS FOR ()-[r:TARGETS]-() REQUIRE (r.drug_id, r.disease_id) IS UNIQUE;

// Example graph population
MERGE (c:Company {
    id: 'company_123',
    name: 'Genentech',
    ticker: 'RHHBY',
    sector: 'Biotechnology'
})
MERGE (d:Drug {
    id: 'drug_456',
    name: 'Avastin',
    generic_name: 'bevacizumab',
    mechanism: 'VEGF inhibitor'
})
MERGE (dis:Disease {
    id: 'disease_789',
    name: 'Colorectal Cancer',
    category: 'Oncology'
})

MERGE (c)-[:DEVELOPS {
    development_stage: 'Approved',
    first_approval_date: date('2004-02-26'),
    regulatory_pathway: 'BLA'
}]->(d)

MERGE (d)-[:TARGETS {
    indication: 'Metastatic colorectal cancer',
    efficacy_data: {
        primary_endpoint: 'Overall survival',
        hazard_ratio: 0.66,
        p_value: 0.001
    }
}]->(dis)
```

### Vector Database (Weaviate)

#### Schema Configuration
```python
# Weaviate schema for biomedical embeddings
import weaviate

client = weaviate.Client("http://localhost:8080")

# Publication embeddings
publication_schema = {
    "class": "Publication",
    "description": "Biomedical research publications with semantic embeddings",
    "vectorizer": "text2vec-transformers",
    "moduleConfig": {
        "text2vec-transformers": {
            "poolingStrategy": "masked_mean",
            "model": "sentence-transformers/allenai-specter"
        }
    },
    "properties": [
        {
            "name": "pmid",
            "dataType": ["string"],
            "description": "PubMed ID"
        },
        {
            "name": "title",
            "dataType": ["text"],
            "description": "Article title"
        },
        {
            "name": "abstract",
            "dataType": ["text"],
            "description": "Article abstract"
        },
        {
            "name": "authors",
            "dataType": ["string[]"],
            "description": "Author names"
        },
        {
            "name": "journal",
            "dataType": ["string"],
            "description": "Journal name"
        },
        {
            "name": "publication_date",
            "dataType": ["date"],
            "description": "Publication date"
        },
        {
            "name": "mesh_terms",
            "dataType": ["string[]"],
            "description": "MeSH terms"
        },
        {
            "name": "entities",
            "dataType": ["object"],
            "description": "Extracted biomedical entities"
        },
        {
            "name": "investment_relevance_score",
            "dataType": ["number"],
            "description": "Investment relevance score (0-1)"
        }
    ]
}

client.schema.create_class(publication_schema)

# Company profile embeddings
company_schema = {
    "class": "CompanyProfile",
    "description": "Company profiles with business and scientific embeddings",
    "vectorizer": "text2vec-transformers",
    "moduleConfig": {
        "text2vec-transformers": {
            "poolingStrategy": "masked_mean"
        }
    },
    "properties": [
        {
            "name": "company_id",
            "dataType": ["string"],
            "description": "Company identifier"
        },
        {
            "name": "name",
            "dataType": ["string"],
            "description": "Company name"
        },
        {
            "name": "business_description",
            "dataType": ["text"],
            "description": "Business description and strategy"
        },
        {
            "name": "pipeline_summary",
            "dataType": ["text"],
            "description": "Drug pipeline summary"
        },
        {
            "name": "therapeutic_areas",
            "dataType": ["string[]"],
            "description": "Therapeutic focus areas"
        },
        {
            "name": "competitive_position",
            "dataType": ["text"],
            "description": "Competitive positioning analysis"
        }
    ]
}

client.schema.create_class(company_schema)
```

## Data Quality & Governance

### Data Quality Framework

#### Automated Data Quality Checks
```python
# Data quality validation framework
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum

class QualityCheckType(Enum):
    COMPLETENESS = "completeness"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"
    CONSISTENCY = "consistency"
    ACCURACY = "accuracy"
    TIMELINESS = "timeliness"

@dataclass
class QualityCheck:
    name: str
    check_type: QualityCheckType
    description: str
    threshold: float
    is_critical: bool

@dataclass
class QualityResult:
    check: QualityCheck
    passed: bool
    score: float
    details: Dict[str, Any]

class DataQualityValidator:
    def __init__(self):
        self.checks = self._define_quality_checks()
    
    def _define_quality_checks(self) -> List[QualityCheck]:
        return [
            # Completeness checks
            QualityCheck(
                name="publication_abstract_completeness",
                check_type=QualityCheckType.COMPLETENESS,
                description="Publications must have non-empty abstracts",
                threshold=0.95,
                is_critical=True
            ),
            QualityCheck(
                name="company_ticker_completeness",
                check_type=QualityCheckType.COMPLETENESS,
                description="Public companies must have ticker symbols",
                threshold=0.98,
                is_critical=True
            ),
            
            # Uniqueness checks
            QualityCheck(
                name="pmid_uniqueness",
                check_type=QualityCheckType.UNIQUENESS,
                description="PMID values must be unique",
                threshold=1.0,
                is_critical=True
            ),
            
            # Validity checks
            QualityCheck(
                name="date_validity",
                check_type=QualityCheckType.VALIDITY,
                description="Dates must be valid and reasonable",
                threshold=0.99,
                is_critical=True
            ),
            
            # Timeliness checks
            QualityCheck(
                name="data_freshness",
                check_type=QualityCheckType.TIMELINESS,
                description="Data should be updated within SLA timeframes",
                threshold=0.95,
                is_critical=False
            )
        ]
    
    def validate_dataset(self, dataset: str, data: Any) -> List[QualityResult]:
        results = []
        
        for check in self.checks:
            if self._is_applicable(check, dataset):
                result = self._run_check(check, data)
                results.append(result)
        
        return results
    
    def _run_check(self, check: QualityCheck, data: Any) -> QualityResult:
        # Implementation specific to each check type
        if check.check_type == QualityCheckType.COMPLETENESS:
            score = self._check_completeness(check, data)
        elif check.check_type == QualityCheckType.UNIQUENESS:
            score = self._check_uniqueness(check, data)
        # ... other check implementations
        
        return QualityResult(
            check=check,
            passed=score >= check.threshold,
            score=score,
            details={}
        )
```

### Data Lineage Tracking

#### Lineage Metadata Model
```python
# Data lineage tracking system
from typing import Optional, List, Dict
from datetime import datetime
from dataclasses import dataclass

@dataclass
class DataAsset:
    id: str
    name: str
    type: str  # table, file, model, etc.
    schema: Optional[Dict]
    location: str
    owner: str
    created_at: datetime
    updated_at: datetime

@dataclass
class Transformation:
    id: str
    name: str
    description: str
    code_location: str
    version: str
    parameters: Dict[str, Any]
    execution_time: datetime
    duration_seconds: int

@dataclass
class LineageEdge:
    source_asset: DataAsset
    target_asset: DataAsset
    transformation: Transformation
    dependency_type: str  # direct, indirect

class LineageTracker:
    def __init__(self):
        self.assets: Dict[str, DataAsset] = {}
        self.transformations: Dict[str, Transformation] = {}
        self.lineage_graph: List[LineageEdge] = []
    
    def register_transformation(self, 
                               source_assets: List[str],
                               target_assets: List[str],
                               transformation: Transformation):
        """Register a data transformation and its lineage"""
        self.transformations[transformation.id] = transformation
        
        for source_id in source_assets:
            for target_id in target_assets:
                if source_id in self.assets and target_id in self.assets:
                    edge = LineageEdge(
                        source_asset=self.assets[source_id],
                        target_asset=self.assets[target_id],
                        transformation=transformation,
                        dependency_type="direct"
                    )
                    self.lineage_graph.append(edge)
    
    def get_upstream_lineage(self, asset_id: str, depth: int = None) -> List[DataAsset]:
        """Get all upstream dependencies for a data asset"""
        upstream = []
        current_level = [asset_id]
        current_depth = 0
        
        while current_level and (depth is None or current_depth < depth):
            next_level = []
            for asset in current_level:
                parents = self._get_direct_upstream(asset)
                upstream.extend(parents)
                next_level.extend([p.id for p in parents])
            
            current_level = next_level
            current_depth += 1
        
        return upstream
    
    def get_impact_analysis(self, asset_id: str) -> List[DataAsset]:
        """Get all downstream assets affected by changes to this asset"""
        downstream = []
        current_level = [asset_id]
        
        while current_level:
            next_level = []
            for asset in current_level:
                children = self._get_direct_downstream(asset)
                downstream.extend(children)
                next_level.extend([c.id for c in children])
            
            current_level = next_level
        
        return downstream
```

## Data Security Architecture

### Access Control Framework
```python
# Role-based data access control
from enum import Enum
from typing import Set, Dict, Any

class DataClassification(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

class Permission(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"

class DataSecurityPolicy:
    def __init__(self):
        self.role_permissions = {
            'analyst': {
                DataClassification.PUBLIC: {Permission.READ},
                DataClassification.INTERNAL: {Permission.READ},
                DataClassification.CONFIDENTIAL: {Permission.READ}
            },
            'senior_analyst': {
                DataClassification.PUBLIC: {Permission.READ, Permission.WRITE},
                DataClassification.INTERNAL: {Permission.READ, Permission.WRITE},
                DataClassification.CONFIDENTIAL: {Permission.READ, Permission.WRITE}
            },
            'portfolio_manager': {
                DataClassification.PUBLIC: {Permission.READ, Permission.WRITE},
                DataClassification.INTERNAL: {Permission.READ, Permission.WRITE},
                DataClassification.CONFIDENTIAL: {Permission.READ, Permission.WRITE, Permission.DELETE},
                DataClassification.RESTRICTED: {Permission.READ}
            },
            'data_admin': {
                DataClassification.PUBLIC: {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN},
                DataClassification.INTERNAL: {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN},
                DataClassification.CONFIDENTIAL: {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN},
                DataClassification.RESTRICTED: {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN}
            }
        }
    
    def check_access(self, user_role: str, data_classification: DataClassification, 
                     requested_permission: Permission) -> bool:
        """Check if user role has permission for data classification"""
        role_perms = self.role_permissions.get(user_role, {})
        data_perms = role_perms.get(data_classification, set())
        return requested_permission in data_perms
```

### Encryption and PII Protection
```python
# Data encryption and anonymization
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import hashlib
import base64
import re

class DataProtection:
    def __init__(self, encryption_key: bytes):
        self.fernet = Fernet(encryption_key)
        self.pii_patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            'ssn': re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b')
        }
    
    def encrypt_sensitive_field(self, value: str) -> str:
        """Encrypt sensitive data field"""
        encrypted_bytes = self.fernet.encrypt(value.encode())
        return base64.b64encode(encrypted_bytes).decode()
    
    def decrypt_sensitive_field(self, encrypted_value: str) -> str:
        """Decrypt sensitive data field"""
        encrypted_bytes = base64.b64decode(encrypted_value.encode())
        decrypted_bytes = self.fernet.decrypt(encrypted_bytes)
        return decrypted_bytes.decode()
    
    def anonymize_text(self, text: str) -> str:
        """Remove or mask PII from text"""
        anonymized = text
        
        for pii_type, pattern in self.pii_patterns.items():
            if pii_type == 'email':
                anonymized = pattern.sub('[EMAIL]', anonymized)
            elif pii_type == 'phone':
                anonymized = pattern.sub('[PHONE]', anonymized)
            elif pii_type == 'ssn':
                anonymized = pattern.sub('[SSN]', anonymized)
        
        return anonymized
    
    def hash_identifier(self, identifier: str) -> str:
        """Create consistent hash for identifiers"""
        return hashlib.sha256(identifier.encode()).hexdigest()
```

## Data Analytics & Feature Engineering

### Feature Store Architecture
```python
# ML Feature store implementation
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pandas as pd

class FeatureStore:
    def __init__(self):
        self.feature_definitions = {}
        self.feature_groups = {}
    
    def register_feature_group(self, 
                               name: str,
                               entity_key: str,
                               features: Dict[str, Any],
                               data_source: str,
                               update_frequency: str):
        """Register a new feature group"""
        self.feature_groups[name] = {
            'entity_key': entity_key,
            'features': features,
            'data_source': data_source,
            'update_frequency': update_frequency,
            'last_updated': None
        }
    
    def get_features(self, 
                     entity_ids: List[str],
                     feature_names: List[str],
                     point_in_time: Optional[datetime] = None) -> pd.DataFrame:
        """Retrieve features for entities at a specific point in time"""
        if point_in_time is None:
            point_in_time = datetime.utcnow()
        
        # Implementation would query appropriate storage backend
        # and return features as DataFrame
        pass

# Company feature definitions
company_features = {
    'market_cap': {
        'type': 'numerical',
        'description': 'Market capitalization in USD',
        'source': 'financial_data',
        'update_frequency': 'daily'
    },
    'pipeline_count': {
        'type': 'numerical',
        'description': 'Number of drugs in pipeline',
        'source': 'clinical_trials',
        'update_frequency': 'weekly'
    },
    'publication_velocity': {
        'type': 'numerical',
        'description': 'Recent publication count (30 days)',
        'source': 'pubmed_data',
        'update_frequency': 'daily'
    },
    'regulatory_risk_score': {
        'type': 'numerical',
        'description': 'Regulatory risk assessment (0-1)',
        'source': 'ml_models',
        'update_frequency': 'weekly'
    }
}

# Drug feature definitions
drug_features = {
    'development_stage': {
        'type': 'categorical',
        'description': 'Current development phase',
        'source': 'clinical_trials',
        'update_frequency': 'weekly'
    },
    'indication_prevalence': {
        'type': 'numerical',
        'description': 'Target indication patient population',
        'source': 'epidemiology_data',
        'update_frequency': 'monthly'
    },
    'competitive_density': {
        'type': 'numerical',
        'description': 'Number of competing drugs in indication',
        'source': 'competitive_analysis',
        'update_frequency': 'monthly'
    },
    'mechanism_novelty': {
        'type': 'numerical',
        'description': 'Novelty score of mechanism of action',
        'source': 'patent_analysis',
        'update_frequency': 'quarterly'
    }
}
```

## Performance & Optimization

### Data Processing Performance
- **Streaming Latency**: <30 seconds end-to-end for real-time data
- **Batch Processing**: Complete daily ETL within 4-hour window
- **Query Performance**: <2 seconds for complex analytical queries
- **Search Performance**: <500ms for semantic search across 10M+ documents

### Storage Optimization
- **Compression**: 70-80% reduction using columnar formats (Parquet)
- **Partitioning**: Date-based partitioning for time-series data
- **Indexing**: B-tree and GIN indexes for frequent query patterns
- **Caching**: Multi-tier caching with Redis and application-level caches

### Scalability Targets
- **Data Volume**: Support 100TB+ with linear scaling
- **Ingestion Rate**: Handle 1M+ events per minute peak load
- **Concurrent Users**: Support 1000+ concurrent analytical queries
- **Geographic Distribution**: Multi-region deployment with <100ms latency

This comprehensive data architecture provides the foundation for a robust, scalable, and secure data platform that can handle the complex requirements of biomedical investment research while maintaining high performance and data quality standards.