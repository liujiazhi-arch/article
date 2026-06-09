from __future__ import annotations

import re
from collections.abc import Iterable


CITATION_TOKEN_PATTERN = r"\[\d{1,3}(?:[,，、\-]\d{1,3})*\]"
CITATION_TOKEN_RE = re.compile(CITATION_TOKEN_PATTERN)
CITATION_TOKEN_SPLIT_RE = re.compile(f"({CITATION_TOKEN_PATTERN})")
CITATION_NUMBER_GROUP_RE = re.compile(r"\[(\d+(?:[-,，、]\d+)*)\]")


def is_citation_token(text: str | None) -> bool:
    return bool(CITATION_TOKEN_RE.fullmatch(text or ""))


def contains_citation_token(text: str | None) -> bool:
    return bool(CITATION_TOKEN_RE.search(text or ""))


def citation_numbers_from_token(text: str | None) -> list[int]:
    match = re.fullmatch(r"\[(.+)\]", text or "")
    if match is None:
        return []

    numbers: list[int] = []
    for part in re.split(r"[,，、]", match.group(1)):
        part = part.strip()
        if not part:
            continue
        range_match = re.fullmatch(r"(\d{1,3})-(\d{1,3})", part)
        if range_match is not None:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            step = 1 if start <= end else -1
            numbers.extend(range(start, end + step, step))
            continue
        if re.fullmatch(r"\d{1,3}", part):
            numbers.append(int(part))
    return numbers


def citation_numbers_from_group(raw: str | None) -> list[int]:
    normalized = str(raw or "").replace("，", ",").replace("、", ",")
    numbers: list[int] = []
    for part in normalized.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            try:
                start = int(start_text)
                end = int(end_text)
            except ValueError:
                continue
            if start <= end:
                numbers.extend(range(start, end + 1))
            else:
                numbers.extend(range(end, start + 1))
            continue
        try:
            numbers.append(int(part))
        except ValueError:
            continue
    return numbers


def format_citation_numbers(numbers: Iterable[int]) -> str:
    unique_numbers = sorted(set(numbers))
    parts: list[str] = []
    index = 0
    while index < len(unique_numbers):
        start = unique_numbers[index]
        end = start
        while index + 1 < len(unique_numbers) and unique_numbers[index + 1] == end + 1:
            index += 1
            end = unique_numbers[index]
        if end - start >= 2:
            parts.append(f"{start}-{end}")
        elif end == start:
            parts.append(str(start))
        else:
            parts.extend([str(start), str(end)])
        index += 1
    return f"[{','.join(parts)}]"
