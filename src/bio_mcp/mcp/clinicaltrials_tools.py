"""
ClinicalTrials.gov tools for Bio-MCP server.
Phase 2: MCP Tools Integration

Implements MCP tools for:
- clinicaltrials.search: Search clinical trials with investment filtering
- clinicaltrials.get: Retrieve specific trial by NCT ID
- clinicaltrials.investment_search: Investment-focused trial search
- clinicaltrials.investment_summary: Investment analysis for trial portfolios
- clinicaltrials.sync: Sync trials to database
"""

import time
from dataclasses import dataclass
from typing import Any

from mcp.types import TextContent

from bio_mcp.config.logging_config import get_logger
from bio_mcp.mcp.response_builder import (
    ErrorCodes,
    MCPResponseBuilder,
    get_format_preference,
)
from bio_mcp.services.services import get_service_manager
from bio_mcp.sources.clinicaltrials.models import ClinicalTrialDocument

logger = get_logger(__name__)


@dataclass 
class ClinicalTrialsSearchResult:
    """Result from clinical trials search operation."""
    
    query: str
    total_results: int
    nct_ids: list[str]
    search_params: dict[str, Any]
    performance: dict[str, float] | None = None


@dataclass
class ClinicalTrialsGetResult:
    """Result from clinical trial retrieval."""
    
    nct_id: str
    found: bool
    document: ClinicalTrialDocument | None = None


@dataclass
class InvestmentSearchResult:
    """Result from investment-focused search."""
    
    query: str
    min_investment_score: float
    total_candidates: int
    investment_relevant: int
    nct_ids: list[str]
    performance: dict[str, float] | None = None


