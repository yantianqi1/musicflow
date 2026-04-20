import json
import httpx
from typing import AsyncGenerator
from backend.config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_MAX_TOKENS


class LLMClient:
    """OpenAI-compatible chat completions client.

    Works with any provider that implements the OpenAI format:
    OpenAI, DeepSeek, Ollama, vLLM, LiteLLM, Azure OpenAI, etc.

    Switch provider by changing LLM_BASE_URL / LLM_API_KEY / LLM_MODEL in .env.
    """

    def __init__(self, base_url: str, api_key: str, model: str, max_tokens: int):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _build_payload(self, messages: list[dict], tools: list[dict] | None = None,
                       tool_choice: str = "auto", stream: bool = False,
                       temperature: float | None = None) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "stream": stream,
            "temperature": temperature if temperature is not None else 0.6,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        return payload

    async def chat(self, messages: list[dict], tools: list[dict] | None = None,
                   tool_choice: str = "auto", temperature: float | None = None) -> dict:
        """Non-streaming chat completion. Returns the full response."""
        payload = self._build_payload(messages, tools, tool_choice, stream=False, temperature=temperature)
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return self._extract_message(data)

    @staticmethod
    def _sanitize_tool_call_id(raw: str) -> str:
        """Strip Gemini thought-signature pollution from tool_call.id.

        Some OpenAI-compatible proxies (e.g. wdapi.top) bundle Gemini
        ``thought_signature`` payloads into the ``id`` field of streamed
        tool_call deltas, producing values like
        ``call_xxx__thought__<base64>__thought__<base64>...``. These ids can
        balloon to tens of KB and break URL routing + SSE rendering. We keep
        only the first segment (the real id) and cap the length defensively.
        """
        if not raw:
            return raw
        cleaned = raw.split("__thought__", 1)[0]
        # Some proxies also separate sigs with whitespace/newlines
        cleaned = cleaned.split("\n", 1)[0].strip()
        return cleaned[:128]

    async def chat_stream(self, messages: list[dict], tools: list[dict] | None = None,
                          tool_choice: str = "auto", temperature: float | None = None) -> AsyncGenerator[dict, None]:
        """Streaming chat completion. Yields delta events.

        Yields dicts of two forms:
          {"type": "text", "content": "..."}
          {"type": "tool_calls", "tool_calls": [{"index":0, "id":"...", "function":{"name":"...", "arguments":"..."}}]}
          {"type": "done"}
        """
        payload = self._build_payload(messages, tools, tool_choice, stream=True, temperature=temperature)
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    resp.raise_for_status()
                accumulated_tool_calls: dict[int, dict] = {}
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    if not delta:
                        continue

                    # Text content
                    if delta.get("content"):
                        yield {"type": "text", "content": delta["content"]}

                    # Tool calls (streamed incrementally)
                    if delta.get("tool_calls"):
                        for tc in delta["tool_calls"]:
                            idx = tc["index"]
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": self._sanitize_tool_call_id(tc.get("id", "")),
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            entry = accumulated_tool_calls[idx]
                            if tc.get("id"):
                                # Only keep the first clean id we see; ignore
                                # subsequent deltas that carry thought-signature
                                # pollution on the id field.
                                if not entry["id"]:
                                    entry["id"] = self._sanitize_tool_call_id(tc["id"])
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                entry["function"]["name"] = fn["name"]
                            if fn.get("arguments"):
                                entry["function"]["arguments"] += fn["arguments"]

                # After stream ends, emit accumulated tool_calls if any
                if accumulated_tool_calls:
                    tool_calls = [accumulated_tool_calls[i] for i in sorted(accumulated_tool_calls)]
                    yield {"type": "tool_calls", "tool_calls": tool_calls}

                yield {"type": "done"}

    @staticmethod
    def _extract_message(data: dict) -> dict:
        """Extract the assistant message from a non-streaming response."""
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        return {
            "role": msg.get("role", "assistant"),
            "content": msg.get("content"),
            "tool_calls": msg.get("tool_calls"),
        }


# Module-level singleton
llm = LLMClient(LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_MAX_TOKENS)
