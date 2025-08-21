"""FastAPI application for Bio-MCP HTTP adapter."""

from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from bio_mcp.http.adapters import invoke_tool_safely
from bio_mcp.http.errors import ErrorCode, classify_exception, create_error_envelope
from bio_mcp.http.jobs.api import create_job_router
from bio_mcp.http.jobs.service import JobService
from bio_mcp.http.jobs.storage import SQLAlchemyJobRepository
from bio_mcp.http.lifecycle import check_readiness, get_health_status
from bio_mcp.http.registry import ToolRegistry, build_registry
from bio_mcp.http.tracing import TraceContext, generate_trace_id
from bio_mcp.shared.clients.database import get_database_manager


class InvokeRequest(BaseModel):
    """Request model for tool invocation."""
    tool: str
    params: dict[str, Any] = {}
    idempotency_key: str | None = None


class InvokeResponse(BaseModel):
    """Response model for successful tool invocation."""
    ok: bool = True
    tool: str
    result: Any
    trace_id: str


class ErrorResponse(BaseModel):
    """Response model for errors."""
    ok: bool = False
    error_code: str
    message: str
    trace_id: str
    tool: str | None = None


class HealthResponse(BaseModel):
    """Response model for health checks."""
    status: str


class ToolsResponse(BaseModel):
    """Response model for tools listing."""
    tools: list[str]


def create_error_response(
    error_code: str, 
    message: str, 
    trace_id: str, 
    tool: str | None = None
) -> ErrorResponse:
    """Create a standardized error response (legacy compatibility)."""
    return ErrorResponse(
        error_code=error_code,
        message=message,
        trace_id=trace_id,
        tool=tool
    )


def create_app(registry: ToolRegistry | None = None) -> FastAPI:
    """Create and configure the FastAPI application.
    
    Args:
        registry: Optional tool registry. If None, builds default registry.
    """
    app = FastAPI(
        title="Bio-MCP HTTP Adapter",
        description="HTTP adapter for Bio-MCP server tools",
        version="1.0.0"
    )
    
    # Use provided registry or build default
    if registry is None:
        registry = build_registry()
    
    # Store registry in app state
    app.state.registry = registry
    
    # Create a job service factory
    def create_job_service() -> JobService:
        """Create job service instance with database session."""
        db_manager = get_database_manager()
        session = db_manager.get_session()
        repository = SQLAlchemyJobRepository(session)
        return JobService(repository)
    
    # Create and include job router with service factory
    job_router = create_job_router(job_service_factory=create_job_service)
    app.include_router(job_router)
    
    @app.get("/healthz", response_model=HealthResponse)
    async def healthz():
        """Liveness check - returns 200 if process is alive."""
        return HealthResponse(status="healthy")
    
    @app.get("/readyz", response_model=HealthResponse)
    async def readyz():
        """Readiness check - returns 200 if dependencies are ready."""
        if await check_readiness():
            return HealthResponse(status="ready")
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=HealthResponse(status="not_ready").model_dump()
            )
    
    @app.get("/health")
    async def health_detailed():
        """Detailed health check with all dependency status."""
        health_status = await get_health_status()
        
        if health_status.healthy:
            return {
                "status": "healthy",
                "message": health_status.message,
                "details": health_status.details,
                "duration_ms": health_status.check_duration_ms
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "unhealthy",
                    "message": health_status.message,
                    "details": health_status.details,
                    "duration_ms": health_status.check_duration_ms
                }
            )
    
    @app.get("/v1/mcp/tools", response_model=ToolsResponse)
    async def list_tools():
        """List available tools."""
        tools = app.state.registry.list_tool_names()
        return ToolsResponse(tools=tools)
    
    @app.post("/v1/mcp/invoke")
    async def invoke_tool(request: InvokeRequest):
        """Invoke a tool with given parameters using async-safe execution."""
        trace_id = generate_trace_id()
        
        # Create trace context for this request
        with TraceContext(trace_id, request.tool) as trace:
            # Add request metadata to trace
            trace.add_metadata("params", request.params)
            if request.idempotency_key:
                trace.add_metadata("idempotency_key", request.idempotency_key)
            
            try:
                # Get tool from registry
                tool_func = app.state.registry.get_tool(request.tool)
                if tool_func is None:
                    error_envelope = create_error_envelope(
                        error_code=ErrorCode.TOOL_NOT_FOUND,
                        message=f"Tool '{request.tool}' not found",
                        trace_id=trace_id,
                        tool_name=request.tool
                    )
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=error_envelope.model_dump()
                    )
                
                # Execute tool with async-safe adapter
                result = await invoke_tool_safely(
                    tool_func=tool_func,
                    tool_name=request.tool,
                    params=request.params,
                    trace_id=trace_id
                )
                
                # Mark trace as successful
                trace.set_success(result)
                
                return InvokeResponse(
                    tool=request.tool,
                    result=result,
                    trace_id=trace_id
                )
                
            except HTTPException:
                # Re-raise HTTP exceptions (like 404) as-is
                raise
            except Exception as e:
                # Classify exception and create proper error envelope
                error_code = classify_exception(e, request.tool)
                error_envelope = create_error_envelope(
                    error_code=error_code,
                    message=str(e),
                    trace_id=trace_id,
                    tool_name=request.tool,
                    exception=e
                )
                
                # Mark trace as failed
                trace.set_error(e)
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_envelope.model_dump()
                )
    
    return app