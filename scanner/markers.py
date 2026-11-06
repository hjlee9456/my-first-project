"""복사본·임시파일 표지 (인계서 7장 1).

표지는 '판정'이 아니라 '단서'다. 예: '붙임(1).hwpx' 처럼 정상 문서도 (숫자) 표지가 붙을 수 있다.
"""
from __future__ import annotations

import re

# 윈도우 복사 시 이름 규칙: '문서 - 복사본.hwpx', '문서 - 복사본 (2).hwpx', 영문 '문서 - Copy.docx'
# 예전 윈도우: 'Copy of 문서.docx', 'Copy (2) of 문서.docx'
# 내려받기 중복: '문서 (1).pdf', '문서(1).pdf'
_COPY_NAME_RULES: list[tuple[str, re.Pattern]] = [
    (" - 복사본", re.compile(r" - 복사본( \(\d+\))?$")),
    (" - Copy", re.compile(r" - Copy( \(\d+\))?$", re.IGNORECASE)),
    ("Copy of", re.compile(r"^Copy (\(\d+\) )?of ", re.IGNORECASE)),
    ("(숫자)", re.compile(r"\s?\(\d{1,3}\)$")),
]

# 만든 날짜가 수정한 날짜보다 이만큼(나노초) 넘게 늦으면 '복사본 날짜 표지'
# (FAT 계열 2초 단위 시각 오차를 고려)
COPY_DATE_TOLERANCE_NS = 2_000_000_000


def split_ext(name: str) -> tuple[str, str]:
    """('보고서', '.hwpx'). 점으로 시작하는 이름('.hidden')은 확장자 없음으로 본다."""
    i = name.rfind(".")
    if i <= 0:
        return name, ""
    return name[:i], name[i:].lower()


def copy_name_marker(name: str) -> str | None:
    stem, _ = split_ext(name)
    for label, rx in _COPY_NAME_RULES:
        if rx.search(stem):
            return label
    return None


def is_temp(name: str) -> bool:
    _, ext = split_ext(name)
    return name.startswith("~$") or ext == ".tmp"


def is_copy_by_date(birth_ns: int | None, mtime_ns: int) -> bool:
    return birth_ns is not None and birth_ns > mtime_ns + COPY_DATE_TOLERANCE_NS
