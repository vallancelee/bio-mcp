"""
ClinicalTrials.gov document models.

This module provides document models specifically designed for clinical trial data
from ClinicalTrials.gov, with investment-focused scoring and fields optimized
for biotech research and analysis.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from bio_mcp.shared.models.base_models import BaseDocument


@dataclass
class ClinicalTrialDocument(BaseDocument):
    """ClinicalTrials.gov-specific document model extending BaseDocument."""

    # Clinical trial-specific core fields
    nct_id: str = ""
    phase: str | None = None  # EARLY_PHASE1, PHASE1, PHASE2, PHASE3, PHASE4
    status: str | None = None  # RECRUITING, ACTIVE_NOT_RECRUITING, COMPLETED, etc.
    study_type: str | None = None  # INTERVENTIONAL, OBSERVATIONAL

    # Sponsor and organization
    sponsor_name: str | None = None
    sponsor_class: str | None = None  # INDUSTRY, NIH, ACADEMIC, OTHER
    collaborators: list[str] = field(default_factory=list)

    # Enrollment and participant information
    enrollment_count: int | None = None
    enrollment_type: str | None = None  # ACTUAL, ESTIMATED
    age_eligibility: str | None = None
    gender_eligibility: str | None = None

    # Medical and research context
    conditions: list[str] = field(default_factory=list)
    interventions: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)

    # Timeline and completion
    start_date: date | None = None
    primary_completion_date: date | None = None
    completion_date: date | None = None
    first_posted_date: date | None = None
    last_update_posted_date: date | None = None

    # Results and outcomes
    has_results: bool = False
    primary_outcomes: list[str] = field(default_factory=list)
    secondary_outcomes: list[str] = field(default_factory=list)

    # Additional structured content
    brief_summary: str | None = None
    detailed_description: str | None = None
    keywords: list[str] = field(default_factory=list)

    # Investment relevance (computed)
    investment_relevance_score: float = 0.0

    def __post_init__(self):
        """Post-initialization processing."""
        # Compute investment relevance score
        self.investment_relevance_score = self.get_investment_relevance_score()

    @classmethod
    def from_api_data(cls, api_data: dict[str, Any]) -> "ClinicalTrialDocument":
        """Create ClinicalTrialDocument from ClinicalTrials.gov API response."""
        try:
            protocol_section = api_data.get("protocolSection", {})

            # Extract identification info
            identification = protocol_section.get("identificationModule", {})
            nct_id = identification.get("nctId", "")
            brief_title = identification.get("briefTitle", "")
            official_title = identification.get("officialTitle", "")

            # Use brief title preferentially, fall back to official title
            title = brief_title or official_title or ""

            # Extract status info
            status_module = protocol_section.get("statusModule", {})
            overall_status = status_module.get("overallStatus")
            start_date = cls._parse_date(status_module.get("startDateStruct"))
            primary_completion_date = cls._parse_date(
                status_module.get("primaryCompletionDateStruct")
            )
            completion_date = cls._parse_date(status_module.get("completionDateStruct"))
            first_posted_date = cls._parse_date(
                status_module.get("studyFirstPostDateStruct")
            )
            last_update_date = cls._parse_date(
                status_module.get("lastUpdatePostDateStruct")
            )

            # Extract sponsor info
            sponsor_module = protocol_section.get("sponsorCollaboratorsModule", {})
            lead_sponsor = sponsor_module.get("leadSponsor", {})
            sponsor_name = lead_sponsor.get("name")
            sponsor_class = lead_sponsor.get("class")

            # Extract collaborators
            collaborators_data = sponsor_module.get("collaborators", [])
            collaborators = [
                c.get("name", "") for c in collaborators_data if c.get("name")
            ]

            # Extract description
            description_module = protocol_section.get("descriptionModule", {})
            brief_summary = description_module.get("briefSummary")
            detailed_description = description_module.get("detailedDescription")

            # Use brief summary as primary content for chunking
            content_text = brief_summary or detailed_description or ""
            abstract_text = brief_summary  # Keep brief summary as abstract

            # Extract conditions
            conditions_module = protocol_section.get("conditionsModule", {})
            conditions = conditions_module.get("conditions", [])
            keywords = conditions_module.get("keywords", [])

            # Extract design info
            design_module = protocol_section.get("designModule", {})
            study_type = design_module.get("studyType")
            phases = design_module.get("phases", [])
            phase = phases[0] if phases else None

            # Extract enrollment
            enrollment_info = design_module.get("enrollmentInfo", {})
            enrollment_count = enrollment_info.get("count")
            enrollment_type = enrollment_info.get("type")

            # Extract eligibility
            eligibility_module = protocol_section.get("eligibilityModule", {})
            age_eligibility = eligibility_module.get("minimumAge")
            gender_eligibility = eligibility_module.get("sex")

            # Extract interventions
            interventions_module = protocol_section.get("armsInterventionsModule", {})
            interventions_data = interventions_module.get("interventions", [])
            interventions = [
                i.get("name", "") for i in interventions_data if i.get("name")
            ]

            # Extract outcomes
            outcomes_module = protocol_section.get("outcomesModule", {})
            primary_outcomes_data = outcomes_module.get("primaryOutcomes", [])
            secondary_outcomes_data = outcomes_module.get("secondaryOutcomes", [])

            primary_outcomes = [
                o.get("measure", "") for o in primary_outcomes_data if o.get("measure")
            ]
            secondary_outcomes = [
                o.get("measure", "")
                for o in secondary_outcomes_data
                if o.get("measure")
            ]

            # Extract contact/location info
            contacts_module = protocol_section.get("contactsLocationsModule", {})
            locations_data = contacts_module.get("locations", [])
            locations = []
            for loc in locations_data:
                city = loc.get("city", "")
                country = loc.get("country", "")
                if city and country:
                    locations.append(f"{city}, {country}")

            # Check if study has results
            has_results = bool(api_data.get("hasResults", False))

            # Create publication date from study dates (convert date to datetime)
            if first_posted_date:
                publication_date = datetime.combine(first_posted_date, datetime.min.time())
            elif start_date:
                publication_date = datetime.combine(start_date, datetime.min.time())
            else:
                publication_date = None

            return cls(
                # BaseDocument fields
                id=f"ctgov:{nct_id}",
                source_id=nct_id,
                source="ctgov",
                title=title,
                abstract=abstract_text,
                content=content_text,
                publication_date=publication_date,
                # ClinicalTrial-specific fields
                nct_id=nct_id,
                phase=phase,
                status=overall_status,
                study_type=study_type,
                sponsor_name=sponsor_name,
                sponsor_class=sponsor_class,
                collaborators=collaborators,
                enrollment_count=enrollment_count,
                enrollment_type=enrollment_type,
                age_eligibility=age_eligibility,
                gender_eligibility=gender_eligibility,
                conditions=conditions,
                interventions=interventions,
                locations=locations,
                start_date=start_date,
                primary_completion_date=primary_completion_date,
                completion_date=completion_date,
                first_posted_date=first_posted_date,
                last_update_posted_date=last_update_date,
                has_results=has_results,
                primary_outcomes=primary_outcomes,
                secondary_outcomes=secondary_outcomes,
                brief_summary=brief_summary,
                detailed_description=detailed_description,
                keywords=keywords,
            )

        except Exception as e:
            raise ValueError(f"Failed to parse clinical trial API data: {e}")

    @staticmethod
    def _parse_date(date_struct: dict[str, Any] | None) -> date | None:
        """Parse date from ClinicalTrials.gov date structure."""
        if not date_struct or not isinstance(date_struct, dict):
            return None

        try:
            date_str = date_struct.get("date")
            if date_str:
                # API returns dates in YYYY-MM-DD format
                return datetime.fromisoformat(date_str).date()
        except (ValueError, TypeError):
            pass

        return None

    def get_investment_relevance_score(self) -> float:
        """
        Calculate investment relevance score for biotech analysis (0.0-1.0).

        This score prioritizes factors important for investment research:
        - Later phase trials (Phase 3 > Phase 2 > Phase 1)
        - Industry sponsorship (vs academic/NIH)
        - Large enrollment sizes
        - Active/recruiting status
        - High-value therapeutic areas
        - Results availability
        """
        score = 0.0

        # Phase-based scoring (most important factor)
        phase_weights = {
            "PHASE3": 0.35,
            "PHASE2": 0.25,
            "PHASE1_PHASE2": 0.20,
            "PHASE1": 0.15,
            "EARLY_PHASE1": 0.10,
        }

        if self.phase:
            score += phase_weights.get(self.phase, 0.05)

        # Sponsor class scoring
        if self.sponsor_class == "INDUSTRY":
            score += 0.20  # Industry trials highly relevant for investment
        elif self.sponsor_class in ["ACADEMIC", "NIH"]:
            score += 0.10  # Academic trials somewhat relevant

        # Enrollment size scoring
        if self.enrollment_count:
            if self.enrollment_count >= 500:
                score += 0.15  # Large pivotal trials
            elif self.enrollment_count >= 100:
                score += 0.10  # Medium-sized trials
            elif self.enrollment_count >= 50:
                score += 0.05  # Smaller trials

        # Status-based scoring
        active_statuses = [
            "RECRUITING",
            "ACTIVE_NOT_RECRUITING",
            "ENROLLING_BY_INVITATION",
        ]
        if self.status in active_statuses:
            score += 0.10
        elif self.status == "COMPLETED":
            score += 0.05  # Completed trials have some value

        # Results availability
        if self.has_results:
            score += 0.10

        # High-value therapeutic areas
        high_value_conditions = {
            "cancer",
            "oncology",
            "tumor",
            "carcinoma",
            "leukemia",
            "lymphoma",
            "diabetes",
            "alzheimer",
            "parkinson",
            "multiple sclerosis",
            "rheumatoid arthritis",
            "crohn",
            "psoriasis",
            "obesity",
            "cardiovascular",
            "heart disease",
            "rare disease",
            "orphan",
        }

        condition_boost = 0.05
        for condition in self.conditions:
            condition_lower = condition.lower()
            if any(hv_cond in condition_lower for hv_cond in high_value_conditions):
                score += condition_boost
                break  # Only count once

        # Investment-relevant intervention types
        investment_interventions = {
            "drug",
            "biological",
            "genetic",
            "device",
            "vaccine",
            "monoclonal antibody",
            "cell therapy",
            "gene therapy",
        }

        for intervention in self.interventions:
            intervention_lower = intervention.lower()
            if any(
                inv_type in intervention_lower for inv_type in investment_interventions
            ):
                score += 0.05
                break  # Only count once

        return min(score, 1.0)  # Cap at 1.0

    def get_search_content(self) -> str:
        """Return text content for embedding and search."""
        parts = []

        if self.title:
            parts.append(self.title)

        if self.brief_summary:
            parts.append(self.brief_summary)

        if self.detailed_description:
            parts.append(self.detailed_description)

        # Add key structured information
        if self.conditions:
            parts.append(f"Conditions: {', '.join(self.conditions)}")

        if self.interventions:
            parts.append(f"Interventions: {', '.join(self.interventions)}")

        if self.sponsor_name:
            parts.append(f"Sponsor: {self.sponsor_name}")

        if self.phase:
            parts.append(f"Phase: {self.phase}")

        return "\n\n".join(parts).strip()

    def get_display_title(self) -> str:
        """Return formatted title for display."""
        if not self.title:
            return f"Clinical Trial {self.nct_id}"

        # Truncate very long titles
        if len(self.title) > 100:
            return f"{self.title[:97]}..."

        return self.title

    def to_database_format(self) -> dict[str, Any]:
        """Convert to format suitable for database storage."""
        base_data = {
            "id": self.id,
            "source_id": self.source_id,
            "source": self.source,
            "title": self.title,
            "abstract": self.abstract,
            "content": self.content,
            "authors": self.authors,
            "publication_date": self.publication_date,
            "quality_score": int(
                self.investment_relevance_score * 100
            ),  # Convert to 0-100
            "last_updated": self.last_update_posted_date or datetime.now(),
        }

        # Add clinical trial specific metadata
        metadata: dict[str, Any] = {
            "nct_id": self.nct_id,
            "phase": self.phase,
            "status": self.status,
            "study_type": self.study_type,
            "sponsor_name": self.sponsor_name,
            "sponsor_class": self.sponsor_class,
            "enrollment_count": self.enrollment_count,
            "enrollment_type": self.enrollment_type,
            "conditions": self.conditions,
            "interventions": self.interventions,
            "locations": self.locations,
            "has_results": self.has_results,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "primary_completion_date": self.primary_completion_date.isoformat() if self.primary_completion_date else None,
            "first_posted_date": self.first_posted_date.isoformat() if self.first_posted_date else None,
            "last_update_posted_date": self.last_update_posted_date.isoformat() if self.last_update_posted_date else None,
            "investment_relevance_score": self.investment_relevance_score,
        }
        base_data["metadata"] = metadata  # type: ignore[assignment]

        return base_data

    def get_summary_for_display(self) -> dict[str, Any]:
        """Get a summary dict suitable for display in search results."""
        return {
            "nct_id": self.nct_id,
            "title": self.get_display_title(),
            "phase": self.phase,
            "status": self.status,
            "sponsor": self.sponsor_name,
            "sponsor_class": self.sponsor_class,
            "conditions": self.conditions[:3],  # Limit for display
            "interventions": self.interventions[:3],  # Limit for display
            "enrollment": self.enrollment_count,
            "investment_score": round(self.investment_relevance_score, 2),
            "has_results": self.has_results,
        }
