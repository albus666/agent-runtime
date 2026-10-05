from agent_runtime.agent import DefaultAgent
from agent_runtime.tools.rag import rag_tools
from evals.rag.task import INDEX, NAME, PROMPT, REPLIES, passed
from fakes import ScriptedEnvironment


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
    """跑只读检索这道剧本题。

    :return: 例如 {"name": "查出入职日期", "ok": True, "steps": 3}
    """
    result = DefaultAgent(
        ScriptedReplies(REPLIES),
        ScriptedEnvironment(),
        tools=rag_tools(INDEX),
    ).run(PROMPT)
    return {"name": NAME, "ok": passed(result), "steps": result.steps}
