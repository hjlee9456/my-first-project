"""운영체제별 정보 읽기 — 볼륨 일련번호, 만든 날짜, 파일 속성, 남은 공간.

모두 '읽기'만 한다. 윈도우 API 중 읽기 함수(GetVolumePathNameW,
GetVolumeInformationW)만 부른다.
"""
from __future__ import annotations

import os
import stat as _stat
from dataclasses import dataclass
from shutil import disk_usage

IS_WINDOWS = os.name == "nt"

FILE_ATTRIBUTE_READONLY = 0x1
FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_ENCRYPTED = 0x4000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
# 재분석 지점 중 '다른 곳을 가리키는 것'(바로 가기 폴더·심볼릭 링크·탑재 지점) 표시 비트
REPARSE_TAG_NAME_SURROGATE = 0x20000000


@dataclass
class VolumeInfo:
    serial: str
    label: str | None
    fs_type: str | None
    mount_root: str | None


def volume_info(path: str) -> VolumeInfo:
    if IS_WINDOWS:
        return _volume_info_windows(path)
    st = os.stat(path)
    return VolumeInfo(serial=f"dev-{st.st_dev:x}", label=None, fs_type=None, mount_root=None)


def _volume_info_windows(path: str) -> VolumeInfo:  # pragma: no cover - 윈도우 전용
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetVolumePathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    k32.GetVolumePathNameW.restype = wintypes.BOOL
    k32.GetVolumeInformationW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD]
    k32.GetVolumeInformationW.restype = wintypes.BOOL

    buf = ctypes.create_unicode_buffer(1024)
    if not k32.GetVolumePathNameW(path, buf, 1024):
        raise ctypes.WinError(ctypes.get_last_error())
    root = buf.value
    name = ctypes.create_unicode_buffer(261)
    fsname = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    maxlen = wintypes.DWORD()
    flags = wintypes.DWORD()
    ok = k32.GetVolumeInformationW(root, name, 261, ctypes.byref(serial), ctypes.byref(maxlen),
                                   ctypes.byref(flags), fsname, 261)
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    s = serial.value
    return VolumeInfo(serial=f"{s >> 16:04X}-{s & 0xFFFF:04X}", label=name.value or None,
                      fs_type=fsname.value or None, mount_root=root)


def space(path: str) -> tuple[int, int] | None:
    """(전체, 남은) 바이트. 알 수 없으면 None."""
    try:
        u = disk_usage(path)
        return u.total, u.free
    except OSError:
        return None


def birthtime_ns(path: str, st: os.stat_result) -> int | None:
    """만든 날짜(나노초). 리눅스처럼 알 수 없으면 None.

    시험에서는 이 함수를 바꿔 끼워 '만든 날짜'를 모의한다(리눅스에는 만든 날짜가 없음).
    """
    v = getattr(st, "st_birthtime_ns", None)
    if v is not None:
        return int(v)
    v = getattr(st, "st_birthtime", None)
    if v is not None:
        return int(v * 1_000_000_000)
    if IS_WINDOWS:  # 파이썬 3.11 이하 윈도우에서는 st_ctime 이 만든 날짜
        return int(st.st_ctime_ns)
    return None


@dataclass
class Flags:
    attrs: int
    readonly: bool
    hidden: bool
    is_system: bool
    is_link: bool       # 다른 곳을 가리키는 재분석 지점·심볼릭 링크 → 따라가지 않음
    placeholder: bool   # 클라우드 자리표시자 등 내용이 이 PC에 없는 파일 → 읽지 않음


def flags(st: os.stat_result, name: str) -> Flags:
    if IS_WINDOWS:
        a = getattr(st, "st_file_attributes", 0)
        tag = getattr(st, "st_reparse_tag", 0)
        is_link = bool(a & FILE_ATTRIBUTE_REPARSE_POINT) and bool(tag & REPARSE_TAG_NAME_SURROGATE)
        if _stat.S_ISLNK(st.st_mode):
            is_link = True
        placeholder = bool(a & (FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_OPEN
                                | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS))
        return Flags(attrs=a, readonly=bool(a & FILE_ATTRIBUTE_READONLY),
                     hidden=bool(a & FILE_ATTRIBUTE_HIDDEN), is_system=bool(a & FILE_ATTRIBUTE_SYSTEM),
                     is_link=is_link, placeholder=placeholder)
    return Flags(attrs=st.st_mode, readonly=not (st.st_mode & 0o222), hidden=name.startswith("."),
                 is_system=False, is_link=_stat.S_ISLNK(st.st_mode), placeholder=False)
