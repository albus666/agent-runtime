from agent_runtime.agent import DefaultAgent
from agent_runtime.environment import LocalEnvironment
from agent_runtime.tools.rag import rag_tools
from evals.rag.run_eval import run_eval
from evals.rag.task import INDEX, QUOTE
from fakes import ScriptedEnvironment
from test_tool_calls import RecordingModel


def test_search_returns_chunk_id_and_read_chunk_returns_text():
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "先搜索",
            "tool_calls": [
                {"id": "s1", "name": "search_docs", "arguments": {"query": "入职"}},
            ],
        },
        {
            "role": "assistant",
            "content": "再读原文",
            "tool_calls": [
                {"id": "s2", "name": "read_chunk", "arguments": {"id": "c1"}},
            ],
        },
        QUOTE,
    ])
    result = DefaultAgent(
        model,
        ScriptedEnvironment(),
        tools=rag_tools(INDEX),
    ).run("星河哪一天入职？")

    search = next(message for message in result.messages if message.get("tool_call_id") == "s1")
    chunk = next(message for message in result.messages if message.get("tool_call_id") == "s2")
    assert "c1" in search["content"]
    assert QUOTE in chunk["content"]
    assert result.status == "ok"


def test_str_replace_is_unknown_and_does_not_write(tmp_path):
    file = tmp_path / "hello.py"
    original = "return a + b\n"
    file.write_text(original, encoding="utf-8")
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "改文件",
            "tool_calls": [
                {
                    "id": "c1",
                    "name": "str_replace",
                    "arguments": {
                        "path": "hello.py",
                        "old_string": "return a + b",
                        "new_string": "return a + b + 1",
                    },
                },
            ],
        },
        "做完了",
    ])
    result = DefaultAgent(
        model,
        LocalEnvironment(tmp_path),
        tools=rag_tools(INDEX),
    ).run("把返回值加 1")

    assert file.read_text(encoding="utf-8") == original
    blob = "\n".join(message["content"] for message in result.messages)
    assert "未知工具" in blob
    assert result.messages[-1] == {"role": "exit", "content": "做完了"}
    assert result.status == "ok"


def test_rag_eval_passes():
    outcome = run_eval()
    assert outcome["ok"] is True
    assert outcome["steps"] == 3
