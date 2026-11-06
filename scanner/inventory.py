"""1. 목록 만들기 — 폴더를 훑어 파일마다 크기·날짜·속성·표지를 DB에 적는다.

- 접근 거부·경로 오류는 오류 표에 적고 계속한다(멈추지 않는다).
- 바로가기 폴더(정션)·심볼릭 링크는 따라가지 않는다(무한 고리 방지).
- 출력 폴더, 표지 파일(.filetidy-output)이 든 폴더, 제외 목록은 건너뛴다.
"""
from __future__ import annotations

import os
import stat as _stat
import time
from dataclasses import dataclass, field

from . import platform_info as pinfo
from .db import Database, classify_os_error
from .exclusions import Exclusions
from .markers import copy_name_marker, is_copy_by_date, is_temp, split_ext
from .output import MARKER_NAME
from .textsafe import dbtext, has_name_issue, to_raw
from .winpath import anchor_of, drive_letter, is_within, normalize_root, rel_parts, to_fs


@dataclass
class Root:
    path: str
    anchor: str
    letter: str | None
    simulated: bool = False


def prepare_roots(paths: list[str], simulated: list[tuple[str, str]] | None = None,
                  warn=print) -> list[Root]:
    """검사 시작점 정리. 다른 시작점 안에 든 시작점은 뺀다(같은 파일을 두 번 세지 않게)."""
    cands: list[Root] = []
    for p in paths:
        np = normalize_root(p)
        cands.append(Root(np, anchor_of(np), drive_letter(np), False))
    for letter, p in simulated or []:
        np = normalize_root(p)
        cands.append(Root(np, np, letter.upper(), True))
    cands.sort(key=lambda r: len(r.path))
    keep: list[Root] = []
    for r in cands:
        outer = next((k for k in keep if is_within(r.path, k.path)), None)
        if outer:
            warn(f"  알림: '{r.path}' 는 '{outer.path}' 안에 있어 따로 검사하지 않습니다.")
            continue
        keep.append(r)
    return keep


@dataclass
class InventoryStats:
    files: int = 0
    dirs: int = 0
    bytes: int = 0
    errors: int = 0
    skipped: int = 0
    roots: list[dict] = field(default_factory=list)


_FILE_UPSERT = """
INSERT INTO files(path, path_raw, dir_id, root_id, volume_id, drive_letter, name, ext, size,
                  birth_ns, mtime_ns, attrs, readonly, hidden, system, status,
                  copy_by_date, copy_name, is_temp, name_issue, stat_key, seen_run)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
ON CONFLICT(path) DO UPDATE SET
  path_raw=excluded.path_raw, dir_id=excluded.dir_id, root_id=excluded.root_id,
  volume_id=excluded.volume_id, drive_letter=excluded.drive_letter, name=excluded.name,
  ext=excluded.ext, size=excluded.size, birth_ns=excluded.birth_ns, mtime_ns=excluded.mtime_ns,
  attrs=excluded.attrs, readonly=excluded.readonly, hidden=excluded.hidden, system=excluded.system,
  status=excluded.status, copy_by_date=excluded.copy_by_date, copy_name=excluded.copy_name,
  is_temp=excluded.is_temp, name_issue=excluded.name_issue,
  partial_hash = CASE WHEN files.stat_key IS excluded.stat_key AND files.hash_status='ok'
                      THEN files.partial_hash ELSE NULL END,
  full_hash    = CASE WHEN files.stat_key IS excluded.stat_key AND files.hash_status='ok'
                      THEN files.full_hash ELSE NULL END,
  hash_status  = CASE WHEN files.stat_key IS excluded.stat_key AND files.hash_status='ok'
                      THEN 'ok' ELSE NULL END,
  stat_key=excluded.stat_key, seen_run=excluded.seen_run
"""

_DIR_UPSERT = """
INSERT INTO dirs(path, path_raw, parent_id, root_id, volume_id, name, depth, listed_ok, seen_run)
VALUES (?,?,?,?,?,?,?,1,?)
ON CONFLICT(path) DO UPDATE SET
  path_raw=excluded.path_raw, parent_id=excluded.parent_id, root_id=excluded.root_id,
  volume_id=excluded.volume_id, name=excluded.name, depth=excluded.depth, listed_ok=1,
  seen_run=excluded.seen_run
RETURNING dir_id
"""


def _upsert_volume(db: Database, run_id: int, root: Root) -> int:
    try:
        vi = pinfo.volume_info(root.path)
        serial, label, fs_type, mount = vi.serial, vi.label, vi.fs_type, vi.mount_root
    except OSError:
        serial, label, fs_type, mount = f"알수없음-{root.letter or root.path}", None, None, None
    sp = pinfo.space(root.path) or (None, None)
    row = db.con.execute(
        """INSERT INTO volumes(serial, label, fs_type, mount_root, last_letter, total_bytes, free_bytes, seen_run)
           VALUES(?,?,?,?,?,?,?,?)
           ON CONFLICT(serial) DO UPDATE SET label=excluded.label, fs_type=excluded.fs_type,
             mount_root=excluded.mount_root, last_letter=excluded.last_letter,
             total_bytes=excluded.total_bytes, free_bytes=excluded.free_bytes, seen_run=excluded.seen_run
           RETURNING volume_id""",
        (serial, label, fs_type, mount, root.letter, sp[0], sp[1], run_id)).fetchone()
    return int(row[0])


