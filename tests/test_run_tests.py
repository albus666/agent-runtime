from agent_runtime.agent import DefaultAgent
from fakes import ScriptedEnvironment
from test_tool_calls import RecordingModel
from evals.coding.run_eval import run_eval


def test_failed_test_command_stays_in_the_loop():
    command = "python -m pytest"
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "跑测试",
            "tool_calls": [
                {"id": "c1", "name": "run_tests", "arguments": {"command": command}},
            ],
        },
        "做完了",
    ])
    env = ScriptedEnvironment(
        outputs={command: "FAILED test_add"},
        returncodes={command: 1},
    )
    result = DefaultAgent(model, env).run("跑一下")

    tool = next(message for message in result.messages if message["role"] == "tool")
    assert '"exit_code": 1' in tool["content"]
    assert "FAILED test_add" in tool["content"]
    assert result.messages[-1] == {"role": "exit", "content": "做完了"}
    assert result.status == "ok"


def test_failed_tool_does_not_stop_the_next_call():
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "先失败再回显",
            "tool_calls": [
                {"id": "c1", "name": "missing", "arguments": {}},
                {"id": "c2", "name": "echo", "arguments": {"text": "bye"}},
            ],
        },
        "做完了",
    ])
    result = DefaultAgent(model, ScriptedEnvironment()).run("继续")

    tools = [message for message in result.messages if message["role"] == "tool"]
    assert [message["tool_call_id"] for message in tools] == ["c1", "c2"]
    assert "not_found" in tools[0]["content"]
    assert tools[1]["content"] == "bye"
    assert result.status == "ok"


def test_denied_test_command_is_not_executed():
    command = "rm hello.py"
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "删掉",
            "tool_calls": [
                {"id": "c1", "name": "run_tests", "arguments": {"command": command}},
            ],
        },
        "做完了",
    ])
    env = ScriptedEnvironment()
    result = DefaultAgent(model, env).run("删掉文件")

    tool = next(message for message in result.messages if message["role"] == "tool")
    assert '"error": "denied"' in tool["content"]
    assert env.history == []
    assert result.status == "ok"


def test_same_failing_command_stops_on_the_third_call():
    command = "python -m pytest"
    calls = [
        {
            "role": "assistant",
            "content": f"第 {index} 次",
            "tool_calls": [
                {"id": f"c{index}", "name": "run_tests", "arguments": {"command": command}},
            ],
        }
        for index in (1, 2, 3)
    ]
    model = RecordingModel([*calls, "做完了"])
    env = ScriptedEnvironment(timeouts=[command])
    result = DefaultAgent(model, env).run("反复跑同一个测试")

    assert env.history == [command, command]
    blob = "\n".join(message["content"] for message in result.messages)
    assert "同一测试命令已连续失败" in blob
    assert result.status == "ok"


def test_coding_eval_passes():
    outcome = run_eval()
    assert outcome["ok"] is True
    assert outcome["steps"] == 2
