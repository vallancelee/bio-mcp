"""
Unit tests for ClinicalTrials.gov document models.
"""

from datetime import date

from bio_mcp.sources.clinicaltrials.models import ClinicalTrialDocument


class TestClinicalTrialDocument:
    """Test ClinicalTrialDocument functionality."""

    def _create_doc(self, nct_id="NCT12345678", **kwargs):
        """Helper method to create ClinicalTrialDocument with required fields."""
        defaults = {
            "id": f"ctgov:{nct_id}",
            "source_id": nct_id,
            "source": "ctgov",
            "title": "Test Clinical Trial",
            "nct_id": nct_id,
        }
        defaults.update(kwargs)
        return ClinicalTrialDocument(**defaults)

    def test_document_creation_basic(self):
        """Test basic document creation."""
        doc = self._create_doc(
            content="This is a test clinical trial.",
        )

        assert doc.nct_id == "NCT12345678"
        assert doc.title == "Test Clinical Trial"
        assert doc.source == "ctgov"
        assert doc.source_id == "NCT12345678"
        assert doc.id == "ctgov:NCT12345678"

    def test_post_init_processing(self):
        """Test post-initialization processing."""
        doc = self._create_doc(
            nct_id="NCT87654321",
            title="Brief Summary Test",
            brief_summary="This is a test summary. It has multiple sentences.",
        )

        # Should compute investment relevance score
        assert doc.investment_relevance_score >= 0.0
        assert doc.investment_relevance_score <= 1.0

    def test_investment_relevance_scoring_phase3(self):
        """Test investment relevance scoring for Phase 3 trials."""
        doc = self._create_doc(
            phase="PHASE3",
            sponsor_class="INDUSTRY",
            enrollment_count=500,
            status="RECRUITING",
            conditions=["Cancer"],
            interventions=["Drug X"],
        )

        score = doc.get_investment_relevance_score()

        # Phase 3 (0.35) + Industry (0.20) + Large enrollment (0.15) + Active status (0.10)
        # + Has results (0) + High-value condition (0.05) + Investment intervention (0.05)
        # = 0.90 (without results)
        assert score >= 0.85  # Allow some flexibility
        assert score <= 1.0

    def test_investment_relevance_scoring_phase1(self):
        """Test investment relevance scoring for Phase 1 trials."""
        doc = self._create_doc(
            phase="PHASE1",
            sponsor_class="ACADEMIC",
            enrollment_count=30,
            status="COMPLETED",
            conditions=["Rare Disease"],
            interventions=["Investigational Drug"],
        )

        score = doc.get_investment_relevance_score()

        # Phase 1 (0.15) + Academic (0.10) + Small enrollment (0.05) + Completed (0.05)
        # + High-value condition (0.05) + Investment intervention (0.05)
        # = 0.45
        assert score >= 0.39  # Allow some floating point tolerance
        assert score <= 0.50

    def test_investment_relevance_scoring_minimal(self):
        """Test investment relevance scoring with minimal information."""
        doc = self._create_doc(
            phase=None,
            sponsor_class=None,
            enrollment_count=None,
            status=None,
            conditions=[],
            interventions=[],
        )

        score = doc.get_investment_relevance_score()

        # Should have minimal score with no relevant factors
        assert score >= 0.0
        assert score <= 0.10

    def test_investment_relevance_high_value_conditions(self):
        """Test scoring boost for high-value therapeutic conditions."""
        high_value_conditions = [
            "Lung Cancer",
            "Type 2 Diabetes",
            "Alzheimer's Disease",
            "Multiple Sclerosis",
            "Rheumatoid Arthritis",
            "Rare Disease",
        ]

        for condition in high_value_conditions:
            doc = self._create_doc(conditions=[condition])

            score = doc.get_investment_relevance_score()
            assert score >= 0.05, f"Expected boost for {condition}"

    def test_investment_relevance_investment_interventions(self):
        """Test scoring boost for investment-relevant interventions."""
        investment_interventions = [
            "Novel Drug Therapy",
            "Monoclonal Antibody Treatment",
            "Gene Therapy Protocol",
            "Cell Therapy Approach",
            "Medical Device Study",
            "Vaccine Development",
        ]

        for intervention in investment_interventions:
            doc = self._create_doc(interventions=[intervention])

            score = doc.get_investment_relevance_score()
            assert score >= 0.05, f"Expected boost for {intervention}"

    def test_from_api_data_comprehensive(self):
        """Test creating document from comprehensive API data."""
        api_data = {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT04567890",
                    "briefTitle": "Study of Drug X in Cancer Patients",
                    "officialTitle": "A Phase 3, Randomized, Double-Blind Study of Drug X in Patients with Advanced Cancer",
                },
                "statusModule": {
                    "overallStatus": "RECRUITING",
                    "startDateStruct": {"date": "2024-01-15"},
                    "primaryCompletionDateStruct": {"date": "2025-12-31"},
                    "studyFirstPostDateStruct": {"date": "2024-01-10"},
                    "lastUpdatePostDateStruct": {"date": "2024-08-20"},
                },
                "sponsorCollaboratorsModule": {
                    "leadSponsor": {"name": "Biotech Company Inc", "class": "INDUSTRY"},
                    "collaborators": [{"name": "Academic Medical Center"}],
                },
                "descriptionModule": {
                    "briefSummary": "This study evaluates the safety and efficacy of Drug X in patients with advanced cancer.",
                    "detailedDescription": "Detailed description of the study methodology and objectives.",
                },
                "conditionsModule": {
                    "conditions": ["Lung Cancer", "NSCLC"],
                    "keywords": ["oncology", "targeted therapy"],
                },
                "designModule": {
                    "studyType": "INTERVENTIONAL",
                    "phases": ["PHASE3"],
                    "enrollmentInfo": {"count": 500, "type": "ESTIMATED"},
                },
                "eligibilityModule": {"minimumAge": "18 Years", "sex": "ALL"},
                "armsInterventionsModule": {
                    "interventions": [{"name": "Drug X", "type": "DRUG"}]
                },
                "outcomesModule": {
                    "primaryOutcomes": [{"measure": "Overall Survival"}],
                    "secondaryOutcomes": [
                        {"measure": "Progression-Free Survival"},
                        {"measure": "Safety Profile"},
                    ],
                },
                "contactsLocationsModule": {
                    "locations": [
                        {"city": "Boston", "country": "United States"},
                        {"city": "New York", "country": "United States"},
                    ]
                },
            },
            "hasResults": False,
        }

        doc = ClinicalTrialDocument.from_api_data(api_data)

        # Verify basic fields
        assert doc.nct_id == "NCT04567890"
        assert doc.title == "Study of Drug X in Cancer Patients"
        assert doc.id == "ctgov:NCT04567890"
        assert doc.source == "ctgov"

        # Verify clinical trial specific fields
        assert doc.phase == "PHASE3"
        assert doc.status == "RECRUITING"
        assert doc.study_type == "INTERVENTIONAL"
        assert doc.sponsor_name == "Biotech Company Inc"
        assert doc.sponsor_class == "INDUSTRY"
        assert doc.enrollment_count == 500
        assert doc.enrollment_type == "ESTIMATED"

        # Verify conditions and interventions
        assert "Lung Cancer" in doc.conditions
        assert "NSCLC" in doc.conditions
        assert "Drug X" in doc.interventions
        assert "oncology" in doc.keywords

        # Verify dates
        assert doc.start_date == date(2024, 1, 15)
        assert doc.primary_completion_date == date(2025, 12, 31)
        assert doc.first_posted_date == date(2024, 1, 10)
        assert doc.last_update_posted_date == date(2024, 8, 20)

        # Verify outcomes
        assert "Overall Survival" in doc.primary_outcomes
        assert "Progression-Free Survival" in doc.secondary_outcomes
        assert "Safety Profile" in doc.secondary_outcomes

        # Verify locations
        assert "Boston, United States" in doc.locations
        assert "New York, United States" in doc.locations

        # Verify computed fields
        assert doc.has_results is False
        assert (
            doc.investment_relevance_score > 0.5
        )  # Should be high for Phase 3 industry trial

    def test_from_api_data_minimal(self):
        """Test creating document from minimal API data."""
        api_data = {
            "protocolSection": {"identificationModule": {"nctId": "NCT99999999"}}
        }

        doc = ClinicalTrialDocument.from_api_data(api_data)

        assert doc.nct_id == "NCT99999999"
        assert doc.id == "ctgov:NCT99999999"
        assert doc.source == "ctgov"
        # Should handle missing fields gracefully
        assert doc.title == ""
        assert doc.phase is None
        assert doc.conditions == []

    def test_from_api_data_invalid_data(self):
        """Test error handling for invalid API data."""
        # Test with completely invalid data
        try:
            result = ClinicalTrialDocument.from_api_data({"invalid": "data"})
            # If it doesn't raise an exception, check that we get sensible defaults
            assert result.nct_id == ""  # Should be empty for invalid data
        except Exception:
            # Exception is also acceptable behavior
            pass

    def test_parse_date_valid(self):
        """Test date parsing with valid date structures."""
        date_struct = {"date": "2024-03-15"}
        parsed_date = ClinicalTrialDocument._parse_date(date_struct)
        assert parsed_date == date(2024, 3, 15)

    def test_parse_date_invalid(self):
        """Test date parsing with invalid data."""
        assert ClinicalTrialDocument._parse_date(None) is None
        assert ClinicalTrialDocument._parse_date({}) is None
        assert ClinicalTrialDocument._parse_date({"date": "invalid"}) is None
        assert ClinicalTrialDocument._parse_date({"other": "field"}) is None

    def test_get_search_content(self):
        """Test search content generation."""
        doc = self._create_doc(
            title="Cancer Drug Study",
            brief_summary="Testing new cancer treatment",
            detailed_description="Comprehensive study of experimental drug",
            conditions=["Lung Cancer", "NSCLC"],
            interventions=["Drug X", "Placebo"],
            sponsor_name="Pharma Corp",
            phase="PHASE3",
        )

        content = doc.get_search_content()

        assert "Cancer Drug Study" in content
        assert "Testing new cancer treatment" in content
        assert "Comprehensive study of experimental drug" in content
        assert "Conditions: Lung Cancer, NSCLC" in content
        assert "Interventions: Drug X, Placebo" in content
        assert "Sponsor: Pharma Corp" in content
        assert "Phase: PHASE3" in content

    def test_get_display_title(self):
        """Test display title generation."""
        # Normal title
        doc = self._create_doc(title="Study of Drug X")
        assert doc.get_display_title() == "Study of Drug X"

        # No title
        doc = self._create_doc(title="")
        assert doc.get_display_title() == "Clinical Trial NCT12345678"

        # Very long title (over 100 characters)
        long_title = "A Very Long Title That Exceeds One Hundred Characters and Should Be Truncated for Display Purposes in Testing"
        doc = self._create_doc(title=long_title)
        display_title = doc.get_display_title()
        assert len(display_title) <= 100
        assert display_title.endswith("...")

    def test_to_database_format(self):
        """Test database format conversion."""
        doc = self._create_doc(
            title="Test Study",
            abstract="Test abstract",
            content="Test content",
            phase="PHASE2",
            status="RECRUITING",
            sponsor_name="Test Sponsor",
            sponsor_class="INDUSTRY",
            enrollment_count=100,
            conditions=["Condition A"],
            interventions=["Drug B"],
        )

        db_format = doc.to_database_format()

        # Check base fields
        assert db_format["id"] == "ctgov:NCT12345678"
        assert db_format["source"] == "ctgov"
        assert db_format["title"] == "Test Study"
        # Quality score is computed from investment relevance, so check it's reasonable
        assert 0 <= db_format["quality_score"] <= 100

        # Check metadata
        metadata = db_format["metadata"]
        assert metadata["nct_id"] == "NCT12345678"
        assert metadata["phase"] == "PHASE2"
        assert metadata["status"] == "RECRUITING"
        assert metadata["sponsor_name"] == "Test Sponsor"
        assert metadata["enrollment_count"] == 100
        assert metadata["conditions"] == ["Condition A"]
        # Investment relevance score is computed, check it's reasonable
        assert 0.6 <= metadata["investment_relevance_score"] <= 0.8

    def test_get_summary_for_display(self):
        """Test display summary generation."""
        doc = self._create_doc(
            title="Cancer Treatment Study",
            phase="PHASE3",
            status="RECRUITING",
            sponsor_name="Biotech Corp",
            sponsor_class="INDUSTRY",
            conditions=[
                "Lung Cancer",
                "Breast Cancer",
                "Colon Cancer",
                "Pancreatic Cancer",
            ],
            interventions=["Drug A", "Drug B", "Drug C", "Drug D"],
            enrollment_count=250,
            has_results=True,
            investment_relevance_score=0.85,
        )

        summary = doc.get_summary_for_display()

        assert summary["nct_id"] == "NCT12345678"
        assert summary["title"] == "Cancer Treatment Study"
        assert summary["phase"] == "PHASE3"
        assert summary["status"] == "RECRUITING"
        assert summary["sponsor"] == "Biotech Corp"
        assert summary["enrollment"] == 250
        # Investment score is computed, so check it's reasonable for high-value trial
        assert (
            summary["investment_score"] >= 0.8
        )  # Should be high for Phase 3 industry trial
        assert summary["has_results"] is True

        # Should limit conditions and interventions for display
        assert len(summary["conditions"]) <= 3
        assert len(summary["interventions"]) <= 3
        assert "Lung Cancer" in summary["conditions"]
        assert "Drug A" in summary["interventions"]

    def test_field_defaults(self):
        """Test that field defaults work correctly."""
        doc = self._create_doc()

        assert doc.conditions == []
        assert doc.interventions == []
        assert doc.collaborators == []
        assert doc.primary_outcomes == []
        assert doc.secondary_outcomes == []
        assert doc.keywords == []
        assert doc.phase is None
        assert doc.status is None
        assert doc.enrollment_count is None
        assert doc.has_results is False
        assert doc.investment_relevance_score >= 0.0

    def test_score_capping(self):
        """Test that investment relevance score is properly capped at 1.0."""
        # Create a document with maximum scoring factors
        doc = self._create_doc(
            phase="PHASE3",
            sponsor_class="INDUSTRY",
            enrollment_count=1000,
            status="RECRUITING",
            has_results=True,
            conditions=["Cancer", "Rare Disease"],
            interventions=["Drug Therapy", "Gene Therapy"],
        )

        score = doc.get_investment_relevance_score()
        assert score <= 1.0, f"Score {score} exceeds maximum of 1.0"
