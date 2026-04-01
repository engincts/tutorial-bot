"""Orchestration katmanı unit testleri — LLM/DB mock'lanır."""
from __future__ import annotations

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.domain.knowledge_component import KCMasterySnapshot, KnowledgeComponent, MasteryLevel
from app.domain.learner_profile import LearnerProfile
from app.services.orchestration.pedagogy_planner import PedagogyPlanner
from app.services.orchestration.prompt_builder import PromptBuilder
from app.services.orchestration.session_manager import SessionManager
from app.domain.session_context import SessionContext
from app.settings import AppEnv, EmbedderProvider, LLMProvider, Settings


def make_settings(**kw) -> Settings:
    base = dict(
        app_env=AppEnv.TEST,
        openai_api_key="sk-test",
        embedder_provider=EmbedderProvider.BGE_M3,
        llm_provider=LLMProvider.OPENAI,
        mastery_threshold_low=0.4,
        mastery_threshold_high=0.7,
    )
    base.update(kw)
    return Settings(**base)


# ── PedagogyPlanner ───────────────────────────────────────────────────────────

class TestPedagogyPlanner:
    @pytest.fixture
    def planner(self, tmp_path):
        # Geçici prompts klasörü oluştur
        (tmp_path / "reinforcement.md").write_text("# Pekiştirme")
        (tmp_path / "practice.md").write_text("# Pratik")
        (tmp_path / "challenge.md").write_text("# Zorlayıcı")
        return PedagogyPlanner(settings=make_settings(), prompts_dir=str(tmp_path))

    def _snap(self, p_mastery: float, attempts: int = 1) -> KCMasterySnapshot:
        snap = KCMasterySnapshot()
        snap.upsert(KnowledgeComponent("kc1", "KÇ1", p_mastery=p_mastery, attempts=attempts))
        return snap

    def test_low_mastery_returns_reinforcement(self, planner):
        strategy = planner.select_strategy(self._snap(0.2))
        assert "Pekiştirme" in strategy

    def test_mid_mastery_returns_practice(self, planner):
        strategy = planner.select_strategy(self._snap(0.55))
        assert "Pratik" in strategy

    def test_high_mastery_returns_challenge(self, planner):
        strategy = planner.select_strategy(self._snap(0.85))
        assert "Zorlayıcı" in strategy

    def test_empty_snapshot_returns_reinforcement(self, planner):
        strategy = planner.select_strategy(KCMasterySnapshot())
        assert "Pekiştirme" in strategy

    def test_mastery_level_for(self, planner):
        assert planner.mastery_level_for(self._snap(0.2)) == MasteryLevel.INTRODUCED
        assert planner.mastery_level_for(self._snap(0.55)) == MasteryLevel.PRACTICING
        assert planner.mastery_level_for(self._snap(0.85)) == MasteryLevel.MASTERED


# ── PromptBuilder ─────────────────────────────────────────────────────────────

class TestPromptBuilder:
    @pytest.fixture
    def builder(self, tmp_path):
        (tmp_path / "system_base.md").write_text("# Sistem Direktifi")
        return PromptBuilder(prompts_dir=str(tmp_path))

    def test_builds_messages_list(self, builder):
        from app.domain.interaction import Misconception
        messages = builder.build(
            user_query="Türev nedir?",
            profile=LearnerProfile(display_name="Ali"),
            mastery_snapshot=KCMasterySnapshot(),
            pedagogy_directive="# Pratik",
            content_chunks=[],
            memory_interactions=[],
            misconceptions=[],
            conversation_history=[],
        )
        assert len(messages) >= 2
        assert messages[0].role == "system"
        assert messages[-1].role == "user"
        assert messages[-1].content == "Türev nedir?"

    def test_system_contains_profile(self, builder):
        from app.domain.interaction import Misconception
        messages = builder.build(
            user_query="Soru",
            profile=LearnerProfile(display_name="Zeynep"),
            mastery_snapshot=KCMasterySnapshot(),
            pedagogy_directive="",
            content_chunks=[],
            memory_interactions=[],
            misconceptions=[],
            conversation_history=[],
        )
        assert "Zeynep" in messages[0].content

    def test_conversation_history_injected(self, builder):
        history = [
            {"role": "user", "content": "Önceki soru"},
            {"role": "assistant", "content": "Önceki cevap"},
        ]
        messages = builder.build(
            user_query="Yeni soru",
            profile=LearnerProfile(),
            mastery_snapshot=KCMasterySnapshot(),
            pedagogy_directive="",
            content_chunks=[],
            memory_interactions=[],
            misconceptions=[],
            conversation_history=history,
        )
        roles = [m.role for m in messages]
        assert roles.count("user") == 2
        assert roles.count("assistant") == 1

    def test_misconceptions_in_system(self, builder):
        from app.domain.interaction import Misconception
        misc = Misconception(
            learner_id=uuid.uuid4(),
            kc_id="algebra",
            description="Negatif sayıları karıştırıyor",
        )
        messages = builder.build(
            user_query="Soru",
            profile=LearnerProfile(),
            mastery_snapshot=KCMasterySnapshot(),
            pedagogy_directive="",
            content_chunks=[],
            memory_interactions=[],
            misconceptions=[misc],
            conversation_history=[],
        )
        assert "Negatif sayıları" in messages[0].content


# ── SessionManager ────────────────────────────────────────────────────────────

class TestSessionManager:
    @pytest.fixture
    def mock_cache(self):
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.delete = AsyncMock()
        cache.extend_ttl = AsyncMock()
        return cache

    @pytest.mark.asyncio
    async def test_creates_new_session_when_not_found(self, mock_cache):
        manager = SessionManager(cache=mock_cache)
        sid = uuid.uuid4()
        lid = uuid.uuid4()
        ctx = await manager.get_or_create(sid, lid)
        assert ctx.session_id == sid
        assert ctx.learner_id == lid
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_loads_existing_session(self, mock_cache):
        sid = uuid.uuid4()
        lid = uuid.uuid4()
        existing = SessionContext(session_id=sid, learner_id=lid)
        existing.add_turn("user", "Eski mesaj")
        mock_cache.get = AsyncMock(return_value=existing.to_dict())

        manager = SessionManager(cache=mock_cache)
        ctx = await manager.get_or_create(sid, lid)
        assert len(ctx.turns) == 1
        assert ctx.turns[0].content == "Eski mesaj"

    @pytest.mark.asyncio
    async def test_reset_calls_delete(self, mock_cache):
        manager = SessionManager(cache=mock_cache)
        sid = uuid.uuid4()
        await manager.reset(sid)
        mock_cache.delete.assert_called_once_with(str(sid))
