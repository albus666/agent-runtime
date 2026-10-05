from agent_runtime.agent import DefaultAgent
from agent_runtime.environment import LocalEnvironment
from fakes import ScriptedModel


def test_echo_returns_output(tmp_path):
    env = LocalEnvironment(tmp_path)
    result = env.execute("echo hello")
    assert result["returncode"] == 0
    assert "hello" in result["output"]


def test_redirect_stays_in_workspace(tmp_path):
    env = LocalEnvironment(tmp_path)
    env.execute("echo hello > note.txt")
    assert (tmp_path / "note.txt").is_file()
    assert not (tmp_path.parent / "note.txt").exists()


def test_timeout_is_observed_and_run_finishes(tmp_path):
    command = 'python -c "import time; time.sleep(5); assert True"'
    env = LocalEnvironment(tmp_path, timeout=0.2)
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
    result = DefaultAgent(model=model, env=env).run("计时")
    assert result.status == "ok"
    text = "\n".join(message["content"] for message in result.messages)
    assert '"error": "timeout"' in text


def test_long_output_is_truncated(tmp_path):
    env = LocalEnvironment(tmp_path, max_output=5)
    result = env.execute("echo hello")
    assert result["output"].endswith("[truncated]")
    assert len(result["output"]) <= 5 + len("\n[truncated]")
