from agent_runtime.agent import DefaultAgent
from agent_runtime.environment import LocalEnvironment
from agent_runtime.permissions import PermissionPolicy
from test_tool_calls import RecordingModel


def test_read_file_content_is_visible_on_next_query(tmp_path):
    (tmp_path / "hello.py").write_text("VALUE = 42\n", encoding="utf-8")
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "我先读文件",
            "tool_calls": [
                {"id": "c1", "name": "read_file", "arguments": {"path": "hello.py"}},
            ],
        },
        "做完了",
    ])
    result = DefaultAgent(model, LocalEnvironment(tmp_path)).run("读出常量")

    assert result.status == "ok"
    assert any(
        "VALUE = 42" in message.get("content", "")
        for message in model.queries[1]
    )


def test_grep_finds_relative_path(tmp_path):
    (tmp_path / "hello.py").write_text("VALUE = 42\n", encoding="utf-8")
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "我先搜索",
            "tool_calls": [
                {"id": "c1", "name": "grep", "arguments": {"pattern": "VALUE"}},
            ],
        },
        "做完了",
    ])
    result = DefaultAgent(model, LocalEnvironment(tmp_path)).run("找出 VALUE")

    assert result.status == "ok"
    seen = "\n".join(message.get("content", "") for message in model.queries[1])
    assert "hello.py:1:VALUE = 42" in seen


def test_str_replace_changes_the_unique_match(tmp_path):
    file = tmp_path / "hello.py"
    file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "我来改",
            "tool_calls": [
                {
                    "id": "c1",
                    "name": "str_replace",
                    "arguments": {
                        "path": "hello.py",
                        "old_string": "return a + b",
                        "new_string": "return a + b + 1",
                    },
                },
            ],
        },
        "改好了",
    ])
    result = DefaultAgent(
        model,
        LocalEnvironment(tmp_path),
        policy=PermissionPolicy(lambda command: True),
    ).run("把返回值加 1")

    assert result.status == "ok"
    assert file.read_text(encoding="utf-8") == "def add(a, b):\n    return a + b + 1\n"


def test_str_replace_ambiguous_leaves_file_unchanged(tmp_path):
    file = tmp_path / "hello.py"
    original = "x = 1\nx = 1\n"
    file.write_text(original, encoding="utf-8")
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "两处都改",
            "tool_calls": [
                {
                    "id": "c1",
                    "name": "str_replace",
                    "arguments": {
                        "path": "hello.py",
                        "old_string": "x = 1",
                        "new_string": "x = 2",
                    },
                },
            ],
        },
        "做完了",
    ])
    result = DefaultAgent(
        model,
        LocalEnvironment(tmp_path),
        policy=PermissionPolicy(lambda command: True),
    ).run("改赋值")

    assert file.read_text(encoding="utf-8") == original
    blob = "\n".join(message["content"] for message in result.messages)
    assert "ambiguous" in blob
    assert result.status == "ok"


def test_str_replace_parent_path_is_denied(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("secret-42\n", encoding="utf-8")
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "改上级文件",
            "tool_calls": [
                {
                    "id": "c1",
                    "name": "str_replace",
                    "arguments": {
                        "path": "../secret.txt",
                        "old_string": "secret-42",
                        "new_string": "stolen",
                    },
                },
            ],
        },
        "做完了",
    ])
    result = DefaultAgent(
        model,
        LocalEnvironment(workspace),
        policy=PermissionPolicy(lambda command: True),
    ).run("读取上级目录里的秘密文件")

    assert secret.read_text(encoding="utf-8") == "secret-42\n"
    blob = "\n".join(message["content"] for message in result.messages)
    assert '"error": "denied"' in blob
    assert result.status == "ok"


def test_str_replace_ask_refuses_without_writing(tmp_path):
    file = tmp_path / "hello.py"
    original = "return a + b\n"
    file.write_text(original, encoding="utf-8")
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "我来改",
            "tool_calls": [
                {
                    "id": "c1",
                    "name": "str_replace",
                    "arguments": {
                        "path": "hello.py",
                        "old_string": "return a + b",
                        "new_string": "return a + b + 1",
                    },
                },
            ],
        },
        "做完了",
    ])
    result = DefaultAgent(
        model,
        LocalEnvironment(tmp_path),
        policy=PermissionPolicy(lambda command: False),
    ).run("把返回值加 1")

    assert file.read_text(encoding="utf-8") == original
    blob = "\n".join(message["content"] for message in result.messages)
    assert '"error": "denied"' in blob
    assert result.status == "ok"
