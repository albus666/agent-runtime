"""轻量事件日志。只追加 JSONL，不保存完整上下文。"""
import json
from datetime import datetime
from pathlib import Path

_SECRET_KEYS = {"api_key", "authorization", "token", "password"}
_LENGTH_KEYS = {"old_string", "new_string", "content", "text", "output", "system_prompt"}


class EventLogger:
    """把一轮运行的事件追加到一个 JSONL 文件。"""

    def __init__(self, path: str | Path, run_id: str | None = None):
        """
        :param path: 例如 Path("logs/coding-demo.events.jsonl")
        :param run_id: 例如 "run_20261004T184554"。不传时按当前时间生成
        """
        self.path = Path(path)
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        self.run_id = run_id or f"run_{stamp}"

    def emit(self, event: str, **fields) -> None:
        """
        :param event: 例如 "tool_finished"
        :param fields: 事件字段。例如 step=1, tool="read_file"
        """
        record = {
            "event": event,
            "run_id": self.run_id,
            "time": datetime.now().isoformat(timespec="seconds"),
        }
        record.update(fields)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def summarize_arguments(arguments: dict | None) -> dict:
    """参数只留短字段。替换原文和长文本只记长度。

    :param arguments: 例如 {"path": "hello.py", "old_string": "return a + b"}
    :return: 例如 {"path": "hello.py", "old_string_len": 12}
    """
    summary = {}
    for key, value in (arguments or {}).items():
        if key.lower() in _SECRET_KEYS:
            continue
        if key in _LENGTH_KEYS or (isinstance(value, str) and len(value) > 80):
            summary[f"{key}_len"] = len(str(value))
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            summary[key] = value
            continue
        summary[f"{key}_len"] = len(json.dumps(value, ensure_ascii=False))
    return summary


def summarize_result(text: str) -> tuple[bool, str]:
    """工具返回值收成一句摘要。

    :param text: 工具写进历史的字符串。例如一段 JSON，或读到的文件正文
    :return: (是否成功, 摘要)。例如 (False, "1 failed")
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return True, f"{len(text)} chars"
    if not isinstance(payload, dict):
        return True, f"{len(text)} chars"
    if "error" in payload and payload.get("ok") is not True:
        return False, str(payload.get("error") or "failed")
    output = str(payload.get("output") or "")
    lines = [line for line in output.strip().splitlines() if line.strip()]
    if lines and ("passed" in lines[-1] or "failed" in lines[-1].lower()):
        return bool(payload.get("ok")), lines[-1][:120]
    if payload.get("ok") is True and isinstance(payload.get("data"), dict):
        names = ",".join(list(payload["data"])[:8])
        return True, f"fields {names}" if names else "ok"
    if payload.get("ok") is True:
        return True, f"{len(output)} chars" if output else "ok"
    if payload.get("ok") is False:
        return False, str(payload.get("error") or "failed")
    return True, f"{len(text)} chars"


def clip_text(value: str, limit: int = 160) -> str:
    """
    :param value: 原始任务文本
    :param limit: 保留的最大字符数。例如 160
    :return: 超长时截断并标出原长度
    """
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + f"...({len(text)} chars)"
