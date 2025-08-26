"""Frame parsing logic for natural language queries."""
import re
from typing import Any


class FrameParser:
    """Parse natural language queries into structured frames."""
    
    def __init__(self, config=None):
        self.config = config
        self._setup_patterns()
    
    def _setup_patterns(self):
        """Setup regex patterns for entity extraction."""
        self.patterns = {
            "topic": {
                "recent_pubs_by_topic": [
                    r"recent.*publications.*on\s+(.+)",
                    r"recent.*papers.*about\s+(.+)",
                    r"latest.*research.*on\s+(.+)",
                ],
                "indication_phase_trials": [
                    r"trials.*for\s+(.+)",
                    r"clinical.*trials.*treating\s+(.+)",
                ],
            }
        }
    
    def parse_frame(self, query: str) -> dict[str, Any]:
        """Parse query into structured frame."""
        if not query or not query.strip():
            raise ValueError("Empty query cannot be parsed")
        
        query_lower = query.lower()
        
        # Determine intent based on keywords
        intent = self._extract_intent(query_lower)
        
        # Extract entities based on intent
        entities = self._extract_entities(query, intent)
        
        return {
            "intent": intent,
            "entities": entities,
            "filters": {},
            "fetch_policy": "cache_then_network",
            "time_budget_ms": 5000
        }
    
    def _extract_intent(self, query: str) -> str:
        """Extract intent from query."""
        if any(word in query for word in ["recent", "latest", "new", "publications", "papers"]):
            return "recent_pubs_by_topic"
        elif any(word in query for word in ["trials", "clinical", "study"]):
            return "indication_phase_trials"
        elif any(word in query for word in ["search", "find", "documents"]):
            return "hybrid_search"
        else:
            return "recent_pubs_by_topic"  # default
    
    def _extract_entities(self, query: str, intent: str) -> dict[str, Any]:
        """Extract entities from query based on intent."""
        entities = {}
        
        if intent == "recent_pubs_by_topic":
            # Extract topic after "on", "about", etc.
            for pattern in self.patterns["topic"]["recent_pubs_by_topic"]:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    entities["topic"] = match.group(1).strip()
                    break
            
            # If no pattern matched, use the whole query minus common words
            if "topic" not in entities:
                # Remove common words and use rest as topic
                topic = re.sub(r'\b(recent|latest|new|publications|papers|on|about|research)\b', '', query, flags=re.IGNORECASE)
                entities["topic"] = topic.strip()
        
        elif intent == "indication_phase_trials":
            # Extract indication from trials queries
            for pattern in self.patterns["topic"]["indication_phase_trials"]:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    entities["indication"] = match.group(1).strip()
                    break
        
        return entities