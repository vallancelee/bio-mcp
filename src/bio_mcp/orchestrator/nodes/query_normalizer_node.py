"""
Query Normalization Node for Bio-MCP LangGraph Orchestrator.

This node enhances user queries by:
- Extracting medical entities (drug names, companies)
- Mapping brand names to generic names
- Converting natural language to search-optimized terms
- Adding relevant medical context
"""

import re

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import OrchestratorState

logger = get_logger(__name__)


class QueryNormalizer:
    """Normalizes and enhances biomedical research queries."""

    def __init__(self):
        """Initialize with medical term mappings."""
        # Brand name to generic drug mappings
        self.drug_mappings = {
            # GLP-1 agonists
            "ozempic": "semaglutide",
            "wegovy": "semaglutide",
            "mounjaro": "tirzepatide",
            "zepbound": "tirzepatide",
            "rybelsus": "semaglutide oral",
            "victoza": "liraglutide",
            "saxenda": "liraglutide",
            "trulicity": "dulaglutide",
            "bydureon": "exenatide",
            "byetta": "exenatide",
            # Other common drugs
            "humira": "adalimumab",
            "keytruda": "pembrolizumab",
            "opdivo": "nivolumab",
            "tecfidera": "dimethyl fumarate",
            "aduhelm": "aducanumab",
        }

        # Company mappings
        self.company_mappings = {
            "novo nordisk": ["semaglutide", "liraglutide", "insulin"],
            "eli lilly": ["tirzepatide", "dulaglutide", "insulin"],
            "pfizer": ["paxlovid", "comirnaty", "ibrance"],
            "moderna": ["spikevax", "mRNA vaccine"],
            "genentech": ["herceptin", "avastin", "tecentriq"],
            "abbvie": ["humira", "adalimumab", "skyrizi"],
            "merck": ["keytruda", "pembrolizumab", "gardasil"],
            "bristol myers squibb": ["opdivo", "nivolumab", "revlimid"],
            "johnson & johnson": ["janssen", "stelara", "darzalex"],
            "amgen": ["enbrel", "prolia", "repatha"],
        }

        # Therapeutic class keywords
        self.therapeutic_classes = {
            "diabetes": ["glp-1", "sglt2", "insulin", "metformin", "diabetes mellitus"],
            "obesity": ["glp-1", "weight loss", "bariatric", "obesity treatment"],
            "cancer": [
                "oncology",
                "chemotherapy",
                "immunotherapy",
                "tumor",
                "neoplasm",
            ],
            "immunology": [
                "autoimmune",
                "inflammation",
                "immunosuppressive",
                "biologics",
            ],
            "cardiology": [
                "cardiovascular",
                "heart failure",
                "hypertension",
                "cardiotoxicity",
            ],
            "neurology": [
                "alzheimer",
                "parkinson",
                "multiple sclerosis",
                "neurodegeneration",
            ],
        }

        # Question patterns to remove/transform
        self.question_patterns = [
            (r"what is the drug behind", ""),
            (r"who is behind", ""),
            (r"what (?:is|are)", ""),
            (r"who (?:makes|manufactures)", ""),
            (r"tell me about", ""),
            (r"can you explain", ""),
            (r"\?", ""),
        ]

    def normalize_query(self, query: str) -> dict[str, any]:
        """
        Normalize and enhance a biomedical query.

        Args:
            query: Original user query

        Returns:
            Dictionary with normalized query components
        """
        logger.info(f"Normalizing query: {query[:100]}...")

        original_query = query.lower().strip()

        # Extract entities
        entities = self._extract_entities(original_query)

        # Map brand names to generics
        mapped_terms = self._map_drug_names(entities["drugs"])

        # Add company context
        company_terms = self._get_company_context(entities["companies"])

        # Add therapeutic class context
        therapeutic_terms = self._get_therapeutic_context(original_query)

        # Remove question patterns
        cleaned_query = self._remove_question_patterns(original_query)

        # Build enhanced search terms
        search_terms = set()
        search_terms.update(mapped_terms)
        search_terms.update(company_terms)
        search_terms.update(therapeutic_terms)
        search_terms.update(entities["medical_terms"])

        # Add original meaningful terms
        meaningful_terms = self._extract_meaningful_terms(cleaned_query)
        search_terms.update(meaningful_terms)

        # Create final normalized query
        normalized_query = " ".join(sorted(search_terms))

        result = {
            "original_query": query,
            "normalized_query": normalized_query,
            "entities": entities,
            "mapped_drugs": mapped_terms,
            "company_context": company_terms,
            "therapeutic_context": therapeutic_terms,
            "enhancement_applied": len(search_terms) > len(meaningful_terms),
        }

        logger.info(
            f"Query normalized: '{normalized_query[:100]}...' (enhanced: {result['enhancement_applied']})"
        )

        return result

    def _extract_entities(self, query: str) -> dict[str, list[str]]:
        """Extract medical entities from query."""
        entities = {"drugs": [], "companies": [], "medical_terms": []}

        # Find drug brand names
        for brand_name in self.drug_mappings.keys():
            if brand_name in query:
                entities["drugs"].append(brand_name)

        # Find company names
        for company in self.company_mappings.keys():
            if company in query:
                entities["companies"].append(company)

        # Find existing medical terms (basic pattern matching)
        medical_patterns = [
            r"\b\w+mab\b",  # monoclonal antibodies
            r"\b\w+tinib\b",  # kinase inhibitors
            r"\b\w+vastatin\b",  # statins
            r"\b\w+ide\b",  # peptides
            r"\b\w+ase inhibitor\b",  # enzyme inhibitors
        ]

        for pattern in medical_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            entities["medical_terms"].extend(matches)

        return entities

    def _map_drug_names(self, brand_names: list[str]) -> list[str]:
        """Map brand names to generic names."""
        generic_names = []
        for brand in brand_names:
            if brand in self.drug_mappings:
                generic_names.append(self.drug_mappings[brand])
        return generic_names

    def _get_company_context(self, companies: list[str]) -> list[str]:
        """Get relevant drug context for companies."""
        context_terms = []
        for company in companies:
            if company in self.company_mappings:
                context_terms.extend(self.company_mappings[company][:2])  # Top 2 drugs
        return context_terms

    def _get_therapeutic_context(self, query: str) -> list[str]:
        """Add therapeutic class context based on query content."""
        context_terms = []
        for therapy_area, keywords in self.therapeutic_classes.items():
            if any(keyword in query for keyword in [therapy_area] + keywords[:2]):
                context_terms.extend(keywords[:2])  # Add top 2 relevant terms
                break  # Only add one therapeutic area to avoid over-expansion
        return context_terms

    def _remove_question_patterns(self, query: str) -> str:
        """Remove common question patterns."""
        cleaned = query
        for pattern, replacement in self.question_patterns:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _extract_meaningful_terms(self, query: str) -> list[str]:
        """Extract meaningful terms from cleaned query."""
        # Split and filter terms
        terms = query.split()

        # Remove stop words and short terms
        stop_words = {
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "it",
            "its",
            "this",
            "that",
            "these",
            "those",
            "a",
            "an",
        }

        meaningful = []
        for term in terms:
            term = term.strip(".,!?()[]{}\"'")
            if len(term) >= 3 and term.lower() not in stop_words and not term.isdigit():
                meaningful.append(term)

        return meaningful


