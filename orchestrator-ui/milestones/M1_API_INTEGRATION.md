# M1 — API Integration (2 days)

## Objective
Create the backend FastAPI infrastructure for orchestrator execution, streaming results, and session management. This milestone establishes the foundation for the orchestrator UI by implementing all necessary API endpoints and real-time communication channels.

## Dependencies
- Bio-MCP server with LangGraph orchestrator (M4 synthesis milestone completed)
- Existing FastAPI HTTP adapter at `src/bio_mcp/http/app.py`
- Database infrastructure and session management
- MCP tool definitions and routing

## Deliverables

### 1. Orchestrator FastAPI Application

**File**: `src/bio_mcp/http/orchestrator_app.py`
```python
"""FastAPI application for Bio-MCP orchestrator with streaming support."""
from datetime import UTC, datetime, timedelta
from typing import Any, AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
import json
import asyncio

from bio_mcp.orchestrator.graph import BioMCPGraph
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.http.jobs.service import JobService
from bio_mcp.shared.clients.database import get_database_manager


class OrchestrationRequest(BaseModel):
    """Request model for orchestrator execution."""
    query: str = Field(..., description="Natural language query to orchestrate")
    config: dict[str, Any] = Field(default_factory=dict, description="Execution configuration")
    debug_mode: bool = Field(default=False, description="Enable debug mode with breakpoints")
    session_name: str | None = Field(default=None, description="Optional session name")

class OrchestrationResponse(BaseModel):
    """Response model for orchestration initiation."""
    session_id: str
    status: str = "initiated"
    query: str
    estimated_duration_ms: int = Field(default=5000)
    stream_url: str

class SessionListResponse(BaseModel):
    """Response model for session listing."""
    sessions: list[dict[str, Any]]
    total: int
    limit: int
    offset: int

class GraphVisualizationResponse(BaseModel):
    """Response model for graph visualization data."""
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    layout: dict[str, Any]
    metadata: dict[str, Any]


def create_orchestrator_app() -> FastAPI:
    """Create and configure the orchestrator FastAPI application."""
    app = FastAPI(
        title="Bio-MCP Orchestrator API",
        description="Real-time orchestration API with streaming support",
        version="1.0.0",
        docs_url="/orchestrator/docs",
        redoc_url="/orchestrator/redoc"
    )

    # Initialize orchestrator
    config = OrchestratorConfig()
    orchestrator = BioMCPGraph(config)
    
    # Session storage (in production, use Redis or database)
    active_sessions: dict[str, dict[str, Any]] = {}
    session_results: dict[str, dict[str, Any]] = {}

    @app.post("/v1/orchestrator/query", response_model=OrchestrationResponse)
    async def execute_orchestration(request: OrchestrationRequest):
        """Initiate orchestrator execution with streaming support."""
        session_id = str(uuid4())
        
        # Create session record
        session_data = {
            "session_id": session_id,
            "query": request.query,
            "config": request.config,
            "debug_mode": request.debug_mode,
            "session_name": request.session_name or f"Session {session_id[:8]}",
            "status": "queued",
            "created_at": datetime.now(UTC).isoformat(),
            "estimated_duration_ms": 5000,
        }
        active_sessions[session_id] = session_data
        
        # Start orchestration in background
        asyncio.create_task(execute_orchestration_background(session_id, request))
        
        return OrchestrationResponse(
            session_id=session_id,
            query=request.query,
            stream_url=f"/v1/orchestrator/stream/{session_id}"
        )

    async def execute_orchestration_background(session_id: str, request: OrchestrationRequest):
        """Execute orchestration in background with result streaming."""
        try:
            active_sessions[session_id]["status"] = "running"
            active_sessions[session_id]["started_at"] = datetime.now(UTC).isoformat()
            
            # Execute orchestration with streaming
            if request.debug_mode:
                # Debug mode - step-by-step execution
                result = await execute_debug_orchestration(session_id, request)
            else:
                # Normal streaming execution
                result = await orchestrator.invoke(request.query, request.config)
            
            # Store final result
            session_results[session_id] = result
            active_sessions[session_id]["status"] = "completed"
            active_sessions[session_id]["completed_at"] = datetime.now(UTC).isoformat()
            
        except Exception as e:
            # Handle orchestration errors
            error_result = {
                "error": str(e),
                "error_type": type(e).__name__,
                "session_id": session_id,
                "failed_at": datetime.now(UTC).isoformat()
            }
            session_results[session_id] = error_result
            active_sessions[session_id]["status"] = "failed"
            active_sessions[session_id]["error"] = str(e)

    async def execute_debug_orchestration(session_id: str, request: OrchestrationRequest):
        """Execute orchestration in debug mode with breakpoints."""
        # Implementation for debug mode execution
        # This will be enhanced with WebSocket communication
        return await orchestrator.invoke(request.query, request.config)

    @app.get("/v1/orchestrator/stream/{session_id}")
    async def stream_orchestration_results(session_id: str):
        """Stream orchestration results via Server-Sent Events."""
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        async def event_generator() -> AsyncGenerator[str, None]:
            """Generate SSE events for orchestration progress."""
            last_update = datetime.now(UTC)
            
            while True:
                try:
                    # Get current session status
                    session = active_sessions.get(session_id)
                    if not session:
                        yield f"event: error\ndata: {json.dumps({'error': 'Session expired'})}\n\n"
                        break

                    # Send status updates
                    status_data = {
                        "session_id": session_id,
                        "status": session["status"],
                        "timestamp": datetime.now(UTC).isoformat()
                    }
                    yield f"event: status\ndata: {json.dumps(status_data)}\n\n"

                    # Send final result when completed
                    if session["status"] in ["completed", "failed"]:
                        if session_id in session_results:
                            result_data = session_results[session_id]
                            yield f"event: result\ndata: {json.dumps(result_data)}\n\n"
                        yield f"event: done\ndata: {json.dumps({'session_id': session_id})}\n\n"
                        break

                    # Wait before next update
                    await asyncio.sleep(0.1)  # 100ms polling interval
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    error_data = {"error": str(e), "session_id": session_id}
                    yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
                    break

        return EventSourceResponse(event_generator())

    @app.get("/v1/orchestrator/sessions", response_model=SessionListResponse)
    async def list_sessions(limit: int = 50, offset: int = 0):
        """List recent orchestration sessions."""
        # Sort sessions by creation time (most recent first)
        sorted_sessions = sorted(
            active_sessions.values(),
            key=lambda s: s["created_at"],
            reverse=True
        )
        
        # Apply pagination
        paginated_sessions = sorted_sessions[offset:offset + limit]
        
        return SessionListResponse(
            sessions=paginated_sessions,
            total=len(sorted_sessions),
            limit=limit,
            offset=offset
        )

    @app.get("/v1/orchestrator/session/{session_id}")
    async def get_session_details(session_id: str):
        """Get detailed information about a specific session."""
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = active_sessions[session_id].copy()
        
        # Include results if available
        if session_id in session_results:
            session_data["result"] = session_results[session_id]
            
        return session_data

    @app.delete("/v1/orchestrator/session/{session_id}")
    async def delete_session(session_id: str):
        """Delete a session and its results."""
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Clean up session data
        active_sessions.pop(session_id, None)
        session_results.pop(session_id, None)
        
        return {"message": f"Session {session_id} deleted successfully"}

    @app.get("/v1/orchestrator/graph/visualization", response_model=GraphVisualizationResponse)
    async def get_graph_visualization():
        """Get orchestrator graph structure for visualization."""
        # Build graph and extract structure
        graph = orchestrator.build_graph()
        
        # Convert LangGraph to visualization format
        nodes = []
        edges = []
        
        # Extract nodes from graph
        for node_name in graph.nodes:
            nodes.append({
                "id": node_name,
                "type": "orchestrator_node",
                "label": node_name.replace("_", " ").title(),
                "position": {"x": 0, "y": 0},  # Will be calculated by frontend
                "data": {
                    "node_type": "processing",
                    "description": f"Orchestrator node: {node_name}"
                }
            })
        
        # Extract edges from graph
        for source, targets in graph.edges.items():
            if isinstance(targets, list):
                for target in targets:
                    edges.append({
                        "id": f"{source}->{target}",
                        "source": source,
                        "target": target,
                        "type": "orchestrator_edge"
                    })
            else:
                edges.append({
                    "id": f"{source}->{targets}",
                    "source": source,
                    "target": targets,
                    "type": "orchestrator_edge"
                })
        
        return GraphVisualizationResponse(
            nodes=nodes,
            edges=edges,
            layout={"direction": "horizontal", "spacing": 150},
            metadata={
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "graph_type": "langgraph_orchestrator"
            }
        )

    @app.post("/v1/orchestrator/debug/breakpoint/{session_id}")
    async def set_debug_breakpoint(session_id: str, node_name: str, enabled: bool = True):
        """Set or remove debug breakpoints for a session."""
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = active_sessions[session_id]
        if not session.get("debug_mode"):
            raise HTTPException(status_code=400, detail="Session is not in debug mode")
        
        # Store breakpoint configuration
        breakpoints = session.setdefault("breakpoints", {})
        breakpoints[node_name] = enabled
        
        return {
            "session_id": session_id,
            "node_name": node_name,
            "breakpoint_enabled": enabled,
            "total_breakpoints": sum(1 for bp in breakpoints.values() if bp)
        }

    @app.post("/v1/orchestrator/debug/step/{session_id}")
    async def debug_step_execution(session_id: str, node_name: str):
        """Execute a single step in debug mode."""
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = active_sessions[session_id]
        if not session.get("debug_mode"):
            raise HTTPException(status_code=400, detail="Session is not in debug mode")
        
        # This will be implemented with more sophisticated debug control
        return {
            "session_id": session_id,
            "node_name": node_name,
            "status": "stepped",
            "message": f"Executed step for node: {node_name}"
        }

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check for orchestrator API."""
        return {
            "status": "healthy",
            "service": "orchestrator-api",
            "timestamp": datetime.now(UTC).isoformat(),
            "active_sessions": len(active_sessions)
        }

    return app


# Create the application instance
app = create_orchestrator_app()
```

