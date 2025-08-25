# T3: Job API for Long-Running Tools Plan

**Goal:** Add asynchronous job API for long-running operations with database persistence and progress tracking.

## TDD Approach (Red-Green-Refactor)

1. **Write failing tests for job database schema**
   - Test job table creation and migrations
   - Test job status transitions and validation
   - Test job data persistence and retrieval
   - Test job cleanup and TTL behavior

2. **Write failing tests for job lifecycle management**
   - Test job creation with unique job IDs
   - Test job status updates (pending → running → completed/failed)
   - Test job cancellation and timeout handling
   - Test concurrent job execution limits

3. **Write failing tests for job API endpoints**
   - Test POST `/v1/jobs` for job creation
   - Test GET `/v1/jobs/{job_id}` for job status
   - Test DELETE `/v1/jobs/{job_id}` for job cancellation
   - Test GET `/v1/jobs` for job listing with pagination

4. **Implement job infrastructure with clean architecture**
   - Create job database models with SQLAlchemy
   - Implement job service layer with business logic
   - Create job worker pool with asyncio task management
   - Add job API controllers with proper error handling

5. **Refactor: extract job management patterns**
   - Extract job execution strategies (immediate vs queued)
   - Create job result serialization/deserialization
   - Add job metrics and observability hooks

## Clean Code Principles

- **Single Responsibility:** Separate job persistence, execution, and API concerns
- **Dependency Inversion:** Abstract job storage and execution interfaces
- **Command Pattern:** Jobs as executable commands with rollback capability
- **Observer Pattern:** Job status change notifications
- **Factory Pattern:** Job creation based on tool type and parameters

## File Structure
```
src/bio_mcp/http/
├── jobs/
│   ├── __init__.py
│   ├── models.py           # SQLAlchemy job models
│   ├── service.py          # Job business logic service
│   ├── worker.py           # Job execution worker pool
│   ├── api.py              # Job API endpoints
│   └── storage.py          # Job persistence layer

tests/http/
├── test_job_models.py      # Database model tests
├── test_job_service.py     # Business logic tests
├── test_job_worker.py      # Worker execution tests
├── test_job_api.py         # API endpoint tests
└── test_job_integration.py # End-to-end job tests
```

## Implementation Steps

1. **Create job module structure and migrations**
   ```bash
   mkdir -p src/bio_mcp/http/jobs
   touch src/bio_mcp/http/jobs/{__init__.py,models.py,service.py,worker.py,api.py,storage.py}
   ```

2. **Create job test files**
   ```bash
   touch tests/http/{test_job_models.py,test_job_service.py,test_job_worker.py,test_job_api.py,test_job_integration.py}
   ```

3. **Write tests first (TDD)**
   - Start with job model and database schema tests
   - Add job service business logic tests
   - Add worker pool and execution tests
   - Add API endpoint tests with proper authentication

4. **Implement job system**
   - Create job database models with proper indexing
   - Implement job service with status management
   - Create worker pool with concurrency limits
   - Add job API endpoints with validation

## Key Components to Implement

### 1. Job Models (`models.py`)
```python
from sqlalchemy import Column, String, DateTime, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB

class JobStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Job(Base):
    """Database model for async jobs."""
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    tool_name = Column(String(100), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    parameters = Column(JSONB, nullable=False)
    result = Column(JSONB)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    trace_id = Column(String(36))
```

### 2. Job Service (`service.py`)
```python
class JobService:
    """Service layer for job management."""
    
    async def create_job(
        self,
        tool_name: str,
        parameters: dict,
        trace_id: str,
        ttl_hours: int = 24
    ) -> str:
        """Create a new job and return job ID."""
        pass
    
    async def get_job_status(self, job_id: str) -> JobStatusResponse:
        """Get current job status and results."""
        pass
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running or pending job."""
        pass
    
    async def list_jobs(
        self, 
        status: JobStatus = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[JobSummary]:
        """List jobs with pagination."""
        pass
```

### 3. Job Worker (`worker.py`)
```python
class JobWorker:
    """Executes jobs asynchronously with concurrency control."""
    
    def __init__(self, max_concurrent_jobs: int = 10):
        self.max_concurrent = max_concurrent_jobs
        self.running_jobs = {}
        self.job_semaphore = asyncio.Semaphore(max_concurrent_jobs)
    
    async def execute_job(self, job: Job) -> None:
        """Execute a job with proper error handling."""
        pass
    
    async def start_worker_pool(self) -> None:
        """Start background worker to process pending jobs."""
        pass
```

