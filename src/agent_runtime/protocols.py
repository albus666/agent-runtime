from pathlib import Path
from typing import Protocol


class Model(Protocol):
    """模型协议。具体类例如 ScriptedModel、OpenAICompatModel。"""

    def query(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """
        :param messages: 送给模型的历史。例如 [{"role": "user", "content": "echo hello"}]
        :param tools: 工具 schema。例如 [{"type": "function", "function": {"name": "echo", "parameters": {"type": "object"}}}]。剧本模型可以忽略
        :return: 旧剧本例如 {"role": "assistant", "content": "done"}。带工具时例如 {"role": "assistant", "content": "我先回显", "tool_calls": [{"id": "c1", "name": "echo", "arguments": {"text": "hello"}}]}
        """
        ...


class Environment(Protocol):
    """环境协议。具体类例如 LocalEnvironment、ScriptedEnvironment。"""

    workspace: Path

    def execute(self, command: str) -> dict:
        """
        :param command: 要执行的命令。例如 "echo hello"
        :return: 例如 {"output": "hello\\n", "returncode": 0}
        """
        ...