### 2. Enhanced HTTP App Integration

**File**: `src/bio_mcp/http/app.py` (Updates)
```python
# Add orchestrator app mounting
from bio_mcp.http.orchestrator_app import create_orchestrator_app

def create_app(registry: ToolRegistry | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Bio-MCP HTTP Adapter",
        description="HTTP adapter for Bio-MCP server tools with orchestrator",
        version="1.0.0",
    )
    
    # ... existing setup ...
    
    # Mount orchestrator application
    orchestrator_app = create_orchestrator_app()
    app.mount("/orchestrator", orchestrator_app)
    
    # Serve orchestrator UI static files
    orchestrator_ui_dir = Path(__file__).parent / "static" / "orchestrator"
    if orchestrator_ui_dir.exists():
        app.mount("/orchestrator/ui", StaticFiles(directory=str(orchestrator_ui_dir)), name="orchestrator-ui")
    
    @app.get("/orchestrator/")
    async def serve_orchestrator_ui():
        """Serve the orchestrator UI."""
        ui_file = Path(__file__).parent / "static" / "orchestrator" / "index.html"
        if ui_file.exists():
            return FileResponse(str(ui_file))
        else:
            return {"message": "Orchestrator UI not available"}
    
    # ... rest of existing endpoints ...
    
    return app
```

