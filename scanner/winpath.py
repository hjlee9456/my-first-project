"""윈도우 긴 경로(260자 초과) 처리.

윈도우에서 파일 시스템을 부를 때는 경로 앞에 \\\\?\\ 를 붙여 260자 제한을 피한다.
\\\\?\\ 경로는 윈도우가 이름을 고치지 않으므로(끝 공백·마침표 등), 경로는
검사 시작점만 한 번 정리하고 나머지는 폴더 이름을 그대로 이어 붙여 만든다.
"""
from __future__ import annotations

import ntpath
import os

IS_WINDOWS = os.name == "nt"
LONG_PREFIX = "\\\\?\\"
UNC_LONG_PREFIX = "\\\\?\\UNC\\"


def to_fs(path: str, windows: bool = IS_WINDOWS) -> str:
    """파일 시스템 호출에 넘길 경로. 윈도우에서는 \\\\?\\ 접두사를 붙인다.

    path 는 이미 절대 경로이고 구분자가 역슬래시여야 한다.
    """
    if not windows:
        return path
    if path.startswith(LONG_PREFIX):
        return path
    if path.startswith("\\\\"):
        return UNC_LONG_PREFIX + path[2:]
    return LONG_PREFIX + path


def from_fs(path: str) -> str:
    """\\\\?\\ 접두사를 떼어 사람이 읽는 경로로 되돌린다."""
    if path.startswith(UNC_LONG_PREFIX):
        return "\\\\" + path[len(UNC_LONG_PREFIX):]
    if path.startswith(LONG_PREFIX):
        return path[len(LONG_PREFIX):]
    return path


def normalize_root(path: str, windows: bool = IS_WINDOWS) -> str:
    """사용자가 준 경로를 절대 경로로 정리한다. 'E:' 는 'E:\\' 로 본다."""
    p = path.strip().strip('"')
    if windows:
        if len(p) == 2 and p[1] == ":":
            p += "\\"
        p = from_fs(p)
        p = ntpath.abspath(p) if IS_WINDOWS else ntpath.normpath(p)
        return p
    return os.path.abspath(p)


def anchor_of(path: str, windows: bool = IS_WINDOWS) -> str:
    """드라이브 맨 위(C:\\, \\\\서버\\공유\\, /)."""
    if windows:
        drive, _ = ntpath.splitdrive(path)
        return drive + "\\"
    return "/"


def drive_letter(path: str, windows: bool = IS_WINDOWS) -> str | None:
    if not windows:
        return None
    drive, _ = ntpath.splitdrive(path)
    if len(drive) == 2 and drive[1] == ":":
        return drive[0].upper()
    return None


def rel_parts(path: str, anchor: str) -> list[str]:
    """anchor 아래 상대 경로 조각들."""
    rest = path[len(anchor):] if path.startswith(anchor) else path
    return [c for c in rest.replace("\\", "/").split("/") if c]


def is_within(child: str, parent: str) -> bool:
    """child 가 parent 와 같거나 그 아래인지 (대소문자 무시)."""
    c = os.path.normcase(child).rstrip("\\/")
    p = os.path.normcase(parent).rstrip("\\/")
    if c == p:
        return True
    sep = "\\" if IS_WINDOWS else "/"
    return c.startswith(p + sep) or (p.endswith(":") and c.startswith(p + sep))
