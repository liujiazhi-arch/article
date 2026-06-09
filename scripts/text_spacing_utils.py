from __future__ import annotations

import re


CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
DIGIT_CHAR_RE = re.compile(r"\d")
NUM_CJK_EXCEPTIONS = sorted(
    [
        "组件",
        "批次",
        "年月日",
        "年",
        "月",
        "日",
        "时",
        "分",
        "秒",
        "度",
        "℃",
        "个",
        "只",
        "件",
        "台",
        "条",
        "块",
        "片",
        "张",
        "幅",
        "套",
        "段",
        "页",
        "%",
        "％",
    ],
    key=len,
    reverse=True,
)
NUM_CJK_LEFT_EXCEPTIONS = {"第", "图", "表", "式"}


def starts_with_num_cjk_exception(text: str, index: int) -> bool:
    if index < 0 or index >= len(text):
        return False
    return any(text.startswith(token, index) for token in NUM_CJK_EXCEPTIONS)


def needs_num_cjk_space(text: str, index: int, left_char: str, right_char: str) -> bool:
    if DIGIT_CHAR_RE.match(left_char) and CJK_CHAR_RE.match(right_char):
        return not starts_with_num_cjk_exception(text, index + 1)
    if CJK_CHAR_RE.match(left_char) and DIGIT_CHAR_RE.match(right_char):
        return left_char not in NUM_CJK_LEFT_EXCEPTIONS
    return False
