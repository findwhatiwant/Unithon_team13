import time
from typing import Protocol


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    def generate(self, system: str, user: str) -> str: ...


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        max_retries: int = 2,
    ):
        from google import genai

        self._model = model
        self._max_retries = max_retries
        self._client = genai.Client(api_key=api_key)

    def generate(self, system: str, user: str) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            temperature=0.7,
        )
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=user,
                    config=config,
                )
                return response.text or ""
            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(2**attempt)
        raise LLMError(f"{type(last_error).__name__}: {last_error}") from last_error
