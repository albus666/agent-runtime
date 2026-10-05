import json
from pathlib import Path


def save_trajectory(path: Path, step: int, messages: list[dict]) -> None:
    """
    :param path: JSONL 轨迹文件。例如 Path("traj.jsonl")
    :param step: 已经完成的步数。例如 1
    :param messages: 当时的完整历史。例如 [{"role": "user", "content": "echo hello"}, {"role": "assistant", "content": "done"}]
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"step": step, "messages": messages}, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_trajectory(path: Path) -> list[dict]:
    """
    :param path: 已有的轨迹文件。例如 Path("traj.jsonl")
    :return: 文件最后一行里的 messages。例如 [{"role": "exit", "content": "done"}]
    """
    last = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            last = json.loads(line)
    if last is None:
        raise ValueError("empty trajectory")
    return last["messages"]
