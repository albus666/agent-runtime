from agent_runtime.agent import DefaultAgent
from fakes import ScriptedEnvironment, ScriptedModel


class RecordingModel(ScriptedModel):
    """记录每次 query 收到的消息，返回格式仍是原来的助手字典。"""

    def __init__(self, replies: list[str]):
        super().__init__(replies)
        self.queries: list[list[dict]] = []

    def query(self, messages: list[dict], tools=None) -> dict:
        self.queries.append([dict(message) for message in messages])
        return super().query(messages)


def test_exit_is_kept_but_not_sent_to_query():
    model = RecordingModel(["done"])
    result = DefaultAgent(model, ScriptedEnvironment()).run("say hi")
    assert result.messages[-1]["role"] == "exit"
    assert all(message.get("role") != "exit" for message in model.queries[0])


def test_steering_is_visible_on_the_next_query():
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "echo",
            "tool_calls": [
                {"id": "c1", "name": "echo", "arguments": {"text": "hi"}},
            ],
        },
        "done",
    ])
    env = ScriptedEnvironment()
    agent = DefaultAgent(model, env)

    def inject(running):
        if running.steps == 1:
            running.push_steering("顺便加测试")

    agent.after_query = inject
    result = agent.run("do the task")

    assert any(message["content"] == "顺便加测试" for message in model.queries[1])
    steering_at = next(i for i, message in enumerate(result.messages) if message["content"] == "顺便加测试")
    second_reply = next(
        i for i, message in enumerate(result.messages)
        if message["role"] == "assistant" and message["content"] == "done"
    )
    assert steering_at < second_reply
    assert result.status == "ok"


def test_followup_runs_after_the_first_final_answer():
    model = RecordingModel(["先这样", "第二个回答"])
    agent = DefaultAgent(model, ScriptedEnvironment())

    def inject(running):
        if running.steps == 1:
            running.push_followup("再写一个测试")

    agent.after_query = inject
    result = agent.run("write something")

    assert result.steps == 2
    assert any(message["content"] == "再写一个测试" for message in model.queries[1])
    assert [message["content"] for message in result.messages if message["role"] == "exit"] == [
        "先这样",
        "第二个回答",
    ]
    assert result.status == "ok"
    assert result.final_text == "第二个回答"


def test_steering_before_exit_and_followup_after():
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "echo",
            "tool_calls": [
                {"id": "c1", "name": "echo", "arguments": {"text": "hi"}},
            ],
        },
        "先完成",
        "再完成",
    ])
    env = ScriptedEnvironment()
    agent = DefaultAgent(model, env)

    def inject(running):
        if running.steps == 1:
            running.push_steering("顺便加测试")
            running.push_followup("再写一个测试")

    agent.after_query = inject
    result = agent.run("do both")

    assert any(message["content"] == "顺便加测试" for message in model.queries[1])
    assert any(message["content"] == "再写一个测试" for message in model.queries[2])
    steering_at = next(i for i, message in enumerate(result.messages) if message["content"] == "顺便加测试")
    first_exit = next(i for i, message in enumerate(result.messages) if message["role"] == "exit")
    followup_at = next(i for i, message in enumerate(result.messages) if message["content"] == "再写一个测试")
    assert steering_at < first_exit < followup_at
    assert result.status == "ok"
