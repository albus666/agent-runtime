from agent_runtime.agent import DefaultAgent
from fakes import ScriptedEnvironment, ScriptedModel


class RecordingModel(ScriptedModel):
    """记录每次 query 收到的消息。"""

    def __init__(self, replies):
        super().__init__(replies)
        self.queries = []

    def query(self, messages, tools=None):
        self.queries.append([dict(message) for message in messages])
        self.calls += 1
        reply = self._replies.pop(0)
        if isinstance(reply, dict):
            return reply
        return {"role": "assistant", "content": reply}


def test_text_without_tool_calls_exits():
    model = RecordingModel(["做完了"])
    result = DefaultAgent(model, ScriptedEnvironment()).run("say hi")

    assert result.status == "ok"
    assert result.messages[-1] == {"role": "exit", "content": "做完了"}
    assert all(message.get("role") != "exit" for query in model.queries for message in query)


def test_echo_result_is_visible_on_next_query():
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "我先回显",
            "tool_calls": [
                {"id": "c1", "name": "echo", "arguments": {"text": "hello"}}
            ],
        },
        "做完了",
    ])
    result = DefaultAgent(model, ScriptedEnvironment()).run("say hi")

    assert result.status == "ok"
    assert result.messages[-1] == {"role": "exit", "content": "做完了"}
    assert all(message.get("role") != "exit" for query in model.queries for message in query)
    assert any(
        message.get("role") == "tool" and message.get("content") == "hello"
        for message in model.queries[1]
    )


def test_unknown_tool_is_observation_then_exits():
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "我先回显",
            "tool_calls": [
                {"id": "c1", "name": "read", "arguments": {"text": "hello"}}
            ],
        },
        "做完了",
    ])
    result = DefaultAgent(model, ScriptedEnvironment()).run("say hi")

    assert any("not_found" in message['content'] for message in result.messages)
    assert result.messages[-1] == {"role": "exit", "content": "做完了"}
    assert result.status == "ok"


def test_two_tool_calls_run_in_order():
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "我先回显",
            "tool_calls": [
                {"id": "c1", "name": "echo", "arguments": {"text": "hello"}},
                {"id": "c2", "name": "echo", "arguments": {"text": "bye"}},
            ],
        },
        "做完了",
    ])
    result = DefaultAgent(model, ScriptedEnvironment()).run("say hi and bye")

    tools = [message for message in result.messages if message["role"] == "tool"]
    assert [message["content"] for message in tools] == ["hello", "bye"]
    assert [message["tool_call_id"] for message in tools] == ["c1", "c2"]
    assert result.status == "ok"