### 3. WebSocket Debug Communication

**File**: `src/bio_mcp/http/websocket_debug.py`
```python
"""WebSocket communication for orchestrator debugging."""
from typing import Any, Dict, List
import json
import asyncio
from datetime import UTC, datetime

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel


class DebugMessage(BaseModel):
    """Base debug message format."""
    type: str
    session_id: str
    timestamp: str = datetime.now(UTC).isoformat()
    data: Dict[str, Any] = {}


class WebSocketDebugManager:
    """Manage WebSocket connections for debug sessions."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.debug_sessions: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept WebSocket connection for debug session."""
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, session_id: str):
        """Remove WebSocket connection."""
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
    
    async def send_debug_message(self, session_id: str, message: DebugMessage):
        """Send debug message to all connected clients."""
        if session_id in self.active_connections:
            message_json = message.model_dump_json()
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_text(message_json)
                except Exception:
                    # Remove failed connections
                    self.disconnect(connection, session_id)
    
    async def handle_debug_command(self, session_id: str, command: Dict[str, Any]) -> Dict[str, Any]:
        """Process debug commands from client."""
        command_type = command.get("type")
        
        if command_type == "set_breakpoint":
            return await self.set_breakpoint(session_id, command["node_name"], command.get("enabled", True))
        elif command_type == "step":
            return await self.step_execution(session_id, command["node_name"])
        elif command_type == "inspect_state":
            return await self.inspect_node_state(session_id, command["node_name"])
        else:
            return {"error": f"Unknown debug command: {command_type}"}
    
    async def set_breakpoint(self, session_id: str, node_name: str, enabled: bool) -> Dict[str, Any]:
        """Set or remove breakpoint for a node."""
        if session_id not in self.debug_sessions:
            self.debug_sessions[session_id] = {"breakpoints": {}}
        
        self.debug_sessions[session_id]["breakpoints"][node_name] = enabled
        
        return {
            "type": "breakpoint_set",
            "node_name": node_name,
            "enabled": enabled
        }
    
    async def step_execution(self, session_id: str, node_name: str) -> Dict[str, Any]:
        """Execute one step in debug mode."""
        # This will interface with the orchestrator's debug capabilities
        return {
            "type": "step_executed",
            "node_name": node_name,
            "timestamp": datetime.now(UTC).isoformat()
        }
    
    async def inspect_node_state(self, session_id: str, node_name: str) -> Dict[str, Any]:
        """Get detailed state information for a node."""
        # This will extract state from the orchestrator
        return {
            "type": "state_inspection",
            "node_name": node_name,
            "state": {},  # Actual state will be populated
            "timestamp": datetime.now(UTC).isoformat()
        }


# Global debug manager instance
debug_manager = WebSocketDebugManager()


async def websocket_debug_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for debug communication."""
    await debug_manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive debug commands from client
            data = await websocket.receive_text()
            command = json.loads(data)
            
            # Process command and send response
            response = await debug_manager.handle_debug_command(session_id, command)
            response_message = DebugMessage(
                type="command_response",
                session_id=session_id,
                data=response
            )
            await debug_manager.send_debug_message(session_id, response_message)
            
    except WebSocketDisconnect:
        debug_manager.disconnect(websocket, session_id)
```

