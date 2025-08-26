"""
Unit tests for clinical trial quality scoring.
"""

from datetime import datetime

import pytest

from bio_mcp.sources.clinicaltrials.models import ClinicalTrialDocument


def create_test_trial(**kwargs) -> ClinicalTrialDocument:
    """Helper to create test clinical trial document with required base fields."""
    # Set required base document fields
    nct_id = kwargs.get("nct_id", "NCT12345678")
    base_fields = {
        "id": f"ctgov:{nct_id}",
        "source_id": nct_id,
        "source": "ctgov",
        "title": kwargs.get("title", "Test Clinical Trial"),
    }
    
    # Merge with provided kwargs
    all_fields = {**base_fields, **kwargs}
    return ClinicalTrialDocument(**all_fields)
from bio_mcp.sources.clinicaltrials.quality import (
    ClinicalTrialQualityConfig,
    _calculate_condition_score,
    _calculate_enrollment_score,
    _calculate_intervention_score,
    _calculate_phase_score,
    _calculate_results_score,
    _calculate_sponsor_score,
    _calculate_status_score,
    calculate_clinical_trial_quality,
    calculate_quality_metrics,
)


class TestClinicalTrialQualityConfig:
    """Test ClinicalTrialQualityConfig dataclass."""
    
    def test_default_config_creation(self):
        """Test creating default configuration."""
        config = ClinicalTrialQualityConfig()
        
        # Verify key parameters
        assert config.PHASE_3_BOOST == 0.30
        assert config.INDUSTRY_SPONSOR_BOOST == 0.15
        assert config.LARGE_ENROLLMENT_THRESHOLD == 500
        assert config.BASE_QUALITY_SCORE == 0.4
        assert config.MAX_QUALITY_SCORE == 1.0
        
        # Verify high-value conditions include key areas
        assert "cancer" in config.HIGH_VALUE_CONDITIONS
        assert "diabetes" in config.HIGH_VALUE_CONDITIONS
        assert "alzheimer" in config.HIGH_VALUE_CONDITIONS
        assert "rare disease" in config.HIGH_VALUE_CONDITIONS
        
        # Verify investment interventions
        assert "monoclonal antibody" in config.INVESTMENT_INTERVENTIONS
        assert "gene therapy" in config.INVESTMENT_INTERVENTIONS
        assert "drug" in config.INVESTMENT_INTERVENTIONS


class TestPhaseScoring:
    """Test phase-based quality scoring."""
    
    def test_phase_3_highest_score(self):
        """Test Phase 3 trials get highest phase score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(phase="PHASE3")
        
        score = _calculate_phase_score(trial, config)
        assert score == config.PHASE_3_BOOST
    
    def test_phase_2_moderate_score(self):
        """Test Phase 2 trials get moderate score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(phase="PHASE2")
        
        score = _calculate_phase_score(trial, config)
        assert score == config.PHASE_2_BOOST
        assert score < config.PHASE_3_BOOST
    
    def test_phase_1_lower_score(self):
        """Test Phase 1 trials get lower score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(phase="PHASE1")
        
        score = _calculate_phase_score(trial, config)
        assert score == config.PHASE_1_BOOST
        assert score < config.PHASE_2_BOOST
    
    def test_no_phase_zero_score(self):
        """Test trials without phase get zero score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", phase=None)
        
        score = _calculate_phase_score(trial, config)
        assert score == 0.0


class TestSponsorScoring:
    """Test sponsor-based quality scoring."""
    
    def test_industry_sponsor_highest_score(self):
        """Test industry sponsors get highest score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", sponsor_class="INDUSTRY")
        
        score = _calculate_sponsor_score(trial, config)
        assert score == config.INDUSTRY_SPONSOR_BOOST
    
    def test_academic_sponsor_moderate_score(self):
        """Test academic sponsors get moderate score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", sponsor_class="ACADEMIC")
        
        score = _calculate_sponsor_score(trial, config)
        assert score == config.ACADEMIC_SPONSOR_BOOST
        assert score < config.INDUSTRY_SPONSOR_BOOST
    
    def test_nih_sponsor_lower_score(self):
        """Test NIH sponsors get lower score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", sponsor_class="NIH")
        
        score = _calculate_sponsor_score(trial, config)
        assert score == config.NIH_SPONSOR_BOOST
        assert score < config.ACADEMIC_SPONSOR_BOOST
    
    def test_no_sponsor_zero_score(self):
        """Test trials without sponsor class get zero score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", sponsor_class=None)
        
        score = _calculate_sponsor_score(trial, config)
        assert score == 0.0


