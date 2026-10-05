from ..observation import _observation
from .registry import ToolSpec


def run_tests(env, policy, arguments: dict) -> str:
    """在工作区里执行一条测试命令。退出码不是 0 时仍返回结果，不中断循环。

    :param env: 提供 execute 的环境。例如 LocalEnvironment(tmp_path) 或 ScriptedEnvironment(returncodes={"python -m pytest": 1})
    :param policy: 命令权限。例如 PermissionPolicy(lambda command: False)
    :param arguments: 工具参数。例如 {"command": "python -m pytest"}
    :return: 观察文本，含 exit_code 和输出。例如 exit_code 为 1、output 为 "FAILED test_add"
    """
    command = str(arguments.get("command", "")).strip()
    if not command:
        return _observation(command or "run_tests", "null", "缺少 command 参数", error="invalid_argument", tool="run_tests")
    if not _is_test_command(command):
        return _observation(command, "null", "只允许执行测试命令", error="denied", tool="run_tests")
    if policy.decide(command) == "deny":
        return _observation(command, "null", "命令未获允许", error="denied", tool="run_tests")
    try:
        result = env.execute(command)
    except TimeoutError:
        return _observation(command, "null", "", error="timeout", tool="run_tests")
    code = result.get("returncode", 0)
    output = result.get("output", "")
    error = None if code == 0 else "test_failed"
    return _observation(command, str(code), output, error=error, tool="run_tests")


def _is_test_command(command: str) -> bool:
    """只放行测试命令。例如 "python -m pytest"、"pytest -q"，或带 assert 的 "python -c"。

    :param command: 去掉首尾空白后的命令
    :return: 可以执行时为 True
    """
    if command.startswith(("pytest", "python -m pytest", "python -m unittest")):
        return True
    return command.startswith("python -c ") and "assert " in command


def tool(env, policy) -> ToolSpec:
    """
    :param env: 执行测试命令的环境。例如 LocalEnvironment(tmp_path)
    :param policy: 执行前要问的权限。例如 PermissionPolicy(lambda command: False)
    :return: 名为 run_tests 的 ToolSpec
    """
    return ToolSpec(
        name="run_tests",
        description="Run a test command in the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        handler=lambda arguments: run_tests(env, policy, arguments),
        permission="allow",
        read_only=False,
    )
