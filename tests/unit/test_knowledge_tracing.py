"""Knowledge Tracing model testleri."""
import uuid
import pytest
from app.services.knowledge_tracing.dkt_model import DKTModel
from app.services.knowledge_tracing.akt_model import AKTModel
from app.services.knowledge_tracing.bkt_model import BKTModel


class TestBKTModel:
    @pytest.fixture
    def model(self):
        return BKTModel()

    @pytest.fixture
    def learner(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_initial_estimate_is_prior(self, model, learner):
        result = await model.estimate(learner, ["physics"])
        assert result["physics"] == pytest.approx(0.1, abs=0.01)

    @pytest.mark.asyncio
    async def test_correct_answer_increases_mastery(self, model, learner):
        before = (await model.estimate(learner, ["physics"]))["physics"]
        await model.update(learner, "physics", correct=True)
        after = (await model.estimate(learner, ["physics"]))["physics"]
        assert after > before
        # BKT check: P(L|correct) should be ~0.24 given defaults
        assert after > 0.2

    @pytest.mark.asyncio
    async def test_wrong_answer_decreases_mastery(self, model, learner):
        await model.update(learner, "physics", correct=True)
        high = (await model.estimate(learner, ["physics"]))["physics"]
        await model.update(learner, "physics", correct=False)
        lower = (await model.estimate(learner, ["physics"]))["physics"]
        assert lower < high

    @pytest.mark.asyncio
    async def test_soft_update_stability(self, model, learner):
        # Confidence 0.7 should increase mastery but less than a full correct=True
        await model.soft_update(learner, "physics", confidence=0.7)
        p1 = (await model.estimate(learner, ["physics"]))["physics"]
        
        # New model for comparison
        model2 = BKTModel()
        await model2.update(learner, "physics", correct=True)
        p2 = (await model2.estimate(learner, ["physics"]))["physics"]
        
        assert p1 < p2
        assert p1 > 0.1

    @pytest.mark.asyncio
    async def test_mastery_bounded(self, model, learner):
        for _ in range(50):
            await model.update(learner, "x", correct=True)
        p = (await model.estimate(learner, ["x"]))["x"]
        assert 0.01 <= p <= 0.99


class TestDKTModel:
    @pytest.fixture
    def model(self):
        return DKTModel()

    @pytest.fixture
    def learner(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_initial_estimate_is_prior(self, model, learner):
        result = await model.estimate(learner, ["algebra"])
        assert 0.0 <= result["algebra"] <= 1.0
        assert result["algebra"] == pytest.approx(0.3, abs=0.05)

    @pytest.mark.asyncio
    async def test_correct_answer_increases_mastery(self, model, learner):
        before = (await model.estimate(learner, ["algebra"]))["algebra"]
        await model.update(learner, "algebra", correct=True)
        after = (await model.estimate(learner, ["algebra"]))["algebra"]
        assert after > before

    @pytest.mark.asyncio
    async def test_multiple_correct_approaches_mastery(self, model, learner):
        for _ in range(20):
            await model.update(learner, "algebra", correct=True)
        p = (await model.estimate(learner, ["algebra"]))["algebra"]
        assert p > 0.7

    @pytest.mark.asyncio
    async def test_wrong_answer_decreases_mastery(self, model, learner):
        # Önce yükselt
        for _ in range(5):
            await model.update(learner, "algebra", correct=True)
        high = (await model.estimate(learner, ["algebra"]))["algebra"]
        await model.update(learner, "algebra", correct=False)
        lower = (await model.estimate(learner, ["algebra"]))["algebra"]
        assert lower < high

    @pytest.mark.asyncio
    async def test_mastery_bounded(self, model, learner):
        for _ in range(50):
            await model.update(learner, "x", correct=True)
        p = (await model.estimate(learner, ["x"]))["x"]
        assert 0.0 <= p <= 1.0

    @pytest.mark.asyncio
    async def test_multiple_kc_independent(self, model, learner):
        for _ in range(10):
            await model.update(learner, "algebra", correct=True)
        results = await model.estimate(learner, ["algebra", "geometry"])
        assert results["algebra"] > results["geometry"]


class TestAKTModel:
    @pytest.fixture
    def model(self):
        return AKTModel(checkpoint_path=None)

    @pytest.fixture
    def learner(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_initial_estimate_prior(self, model, learner):
        result = await model.estimate(learner, ["calculus"])
        assert result["calculus"] == pytest.approx(0.3, abs=0.05)

    @pytest.mark.asyncio
    async def test_correct_answers_increase_mastery(self, model, learner):
        for _ in range(10):
            await model.update(learner, "calculus", correct=True)
        p = (await model.estimate(learner, ["calculus"]))["calculus"]
        assert p > 0.5

    @pytest.mark.asyncio
    async def test_recent_answers_weighted_more(self, model, learner):
        """Son doğru cevaplar eskiden daha fazla ağırlık taşımalı."""
        # Önce 5 yanlış, sonra 5 doğru
        for _ in range(5):
            await model.update(learner, "kc", correct=False)
        for _ in range(5):
            await model.update(learner, "kc", correct=True)
        p_after_correct = (await model.estimate(learner, ["kc"]))["kc"]

        # Önce 5 doğru, sonra 5 yanlış (farklı learner)
        learner2 = uuid.uuid4()
        for _ in range(5):
            await model.update(learner2, "kc", correct=True)
        for _ in range(5):
            await model.update(learner2, "kc", correct=False)
        p_after_wrong = (await model.estimate(learner2, ["kc"]))["kc"]

        assert p_after_correct > p_after_wrong

    @pytest.mark.asyncio
    async def test_mastery_bounded(self, model, learner):
        for _ in range(50):
            await model.update(learner, "x", correct=True)
        p = (await model.estimate(learner, ["x"]))["x"]
        assert 0.0 <= p <= 1.0
