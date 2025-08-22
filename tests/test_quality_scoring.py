"""
Tests for quality scoring domain object.
Tests journal impact, recency, and legacy quality boost calculations.
"""

from datetime import UTC, datetime

import pytest

from bio_mcp.sources.pubmed.quality import JournalQualityScorer, QualityConfig


class TestQualityConfig:
    """Test quality configuration object."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = QualityConfig()

        assert config.JOURNAL_BOOST_FACTOR == 0.10
        assert config.RECENCY_BOOST_FACTOR == 0.05
        assert config.RECENT_YEARS_THRESHOLD == 2
        assert config.LEGACY_QUALITY_DIVISOR == 20
        assert "nature" in config.TIER_1_JOURNALS
        assert "science" in config.TIER_1_JOURNALS
        assert len(config.TIER_1_JOURNALS) == 6

    def test_config_is_frozen(self):
        """Test that config is immutable."""
        config = QualityConfig()

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            config.JOURNAL_BOOST_FACTOR = 0.20


class TestJournalQualityScorer:
    """Test journal quality scoring functionality."""

    def test_default_initialization(self):
        """Test scorer initializes with default config."""
        scorer = JournalQualityScorer()
        assert scorer.config is not None
        assert isinstance(scorer.config, QualityConfig)

    def test_custom_config_initialization(self):
        """Test scorer initializes with custom config."""
        custom_config = QualityConfig()
        scorer = JournalQualityScorer(custom_config)
        assert scorer.config is custom_config

    def test_journal_boost_tier_1_journals(self):
        """Test boost calculation for tier 1 journals."""
        scorer = JournalQualityScorer()

        # Test exact matches
        assert scorer._calculate_journal_boost("Nature") == 0.10
        assert scorer._calculate_journal_boost("Science") == 0.10
        assert scorer._calculate_journal_boost("Cell") == 0.10

        # Test case insensitive
        assert scorer._calculate_journal_boost("NATURE") == 0.10
        assert scorer._calculate_journal_boost("nature") == 0.10

        # Test partial matches (common journal naming)
        assert scorer._calculate_journal_boost("Nature Medicine") == 0.10
        assert (
            scorer._calculate_journal_boost("New England Journal of Medicine") == 0.10
        )

    def test_journal_boost_no_match(self):
        """Test no boost for non-tier 1 journals."""
        scorer = JournalQualityScorer()

        assert scorer._calculate_journal_boost("Journal of Generic Research") == 0.0
        assert scorer._calculate_journal_boost("PLOS ONE") == 0.0
        assert scorer._calculate_journal_boost("") == 0.0
        assert scorer._calculate_journal_boost(None) == 0.0

    def test_recency_boost_recent_papers(self):
        """Test recency boost for recent publications."""
        scorer = JournalQualityScorer()
        current_year = datetime.now(UTC).year

        # Test current year (should get boost)
        recent_date = datetime(current_year, 6, 15)
        assert scorer._calculate_recency_boost(recent_date) == 0.05

        # Test previous year (should get boost with threshold=2)
        last_year_date = datetime(current_year - 1, 6, 15)
        assert scorer._calculate_recency_boost(last_year_date) == 0.05

        # Test string format recent
        assert scorer._calculate_recency_boost(f"{current_year}-06-15") == 0.05
        assert scorer._calculate_recency_boost(f"{current_year - 1}-06-15") == 0.05

    def test_recency_boost_old_papers(self):
        """Test no boost for old publications."""
        scorer = JournalQualityScorer()
        current_year = datetime.now(UTC).year

        # Test old date (should not get boost)
        old_date = datetime(current_year - 5, 6, 15)
        assert scorer._calculate_recency_boost(old_date) == 0.0

        # Test string format old
        assert scorer._calculate_recency_boost(f"{current_year - 5}-06-15") == 0.0

        # Test invalid formats
        assert scorer._calculate_recency_boost("invalid-date") == 0.0
        assert scorer._calculate_recency_boost("") == 0.0
        assert scorer._calculate_recency_boost(None) == 0.0

    def test_legacy_boost_calculation(self):
        """Test legacy quality score boost calculation."""
        scorer = JournalQualityScorer()

        # Test positive quality scores
        assert scorer._calculate_legacy_boost(20) == 1.0  # 20/20
        assert scorer._calculate_legacy_boost(10) == 0.5  # 10/20
        assert scorer._calculate_legacy_boost(5) == 0.25  # 5/20

        # Test edge cases
        assert scorer._calculate_legacy_boost(0) == 0.0
        assert scorer._calculate_legacy_boost(None) == 0.0
        assert scorer._calculate_legacy_boost(-5) == 0.0  # Negative scores

    def test_calculate_quality_boost_combined(self):
        """Test combined quality boost calculation."""
        scorer = JournalQualityScorer()
        current_year = datetime.now(UTC).year

        # Test document with all boosts
        document_all_boosts = {
            "journal": "Nature Biotechnology",  # Journal boost: 0.10
            "publication_date": datetime(current_year, 1, 1),  # Recency boost: 0.05
            "quality_total": 10,  # Legacy boost: 0.5
        }

        total_boost = scorer.calculate_quality_boost(document_all_boosts)
        expected = 0.10 + 0.05 + 0.5  # 0.65 total boost
        assert abs(total_boost - expected) < 0.001

        # Test document with no boosts
        document_no_boosts = {
            "journal": "Generic Journal",
            "publication_date": datetime(current_year - 10, 1, 1),
            "quality_total": 0,
        }

        assert scorer.calculate_quality_boost(document_no_boosts) == 0.0

    def test_apply_quality_boost_sorting(self):
        """Test that quality boost is applied and results are sorted correctly."""
        scorer = JournalQualityScorer()
        current_year = datetime.now(UTC).year

        # Mock search results with different quality indicators
        results = [
            {
                "pmid": "test1",
                "title": "Test Paper 1",
                "journal": "Generic Journal",  # No journal boost
                "publication_date": f"{current_year - 5}-01-01",  # No recency boost
                "score": 0.9,  # High base score
                "quality_total": 0,
            },
            {
                "pmid": "test2",
                "title": "Test Paper 2",
                "journal": "Nature",  # Journal boost: 0.10
                "publication_date": f"{current_year}-01-01",  # Recency boost: 0.05
                "score": 0.7,  # Lower base score
                "quality_total": 10,  # Legacy boost: 0.5
            },
        ]

        boosted_results = scorer.apply_quality_boost(results)

        # Verify boosts were applied
        paper1 = next(r for r in boosted_results if r["pmid"] == "test1")
        paper2 = next(r for r in boosted_results if r["pmid"] == "test2")

        assert paper1["quality_boost"] == 0.0
        assert paper1["boosted_score"] == 0.9

        expected_boost2 = 0.10 + 0.05 + 0.5  # 0.65
        assert abs(paper2["quality_boost"] - expected_boost2) < 0.001
        expected_boosted_score2 = 0.7 * (1 + expected_boost2)
        assert abs(paper2["boosted_score"] - expected_boosted_score2) < 0.001

        # Verify sorting: paper2 should now rank higher despite lower base score
        assert boosted_results[0]["pmid"] == "test2"  # Should be first
        assert boosted_results[1]["pmid"] == "test1"  # Should be second

    def test_apply_quality_boost_zero_scores(self):
        """Test quality boost handling with zero scores."""
        scorer = JournalQualityScorer()

        results = [
            {
                "pmid": "test1",
                "journal": "Nature",
                "score": 0.0,  # Zero score
                "quality_total": 5,
            },
            {
                "pmid": "test2",
                "journal": "Science",
                "score": None,  # None score
                "quality_total": 10,
            },
        ]

        boosted_results = scorer.apply_quality_boost(results)

        # Should handle zero/None scores gracefully
        for result in boosted_results:
            assert "quality_boost" in result
            assert "boosted_score" in result
            # Zero scores should remain zero regardless of quality boost
            assert result["boosted_score"] in (0.0, None)


# Pytest configuration
pytestmark = pytest.mark.unit
