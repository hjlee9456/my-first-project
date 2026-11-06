"""출력 폴더 — 진단기가 무언가를 쓸 수 있는 유일한 곳.

규칙
- 출력 폴더는 새로 만들거나, 이 프로그램이 전에 만든 폴더(표지 파일이 있는 폴더)만 쓴다.
  다른 파일이 든 기존 폴더는 거부한다(남의 파일을 덮어쓰지 않기 위해).
- 출력 폴더 안의 '이름 하나짜리' 파일만 쓴다. 하위 경로·상위 경로(..)는 거부한다.
- 검사 대상 파일에는 손대지 않는다. 출력 폴더는 검사에서 자동으로 빠진다.

쓰기 함수 이름을 put_* 로 둔 까닭: tests/safety_rules.py 는 진단기 소스에서 write_text 같은
쓰기 이름을 모두 막는다. 진단기의 다른 모듈은 이 파일의 put_* 만 부를 수 있고, put_* 가
출력 폴더 밖에 쓰지 못하는지는 tests/test_output_guard.py 가 실제로 실행해 확인한다.
"""
from __future__ import annotations

import datetime as _dt
import io
import os
import sqlite3

from . import TOOL_NAME, __version__
from .winpath import is_within, normalize_root, to_fs

MARKER_NAME = ".filetidy-output"


class OutputDirError(Exception):
    pass


class OutputDir:
    def __init__(self, path: str, scan_roots: list[str] | None = None):
        self.path = normalize_root(path)
        for r in scan_roots or []:
            if is_within(r, self.path):
                raise OutputDirError(
                    f"출력 폴더가 검사 대상({r})과 같거나 그 위에 있습니다. "
                    "검사 대상 밖의 새 폴더를 지정하세요.")
        fs = to_fs(self.path)
        if os.path.lexists(fs):
            if not os.path.isdir(fs):
                raise OutputDirError(f"출력 경로가 폴더가 아닙니다: {self.path}")
            names = os.listdir(fs)
            if names and MARKER_NAME not in names:
                raise OutputDirError(
                    f"출력 폴더에 이 프로그램이 만들지 않은 파일이 있습니다: {self.path}\n"
                    "비어 있는 폴더나 새 폴더 이름을 지정하세요.")
        else:
            os.makedirs(fs)
        marker = to_fs(os.path.join(self.path, MARKER_NAME))
        if not os.path.exists(marker):
            stamp = _dt.datetime.now().isoformat(timespec="seconds")
            with open(marker, "w", encoding="utf-8") as f:
                f.write(f"{TOOL_NAME} {__version__} 출력 폴더 표지 — {stamp}\n"
                        "이 폴더는 진단 검사에서 자동으로 빠집니다.\n")

    def file_path(self, name: str) -> str:
        bad = (not name or name in (".", "..") or "/" in name or "\\" in name
               or ":" in name or name.startswith("."))
        if bad:
            raise OutputDirError(f"출력 파일 이름이 올바르지 않습니다: {name!r}")
        p = os.path.join(self.path, name)
        if not is_within(p, self.path):
            raise OutputDirError(f"출력 폴더 밖에 쓰려고 했습니다: {p}")
        return p

    def put_bytes(self, name: str, data: bytes) -> str:
        target = self.file_path(name)
        tmp = target + ".작성중"
        with open(to_fs(tmp), "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(to_fs(tmp), to_fs(target))  # 출력 폴더 안의 우리 파일끼리만
        return target

    def put_text(self, name: str, text: str) -> str:
        return self.put_bytes(name, text.encode("utf-8"))

    def put_xlsx(self, name: str, build) -> str:
        """build(workbook) 으로 엑셀을 메모리에서 만든 뒤 출력 폴더에 쓴다."""
        import xlsxwriter

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {
            "in_memory": True,
            "strings_to_formulas": False,  # '=' 로 시작하는 파일 이름이 수식이 되지 않게
            "strings_to_urls": False,
            "strings_to_numbers": False,
        })
        build(wb)
        wb.close()
        return self.put_bytes(name, buf.getvalue())

    def connect_db(self, name: str) -> sqlite3.Connection:
        con = sqlite3.connect(self.file_path(name))
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA foreign_keys=OFF")
        return con
