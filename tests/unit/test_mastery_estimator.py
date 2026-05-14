import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.knowledge_tracing.mastery_estimator import MasteryEstimator
from app.domain.knowledge_component import KCMasterySnapshot, KnowledgeComponent

@pytest.mark.asyncio
async def test_estimate_for_query_calls_mapper():
    # Mocklar
    tracer = AsyncMock()
    tracer.estimate.return_value = {"math_calc": 0.5}
    
    mapper = AsyncMock()
    mapper.extract.return_value = ["math_calc"]
    
    profile_retriever = AsyncMock()
    profile_retriever.load_mastery_snapshot.return_value = KCMasterySnapshot()
    
    estimator = MasteryEstimator(tracer, mapper, profile_retriever)
    
    learner_id = uuid.uuid4()
    query = "How to do calculus?"
    
    kc_ids, snapshot = await estimator.estimate_for_query(
        learner_id=learner_id,
        query=query,
        course_names=["math"]
    )
    
    assert "math_calc" in kc_ids
    assert snapshot.components["math_calc"].p_mastery == 0.5
    mapper.extract.assert_called_once_with(query, course_names=["math"])

@pytest.mark.asyncio
async def test_update_after_interaction_calls_tracer():
    tracer = AsyncMock()
    tracer.update.return_value = 0.6
    
    mapper = AsyncMock()
    profile_retriever = AsyncMock()
    
    estimator = MasteryEstimator(tracer, mapper, profile_retriever)
    
    learner_id = uuid.uuid4()
    result = await estimator.update_after_interaction(
        learner_id=learner_id,
        kc_ids=["math_calc"],
        correct=True
    )
    
    assert result["math_calc"] == 0.6
    tracer.update.assert_called_once_with(
        learner_id=learner_id,
        kc_id="math_calc",
        correct=True
    )
