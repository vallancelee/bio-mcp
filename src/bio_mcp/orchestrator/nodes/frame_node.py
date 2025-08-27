"""Frame parser node for LangGraph orchestrator."""

from datetime import UTC, datetime
from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.frame import FrameParser
from bio_mcp.orchestrator.state import FrameModel, OrchestratorState

logger = get_logger(__name__)


class FrameParserNode:
    """Node that parses natural language queries into structured frames."""

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.parser = FrameParser(config)

    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Parse query into frame structure."""
        start_time = datetime.now(UTC)
        query = state["query"]

        try:
            # Parse using existing frame parser
            frame_dict = self.parser.parse_frame(query)

            # Validate with Pydantic model
            frame = FrameModel(**frame_dict)

            # Calculate latency
            latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

            logger.info(
                "Frame parsed successfully",
                extra={
                    "query": query,
                    "intent": frame.intent,
                    "entities": frame.entities,
                    "latency_ms": latency_ms,
                },
            )

            # Update state
            return {
                "frame": frame.model_dump(),
                "node_path": state["node_path"] + ["parse_frame"],
                "latencies": {**state["latencies"], "parse_frame": latency_ms},
                "messages": state["messages"]
                + [{"role": "system", "content": f"Parsed intent: {frame.intent}"}],
            }

        except Exception as e:
            logger.error(
                "Frame parsing failed", extra={"query": query, "error": str(e)}
            )

            # Return error state
            return {
                "errors": state["errors"]
                + [
                    {
                        "node": "parse_frame",
                        "error": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ],
                "node_path": state["node_path"] + ["parse_frame"],
                "messages": state["messages"]
                + [{"role": "system", "content": f"Frame parsing error: {e!s}"}],
            }


def create_frame_parser_node(config: OrchestratorConfig):
    """Factory function to create frame parser node."""
    return FrameParserNode(config)
