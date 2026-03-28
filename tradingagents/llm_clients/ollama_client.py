import json
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
    timeout: float = 300.0

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

        if stop:
            payload["options"] = {"stop": stop}

        response = requests.post(
            f"{self.base_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        message = data.get("message", {})

        ai_message = AIMessage(
            content=message.get("content", "") or "",
            tool_calls=self._extract_tool_calls(message),
            additional_kwargs={"thinking": message.get("thinking", "")},
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
        timeout = float(self.kwargs.get("timeout", 300))
        return RequestChatOllama(model=self.model, base_url=base_url.rstrip("/v1"), timeout=timeout)

    def validate_model(self) -> bool:
        return True
