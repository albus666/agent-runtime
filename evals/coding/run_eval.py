import tempfile
from pathlib import Path

from agent_runtime.agent import DefaultAgent
from agent_runtime.environment import LocalEnvironment
from agent_runtime.permissions import PermissionPolicy
from evals.coding.task import PROMPT, REPLIES, prepare, passed


class ScriptedReplies:
    """按剧本返回整份回复。字典原样返回，字符串包成只有正文的助手回复。"""

    def __init__(self, replies):
        self._replies = list(replies)

    def query(self, messages, tools=None):
        """
        :param messages: 本轮送给模型的历史
        :return: 剧本中的下一条回复
        """
        reply = self._replies.pop(0)
        if isinstance(reply, dict):
            return reply
        return {"role": "assistant", "content": reply}


def run_eval() -> dict:
    """跑改返回值这道剧本题。

    :return: 例如 {"name": "改返回值并跑测试", "ok": True, "steps": 2}
    """
    from evals.coding.task import NAME

    with tempfile.TemporaryDirectory() as directory:
        workspace = prepare(Path(directory))
        result = DefaultAgent(
            ScriptedReplies(REPLIES),
            LocalEnvironment(workspace),
            policy=PermissionPolicy(lambda command: True),
        ).run(PROMPT)
        ok = passed(result, workspace)
        steps = result.steps
    return {"name": NAME, "ok": ok, "steps": steps}
