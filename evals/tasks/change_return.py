from pathlib import Path

NAME = "改返回值"
PROMPT = "把返回值加 1"
REPLIES = [
    {
        "role": "assistant",
        "content": "读文件",
        "tool_calls": [
            {"id": "c1", "name": "read_file", "arguments": {"path": "hello.py"}},
        ],
    },
    {
        "role": "assistant",
        "content": "改返回值",
        "tool_calls": [
            {
                "id": "c2",
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
]
ORIGINAL = "def add(a, b):\n    return a + b\n"
EXPECTED = "def add(a, b):\n    return a + b + 1\n"


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
    :param result: DefaultAgent.run 的返回值。例如 RunResult(status="ok", final_text="改好了", steps=3, messages=[])
    :param workspace: prepare 返回的工作区。例如 Path(".../workspace")
    """
    text = (workspace / "hello.py").read_text(encoding="utf-8")
    return result.status == "ok" and text == EXPECTED
