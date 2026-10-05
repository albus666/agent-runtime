from agent_runtime.agent import DefaultAgent
from agent_runtime.trajectory import load_trajectory
from fakes import ScriptedEnvironment, ScriptedModel


def test_trajectory_matches_messages_without_another_query(tmp_path):
    model = ScriptedModel([
        {
            "role": "assistant",
            "content": "echo",
            "tool_calls": [
                {"id": "c1", "name": "echo", "arguments": {"text": "hi"}},
            ],
        },
        "done",
    ])
    path = tmp_path / "run.jsonl"
    agent = DefaultAgent(model, ScriptedEnvironment(), max_steps=4, trajectory_path=path)
    result = agent.run("say hi")
    calls = model.calls

    loaded = load_trajectory(path)
    assert loaded == result.messages
    assert loaded == agent.messages
    assert model.calls == calls
