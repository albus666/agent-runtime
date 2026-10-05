from ..observation import _observation
from ..paths import is_inside_workspace, resolve_in_workspace
from .registry import ToolSpec


def _is_binary(path) -> bool:
    try:
        with path.open("rb") as handle:
            return b"\x00" in handle.read(8192)
    except OSError:
        return True


def grep(env, arguments: dict) -> str:
    """在工作区里查找一段文本，返回相对路径、行号和该行内容。

    :param env: 提供 workspace 的环境。例如 LocalEnvironment(tmp_path)
    :param arguments: 工具参数。例如 {"pattern": "VALUE", "path": "hello.py", "case_sensitive": False}。path 可省略，省略时搜索整个工作区
    :return: 例如 "hello.py:1:VALUE = 42"。路径越出工作区时观察里是 denied，路径不存在时是 not_found，缺少 pattern 时是 invalid_argument
    """
    pattern = str(arguments.get("pattern", ""))
    relative = str(arguments.get("path", ""))
    target = relative or "."
    case_sensitive = bool(arguments.get("case_sensitive", False))
    if not pattern:
        return _observation(target, "null", "缺少 pattern 参数", error="invalid_argument")

    root, start, target, inside = resolve_in_workspace(env.workspace, relative)
    if not inside:
        return _observation(target, "null", "超出工作区目录", error="denied")
    if not start.exists():
        return _observation(target, "null", "文件不存在", error="not_found")

    # 目录用 rglob；文件（含指向单个文件的链接）只查这一项。链接是否逃出工作区在循环里判断。
    files = start.rglob("*") if start.is_dir() else [start]
    needle = pattern if case_sensitive else pattern.lower()
    matches: list[str] = []
    denied = 0
    for path in files:
        if not path.is_file():
            continue
        # rglob 会跟随符号链接。展开后落到工作区外就记一笔，不静默丢掉。
        if not is_inside_workspace(root, path):
            denied += 1
            continue
        if _is_binary(path):
            continue
        rel = path.relative_to(root).as_posix()
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for lineno, line in enumerate(handle, 1):
                    hay = line if case_sensitive else line.lower()
                    if needle in hay:
                        matches.append(f"{rel}:{lineno}:{line.rstrip()}")
        except OSError:
            continue

    suffix = f"（跳过 {denied} 个越界文件）" if denied else ""
    if not matches:
        return _observation(target, "null", f"未匹配到 {pattern!r}{suffix}")
    if suffix:
        matches.append(suffix)
    return "\n".join(matches)


def tool(env) -> ToolSpec:
    """
    :param env: 搜索时使用的环境。例如 LocalEnvironment(tmp_path)
    :return: 名为 grep、权限 allow 的 ToolSpec
    """
    return ToolSpec(
        name="grep",
        description="Search for text inside the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
                "case_sensitive": {"type": "boolean"},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
        handler=lambda arguments: grep(env, arguments),
        permission="allow",
        read_only=True,
    )
