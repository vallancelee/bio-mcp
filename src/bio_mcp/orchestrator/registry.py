"""Node registry for orchestrator components (eliminates circular dependencies)."""

from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.interfaces import (
    BaseNodeRegistry,
    NodeFactory,
    NodeRegistration,
)

logger = get_logger(__name__)


class NodeRegistry(BaseNodeRegistry):
    """Registry for orchestrator nodes that supports dependency injection."""

    def __init__(self):
        self._nodes: dict[str, NodeRegistration] = {}
        self._initialized = False

    def register(self, registration: NodeRegistration) -> None:
        """Register a node with the registry."""
        if registration.name in self._nodes:
            logger.warning(
                f"Overriding existing node registration: {registration.name}"
            )

        self._nodes[registration.name] = registration
        logger.debug(
            f"Registered node: {registration.name} with dependencies: {registration.dependencies}"
        )

    def get_factory(self, name: str) -> NodeFactory:
        """Get factory function for a node."""
        if name not in self._nodes:
            raise ValueError(f"Node '{name}' not found in registry")

        return self._nodes[name].factory

    def list_nodes(self) -> list[str]:
        """List all registered node names."""
        return list(self._nodes.keys())

    def get_dependencies(self, name: str) -> list[str]:
        """Get dependencies for a node."""
        if name not in self._nodes:
            raise ValueError(f"Node '{name}' not found in registry")

        return self._nodes[name].dependencies.copy()

    def get_metadata(self, name: str) -> dict[str, Any]:
        """Get metadata for a node."""
        if name not in self._nodes:
            raise ValueError(f"Node '{name}' not found in registry")

        return self._nodes[name].metadata.copy()

    def validate_dependencies(self) -> bool:
        """Validate all registered nodes have their dependencies satisfied."""
        for name, registration in self._nodes.items():
            for dep in registration.dependencies:
                if dep not in self._nodes:
                    logger.error(f"Node '{name}' has unsatisfied dependency: '{dep}'")
                    return False

        return True

    def get_initialization_order(self) -> list[str]:
        """Get nodes in dependency order for initialization."""
        # Simple topological sort
        visited = set()
        temp_visited = set()
        result = []

        def visit(node_name: str):
            if node_name in temp_visited:
                raise ValueError(
                    f"Circular dependency detected involving node: {node_name}"
                )

            if node_name in visited:
                return

            temp_visited.add(node_name)

            # Visit dependencies first
            for dep in self.get_dependencies(node_name):
                visit(dep)

            temp_visited.remove(node_name)
            visited.add(node_name)
            result.append(node_name)

        for node_name in self._nodes.keys():
            if node_name not in visited:
                visit(node_name)

        return result


# Global registry instance
_registry = NodeRegistry()


def get_registry() -> NodeRegistry:
    """Get the global node registry instance."""
    return _registry


def register_node(
    name: str,
    factory: NodeFactory,
    dependencies: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Convenience function to register a node."""
    registration = NodeRegistration(name, factory, dependencies, metadata)
    _registry.register(registration)


def initialize_core_nodes():
    """Initialize core node registrations."""
    # Import factory functions only when needed to avoid circular deps
    from bio_mcp.orchestrator.nodes.llm_parse_node import create_llm_parse_node
    from bio_mcp.orchestrator.nodes.router_node import create_router_node
    from bio_mcp.orchestrator.nodes.synthesizer_node import create_synthesizer_node
    from bio_mcp.orchestrator.nodes.tool_nodes import create_pubmed_search_node

    # Register core nodes with dependencies
    register_node(
        name="llm_parse",
        factory=create_llm_parse_node,
        dependencies=[],
        metadata={"version": "v2", "type": "parser"},
    )

    register_node(
        name="router",
        factory=create_router_node,
        dependencies=["llm_parse"],
        metadata={"version": "v1", "type": "router"},
    )

    register_node(
        name="pubmed_search",
        factory=create_pubmed_search_node,
        dependencies=["router"],
        metadata={"version": "v1", "type": "tool", "source": "pubmed"},
    )

    register_node(
        name="synthesizer",
        factory=create_synthesizer_node,
        dependencies=["pubmed_search"],
        metadata={"version": "v1", "type": "synthesizer"},
    )

    logger.info(f"Initialized {len(_registry.list_nodes())} core nodes in registry")


def register_enhanced_nodes():
    """Register enhanced nodes when they become available."""
    try:
        from bio_mcp.orchestrator.nodes.enhanced_tool_nodes import (
            create_enhanced_ctgov_search_node,
            create_enhanced_pubmed_search_node,
            create_enhanced_rag_search_node,
        )

        register_node(
            name="enhanced_pubmed_search",
            factory=create_enhanced_pubmed_search_node,
            dependencies=["router"],
            metadata={
                "version": "v2",
                "type": "tool",
                "source": "pubmed",
                "enhanced": True,
            },
        )

        register_node(
            name="ctgov_search",
            factory=create_enhanced_ctgov_search_node,
            dependencies=["router"],
            metadata={"version": "v1", "type": "tool", "source": "clinicaltrials"},
        )

        register_node(
            name="rag_search",
            factory=create_enhanced_rag_search_node,
            dependencies=["router"],
            metadata={"version": "v1", "type": "tool", "source": "rag"},
        )

        logger.info("Registered enhanced nodes")
    except ImportError as e:
        logger.debug(f"Enhanced nodes not available: {e}")


def ensure_registry_initialized():
    """Ensure the registry is initialized with all available nodes."""
    if not _registry._initialized:
        initialize_core_nodes()
        register_enhanced_nodes()

        if not _registry.validate_dependencies():
            raise RuntimeError("Node registry has unsatisfied dependencies")

        _registry._initialized = True
        logger.info(f"Registry initialized with nodes: {_registry.list_nodes()}")
