import tempfile
from pathlib import Path

from agent_runtime.agent import DefaultAgent
from agent_runtime.environment import LocalEnvironment
from agent_runtime.permissions import PermissionPolicy
from agent_runtime.tools.rag import rag_tools
from agent_runtime.tools.registry import coding_tools
from evals.coding.task import NAME as CODING_NAME
from evals.coding.task import PROMPT as CODING_PROMPT
from evals.coding.task import REPLIES as CODING_REPLIES
from evals.coding.task import passed as coding_passed
from evals.coding.task import prepare as coding_prepare
from evals.rag.task import INDEX
from evals.rag.task import NAME as RAG_NAME
from evals.rag.task import PROMPT as RAG_PROMPT
from evals.rag.task import REPLIES as RAG_REPLIES
from evals.rag.task import passed as rag_passed
from evals.tasks import TASKS
from fakes import ScriptedEnvironment, ScriptedModel


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


def run_fence_tasks() -> list[dict]:
    """跑三道剧本题。回复是 tool_calls，写入走允许的权限策略。

    :return: 例如 [{"name": "读出常量", "ok": True, "steps": 2}]
    """
    policy = PermissionPolicy(lambda command: True)
    results = []
    for task in TASKS:
        with tempfile.TemporaryDirectory() as directory:
            workspace = task.prepare(Path(directory))
            model = ScriptedModel(list(task.REPLIES))
            env = LocalEnvironment(workspace)
            result = DefaultAgent(model, env, policy=policy).run(task.PROMPT)
            ok = task.passed(result, workspace)
        results.append({
            "name": task.NAME,
            "ok": ok,
            "steps": result.steps,
        })
    return results


def run_eval() -> dict:
    """Coding 和 RAG 都调用 DefaultAgent.run，只是登记表不同。

    :return: 例如 {"coding": {"name": "改返回值并跑测试", "ok": True, "steps": 2}, "rag": {"name": "查出入职日期", "ok": True, "steps": 3}}
    """
    policy = PermissionPolicy(lambda command: True)
    with tempfile.TemporaryDirectory() as directory:
        workspace = coding_prepare(Path(directory))
        env = LocalEnvironment(workspace)
        coding_result = DefaultAgent(
            ScriptedReplies(CODING_REPLIES),
            env,
            policy=policy,
            tools=coding_tools(env, policy),
        ).run(CODING_PROMPT)
        coding = {
            "name": CODING_NAME,
            "ok": coding_passed(coding_result, workspace),
            "steps": coding_result.steps,
        }

    rag_result = DefaultAgent(
        ScriptedReplies(RAG_REPLIES),
        ScriptedEnvironment(),
        tools=rag_tools(INDEX),
    ).run(RAG_PROMPT)
    rag = {
        "name": RAG_NAME,
        "ok": rag_passed(rag_result),
        "steps": rag_result.steps,
    }
    return {"coding": coding, "rag": rag}
