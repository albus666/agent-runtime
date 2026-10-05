import json

from agent_runtime.agent import DefaultAgent
from agent_runtime.event_log import summarize_arguments
from fakes import ScriptedEnvironment, ScriptedModel


def test_argument_summary_keeps_path_and_hides_replacement_text():
    summary = summarize_arguments({
        "path": "hello.py",
        "old_string": "return a + b",
        "new_string": "return a + b + 1",
        "api_key": "sk-secret",
    })
    assert summary == {
        "path": "hello.py",
        "old_string_len": len("return a + b"),
        "new_string_len": len("return a + b + 1"),
    }


def test_run_writes_events_without_file_body_or_system_prompt(tmp_path):
    secret = "SYSTEM PROMPT SHOULD STAY OUT"
    model = ScriptedModel([
        {
            "role": "assistant",
            "content": "改文件",
            "tool_calls": [{
                "id": "c1",
                "name": "str_replace",
                "arguments": {
                    "path": "hello.py",
                    "old_string": "return a + b",
                    "new_string": "return a + b + 1",
                },
            }],
        },
        "改好了",
    ])
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "hello.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    log_path = tmp_path / "logs" / "demo.events.jsonl"
    from agent_runtime.environment import LocalEnvironment
    from agent_runtime.permissions import PermissionPolicy

    result = DefaultAgent(
        model,
        LocalEnvironment(workspace),
        policy=PermissionPolicy(lambda command: True),
        system_prompt=secret,
        event_log=log_path,
        max_steps=4,
    ).run("修改 hello.py")

    assert result.status == "ok"
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    events = [row["event"] for row in rows]
    assert events[0] == "run_started"
    assert "model_requested" in events
    assert "model_replied" in events
    assert "tool_started" in events
    assert "tool_finished" in events
    assert events[-1] == "run_finished"
    blob = log_path.read_text(encoding="utf-8")
    assert secret not in blob
    assert "return a + b" not in blob
    started = next(row for row in rows if row["event"] == "tool_started")
    assert started["arguments"]["path"] == "hello.py"
    assert "old_string_len" in started["arguments"]
    finished = next(row for row in rows if row["event"] == "tool_finished")
    assert finished["ok"] is True
    assert "duration_ms" in finished
    assert rows[-1]["status"] == "ok"