def create_query_normalizer_node(config: OrchestratorConfig):
    """Create query normalization node for LangGraph."""

    normalizer = QueryNormalizer()

    def query_normalizer_node(state: OrchestratorState) -> OrchestratorState:
        """Process and normalize the user query."""
        logger.info("Starting query normalization")

        try:
            # Normalize the original query
            normalization_result = normalizer.normalize_query(state.query)

            # Update state with normalized query
            state.normalized_query = normalization_result["normalized_query"]
            state.query_entities = normalization_result["entities"]
            state.query_enhancement_metadata = {
                "original_query": normalization_result["original_query"],
                "mapped_drugs": normalization_result["mapped_drugs"],
                "company_context": normalization_result["company_context"],
                "therapeutic_context": normalization_result["therapeutic_context"],
                "enhancement_applied": normalization_result["enhancement_applied"],
            }

            # Add to node path
            if hasattr(state, "node_path") and state.node_path is not None:
                state.node_path.append("query_normalizer")
            else:
                state.node_path = ["query_normalizer"]

            logger.info(
                f"Query normalization completed: {state.normalized_query[:100]}..."
            )

        except Exception as e:
            logger.error(f"Query normalization failed: {e}")
            # Fallback: use original query
            state.normalized_query = state.query
            state.query_entities = {"drugs": [], "companies": [], "medical_terms": []}
            state.query_enhancement_metadata = {
                "enhancement_applied": False,
                "error": str(e),
            }

        return state

    return query_normalizer_node