### 4. Job API Endpoints (`api.py`)
```python
@router.post("/v1/jobs", response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest):
    """Create a new asynchronous job."""
    pass

@router.get("/v1/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get job status and results."""
    pass

@router.delete("/v1/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running job."""
    pass

@router.get("/v1/jobs", response_model=JobListResponse)
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0)
):
    """List jobs with pagination."""
    pass
```

## Database Migration

Create Alembic migration for job table:
```sql
-- Migration: Add jobs table for async execution
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_name VARCHAR(100) NOT NULL,
    status job_status_enum DEFAULT 'pending',
    parameters JSONB NOT NULL,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ, 
    expires_at TIMESTAMPTZ NOT NULL,
    trace_id VARCHAR(36)
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);
CREATE INDEX idx_jobs_tool_name ON jobs(tool_name);
CREATE INDEX idx_jobs_trace_id ON jobs(trace_id);
```

## Tool Classification

### Immediate Tools (Sync/Fast)
- `ping` - Always immediate
- `pubmed.search` - Fast queries (< 2s)
- `corpus.checkpoint.*` - Simple database operations

### Job-Eligible Tools (Async/Slow)
- `rag.get` - Vector search can be slow
- `pubmed.sync` - Large data synchronization
- `rag.index` - Document indexing operations
- Future ETL/ML tools

## Job Request/Response Models

### Job Creation
```python
class JobCreateRequest(BaseModel):
    tool: str
    params: dict[str, Any] = {}
    ttl_hours: int = Field(24, ge=1, le=168)  # 1 hour to 1 week
    priority: int = Field(0, ge=0, le=10)     # 0=lowest, 10=highest

class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    estimated_duration: Optional[str] = None
    position_in_queue: Optional[int] = None
```

### Job Status
```python
class JobStatusResponse(BaseModel):
    job_id: str
    tool: str
    status: JobStatus
    progress: Optional[float] = None      # 0.0 to 1.0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
```

## Configuration Options

```python
JOB_CONFIG = {
    "max_concurrent_jobs": 10,
    "job_cleanup_interval_hours": 24,
    "default_job_ttl_hours": 24,
    "max_job_ttl_hours": 168,
    "job_poll_interval_seconds": 1.0,
    "result_compression": True,
    "enable_job_metrics": True
}
```

## Error Handling Strategy

- **Job Creation Errors:** Immediate HTTP 400 with validation details
- **Job Execution Errors:** Stored in job record, returned via status API
- **Worker Pool Errors:** Graceful degradation with retry logic
- **Database Errors:** Circuit breaker pattern with fallback responses

## Acceptance Criteria

- [ ] Job database table created with proper indexes and constraints
- [ ] Job creation API accepts tool name and parameters
- [ ] Job status API returns current status and results when complete
- [ ] Job cancellation works for pending and running jobs
- [ ] Worker pool respects concurrency limits and processes jobs FIFO
- [ ] Job results persist for configured TTL before cleanup
- [ ] Long-running tools (>5s) automatically use job API
- [ ] Fast tools (<5s) continue using immediate execution
- [ ] Proper error handling with structured error responses
- [ ] Job metrics and logging for observability
- [ ] Unit test coverage ≥ 90% for all job modules
- [ ] Integration tests with real database persistence
- [ ] All tests pass: `uv run pytest tests/http/`
- [ ] Code passes linting: `uv run ruff check`

## Integration with Existing Components

- **Registry:** Enhance tool metadata to indicate job-eligible tools
- **Adapters:** Route slow tools through job API, fast tools immediate
- **Tracing:** Ensure job operations include trace correlation
- **Errors:** Use existing error classification for job failures
- **Health:** Job system health included in dependency checks

## Performance Requirements

- **Job Creation:** < 100ms for job submission
- **Status Polling:** < 50ms for status retrieval  
- **Worker Throughput:** Handle 100+ concurrent jobs efficiently
- **Database Performance:** Job queries optimized with proper indexing
- **Memory Usage:** Bounded job result storage with compression

## Notes

- Jobs provide better UX for long-running operations (>5s)
- Database persistence ensures job survival across server restarts
- Proper cleanup prevents job table growth over time
- Worker pool design allows horizontal scaling in future
- This enables reliable execution of heavy biomedical processing tasks