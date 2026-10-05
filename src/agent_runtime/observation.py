import json


def _observation(
    command: str,
    exit_code: str,
    output: str,
    error: str | None = None,
    tool: str | None = None,
) -> str:
    """把一次工具结果写成 JSON 字符串。

    :param command: 命令或路径。例如 "python -m pytest test_hello.py -q"
    :param exit_code: 例如 "0"；拒绝或超时时为 "null"
    :param output: 例如 "1 passed"。没有输出时传 ""
    :param error: 例如 "denied"、"timeout"、"not_found"。成功时不传
    :param tool: 工具名。例如 "run_tests"。不传时与 command 相同
    :return: 例如 {"tool": "run_tests", "ok": false, "error": "timeout", "exit_code": null, "output": "", "command": "python -m pytest -q"}
    """
    if exit_code in (None, "null", ""):
        code = None
    else:
        code = int(exit_code) if str(exit_code).lstrip("-").isdigit() else exit_code
    payload = {
        "tool": tool or command,
        "ok": error is None and code == 0,
        "exit_code": code,
        "output": output or "",
        "command": command,
    }
    if error:
        payload["error"] = error
    return json.dumps(payload, ensure_ascii=False)
