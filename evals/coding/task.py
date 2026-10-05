from pathlib import Path

NAME = "改返回值并跑测试"
PROMPT = "把返回值加 1，然后跑测试"
ORIGINAL = "def add(a, b):\n    return a + b\n"
EXPECTED = "def add(a, b):\n    return a + b + 1\n"
COMMAND = "python -c \"import hello; assert hello.add(1, 2) == 4; print('tests passed')\""
REPLIES = [
    {
        "role": "assistant",
        "content": "先读，再改，再跑测试",
        "tool_calls": [
            {"id": "c1", "name": "read_file", "arguments": {"path": "hello.py"}},
            {
                "id": "c2",
                "name": "str_replace",
                "arguments": {
                    "path": "hello.py",
                    "old_string": "return a + b",
                    "new_string": "return a + b + 1",
                },
            },
            {"id": "c3", "name": "run_tests", "arguments": {"command": COMMAND}},
        ],
    },
    "改好了",
]


def prepare(root: Path) -> Path:
    """
    :param root: 临时根目录。例如 tempfile.TemporaryDirectory() 里的 Path
    :return: 工作区目录。例如 root / "workspace"
    """
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "hello.py").write_text(ORIGINAL, encoding="utf-8")
    return workspace


def passed(result, workspace: Path) -> bool:
    """
    :param result: DefaultAgent.run 的返回值。例如 RunResult(status="ok", final_text="改好了", steps=2, messages=[])
    :param workspace: prepare 返回的工作区。例如 Path(".../workspace")
    """
    text = (workspace / "hello.py").read_text(encoding="utf-8")
    blob = "\n".join(message["content"] for message in result.messages)
    return result.status == "ok" and text == EXPECTED and "tests passed" in blob