def _upsert_root(db: Database, run_id: int, root: Root, volume_id: int) -> int:
    row = db.con.execute(
        """INSERT INTO roots(path, anchor, letter, simulated, volume_id, seen_run) VALUES(?,?,?,?,?,?)
           ON CONFLICT(path) DO UPDATE SET anchor=excluded.anchor, letter=excluded.letter,
             simulated=excluded.simulated, volume_id=excluded.volume_id, seen_run=excluded.seen_run
           RETURNING root_id""",
        (dbtext(root.path), root.anchor, root.letter, int(root.simulated), volume_id, run_id)).fetchone()
    return int(row[0])


def collect(db: Database, run_id: int, roots: list[Root], excl: Exclusions,
            progress=print, progress_every: float = 2.0) -> InventoryStats:
    stats = InventoryStats()
    con = db.con
    batch: list[tuple] = []
    last_report = time.monotonic()
    last_commit = time.monotonic()

    def flush():
        if batch:
            con.executemany(_FILE_UPSERT, batch)
            batch.clear()

    def upsert_dir(path: str, parent_id, root_id, volume_id, name, depth) -> int:
        row = con.execute(_DIR_UPSERT, (dbtext(path), to_raw(path), parent_id, root_id, volume_id,
                                        dbtext(name), depth, run_id)).fetchone()
        stats.dirs += 1
        return int(row[0])

    def incomplete(dir_id: int):
        con.execute("UPDATE dirs SET listed_ok=0 WHERE dir_id=?", (dir_id,))

    def os_error(stage: str, path: str, e: OSError):
        kind, code = classify_os_error(e)
        db.error(run_id, stage, kind, dbtext(path), dbtext(str(e)), code)
        stats.errors += 1

    for root in roots:
        try:
            st = os.stat(to_fs(root.path))
            if not _stat.S_ISDIR(st.st_mode):
                raise NotADirectoryError(f"폴더가 아닙니다: {root.path}")
        except OSError as e:
            os_error("목록", root.path, e)
            progress(f"  검사 시작점을 열 수 없습니다: {root.path} ({e})")
            continue
        volume_id = _upsert_volume(db, run_id, root)
        root_id = _upsert_root(db, run_id, root, volume_id)
        root_dir_id = upsert_dir(root.path, None, root_id, volume_id, root.path, 0)
        root_files_before = stats.files
        root_bytes_before = stats.bytes
        stack: list[tuple[str, int, int, list[str]]] = [
            (root.path, root_dir_id, 0, rel_parts(root.path, root.anchor))]
        while stack:
            dpath, did, depth, parts = stack.pop()
            try:
                with os.scandir(to_fs(dpath)) as it:
                    entries = list(it)
            except OSError as e:
                os_error("목록", dpath, e)
                incomplete(did)
                continue
            if any(en.name == MARKER_NAME for en in entries):
                db.skip(run_id, "이 프로그램의 출력 폴더", "dir", dbtext(dpath))
                stats.skipped += 1
                continue
            entries.sort(key=lambda en: en.name)
            subdirs: list[tuple[str, int, int, list[str]]] = []
            for en in entries:
                full = os.path.join(dpath, en.name)
                try:
                    st = en.stat(follow_symlinks=False)
                except OSError as e:
                    os_error("목록", full, e)
                    incomplete(did)
                    continue
                fl = pinfo.flags(st, en.name)
                is_dir = _stat.S_ISDIR(st.st_mode) or (
                    pinfo.IS_WINDOWS and bool(fl.attrs & pinfo.FILE_ATTRIBUTE_DIRECTORY))
                kind = "dir" if is_dir else "file"
                if fl.is_link:
                    db.skip(run_id, "바로가기·링크(따라가지 않음)", kind, dbtext(full))
                    stats.skipped += 1
                    continue
                cparts = parts + [en.name]
                reason = excl.match(full, cparts)
                if reason:
                    db.skip(run_id, reason, kind, dbtext(full))
                    stats.skipped += 1
                    continue
                if is_dir:
                    cid = upsert_dir(full, did, root_id, volume_id, en.name, depth + 1)
                    subdirs.append((full, cid, depth + 1, cparts))
                    continue
                if not _stat.S_ISREG(st.st_mode):
                    db.skip(run_id, "특수 파일", "file", dbtext(full))
                    stats.skipped += 1
                    continue
                birth = pinfo.birthtime_ns(full, st)
                mtime = int(st.st_mtime_ns)
                size = int(st.st_size)
                _, ext = split_ext(en.name)
                batch.append((
                    dbtext(full), to_raw(full), did, root_id, volume_id, root.letter,
                    dbtext(en.name), dbtext(ext), size, birth, mtime, int(fl.attrs),
                    int(fl.readonly), int(fl.hidden), int(fl.is_system),
                    "placeholder" if fl.placeholder else "ok",
                    int(is_copy_by_date(birth, mtime)), copy_name_marker(en.name),
                    int(is_temp(en.name)), int(has_name_issue(full)),
                    f"{size}:{mtime}:{birth if birth is not None else ''}", run_id))
                stats.files += 1
                stats.bytes += size
                if len(batch) >= 5000:
                    flush()
            # 이름 순서대로 내려가도록 거꾸로 쌓는다
            stack.extend(reversed(subdirs))
            now = time.monotonic()
            if now - last_commit > 2.0:
                flush()
                con.commit()
                last_commit = now
            if now - last_report > progress_every:
                progress(f"  목록: 파일 {stats.files:,}개 · 폴더 {stats.dirs:,}개 · 오류 {stats.errors:,}건")
                last_report = now
        stats.roots.append({"path": root.path, "files": stats.files - root_files_before,
                            "bytes": stats.bytes - root_bytes_before})
    flush()
    con.commit()
    return stats
