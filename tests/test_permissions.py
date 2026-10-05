from agent_runtime.agent import DefaultAgent
from agent_runtime.permissions import PermissionPolicy
from fakes import ScriptedModel, ScriptedEnvironment


def _run_tests(command):
    return {
        "role": "assistant",
        "content": "跑测试",
        "tool_calls": [
            {"id": "c1", "name": "run_tests", "arguments": {"command": command}},
        ],
    }


def test_test_command_is_executed():
    command = "python -m pytest"
    model = ScriptedModel([_run_tests(command), "done"])
    env = ScriptedEnvironment()
    result = DefaultAgent(model, env, policy=PermissionPolicy(lambda command: True)).run("跑测试")
    assert result.status == "ok"
    assert env.history == [command]


def test_dangerous_command_is_denied():
    model = ScriptedModel([_run_tests("rm -rf /"), "done"])
    env = ScriptedEnvironment()
    result = DefaultAgent(model, env, policy=PermissionPolicy(lambda command: True)).run("删掉")
    assert env.history == []
    blob = "\n".join(message["content"] for message in result.messages)
    assert '"error": "denied"' in blob


def test_redirect_asks():
    command = "python -m pytest > a.txt"
    denied_env = ScriptedEnvironment()
    denied = DefaultAgent(
        ScriptedModel([_run_tests(command), "done"]),
        denied_env,
        policy=PermissionPolicy(lambda command: False),
    ).run("写文件")
    assert denied_env.history == []
    blob = "\n".join(message["content"] for message in denied.messages)
    assert '"error": "denied"' in blob

    allowed_env = ScriptedEnvironment()
    DefaultAgent(
        ScriptedModel([_run_tests(command), "done"]),
        allowed_env,
        policy=PermissionPolicy(lambda command: True),
    ).run("写文件")
    assert allowed_env.history == [command]


def test_returncode_1():
    command = "python -m pytest"
    model = ScriptedModel([_run_tests(command), "done"])
    env = ScriptedEnvironment(returncodes={command: 1})
    result = DefaultAgent(model, env).run("跑测试")
    blob = "\n".join(message["content"] for message in result.messages)
    assert '"exit_code": 1' in blob
    assert result.status == "ok"