### 4. Session Management and Storage

**File**: `src/bio_mcp/http/session_storage.py`
```python
"""Session storage for orchestrator executions."""
from typing import Any, Dict, List, Optional
from datetime import UTC, datetime, timedelta
import json
import asyncio
from pathlib import Path

from pydantic import BaseModel


class OrchestrationSession(BaseModel):
    """Model for orchestration session data."""
    session_id: str
    query: str
    config: Dict[str, Any]
    debug_mode: bool = False
    session_name: Optional[str] = None
    status: str = "created"
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class SessionStorage:
    """Storage manager for orchestration sessions."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("orchestrator_sessions")
        self.storage_path.mkdir(exist_ok=True)
        self.sessions: Dict[str, OrchestrationSession] = {}
        self.cleanup_interval = 3600  # 1 hour cleanup interval
        self.session_ttl = timedelta(days=7)  # Keep sessions for 7 days
        
        # Start background cleanup task
        asyncio.create_task(self.cleanup_expired_sessions())
    
    async def create_session(self, session_data: Dict[str, Any]) -> OrchestrationSession:
        """Create a new orchestration session."""
        session = OrchestrationSession(
            created_at=datetime.now(UTC),
            **session_data
        )
        
        self.sessions[session.session_id] = session
        await self.save_session(session)
        return session
    
    async def get_session(self, session_id: str) -> Optional[OrchestrationSession]:
        """Get session by ID."""
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        # Try to load from storage
        return await self.load_session(session_id)
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> Optional[OrchestrationSession]:
        """Update session with new data."""
        session = await self.get_session(session_id)
        if not session:
            return None
        
        # Update session data
        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        self.sessions[session_id] = session
        await self.save_session(session)
        return session
    
    async def list_sessions(self, limit: int = 50, offset: int = 0) -> List[OrchestrationSession]:
        """List sessions with pagination."""
        # Load all sessions from storage
        await self.load_all_sessions()
        
        # Sort by creation time (most recent first)
        sorted_sessions = sorted(
            self.sessions.values(),
            key=lambda s: s.created_at,
            reverse=True
        )
        
        return sorted_sessions[offset:offset + limit]
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
        
        # Delete from storage
        session_file = self.storage_path / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            return True
        
        return False
    
    async def save_session(self, session: OrchestrationSession):
        """Save session to persistent storage."""
        session_file = self.storage_path / f"{session.session_id}.json"
        with open(session_file, 'w') as f:
            json.dump(session.model_dump(mode='json'), f, indent=2)
    
    async def load_session(self, session_id: str) -> Optional[OrchestrationSession]:
        """Load session from persistent storage."""
        session_file = self.storage_path / f"{session_id}.json"
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            session = OrchestrationSession.model_validate(session_data)
            self.sessions[session_id] = session
            return session
        except Exception:
            return None
    
    async def load_all_sessions(self):
        """Load all sessions from storage."""
        for session_file in self.storage_path.glob("*.json"):
            session_id = session_file.stem
            if session_id not in self.sessions:
                await self.load_session(session_id)
    
    async def cleanup_expired_sessions(self):
        """Background task to clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                cutoff_time = datetime.now(UTC) - self.session_ttl
                expired_sessions = [
                    session_id for session_id, session in self.sessions.items()
                    if session.created_at < cutoff_time
                ]
                
                for session_id in expired_sessions:
                    await self.delete_session(session_id)
                
            except Exception:
                # Log error but continue cleanup
                pass


# Global session storage instance
session_storage = SessionStorage()
```

