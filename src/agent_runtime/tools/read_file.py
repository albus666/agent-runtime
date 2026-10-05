from ..observation import _observation
from ..paths import resolve_in_workspace
from .registry import ToolSpec


def read_file(env, arguments: dict) -> str:
    """
    :param env: 提供 workspace 的环境。例如 LocalEnvironment(tmp_path)
    :param arguments: 工具参数。例如 {"path": "hello.py"}
    :return: 文件正文。路径越出工作区时观察里是 denied，文件不存在时是 not_found
    """
    relative = str(arguments.get("path", ""))
    _root, path, target, inside = resolve_in_workspace(env.workspace, relative)
    if not inside:
        return _observation(target, "null", "超出工作区目录", error="denied")
    if not path.is_file():
        return _observation(target, "null", "文件不存在", error="not_found")
    return path.read_text(encoding="utf-8")


def tool(env) -> ToolSpec:
    """
    :param env: 读文件时使用的环境。例如 LocalEnvironment(tmp_path)
    :return: 名为 read_file、权限 allow 的 ToolSpec
    """
    return ToolSpec(
        name="read_file",
        description="Read one file inside the workspace.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=lambda arguments: read_file(env, arguments),
        permission="allow",
        read_only=True,
    )