class TestEnrollmentScoring:
    """Test enrollment-based quality scoring."""
    
    def test_large_enrollment_highest_score(self):
        """Test large enrollment gets highest score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", enrollment_count=1000)
        
        score = _calculate_enrollment_score(trial, config)
        assert score == config.LARGE_ENROLLMENT_BOOST
    
    def test_medium_enrollment_moderate_score(self):
        """Test medium enrollment gets moderate score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", enrollment_count=200)
        
        score = _calculate_enrollment_score(trial, config)
        assert score == config.MEDIUM_ENROLLMENT_BOOST
        assert score < config.LARGE_ENROLLMENT_BOOST
    
    def test_small_enrollment_lower_score(self):
        """Test small enrollment gets lower score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", enrollment_count=75)
        
        score = _calculate_enrollment_score(trial, config)
        assert score == config.SMALL_ENROLLMENT_BOOST
        assert score < config.MEDIUM_ENROLLMENT_BOOST
    
    def test_tiny_enrollment_zero_score(self):
        """Test very small enrollment gets zero score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", enrollment_count=25)
        
        score = _calculate_enrollment_score(trial, config)
        assert score == 0.0
    
    def test_no_enrollment_zero_score(self):
        """Test trials without enrollment get zero score."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", enrollment_count=None)
        
        score = _calculate_enrollment_score(trial, config)
        assert score == 0.0


class TestStatusScoring:
    """Test status-based quality scoring."""
    
    def test_recruiting_status_boost(self):
        """Test recruiting status gets boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", status="RECRUITING")
        
        score = _calculate_status_score(trial, config)
        assert score == config.ACTIVE_STATUS_BOOST
    
    def test_active_not_recruiting_boost(self):
        """Test active not recruiting gets boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", status="ACTIVE_NOT_RECRUITING")
        
        score = _calculate_status_score(trial, config)
        assert score == config.ACTIVE_STATUS_BOOST
    
    def test_completed_status_lower_boost(self):
        """Test completed status gets lower boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", status="COMPLETED")
        
        score = _calculate_status_score(trial, config)
        assert score == config.COMPLETED_STATUS_BOOST
        assert score < config.ACTIVE_STATUS_BOOST
    
    def test_terminated_status_zero_boost(self):
        """Test terminated status gets zero boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", status="TERMINATED")
        
        score = _calculate_status_score(trial, config)
        assert score == 0.0


class TestResultsScoring:
    """Test results availability scoring."""
    
    def test_has_results_boost(self):
        """Test trials with results get boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", has_results=True)
        
        score = _calculate_results_score(trial, config)
        assert score == config.RESULTS_AVAILABLE_BOOST
    
    def test_no_results_zero_boost(self):
        """Test trials without results get zero boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", has_results=False)
        
        score = _calculate_results_score(trial, config)
        assert score == 0.0


class TestConditionScoring:
    """Test condition-based quality scoring."""
    
    def test_cancer_condition_boost(self):
        """Test cancer conditions get boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(
            nct_id="NCT12345678", 
            conditions=["Lung Cancer", "NSCLC"]
        )
        
        score = _calculate_condition_score(trial, config)
        assert score == config.HIGH_VALUE_CONDITION_BOOST
    
    def test_diabetes_condition_boost(self):
        """Test diabetes conditions get boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(
            nct_id="NCT12345678",
            conditions=["Type 2 Diabetes Mellitus"]
        )
        
        score = _calculate_condition_score(trial, config)
        assert score == config.HIGH_VALUE_CONDITION_BOOST
    
    def test_rare_disease_condition_boost(self):
        """Test rare disease conditions get boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(
            nct_id="NCT12345678",
            conditions=["Rare Genetic Disorder"]
        )
        
        score = _calculate_condition_score(trial, config)
        assert score == config.HIGH_VALUE_CONDITION_BOOST
    
    def test_common_condition_no_boost(self):
        """Test common conditions get no boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(
            nct_id="NCT12345678",
            conditions=["Common Cold", "Seasonal Allergies"]
        )
        
        score = _calculate_condition_score(trial, config)
        assert score == 0.0
    
    def test_no_conditions_zero_boost(self):
        """Test trials without conditions get zero boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", conditions=[])
        
        score = _calculate_condition_score(trial, config)
        assert score == 0.0


