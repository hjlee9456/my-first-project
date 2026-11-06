"""시험 도우미 — 합성 정답셋을 진단하고 결과를 정답셋 기준 상대 경로로 바꾼다."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager

from scanner import platform_info
from scanner.scan import run_scan
from scanner.textsafe import dbtext


def rel_of(data_dir: str, path: str) -> str:
    prefix = dbtext(data_dir.rstrip("\\/")) + os.sep
    assert path.startswith(prefix), (path, prefix)
    return path[len(prefix):].replace(os.sep, "/")


def answer_rel(p: str) -> str:
    """정답의 경로를 진단기 DB 글자 꼴로 (cp949 이름 등)."""
    return dbtext(p)


@contextmanager
def mocked_birthtimes(info: dict):
    """리눅스에는 '만든 날짜'가 없으므로 정답셋의 모의 값을 넣는다. 윈도우에서는 실제 값을 쓴다."""
    if os.name == "nt":
        yield
        return
    with open(info["mock_path"], encoding="utf-8") as f:
        mock = json.load(f)["birth_ns"]
    data = info["data"]
    table = {os.path.join(data, *rel.split("/")): ns for rel, ns in mock.items()}
    original = platform_info.birthtime_ns

    def fake(path, st):
        return table.get(path)

    platform_info.birthtime_ns = fake
    try:
        yield
    finally:
        platform_info.birthtime_ns = original


def scan_dataset(info: dict, out_dir: str, **kw):
    sims = [(k, v) for k, v in sorted(info["roots"].items())]
    with mocked_birthtimes(info):
        return run_scan([], out_dir, simulated=sims, progress=lambda *_: None, **kw)


def results(info: dict, db_path: str, run_id: int | None = None) -> dict:
    con = sqlite3.connect(db_path)
    if run_id is None:
        run_id = con.execute("SELECT MAX(run_id) FROM runs WHERE status='완료'").fetchone()[0]
    data = info["data"]
    rel = lambda p: rel_of(data, p)  # noqa: E731
    files = {rel(p): dict(size=s, ro=ro, hid=h, temp=t, cn=cn, cd=cd)
             for p, s, ro, h, t, cn, cd in con.execute(
                 "SELECT path, size, readonly, hidden, is_temp, copy_name, copy_by_date FROM files WHERE seen_run=?",
                 (run_id,))}
    dup = {}
    for no, p in con.execute("""SELECT m.group_no, f.path FROM dup_members m JOIN files f ON f.file_id=m.file_id
                                WHERE m.run_id=?""", (run_id,)):
        dup.setdefault(no, []).append(rel(p))
    groups = {}
    for no, level, p, ac, role in con.execute(
            """SELECT g.group_no, g.level, d.path, m.a_class, m.role FROM folder_groups g
               JOIN folder_members m ON m.run_id=g.run_id AND m.group_no=g.group_no
               JOIN dirs d ON d.dir_id=m.dir_id WHERE g.run_id=?""", (run_id,)):
        groups.setdefault(no, {"level": level, "members": []})["members"].append(
            {"path": rel(p), "role": role, "a_class": ac})
    contains = [{"inner": rel(a), "outer": rel(b)} for a, b in con.execute(
        """SELECT di.path, dx.path FROM folder_contains c JOIN dirs di ON di.dir_id=c.inner_dir_id
           JOIN dirs dx ON dx.dir_id=c.outer_dir_id WHERE c.run_id=?""", (run_id,))]
    errors = con.execute("SELECT stage, kind, path FROM errors WHERE run_id=?", (run_id,)).fetchall()
    skipped = con.execute("SELECT reason, kind, path FROM skipped WHERE run_id=?", (run_id,)).fetchall()
    con.close()
    return {"run_id": run_id, "files": files, "dup": list(dup.values()), "groups": list(groups.values()),
            "contains": contains, "errors": errors, "skipped": skipped}


def group_signature(g: dict):
    """묶음 비교용 — 구조 번호는 '같은 것끼리 같은 번호'라는 분할만 비교한다."""
    by_class: dict[int, set] = {}
    for m in g["members"]:
        by_class.setdefault(m["a_class"], set()).add(m["path"])
    return (g["level"], frozenset((m["path"], m["role"]) for m in g["members"]),
            frozenset(frozenset(v) for v in by_class.values()))


def snapshot(root: str) -> dict:
    """폴더 아래 모든 파일·폴더의 경로·크기·수정 시각·속성·내용 해시."""
    import hashlib
    import stat as st_mod

    from scanner.winpath import to_fs
    out = {}
    stack = [root]
    while stack:
        d = stack.pop()
        with os.scandir(to_fs(d)) as it:
            for e in it:
                full = os.path.join(d, e.name)
                st = e.stat(follow_symlinks=False)
                rel = os.path.relpath(full, root)
                if e.is_symlink() or (os.name == "nt" and getattr(st, "st_reparse_tag", 0)):
                    target = os.readlink(to_fs(full)) if e.is_symlink() else "reparse"
                    if os.path.isabs(target):
                        target = os.path.relpath(target, root)
                    out[rel] = ("link", target)
                elif st_mod.S_ISDIR(st.st_mode):
                    out[rel] = ("dir",)
                    stack.append(full)
                else:
                    h = hashlib.sha256()
                    with open(to_fs(full), "rb") as f:
                        h.update(f.read())
                    out[rel] = ("file", st.st_size, st.st_mtime_ns, st.st_mode,
                                getattr(st, "st_file_attributes", 0), h.hexdigest())
    return out
