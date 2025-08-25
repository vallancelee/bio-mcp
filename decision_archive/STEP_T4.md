# T4: Database Migration Integration Plan

**Goal:** Integrate the T3 Job API system into the main database schema with proper Alembic migrations, moving from manual table creation to production-ready database integration.

## Current State Assessment

### ✅ What T3 Achieved
- Complete job system implemented (models, service, worker, API)
- PostgreSQL integration tests working with manual table creation
- 58 tests passing (50 unit + 8 PostgreSQL integration)
- Job system integrated into HTTP app
- Production-ready code quality

### 🔧 What T4 Needs to Fix
- Jobs table created manually in integration tests only
- JobRecord not in main database models (separate definition in jobs/)
- No Alembic migration for jobs table
- Production database won't have jobs table
- Health checks don't verify jobs table existence

## Implementation Steps (TDD + Clean Architecture)

### Step 1: Database Schema Integration
**Objective:** Move job models into main database schema

1. **Move JobStatus and JobRecord to `shared/models/database_models.py`**
   - Import existing job models into main database module
   - Remove duplicate definitions from `jobs/models.py`
   - Update imports across codebase

2. **Verify model consistency**
   - Ensure enum values match between manual creation and SQLAlchemy model
   - Test that existing job tests still pass with centralized models

### Step 2: Alembic Migration Creation
**Objective:** Generate proper database migration for jobs table

1. **Generate migration with autogenerate**
   ```bash
   uv run alembic revision --autogenerate -m "add_jobs_table_for_async_operations"
   ```

2. **Review and enhance generated migration**
   - Verify PostgreSQL enum type creation: `jobstatus`
   - Ensure proper indexes on: `status`, `created_at`, `tool_name`, `trace_id`, `expires_at`
   - Add proper foreign key constraints if needed
   - Validate JSONB column types for PostgreSQL

3. **Test migration rollback**
   - Ensure migration can be safely rolled back
   - Test upgrade/downgrade cycle

### Step 3: Integration Test Migration
**Objective:** Update integration tests to use real migrations instead of manual table creation

1. **Remove manual table creation from integration tests**
   - Delete the manual `CREATE TABLE` and `CREATE TYPE` statements
   - Use standard database initialization with migrations

2. **Update test database setup**
   - Ensure test database runs full Alembic migrations
   - Verify tests still pass with migration-created tables

3. **Add migration-specific tests**
   - Test that migration creates correct table structure
   - Test that PostgreSQL enum values match Python enum values
   - Verify all indexes are created correctly

### Step 4: Production Database Readiness
**Objective:** Ensure production deployments will have jobs table

1. **Update database initialization**
   - Ensure `init_database()` includes JobRecord in metadata
   - Verify all models are properly imported for autogenerate

2. **Update health checks**
   - Add jobs table verification to readiness checks
   - Ensure `/readyz` fails if jobs table doesn't exist
   - Test health check with and without migrations applied

### Step 5: Deployment Integration
**Objective:** Ensure smooth deployment with database migrations

1. **Migration deployment strategy**
   - Document migration order (run before app deployment)
   - Add migration verification to deployment scripts
   - Ensure zero-downtime deployment compatibility

2. **Rollback safety**
   - Verify that job system gracefully handles missing table (during rollbacks)
   - Add proper error handling for schema mismatches
   - Document rollback procedures

## File Structure Changes

```
src/bio_mcp/shared/models/database_models.py
├── Add: JobStatus(enum.Enum)
├── Add: JobRecord(Base)
└── Update: imports and dependencies

src/bio_mcp/http/jobs/models.py  
├── Remove: duplicate JobStatus and JobRecord
├── Keep: JobData business logic class
└── Update: imports to use shared models

migrations/versions/
└── Add: 002_add_jobs_table_for_async_operations.py

tests/http/test_job_integration.py
├── Remove: manual CREATE TABLE statements
├── Update: use standard database initialization
└── Add: migration verification tests
```

## Database Schema (Target State)

### Jobs Table (PostgreSQL)
```sql
-- Enum type
CREATE TYPE jobstatus AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled');

-- Main table
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_name VARCHAR(100) NOT NULL,
    status jobstatus NOT NULL DEFAULT 'pending',
    trace_id VARCHAR(36) NOT NULL,
    parameters JSONB NOT NULL,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL
);

-- Indexes for performance
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);
CREATE INDEX idx_jobs_tool_name ON jobs(tool_name);
CREATE INDEX idx_jobs_trace_id ON jobs(trace_id);
CREATE INDEX idx_jobs_expires_at ON jobs(expires_at);
```

## Testing Strategy

### Migration Testing
```bash
# Test migration forward
uv run alembic upgrade head

# Test migration backward
uv run alembic downgrade -1

# Test autogenerate detects no changes after migration
uv run alembic revision --autogenerate -m "test_no_changes"
```

### Integration Testing
```bash
# Test with clean database
uv run pytest tests/http/test_job_integration.py -v

# Test job system end-to-end
uv run pytest tests/http/test_job_*.py -v
```

### Health Check Testing
```bash
# Test readiness with migrations
curl localhost:8080/readyz

# Test health with job system
curl localhost:8080/health
```

## Acceptance Criteria

- [ ] JobStatus and JobRecord moved to `shared/models/database_models.py`
- [ ] All job tests pass with centralized models
- [ ] Alembic migration created and tested (forward/backward)
- [ ] PostgreSQL enum type properly created in migration
- [ ] All required indexes created by migration
- [ ] Integration tests use real migrations instead of manual table creation
- [ ] Health checks verify jobs table existence
- [ ] Production database initialization includes job models
- [ ] Migration documentation updated
- [ ] Rollback procedures documented

## Risk Mitigation

### Schema Drift Prevention
- Alembic autogenerate will catch any model changes
- Integration tests verify schema matches code expectations
- Health checks ensure table exists before job operations

### Deployment Safety
- Migration runs before application deployment
- Health checks prevent app startup with wrong schema
- Graceful degradation if jobs table missing

### Performance Considerations
- Proper indexing strategy for common job queries
- JSONB storage for efficient parameter/result access
- Cleanup strategy for expired jobs

## Success Metrics

1. **Migration Success**: Clean migration up/down without data loss
2. **Test Coverage**: All 58 existing job tests pass with new schema
3. **Performance**: Job operations maintain current performance levels
4. **Production Ready**: Health checks pass, app starts successfully
5. **Maintainability**: Single source of truth for job models

This T4 plan moves the job system from "works in tests" to "production ready with proper database integration".