class TestInterventionScoring:
    """Test intervention-based quality scoring."""
    
    def test_monoclonal_antibody_boost(self):
        """Test monoclonal antibody interventions get boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(
            nct_id="NCT12345678",
            interventions=["Anti-PD1 Monoclonal Antibody"]
        )
        
        score = _calculate_intervention_score(trial, config)
        assert score == config.INVESTMENT_INTERVENTION_BOOST
    
    def test_gene_therapy_boost(self):
        """Test gene therapy interventions get boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(
            nct_id="NCT12345678",
            interventions=["CAR-T Cell Gene Therapy"]
        )
        
        score = _calculate_intervention_score(trial, config)
        assert score == config.INVESTMENT_INTERVENTION_BOOST
    
    def test_drug_intervention_boost(self):
        """Test drug interventions get boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(
            nct_id="NCT12345678",
            interventions=["Experimental Drug XYZ"]
        )
        
        score = _calculate_intervention_score(trial, config)
        assert score == config.INVESTMENT_INTERVENTION_BOOST
    
    def test_behavioral_intervention_no_boost(self):
        """Test behavioral interventions get no boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(
            nct_id="NCT12345678",
            interventions=["Behavioral Therapy", "Exercise Program"]
        )
        
        score = _calculate_intervention_score(trial, config)
        assert score == 0.0
    
    def test_no_interventions_zero_boost(self):
        """Test trials without interventions get zero boost."""
        config = ClinicalTrialQualityConfig()
        trial = create_test_trial(nct_id="NCT12345678", interventions=[])
        
        score = _calculate_intervention_score(trial, config)
        assert score == 0.0


class TestCalculateClinicalTrialQuality:
    """Test main quality calculation function."""
    
    def test_high_quality_phase3_industry_trial(self):
        """Test high-quality Phase 3 industry trial gets high score."""
        trial = create_test_trial(
            nct_id="NCT12345678",
            title="Phase 3 Cancer Drug Study",
            phase="PHASE3",
            sponsor_class="INDUSTRY",
            enrollment_count=800,
            status="RECRUITING",
            has_results=False,
            conditions=["Lung Cancer"],
            interventions=["Monoclonal Antibody XYZ"],
        )
        
        score = calculate_clinical_trial_quality(trial)
        
        # Should be high quality (>0.8)
        assert score > 0.8
        assert score <= 1.0
    
    def test_moderate_quality_phase2_academic_trial(self):
        """Test moderate quality Phase 2 academic trial."""
        trial = create_test_trial(
            nct_id="NCT87654321",
            title="Phase 2 Diabetes Study",
            phase="PHASE2",
            sponsor_class="ACADEMIC",
            enrollment_count=150,
            status="ACTIVE_NOT_RECRUITING",
            has_results=True,
            conditions=["Type 2 Diabetes"],
            interventions=["Experimental Drug ABC"],
        )
        
        score = calculate_clinical_trial_quality(trial)
        
        # Should be moderate to high quality (0.5-1.0)
        assert 0.5 <= score <= 1.0
    
    def test_low_quality_early_phase_trial(self):
        """Test low quality early phase trial."""
        trial = create_test_trial(
            nct_id="NCT11111111",
            title="Early Phase 1 Safety Study",
            phase="EARLY_PHASE1",
            sponsor_class="ACADEMIC",
            enrollment_count=20,
            status="COMPLETED",
            has_results=False,
            conditions=["Healthy Volunteers"],
            interventions=["Behavioral Intervention"],
        )
        
        score = calculate_clinical_trial_quality(trial)
        
        # Should be low quality (<0.6)
        assert score < 0.6
    
    def test_score_capped_at_maximum(self):
        """Test quality score is properly capped."""
        # Create a trial that would theoretically score >1.0
        trial = create_test_trial(
            nct_id="NCT99999999",
            title="Perfect Trial",
            phase="PHASE3",
            sponsor_class="INDUSTRY",
            enrollment_count=2000,
            status="RECRUITING",
            has_results=True,
            conditions=["Cancer", "Rare Disease", "Alzheimer"],
            interventions=["Gene Therapy", "Monoclonal Antibody", "CAR-T Cell Therapy"],
        )
        
        score = calculate_clinical_trial_quality(trial)
        assert score == 1.0  # Should be capped at maximum
    
    def test_custom_config(self):
        """Test quality calculation with custom configuration."""
        custom_config = ClinicalTrialQualityConfig(
            PHASE_3_BOOST=0.5,  # Higher boost for Phase 3
            INDUSTRY_SPONSOR_BOOST=0.3,  # Higher boost for industry
        )
        
        trial = create_test_trial(
            nct_id="NCT12345678",
            phase="PHASE3",
            sponsor_class="INDUSTRY",
        )
        
        default_score = calculate_clinical_trial_quality(trial)
        custom_score = calculate_clinical_trial_quality(trial, custom_config)
        
        # Custom config should give higher score
        assert custom_score > default_score
    
    def test_minimal_trial_gets_base_score(self):
        """Test minimal trial gets approximately base score."""
        trial = create_test_trial(nct_id="NCT00000000")  # Only required field
        
        score = calculate_clinical_trial_quality(trial)
        
        config = ClinicalTrialQualityConfig()
        # Should be close to base score (might be slightly different due to rounding)
        assert abs(score - config.BASE_QUALITY_SCORE) < 0.05


