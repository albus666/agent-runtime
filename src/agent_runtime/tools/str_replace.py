from ..observation import _observation
from ..paths import resolve_in_workspace
from .registry import ToolSpec


def str_replace(env, policy, arguments: dict) -> str:
    """把文件里恰好出现一次的原文换成新文本。

    :param env: 提供 workspace 的环境。例如 LocalEnvironment(tmp_path)
    :param policy: 写入前询问的权限。例如 PermissionPolicy(lambda command: True)
    :param arguments: 工具参数。例如 {"path": "hello.py", "old_string": "return a + b", "new_string": "return a + b + 1"}
    :return: 替换后的文件正文。路径越界或 ask_fn 拒绝时是 denied，原文找不到是 not_found，出现多次是 ambiguous
    """
    relative = str(arguments.get("path", ""))
    old = str(arguments.get("old_string", ""))
    new = str(arguments.get("new_string", ""))
    _root, path, target, inside = resolve_in_workspace(env.workspace, relative)
    if not inside:
        return _observation(target, "null", "超出工作区目录", error="denied")
    if not path.is_file():
        return _observation(target, "null", "文件不存在", error="not_found")
    if not old:
        return _observation(target, "null", "未给出要替换的原文", error="not_found")

    text = path.read_text(encoding="utf-8")
    found = text.count(old)
    if found == 0:
        return _observation(target, "null", "原文不存在", error="not_found")
    if found > 1:
        return _observation(target, "null", "原文出现多次", error="ambiguous")
    if not policy.ask_fn(f"str_replace {target}"):
        return _observation(target, "null", "未获允许，文件未修改", error="denied")

    updated = text.replace(old, new, 1)
    path.write_text(updated, encoding="utf-8")
    return updated


def tool(env, policy) -> ToolSpec:
    """
    :param env: 要修改的工作区。例如 LocalEnvironment(tmp_path)
    :param policy: 写入前询问的权限。例如 PermissionPolicy(lambda command: True)
    :return: 名为 str_replace、权限 ask 的 ToolSpec
    """
    return ToolSpec(
        name="str_replace",
        description="Replace one unique occurrence of text in a workspace file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
            },
            "required": ["path", "old_string", "new_string"],
            "additionalProperties": False,
        },
        handler=lambda arguments: str_replace(env, policy, arguments),
        permission="ask",
        read_only=False,
    )
