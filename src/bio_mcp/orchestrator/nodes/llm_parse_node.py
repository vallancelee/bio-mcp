"""LLM-based query parser node for unified intent and entity extraction."""

import json
import re
from datetime import UTC, datetime
from typing import Any

import openai
from pydantic import ValidationError

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.types import FrameModel, OrchestratorState

logger = get_logger(__name__)


class LLMParseNode:
    """Node that uses LLM to parse queries into structured frames with confidence scores."""

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.client = openai.AsyncOpenAI()
        self._setup_medical_knowledge()

    def _setup_medical_knowledge(self):
        """Setup medical knowledge base for backstop rules."""
        # Drug brand name to generic mappings (from query_normalizer_node)
        self.drug_mappings = {
            "ozempic": "semaglutide",
            "wegovy": "semaglutide",
            "mounjaro": "tirzepatide",
            "trulicity": "dulaglutide",
            "victoza": "liraglutide",
            "saxenda": "liraglutide",
            "jardiance": "empagliflozin",
            "farxiga": "dapagliflozin",
            "invokana": "canagliflozin",
            "januvia": "sitagliptin",
            "glipizide": "glipizide",
            "metformin": "metformin",
            "insulin": "insulin",
            "lantus": "insulin glargine",
            "novolog": "insulin aspart",
            "humalog": "insulin lispro",
            "levemir": "insulin detemir",
        }

        # Company mappings
        self.company_mappings = {
            "novo nordisk": "Novo Nordisk",
            "eli lilly": "Eli Lilly",
            "lilly": "Eli Lilly",
            "pfizer": "Pfizer",
            "johnson & johnson": "Johnson & Johnson",
            "j&j": "Johnson & Johnson",
            "roche": "Roche",
            "novartis": "Novartis",
            "astrazeneca": "AstraZeneca",
            "gsk": "GlaxoSmithKline",
            "glaxosmithkline": "GlaxoSmithKline",
        }

        # Regex patterns for backstop recognition
        self.patterns = {
            "nct_id": re.compile(r"\bNCT\d{8}\b", re.IGNORECASE),
            "pmid": re.compile(r"\bPMID:?\s*(\d+)\b", re.IGNORECASE),
            "phase": re.compile(r"\bPhase\s+([I1V2-4]+)\b", re.IGNORECASE),
            "doi": re.compile(r"\b10\.\d{4,}[/.]\S+\b"),
        }

    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Parse query using LLM with JSON schema validation."""
        start_time = datetime.now(UTC)
        query = state["query"]

        try:
            # Call LLM with structured schema
            frame_data = await self._call_llm_with_schema(query)

            # Validate with Pydantic model
            try:
                frame_model = FrameModel(**frame_data)
                frame = frame_model.model_dump()
            except ValidationError as e:
                logger.warning(f"Initial frame validation failed: {e}")
                # Retry once with error feedback
                frame_data = await self._call_llm_with_schema(
                    query, retry_error=f"Previous response failed validation: {e}"
                )
                frame_model = FrameModel(**frame_data)
                frame = frame_model.model_dump()

            # Apply backstop rules for known patterns
            frame = self._apply_backstop_rules(query, frame)

            # Calculate latency
            latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

            logger.info(
                "LLM parse completed",
                extra={
                    "query": query[:100],
                    "intent": frame["intent"],
                    "intent_confidence": frame.get("intent_confidence", 1.0),
                    "entities": list(frame.get("entities", {}).keys()),
                    "latency_ms": latency_ms,
                },
            )

            # Update state
            return {
                "frame": frame,
                "intent_confidence": frame.get("intent_confidence", 1.0),
                "entity_confidence": frame.get("entity_confidence", {}),
                "node_path": state["node_path"] + ["llm_parse"],
                "latencies": {**state["latencies"], "llm_parse": latency_ms},
                "messages": state["messages"]
                + [
                    {
                        "role": "system",
                        "content": f"Parsed intent: {frame['intent']} (conf: {frame.get('intent_confidence', 1.0):.2f})",
                    }
                ],
            }

        except Exception as e:
            logger.error("LLM parse failed", extra={"query": query, "error": str(e)})

            # Return error state
            latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
            return {
                "errors": state["errors"]
                + [
                    {
                        "node": "llm_parse",
                        "error": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ],
                "node_path": state["node_path"] + ["llm_parse"],
                "latencies": {**state["latencies"], "llm_parse": latency_ms},
                "messages": state["messages"]
                + [{"role": "system", "content": f"LLM parsing error: {e!s}"}],
            }

    async def _call_llm_with_schema(
        self, query: str, retry_error: str | None = None
    ) -> dict[str, Any]:
        """Call OpenAI with structured JSON schema for frame extraction."""

        system_prompt = """You are a biomedical query parser that extracts structured information from user queries about scientific literature, clinical trials, and drug research.

