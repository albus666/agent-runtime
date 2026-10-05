from agent_runtime.agent import FORMAT_ERROR, DefaultAgent
from fakes import ScriptedEnvironment, ScriptedModel


def _agent(model, env, max_steps=4, trajectory_path=None):
    return DefaultAgent(model, env, max_steps=max_steps, trajectory_path=trajectory_path)


def _echo(text):
    return {
        "role": "assistant",
        "content": "echo",
        "tool_calls": [
            {"id": "c1", "name": "echo", "arguments": {"text": text}},
        ],
    }


def test_final_answer_stops():
    model = ScriptedModel(["done"])
    result = _agent(model, ScriptedEnvironment()).run("say hi")
    assert result.status == "ok"
    assert result.steps == 1
    assert result.messages[-1]["role"] == "exit"
    assert result.final_text == "done"


def test_command_then_final_answer():
    model = ScriptedModel([_echo("hi"), "done"])
    result = _agent(model, ScriptedEnvironment()).run("say hi")
    assert result.status == "ok"
    assert result.steps == 2
    blob = "\n".join(message["content"] for message in result.messages)
    assert "hi" in blob
    assert result.final_text == "done"


def test_format_error_then_recovers():
    model = ScriptedModel(["", "done"])
    env = ScriptedEnvironment()
    result = _agent(model, env).run("do it")
    blob = "\n".join(message["content"] for message in result.messages)
    assert FORMAT_ERROR in blob
    assert result.status == "ok"
    assert env.history == []


def test_markdown_code_block_is_not_executed():
    text = "```bash\necho hacked\n```"
    model = ScriptedModel([text])
    env = ScriptedEnvironment()
    result = _agent(model, env).run("do something")
    assert env.history == []
    assert result.status == "ok"
    assert result.final_text == text


def test_max_steps_stops_before_another_query():
    model = ScriptedModel([_echo("hi"), "should not be used"])
    result = _agent(model, ScriptedEnvironment(), max_steps=1).run("loop")
    assert result.status == "max_steps"
    assert result.messages[-1] == {"role": "exit", "content": "stopped: max_steps reached"}
    assert result.final_text == "stopped: max_steps reached"
    assert model.calls == 1


def test_timeout_then_recovers():
    command = "python -m pytest"
    model = ScriptedModel([
        {
            "role": "assistant",
            "content": "跑测试",
            "tool_calls": [
                {"id": "c1", "name": "run_tests", "arguments": {"command": command}},
            ],
        },
        "done",
    ])
    env = ScriptedEnvironment(timeouts=[command])
    result = _agent(model, env).run("wait")
    blob = "\n".join(message["content"] for message in result.messages)
    assert '"error": "timeout"' in blob
    assert result.status == "ok"
    assert result.final_text == "done"
