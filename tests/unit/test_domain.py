"""Domain model testleri — DB gerektirmez."""
import uuid
import pytest

from app.domain.knowledge_component import KnowledgeComponent, KCMasterySnapshot, MasteryLevel
from app.domain.interaction import Interaction, InteractionType
from app.domain.learner_profile import LearnerProfile
from app.domain.session_context import SessionContext


# ── KnowledgeComponent ────────────────────────────────────────────────────────

class TestKnowledgeComponent:
    def test_mastery_level_unknown_when_no_attempts(self):
        kc = KnowledgeComponent(kc_id="algebra", label="Cebir")
        assert kc.mastery_level == MasteryLevel.UNKNOWN

    def test_mastery_level_introduced(self):
        kc = KnowledgeComponent(kc_id="algebra", label="Cebir", p_mastery=0.2, attempts=2)
        assert kc.mastery_level == MasteryLevel.INTRODUCED

    def test_mastery_level_practicing(self):
        kc = KnowledgeComponent(kc_id="algebra", label="Cebir", p_mastery=0.55, attempts=5)
        assert kc.mastery_level == MasteryLevel.PRACTICING

    def test_mastery_level_mastered(self):
        kc = KnowledgeComponent(kc_id="algebra", label="Cebir", p_mastery=0.85, attempts=10)
        assert kc.mastery_level == MasteryLevel.MASTERED

    def test_update_clamps_to_zero_one(self):
        kc = KnowledgeComponent(kc_id="x", label="X", p_mastery=0.5, attempts=1)
        kc.update(1.5)
        assert kc.p_mastery == 1.0
        kc.update(-0.5)
        assert kc.p_mastery == 0.0

    def test_update_increments_attempts(self):
        kc = KnowledgeComponent(kc_id="x", label="X", attempts=3)
        kc.update(0.6)
        assert kc.attempts == 4


class TestKCMasterySnapshot:
    def test_weakest_returns_sorted(self):
        snap = KCMasterySnapshot()
        snap.upsert(KnowledgeComponent("a", "A", p_mastery=0.8, attempts=1))
        snap.upsert(KnowledgeComponent("b", "B", p_mastery=0.2, attempts=1))
        snap.upsert(KnowledgeComponent("c", "C", p_mastery=0.5, attempts=1))
        weakest = snap.weakest(2)
        assert weakest[0].kc_id == "b"
        assert weakest[1].kc_id == "c"

    def test_to_prompt_context_empty(self):
        snap = KCMasterySnapshot()
        assert "henüz" in snap.to_prompt_context().lower()

    def test_to_prompt_context_has_labels(self):
        snap = KCMasterySnapshot()
        snap.upsert(KnowledgeComponent("fractions", "Kesirler", p_mastery=0.6, attempts=3))
        ctx = snap.to_prompt_context()
        assert "Kesirler" in ctx


# ── Interaction ───────────────────────────────────────────────────────────────

class TestInteraction:
    def _make(self, **kwargs) -> Interaction:
        defaults = dict(
            learner_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            interaction_type=InteractionType.QUESTION,
            content_summary="Türev nedir?",
            kc_tags=["calculus"],
        )
        defaults.update(kwargs)
        return Interaction(**defaults)

    def test_to_embed_text_includes_type_and_kc(self):
        i = self._make()
        text = i.to_embed_text()
        assert "question" in text
        assert "calculus" in text
        assert "Türev nedir?" in text

    def test_to_embed_text_no_kc_tags(self):
        i = self._make(kc_tags=[])
        text = i.to_embed_text()
        assert "genel" in text


# ── LearnerProfile ────────────────────────────────────────────────────────────

class TestLearnerProfile:
    def test_preferences_roundtrip(self):
        p = LearnerProfile()
        p.set_preference("explanation_style", "örnekli")
        assert p.get_preference("explanation_style") == "örnekli"

    def test_to_prompt_context_with_preferences(self):
        p = LearnerProfile(display_name="Ali")
        p.set_preference("explanation_style", "adım adım")
        ctx = p.to_prompt_context()
        assert "Ali" in ctx
        assert "adım adım" in ctx

    def test_get_missing_preference_returns_default(self):
        p = LearnerProfile()
        assert p.get_preference("nonexistent", "fallback") == "fallback"


# ── SessionContext ────────────────────────────────────────────────────────────

class TestSessionContext:
    def test_add_turn_and_recent(self):
        ctx = SessionContext(
            session_id=uuid.uuid4(),
            learner_id=uuid.uuid4(),
        )
        ctx.add_turn("user", "Merhaba")
        ctx.add_turn("assistant", "Merhaba! Nasıl yardımcı olabilirim?")
        assert len(ctx.recent_turns(6)) == 2

    def test_recent_turns_limit(self):
        ctx = SessionContext(session_id=uuid.uuid4(), learner_id=uuid.uuid4())
        for i in range(10):
            ctx.add_turn("user", f"Mesaj {i}")
        assert len(ctx.recent_turns(3)) == 3

    def test_serialization_roundtrip(self):
        lid = uuid.uuid4()
        sid = uuid.uuid4()
        ctx = SessionContext(session_id=sid, learner_id=lid)
        ctx.add_turn("user", "Test mesajı", kc_tags=["algebra"])
        from app.domain.knowledge_component import KnowledgeComponent
        ctx.mastery_snapshot.upsert(
            KnowledgeComponent("algebra", "Cebir", p_mastery=0.7, attempts=5)
        )

        data = ctx.to_dict()
        restored = SessionContext.from_dict(data)

        assert restored.session_id == sid
        assert restored.learner_id == lid
        assert len(restored.turns) == 1
        assert restored.turns[0].content == "Test mesajı"
        assert restored.mastery_snapshot.get("algebra").p_mastery == 0.7

    def test_to_conversation_history_format(self):
        ctx = SessionContext(session_id=uuid.uuid4(), learner_id=uuid.uuid4())
        ctx.add_turn("user", "Soru")
        ctx.add_turn("assistant", "Cevap")
        history = ctx.to_conversation_history()
        assert history[0] == {"role": "user", "content": "Soru"}
        assert history[1] == {"role": "assistant", "content": "Cevap"}
