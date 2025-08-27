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
            "results_per_second": len(nct_ids) / elapsed_time
            if elapsed_time > 0
            else 0,
        }

        # Create result
        result = ClinicalTrialsSearchResult(
            query=query,
            total_results=len(nct_ids),
            nct_ids=nct_ids,
            search_params=search_params,
            performance=performance,
        )

        logger.info(
            f"ClinicalTrials search completed: {len(nct_ids)} results in {elapsed_time:.2f}s"
        )

        return format_clinicaltrials_search_response(result)

    except Exception as e:
        logger.error(f"ClinicalTrials search failed: {e}")
        builder = MCPResponseBuilder("clinicaltrials.search")
        return builder.error(
            ErrorCodes.SEARCH_FAILED, f"ClinicalTrials search failed: {e!s}"
        )


async def handle_clinicaltrials_get(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle clinicaltrials.get tool."""
    try:
        nct_id = arguments.get("nct_id")
        if not nct_id:
            builder = MCPResponseBuilder("clinicaltrials.get")
            return builder.error(ErrorCodes.INVALID_REQUEST, "nct_id is required")

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
            ErrorCodes.RETRIEVAL_FAILED, f"ClinicalTrials get failed: {e!s}"
        )


async def handle_clinicaltrials_investment_search(
    arguments: dict[str, Any],
) -> list[TextContent]:
    """Handle clinicaltrials.investment_search tool."""
    try:
        start_time = time.time()

        query = arguments.get("query", "")
        min_investment_score = arguments.get("min_investment_score", 0.5)
        limit = arguments.get("limit", 25)

        logger.info(
            f"Investment search: query='{query}', min_score={min_investment_score}"
        )

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
            ErrorCodes.SEARCH_FAILED, f"Investment search failed: {e!s}"
        )


async def handle_clinicaltrials_investment_summary(
    arguments: dict[str, Any],
) -> list[TextContent]:
    """Handle clinicaltrials.investment_summary tool."""
    try:
        nct_ids = arguments.get("nct_ids", [])
        if not nct_ids:
            builder = MCPResponseBuilder("clinicaltrials.investment_summary")
            return builder.error(ErrorCodes.INVALID_REQUEST, "nct_ids list is required")

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
            ErrorCodes.ANALYSIS_FAILED, f"Investment summary failed: {e!s}"
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
                ErrorCodes.INVALID_REQUEST, "query and query_key are required"
            )

        logger.info(
            f"Syncing trials: query='{query}', key='{query_key}', limit={limit}"
        )

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
            ErrorCodes.SYNC_FAILED, f"ClinicalTrials sync failed: {e!s}"
        )


def format_clinicaltrials_search_response(
    result: ClinicalTrialsSearchResult,
) -> list[TextContent]:
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


def format_clinicaltrials_get_response(
    result: ClinicalTrialsGetResult,
) -> list[TextContent]:
    """Format clinical trial get response for human consumption."""
    format_pref = get_format_preference({})

    if not result.found:
        builder = MCPResponseBuilder("clinicaltrials.get")
        return builder.error(
            ErrorCodes.NOT_FOUND, f"Clinical trial {result.nct_id} not found"
        )

    doc = result.document
    if not doc:
        builder = MCPResponseBuilder("clinicaltrials.get")
        return builder.error(
            ErrorCodes.RETRIEVAL_FAILED,
            f"Failed to retrieve trial data for {result.nct_id}",
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
            lines.append(
                doc.brief_summary[:500] + "..."
                if len(doc.brief_summary) > 500
                else doc.brief_summary
            )

        return [TextContent(type="text", text="\n".join(lines))]

    else:
        # JSON format - return summary dict
        return MCPResponseBuilder.json_response(doc.get_summary_for_display())


def format_investment_search_response(
    result: InvestmentSearchResult,
) -> list[TextContent]:
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
                lines.append(
                    f"- **{trial['nct_id']}** (Score: {trial['investment_score']}) - {trial['title'][:60]}..."
                )

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

            lines.extend(
                [
                    "**Status:** ✅ Success",
                    f"**Synced:** {synced} trials",
                    f"**Skipped:** {skipped} (already in database)",
                    f"**Investment Relevant:** {investment_count}",
                    f"**Average Investment Score:** {avg_score:.2f}",
                ]
            )

            if "watermark_updated" in result:
                lines.append(f"**Watermark Updated:** {result['watermark_updated']}")
        else:
            lines.extend(
                [
                    "**Status:** ❌ Failed",
                    f"**Error:** {result.get('error', 'Unknown error')}",
                ]
            )

        return [TextContent(type="text", text="\n".join(lines))]

    else:
        return MCPResponseBuilder.json_response(result)


@dataclass
class IncrementalSyncResult:
    """Result from incremental sync operation."""

    query_key: str
    synced: int
    new: int
    updated: int
    quality_metrics: dict[str, Any]
    performance: dict[str, float]
    success: bool
    watermark_updated: str | None = None
    error: str | None = None


async def handle_clinicaltrials_sync_incremental(
    arguments: dict[str, Any],
) -> list[TextContent]:
    """Handle clinicaltrials.sync.incremental tool."""
    try:
        start_time = time.time()

        # Extract required parameters
        query_key = arguments.get("query_key")
        if not query_key:
            builder = MCPResponseBuilder("clinicaltrials.sync.incremental")
            return builder.error(
                ErrorCodes.INVALID_REQUEST,
                "query_key is required for checkpoint tracking",
            )

        # Extract optional parameters
        query = arguments.get("query", "")
        limit = arguments.get("limit", 100)
        batch_size = arguments.get("batch_size", 50)
        min_quality_score = arguments.get("min_quality_score", 0.5)

        # Validate parameters
        if limit <= 0 or limit > 1000:
            builder = MCPResponseBuilder("clinicaltrials.sync.incremental")
            return builder.error(
                ErrorCodes.INVALID_REQUEST, "limit must be between 1 and 1000"
            )

        if batch_size <= 0 or batch_size > 200:
            builder = MCPResponseBuilder("clinicaltrials.sync.incremental")
            return builder.error(
                ErrorCodes.INVALID_REQUEST, "batch_size must be between 1 and 200"
            )

        if not (0.0 <= min_quality_score <= 1.0):
            builder = MCPResponseBuilder("clinicaltrials.sync.incremental")
            return builder.error(
                ErrorCodes.INVALID_REQUEST,
                "min_quality_score must be between 0.0 and 1.0",
            )

        logger.info(
            f"Starting incremental sync: query_key='{query_key}', limit={limit}"
        )

        # Get service
        service_manager = get_service_manager()
        ct_service = await service_manager.get_clinicaltrials_service()

        # Get sync strategy from service
        sync_strategy = ct_service.sync_strategy
        if not sync_strategy:
            builder = MCPResponseBuilder("clinicaltrials.sync.incremental")
            return builder.error(
                ErrorCodes.SERVICE_UNAVAILABLE,
                "ClinicalTrials sync strategy not available",
            )

        # Perform incremental sync with quality filtering
        if min_quality_score > 0.0:
            sync_result = await sync_strategy.sync_with_quality_filtering(
                query=query,
                query_key=query_key,
                limit=limit,
                min_quality_score=min_quality_score,
                batch_size=batch_size,
            )
        else:
            sync_result = await sync_strategy.sync_incremental(
                query=query, query_key=query_key, limit=limit, batch_size=batch_size
            )

        # Extract performance metrics
        total_time = time.time() - start_time
        performance = sync_result.get("performance", {})
        performance["total_tool_time_seconds"] = total_time

        # Create structured result
        result = IncrementalSyncResult(
            query_key=query_key,
            synced=sync_result.get("synced", 0),
            new=sync_result.get("new", 0),
            updated=sync_result.get("updated", 0),
            quality_metrics=sync_result.get("quality_metrics", {}),
            performance=performance,
            success=sync_result.get("success", False),
            watermark_updated=sync_result.get("watermark_updated"),
            error=sync_result.get("error"),
        )

        logger.info(
            f"Incremental sync completed: {result.synced} trials synced "
            f"in {total_time:.2f}s (success: {result.success})"
        )

        return format_incremental_sync_response(result, sync_result)

    except Exception as e:
        logger.error(f"Incremental sync failed: {e}")
        builder = MCPResponseBuilder("clinicaltrials.sync.incremental")
        return builder.error(ErrorCodes.SYNC_FAILED, f"Incremental sync failed: {e!s}")


async def handle_clinicaltrials_quality_calculate(
    arguments: dict[str, Any],
) -> list[TextContent]:
    """Handle clinicaltrials.quality.calculate tool for bulk quality scoring."""
    try:
        # Extract parameters
        nct_ids = arguments.get("nct_ids", [])
        if not nct_ids:
            builder = MCPResponseBuilder("clinicaltrials.quality.calculate")
            return builder.error(
                ErrorCodes.INVALID_REQUEST, "nct_ids array is required"
            )

        if len(nct_ids) > 100:
            builder = MCPResponseBuilder("clinicaltrials.quality.calculate")
            return builder.error(
                ErrorCodes.INVALID_REQUEST, "Maximum 100 NCT IDs allowed per request"
            )

        logger.info(f"Calculating quality scores for {len(nct_ids)} trials")

        # Get service
        service_manager = get_service_manager()
        ct_service = await service_manager.get_clinicaltrials_service()

        # Get documents and calculate quality scores
        quality_results = []
        total_processed = 0
        total_errors = 0

        for nct_id in nct_ids:
            try:
                document = await ct_service.get_document(nct_id)
                if document:
                    # Quality score is already calculated in the document model
                    quality_results.append(
                        {
                            "nct_id": nct_id,
                            "quality_score": document.investment_relevance_score,
                            "phase": document.phase,
                            "sponsor_class": document.sponsor_class,
                            "enrollment_count": document.enrollment_count,
                            "investment_relevant": document.investment_relevance_score
                            >= 0.6,
                        }
                    )
                    total_processed += 1
                else:
                    quality_results.append(
                        {
                            "nct_id": nct_id,
                            "error": "Trial not found",
                        }
                    )
                    total_errors += 1
            except Exception as e:
                quality_results.append(
                    {
                        "nct_id": nct_id,
                        "error": str(e),
                    }
                )
                total_errors += 1

        # Calculate aggregate metrics
        scores = [r["quality_score"] for r in quality_results if "quality_score" in r]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        high_quality_count = sum(1 for score in scores if score >= 0.7)
        investment_relevant_count = sum(1 for score in scores if score >= 0.6)

        result = {
            "total_requested": len(nct_ids),
            "total_processed": total_processed,
            "total_errors": total_errors,
            "avg_quality_score": avg_score,
            "high_quality_count": high_quality_count,
            "investment_relevant_count": investment_relevant_count,
            "quality_results": quality_results,
        }

        logger.info(
            f"Quality calculation completed: {total_processed} processed, "
            f"{total_errors} errors, avg score: {avg_score:.2f}"
        )

        return format_quality_calculation_response(result)

    except Exception as e:
        logger.error(f"Quality calculation failed: {e}")
        builder = MCPResponseBuilder("clinicaltrials.quality.calculate")
        return builder.error(
            ErrorCodes.CALCULATION_FAILED, f"Quality calculation failed: {e!s}"
        )


def format_incremental_sync_response(
    result: IncrementalSyncResult, full_result: dict[str, Any]
) -> list[TextContent]:
    """Format incremental sync response."""
    format_pref = get_format_preference({})

    if format_pref == "human":
        lines = [
            "🔄 **ClinicalTrials.gov Incremental Sync Results**",
            "",
        ]

        if result.success:
            quality_metrics = result.quality_metrics
            performance = result.performance

            lines.extend(
                [
                    "**Status:** ✅ Success",
                    f"**Query Key:** {result.query_key}",
                    f"**Synced:** {result.synced} trials",
                    f"**New:** {result.new}",
                    f"**Updated:** {result.updated}",
                    "",
                    "**Quality Metrics:**",
                    f"• Average Quality Score: {quality_metrics.get('avg_quality_score', 0):.2f}",
                    f"• Investment Relevant: {quality_metrics.get('investment_relevant_count', 0)}",
                    f"• High Quality (≥0.7): {quality_metrics.get('high_quality_count', 0)}",
                    "",
                    "**Performance:**",
                    f"• Total Time: {performance.get('total_tool_time_seconds', 0):.2f}s",
                    f"• Sync Rate: {performance.get('trials_per_second', 0):.1f} trials/sec",
                    f"• Batch Size: {performance.get('batch_size', 'N/A')}",
                ]
            )

            if result.watermark_updated:
                lines.append(f"**Watermark Updated:** {result.watermark_updated}")

            # Add quality filtering info if present
            if full_result.get("quality_filtered"):
                lines.extend(
                    [
                        "",
                        "**Quality Filtering:**",
                        f"• Threshold: {full_result.get('min_quality_threshold', 0):.2f}",
                        f"• Filtered Count: {full_result.get('quality_filtered_count', 0)}",
                        f"• Rejected Count: {full_result.get('quality_rejected_count', 0)}",
                        f"• Filter Efficiency: {full_result.get('quality_filter_efficiency', 0):.1%}",
                    ]
                )

        else:
            lines.extend(
                [
                    "**Status:** ❌ Failed",
                    f"**Query Key:** {result.query_key}",
                    f"**Error:** {result.error or 'Unknown error'}",
                ]
            )

        return [TextContent(type="text", text="\n".join(lines))]

    else:
        # Return full structured result for JSON format
        return MCPResponseBuilder.json_response(full_result)


def format_quality_calculation_response(result: dict[str, Any]) -> list[TextContent]:
    """Format quality calculation response."""
    format_pref = get_format_preference({})

    if format_pref == "human":
        lines = [
            "⭐ **ClinicalTrials.gov Quality Calculation Results**",
            "",
            f"**Total Requested:** {result['total_requested']}",
            f"**Processed:** {result['total_processed']}",
            f"**Errors:** {result['total_errors']}",
            "",
            "**Quality Summary:**",
            f"• Average Score: {result['avg_quality_score']:.2f}",
            f"• High Quality (≥0.7): {result['high_quality_count']}",
            f"• Investment Relevant (≥0.6): {result['investment_relevant_count']}",
            "",
            "**Individual Results:**",
        ]

        for item in result["quality_results"][:10]:  # Show first 10 for brevity
            if "quality_score" in item:
                lines.append(
                    f"• {item['nct_id']}: {item['quality_score']:.2f} "
                    f"({item.get('phase', 'N/A')} - {item.get('sponsor_class', 'N/A')})"
                )
            else:
                lines.append(
                    f"• {item['nct_id']}: Error - {item.get('error', 'Unknown')}"
                )

        if len(result["quality_results"]) > 10:
            lines.append(f"• ... and {len(result['quality_results']) - 10} more")

        return [TextContent(type="text", text="\n".join(lines))]

    else:
        return MCPResponseBuilder.json_response(result)
