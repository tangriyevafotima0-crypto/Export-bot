"""Tests for the StalkerScorer ML scoring logic.

Tests feature calculations, weighted scoring, classification boundaries,
and score explanation output.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def scorer():
    """Create a StalkerScorer instance with mocked settings."""
    with patch("intelligence.ml_scorer.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            alert_threshold=70,
            database_url="sqlite+aiosqlite:///test.db",
        )
        from intelligence.ml_scorer import StalkerScorer
        scorer = StalkerScorer()
        return scorer


class TestWeightedScoring:
    """Tests for the _calculate_weighted_score method."""

    def test_zero_features_gives_zero_score(self, scorer):
        """All zero features should produce score of 0."""
        features = {
            "story_view_frequency": 0.0,
            "story_view_consistency": 0.0,
            "reaction_speed_score": 0.0,
            "view_timing_variance": 0.0,
            "online_during_my_active_hours": 0.0,
            "mutual_group_activity": 0.0,
            "read_without_reply_ratio": 0.0,
            "profile_content_engagement": 0.0,
        }
        score = scorer._calculate_weighted_score(features)
        assert score == 0.0

    def test_max_features_gives_100_score(self, scorer):
        """All max features (1.0) should produce score of 100."""
        features = {
            "story_view_frequency": 1.0,
            "story_view_consistency": 1.0,
            "reaction_speed_score": 1.0,
            "view_timing_variance": 1.0,
            "online_during_my_active_hours": 1.0,
            "mutual_group_activity": 1.0,
            "read_without_reply_ratio": 1.0,
            "profile_content_engagement": 1.0,
        }
        score = scorer._calculate_weighted_score(features)
        assert score == 100.0

    def test_partial_features(self, scorer):
        """Half features should produce a score around 50."""
        features = {
            "story_view_frequency": 0.5,
            "story_view_consistency": 0.5,
            "reaction_speed_score": 0.5,
            "view_timing_variance": 0.5,
            "online_during_my_active_hours": 0.5,
            "mutual_group_activity": 0.5,
            "read_without_reply_ratio": 0.5,
            "profile_content_engagement": 0.5,
        }
        score = scorer._calculate_weighted_score(features)
        assert 45.0 <= score <= 55.0

    def test_story_consistency_highest_weight(self, scorer):
        """story_view_consistency (weight 0.25) should contribute most to score."""
        features_consistency = {
            "story_view_frequency": 0.0,
            "story_view_consistency": 1.0,
            "reaction_speed_score": 0.0,
            "view_timing_variance": 0.0,
            "online_during_my_active_hours": 0.0,
            "mutual_group_activity": 0.0,
            "read_without_reply_ratio": 0.0,
            "profile_content_engagement": 0.0,
        }
        features_mutual = {
            "story_view_frequency": 0.0,
            "story_view_consistency": 0.0,
            "reaction_speed_score": 0.0,
            "view_timing_variance": 0.0,
            "online_during_my_active_hours": 0.0,
            "mutual_group_activity": 1.0,
            "read_without_reply_ratio": 0.0,
            "profile_content_engagement": 0.0,
        }
        score_consistency = scorer._calculate_weighted_score(features_consistency)
        score_mutual = scorer._calculate_weighted_score(features_mutual)
        assert score_consistency > score_mutual

    def test_score_capped_at_100(self, scorer):
        """Score should never exceed 100 even with extreme values."""
        features = {
            "story_view_frequency": 2.0,
            "story_view_consistency": 2.0,
            "reaction_speed_score": 2.0,
            "view_timing_variance": 2.0,
            "online_during_my_active_hours": 2.0,
            "mutual_group_activity": 2.0,
            "read_without_reply_ratio": 2.0,
            "profile_content_engagement": 2.0,
        }
        score = scorer._calculate_weighted_score(features)
        assert score == 100.0


class TestClassification:
    """Tests for the _classify_score method."""

    def test_normal_classification(self, scorer):
        """Scores 0-24 should be classified as NORMAL."""
        assert scorer._classify_score(0) == "NORMAL"
        assert scorer._classify_score(10) == "NORMAL"
        assert scorer._classify_score(24.9) == "NORMAL"

    def test_curious_classification(self, scorer):
        """Scores 25-49 should be classified as CURIOUS."""
        assert scorer._classify_score(25) == "CURIOUS"
        assert scorer._classify_score(35) == "CURIOUS"
        assert scorer._classify_score(49.9) == "CURIOUS"

    def test_suspicious_classification(self, scorer):
        """Scores 50-74 should be classified as SUSPICIOUS."""
        assert scorer._classify_score(50) == "SUSPICIOUS"
        assert scorer._classify_score(60) == "SUSPICIOUS"
        assert scorer._classify_score(74.9) == "SUSPICIOUS"

    def test_stalker_classification(self, scorer):
        """Scores 75-100 should be classified as STALKER."""
        assert scorer._classify_score(75) == "STALKER"
        assert scorer._classify_score(90) == "STALKER"
        assert scorer._classify_score(100) == "STALKER"

    def test_boundary_at_25(self, scorer):
        """Score at exactly 25 should transition from NORMAL to CURIOUS."""
        assert scorer._classify_score(24.99) == "NORMAL"
        assert scorer._classify_score(25.0) == "CURIOUS"

    def test_boundary_at_50(self, scorer):
        """Score at exactly 50 should transition from CURIOUS to SUSPICIOUS."""
        assert scorer._classify_score(49.99) == "CURIOUS"
        assert scorer._classify_score(50.0) == "SUSPICIOUS"

    def test_boundary_at_75(self, scorer):
        """Score at exactly 75 should transition from SUSPICIOUS to STALKER."""
        assert scorer._classify_score(74.99) == "SUSPICIOUS"
        assert scorer._classify_score(75.0) == "STALKER"


class TestNormalizeScores:
    """Tests for the _normalize_scores method."""

    @pytest.mark.asyncio
    async def test_normalizes_multiple_results(self, scorer):
        """Should add normalized_score field to results."""
        results = [
            {"total_score": 10.0, "user_id": 1},
            {"total_score": 50.0, "user_id": 2},
            {"total_score": 90.0, "user_id": 3},
        ]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(suspicion_score=0.0)
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        async def mock_get_session():
            yield mock_session

        with patch("intelligence.ml_scorer.get_session", mock_get_session):
            await scorer._normalize_scores(results)

        assert "normalized_score" in results[0]
        assert "normalized_score" in results[2]
        assert results[0]["normalized_score"] < results[2]["normalized_score"]

    @pytest.mark.asyncio
    async def test_skip_single_result(self, scorer):
        """Should not normalize if only one result."""
        results = [{"total_score": 50.0, "user_id": 1}]
        await scorer._normalize_scores(results)
        assert "normalized_score" not in results[0]


class TestExplainScore:
    """Tests for the explain_score method."""

    @pytest.mark.asyncio
    async def test_explain_score_returns_breakdown(self, scorer):
        """Should return a detailed breakdown with all features."""
        features = {
            "story_view_frequency": 0.8,
            "story_view_consistency": 0.6,
            "reaction_speed_score": 0.7,
            "view_timing_variance": 0.3,
            "online_during_my_active_hours": 0.5,
            "mutual_group_activity": 0.0,
            "read_without_reply_ratio": 0.2,
            "profile_content_engagement": 0.1,
        }

        with patch.object(scorer, "_compute_features", return_value=features):
            result = await scorer.explain_score(123456)

        assert "total_score" in result
        assert "classification" in result
        assert "breakdown" in result
        assert "top_factor" in result
        assert len(result["breakdown"]) == 8

        for item in result["breakdown"]:
            assert "feature" in item
            assert "raw_value" in item
            assert "weight" in item
            assert "contribution" in item
            assert "explanation" in item

    @pytest.mark.asyncio
    async def test_explain_score_sorted_by_contribution(self, scorer):
        """Breakdown should be sorted by contribution descending."""
        features = {
            "story_view_frequency": 0.2,
            "story_view_consistency": 0.9,
            "reaction_speed_score": 0.1,
            "view_timing_variance": 0.0,
            "online_during_my_active_hours": 0.0,
            "mutual_group_activity": 0.0,
            "read_without_reply_ratio": 0.0,
            "profile_content_engagement": 0.0,
        }

        with patch.object(scorer, "_compute_features", return_value=features):
            result = await scorer.explain_score(123456)

        contributions = [item["contribution"] for item in result["breakdown"]]
        assert contributions == sorted(contributions, reverse=True)
