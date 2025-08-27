# Circular Dependency Avoidance Pattern for LangGraph

**⚠️ CRITICAL REFERENCE - USE THIS PATTERN TO AVOID CIRCULAR DEPENDENCIES**

## The Problem
LangGraph implementations commonly suffer from circular dependencies because:
- Nodes import state types
- State management imports node definitions  
- Graph builders import both nodes and state
- Configuration hubs are imported by everything

## The Solution: Layered Architecture + Node Registry

### Layer Structure (STRICT DEPENDENCY FLOW)
```
Layer 1: Pure Types (no dependencies)
  ↓
Layer 2: Abstract Interfaces (types only)
  ↓  
Layer 3: Node Registry (types + interfaces)
  ↓
Layer 4: Node Implementations (types + interfaces)
  ↓
Layer 5: Graph Builder (registry only)
```

## Implementation Pattern

### 1. **Pure Types Module** (`types.py`)
```python
# NO IMPLEMENTATION DEPENDENCIES - ONLY TYPES
from typing import TypedDict, Callable
from pydantic import BaseModel
from langgraph.graph.message import add_messages

class OrchestratorState(TypedDict):
    # All state fields...
    pass

class NodeResult(BaseModel):
    # Result schema...
    pass

# Type aliases
NodeFunction = Callable[[OrchestratorState], dict[str, Any]]
ConfigDict = dict[str, Any]
```

### 2. **Abstract Interfaces** (`interfaces.py`) 
```python
# PROTOCOLS AND ABSTRACT BASE CLASSES
from abc import ABC, abstractmethod
from typing import Protocol
from .types import OrchestratorState, NodeResult, ConfigDict

class BaseNode(Protocol):
    async def __call__(self, state: OrchestratorState) -> dict[str, Any]: ...

class NodeFactory(Protocol):
    def __call__(self, config: ConfigDict) -> BaseNode: ...

class BaseNodeRegistry(Protocol):
    def register(self, name: str, factory: NodeFactory) -> None: ...
    def get_factory(self, name: str) -> NodeFactory: ...
```

### 3. **Node Registry** (`registry.py`) - **THE KEY COMPONENT**
```python
# DEPENDENCY INJECTION REGISTRY
from .interfaces import NodeFactory, BaseNodeRegistry
from .types import ConfigDict

class NodeRegistry(BaseNodeRegistry):
    def __init__(self):
        self._nodes: dict[str, NodeFactory] = {}
    
    def register(self, name: str, factory: NodeFactory) -> None:
        self._nodes[name] = factory
    
    def get_factory(self, name: str) -> NodeFactory:
        return self._nodes[name]
    
    def validate_dependencies(self) -> bool:
        # Dependency validation logic
        pass

# GLOBAL REGISTRY INSTANCE
_registry = NodeRegistry()

def get_registry() -> NodeRegistry:
    return _registry

def initialize_nodes():
    # IMPORT ONLY WHEN NEEDED (runtime imports)
    from .nodes.parser import create_parser_node
    from .nodes.router import create_router_node
    
    _registry.register("parser", create_parser_node)
    _registry.register("router", create_router_node)
```

### 4. **Node Implementations** 
```python
# IMPORT FROM TYPES ONLY
from ..types import OrchestratorState, ConfigDict
from ..interfaces import BaseNode

class ParserNode(BaseNode):
    def __init__(self, config: ConfigDict):
        self.config = config
    
    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        # Implementation...
        pass

def create_parser_node(config: ConfigDict) -> BaseNode:
    return ParserNode(config)
```

### 5. **Graph Builder** (Uses Registry Only)
```python
# NO DIRECT NODE IMPORTS - USE REGISTRY
from langgraph.graph import StateGraph, END
from .registry import ensure_registry_initialized, get_registry
from .types import OrchestratorState, ConfigDict

def build_graph(config: ConfigDict) -> StateGraph:
    ensure_registry_initialized()
    registry = get_registry()
    
    workflow = StateGraph(OrchestratorState)
    
    # Get nodes from registry (no imports!)
    parser = registry.get_factory("parser")(config)
    router = registry.get_factory("router")(config)
    
    workflow.add_node("parser", parser)
    workflow.add_node("router", router)
    
    # Add edges...
    return workflow
```

## Key Rules to Remember

### ✅ DO:
1. **Layer 1 (types.py)**: Only type definitions, no implementations
2. **Layer 2 (interfaces.py)**: Only protocols/ABC, import from types only
3. **Layer 3 (registry.py)**: Dependency injection, lazy imports in functions
4. **Layer 4 (nodes/)**: Import from types + interfaces only
5. **Layer 5 (graph_builder.py)**: Use registry, no direct node imports
6. **Use runtime imports**: Import in functions when needed, not at module level
7. **Validate dependencies**: Use registry to check dependency satisfaction

### ❌ DON'T:
1. **Never import nodes directly in graph builders**
2. **Never import implementation from types modules**  
3. **Never import config in types modules**
4. **Never create circular imports between layers**
5. **Never import at module level if it creates cycles**

## Testing Pattern
```python
# Test imports individually to catch circular deps early
def test_no_circular_dependencies():
    # Test each layer can import independently
    from .types import OrchestratorState  # ✅ 
    from .interfaces import BaseNode       # ✅
    from .registry import get_registry     # ✅
    from .nodes.parser import ParserNode   # ✅
    from .graph_builder import build_graph # ✅
```

## Benefits Achieved

1. **🚫 No Circular Dependencies**: Clean unidirectional flow
2. **🧪 Better Testability**: Each layer testable in isolation
3. **🔧 Maintainability**: Clear separation of concerns  
4. **📈 Extensibility**: Easy to add nodes via registry
5. **✅ Dependency Validation**: Runtime checks for missing deps
6. **🏗️ Clean Architecture**: Follows SOLID principles

## When to Use This Pattern

- ✅ LangGraph implementations with multiple nodes
- ✅ Complex systems with many interdependent components
- ✅ When you see "circular import" errors
- ✅ When testing becomes difficult due to import issues
- ✅ When you need dependency injection

## Remember This Pattern!
**The Node Registry is the key component that makes this work** - it provides dependency injection that breaks circular dependencies while maintaining clean, extensible code.

---
*Use this pattern in any complex system to avoid circular dependency hell!*