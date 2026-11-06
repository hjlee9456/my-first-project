"""금지 규칙 시험 (인계서 5장 규칙 3·4).

1) 검사기 자체가 제대로 잡는지 — 일부러 나쁜 코드 조각을 넣어 본다.
2) 실제 소스가 규칙을 지키는지.
"""
import pytest

import safety_rules as sr

# ── 1) 검사기 자기 시험 ──────────────────────────────────────────
DELETE_SAMPLES = [
    "import os\nos.remove('a')",
    "import os\nos.unlink('a')",
    "import shutil\nshutil.rmtree('a')",
    "from pathlib import Path\nPath('a').unlink()",
    "from os import remove as r\nr('a')",
    "import os\ngetattr(os, 'remove')('a')",
    "import send2trash\nsend2trash.send2trash('a')",
    "from send2trash import send2trash",
    "import subprocess\nsubprocess.run(['del', '/q', 'a'])",
    "import subprocess\nsubprocess.run('rmdir /s /q a', shell=True)",
    "import ctypes\nctypes.windll.kernel32.DeleteFileW('a')",
    "x = [1]\nx.remove(1)",  # 무해해도 막는다(규칙 단순화)
    "exec('os.remove(1)')",
]

WRITE_SAMPLES = [
    "open('a', 'w')",
    "open('a', 'ab')",
    "open('a', mode='r+')",
    "open('a', mode=m)",
    "from pathlib import Path\nPath('a').write_text('x')",
    "from pathlib import Path\nPath('a').rename('b')",
    "from pathlib import Path\nPath('a').replace('b')",
    "import os\nos.replace('a', 'b')",
    "import os\nos.rename('a', 'b')",
    "import os\nos.utime('a', None)",
    "import os\nos.chmod('a', 0o444)",
    "import os\nos.open('a', 1)",
    "import os\nos.makedirs('a')",
    "import shutil\nshutil.copy2('a', 'b')",
    "from shutil import move",
    "import subprocess",
    "import sqlite3\nsqlite3.connect('x.db')",
    "import xlsxwriter\nxlsxwriter.Workbook('x.xlsx')",
    "import zipfile\nzipfile.ZipFile('a.zip', 'w')",
    "import zipfile\nzipfile.ZipFile('a.zip', m)",
    "from pathlib import Path\nPath('a').open('wb')",
    "import ctypes\nctypes.windll.kernel32.SetFileTime(1, 2, 3, 4)",
    "import ctypes\nctypes.windll.kernel32.MoveFileExW('a', 'b', 0)",
    "import os\nos.system('copy a b')",
    "eval('1')",
    "import importlib",
    "import os\ngetattr(os, 'rename')",
]

READ_ONLY_OK = [
    "with open('a', 'rb') as f:\n    f.read()",
    "open('a')",
    "open('a', 'r')",
    "s = 'a-b'.replace('-', '/')",
    "import re\nre.compile('x')",
    "from shutil import disk_usage\ndisk_usage('/')",
    "import os\nos.scandir('.')\nos.stat('a')",
    "import zipfile\nzipfile.ZipFile('a.zip').open('Contents/section0.xml')",
    "import zipfile\nzipfile.ZipFile('a.zip', 'r')",
    "d = {}\nd.get('k', 'x')",
]


@pytest.mark.parametrize("code", DELETE_SAMPLES)
def test_checker_catches_delete(code):
    assert sr.check_delete(code, "<표본>"), f"삭제 코드를 놓쳤다: {code!r}"


@pytest.mark.parametrize("code", WRITE_SAMPLES)
def test_checker_catches_write(code):
    assert sr.check_write(code, "<표본>"), f"쓰기 코드를 놓쳤다: {code!r}"


@pytest.mark.parametrize("code", READ_ONLY_OK)
def test_checker_allows_read_only(code):
    v = sr.check_write(code, "<표본>") + sr.check_delete(code, "<표본>")
    assert not v, f"읽기 전용 코드를 잘못 막았다: {code!r} → {v}"


# ── 2) 실제 소스 검사 ────────────────────────────────────────────
def test_sources_exist():
    files = sr.python_files(["scanner"], include_top=False)
    names = {p.name for p in files}
    assert "output.py" in names and "inventory.py" in names, "검사할 진단기 소스가 없다"


def test_no_delete_anywhere():
    files = sr.python_files(["scanner", "executor", "testkit"])
    v = sr.scan_delete(files)
    assert not v, "삭제 기능 발견:\n" + "\n".join(map(str, v))


def test_scanner_is_read_only():
    files = sr.python_files(["scanner"], include_top=False)
    v = sr.scan_write(files)
    assert not v, "진단기에 쓰기·이동 코드 발견:\n" + "\n".join(map(str, v))


def test_write_exception_is_only_output_module():
    assert sr.WRITE_ALLOWED_FILES == {"scanner/output.py"}


def test_scanner_does_not_import_executor_or_testkit():
    import ast
    for p in sr.python_files(["scanner"], include_top=False):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods = [n.module]
            for m in mods:
                assert not m.startswith(("executor", "testkit")), f"{p.name}: {m}"