async def handle_clinicaltrials_search(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle clinicaltrials.search tool."""
    try:
        start_time = time.time()
        
        # Extract parameters
        query = arguments.get("query", "")
        condition = arguments.get("condition")
        intervention = arguments.get("intervention") 
        phase = arguments.get("phase")
        status = arguments.get("status")
        sponsor_class = arguments.get("sponsor_class")
        limit = arguments.get("limit", 50)
        
        logger.info(f"ClinicalTrials search: query='{query}', limit={limit}")
        
        # Get service
        service_manager = get_service_manager()
        ct_service = await service_manager.get_clinicaltrials_service()
        
        # Build search parameters
        search_params: dict[str, Any] = {}
        if condition:
            search_params["condition"] = condition
        if intervention:
            search_params["intervention"] = intervention
        if phase:
            search_params["phase"] = phase
        if status:
            search_params["status"] = status
        if sponsor_class:
            search_params["sponsor_class"] = sponsor_class
        if limit:
            search_params["limit"] = limit
            
        # Perform search
        nct_ids = await ct_service.search(query, **search_params)
        
        # Performance metrics
        elapsed_time = time.time() - start_time
        performance = {
            "search_time_ms": elapsed_time * 1000,
            "results_per_second": len(nct_ids) / elapsed_time if elapsed_time > 0 else 0,
        }
        
        # Create result
        result = ClinicalTrialsSearchResult(
            query=query,
            total_results=len(nct_ids),
            nct_ids=nct_ids,
            search_params=search_params,
            performance=performance,
        )
        
        logger.info(f"ClinicalTrials search completed: {len(nct_ids)} results in {elapsed_time:.2f}s")
        
        return format_clinicaltrials_search_response(result)
        
    except Exception as e:
        logger.error(f"ClinicalTrials search failed: {e}")
        builder = MCPResponseBuilder("clinicaltrials.search")
        return builder.error(
            ErrorCodes.SEARCH_FAILED, 
            f"ClinicalTrials search failed: {e!s}"
        )


async def handle_clinicaltrials_get(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle clinicaltrials.get tool."""
    try:
        nct_id = arguments.get("nct_id")
        if not nct_id:
            builder = MCPResponseBuilder("clinicaltrials.get")
            return builder.error(
                ErrorCodes.INVALID_REQUEST,
                "nct_id is required"
            )
            
        logger.info(f"Retrieving clinical trial: {nct_id}")
        
        # Get service
        service_manager = get_service_manager()
        ct_service = await service_manager.get_clinicaltrials_service()
        
        # Get document
        try:
            document = await ct_service.get_document(nct_id)
            found = True
        except ValueError:
            # Trial not found
            document = None
            found = False
            
        result = ClinicalTrialsGetResult(
            nct_id=nct_id,
            found=found, 
            document=document,
        )
        
        logger.info(f"Clinical trial retrieval: {nct_id} found={found}")
        
        return format_clinicaltrials_get_response(result)
        
    except Exception as e:
        logger.error(f"ClinicalTrials get failed: {e}")
        builder = MCPResponseBuilder("clinicaltrials.get")
        return builder.error(
            ErrorCodes.RETRIEVAL_FAILED,
            f"ClinicalTrials get failed: {e!s}"
        )


async def handle_clinicaltrials_investment_search(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle clinicaltrials.investment_search tool."""
    try:
        start_time = time.time()
        
        query = arguments.get("query", "")
        min_investment_score = arguments.get("min_investment_score", 0.5)
        limit = arguments.get("limit", 25)
        
        logger.info(f"Investment search: query='{query}', min_score={min_investment_score}")
        
        # Get service
        service_manager = get_service_manager()
        ct_service = await service_manager.get_clinicaltrials_service()
        
        # Perform investment-focused search
        nct_ids = await ct_service.search_investment_relevant(
            query=query,
            min_investment_score=min_investment_score,
            limit=limit,
        )
        
        # Calculate metrics (we'd need to modify service to return more details)
        elapsed_time = time.time() - start_time
        performance = {
            "search_time_ms": elapsed_time * 1000,
        }
        
        result = InvestmentSearchResult(
            query=query,
            min_investment_score=min_investment_score,
            total_candidates=0,  # Would need service modification to get this
            investment_relevant=len(nct_ids),
            nct_ids=nct_ids,
            performance=performance,
        )
        
        logger.info(f"Investment search completed: {len(nct_ids)} relevant trials")
        
        return format_investment_search_response(result)
        
    except Exception as e:
        logger.error(f"Investment search failed: {e}")
        builder = MCPResponseBuilder("clinicaltrials.investment_search")
        return builder.error(
            ErrorCodes.SEARCH_FAILED,
            f"Investment search failed: {e!s}"
        )


async def handle_clinicaltrials_investment_summary(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle clinicaltrials.investment_summary tool."""
    try:
        nct_ids = arguments.get("nct_ids", [])
        if not nct_ids:
            builder = MCPResponseBuilder("clinicaltrials.investment_summary")
            return builder.error(
                ErrorCodes.INVALID_REQUEST,
                "nct_ids list is required"
            )
            
        logger.info(f"Generating investment summary for {len(nct_ids)} trials")
        
        # Get service
        service_manager = get_service_manager()
        ct_service = await service_manager.get_clinicaltrials_service()
        
        # Get investment summary
        summary = await ct_service.get_investment_summary(nct_ids)
        
        logger.info("Investment summary generated successfully")
        
        return format_investment_summary_response(summary)
        
    except Exception as e:
        logger.error(f"Investment summary failed: {e}")
        builder = MCPResponseBuilder("clinicaltrials.investment_summary")
        return builder.error(
            ErrorCodes.ANALYSIS_FAILED,
            f"Investment summary failed: {e!s}"
        )


async def handle_clinicaltrials_sync(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle clinicaltrials.sync tool."""
    try:
        query = arguments.get("query")
        query_key = arguments.get("query_key") 
        limit = arguments.get("limit", 100)
        
        if not query or not query_key:
            builder = MCPResponseBuilder("clinicaltrials.sync")
            return builder.error(
                ErrorCodes.INVALID_REQUEST,
                "query and query_key are required"
            )
            
        logger.info(f"Syncing trials: query='{query}', key='{query_key}', limit={limit}")
        
        # Get service
        service_manager = get_service_manager()
        ct_service = await service_manager.get_clinicaltrials_service()
        
        # Perform sync
        result = await ct_service.sync_documents(query, query_key, limit)
        
        logger.info("ClinicalTrials sync completed successfully")
        
        return format_sync_response(result)
        
    except Exception as e:
        logger.error(f"ClinicalTrials sync failed: {e}")
        builder = MCPResponseBuilder("clinicaltrials.sync")
        return builder.error(
            ErrorCodes.SYNC_FAILED,
            f"ClinicalTrials sync failed: {e!s}"
        )


def format_clinicaltrials_search_response(result: ClinicalTrialsSearchResult) -> list[TextContent]:
    """Format clinical trials search response for human consumption."""
    format_pref = get_format_preference({})
    
    if format_pref == "human":
        # Human-readable format
        lines = [
            "🔬 **ClinicalTrials.gov Search Results**",
            "",
            f"**Query:** {result.query}",
            f"**Found:** {result.total_results} clinical trials",
        ]
        
        if result.search_params:
            lines.append("")
            lines.append("**Search Parameters:**")
            for key, value in result.search_params.items():
                if key != "limit":
                    lines.append(f"- {key.replace('_', ' ').title()}: {value}")
        
        if result.performance:
            search_time = result.performance.get("search_time_ms", 0)
            lines.append(f"**Search time:** {search_time:.1f}ms")
        
        if result.nct_ids:
            lines.append("")
            lines.append("**NCT IDs:**")
            for nct_id in result.nct_ids[:10]:  # Limit display
                lines.append(f"- {nct_id}")
            
            if len(result.nct_ids) > 10:
                lines.append(f"- ... and {len(result.nct_ids) - 10} more")
        
        return [TextContent(type="text", text="\n".join(lines))]
    
    else:
        # JSON format
        response_data = {
            "query": result.query,
            "total_results": result.total_results,
            "nct_ids": result.nct_ids,
            "search_params": result.search_params,
            "performance": result.performance,
        }
        return MCPResponseBuilder.json_response(response_data)


def format_clinicaltrials_get_response(result: ClinicalTrialsGetResult) -> list[TextContent]:
    """Format clinical trial get response for human consumption."""
    format_pref = get_format_preference({})
    
    if not result.found:
        builder = MCPResponseBuilder("clinicaltrials.get")
        return builder.error(
            ErrorCodes.NOT_FOUND,
            f"Clinical trial {result.nct_id} not found"
        )
    
    doc = result.document
    if not doc:
        builder = MCPResponseBuilder("clinicaltrials.get")
        return builder.error(
            ErrorCodes.RETRIEVAL_FAILED,
            f"Failed to retrieve trial data for {result.nct_id}"
        )
    
    if format_pref == "human":
        lines = [
            f"🔬 **Clinical Trial: {doc.nct_id}**",
            "",
            f"**Title:** {doc.get_display_title()}",
        ]
        
        if doc.phase:
            lines.append(f"**Phase:** {doc.phase}")
        if doc.status:
            lines.append(f"**Status:** {doc.status}")
        if doc.sponsor_name:
            lines.append(f"**Sponsor:** {doc.sponsor_name} ({doc.sponsor_class})")
        if doc.enrollment_count:
            lines.append(f"**Enrollment:** {doc.enrollment_count} participants")
        
        lines.append(f"**Investment Score:** {doc.investment_relevance_score:.2f}")
        
        if doc.conditions:
            lines.append(f"**Conditions:** {', '.join(doc.conditions[:3])}")
        if doc.interventions:
            lines.append(f"**Interventions:** {', '.join(doc.interventions[:3])}")
            
        if doc.brief_summary:
            lines.append("")
            lines.append("**Summary:**")
            lines.append(doc.brief_summary[:500] + "..." if len(doc.brief_summary) > 500 else doc.brief_summary)
        
        return [TextContent(type="text", text="\n".join(lines))]
    
    else:
        # JSON format - return summary dict
        return MCPResponseBuilder.json_response(doc.get_summary_for_display())


def format_investment_search_response(result: InvestmentSearchResult) -> list[TextContent]:
    """Format investment search response."""
    format_pref = get_format_preference({})
    
    if format_pref == "human":
        lines = [
            "💰 **Investment-Relevant Clinical Trials**",
            "",
            f"**Query:** {result.query or '(investment-focused search)'}",
            f"**Min Investment Score:** {result.min_investment_score}",
            f"**Found:** {result.investment_relevant} investment-relevant trials",
        ]
        
        if result.performance:
            search_time = result.performance.get("search_time_ms", 0)
            lines.append(f"**Search time:** {search_time:.1f}ms")
        
        if result.nct_ids:
            lines.append("")
            lines.append("**High-Value Trials:**")
            for nct_id in result.nct_ids:
                lines.append(f"- {nct_id}")
        
        return [TextContent(type="text", text="\n".join(lines))]
    
    else:
        response_data = {
            "query": result.query,
            "min_investment_score": result.min_investment_score,
            "investment_relevant": result.investment_relevant,
            "nct_ids": result.nct_ids,
            "performance": result.performance,
        }
        return MCPResponseBuilder.json_response(response_data)


def format_investment_summary_response(summary: dict[str, Any]) -> list[TextContent]:
    """Format investment summary response."""
    format_pref = get_format_preference({})
    
    if format_pref == "human":
        lines = [
            "📊 **Investment Analysis Summary**",
            "",
            f"**Total Trials:** {summary.get('total_trials', 0)}",
            f"**Investment Relevant:** {summary.get('investment_relevant', 0)} ({summary.get('investment_percentage', 0):.1f}%)",
            f"**Average Investment Score:** {summary.get('avg_investment_score', 0):.2f}",
        ]
        
        # Phase distribution
        phase_dist = summary.get("phase_distribution", {})
        if phase_dist:
            lines.append("")
            lines.append("**Phase Distribution:**")
            for phase, count in phase_dist.items():
                lines.append(f"- {phase}: {count}")
        
        # Sponsor distribution  
        sponsor_dist = summary.get("sponsor_distribution", {})
        if sponsor_dist:
            lines.append("")
            lines.append("**Sponsor Distribution:**")
            for sponsor, count in sponsor_dist.items():
                lines.append(f"- {sponsor}: {count}")
        
        # Top conditions
        top_conditions = summary.get("top_conditions", [])
        if top_conditions:
            lines.append("")
            lines.append("**Top Conditions:**")
            for item in top_conditions:
                lines.append(f"- {item['condition']}: {item['count']} trials")
        
        # High value trials
        high_value = summary.get("high_value_trials", [])
        if high_value:
            lines.append("")
            lines.append("**Top Investment Opportunities:**")
            for trial in high_value:
                lines.append(f"- **{trial['nct_id']}** (Score: {trial['investment_score']}) - {trial['title'][:60]}...")
        
        return [TextContent(type="text", text="\n".join(lines))]
    
    else:
        return MCPResponseBuilder.json_response(summary)


def format_sync_response(result: dict[str, Any]) -> list[TextContent]:
    """Format sync response."""
    format_pref = get_format_preference({})
    
    if format_pref == "human":
        lines = [
            "🔄 **ClinicalTrials.gov Sync Results**",
            "",
        ]
        
        if result.get("success"):
            synced = result.get("synced", 0)
            skipped = result.get("skipped", 0)
            investment_count = result.get("investment_relevant_count", 0)
            avg_score = result.get("avg_investment_score", 0.0)
            
            lines.extend([
                "**Status:** ✅ Success",
                f"**Synced:** {synced} trials",
                f"**Skipped:** {skipped} (already in database)",
                f"**Investment Relevant:** {investment_count}",
                f"**Average Investment Score:** {avg_score:.2f}",
            ])
            
            if "watermark_updated" in result:
                lines.append(f"**Watermark Updated:** {result['watermark_updated']}")
        else:
            lines.extend([
                "**Status:** ❌ Failed", 
                f"**Error:** {result.get('error', 'Unknown error')}",
            ])
        
        return [TextContent(type="text", text="\n".join(lines))]
    
    else:
        return MCPResponseBuilder.json_response(result)