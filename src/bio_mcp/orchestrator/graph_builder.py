"""Enhanced graph builder with real node implementations."""

from langgraph.graph import END, StateGraph

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.nodes.llm_parse_node import create_llm_parse_node
from bio_mcp.orchestrator.nodes.router_node import create_router_node, routing_function
from bio_mcp.orchestrator.nodes.synthesizer_node import create_synthesizer_node
from bio_mcp.orchestrator.nodes.tool_nodes import create_pubmed_search_node
from bio_mcp.orchestrator.state import OrchestratorState

logger = get_logger(__name__)


def build_orchestrator_graph(config: OrchestratorConfig) -> StateGraph:
    """Build the complete orchestrator graph with real nodes."""

    # Create graph
    workflow = StateGraph(OrchestratorState)

    # Create nodes
    llm_parser = create_llm_parse_node(config)
    router = create_router_node(config)
    pubmed_search = create_pubmed_search_node(config)
    synthesizer = create_synthesizer_node(config)

    # Add nodes to graph
    workflow.add_node("llm_parse", llm_parser)
    workflow.add_node("router", router)
    workflow.add_node("pubmed_search", pubmed_search)
    workflow.add_node("synthesizer", synthesizer)

    # Set entry point
    workflow.set_entry_point("llm_parse")

    # Add sequential edges
    workflow.add_edge("llm_parse", "router")

    # Add conditional routing (simplified for M1 - just PubMed for now)
    workflow.add_conditional_edges(
        "router",
        routing_function,
        {
            "pubmed_search": "pubmed_search",
            # For M1, default other routes to pubmed_search as well
            "ctgov_search": "pubmed_search",
            "rag_search": "pubmed_search",
        },
    )

    # All tool nodes lead to synthesizer
    workflow.add_edge("pubmed_search", "synthesizer")

    # End after synthesis
    workflow.add_edge("synthesizer", END)

    logger.info("Built complete orchestrator graph with LLM-based parser")
    logger.info(f"Graph nodes: {list(workflow.nodes.keys())}")
    logger.info(f"Graph edges: {workflow.edges}")
    return workflow
