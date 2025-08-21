"""Job API endpoints for long-running tool execution."""


from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from bio_mcp.http.jobs.models import JobStatus
from bio_mcp.http.jobs.service import JobNotFoundError, JobService


class CreateJobRequest(BaseModel):
    """Request model for job creation."""
    tool: str = Field(..., description="Tool name to execute")
    params: dict = Field(default_factory=dict, description="Tool parameters")
    ttl_hours: int = Field(default=24, ge=1, le=168, description="Job TTL in hours (1-168)")


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    tool: str
    status: JobStatus
    created_at: str
    duration_ms: int | None = None
    result: dict | None = None
    error: str | None = None


class CreateJobResponse(BaseModel):
    """Response model for job creation."""
    job_id: str
    status: JobStatus


class CancelJobResponse(BaseModel):
    """Response model for job cancellation."""
    cancelled: bool
    message: str | None = None


class ListJobsResponse(BaseModel):
    """Response model for job listing."""
    jobs: list[JobStatusResponse]
    total: int
    limit: int
    offset: int


def create_job_router(job_service_factory=None) -> APIRouter:
    """Create job API router with endpoints."""
    router = APIRouter(prefix="/v1/jobs", tags=["jobs"])
    
    def get_job_service() -> JobService:
        """Dependency to get job service instance."""
        if job_service_factory is not None:
            return job_service_factory()
        # This will be configured in production setup
        raise NotImplementedError("Job service dependency not configured")
    
    @router.post("", response_model=CreateJobResponse, status_code=201)
    async def create_job(
        request: CreateJobRequest,
        job_service: JobService = Depends(get_job_service)
    ) -> CreateJobResponse:
        """Create a new job for long-running tool execution."""
        # Generate trace ID from job context
        trace_id = f"job-{request.tool}-create"
        
        job_id = await job_service.create_job(
            tool_name=request.tool,
            parameters=request.params,
            trace_id=trace_id,
            ttl_hours=request.ttl_hours
        )
        
        return CreateJobResponse(
            job_id=job_id,
            status=JobStatus.PENDING
        )
    
    @router.get("/{job_id}", response_model=JobStatusResponse)
    async def get_job_status(
        job_id: str,
        job_service: JobService = Depends(get_job_service)
    ) -> JobStatusResponse:
        """Get status and details of a specific job."""
        try:
            job_data = await job_service.get_job_status(job_id)
        except JobNotFoundError:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return JobStatusResponse(
            job_id=job_data.id,
            tool=job_data.tool_name,
            status=job_data.status,
            created_at=job_data.created_at.isoformat(),
            duration_ms=int(job_data.duration_ms) if job_data.duration_ms is not None else None,
            result=job_data.result,
            error=job_data.error_message
        )
    
    @router.delete("/{job_id}", response_model=CancelJobResponse)
    async def cancel_job(
        job_id: str,
        job_service: JobService = Depends(get_job_service)
    ) -> CancelJobResponse:
        """Cancel a pending or running job."""
        try:
            success = await job_service.cancel_job(job_id)
        except JobNotFoundError:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        if success:
            return CancelJobResponse(cancelled=True)
        else:
            return CancelJobResponse(
                cancelled=False,
                message="Job already completed or failed"
            )
    
    @router.get("", response_model=ListJobsResponse)
    async def list_jobs(
        status: JobStatus | None = Query(None, description="Filter by job status"),
        limit: int = Query(50, ge=1, le=100, description="Maximum number of jobs to return"),
        offset: int = Query(0, ge=0, description="Number of jobs to skip"),
        job_service: JobService = Depends(get_job_service)
    ) -> ListJobsResponse:
        """List jobs with optional filtering and pagination."""
        jobs = await job_service.list_jobs(
            status=status,
            limit=limit,
            offset=offset
        )
        
        job_responses = [
            JobStatusResponse(
                job_id=job.id,
                tool=job.tool_name,
                status=job.status,
                created_at=job.created_at.isoformat(),
                duration_ms=job.duration_ms,
                result=job.result,
                error=job.error_message
            )
            for job in jobs
        ]
        
        return ListJobsResponse(
            jobs=job_responses,
            total=len(jobs),  # This is a simplification; real impl would get total count
            limit=limit,
            offset=offset
        )
    
    return router