class TestCalculateQualityMetrics:
    """Test aggregate quality metrics calculation."""
    
    def test_empty_trials_list(self):
        """Test quality metrics for empty trials list."""
        metrics = calculate_quality_metrics([])
        
        assert metrics["total_trials"] == 0
        assert metrics["avg_quality_score"] == 0.0
        assert metrics["high_quality_count"] == 0
        assert metrics["investment_relevant_count"] == 0
    
    def test_mixed_quality_trials(self):
        """Test quality metrics for mixed quality trials."""
        trials = [
            # High quality trial
            create_test_trial(
                nct_id="NCT11111111",
                phase="PHASE3",
                sponsor_class="INDUSTRY",
                enrollment_count=500,
                status="RECRUITING",
                conditions=["Cancer"],
                interventions=["Monoclonal Antibody"],
            ),
            # Moderate quality trial
            create_test_trial(
                nct_id="NCT22222222",
                phase="PHASE2",
                sponsor_class="ACADEMIC",
                enrollment_count=100,
                status="COMPLETED",
                conditions=["Diabetes"],
            ),
            # Low quality trial
            create_test_trial(
                nct_id="NCT33333333",
                phase="PHASE1",
                enrollment_count=30,
                status="TERMINATED",
            ),
        ]
        
        metrics = calculate_quality_metrics(trials)
        
        assert metrics["total_trials"] == 3
        assert metrics["avg_quality_score"] > 0.0
        assert "quality_distribution" in metrics
        assert "investment_relevant_count" in metrics
        assert "investment_relevant_percentage" in metrics
        
        # Should have at least one high-quality trial
        assert metrics["high_quality_count"] >= 1
    
    def test_quality_distribution_buckets(self):
        """Test quality distribution bucket calculation."""
        # Create trials with known quality ranges
        high_quality_trial = create_test_trial(
            nct_id="NCT11111111",
            phase="PHASE3",
            sponsor_class="INDUSTRY", 
            enrollment_count=1000,
            status="RECRUITING",
            conditions=["Cancer"],
            interventions=["Gene Therapy"],
        )
        
        poor_quality_trial = create_test_trial(
            nct_id="NCT22222222",
            # Minimal fields only
        )
        
        trials = [high_quality_trial, poor_quality_trial]
        metrics = calculate_quality_metrics(trials)
        
        distribution = metrics["quality_distribution"]
        assert "excellent" in distribution
        assert "good" in distribution 
        assert "moderate" in distribution
        assert "poor" in distribution
        
        # Should have at least one trial in excellent or good category
        assert distribution["excellent"] + distribution["good"] >= 1
        
        # Should have at least one trial in lower quality categories (poor or moderate)
        assert distribution["poor"] + distribution["moderate"] >= 1


@pytest.fixture
def sample_trial():
    """Create a sample clinical trial for testing."""
    return create_test_trial(
        nct_id="NCT12345678",
        title="Test Clinical Trial",
        phase="PHASE2",
        sponsor_class="INDUSTRY",
        enrollment_count=200,
        status="RECRUITING",
        conditions=["Cancer"],
        interventions=["Drug X"],
        has_results=False,
        publication_date=datetime(2024, 1, 15),
    )


def test_sample_trial_fixture(sample_trial):
    """Test the sample trial fixture."""
    assert sample_trial.nct_id == "NCT12345678"
    assert sample_trial.phase == "PHASE2"
    assert sample_trial.sponsor_class == "INDUSTRY"
    
    # Should get moderate to high quality score
    score = calculate_clinical_trial_quality(sample_trial)
    assert 0.5 <= score <= 1.0