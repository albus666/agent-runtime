# tests/fakes.py
from pathlib import Path


class ScriptedModel:
    """按剧本返回的假模型，不联网。例如 ScriptedModel(["done"])。"""

    def __init__(self, replies: list[str]):
        """
        :param replies: 按 query 次数依次弹出。字符串包成正文，字典原样返回。例如 ["done"] 或 [{"role": "assistant", "content": "读文件", "tool_calls": [{"id": "c1", "name": "read_file", "arguments": {"path": "hello.py"}}]}]
        """
        self._replies = list(replies)
        self.calls = 0

    def query(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """
        :param messages: 本轮送给模型的历史。例如 [{"role": "user", "content": "echo hello"}]
        :param tools: 工具 schema。剧本模型忽略它。例如 None
        :return: 字符串例如 {"role": "assistant", "content": "done"}。字典原样返回，可带 tool_calls
        """
        self.calls += 1
        if not self._replies:
            raise IndexError("scripted replies exhausted")
        reply = self._replies.pop(0)
        if isinstance(reply, dict):
            return reply
        return {"role": "assistant", "content": reply}


class ScriptedEnvironment:
    """按表返回的假环境，不真的执行命令。例如 ScriptedEnvironment({"echo hello": "hello"})."""

    def __init__(self, outputs=None, timeouts=None, returncodes=None):
        """
        workspace 固定为 Path(".")，用来满足 Environment。这个假环境不读文件，测试也不会用到这个路径。

        :param outputs: 命令到标准输出。例如 {"echo hello": "hello\\n"}
        :param timeouts: 会超时的命令。例如 ["sleep 5"]
        :param returncodes: 命令到退出码。例如 {"echo hello": 1}，没写的命令是 0
        """
        self.workspace = Path(".")
        self._outputs = outputs or {}
        self._timeouts = set(timeouts or [])
        self._returncodes = returncodes or {}
        self.history = []

    def execute(self, command):
        """
        :param command: 要假装执行的命令。例如 "echo hello"
        :return: 例如 {"output": "hello\\n", "returncode": 0}
        """
        self.history.append(command)
        if command in self._timeouts:
            raise TimeoutError(f"命令超时: {command}")
        output = self._outputs.get(command, "")
        return {"output": output, "returncode": self._returncodes.get(command, 0)}
