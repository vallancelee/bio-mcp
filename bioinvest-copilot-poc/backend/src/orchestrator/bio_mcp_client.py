"""
Bio-MCP Client for connecting to the Bio-MCP server and orchestrating biomedical data queries.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BioMCPClient:
    """Client for communicating with the Bio-MCP server"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        """Initialize the Bio-MCP client
        
        Args:
            base_url: Base URL of the Bio-MCP server
        """
        self.base_url = base_url
        self.client: Optional[httpx.AsyncClient] = None
        self.tools_available: List[str] = []
        
    async def initialize(self):
        """Initialize the HTTP client and discover available tools"""
        self.client = httpx.AsyncClient(timeout=30.0)
        
        try:
            # Discover available tools
            await self.discover_tools()
            logger.info(f"Bio-MCP client initialized with {len(self.tools_available)} tools")
        except Exception as e:
            logger.error(f"Failed to initialize Bio-MCP client: {e}")
            raise
    
    async def close(self):
        """Close the HTTP client"""
        if self.client:
            await self.client.aclose()
    
    async def health_check(self) -> bool:
        """Check if the Bio-MCP server is healthy
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            # Since Bio-MCP works through LangGraph orchestrator integration,
            # we test if we can access the core Bio-MCP imports
            import bio_mcp.sources.pubmed.service
            import bio_mcp.sources.clinicaltrials.service
            import bio_mcp.mcp.rag_tools
            
            # If imports succeed, Bio-MCP integration is available
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
    
    async def discover_tools(self):
        """Discover available MCP tools from the server"""
        try:
            # For this POC, we'll assume standard Bio-MCP tools are available
            # In a full implementation, we'd query the MCP server for available tools
            self.tools_available = [
                "pubmed.search",
                "pubmed.get", 
                "pubmed.sync",
                "clinicaltrials.search",
                "clinicaltrials.get",
                "clinicaltrials.sync",
                "rag.search",
                "rag.get"
            ]
            
            logger.info(f"Discovered tools: {self.tools_available}")
            
        except Exception as e:
            logger.error(f"Failed to discover tools: {e}")
            self.tools_available = []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a specific MCP tool
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool response data
        """
        if not self.client:
            raise RuntimeError("Client not initialized")
        
        if tool_name not in self.tools_available:
            raise ValueError(f"Tool {tool_name} not available. Available tools: {self.tools_available}")
        
        try:
            # For POC, we'll simulate MCP tool calls with direct HTTP requests
            # In production, this would use the MCP protocol
            
            if tool_name == "pubmed.search":
                return await self._call_pubmed_search(arguments)
            elif tool_name == "clinicaltrials.search":
                return await self._call_clinicaltrials_search(arguments)
            elif tool_name == "rag.search":
                return await self._call_rag_search(arguments)
            else:
                raise ValueError(f"Tool {tool_name} not implemented in POC")
                
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name}: {e}")
            raise
    
    async def pubmed_search(self, query: str, max_results: int = 50) -> Dict[str, Any]:
        """Search PubMed for biomedical literature
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            PubMed search results
        """
        return await self.call_tool("pubmed.search", {
            "query": query,
            "max_results": max_results
        })
    
    async def clinical_trials_search(self, query: str, max_results: int = 50) -> Dict[str, Any]:
        """Search ClinicalTrials.gov for clinical studies
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            Clinical trials search results
        """
        return await self.call_tool("clinicaltrials.search", {
            "query": query,
            "max_results": max_results
        })
    
    async def rag_search(self, query: str, max_results: int = 20) -> Dict[str, Any]:
        """Search the RAG knowledge base
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            RAG search results
        """
        return await self.call_tool("rag.search", {
            "query": query,
            "max_results": max_results
        })
    
    async def _call_pubmed_search(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Internal method to call PubMed search (POC simulation)"""
        
        # For POC, we'll return simulated results
        # In production, this would call the actual Bio-MCP server
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 50)
        
        logger.info(f"Simulating PubMed search for: {query}")
        
        # Simulate processing time
        await asyncio.sleep(1.0)
        
        # Return simulated results based on query content
        simulated_results = []
        
        # Check for GLP-1 related queries
        if "glp-1" in query.lower() or "semaglutide" in query.lower():
            simulated_results = [
                {
                    "pmid": "37845123",
                    "title": "Comparative efficacy of tirzepatide vs semaglutide in type 2 diabetes",
                    "abstract": "Background: GLP-1 receptor agonists have revolutionized diabetes treatment. This study compares tirzepatide (dual GIP/GLP-1 agonist) with semaglutide in type 2 diabetes patients. Methods: Randomized controlled trial with 2000 participants. Results: Tirzepatide demonstrated superior glycemic control (HbA1c reduction 2.1% vs 1.8%) and weight loss (12.5 kg vs 9.2 kg) compared to semaglutide. Conclusion: Tirzepatide shows superior efficacy in both glycemic control and weight reduction.",
                    "authors": ["Smith, J", "Johnson, A", "Williams, K"],
                    "journal": "New England Journal of Medicine",
                    "publication_date": "2023-11-15",
                    "doi": "10.1056/NEJMoa2307563",
                    "mesh_terms": ["Diabetes Mellitus, Type 2", "GLP-1 Receptor Agonists", "Weight Loss"],
                    "keywords": ["tirzepatide", "semaglutide", "GLP-1", "diabetes"],
                    "citation_count": 156,
                    "impact_factor": 70.67,
                    "relevance_score": 0.94
                },
                {
                    "pmid": "37823456", 
                    "title": "Cardiovascular safety of GLP-1 receptor agonists: a meta-analysis",
                    "abstract": "Objective: To assess cardiovascular safety of GLP-1 receptor agonists. Methods: Meta-analysis of 15 randomized controlled trials including semaglutide, liraglutide, and dulaglutide. Results: Significant reduction in major adverse cardiovascular events (HR 0.86, 95% CI 0.80-0.93, p<0.001). All agents showed consistent cardiovascular benefits. Conclusion: GLP-1 receptor agonists demonstrate robust cardiovascular safety with potential benefits.",
                    "authors": ["Chen, L", "Rodriguez, M", "Kim, S"],
                    "journal": "The Lancet",
                    "publication_date": "2023-10-28",
                    "doi": "10.1016/S0140-6736(23)02184-0",
                    "mesh_terms": ["Cardiovascular Diseases", "GLP-1 Receptor Agonists", "Meta-Analysis"],
                    "keywords": ["cardiovascular safety", "GLP-1", "meta-analysis"],
                    "citation_count": 89,
                    "impact_factor": 59.10,
                    "relevance_score": 0.87
                }
            ]
        
        # Generic biotech results for other queries
        else:
            simulated_results = [
                {
                    "pmid": "37901234",
                    "title": f"Recent advances in {query.split()[0] if query.split() else 'biomedical'} research",
                    "abstract": f"This review discusses recent developments in {query[:50]}... [simulated abstract content]",
                    "authors": ["Researcher, A", "Scientist, B"],
                    "journal": "Nature Biotechnology",
                    "publication_date": "2023-12-01",
                    "doi": "10.1038/nbt.2023.001",
                    "mesh_terms": ["Biotechnology", "Drug Development"],
                    "keywords": query.split()[:3] if query else ["biotechnology"],
                    "citation_count": 23,
                    "impact_factor": 46.9,
                    "relevance_score": 0.72
                }
            ]
        
        return {
            "results": simulated_results[:min(max_results, len(simulated_results))],
            "total_results": len(simulated_results),
            "search_terms": query.split(),
            "metadata": {
                "query_translation": query,
                "search_time_ms": 1000,
                "cache_hit": False
            }
        }
    
    async def _call_clinicaltrials_search(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Internal method to call ClinicalTrials search (POC simulation)"""
        
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 50)
        
        logger.info(f"Simulating ClinicalTrials search for: {query}")
        
        # Simulate processing time
        await asyncio.sleep(1.5)
        
        # Return simulated clinical trial results
        simulated_studies = []
        
        if "glp-1" in query.lower() or "diabetes" in query.lower():
            simulated_studies = [
                {
                    "nct_id": "NCT04537923",
                    "title": "SURMOUNT-1: A Study of Tirzepatide in Adults with Obesity",
                    "brief_summary": "This study evaluates the efficacy and safety of tirzepatide for chronic weight management in adults with obesity or overweight with weight-related comorbidities.",
                    "conditions": ["Obesity", "Overweight"],
                    "interventions": ["Tirzepatide", "Placebo"],
                    "phase": "Phase 3",
                    "status": "Completed",
                    "enrollment": {"target": 2539, "actual": 2539, "type": "Actual"},
                    "dates": {
                        "start_date": "2020-12-21",
                        "completion_date": "2021-12-15",
                        "last_update": "2022-04-28"
                    },
                    "sponsors": {
                        "lead_sponsor": "Eli Lilly and Company",
                        "collaborators": []
                    },
                    "locations": [
                        {"facility": "Research Site", "city": "Phoenix", "state": "Arizona", "country": "United States"}
                    ],
                    "primary_endpoint": "Percent change from baseline in body weight at Week 72",
                    "investment_score": 0.89,
                    "relevance_score": 0.91
                }
            ]
        
        return {
            "studies": simulated_studies[:min(max_results, len(simulated_studies))],
            "total_found": len(simulated_studies),
            "search_terms": query.split(),
            "metadata": {
                "search_time_ms": 1500,
                "cache_hit": False
            }
        }
    
    async def _call_rag_search(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Internal method to call RAG search (POC simulation)"""
        
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 20)
        
        logger.info(f"Simulating RAG search for: {query}")
        
        # Simulate processing time
        await asyncio.sleep(0.8)
        
        # Return simulated RAG results
        simulated_documents = [
            {
                "doc_id": "doc_001",
                "title": f"Internal Analysis: {query[:30]}",
                "content": f"This internal document discusses key findings related to {query}. Based on our proprietary analysis, we identified several important trends and opportunities in this space.",
                "source": "Internal Research Database",
                "metadata": {
                    "document_type": "research_report",
                    "created_date": "2023-11-01",
                    "author": "Research Team"
                },
                "relevance_score": 0.85,
                "chunks": [
                    {
                        "chunk_id": "chunk_001_001",
                        "text": f"Key insights about {query} include market opportunities and competitive dynamics...",
                        "position": 0,
                        "relevance_score": 0.82
                    }
                ]
            }
        ]
        
        return {
            "documents": simulated_documents[:min(max_results, len(simulated_documents))],
            "total_matches": len(simulated_documents),
            "search_mode": "hybrid",
            "processing_time_ms": 800,
            "metadata": {
                "query_embedding_computed": True,
                "vector_search_time_ms": 200,
                "rerank_time_ms": 100
            }
        }