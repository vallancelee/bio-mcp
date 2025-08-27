"""
Pydantic models for the BioInvest AI Copilot POC backend
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryStatus(Enum):
    """Status of a research query"""
    INITIATED = "initiated"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisOptions(BaseModel):
    """Analysis options for research queries"""
    max_results_per_source: int = Field(default=50, ge=1, le=200, description="Maximum results per source")
    include_synthesis: bool = Field(default=True, description="Generate AI synthesis of results")
    priority: str = Field(default="balanced", description="Analysis priority: speed, comprehensive, or balanced")


class OrchestrationRequest(BaseModel):
    """Request model for submitting research queries"""
    query: str = Field(..., description="Natural language research query", min_length=1, max_length=1000)
    sources: List[str] = Field(
        default=["pubmed", "clinical_trials", "rag"],
        description="Data sources to search"
    )
    options: AnalysisOptions = Field(default_factory=AnalysisOptions, description="Analysis configuration")


class OrchestrationResponse(BaseModel):
    """Response model for submitted queries"""
    query_id: str = Field(..., description="Unique query identifier")
    status: QueryStatus = Field(..., description="Current query status")
    estimated_completion_time: int = Field(..., description="Estimated completion time in seconds")
    progress: Dict[str, str] = Field(..., description="Progress by data source")
    partial_results_available: bool = Field(..., description="Whether partial results are available")
    stream_url: str = Field(..., description="URL for streaming results")
    created_at: str = Field(..., description="Query creation timestamp")


class Citation(BaseModel):
    """Citation information for research results"""
    id: str = Field(..., description="Unique citation ID")
    type: str = Field(..., description="Citation type (pubmed, clinical_trial, rag)")
    title: str = Field(..., description="Title of cited work")
    authors: Optional[List[str]] = Field(default=None, description="Authors")
    source: str = Field(..., description="Publication source")
    year: Optional[int] = Field(default=None, description="Publication year")
    url: Optional[str] = Field(default=None, description="URL to source")
    snippet: str = Field(..., description="Relevant snippet or excerpt")
    relevance_score: float = Field(..., ge=0, le=1, description="Relevance score (0-1)")


class QualityMetrics(BaseModel):
    """Quality metrics for synthesis results"""
    completeness: float = Field(..., ge=0, le=1, description="Completeness score (0-1)")
    recency: float = Field(..., ge=0, le=1, description="Recency score (0-1)")
    authority: float = Field(..., ge=0, le=1, description="Authority score (0-1)")
    diversity: float = Field(..., ge=0, le=1, description="Source diversity score (0-1)")
    relevance: float = Field(..., ge=0, le=1, description="Relevance score (0-1)")
    overall_score: float = Field(..., ge=0, le=1, description="Overall quality score (0-1)")


class RiskFactor(BaseModel):
    """Risk factor identification"""
    factor: str = Field(..., description="Risk factor name")
    impact: float = Field(..., ge=-1, le=1, description="Impact score (-1 to 1)")
    explanation: str = Field(..., description="Explanation of the risk factor")
    severity: str = Field(..., description="Risk severity (low, medium, high)")


class KeyInsight(BaseModel):
    """Key insight extracted from research"""
    insight: str = Field(..., description="The insight text")
    supporting_evidence: List[str] = Field(..., description="Supporting evidence")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score (0-1)")
    category: str = Field(..., description="Insight category")


class CompetitiveAnalysis(BaseModel):
    """Competitive landscape analysis"""
    direct_competitors: List[Dict[str, Any]] = Field(default_factory=list, description="Direct competitors")
    competitive_threats: List[str] = Field(default_factory=list, description="Key competitive threats")
    market_position: str = Field(..., description="Overall market position assessment")
    competitive_advantages: List[str] = Field(default_factory=list, description="Identified competitive advantages")
    risks: List[RiskFactor] = Field(default_factory=list, description="Competitive risks")


class SynthesisResponse(BaseModel):
    """AI synthesis of research results"""
    summary: str = Field(..., description="Executive summary of findings")
    key_insights: List[KeyInsight] = Field(default_factory=list, description="Key insights extracted")
    competitive_analysis: Optional[CompetitiveAnalysis] = Field(default=None, description="Competitive analysis")
    risk_assessment: List[RiskFactor] = Field(default_factory=list, description="Risk factors identified")
    recommendations: List[str] = Field(default_factory=list, description="Strategic recommendations")
    quality_metrics: QualityMetrics = Field(..., description="Quality assessment of synthesis")
    citations: List[Citation] = Field(default_factory=list, description="Source citations")
    sources_summary: Dict[str, int] = Field(default_factory=dict, description="Count by source type")
    generation_metadata: Dict[str, Any] = Field(default_factory=dict, description="Generation metadata")


class PubMedArticle(BaseModel):
    """PubMed article result"""
    pmid: str = Field(..., description="PubMed ID")
    title: str = Field(..., description="Article title")
    abstract: str = Field(..., description="Article abstract")
    authors: List[str] = Field(default_factory=list, description="Authors")
    journal: str = Field(..., description="Journal name")
    publication_date: str = Field(..., description="Publication date")
    doi: Optional[str] = Field(default=None, description="DOI")
    pmc_id: Optional[str] = Field(default=None, description="PMC ID")
    mesh_terms: List[str] = Field(default_factory=list, description="MeSH terms")
    keywords: List[str] = Field(default_factory=list, description="Keywords")
    citation_count: Optional[int] = Field(default=None, description="Citation count")
    impact_factor: Optional[float] = Field(default=None, description="Journal impact factor")
    relevance_score: Optional[float] = Field(default=None, description="Relevance score")


class ClinicalTrial(BaseModel):
    """Clinical trial result"""
    nct_id: str = Field(..., description="ClinicalTrials.gov NCT ID")
    title: str = Field(..., description="Study title")
    brief_summary: str = Field(..., description="Brief summary")
    detailed_description: Optional[str] = Field(default=None, description="Detailed description")
    conditions: List[str] = Field(default_factory=list, description="Medical conditions")
    interventions: List[str] = Field(default_factory=list, description="Interventions")
    phase: str = Field(..., description="Study phase")
    status: str = Field(..., description="Study status")
    enrollment: Dict[str, Any] = Field(default_factory=dict, description="Enrollment information")
    dates: Dict[str, Any] = Field(default_factory=dict, description="Study dates")
    sponsors: Dict[str, Any] = Field(default_factory=dict, description="Sponsor information")
    locations: List[Dict[str, Any]] = Field(default_factory=list, description="Study locations")
    primary_endpoint: Optional[str] = Field(default=None, description="Primary endpoint")
    secondary_endpoints: List[str] = Field(default_factory=list, description="Secondary endpoints")
    investment_score: Optional[float] = Field(default=None, description="Investment attractiveness score")
    relevance_score: Optional[float] = Field(default=None, description="Relevance score")


class RAGDocument(BaseModel):
    """RAG search document result"""
    doc_id: str = Field(..., description="Document ID")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    source: str = Field(..., description="Document source")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    relevance_score: float = Field(..., ge=0, le=1, description="Relevance score")
    chunks: List[Dict[str, Any]] = Field(default_factory=list, description="Document chunks")


class StreamingEvent(BaseModel):
    """Server-sent event for streaming results"""
    event: str = Field(..., description="Event type")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Event timestamp")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Error timestamp")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracking")