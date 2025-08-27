"""
Quality scoring for clinical trials with investment-focused metrics.

This module provides comprehensive quality scoring for clinical trials,
optimized for biotech investment research and analysis.
"""

from dataclasses import dataclass
from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.sources.clinicaltrials.models import ClinicalTrialDocument

logger = get_logger(__name__)


@dataclass(frozen=True)
class ClinicalTrialQualityConfig:
    """Configuration for clinical trial quality scoring."""

    # Phase-based scoring weights
    PHASE_3_BOOST: float = 0.30  # Phase 3 trials most valuable for investment
    PHASE_2_BOOST: float = 0.20  # Phase 2 trials moderately valuable
    PHASE_1_PHASE_2_BOOST: float = 0.18  # Combined phase trials
    PHASE_1_BOOST: float = 0.10  # Phase 1 trials lower value
    EARLY_PHASE_1_BOOST: float = 0.05  # Early phase lowest value

    # Sponsor type scoring
    INDUSTRY_SPONSOR_BOOST: float = 0.15  # Industry trials for investment relevance
    ACADEMIC_SPONSOR_BOOST: float = 0.08  # Academic trials moderate relevance
    NIH_SPONSOR_BOOST: float = 0.05  # NIH trials lower investment relevance

    # Enrollment size scoring thresholds and boosts
    LARGE_ENROLLMENT_THRESHOLD: int = 500  # Pivotal trial size
    MEDIUM_ENROLLMENT_THRESHOLD: int = 100  # Medium trial size
    SMALL_ENROLLMENT_THRESHOLD: int = 50  # Small trial size

    LARGE_ENROLLMENT_BOOST: float = 0.15  # Large pivotal trials
    MEDIUM_ENROLLMENT_BOOST: float = 0.10  # Medium-sized trials
    SMALL_ENROLLMENT_BOOST: float = 0.05  # Smaller trials

    # Status-based scoring
    ACTIVE_STATUS_BOOST: float = 0.10  # Active/recruiting trials
    COMPLETED_STATUS_BOOST: float = 0.05  # Completed trials have some value

    # Results availability
    RESULTS_AVAILABLE_BOOST: float = 0.15  # Trials with results posted

    # High-value conditions for biotech investment
    HIGH_VALUE_CONDITIONS: frozenset[str] = frozenset(
        [
            # Oncology (highest value)
            "cancer",
            "oncology",
            "tumor",
            "carcinoma",
            "leukemia",
            "lymphoma",
            "melanoma",
            "sarcoma",
            "myeloma",
            "glioma",
            "adenocarcinoma",
            # Metabolic diseases
            "diabetes",
            "obesity",
            "metabolic syndrome",
            # Neurological diseases
            "alzheimer",
            "parkinson",
            "multiple sclerosis",
            "als",
            "huntington",
            "epilepsy",
            "migraine",
            "depression",
            "schizophrenia",
            # Autoimmune/inflammatory
            "rheumatoid arthritis",
            "crohn",
            "psoriasis",
            "lupus",
            "inflammatory bowel",
            # Cardiovascular
            "cardiovascular",
            "heart disease",
            "heart failure",
            "hypertension",
            # Rare diseases (high value due to orphan status)
            "rare disease",
            "orphan",
            "genetic disorder",
            # Infectious diseases
            "hiv",
            "hepatitis",
            "tuberculosis",
            "covid",
        ]
    )

    HIGH_VALUE_CONDITION_BOOST: float = 0.08  # Boost per high-value condition

    # Investment-relevant intervention types
    INVESTMENT_INTERVENTIONS: frozenset[str] = frozenset(
        [
            # Biologics (highest value)
            "monoclonal antibody",
            "biological",
            "biologic",
            "antibody",
            "immunotherapy",
            "car-t",
            "cell therapy",
            "gene therapy",
            # Novel drug classes
            "small molecule",
            "targeted therapy",
            "precision medicine",
            # Emerging technologies
            "mrna",
            "vaccine",
            "genetic",
            "crispr",
            "gene editing",
            # Medical devices (moderate value)
            "device",
            "implant",
            "diagnostic",
            # Traditional drugs
            "drug",
            "pharmaceutical",
            "compound",
        ]
    )

    INVESTMENT_INTERVENTION_BOOST: float = 0.05  # Boost per relevant intervention

    # Base quality score starting point
    BASE_QUALITY_SCORE: float = 0.4  # Neutral starting point

    # Maximum quality score cap
    MAX_QUALITY_SCORE: float = 1.0


def calculate_clinical_trial_quality(
    trial: ClinicalTrialDocument, config: ClinicalTrialQualityConfig | None = None
) -> float:
    """
    Calculate comprehensive quality score for clinical trial (0.0-1.0).

    This scoring system is optimized for biotech investment research,
    prioritizing factors that indicate commercial potential and
    investment relevance.

    Args:
        trial: ClinicalTrialDocument to score
        config: Optional configuration (uses default if None)

    Returns:
        Quality score between 0.0 and 1.0
    """
    if not config:
        config = ClinicalTrialQualityConfig()

    # Start with base score
    score = config.BASE_QUALITY_SCORE

    logger.debug(f"Calculating quality for trial {trial.nct_id}")

    # Phase-based scoring (highest weight factor)
    phase_boost = _calculate_phase_score(trial, config)
    score += phase_boost
    logger.debug(f"Phase boost: {phase_boost} (phase: {trial.phase})")

    # Sponsor class scoring
    sponsor_boost = _calculate_sponsor_score(trial, config)
    score += sponsor_boost
    logger.debug(f"Sponsor boost: {sponsor_boost} (class: {trial.sponsor_class})")

    # Enrollment size scoring
    enrollment_boost = _calculate_enrollment_score(trial, config)
    score += enrollment_boost
    logger.debug(
        f"Enrollment boost: {enrollment_boost} (count: {trial.enrollment_count})"
    )

    # Status-based scoring
    status_boost = _calculate_status_score(trial, config)
    score += status_boost
    logger.debug(f"Status boost: {status_boost} (status: {trial.status})")

    # Results availability
    results_boost = _calculate_results_score(trial, config)
    score += results_boost
    logger.debug(f"Results boost: {results_boost} (has_results: {trial.has_results})")

    # High-value condition scoring
    condition_boost = _calculate_condition_score(trial, config)
    score += condition_boost
    logger.debug(
        f"Condition boost: {condition_boost} (conditions: {len(trial.conditions)})"
    )

    # Investment-relevant intervention scoring
    intervention_boost = _calculate_intervention_score(trial, config)
    score += intervention_boost
    logger.debug(
        f"Intervention boost: {intervention_boost} (interventions: {len(trial.interventions)})"
    )

    # Apply cap
    final_score = min(score, config.MAX_QUALITY_SCORE)

    logger.debug(f"Final quality score for {trial.nct_id}: {final_score:.3f}")

    return final_score


def _calculate_phase_score(
    trial: ClinicalTrialDocument, config: ClinicalTrialQualityConfig
) -> float:
    """Calculate phase-based quality boost."""
    if not trial.phase:
        return 0.0

    phase_weights = {
        "PHASE3": config.PHASE_3_BOOST,
        "PHASE2": config.PHASE_2_BOOST,
        "PHASE1_PHASE2": config.PHASE_1_PHASE_2_BOOST,
        "PHASE1": config.PHASE_1_BOOST,
        "EARLY_PHASE1": config.EARLY_PHASE_1_BOOST,
    }

    return phase_weights.get(trial.phase, 0.0)


def _calculate_sponsor_score(
    trial: ClinicalTrialDocument, config: ClinicalTrialQualityConfig
) -> float:
    """Calculate sponsor class quality boost."""
    if not trial.sponsor_class:
        return 0.0

    if trial.sponsor_class == "INDUSTRY":
        return config.INDUSTRY_SPONSOR_BOOST
    elif trial.sponsor_class == "ACADEMIC":
        return config.ACADEMIC_SPONSOR_BOOST
    elif trial.sponsor_class == "NIH":
        return config.NIH_SPONSOR_BOOST

    return 0.0


def _calculate_enrollment_score(
    trial: ClinicalTrialDocument, config: ClinicalTrialQualityConfig
) -> float:
    """Calculate enrollment size quality boost."""
    if not trial.enrollment_count or trial.enrollment_count <= 0:
        return 0.0

    if trial.enrollment_count >= config.LARGE_ENROLLMENT_THRESHOLD:
        return config.LARGE_ENROLLMENT_BOOST
    elif trial.enrollment_count >= config.MEDIUM_ENROLLMENT_THRESHOLD:
        return config.MEDIUM_ENROLLMENT_BOOST
    elif trial.enrollment_count >= config.SMALL_ENROLLMENT_THRESHOLD:
        return config.SMALL_ENROLLMENT_BOOST

    return 0.0


def _calculate_status_score(
    trial: ClinicalTrialDocument, config: ClinicalTrialQualityConfig
) -> float:
    """Calculate status-based quality boost."""
    if not trial.status:
        return 0.0

    active_statuses = [
        "RECRUITING",
        "ACTIVE_NOT_RECRUITING",
        "ENROLLING_BY_INVITATION",
    ]

    if trial.status in active_statuses:
        return config.ACTIVE_STATUS_BOOST
    elif trial.status == "COMPLETED":
        return config.COMPLETED_STATUS_BOOST

    return 0.0


def _calculate_results_score(
    trial: ClinicalTrialDocument, config: ClinicalTrialQualityConfig
) -> float:
    """Calculate results availability quality boost."""
    return config.RESULTS_AVAILABLE_BOOST if trial.has_results else 0.0


def _calculate_condition_score(
    trial: ClinicalTrialDocument, config: ClinicalTrialQualityConfig
) -> float:
    """Calculate high-value condition quality boost."""
    if not trial.conditions:
        return 0.0

    # Check if any condition matches high-value conditions
    for condition in trial.conditions:
        condition_lower = condition.lower()
        for high_value_condition in config.HIGH_VALUE_CONDITIONS:
            if high_value_condition in condition_lower:
                return config.HIGH_VALUE_CONDITION_BOOST

    return 0.0


def _calculate_intervention_score(
    trial: ClinicalTrialDocument, config: ClinicalTrialQualityConfig
) -> float:
    """Calculate investment-relevant intervention quality boost."""
    if not trial.interventions:
        return 0.0

    # Check if any intervention matches investment-relevant types
    for intervention in trial.interventions:
        intervention_lower = intervention.lower()
        for investment_intervention in config.INVESTMENT_INTERVENTIONS:
            if investment_intervention in intervention_lower:
                return config.INVESTMENT_INTERVENTION_BOOST

    return 0.0


def calculate_quality_metrics(trials: list[ClinicalTrialDocument]) -> dict[str, Any]:
    """
    Calculate aggregate quality metrics for a collection of trials.

    Args:
        trials: List of clinical trial documents

    Returns:
        Dictionary with quality metrics and statistics
    """
    if not trials:
        return {
            "total_trials": 0,
            "avg_quality_score": 0.0,
            "high_quality_count": 0,
            "investment_relevant_count": 0,
            "quality_distribution": {},
        }

    quality_scores = [calculate_clinical_trial_quality(trial) for trial in trials]

    # Calculate quality distribution
    quality_buckets = {
        "excellent": 0,  # 0.8+
        "good": 0,  # 0.6-0.79
        "moderate": 0,  # 0.4-0.59
        "poor": 0,  # <0.4
    }

    for score in quality_scores:
        if score >= 0.8:
            quality_buckets["excellent"] += 1
        elif score >= 0.6:
            quality_buckets["good"] += 1
        elif score >= 0.4:
            quality_buckets["moderate"] += 1
        else:
            quality_buckets["poor"] += 1

    # Investment relevance threshold (typically 0.6+)
    investment_relevant_count = sum(1 for score in quality_scores if score >= 0.6)

    return {
        "total_trials": len(trials),
        "avg_quality_score": sum(quality_scores) / len(quality_scores),
        "max_quality_score": max(quality_scores),
        "min_quality_score": min(quality_scores),
        "high_quality_count": sum(1 for score in quality_scores if score >= 0.7),
        "investment_relevant_count": investment_relevant_count,
        "investment_relevant_percentage": investment_relevant_count / len(trials) * 100,
        "quality_distribution": quality_buckets,
    }
