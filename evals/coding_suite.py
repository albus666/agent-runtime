import tempfile
from pathlib import Path

from agent_runtime.agent import DefaultAgent
from agent_runtime.environment import LocalEnvironment
from agent_runtime.permissions import PermissionPolicy
from evals.coding.task import COMMAND, EXPECTED, ORIGINAL
from evals.run_eval import ScriptedReplies
from fakes import ScriptedEnvironment

ALLOW = PermissionPolicy(lambda command: True)


def _names(result) -> list[str]:
    return [message["name"] for message in result.messages if message.get("role") == "tool"]


def _run(replies, env, prompt, policy=None):
    result = DefaultAgent(ScriptedReplies(replies), env, policy=policy).run(prompt)
    return result, _names(result)


def run_suite() -> list[dict]:
    """跑八道固定的 Coding 剧本。模型是剧本，不连真实接口。

    :return: 每题的名字、是否通过、步数和实际工具顺序
    """
    return [
        _read_return(),
        _grep_constant(),
        _modify_return(),
        _modify_and_test(),
        _replace_miss_then_read(),
        _path_outside_workspace(),
        _test_timeout_then_finish(),
        _test_failure_then_finish(),
    ]


def _read_return() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "hello.py").write_text(ORIGINAL, encoding="utf-8")
        result, names = _run([
            {"role": "assistant", "content": "先读", "tool_calls": [
                {"id": "c1", "name": "read_file", "arguments": {"path": "hello.py"}},
            ]},
            "返回 a + b",
        ], LocalEnvironment(root), "add 返回什么")
    return _outcome("读取返回值", result, names, ["read_file"], "返回 a + b" in result.final_text)


def _grep_constant() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "hello.py").write_text("VALUE = 42\n", encoding="utf-8")
        result, names = _run([
            {"role": "assistant", "content": "先搜", "tool_calls": [
                {"id": "c1", "name": "grep", "arguments": {"pattern": "VALUE"}},
            ]},
            "定义在 hello.py",
        ], LocalEnvironment(root), "VALUE 定义在哪")
    blob = "\n".join(message["content"] for message in result.messages)
    return _outcome("搜索常量", result, names, ["grep"], "hello.py:1:VALUE = 42" in blob)


def _modify_return() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "hello.py").write_text(ORIGINAL, encoding="utf-8")
        result, names = _run([
            {"role": "assistant", "content": "改返回值", "tool_calls": [
                {"id": "c1", "name": "str_replace", "arguments": {
                    "path": "hello.py",
                    "old_string": "return a + b",
                    "new_string": "return a + b + 1",
                }},
            ]},
            "改好了",
        ], LocalEnvironment(root), "把返回值加 1", ALLOW)
        changed = (root / "hello.py").read_text(encoding="utf-8") == EXPECTED
    return _outcome("修改函数", result, names, ["str_replace"], changed)


def _modify_and_test() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "hello.py").write_text(ORIGINAL, encoding="utf-8")
        result, names = _run([
            {"role": "assistant", "content": "改完再测", "tool_calls": [
                {"id": "c1", "name": "str_replace", "arguments": {
                    "path": "hello.py",
                    "old_string": "return a + b",
                    "new_string": "return a + b + 1",
                }},
                {"id": "c2", "name": "run_tests", "arguments": {"command": COMMAND}},
            ]},
            "测试通过",
        ], LocalEnvironment(root), "改完并跑测试", ALLOW)
        blob = "\n".join(message["content"] for message in result.messages)
        changed = (root / "hello.py").read_text(encoding="utf-8") == EXPECTED
    return _outcome("修改并测试", result, names, ["str_replace", "run_tests"], changed and "tests passed" in blob)


def _replace_miss_then_read() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "hello.py").write_text(ORIGINAL, encoding="utf-8")
        result, names = _run([
            {"role": "assistant", "content": "先改", "tool_calls": [
                {"id": "c1", "name": "str_replace", "arguments": {
                    "path": "hello.py",
                    "old_string": "return missing",
                    "new_string": "return a + b + 1",
                }},
            ]},
            {"role": "assistant", "content": "再读", "tool_calls": [
                {"id": "c2", "name": "read_file", "arguments": {"path": "hello.py"}},
            ]},
            "原文还在",
        ], LocalEnvironment(root), "替换失败后重新读取", ALLOW)
        same = (root / "hello.py").read_text(encoding="utf-8") == ORIGINAL
        blob = "\n".join(message["content"] for message in result.messages)
    return _outcome("替换失败后重读", result, names, ["str_replace", "read_file"], same and "not_found" in blob)


def _path_outside_workspace() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        workspace = root / "workspace"
        workspace.mkdir()
        secret = root / "secret.txt"
        secret.write_text("secret-42\n", encoding="utf-8")
        (workspace / "hello.py").write_text(ORIGINAL, encoding="utf-8")
        result, names = _run([
            {"role": "assistant", "content": "读外面", "tool_calls": [
                {"id": "c1", "name": "read_file", "arguments": {"path": "../secret.txt"}},
            ]},
            "拒绝了",
        ], LocalEnvironment(workspace), "读取工作区外的文件")
        blob = "\n".join(message["content"] for message in result.messages)
        safe = secret.read_text(encoding="utf-8") == "secret-42\n"
    return _outcome("拒绝越界路径", result, names, ["read_file"], safe and '"error": "denied"' in blob)


def _test_timeout_then_finish() -> dict:
    command = "python -m pytest"
    result, names = _run([
        {"role": "assistant", "content": "跑测试", "tool_calls": [
            {"id": "c1", "name": "run_tests", "arguments": {"command": command}},
        ]},
        "超时后结束",
    ], ScriptedEnvironment(timeouts=[command]), "跑测试")
    blob = "\n".join(message["content"] for message in result.messages)
    return _outcome("测试超时后继续", result, names, ["run_tests"], '"error": "timeout"' in blob)


def _test_failure_then_finish() -> dict:
    command = "python -m pytest"
    result, names = _run([
        {"role": "assistant", "content": "跑测试", "tool_calls": [
            {"id": "c1", "name": "run_tests", "arguments": {"command": command}},
        ]},
        "测试没过",
    ], ScriptedEnvironment(outputs={command: "FAILED test_add"}, returncodes={command: 1}), "跑测试")
    blob = "\n".join(message["content"] for message in result.messages)
    return _outcome("测试失败后继续", result, names, ["run_tests"], '"exit_code": 1' in blob and result.final_text == "测试没过")


def _outcome(name, result, names, expected_names, passed) -> dict:
    ok = result.status == "ok" and names == expected_names and passed
    return {
        "name": name,
        "ok": ok,
        "steps": result.steps,
        "status": result.status,
        "tools": names,
    }
