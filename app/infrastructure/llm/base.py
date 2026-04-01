from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str = "stop"


class BaseLLMClient(ABC):
    """
    Tüm LLM provider'ları bu interface'i implement eder.
    Dışarıya sadece bu type expose edilir — provider'a doğrudan bağımlılık yok.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse: ...

    @abstractmethod
    async def complete_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ):
        """Async generator — her yield bir string chunk."""
        ...
