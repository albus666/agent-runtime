from ..observation import _observation
from .registry import ToolSpec


def list_companies(index: list[dict], arguments: dict) -> str:
    """
    :param index: 片段列表。例如 [{"id": "c1", "company": "星河", "summary": "入职日期", "text": "星河的入职日期是 3 月 1 日。"}]
    :param arguments: 无参数。例如 {}
    :return: 公司名，每行一个。例如 "星河\\n北辰"
    """
    del arguments
    names = []
    for chunk in index:
        company = str(chunk.get("company", ""))
        if company and company not in names:
            names.append(company)
    return "\n".join(names)


def search_docs(index: list[dict], arguments: dict) -> str:
    """
    :param index: 片段列表。例如 [{"id": "c1", "company": "星河", "summary": "入职日期", "text": "星河的入职日期是 3 月 1 日。"}]
    :param arguments: 例如 {"query": "入职"}
    :return: 编号和摘要。例如 "c1: 入职日期"。没有 query 时是 invalid_argument
    """
    query = str(arguments.get("query", "")).strip()
    if not query:
        return _observation("search_docs", "null", "缺少 query 参数", error="invalid_argument")
    needle = query.lower()
    lines = []
    for chunk in index:
        hay = f"{chunk.get('company', '')}\n{chunk.get('summary', '')}\n{chunk.get('text', '')}".lower()
        if needle in hay:
            lines.append(f"{chunk['id']}: {chunk.get('summary', '')}")
    return "\n".join(lines)


def read_chunk(index: list[dict], arguments: dict) -> str:
    """
    :param index: 片段列表。例如 [{"id": "c1", "text": "星河的入职日期是 3 月 1 日。"}]
    :param arguments: 例如 {"id": "c1"}
    :return: 片段正文。编号不存在时观察里是 not_found
    """
    chunk_id = str(arguments.get("id", ""))
    for chunk in index:
        if str(chunk.get("id")) == chunk_id:
            return str(chunk.get("text", ""))
    return _observation(chunk_id or "read_chunk", "null", "片段不存在", error="not_found")


def rag_tools(index: list[dict]) -> dict[str, ToolSpec]:
    """只登记检索工具。没有 shell、read_file、str_replace。

    :param index: 测试用的小索引
    :return: 以工具名为键的表，含 list_companies、search_docs、read_chunk
    """
    specs = [
        ToolSpec(
            name="list_companies",
            description="List companies in the index.",
            parameters={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            handler=lambda arguments: list_companies(index, arguments),
            permission="allow",
            read_only=True,
        ),
        ToolSpec(
            name="search_docs",
            description="Search chunks and return ids with summaries.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=lambda arguments: search_docs(index, arguments),
            permission="allow",
            read_only=True,
        ),
        ToolSpec(
            name="read_chunk",
            description="Read one chunk by id.",
            parameters={
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
            },
            handler=lambda arguments: read_chunk(index, arguments),
            permission="allow",
            read_only=True,
        ),
    ]
    return {spec.name: spec for spec in specs}
