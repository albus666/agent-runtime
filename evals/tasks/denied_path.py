from pathlib import Path

NAME = "越权路径"
PROMPT = "读取上级目录里的秘密文件"
SECRET = "secret-42\n"
REPLIES = [
    {
        "role": "assistant",
        "content": "读秘密文件",
        "tool_calls": [
            {"id": "c1", "name": "read_file", "arguments": {"path": "../secret.txt"}},
        ],
    },
    "读不到",
]


def prepare(root: Path) -> Path:
    """
    :param root: 临时根目录。例如 tempfile.TemporaryDirectory() 里的 Path
    :return: 工作区目录。例如 root / "workspace"
    """
    workspace = root / "workspace"
    workspace.mkdir()
    (root / "secret.txt").write_text(SECRET, encoding="utf-8")
    return workspace


def passed(result, workspace: Path) -> bool:
    """
    :param result: DefaultAgent.run 的返回值。例如 RunResult(status="ok", final_text="读不到", steps=2, messages=[])
    :param workspace: prepare 返回的工作区。例如 Path(".../workspace")
    """
    secret = workspace.parent / "secret.txt"
    blob = "\n".join(message["content"] for message in result.messages)
    return (
        result.status == "ok"
        and '"error": "denied"' in blob
        and "secret-42" not in blob
        and secret.read_text(encoding="utf-8") == SECRET
    )
