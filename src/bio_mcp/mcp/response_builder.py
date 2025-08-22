"""
MCP Response Builder utility for consistent JSON responses.

Provides standardized response formatting for all MCP tools to ensure
consistent API contracts and better programmatic usage.
"""

import json
import time
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Union

from mcp.types import TextContent


class MCPResponseBuilder:
    """Builder for standardized MCP tool responses."""
    
    def __init__(self, operation: str, version: str = "1.0"):
        self.operation = operation
        self.version = version
        self.start_time = time.time()
        
    def success(
        self,
        data: Any = None,
        format_type: str = "json",
        human_formatter: Optional[callable] = None
    ) -> List[TextContent]:
        """Build a successful response."""
        execution_time_ms = (time.time() - self.start_time) * 1000
        
        response = {
            "success": True,
            "operation": self.operation,
            "data": data,
            "metadata": {
                "execution_time_ms": round(execution_time_ms, 1),
                "timestamp": datetime.now(UTC).isoformat(),
                "version": self.version
            }
        }
        
        if format_type == "human" and human_formatter:
            # Return human-readable format
            human_text = human_formatter(response)
            return [TextContent(type="text", text=human_text)]
        else:
            # Return JSON format (default)
            json_text = json.dumps(response, indent=2, ensure_ascii=False)
            return [TextContent(type="text", text=f"```json\n{json_text}\n```")]
    
    def error(
        self,
        code: str,
        message: str,
        details: Any = None,
        format_type: str = "json"
    ) -> List[TextContent]:
        """Build an error response."""
        execution_time_ms = (time.time() - self.start_time) * 1000
        
        response = {
            "success": False,
            "operation": self.operation,
            "error": {
                "code": code,
                "message": message,
                "details": details
            },
            "metadata": {
                "execution_time_ms": round(execution_time_ms, 1),
                "timestamp": datetime.now(UTC).isoformat(),
                "version": self.version
            }
        }
        
        if format_type == "human":
            # Return human-readable error format
            error_text = f"❌ Error: {message}"
            if details:
                error_text += f"\n\nDetails: {details}"
            error_text += f"\n\nExecution time: {execution_time_ms:.1f}ms"
            return [TextContent(type="text", text=error_text)]
        else:
            # Return JSON format (default)
            json_text = json.dumps(response, indent=2, ensure_ascii=False)
            return [TextContent(type="text", text=f"```json\n{json_text}\n```")]


class ErrorCodes:
    """Standard error codes for MCP tools."""
    
    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    
    # System errors
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    WEAVIATE_ERROR = "WEAVIATE_ERROR"
    
    # Business logic errors
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    OPERATION_FAILED = "OPERATION_FAILED"
    
    # External service errors
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"


def get_format_preference(arguments: Dict[str, Any]) -> str:
    """Extract format preference from tool arguments."""
    return arguments.get("format", "json").lower()


def format_rag_search_human(response: Dict[str, Any]) -> str:
    """Format RAG search response for human consumption."""
    data = response["data"]
    metadata = response["metadata"]
    
    if data["total_results"] == 0:
        return f"""🔍 **Hybrid RAG Search Results**

**Query:** {data["query"]}
**Search Mode:** {data["search_mode"].title()}
**Results:** No documents found

Try different keywords, search modes ('hybrid', 'semantic', 'bm25'), or check if documents have been synced to the corpus.

Execution time: {metadata["execution_time_ms"]}ms"""

    # Format results with enhanced information
    results_text = []
    for i, doc in enumerate(data["results"], 1):
        # Enhanced score display
        score_text = f"Score: {doc['score']:.3f}"
        if "boosted_score" in doc and abs(doc["boosted_score"] - doc["score"]) > 0.001:
            boost_pct = (((doc["boosted_score"] / doc["score"]) - 1) * 100) if doc["score"] > 0 else 0
            score_text += f" → {doc['boosted_score']:.3f} (+{boost_pct:.1f}%)"

        # Add search mode context
        mode_indicator = {"hybrid": "🔀", "semantic": "🧠", "bm25": "🔎"}.get(data["search_mode"], "📄")

        doc_text = f"""**{i}. {doc["title"]}**
{mode_indicator} PMID: {doc["pmid"]} | {score_text}
📰 Journal: {doc["journal"]} | 📅 Date: {doc["publication_date"]}

{doc["content"]}

---"""
        results_text.append(doc_text)

    # Add search statistics
    mode_description = {
        "hybrid": f"Hybrid (BM25 + Vector)",
        "semantic": "Semantic (Vector Only)",
        "bm25": "Keyword (BM25 Only)",
    }.get(data["search_mode"], data["search_mode"].title())

    quality_note = "Quality boosting: ON" if data.get("quality_bias") else "Quality boosting: OFF"

    performance = data.get("performance", {})
    performance_info = ""
    if performance:
        total_ms = performance.get("total_time_ms", metadata["execution_time_ms"])
        target_ms = performance.get("target_time_ms", 1000)
        performance_status = "✅" if total_ms <= target_ms else "⚠️"
        performance_info = f"**{performance_status} Performance:** {total_ms:.1f}ms (target: {target_ms:.0f}ms)\n"

    response_text = f"""🔍 **Hybrid RAG Search Results**

**Query:** {data["query"]} | **Mode:** {mode_description}
**Found:** {data["total_results"]} documents | {quality_note}
{performance_info}
{chr(10).join(results_text)}"""

    return response_text


def format_rag_get_human(response: Dict[str, Any]) -> str:
    """Format RAG get response for human consumption."""
    data = response["data"]
    doc = data["document"]
    metadata = response["metadata"]
    
    return f"""📄 **Document Retrieved**

**Title:** {doc["title"]}
**PMID:** {doc["pmid"]}
**Journal:** {doc["journal"]}
**Publication Date:** {doc["publication_date"]}

**Authors:** {", ".join(doc.get("authors", []))}
**Publication Types:** {", ".join(doc.get("pub_types", []))}
**Keywords:** {", ".join(doc.get("keywords", []))}

**Quality Score:** {doc.get("quality", "N/A")}

**Abstract:**
{doc.get("abstract", "No abstract available.")}

**Vector Database UUID:** {doc["uuid"]}

Execution time: {metadata["execution_time_ms"]}ms"""