Your task is to parse the query and return a JSON object with the following schema:

{
  "intent": "recent_pubs_by_topic" | "indication_phase_trials" | "trials_with_pubs" | "hybrid_search",
  "entities": {
    "topic": "string (research topic, disease, drug)",
    "indication": "string (medical condition)", 
    "drug": "string (drug name, generic preferred)",
    "company": "string (pharmaceutical company)",
    "phase": "string (clinical trial phase)",
    "nct_id": "string (NCT ID if mentioned)",
    "pmid": "string (PMID if mentioned)"
  },
  "filters": {
    "date_range": "string (time period like 'last 6 months')",
    "published_within_days": "number (days for recent filter)",
    "phase": "string (trial phase filter)",
    "status": "string (trial status filter)"
  },
  "tool_hints": {
    "preferred_sources": ["string (pubmed|clinicaltrials|both)"],
    "result_type": "string (papers|trials|both)"
  },
  "intent_confidence": "number 0-1 (confidence in intent classification)",
  "entity_confidence": {
    "entity_name": "number 0-1 (confidence for each entity)"
  }
}

Intent Guidelines:
- recent_pubs_by_topic: User wants recent publications on a topic
- indication_phase_trials: User wants trials for a specific condition/phase
- trials_with_pubs: User wants trials AND related publications
- hybrid_search: Complex queries requiring multiple sources

Entity Extraction:
- Normalize drug names to generic when possible (e.g., Ozempic → semaglutide)  
- Extract company names in full form (e.g., Novo Nordisk, Eli Lilly)
- Identify NCT IDs, PMIDs if present
- Extract time references into appropriate filters

Confidence Scoring:
- Use 0.9+ for very clear intents/entities
- Use 0.7-0.9 for moderately clear
- Use 0.5-0.7 for ambiguous
- Use <0.5 for very uncertain"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Parse this biomedical query: {query}"},
        ]

        if retry_error:
            messages.append(
                {
                    "role": "user",
                    "content": f"The previous response had this error: {retry_error}. Please fix and try again.",
                }
            )

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for consistency
            max_tokens=1000,
        )

        response_text = response.choices[0].message.content
        if not response_text:
            raise ValueError("Empty response from LLM")

        return json.loads(response_text)

    def _apply_backstop_rules(
        self, query: str, frame: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply regex and gazetteer backstop rules to improve accuracy."""
        entities = frame.get("entities", {})
        entity_confidence = frame.get("entity_confidence", {})

        # NCT ID detection
        nct_match = self.patterns["nct_id"].search(query)
        if nct_match and not entities.get("nct_id"):
            entities["nct_id"] = nct_match.group(0).upper()
            entity_confidence["nct_id"] = 1.0

        # PMID detection
        pmid_match = self.patterns["pmid"].search(query)
        if pmid_match and not entities.get("pmid"):
            entities["pmid"] = pmid_match.group(1)
            entity_confidence["pmid"] = 1.0

        # Drug name normalization
        if entities.get("drug"):
            drug_name = entities["drug"].lower()
            if drug_name in self.drug_mappings:
                entities["drug"] = self.drug_mappings[drug_name]
                entity_confidence["drug"] = min(
                    entity_confidence.get("drug", 0.8) + 0.1, 1.0
                )

        # Company name normalization
        if entities.get("company"):
            company_name = entities["company"].lower()
            if company_name in self.company_mappings:
                entities["company"] = self.company_mappings[company_name]
                entity_confidence["company"] = min(
                    entity_confidence.get("company", 0.8) + 0.1, 1.0
                )

        # Phase detection
        phase_match = self.patterns["phase"].search(query)
        if phase_match and not entities.get("phase"):
            entities["phase"] = phase_match.group(1).upper()
            entity_confidence["phase"] = 0.9

        # Update frame
        frame["entities"] = entities
        frame["entity_confidence"] = entity_confidence

        return frame


def create_llm_parse_node(config: OrchestratorConfig):
    """Factory function to create LLM parse node."""
    return LLMParseNode(config)