## Integration Points

### 1. Update Main HTTP App
Add orchestrator app mounting and static file serving for the UI.

### 2. Database Integration
Connect session storage with existing Bio-MCP database infrastructure.

### 3. MCP Tool Integration
Ensure orchestrator can access all existing MCP tools (PubMed, ClinicalTrials, RAG).

### 4. Configuration Management
Integrate with existing Bio-MCP configuration system.

## Testing Requirements

### 1. Unit Tests

**File**: `tests/unit/http/test_orchestrator_api.py`
```python
"""Test orchestrator API endpoints."""
import pytest
from fastapi.testclient import TestClient

from bio_mcp.http.orchestrator_app import create_orchestrator_app


@pytest.fixture
def client():
    app = create_orchestrator_app()
    return TestClient(app)


def test_execute_orchestration(client):
    """Test orchestration execution endpoint."""
    response = client.post(
        "/v1/orchestrator/query",
        json={"query": "GLP-1 receptor agonist trials"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["query"] == "GLP-1 receptor agonist trials"


def test_session_listing(client):
    """Test session listing endpoint."""
    response = client.get("/v1/orchestrator/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "total" in data


def test_graph_visualization(client):
    """Test graph visualization endpoint."""
    response = client.get("/v1/orchestrator/graph/visualization")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
```

### 2. Integration Tests

**File**: `tests/integration/http/test_orchestrator_streaming.py`
```python
"""Test orchestrator streaming functionality."""
import pytest
import asyncio
from fastapi.testclient import TestClient

from bio_mcp.http.orchestrator_app import create_orchestrator_app


@pytest.mark.asyncio
async def test_sse_streaming():
    """Test Server-Sent Events streaming."""
    # This will test the SSE endpoint functionality
    pass


@pytest.mark.asyncio  
async def test_websocket_debug():
    """Test WebSocket debug communication."""
    # This will test WebSocket debug functionality
    pass
```

## Acceptance Criteria
- [ ] FastAPI orchestrator application created with all endpoints
- [ ] Server-Sent Events streaming implementation working
- [ ] WebSocket debug communication functional
- [ ] Session management and storage implemented
- [ ] Graph visualization endpoint returning proper data
- [ ] Integration with existing Bio-MCP HTTP infrastructure
- [ ] Unit tests passing for all endpoints
- [ ] Integration tests validating streaming functionality
- [ ] API documentation auto-generated and accessible

## Files Created/Modified
- `src/bio_mcp/http/orchestrator_app.py` - Main orchestrator FastAPI app
- `src/bio_mcp/http/websocket_debug.py` - WebSocket debug communication
- `src/bio_mcp/http/session_storage.py` - Session persistence management
- `src/bio_mcp/http/app.py` - Updated to mount orchestrator app
- `tests/unit/http/test_orchestrator_api.py` - Unit tests
- `tests/integration/http/test_orchestrator_streaming.py` - Integration tests

## Dependencies Required
```toml
# Add to pyproject.toml
[project]
dependencies = [
    # ... existing dependencies ...
    "sse-starlette>=1.6.5",    # Server-Sent Events support
    "python-socketio>=5.8.0",  # WebSocket communication
    "python-multipart>=0.0.6", # Form data support
]
```

## Next Steps
After completion, proceed to **M2 — Core UI Foundation** which will create the React application and essential components for the orchestrator interface.