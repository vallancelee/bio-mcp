#!/usr/bin/env python3
"""
BioInvest AI Copilot POC - Backend Orchestrator

FastAPI backend that orchestrates Bio-MCP queries and streams results to the frontend.
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from src.models.schemas import (
    OrchestrationRequest,
    OrchestrationResponse,
    QueryStatus,
    SynthesisResponse,
)
from src.orchestrator.bio_mcp_client import BioMCPClient
from src.orchestrator.langgraph_client import LangGraphOrchestrator
from src.services.synthesis import SynthesisService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global state for managing queries and results
active_queries: dict[str, dict[str, Any]] = {}
bio_mcp_client: BioMCPClient | None = None
synthesis_service: SynthesisService | None = None
langgraph_orchestrator: LangGraphOrchestrator | None = None


def _format_source_results(source: str, results: dict[str, Any]) -> dict[str, Any]:
    """Format source results with correct field names for frontend contract"""
    if source == "pubmed":
        return {
            "total_found": results.get("total_found", 0),
            "results": results.get("results", [])[:10],
        }
    elif source == "clinical_trials":
        return {
            "total_found": results.get("total_found", 0),
            "studies": results.get("results", [])[:10],
        }
    elif source == "rag":
        return {
            "total_found": results.get("total_found", 0),
            "documents": results.get("results", [])[:10],
        }
    else:
        return {
            "total_found": results.get("total_found", 0),
            "results": results.get("results", [])[:10],
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global bio_mcp_client, synthesis_service, langgraph_orchestrator

    logger.info("Starting BioInvest POC Backend...")

    # Initialize Bio-MCP client
    bio_mcp_client = BioMCPClient()
    await bio_mcp_client.initialize()

    # Initialize synthesis service
    synthesis_service = SynthesisService()

    # Initialize LangGraph orchestrator - fail fast if issues
    try:
        langgraph_orchestrator = LangGraphOrchestrator()
        await langgraph_orchestrator.initialize()
        logger.info("LangGraph orchestrator initialized successfully")
    except Exception as e:
        logger.error(f"LangGraph orchestrator initialization failed: {e}")
        raise RuntimeError(
            f"POC backend startup failed: LangGraph orchestrator initialization error: {e}"
        ) from e

    logger.info("Backend initialization complete")

    yield

    logger.info("Shutting down Backend...")
    if bio_mcp_client:
        await bio_mcp_client.close()
    if langgraph_orchestrator:
        await langgraph_orchestrator.cleanup()


# Create FastAPI app
app = FastAPI(
    title="BioInvest AI Copilot POC",
    description="Proof-of-concept backend orchestrator for biotech investment research",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "BioInvest AI Copilot POC Backend",
        "version": "0.1.0",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "bio_mcp_connected": bio_mcp_client is not None
        and await bio_mcp_client.health_check(),
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    bio_mcp_healthy = False
    if bio_mcp_client:
        bio_mcp_healthy = await bio_mcp_client.health_check()

    return {
        "status": "healthy" if bio_mcp_healthy else "degraded",
        "components": {
            "bio_mcp": "healthy" if bio_mcp_healthy else "unhealthy",
            "synthesis_service": "healthy" if synthesis_service else "unhealthy",
        },
        "active_queries": len(active_queries),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/research/query", response_model=OrchestrationResponse)
async def submit_query(request: OrchestrationRequest):
    """Submit a new research query for processing"""

    if not bio_mcp_client:
        raise HTTPException(status_code=503, detail="Bio-MCP client not initialized")

    # Generate query ID
    query_id = str(uuid4())

    # Store query state
    active_queries[query_id] = {
        "id": query_id,
        "query": request.query,
        "status": QueryStatus.INITIATED,
        "sources": request.sources,
        "max_results": request.options.max_results_per_source,
        "options": request.options,
        "created_at": datetime.utcnow().isoformat(),
        "results": {},
        "synthesis": None,
        "progress": {
            "pubmed": "pending",
            "clinical_trials": "pending",
            "rag": "pending",
        },
    }

    # Start background processing
    asyncio.create_task(process_query(query_id))

    logger.info(f"Query {query_id} initiated: {request.query[:100]}")

    return OrchestrationResponse(
        query_id=query_id,
        status=QueryStatus.INITIATED,
        estimated_completion_time=30,  # seconds
        progress=active_queries[query_id]["progress"],
        partial_results_available=True,
        stream_url=f"/api/research/stream/{query_id}",
        created_at=active_queries[query_id]["created_at"],
    )


@app.get("/api/research/stream/{query_id}")
async def stream_results(query_id: str):
    """Stream real-time results for a query using Server-Sent Events"""

    if query_id not in active_queries:
        raise HTTPException(status_code=404, detail="Query not found")

    async def generate_events():
        """Generate SSE events for streaming results"""

        query_state = active_queries[query_id]

        # Initial connection event
        yield f"event: connected\ndata: {json.dumps({'query_id': query_id, 'timestamp': datetime.utcnow().isoformat()})}\n\n"

        # If query is already completed, send all results immediately
        if query_state["status"] == QueryStatus.COMPLETED:
            # Send final progress state
            progress_event = {
                "query_id": query_id,
                "status": query_state["status"].value,
                "progress": query_state["progress"],
                "timestamp": datetime.utcnow().isoformat(),
            }
            yield f"event: progress\ndata: {json.dumps(progress_event)}\n\n"

            # Send all available results
            for source, results in query_state["results"].items():
                if results and results.get("results"):
                    partial_event = {
                        "query_id": query_id,
                        "source": source,
                        "results": results["results"][:5],  # First 5 for preview
                        "total_found": results.get("total_found", 0),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    yield f"event: partial_result\ndata: {json.dumps(partial_event)}\n\n"

            # Send final completion event
            final_event = {
                "query_id": query_id,
                "status": "completed",
                "synthesis": query_state.get("synthesis"),
                "total_results": sum(
                    r.get("total_found", 0)
                    for r in query_state["results"].values()
                    if isinstance(r, dict)
                ),
                "timestamp": datetime.utcnow().isoformat(),
            }
            yield f"event: query_completed\ndata: {json.dumps(final_event)}\n\n"
            return

        # If query failed, send error immediately
        if query_state["status"] == QueryStatus.FAILED:
            error_event = {
                "query_id": query_id,
                "status": "failed",
                "error": query_state.get("error", "Unknown error"),
                "timestamp": datetime.utcnow().isoformat(),
            }
            yield f"event: query_failed\ndata: {json.dumps(error_event)}\n\n"
            return

        # For active queries, stream real-time updates
        last_update = time.time()
        max_wait_time = 30  # Maximum 30 seconds
        start_time = time.time()

        while query_state["status"] in [QueryStatus.INITIATED, QueryStatus.PROCESSING]:
            await asyncio.sleep(0.5)  # Check every 500ms

            # Timeout protection
            if time.time() - start_time > max_wait_time:
                timeout_event = {
                    "query_id": query_id,
                    "status": "timeout",
                    "error": "Query processing timeout",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                yield f"event: query_failed\ndata: {json.dumps(timeout_event)}\n\n"
                break

            current_time = time.time()

            # Send progress updates every second
            if current_time - last_update > 1.0:
                progress_event = {
                    "query_id": query_id,
                    "status": query_state["status"].value,
                    "progress": query_state["progress"],
                    "timestamp": datetime.utcnow().isoformat(),
                }
                yield f"event: progress\ndata: {json.dumps(progress_event)}\n\n"
                last_update = current_time

            # Send partial results when available
            for source, results in query_state["results"].items():
                if results and results.get("new_results"):
                    partial_event = {
                        "query_id": query_id,
                        "source": source,
                        "results": results["new_results"],
                        "total_found": results.get("total_found", 0),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    yield f"event: partial_result\ndata: {json.dumps(partial_event)}\n\n"

                    # Mark as sent
                    results["new_results"] = []

            # Check if query completed
            if query_state["status"] == QueryStatus.COMPLETED:
                break

        # Send final results for completed queries
        if query_state["status"] == QueryStatus.COMPLETED:
            final_event = {
                "query_id": query_id,
                "status": "completed",
                "synthesis": query_state.get("synthesis"),
                "total_results": sum(
                    r.get("total_found", 0)
                    for r in query_state["results"].values()
                    if isinstance(r, dict)
                ),
                "timestamp": datetime.utcnow().isoformat(),
            }
            yield f"event: query_completed\ndata: {json.dumps(final_event)}\n\n"

        # Send final error for failed queries
        elif query_state["status"] == QueryStatus.FAILED:
            error_event = {
                "query_id": query_id,
                "status": "failed",
                "error": query_state.get("error", "Unknown error"),
                "timestamp": datetime.utcnow().isoformat(),
            }
            yield f"event: query_failed\ndata: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.get("/api/research/query/{query_id}")
async def get_query_status(query_id: str):
    """Get current status and results for a query"""

    if query_id not in active_queries:
        raise HTTPException(status_code=404, detail="Query not found")

    query_state = active_queries[query_id]

    return {
        "query_id": query_id,
        "status": query_state["status"].value,
        "query": query_state["query"],
        "progress": query_state["progress"],
        "results": {
            source: _format_source_results(source, results)
            for source, results in query_state["results"].items()
        },
        "synthesis": query_state.get("synthesis"),
        "created_at": query_state["created_at"],
        "completed_at": query_state.get("completed_at"),
    }


@app.get("/api/research/synthesis/{query_id}", response_model=SynthesisResponse)
async def get_synthesis(query_id: str):
    """Get AI synthesis for a completed query"""

    if query_id not in active_queries:
        raise HTTPException(status_code=404, detail="Query not found")

    query_state = active_queries[query_id]

    if query_state["status"] != QueryStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Query not yet completed")

    synthesis = query_state.get("synthesis")
    if not synthesis:
        raise HTTPException(status_code=404, detail="Synthesis not available")

    return SynthesisResponse(**synthesis)


@app.get("/api/research/active-queries")
async def get_active_queries():
    """Get list of currently active queries for frontend polling"""

    # Return active and recent queries for the dashboard
    active_query_list = []

    for query_id, state in active_queries.items():
        active_query_list.append(
            {
                "query_id": query_id,
                "status": state["status"].value,
                "query": state["query"][:100],  # Truncate long queries
                "created_at": state["created_at"],
                "completed_at": state.get("completed_at"),
                "progress": state.get("progress", {}),
                "sources": list(state.get("results", {}).keys()),
                "total_results": sum(
                    r.get("total_found", 0)
                    for r in state.get("results", {}).values()
                    if isinstance(r, dict)
                )
                if state.get("results")
                else 0,
            }
        )

    return {
        "active_queries": active_query_list,
        "total_count": len(active_query_list),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/langgraph/visualization")
async def get_langgraph_visualization():
    """Get LangGraph workflow visualization for the frontend."""

    if not langgraph_orchestrator:
        return {
            "error": "LangGraph orchestrator not available",
            "fallback_mode": True,
            "nodes": [],
            "edges": [],
        }

    return langgraph_orchestrator.get_graph_visualization()


@app.get("/api/langgraph/status")
async def get_langgraph_status():
    """Get current status of LangGraph orchestrator."""

    if not langgraph_orchestrator:
        raise HTTPException(
            status_code=503, detail="LangGraph orchestrator not initialized"
        )

    return {
        "langgraph_enabled": True,
        "status": "operational",
        "graph_initialized": langgraph_orchestrator.compiled_graph is not None,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def process_query(query_id: str):
    """Background task to process a research query"""

    try:
        query_state = active_queries[query_id]
        query_state["status"] = QueryStatus.PROCESSING

        logger.info(f"Processing query {query_id}: {query_state['query']}")

        # Execute using LangGraph orchestration
        await process_query_with_langgraph(query_id)

        # Mark as completed
        query_state["status"] = QueryStatus.COMPLETED
        query_state["completed_at"] = datetime.utcnow().isoformat()

        logger.info(f"Query {query_id} completed successfully")

    except Exception as e:
        logger.error(f"Error processing query {query_id}: {str(e)}")
        active_queries[query_id]["status"] = QueryStatus.FAILED
        active_queries[query_id]["error"] = str(e)


async def process_pubmed_search(query_id: str):
    """Process PubMed search for a query"""

    try:
        query_state = active_queries[query_id]
        query_state["progress"]["pubmed"] = "processing"

        # Call Bio-MCP PubMed search
        results = await bio_mcp_client.pubmed_search(
            query=query_state["query"], max_results=query_state["max_results"]
        )

        # Store results
        query_state["results"]["pubmed"] = {
            "total_found": len(results.get("results", [])),
            "results": results.get("results", []),
            "new_results": results.get("results", [])[:5],  # First 5 for streaming
            "metadata": results.get("metadata", {}),
        }

        query_state["progress"]["pubmed"] = "completed"
        logger.info(
            f"PubMed search completed for query {query_id}: {len(results.get('results', []))} results"
        )

    except Exception as e:
        logger.error(f"PubMed search failed for query {query_id}: {str(e)}")
        active_queries[query_id]["progress"]["pubmed"] = "failed"


async def process_clinical_trials_search(query_id: str):
    """Process ClinicalTrials.gov search for a query"""

    try:
        query_state = active_queries[query_id]
        query_state["progress"]["clinical_trials"] = "processing"

        # Call Bio-MCP clinical trials search
        results = await bio_mcp_client.clinical_trials_search(
            query=query_state["query"], max_results=query_state["max_results"]
        )

        # Store results
        query_state["results"]["clinical_trials"] = {
            "total_found": len(results.get("studies", [])),
            "results": results.get("studies", []),
            "new_results": results.get("studies", [])[:5],  # First 5 for streaming
            "metadata": results.get("metadata", {}),
        }

        query_state["progress"]["clinical_trials"] = "completed"
        logger.info(
            f"Clinical trials search completed for query {query_id}: {len(results.get('studies', []))} results"
        )

    except Exception as e:
        logger.error(f"Clinical trials search failed for query {query_id}: {str(e)}")
        active_queries[query_id]["progress"]["clinical_trials"] = "failed"


async def process_rag_search(query_id: str):
    """Process RAG search for a query"""

    try:
        query_state = active_queries[query_id]
        query_state["progress"]["rag"] = "processing"

        # Call Bio-MCP RAG search
        results = await bio_mcp_client.rag_search(
            query=query_state["query"], max_results=query_state["max_results"]
        )

        # Store results
        query_state["results"]["rag"] = {
            "total_found": len(results.get("documents", [])),
            "results": results.get("documents", []),
            "new_results": results.get("documents", [])[:5],  # First 5 for streaming
            "metadata": results.get("metadata", {}),
        }

        query_state["progress"]["rag"] = "completed"
        logger.info(
            f"RAG search completed for query {query_id}: {len(results.get('documents', []))} results"
        )

    except Exception as e:
        logger.error(f"RAG search failed for query {query_id}: {str(e)}")
        active_queries[query_id]["progress"]["rag"] = "failed"


async def generate_synthesis(query_id: str):
    """Generate AI synthesis of query results"""

    try:
        query_state = active_queries[query_id]

        # Compile all results
        all_results = {}
        for source, results in query_state["results"].items():
            if results.get("results"):
                all_results[source] = results["results"]

        if not all_results:
            logger.warning(f"No results to synthesize for query {query_id}")
            return

        # Generate synthesis
        synthesis = await synthesis_service.synthesize_results(
            query=query_state["query"],
            results=all_results,
            options=query_state["analysis_options"],
        )

        query_state["synthesis"] = synthesis
        logger.info(f"Synthesis generated for query {query_id}")

    except Exception as e:
        logger.error(f"Synthesis generation failed for query {query_id}: {str(e)}")


async def process_query_with_langgraph(query_id: str):
    """Process query using LangGraph orchestrator with streaming updates."""

    query_state = active_queries[query_id]

    # Create streaming callback to update query state
    async def stream_callback(event_data):
        """Handle streaming updates from LangGraph orchestrator."""
        event_type = event_data.get("event")
        data = event_data.get("data", {})

        if event_type == "node_started":
            node_name = data.get("node")
            if node_name == "pubmed_search":
                query_state["progress"]["pubmed"] = "processing"
            elif node_name == "ctgov_search":
                query_state["progress"]["clinical_trials"] = "processing"
            elif node_name == "rag_search":
                query_state["progress"]["rag"] = "processing"

        elif event_type == "node_completed":
            node_name = data.get("node")
            if node_name == "pubmed_search":
                query_state["progress"]["pubmed"] = "completed"
            elif node_name == "ctgov_search":
                query_state["progress"]["clinical_trials"] = "completed"
            elif node_name == "rag_search":
                query_state["progress"]["rag"] = "completed"

        elif event_type == "source_failed":
            source = data.get("source")
            if source == "pubmed":
                query_state["progress"]["pubmed"] = "failed"
            elif source == "clinical_trials":
                query_state["progress"]["clinical_trials"] = "failed"
            elif source == "rag":
                query_state["progress"]["rag"] = "failed"

    # Execute using LangGraph orchestrator
    results = await langgraph_orchestrator.execute_research_query(
        query=query_state["query"],
        sources=query_state["sources"],
        options={
            "max_results_per_source": query_state["max_results"],
            "generate_synthesis": query_state["options"].include_synthesis,
        },
        stream_callback=stream_callback,
    )

    # Store results from LangGraph
    if "sources" in results:
        for source, data in results["sources"].items():
            if source in ["pubmed", "clinical_trials", "rag"]:
                # Convert to expected format
                if source == "pubmed" and "results" in data:
                    query_state["results"][source] = {
                        "total_found": len(data["results"]),
                        "results": data["results"],
                        "new_results": data["results"][:5],
                        "metadata": data.get("metadata", {}),
                    }
                elif source == "clinical_trials" and "studies" in data:
                    query_state["results"][source] = {
                        "total_found": len(data["studies"]),
                        "results": data["studies"],
                        "new_results": data["studies"][:5],
                        "metadata": data.get("metadata", {}),
                    }
                elif source == "rag" and "documents" in data:
                    query_state["results"][source] = {
                        "total_found": len(data["documents"]),
                        "results": data["documents"],
                        "new_results": data["documents"][:5],
                        "metadata": data.get("metadata", {}),
                    }

    # Store synthesis if available
    if "synthesis" in results:
        query_state["synthesis"] = results["synthesis"]


# Direct Bio-MCP methods removed - POC uses LangGraph orchestration only


def main():
    """Entry point for the POC backend server."""
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True, log_level="info")


if __name__ == "__main__":
    main()
