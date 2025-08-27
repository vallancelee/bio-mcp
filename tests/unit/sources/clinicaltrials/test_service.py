"""
Unit tests for ClinicalTrials.gov service.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from bio_mcp.shared.utils.checkpoints import CheckpointManager
from bio_mcp.sources.clinicaltrials.client import ClinicalTrialsClient
from bio_mcp.sources.clinicaltrials.config import ClinicalTrialsConfig
from bio_mcp.sources.clinicaltrials.models import ClinicalTrialDocument
from bio_mcp.sources.clinicaltrials.service import ClinicalTrialsService
from bio_mcp.sources.clinicaltrials.sync_strategy import ClinicalTrialsSyncStrategy


class TestClinicalTrialsService:
    """Test ClinicalTrialsService functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock(spec=ClinicalTrialsConfig)
        self.mock_checkpoint_manager = Mock(spec=CheckpointManager)
        self.service = ClinicalTrialsService(
            self.mock_config, self.mock_checkpoint_manager
        )

    @pytest.mark.asyncio
    async def test_initialization_with_checkpoint_manager(self):
        """Test service initialization with checkpoint manager."""
        mock_client = Mock(spec=ClinicalTrialsClient)

        with patch(
            "bio_mcp.sources.clinicaltrials.service.ClinicalTrialsClient"
        ) as mock_client_class:
            mock_client_class.return_value = mock_client

            await self.service.initialize()

        assert self.service._initialized is True
        assert self.service.client is not None
        assert self.service.sync_strategy is not None
        assert isinstance(self.service.sync_strategy, ClinicalTrialsSyncStrategy)

    @pytest.mark.asyncio
    async def test_initialization_without_checkpoint_manager(self):
        """Test service initialization without checkpoint manager."""
        service = ClinicalTrialsService(self.mock_config, None)

        mock_client = Mock(spec=ClinicalTrialsClient)

        with patch(
            "bio_mcp.sources.clinicaltrials.service.ClinicalTrialsClient"
        ) as mock_client_class:
            mock_client_class.return_value = mock_client

            await service.initialize()

        assert service._initialized is True
        assert service.client is not None
        assert service.sync_strategy is None  # No checkpoint manager

    @pytest.mark.asyncio
    async def test_initialization_idempotent(self):
        """Test that initialization is idempotent."""
        mock_client = Mock(spec=ClinicalTrialsClient)

        with patch(
            "bio_mcp.sources.clinicaltrials.service.ClinicalTrialsClient"
        ) as mock_client_class:
            mock_client_class.return_value = mock_client

            # Initialize twice
            await self.service.initialize()
            await self.service.initialize()

        # Should only initialize once
        mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test service cleanup."""
        # Setup initialized service
        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.close = AsyncMock()

        with patch(
            "bio_mcp.sources.clinicaltrials.service.ClinicalTrialsClient"
        ) as mock_client_class:
            mock_client_class.return_value = mock_client
            await self.service.initialize()

        # Test cleanup
        await self.service.cleanup()

        assert self.service._initialized is False
        assert self.service.client is None
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_simple_query(self):
        """Test simple search functionality."""
        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.search = AsyncMock(return_value=["NCT12345678", "NCT87654321"])

        self.service.client = mock_client
        self.service._initialized = True

        result = await self.service.search("cancer")

        assert result == ["NCT12345678", "NCT87654321"]
        mock_client.search.assert_called_once_with("cancer", condition="cancer")

    @pytest.mark.asyncio
    async def test_search_structured_query(self):
        """Test search with structured query."""
        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.search = AsyncMock(return_value=["NCT12345678"])

        self.service.client = mock_client
        self.service._initialized = True

        result = await self.service.search("condition:diabetes phase:PHASE3")

        mock_client.search.assert_called_once_with(
            "condition:diabetes phase:PHASE3", condition="diabetes", phase="PHASE3"
        )
        assert result == ["NCT12345678"]

    @pytest.mark.asyncio
    async def test_search_with_kwargs_override(self):
        """Test search with kwargs overriding query parameters."""
        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.search = AsyncMock(return_value=["NCT12345678"])

        self.service.client = mock_client
        self.service._initialized = True

        # Query has phase:PHASE2 but kwargs override to PHASE3
        await self.service.search(
            "condition:cancer phase:PHASE2", phase="PHASE3", limit=50
        )

        mock_client.search.assert_called_once_with(
            "condition:cancer phase:PHASE2",
            condition="cancer",
            phase="PHASE3",
            limit=50,
        )

    @pytest.mark.asyncio
    async def test_search_not_initialized(self):
        """Test search when service not initialized."""
        # Disable auto-initialization by mocking ensure_initialized to do nothing
        with patch.object(self.service, "ensure_initialized"):
            with pytest.raises(RuntimeError, match="client not initialized"):
                await self.service.search("cancer")

    @pytest.mark.asyncio
    async def test_get_document_success(self):
        """Test getting single document."""
        mock_api_data = {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT12345678",
                    "briefTitle": "Test Study",
                },
                "statusModule": {"overallStatus": "RECRUITING"},
            }
        }

        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.get_study = AsyncMock(return_value=mock_api_data)

        self.service.client = mock_client
        self.service._initialized = True

        result = await self.service.get_document("NCT12345678")

        assert isinstance(result, ClinicalTrialDocument)
        assert result.nct_id == "NCT12345678"
        mock_client.get_study.assert_called_once_with("NCT12345678")

    @pytest.mark.asyncio
    async def test_get_document_not_found(self):
        """Test getting document that doesn't exist."""
        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.get_study = AsyncMock(return_value=None)

        self.service.client = mock_client
        self.service._initialized = True

        with pytest.raises(ValueError, match="not found"):
            await self.service.get_document("NCT99999999")

    @pytest.mark.asyncio
    async def test_get_documents_batch_success(self):
        """Test getting multiple documents."""
        mock_api_data = [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT12345678",
                        "briefTitle": "Test Study 1",
                    },
                    "statusModule": {"overallStatus": "RECRUITING"},
                }
            },
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT87654321",
                        "briefTitle": "Test Study 2",
                    },
                    "statusModule": {"overallStatus": "COMPLETED"},
                }
            },
        ]

        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.get_studies_batch = AsyncMock(return_value=mock_api_data)

        self.service.client = mock_client
        self.service._initialized = True

        result = await self.service.get_documents(["NCT12345678", "NCT87654321"])

        assert len(result) == 2
        assert all(isinstance(doc, ClinicalTrialDocument) for doc in result)
        assert result[0].nct_id == "NCT12345678"
        assert result[1].nct_id == "NCT87654321"

    @pytest.mark.asyncio
    async def test_get_documents_batch_empty_list(self):
        """Test getting documents with empty list."""
        self.service._initialized = True
        self.service.client = Mock()  # Add mock client to avoid attribute errors
        result = await self.service.get_documents([])

        assert result == []

    @pytest.mark.asyncio
    async def test_get_documents_batch_with_parse_errors(self):
        """Test getting documents with some parse errors."""
        mock_api_data = [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT12345678",
                        "briefTitle": "Valid Study",
                    },
                }
            },
            {
                "invalid": "data"  # This will cause parse error
            },
        ]

        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.get_studies_batch = AsyncMock(return_value=mock_api_data)

        self.service.client = mock_client
        self.service._initialized = True

        result = await self.service.get_documents(["NCT12345678", "NCT99999999"])

        # The invalid data gets parsed with default values (empty nct_id)
        # So we get 2 documents, but one has empty/invalid data
        assert len(result) == 2
        assert result[0].nct_id == "NCT12345678"
        # Second document should have empty/invalid NCT ID due to invalid data
        assert result[1].nct_id == ""

    @pytest.mark.asyncio
    async def test_sync_documents_success(self):
        """Test document sync functionality."""
        mock_sync_strategy = Mock(spec=ClinicalTrialsSyncStrategy)
        mock_sync_strategy.sync_incremental = AsyncMock(
            return_value={
                "success": True,
                "synced": 5,
                "new": 4,
                "updated": 1,
                "investment_relevant_count": 3,
                "avg_investment_score": 0.75,
            }
        )

        self.service.sync_strategy = mock_sync_strategy
        self.service._initialized = True

        result = await self.service.sync_documents(
            "condition:cancer", "cancer_sync", 100
        )

        assert result["success"] is True
        assert result["synced"] == 5
        mock_sync_strategy.sync_incremental.assert_called_once_with(
            "condition:cancer", "cancer_sync", 100
        )

    @pytest.mark.asyncio
    async def test_sync_documents_no_sync_strategy(self):
        """Test sync documents when no sync strategy available."""
        self.service.sync_strategy = None
        self.service._initialized = True

        with pytest.raises(RuntimeError, match="Sync strategy not initialized"):
            await self.service.sync_documents("condition:cancer", "cancer_sync", 100)

    @pytest.mark.asyncio
    async def test_sync_by_nct_ids_success(self):
        """Test targeted sync by NCT IDs."""
        mock_sync_strategy = Mock(spec=ClinicalTrialsSyncStrategy)
        mock_sync_strategy.sync_by_nct_ids = AsyncMock(
            return_value={
                "success": True,
                "requested_count": 2,
                "synced": 2,
            }
        )

        self.service.sync_strategy = mock_sync_strategy
        self.service._initialized = True

        nct_ids = ["NCT12345678", "NCT87654321"]
        result = await self.service.sync_by_nct_ids(nct_ids)

        assert result["success"] is True
        assert result["synced"] == 2
        mock_sync_strategy.sync_by_nct_ids.assert_called_once_with(nct_ids)

    @pytest.mark.asyncio
    async def test_search_investment_relevant(self):
        """Test investment-focused search."""
        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.search = AsyncMock(return_value=["NCT12345678", "NCT87654321"])

        # Mock get_documents to return high and low investment score documents
        high_score_doc = Mock(spec=ClinicalTrialDocument)
        high_score_doc.nct_id = "NCT12345678"
        high_score_doc.investment_relevance_score = 0.8

        low_score_doc = Mock(spec=ClinicalTrialDocument)
        low_score_doc.nct_id = "NCT87654321"
        low_score_doc.investment_relevance_score = 0.3

        with patch.object(self.service, "get_documents") as mock_get_docs:
            mock_get_docs.return_value = [high_score_doc, low_score_doc]

            self.service.client = mock_client
            self.service._initialized = True

            result = await self.service.search_investment_relevant(
                "cancer", min_investment_score=0.5, limit=10
            )

        # Should only return high-scoring trial
        assert result == ["NCT12345678"]

        # Should add investment-focused filters
        mock_client.search.assert_called_once()
        search_kwargs = mock_client.search.call_args[1]
        assert search_kwargs["phase"] == "PHASE2"
        assert search_kwargs["sponsor_class"] == "INDUSTRY"
        assert search_kwargs["status"] == "RECRUITING"

    @pytest.mark.asyncio
    async def test_search_investment_relevant_no_filtering(self):
        """Test investment-focused search with no score filtering."""
        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.search = AsyncMock(return_value=["NCT12345678", "NCT87654321"])

        self.service.client = mock_client
        self.service._initialized = True

        # No minimum score filtering
        result = await self.service.search_investment_relevant(
            "cancer", min_investment_score=0.0, limit=10
        )

        # Should return all results without fetching documents
        assert result == ["NCT12345678", "NCT87654321"]

    def test_parse_search_query_structured(self):
        """Test parsing structured search queries."""
        result = self.service._parse_search_query(
            "condition:cancer phase:PHASE3 status:RECRUITING"
        )

        expected = {"condition": "cancer", "phase": "PHASE3", "status": "RECRUITING"}
        assert result == expected

    def test_parse_search_query_simple_with_implicit_indicators(self):
        """Test parsing simple query with implicit phase/sponsor indicators."""
        result = self.service._parse_search_query("diabetes PHASE2 INDUSTRY")

        expected = {
            "condition": "diabetes",
            "phase": "PHASE2",
            "sponsor_class": "INDUSTRY",
        }
        assert result == expected

    def test_parse_search_query_mixed_format(self):
        """Test parsing mixed structured and simple query."""
        result = self.service._parse_search_query(
            "cancer PHASE3 intervention:drugX RECRUITING"
        )

        # The method recognizes "intervention:drugX" as structured
        # and treats other parts as condition text since no other structured keys are found
        expected = {
            "condition": "cancer PHASE3 RECRUITING",  # Non-structured parts become condition
            "intervention": "drugX",
        }
        assert result == expected

    def test_parse_search_query_empty(self):
        """Test parsing empty query."""
        result = self.service._parse_search_query("")
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_investment_summary_comprehensive(self):
        """Test comprehensive investment summary generation."""
        # Create mock documents with varied characteristics
        docs = [
            self._create_mock_document(
                "NCT11111111", "PHASE3", "INDUSTRY", "Cancer", 0.9
            ),
            self._create_mock_document(
                "NCT22222222", "PHASE2", "INDUSTRY", "Diabetes", 0.7
            ),
            self._create_mock_document(
                "NCT33333333", "PHASE1", "ACADEMIC", "Cancer", 0.3
            ),
            self._create_mock_document(
                "NCT44444444", "PHASE3", "NIH", "Alzheimer", 0.6
            ),
        ]

        with patch.object(self.service, "get_documents") as mock_get_docs:
            mock_get_docs.return_value = docs

            nct_ids = ["NCT11111111", "NCT22222222", "NCT33333333", "NCT44444444"]
            result = await self.service.get_investment_summary(nct_ids)

        # Verify summary metrics
        assert result["total_trials"] == 4
        assert result["investment_relevant"] == 3  # Score > 0.5
        assert result["investment_percentage"] == 75.0  # 3/4 * 100
        assert result["avg_investment_score"] == 0.62  # (0.9+0.7+0.3+0.6)/4

        # Verify distributions
        assert result["phase_distribution"]["PHASE3"] == 2
        assert result["phase_distribution"]["PHASE2"] == 1
        assert result["phase_distribution"]["PHASE1"] == 1

        assert result["sponsor_distribution"]["INDUSTRY"] == 2
        assert result["sponsor_distribution"]["ACADEMIC"] == 1
        assert result["sponsor_distribution"]["NIH"] == 1

        # Verify top conditions (Cancer appears twice)
        assert result["top_conditions"][0]["condition"] == "Cancer"
        assert result["top_conditions"][0]["count"] == 2

        # Verify high-value trials are sorted by investment score
        high_value = result["high_value_trials"]
        assert len(high_value) == 4  # All trials returned (limited to 5)
        assert high_value[0]["investment_score"] == 0.9  # Highest first
        assert high_value[0]["nct_id"] == "NCT11111111"

    @pytest.mark.asyncio
    async def test_get_investment_summary_empty_list(self):
        """Test investment summary with empty NCT ID list."""
        result = await self.service.get_investment_summary([])

        expected = {
            "total_trials": 0,
            "investment_relevant": 0,
            "avg_investment_score": 0.0,
            "phase_distribution": {},
            "sponsor_distribution": {},
            "top_conditions": [],
        }

        assert result == expected

    @pytest.mark.asyncio
    async def test_ensure_initialized_calls_initialize(self):
        """Test that ensure_initialized calls initialize when needed."""
        assert self.service._initialized is False

        with patch.object(self.service, "initialize") as mock_init:
            mock_init.return_value = AsyncMock()
            await self.service.ensure_initialized()
            mock_init.assert_called_once()

    def _create_mock_document(
        self,
        nct_id: str,
        phase: str,
        sponsor_class: str,
        condition: str,
        investment_score: float,
    ):
        """Helper to create mock ClinicalTrialDocument."""
        doc = Mock(spec=ClinicalTrialDocument)
        doc.nct_id = nct_id
        doc.phase = phase
        doc.sponsor_class = sponsor_class
        doc.sponsor_name = f"Sponsor for {nct_id}"
        doc.conditions = [condition]
        doc.investment_relevance_score = investment_score
        doc.get_display_title.return_value = f"Study {nct_id}"
        return doc

    @pytest.mark.asyncio
    async def test_search_with_client_error(self):
        """Test search handling client errors."""
        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.search = AsyncMock(side_effect=Exception("API Error"))

        self.service.client = mock_client
        self.service._initialized = True

        with pytest.raises(Exception, match="API Error"):
            await self.service.search("cancer")

    @pytest.mark.asyncio
    async def test_get_document_with_client_error(self):
        """Test get_document handling client errors."""
        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.get_study = AsyncMock(side_effect=Exception("Network Error"))

        self.service.client = mock_client
        self.service._initialized = True

        with pytest.raises(Exception, match="Network Error"):
            await self.service.get_document("NCT12345678")

    @pytest.mark.asyncio
    async def test_search_investment_relevant_with_existing_filters(self):
        """Test investment search that doesn't override existing filters."""
        mock_client = Mock(spec=ClinicalTrialsClient)
        mock_client.search = AsyncMock(return_value=["NCT12345678"])

        self.service.client = mock_client
        self.service._initialized = True

        # Query already has phase specified
        await self.service.search_investment_relevant(
            "condition:cancer phase:PHASE1", min_investment_score=0.0, limit=10
        )

        # Should not override existing phase
        mock_client.search.assert_called_once()
        search_kwargs = mock_client.search.call_args[1]
        assert search_kwargs["phase"] == "PHASE1"  # Should preserve existing phase
        assert (
            search_kwargs["sponsor_class"] == "INDUSTRY"
        )  # Should add missing filters
        assert search_kwargs["status"] == "RECRUITING"  # Should add missing filters
