from pathlib import Path


def resolve_in_workspace(workspace, relative: str) -> tuple[Path, Path, str, bool]:
    """把相对路径解析到工作区内。绝对路径会丢掉 workspace，.. 和符号链接由 resolve 展开。

    :param workspace: 工作区目录。例如 LocalEnvironment(tmp_path).workspace
    :param relative: 相对路径。例如 "hello.py"；空字符串表示工作区本身
    :return: (root, path, target, inside)。inside 为假表示 path 已经越出 root。target 用来写进观察，没传路径时是 "."
    """
    target = relative or "."
    root = Path(workspace).resolve()
    path = (root / relative).resolve() if relative else root
    return root, path, target, path.is_relative_to(root)


def is_inside_workspace(root: Path, path: Path) -> bool:
    """展开 path 上的符号链接后，判断它是否仍在 root 内。

    :param root: 已经 resolve 过的工作区。例如 resolve_in_workspace 返回的 root
    :param path: 待检查的文件。例如 rglob 得到的一个路径
    :return: 仍在工作区内为 True
    """
    return path.resolve().is_relative_to(root)
