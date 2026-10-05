from agent_runtime.agent import DefaultAgent
from agent_runtime.environment import LocalEnvironment
from agent_runtime.tools.rag import rag_tools
from evals.coding.task import ORIGINAL, REPLIES, prepare
from evals.rag.task import INDEX
from evals.run_eval import ScriptedReplies, run_eval


def test_coding_and_rag_both_ok():
    outcome = run_eval()
    assert outcome["coding"]["ok"] is True
    assert outcome["coding"]["steps"] == 2
    assert outcome["rag"]["ok"] is True
    assert outcome["rag"]["steps"] == 3


def test_rag_registry_ignores_coding_writes(tmp_path):
    workspace = prepare(tmp_path)
    result = DefaultAgent(
        ScriptedReplies(REPLIES),
        LocalEnvironment(workspace),
        tools=rag_tools(INDEX),
    ).run("把返回值加 1，然后跑测试")

    assert (workspace / "hello.py").read_text(encoding="utf-8") == ORIGINAL
    blob = "\n".join(message["content"] for message in result.messages)
    assert "未知工具" in blob
    assert result.status == "ok"
    assert result.final_text == "改好了"
