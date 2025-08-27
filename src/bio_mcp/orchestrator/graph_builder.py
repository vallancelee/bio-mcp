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
    nodes_to_create = [
        "llm_parse",
        "router",
        "pubmed_search",
        "ctgov_search",
        "rag_search",
        "synthesizer",
    ]
    node_instances = {}

    for node_name in nodes_to_create:
        try:
            factory = registry.get_factory(node_name)
            node_instances[node_name] = factory(config)
            workflow.add_node(node_name, node_instances[node_name])
            logger.debug(f"Added node: {node_name}")
        except ValueError as e:
            logger.warning(f"Node {node_name} not available in registry: {e}")
            # Skip nodes that aren't available (graceful degradation)
            continue

    # Set entry point
    workflow.set_entry_point("llm_parse")

    # Add sequential edges
    workflow.add_edge("llm_parse", "router")

    # Add conditional routing - now with real nodes (M2)
    # Import routing function only when needed
    from bio_mcp.orchestrator.nodes.router_node import routing_function

    # Build routing map based on available nodes
    routing_map = {}
    if "pubmed_search" in node_instances:
        routing_map["pubmed_search"] = "pubmed_search"
    if "ctgov_search" in node_instances:
        routing_map["ctgov_search"] = "ctgov_search"
    else:
        routing_map["ctgov_search"] = "pubmed_search"  # Fallback
    if "rag_search" in node_instances:
        routing_map["rag_search"] = "rag_search"
    else:
        routing_map["rag_search"] = "pubmed_search"  # Fallback

    workflow.add_conditional_edges("router", routing_function, routing_map)

    # All tool nodes lead to synthesizer
    for node_name in ["pubmed_search", "ctgov_search", "rag_search"]:
        if node_name in node_instances:
            workflow.add_edge(node_name, "synthesizer")

    # End after synthesis
    workflow.add_edge("synthesizer", END)

    logger.info("Built orchestrator graph using registry pattern")
    logger.info(f"Graph nodes: {list(workflow.nodes.keys())}")
    logger.info(f"Registered nodes: {registry.list_nodes()}")
    return workflow
