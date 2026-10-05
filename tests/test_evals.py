from agent_runtime.agent import DefaultAgent
from agent_runtime.environment import LocalEnvironment
from agent_runtime.permissions import PermissionPolicy
from evals.run_eval import run_fence_tasks
from fakes import ScriptedModel


def test_three_tasks_ok():
    results = run_fence_tasks()
    assert [item["ok"] for item in results] == [True, True, True]


def test_ambiguous_replace_leaves_file_and_finishes(tmp_path):
    original = "x = 1\nx = 1\n"
    (tmp_path / "a.py").write_text(original, encoding="utf-8")
    model = ScriptedModel([
        {
            "role": "assistant",
            "content": "改赋值",
            "tool_calls": [
                {
                    "id": "c1",
                    "name": "str_replace",
                    "arguments": {
                        "path": "a.py",
                        "old_string": "x = 1",
                        "new_string": "x = 2",
                    },
                },
            ],
        },
        "不改了",
    ])
    result = DefaultAgent(
        model,
        LocalEnvironment(tmp_path),
        policy=PermissionPolicy(lambda command: True),
    ).run("改赋值")
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == original
    blob = "\n".join(message["content"] for message in result.messages)
    assert '"error": "ambiguous"' in blob
    assert result.status == "ok"
    assert result.final_text == "不改了"