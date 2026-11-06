"""윈도우에서 합성 파일의 '만든 날짜'와 숨김 속성을 실제로 설정한다 (정답셋 생성 전용)."""
from __future__ import annotations

import os

IS_WINDOWS = os.name == "nt"
EPOCH_AS_FILETIME = 116444736000000000
FILE_ATTRIBUTE_HIDDEN = 0x2


def to_fs(path: str) -> str:
    if not IS_WINDOWS or path.startswith("\\\\?\\"):
        return path
    p = os.path.abspath(path) if not os.path.isabs(path) else path
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


def set_birthtime(path: str, birth_ns: int) -> None:  # pragma: no cover - 윈도우 전용
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.SetFileTime.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
    k32.SetFileTime.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    FILE_WRITE_ATTRIBUTES = 0x100
    share = 0x1 | 0x2 | 0x4
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    h = k32.CreateFileW(to_fs(path), FILE_WRITE_ATTRIBUTES, share, None, OPEN_EXISTING,
                        FILE_FLAG_BACKUP_SEMANTICS, None)
    if h in (None, wintypes.HANDLE(-1).value):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        v = birth_ns // 100 + EPOCH_AS_FILETIME
        ft = wintypes.FILETIME(v & 0xFFFFFFFF, v >> 32)
        if not k32.SetFileTime(h, ctypes.byref(ft), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        k32.CloseHandle(h)


def set_hidden(path: str) -> None:  # pragma: no cover - 윈도우 전용
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
    k32.GetFileAttributesW.restype = wintypes.DWORD
    k32.SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    k32.SetFileAttributesW.restype = wintypes.BOOL
    p = to_fs(path)
    a = k32.GetFileAttributesW(p)
    if a == 0xFFFFFFFF:
        raise ctypes.WinError(ctypes.get_last_error())
    if not k32.SetFileAttributesW(p, a | FILE_ATTRIBUTE_HIDDEN):
        raise ctypes.WinError(ctypes.get_last_error())
