import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from .errors import ModelRequestError
from .observation import _observation

_RETRYABLE = {"model_timeout", "rate_limit"}
_ATTEMPTS = 3


class OpenAICompatModel:
    def __init__(self, client, model: str):
        """
        client 必须是一个已经创建好的 OpenAI 兼容客户端。

        它只需要提供下面的调用链：
            client.chat.completions.create(...)

        :param client: 例如 OpenAI(base_url="https://api.deepseek.com", api_key="sk-...")
        :param model: 模型名。例如 "deepseek-chat"
        """
        self.client = client
        self.model = model

    @classmethod
    def from_env(cls):
        """从当前工作目录的环境变量创建客户端。

        需要 LLM_MODEL、LLM_BASE_URL、LLM_API_KEY。密钥不要写进代码。
        """
        load_dotenv()
        model = os.environ.get("LLM_MODEL")
        base_url = os.environ.get("LLM_BASE_URL")
        api_key = os.environ.get("LLM_API_KEY")
        if not model or not base_url or not api_key:
            raise ValueError("LLM_MODEL, LLM_BASE_URL and LLM_API_KEY are required")
        return cls(client=OpenAI(base_url=base_url, api_key=api_key), model=model)

    def query(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """把内部消息转成供应商格式，再把返回转回内部格式。

        :param messages: 内部历史。工具调用例如 {"role": "assistant", "content": "我先读取", "tool_calls": [{"id": "call_1", "name": "read_file", "arguments": {"path": "hello.py"}}]}
        :param tools: 工具 schema。例如 [{"type": "function", "function": {"name": "read_file", "parameters": {"type": "object"}}}]。没有工具时不传
        :return: 没有工具调用时例如 {"role": "assistant", "content": "pong"}。有调用时 arguments 已是字典
        """
        payload = {
            "model": self.model,
            "messages": [_provider_message(message) for message in messages],
            "temperature": 0.2,
            "timeout": 30,
        }
        if tools:
            payload["tools"] = tools
        last_code = "model_error"
        for attempt in range(_ATTEMPTS):
            try:
                response = self.client.chat.completions.create(**payload)
                return _internal_reply(response.choices[0].message)
            except Exception as exc:
                last_code = _classify_model_error(exc)
                if last_code not in _RETRYABLE or attempt == _ATTEMPTS - 1:
                    raise ModelRequestError({
                        "role": "user",
                        "content": _observation("model", "null", last_code, error=last_code),
                    }) from exc
        raise ModelRequestError({
            "role": "user",
            "content": _observation("model", "null", last_code, error=last_code),
        })


def _classify_model_error(exc: Exception) -> str:
    """把供应商异常收成少数几类。超时和限流会重试，上下文超限不重试。

    :param exc: create 抛出的异常。例如 TimeoutError("timeout")
    :return: 例如 "model_timeout"、"rate_limit"、"context_limit"、"model_error"
    """
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "context" in name or "context length" in text or "context_length" in text:
        return "context_limit"
    if "timeout" in name or "timed out" in text:
        return "model_timeout"
    if "ratelimit" in name or "rate limit" in text or "429" in text:
        return "rate_limit"
    return "model_error"


def _provider_message(message: dict) -> dict:
    """内部消息转成 OpenAI 兼容格式。arguments 字典会变成 JSON 字符串。"""
    calls = message.get("tool_calls")
    if message.get("role") == "assistant" and calls:
        return {
            "role": "assistant",
            "content": message.get("content") or None,
            "tool_calls": [
                {
                    "id": call.get("id"),
                    "type": "function",
                    "function": {
                        "name": call.get("name") or "",
                        "arguments": json.dumps(call.get("arguments") or {}, ensure_ascii=False),
                    },
                }
                for call in calls
            ],
        }
    if message.get("role") == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.get("tool_call_id"),
            "content": message.get("content") or "",
        }
    return {"role": message.get("role"), "content": message.get("content") or ""}


def _parse_arguments(raw) -> dict:
    """供应商的 arguments 通常是 JSON 字符串。解析失败时返回空字典，不抛异常。"""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _internal_reply(message) -> dict:
    """供应商消息转成内部格式。没有工具调用时不写 tool_calls 键，循环把它当成普通正文。"""
    reply = {
        "role": getattr(message, "role", None) or "assistant",
        "content": getattr(message, "content", None) or "",
    }
    calls = []
    for call in getattr(message, "tool_calls", None) or []:
        function = getattr(call, "function", None)
        calls.append({
            "id": getattr(call, "id", None) or "call",
            "name": getattr(function, "name", None) or "",
            "arguments": _parse_arguments(getattr(function, "arguments", None)),
        })
    if calls:
        reply["tool_calls"] = calls
    return reply
