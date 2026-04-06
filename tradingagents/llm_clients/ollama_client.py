import json
import time
from typing import Any, Optional

import requests
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool

from .base_client import BaseLLMClient, normalize_content


class RequestChatOllama(BaseChatModel):
    """Minimal Ollama chat model that uses the native /api/chat endpoint."""

    model: str
    base_url: str = "http://localhost:11434"
    timeout: float = 900.0
    connect_timeout: float = 15.0
    max_retries: int = 2
    retry_backoff: float = 2.0
    default_options: dict[str, Any] | None = None

    @property
    def _llm_type(self) -> str:
        return "ollama-native"

    def bind_tools(self, tools: list[Any], **kwargs: Any) -> Any:
        formatted_tools = [convert_to_openai_tool(tool) for tool in tools]
        return self.bind(tools=formatted_tools, **kwargs)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = {
            "model": self.model,
            "messages": [self._to_ollama_message(message) for message in messages],
            "stream": False,
        }

        tools = kwargs.get("tools")
        if tools:
            payload["tools"] = tools

        options = dict(self.default_options or {})
        if stop:
            options["stop"] = stop
        if options:
            payload["options"] = options

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    f"{self.base_url.rstrip('/')}/api/chat",
                    json=payload,
                    timeout=(self.connect_timeout, self.timeout),
                )
                response.raise_for_status()
                data = response.json()
                break
            except requests.exceptions.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                body = ""
                if exc.response is not None:
                    try:
                        body = exc.response.text.strip()
                    except Exception:
                        body = ""

                if status_code is not None and status_code >= 500:
                    last_error = RuntimeError(
                        f"Ollama server error {status_code} for model '{self.model}'. "
                        f"Response: {body[:400]}"
                    )
                    if attempt >= self.max_retries:
                        raise last_error
                    time.sleep(self.retry_backoff * (attempt + 1))
                    continue
                raise
            except requests.exceptions.ReadTimeout as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise
                time.sleep(self.retry_backoff * (attempt + 1))
            except requests.exceptions.ConnectionError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise
                time.sleep(self.retry_backoff * (attempt + 1))
        else:
            raise last_error or RuntimeError("Ollama request failed without a specific error.")

        message = data.get("message", {})

        # Extract content from message, including thinking field for reasoning models
        content = message.get("content", "") or ""
        thinking = message.get("thinking", "") or ""

        # For reasoning models (like glm-4.7-flash, gpt-oss), use thinking if content is empty
        if not content.strip() and thinking.strip():
            content = thinking

        ai_message = AIMessage(
            content=content,
            tool_calls=self._extract_tool_calls(message),
            additional_kwargs={"thinking": thinking} if thinking else {},
        )
        normalize_content(ai_message)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    def _to_ollama_message(self, message: BaseMessage) -> dict[str, Any]:
        role = "user"
        message_type = getattr(message, "type", "")
        if message_type == "system":
            role = "system"
        elif message_type == "ai":
            role = "assistant"
        elif message_type == "tool":
            role = "tool"

        payload = {
            "role": role,
            "content": message.content if isinstance(message.content, str) else str(message.content),
        }

        tool_call_id = getattr(message, "tool_call_id", None)
        if tool_call_id:
            payload["tool_call_id"] = tool_call_id

        return payload

    def _extract_tool_calls(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        tool_calls = []
        for tool_call in message.get("tool_calls", []) or []:
            function_data = tool_call.get("function", {})
            arguments = function_data.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"raw_arguments": arguments}
            tool_calls.append(
                {
                    "id": tool_call.get("id") or function_data.get("name", "tool_call"),
                    "type": "tool_call",
                    "name": function_data.get("name", ""),
                    "args": arguments,
                }
            )
        return tool_calls


class OllamaClient(BaseLLMClient):
    """Client for local Ollama models via the native Ollama chat API."""

    def get_llm(self) -> Any:
        base_url = self.base_url or "http://localhost:11434"
        timeout = float(self.kwargs.get("timeout", 900))
        connect_timeout = float(self.kwargs.get("connect_timeout", 15))
        max_retries = int(self.kwargs.get("max_retries", 2))
        retry_backoff = float(self.kwargs.get("retry_backoff", 2))
        default_options = {
            "num_ctx": int(self.kwargs.get("num_ctx", 8192)),
            "num_predict": int(self.kwargs.get("num_predict", 900)),
        }
        temperature = self.kwargs.get("temperature")
        if temperature is not None:
            default_options["temperature"] = float(temperature)
        return RequestChatOllama(
            model=self.model,
            base_url=base_url.rstrip("/v1"),
            timeout=timeout,
            connect_timeout=connect_timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            default_options=default_options,
        )

    def validate_model(self) -> bool:
        return True
