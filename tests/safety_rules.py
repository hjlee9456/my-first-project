"""금지 규칙 검사기 (인계서 5장 규칙 3·4).

소스 코드를 실행하지 않고 '읽어서' 검사한다. 파이썬 문법 나무(AST)를 훑고,
보조로 글자 그대로도 훑는다.

규칙 A — 삭제 금지 (scanner·executor·testkit·맨 위 .py 전부)
    삭제를 뜻하는 이름(os.remove, unlink, rmtree, send2trash, DeleteFileW …)이
    어디에든 나오면 실패. list.remove 같은 무해한 쓰임도 막는다 — 오탐을 줄이는
    것보다 규칙을 단순하게 지키는 쪽을 택했다.

규칙 B — 진단기 쓰기 금지 (scanner, 단 scanner/output.py 한 파일만 예외)
    이동·이름 변경·복사·속성/날짜 변경·쓰기 모드 열기·외부 명령 실행·
    DB/엑셀 파일 직접 만들기를 막는다. 보고서·DB 출력은 output.py가 맡고,
    output.py는 출력 폴더 안에만 쓰도록 실행 시험(test_output_guard)으로 따로 검사한다.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 규칙 A: 삭제 ──────────────────────────────────────────────
DELETE_NAMES = {
    "remove", "unlink", "rmtree", "rmdir", "removedirs",
    "send2trash", "move_to_trash",
    "DeleteFile", "DeleteFileW", "DeleteFileA",
    "RemoveDirectory", "RemoveDirectoryW", "RemoveDirectoryA",
    "SHFileOperation", "SHFileOperationW", "SHFileOperationA",
    "IFileOperation", "DeleteItem", "DeleteItems",
}
DELETE_MODULES = {"send2trash"}
# 문자열 속 셸 삭제 명령 (subprocess 로 del/rd/rm 을 부르는 우회 차단)
SHELL_DELETE_RE = re.compile(
    r"(?i)^\s*(del|erase|rd|rmdir|rm|remove-item|ri|deltree)(\s|$)")
# 글자 그대로 훑기 (AST가 놓치는 exec 문자열 등 대비)
DELETE_TEXT_RE = re.compile(
    r"\b(os|shutil|pathlib|Path|path|p)\s*\.\s*"
    r"(remove|unlink|rmtree|rmdir|removedirs)\b|send2trash")

# ── 규칙 B: 진단기 쓰기 ────────────────────────────────────────
WRITE_NAMES = {
    # 이동·이름 변경·복사
    "rename", "renames", "move", "copy", "copy2", "copyfile", "copytree",
    "copymode", "copystat", "copyfileobj",
    # 쓰기·만들기
    "write_text", "write_bytes", "touch", "mkdir", "makedirs", "mkfifo",
    "mknod", "symlink", "symlink_to", "hardlink_to", "link", "link_to",
    "truncate", "ftruncate", "fdopen",
    # 속성·날짜·권한
    "chmod", "lchmod", "fchmod", "chown", "lchown", "fchown", "utime",
    "setxattr", "removexattr", "chflags", "lchflags",
    # 외부 명령
    "system", "popen", "startfile", "spawnl", "spawnv", "spawnve", "execv",
    "execve", "execl", "posix_spawn",
    # 윈도우 API 직접 호출
    "MoveFile", "MoveFileW", "MoveFileExW", "MoveFileWithProgressW",
    "CopyFile", "CopyFileW", "CopyFileExW", "CopyFile2", "ReplaceFile",
    "ReplaceFileW", "SetFileTime", "SetFileAttributes", "SetFileAttributesW",
    "SetFileInformationByHandle", "WriteFile", "WriteFileEx", "CreateFile",
    "CreateFileW", "CreateFileA", "SetEndOfFile", "CreateHardLinkW",
    "CreateSymbolicLinkW", "DeviceIoControl", "SetFileShortNameW",
    # 파일을 직접 만드는 라이브러리 호출 (output.py 를 거쳐야 함)
    "Workbook", "connect", "save", "savefig", "to_excel", "to_csv",
    # 우회 수단
    "import_module",
}
# 맨이름(내장 함수)으로 부를 때만 막는 것 — re.compile 같은 속성 호출은 괜찮다
BUILTIN_BANNED = {"exec", "eval", "compile", "__import__", "breakpoint"}
WRITE_MODULES = {"subprocess", "importlib", "tempfile", "pywintypes", "win32file",
                 "win32api", "win32con", "pythoncom", "multiprocessing"}
# shutil 은 disk_usage(남은 공간 읽기) 하나만 허용
SHUTIL_ALLOWED = {"disk_usage"}
MODE_RE = re.compile(r"^[rwxabtU+]{1,4}$")
WRITE_MODE_CHARS = set("wxa+")

WRITE_ALLOWED_FILES = {"scanner/output.py"}


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line} [{self.rule}] {self.detail}"


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _names_in(node: ast.AST):
    """노드 안의 모든 이름(변수·속성·import 별칭)을 (이름, 줄) 로 낸다."""
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            yield n.id, n.lineno
        elif isinstance(n, ast.Attribute):
            yield n.attr, n.lineno
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                yield a.name.split(".")[-1], n.lineno
                if a.asname:
                    yield a.asname, n.lineno
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield n.name, n.lineno
        elif isinstance(n, ast.keyword) and n.arg:
            yield n.arg, getattr(n, "lineno", 0) or 0


def _string_constants(node: ast.AST):
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            yield n.value, n.lineno


def check_delete(source: str, filename: str) -> list[Violation]:
    out: list[Violation] = []
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:  # 읽을 수 없는 소스는 통과시키지 않는다
        return [Violation(filename, e.lineno or 0, "구문오류", str(e))]
    for name, line in _names_in(tree):
        if name in DELETE_NAMES:
            out.append(Violation(filename, line, "삭제금지", f"이름 '{name}'"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] in DELETE_MODULES:
                    out.append(Violation(filename, n.lineno, "삭제금지", f"import {a.name}"))
        elif isinstance(n, ast.ImportFrom) and n.module:
            if n.module.split(".")[0] in DELETE_MODULES:
                out.append(Violation(filename, n.lineno, "삭제금지", f"from {n.module}"))
    for text, line in _string_constants(tree):
        if text in DELETE_NAMES:
            out.append(Violation(filename, line, "삭제금지", f"문자열 '{text}' (getattr 우회 의심)"))
        if SHELL_DELETE_RE.match(text):
            out.append(Violation(filename, line, "삭제금지", f"셸 삭제 명령 '{text[:40]}'"))
    for i, raw in enumerate(source.splitlines(), 1):
        if DELETE_TEXT_RE.search(raw):
            out.append(Violation(filename, i, "삭제금지", f"글자 검사: {raw.strip()[:60]}"))
    return out


# 두 번째 인자가 '열기 모드'인 함수들 (open, ZipFile, gzip.open, tarfile.open …)
OPENERS = {"open", "ZipFile", "TarFile", "GzipFile", "BZ2File", "LZMAFile",
           "NamedTemporaryFile", "TemporaryFile", "SpooledTemporaryFile"}


def _mode_args(call: ast.Call):
    f = call.func
    fname = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
    positions = []
    if fname in OPENERS:
        positions.append(1)
    if isinstance(f, ast.Attribute) and fname == "open":
        positions.append(0)  # Path('a').open('w')
    for i in positions:
        if i < len(call.args):
            a = call.args[i]
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                if MODE_RE.match(a.value):
                    yield a.value
            elif i == 1:
                yield "?"  # 글자로 못 박지 않은 모드는 쓰기로 본다
    for k in call.keywords:
        if k.arg == "mode":
            if isinstance(k.value, ast.Constant) and isinstance(k.value.value, str):
                yield k.value.value
            else:
                yield "?"  # 글자로 못 박지 않은 모드는 쓰기로 본다


def check_write(source: str, filename: str) -> list[Violation]:
    out: list[Violation] = []
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        return [Violation(filename, e.lineno or 0, "구문오류", str(e))]
    for name, line in _names_in(tree):
        if name in WRITE_NAMES:
            out.append(Violation(filename, line, "쓰기금지", f"이름 '{name}'"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id in BUILTIN_BANNED:
            out.append(Violation(filename, n.lineno, "쓰기금지", f"내장 함수 '{n.id}'"))
    for text, line in _string_constants(tree):
        if text in WRITE_NAMES or text in BUILTIN_BANNED:
            out.append(Violation(filename, line, "쓰기금지", f"문자열 '{text}' (getattr 우회 의심)"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                top = a.name.split(".")[0]
                if top in WRITE_MODULES or top == "shutil":
                    out.append(Violation(filename, n.lineno, "쓰기금지", f"import {a.name}"))
        elif isinstance(n, ast.ImportFrom) and n.module:
            top = n.module.split(".")[0]
            if top in WRITE_MODULES:
                out.append(Violation(filename, n.lineno, "쓰기금지", f"from {n.module}"))
            if top == "shutil":
                bad = [a.name for a in n.names if a.name not in SHUTIL_ALLOWED]
                if bad:
                    out.append(Violation(filename, n.lineno, "쓰기금지", f"from shutil import {bad}"))
        elif isinstance(n, ast.Call):
            f = n.func
            fname = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            # 모드 글자가 쓰기(w/x/a/+)면 무슨 함수든 막는다 (open, Path.open, ZipFile …)
            for m in _mode_args(n):
                if m == "?" or (set(m) & WRITE_MODE_CHARS):
                    out.append(Violation(filename, n.lineno, "쓰기금지", f"{fname}(…, '{m}')"))
            # os.open / io.open / codecs.open 은 모드와 무관하게 금지
            if isinstance(f, ast.Attribute) and f.attr == "open" and isinstance(f.value, ast.Name) \
                    and f.value.id in {"os", "io", "codecs", "nt", "posix"}:
                out.append(Violation(filename, n.lineno, "쓰기금지", f"{f.value.id}.open"))
            # Path.replace(target) 는 이동이다. str.replace(a, b) 는 인자가 둘 이상이라 구별된다.
            if isinstance(f, ast.Attribute) and f.attr == "replace" and len(n.args) + len(n.keywords) == 1:
                out.append(Violation(filename, n.lineno, "쓰기금지", ".replace(인자 1개) — 파일 이동 의심"))
            if isinstance(f, ast.Attribute) and f.attr == "replace" and isinstance(f.value, ast.Name) \
                    and f.value.id in {"os", "nt", "posix"}:
                out.append(Violation(filename, n.lineno, "쓰기금지", "os.replace"))
            if isinstance(f, ast.Attribute) and f.attr in {"write", "writelines"} and isinstance(f.value, ast.Name) \
                    and f.value.id in {"os", "nt", "posix"}:
                out.append(Violation(filename, n.lineno, "쓰기금지", f"os.{f.attr}"))
    return out


def python_files(subdirs: list[str], include_top: bool = True) -> list[Path]:
    files: list[Path] = []
    for d in subdirs:
        files.extend(sorted((ROOT / d).rglob("*.py")))
    if include_top:
        files.extend(sorted(ROOT.glob("*.py")))
    return files


def scan_delete(files: list[Path]) -> list[Violation]:
    out: list[Violation] = []
    for p in files:
        out.extend(check_delete(p.read_text(encoding="utf-8"), _rel(p)))
    return out


def scan_write(files: list[Path]) -> list[Violation]:
    out: list[Violation] = []
    for p in files:
        rel = _rel(p)
        if rel in WRITE_ALLOWED_FILES:
            continue
        out.extend(check_write(p.read_text(encoding="utf-8"), rel))
    return out
