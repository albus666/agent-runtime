NAME = "查出入职日期"
PROMPT = "星河哪一天入职？"
QUOTE = "星河的入职日期是 3 月 1 日。"
ABSENT = "年薪一百万"
INDEX = [
    {
        "id": "c1",
        "company": "星河",
        "summary": "入职日期",
        "text": QUOTE,
    },
    {
        "id": "c2",
        "company": "北辰",
        "summary": "办公地点",
        "text": "北辰的办公室在上海。",
    },
]
REPLIES = [
    {
        "role": "assistant",
        "content": "先搜索",
        "tool_calls": [
            {"id": "c1", "name": "search_docs", "arguments": {"query": "入职"}},
        ],
    },
    {
        "role": "assistant",
        "content": "再读原文",
        "tool_calls": [
            {"id": "c2", "name": "read_chunk", "arguments": {"id": "c1"}},
        ],
    },
    QUOTE,
]


def passed(result) -> bool:
    """
    :param result: DefaultAgent.run 的返回值。例如 RunResult(status="ok", final_text="星河的入职日期是 3 月 1 日。", steps=3, messages=[])
    """
    return (
        result.status == "ok"
        and QUOTE in result.final_text
        and ABSENT not in result.final_text
    )
