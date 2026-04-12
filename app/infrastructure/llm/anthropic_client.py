from collections.abc import AsyncGenerator

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from app.infrastructure.llm.base import BaseLLMClient, LLMResponse, Message
from app.settings import Settings


class AnthropicClient(BaseLLMClient):
    def __init__(self, settings: Settings) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60.0)
        self._model = settings.anthropic_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        # Anthropic: system mesajı ayrı parametre
        system_content = ""
        non_system: list[Message] = []
        for m in messages:
            if m.role == "system":
                system_content += m.content + "\n"
            else:
                non_system.append(m)

        response = await self._client.messages.create(
            model=self._model,
            system=system_content.strip() or anthropic.NOT_GIVEN,
            messages=[{"role": m.role, "content": m.content} for m in non_system],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        text_block = next(
            (b for b in response.content if b.type == "text"), None
        )

        return LLMResponse(
            content=text_block.text if text_block else "",
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=response.stop_reason or "stop",
        )

    async def complete_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        system_content = ""
        non_system: list[Message] = []
        for m in messages:
            if m.role == "system":
                system_content += m.content + "\n"
            else:
                non_system.append(m)

        async with self._client.messages.stream(
            model=self._model,
            system=system_content.strip() or anthropic.NOT_GIVEN,
            messages=[{"role": m.role, "content": m.content} for m in non_system],
            temperature=temperature,
            max_tokens=max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield text
