"""파일 이름 글자 문제(cp949·깨진 유니코드) 처리.

윈도우 NTFS 이름에는 짝 없는 서로게이트(깨진 UTF-16)가, 리눅스에는 UTF-8이 아닌
바이트(예: cp949로 만든 이름)가 있을 수 있다. 이런 이름은 그대로 DB(UTF-8)에
넣을 수 없으므로 사람이 읽는 글자는 \\xNN 꼴로 바꿔 넣고, 원래 바이트는 따로 둔다.
"""
from __future__ import annotations

import os

IS_WINDOWS = os.name == "nt"
_ERRORS = "surrogatepass" if IS_WINDOWS else "surrogateescape"


def has_name_issue(s: str) -> bool:
    try:
        s.encode("utf-8")
        return False
    except UnicodeEncodeError:
        return True


def dbtext(s: str) -> str:
    """DB·보고서에 넣을 수 있는 글자. 문제가 없으면 그대로 돌려준다."""
    try:
        s.encode("utf-8")
        return s
    except UnicodeEncodeError:
        return s.encode("utf-8", _ERRORS).decode("utf-8", "backslashreplace")


def to_raw(s: str) -> bytes:
    """경로를 정확히 되살릴 수 있는 바이트."""
    if IS_WINDOWS:
        return s.encode("utf-16-le", "surrogatepass")
    return os.fsencode(s)


def from_raw(b: bytes) -> str:
    if IS_WINDOWS:
        return b.decode("utf-16-le", "surrogatepass")
    return os.fsdecode(b)
