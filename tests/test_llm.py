"""
模拟openai结构
client
└── chat
    └── completions
        └── create()
            └── response
                └── choices[0]
                    └── message
                        ├── role
                        └── content
"""
import pytest

from agent_runtime.agent import Agent
from agent_runtime.llm import OpenAICompatModel
from fakes import ScriptedEnvironment


class FakeMessage:
    def __init__(self, content: str, role: str = "assistant", tool_calls=None):
        self.content = content
        self.role = role
        self.tool_calls = tool_calls


class FakeChoice:
    def __init__(self, message: FakeMessage):
        self.message = message


class FakeResponse:
    def __init__(self, content: str, tool_calls=None):
        self.choices = [FakeChoice(FakeMessage(content, tool_calls=tool_calls))]


class FakeCompletions:
    def __init__(self, content: str):
        self.content = content
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return FakeResponse(self.content)


class FakeClient:
    def __init__(self, content: str):
        # 自引用，chat变为client自己的别名，client.chat.completions==client.completions
        self.chat = self
        self.completions = FakeCompletions(content)

def test_query_returns_assistant_text():
    content = "```bash\necho hi\n```"
    client = FakeClient(content)
    model = OpenAICompatModel(client, model="fake")
    result = model.query([{"role": "user", "content": "say hi"}])
    assert result == {"role": "assistant", "content": content}

def test_exit_is_not_sent_to_the_client():
    client = FakeClient("done")
    model = OpenAICompatModel(client, model="fake")
    agent = Agent("demo", "system", 4, model, ScriptedEnvironment())
    history = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
        {"role": "exit", "content": "done"},
    ]
    agent._call_llm(history)
    sent = client.completions.kwargs["messages"]
    assert all(item["role"] != "exit" for item in sent)
    assert history[-1]["role"] == "exit"


class Function:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class ProviderCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = Function(name, arguments)


class SequenceCompletions:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content, tool_calls = self.replies.pop(0)
        return FakeResponse(content, tool_calls)


class SequenceClient:
    def __init__(self, replies):
        self.chat = self
        self.completions = SequenceCompletions(replies)


def test_tool_schema_is_sent_and_call_is_parsed():
    call = ProviderCall("call_1", "echo", '{"text": "hello"}')
    client = SequenceClient([
        ("我先回显", [call]),
        ("做完了", None),
    ])
    model = OpenAICompatModel(client, model="fake")
    from agent_runtime.agent import DefaultAgent

    result = DefaultAgent(model, ScriptedEnvironment()).run("echo hello")

    sent_tools = client.completions.calls[0]["tools"]
    names = [item["function"]["name"] for item in sent_tools]
    assert "echo" in names
    assert "read_file" in names

    assistant = next(message for message in result.messages if message["role"] == "assistant")
    assert assistant["tool_calls"] == [
        {"id": "call_1", "name": "echo", "arguments": {"text": "hello"}},
    ]
    second = client.completions.calls[1]["messages"]
    provider_call = next(message for message in second if message["role"] == "assistant")
    tool_result = next(message for message in second if message["role"] == "tool")
    assert provider_call["tool_calls"][0]["function"]["name"] == "echo"
    assert provider_call["tool_calls"][0]["function"]["arguments"] == '{"text": "hello"}'
    assert tool_result["tool_call_id"] == "call_1"
    assert tool_result["content"] == "hello"
    assert result.status == "ok"


def test_invalid_tool_arguments_become_empty_dict():
    call = ProviderCall("call_1", "echo", "{not json")
    client = SequenceClient([("{not json", [call])])
    model = OpenAICompatModel(client, model="fake")
    result = model.query([{"role": "user", "content": "echo"}])
    assert result["tool_calls"] == [{"id": "call_1", "name": "echo", "arguments": {}}]


def test_timeout_is_retried_then_succeeds():
    class TimeoutOnce:
        def __init__(self):
            self.calls = 0
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("timed out")
            return FakeResponse("做完了")

    client = TimeoutOnce()
    result = OpenAICompatModel(client, model="fake").query([{"role": "user", "content": "hi"}])
    assert client.calls == 2
    assert result["content"] == "做完了"


def test_context_limit_is_not_retried():
    class ContextClient:
        def __init__(self):
            self.calls = 0
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            self.calls += 1
            raise RuntimeError("maximum context length exceeded")

    from agent_runtime.errors import ModelRequestError

    client = ContextClient()
    with pytest.raises(ModelRequestError, match="context_limit"):
        OpenAICompatModel(client, model="fake").query([{"role": "user", "content": "hi"}])
    assert client.calls == 1


def test_from_env_requires_settings(monkeypatch):
    monkeypatch.setattr("agent_runtime.llm.load_dotenv", lambda: None)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ValueError, match="LLM_MODEL"):
        OpenAICompatModel.from_env()

