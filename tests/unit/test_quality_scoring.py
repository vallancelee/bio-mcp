"""
Unit tests for quality scoring functionality.
"""

from datetime import UTC, datetime

import pytest

from bio_mcp.sources.pubmed.quality import JournalQualityScorer, QualityConfig


class TestQualityConfig:
    """Test quality configuration parameters."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = QualityConfig()
        
        assert config.JOURNAL_BOOST_FACTOR == 0.10
        assert config.RECENCY_BOOST_FACTOR == 0.05
        assert config.RECENT_YEARS_THRESHOLD == 2
        assert config.LEGACY_QUALITY_DIVISOR == 20
        assert config.INVESTMENT_BOOST_FACTOR == 0.08
    
    def test_tier_1_journals_frozen(self):
        """Test that tier 1 journals is a frozen set."""
        config = QualityConfig()
        
        assert isinstance(config.TIER_1_JOURNALS, frozenset)
        assert "nature" in config.TIER_1_JOURNALS
        assert "science" in config.TIER_1_JOURNALS
        assert "cell" in config.TIER_1_JOURNALS
        assert "lancet" in config.TIER_1_JOURNALS
        assert "nejm" in config.TIER_1_JOURNALS
        assert "new england journal of medicine" in config.TIER_1_JOURNALS
    
    def test_investment_keywords_frozen(self):
        """Test that investment keywords is a frozen set."""
        config = QualityConfig()
        
        assert isinstance(config.INVESTMENT_KEYWORDS, frozenset)
        assert "clinical trial" in config.INVESTMENT_KEYWORDS
        assert "fda approval" in config.INVESTMENT_KEYWORDS
        assert "biotech" in config.INVESTMENT_KEYWORDS
        assert "pharma" in config.INVESTMENT_KEYWORDS
        assert "precision medicine" in config.INVESTMENT_KEYWORDS
    
    def test_config_is_frozen(self):
        """Test that QualityConfig is immutable."""
        config = QualityConfig()
        
        with pytest.raises(AttributeError):
            config.JOURNAL_BOOST_FACTOR = 0.20


class TestJournalQualityScorer:
    """Test journal quality scoring functionality."""
    
    def test_scorer_initialization(self):
        """Test scorer initialization with and without config."""
        # Default config
        scorer = JournalQualityScorer()
        assert scorer.config is not None
        assert isinstance(scorer.config, QualityConfig)
        
        # Custom config
        custom_config = QualityConfig()
        scorer_custom = JournalQualityScorer(custom_config)
        assert scorer_custom.config is custom_config
    
    def test_calculate_journal_boost_tier1(self):
        """Test journal boost calculation for tier 1 journals."""
        scorer = JournalQualityScorer()
        
        # Test exact matches
        assert scorer._calculate_journal_boost("Nature") == 0.10
        assert scorer._calculate_journal_boost("Science") == 0.10
        assert scorer._calculate_journal_boost("Cell") == 0.10
        assert scorer._calculate_journal_boost("The Lancet") == 0.10
        assert scorer._calculate_journal_boost("NEJM") == 0.10
        assert scorer._calculate_journal_boost("New England Journal of Medicine") == 0.10
        
        # Test case insensitive
        assert scorer._calculate_journal_boost("NATURE") == 0.10
        assert scorer._calculate_journal_boost("science") == 0.10
        
        # Test partial matches in journal names
        assert scorer._calculate_journal_boost("Nature Biotechnology") == 0.10
        assert scorer._calculate_journal_boost("Cell Reports") == 0.10
    
    def test_calculate_journal_boost_non_tier1(self):
        """Test journal boost for non-tier 1 journals."""
        scorer = JournalQualityScorer()
        
        assert scorer._calculate_journal_boost("PLoS ONE") == 0.0
        assert scorer._calculate_journal_boost("Journal of Biology") == 0.0
        assert scorer._calculate_journal_boost("") == 0.0
        assert scorer._calculate_journal_boost("Random Journal") == 0.0
    
    def test_calculate_recency_boost_datetime(self):
        """Test recency boost calculation with datetime objects."""
        scorer = JournalQualityScorer()
        current_year = datetime.now(UTC).year
        
        # Recent publication (current year)
        recent_date = datetime(current_year, 6, 15)
        assert scorer._calculate_recency_boost(recent_date) == 0.05
        
        # Recent publication (last year)
        last_year_date = datetime(current_year - 1, 6, 15)
        assert scorer._calculate_recency_boost(last_year_date) == 0.05
        
        # Old publication (3 years ago)
        old_date = datetime(current_year - 3, 6, 15)
        assert scorer._calculate_recency_boost(old_date) == 0.0
        
        # Very old publication
        very_old_date = datetime(2010, 6, 15)
        assert scorer._calculate_recency_boost(very_old_date) == 0.0
    
    def test_calculate_recency_boost_string(self):
        """Test recency boost calculation with string dates."""
        scorer = JournalQualityScorer()
        current_year = datetime.now(UTC).year
        
        # Recent year string
        assert scorer._calculate_recency_boost(str(current_year)) == 0.05
        assert scorer._calculate_recency_boost(f"{current_year}-06-15") == 0.05
        assert scorer._calculate_recency_boost(str(current_year - 1)) == 0.05
        
        # Old year string
        assert scorer._calculate_recency_boost(str(current_year - 3)) == 0.0
        assert scorer._calculate_recency_boost("2010") == 0.0
        
        # Invalid strings
        assert scorer._calculate_recency_boost("invalid") == 0.0
        assert scorer._calculate_recency_boost("abc") == 0.0
        assert scorer._calculate_recency_boost("") == 0.0
    
    def test_calculate_recency_boost_edge_cases(self):
        """Test recency boost calculation edge cases."""
        scorer = JournalQualityScorer()
        
        assert scorer._calculate_recency_boost(None) == 0.0
        assert scorer._calculate_recency_boost("") == 0.0
        assert scorer._calculate_recency_boost("abc") == 0.0
        assert scorer._calculate_recency_boost(123) == 0.0
    
    def test_calculate_legacy_boost(self):
        """Test legacy quality score boost calculation."""
        scorer = JournalQualityScorer()
        
        # Valid legacy scores
        assert scorer._calculate_legacy_boost(100) == 5.0  # 100/20
        assert scorer._calculate_legacy_boost(40) == 2.0   # 40/20
        assert scorer._calculate_legacy_boost(1) == 0.05   # 1/20
        
        # Zero or negative scores
        assert scorer._calculate_legacy_boost(0) == 0.0
        assert scorer._calculate_legacy_boost(-10) == 0.0
        
        # None value
        assert scorer._calculate_legacy_boost(None) == 0.0
    
    def test_calculate_investment_boost(self):
        """Test investment relevance boost calculation."""
        scorer = JournalQualityScorer()
        
        # Document with investment keywords in title
        doc = {
            "title": "Phase II Clinical Trial of Novel Biotech Drug",
            "abstract": "",
            "keywords": [],
            "mesh_terms": []
        }
        boost = scorer._calculate_investment_boost(doc)
        assert boost > 0
        assert boost <= 0.08  # Max boost
        
        # Document with keywords in abstract
        doc = {
            "title": "Cancer Research",
            "abstract": "FDA approval pending for this therapeutic intervention",
            "keywords": [],
            "mesh_terms": []
        }
        boost = scorer._calculate_investment_boost(doc)
        assert boost > 0
        
        # Document with keywords in keywords field
        doc = {
            "title": "Treatment Study",
            "abstract": "",
            "keywords": ["precision medicine", "biomarker"],
            "mesh_terms": []
        }
        boost = scorer._calculate_investment_boost(doc)
        assert boost > 0
        
        # Document with keywords in mesh terms
        doc = {
            "title": "Medical Research",
            "abstract": "",
            "keywords": [],
            "mesh_terms": ["Drug Development", "Commercial"]
        }
        boost = scorer._calculate_investment_boost(doc)
        assert boost > 0
    
    def test_calculate_investment_boost_scaling(self):
        """Test investment boost scaling with multiple keywords."""
        scorer = JournalQualityScorer()
        
        # One keyword
        doc_one = {
            "title": "Clinical trial results",
            "abstract": "",
            "keywords": [],
            "mesh_terms": []
        }
        boost_one = scorer._calculate_investment_boost(doc_one)
        
        # Three keywords (should get full boost)
        doc_three = {
            "title": "Phase II clinical trial for FDA approval",
            "abstract": "Biotech company pipeline study",
            "keywords": [],
            "mesh_terms": []
        }
        boost_three = scorer._calculate_investment_boost(doc_three)
        
        # Multiple keywords should give higher boost (up to max)
        assert boost_three >= boost_one
        assert boost_three <= 0.08  # Max boost factor
    
    def test_calculate_investment_boost_no_keywords(self):
        """Test investment boost with no relevant keywords."""
        scorer = JournalQualityScorer()
        
        doc = {
            "title": "Basic Biology Research",
            "abstract": "Fundamental cellular mechanisms",
            "keywords": ["biology", "cells"],
            "mesh_terms": ["Cells", "Biology"]
        }
        
        boost = scorer._calculate_investment_boost(doc)
        assert boost == 0.0
    
    def test_calculate_investment_boost_empty_document(self):
        """Test investment boost with empty document."""
        scorer = JournalQualityScorer()
        
        doc = {}
        boost = scorer._calculate_investment_boost(doc)
        assert boost == 0.0
    
    def test_calculate_quality_boost_comprehensive(self):
        """Test comprehensive quality boost calculation."""
        scorer = JournalQualityScorer()
        current_year = datetime.now(UTC).year
        
        # Document with all boost factors
        doc = {
            "journal": "Nature Biotechnology",  # Journal boost: 0.10
            "publication_date": datetime(current_year, 6, 15),  # Recency boost: 0.05
            "quality_total": 60,  # Legacy boost: 3.0
            "title": "Phase II Clinical Trial Results",  # Investment boost: varies
            "abstract": "FDA approval sought for this biotech therapeutic",
            "keywords": ["precision medicine"],
            "mesh_terms": []
        }
        
        total_boost = scorer.calculate_quality_boost(doc)
        
        # Should include journal boost (0.10) + recency boost (0.05) + legacy boost (3.0) + investment boost
        assert total_boost >= 3.15  # At minimum journal + recency + legacy
        assert total_boost < 4.0   # Reasonable upper bound
    
    def test_calculate_quality_boost_minimal(self):
        """Test quality boost calculation with minimal document."""
        scorer = JournalQualityScorer()
        
        doc = {
            "title": "Basic Research Study"
        }
        
        total_boost = scorer.calculate_quality_boost(doc)
        assert total_boost == 0.0
    
    def test_apply_quality_boost(self):
        """Test applying quality boost to search results."""
        scorer = JournalQualityScorer()
        
        results = [
            {
                "score": 0.8,
                "title": "High Score Study",
                "journal": "Nature",
                "publication_date": datetime(2023, 6, 15)
            },
            {
                "score": 0.6,
                "title": "Medium Score Study", 
                "journal": "PLoS ONE",
                "publication_date": datetime(2020, 1, 1)
            },
            {
                "score": 0.4,
                "title": "Low Score Study",
                "journal": "Random Journal",
                "publication_date": datetime(2015, 1, 1)
            }
        ]
        
        boosted_results = scorer.apply_quality_boost(results)
        
        # Check that boosted scores are calculated
        for result in boosted_results:
            assert "boosted_score" in result
            assert "quality_boost" in result
            assert isinstance(result["boosted_score"], int | float)
            assert isinstance(result["quality_boost"], int | float)
        
        # Results should be sorted by boosted score (descending)
        scores = [r["boosted_score"] for r in boosted_results]
        assert scores == sorted(scores, reverse=True)
        
        # High-impact journal should get boosted score
        nature_result = next(r for r in boosted_results if "Nature" in r.get("journal", ""))
        assert nature_result["boosted_score"] > nature_result["score"]
        assert nature_result["quality_boost"] > 0
    
    def test_apply_quality_boost_zero_scores(self):
        """Test applying quality boost to results with zero scores."""
        scorer = JournalQualityScorer()
        
        results = [
            {
                "score": 0.0,
                "title": "Zero Score Study",
                "journal": "Nature"
            },
            {
                "score": None,
                "title": "None Score Study",
                "journal": "Science"
            }
        ]
        
        boosted_results = scorer.apply_quality_boost(results)
        
        # Zero scores should remain zero even with quality boost
        for result in boosted_results:
            if result["score"] == 0.0 or result["score"] is None:
                assert result["boosted_score"] == result["score"]
                assert result["quality_boost"] == 0
    
    def test_apply_quality_boost_sorting(self):
        """Test that quality boost affects result sorting correctly."""
        scorer = JournalQualityScorer()
        current_year = datetime.now(UTC).year
        
        results = [
            {
                "score": 0.7,
                "title": "Medium Score, High Boost",
                "journal": "Nature",  # Will get journal boost
                "publication_date": datetime(current_year, 1, 1),  # Will get recency boost
                "quality_total": 40  # Will get legacy boost
            },
            {
                "score": 0.9,
                "title": "High Score, No Boost",
                "journal": "Unknown Journal",
                "publication_date": datetime(2010, 1, 1),
                "quality_total": 0
            }
        ]
        
        boosted_results = scorer.apply_quality_boost(results)
        
        # The medium score document with quality boosts might rank higher
        # than the high score document without boosts
        first_result = boosted_results[0]
        second_result = boosted_results[1]
        
        assert first_result["boosted_score"] >= second_result["boosted_score"]


# Mark as unit tests
pytestmark = pytest.mark.unit