from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class QuizQuestion:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    quiz_id: uuid.UUID = field(default_factory=uuid.uuid4)
    question_text: str = ""
    options: list[str] = field(default_factory=list)
    correct_answer: str = ""
    explanation: str = ""

@dataclass
class QuizSession:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    learner_id: uuid.UUID = field(default_factory=uuid.uuid4)
    kc_id: str = ""
    status: str = "active"
    score: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    questions: list[QuizQuestion] = field(default_factory=list)
