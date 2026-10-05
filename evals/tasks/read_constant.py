from pathlib import Path

NAME = "读出常量"
PROMPT = "读出常量"
REPLIES = [
    {
        "role": "assistant",
        "content": "读常量",
        "tool_calls": [
            {"id": "c1", "name": "read_file", "arguments": {"path": "const.py"}},
        ],
    },
    "答案是 42",
]


def prepare(root: Path) -> Path:
    """
    :param root: 临时根目录。例如 tempfile.TemporaryDirectory() 里的 Path
    :return: 工作区目录。例如 root / "workspace"
    """
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "const.py").write_text("VALUE = 42\n", encoding="utf-8")
    return workspace


def passed(result, workspace: Path) -> bool:
    """
    :param result: DefaultAgent.run 的返回值。例如 RunResult(status="ok", final_text="答案是 42", steps=2, messages=[])
    :param workspace: prepare 返回的工作区。例如 Path(".../workspace")
    """
    return result.status == "ok" and "42" in result.final_text
