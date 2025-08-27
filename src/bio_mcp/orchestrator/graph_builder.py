"""Enhanced graph builder using registry pattern (eliminates circular dependencies)."""

from langgraph.graph import END, StateGraph

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.registry import ensure_registry_initialized, get_registry
from bio_mcp.orchestrator.types import OrchestratorState

logger = get_logger(__name__)


def build_orchestrator_graph(config: OrchestratorConfig) -> StateGraph:
    """Build the complete orchestrator graph using registry pattern."""

    # Ensure registry is initialized
    ensure_registry_initialized()
    registry = get_registry()

    # Create graph
    workflow = StateGraph(OrchestratorState)

    # Get nodes from registry
    nodes_to_create = ["llm_parse", "router", "pubmed_search", "synthesizer"]
    node_instances = {}

    for node_name in nodes_to_create:
        try:
            factory = registry.get_factory(node_name)
            node_instances[node_name] = factory(config)
            workflow.add_node(node_name, node_instances[node_name])
            logger.debug(f"Added node: {node_name}")
        except ValueError as e:
            logger.error(f"Failed to create node {node_name}: {e}")
            raise

    # Set entry point
    workflow.set_entry_point("llm_parse")

    # Add sequential edges
    workflow.add_edge("llm_parse", "router")

    # Add conditional routing (simplified for M1 - just PubMed for now)
    # Import routing function only when needed
    from bio_mcp.orchestrator.nodes.router_node import routing_function

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

    logger.info("Built orchestrator graph using registry pattern")
    logger.info(f"Graph nodes: {list(workflow.nodes.keys())}")
    logger.info(f"Registered nodes: {registry.list_nodes()}")
    return workflow
