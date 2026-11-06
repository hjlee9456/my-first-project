"""2. 해시 계산 — 크기가 같은 파일끼리만 앞부분(64KB) → 전체 순으로 좁힌다.

- 해시는 BLAKE2b(256비트).
- 64KB 이하 파일은 앞부분 해시가 곧 전체 해시다.
- 크기가 유일한 파일은 중복일 수 없으므로 읽지 않는다.
- 계산한 해시는 자주 저장(commit)하므로, 중단 뒤 다시 실행하면 이어서 한다.
- 읽는 동안 크기·수정 시각이 바뀐 파일은 해시를 저장하지 않고 오류로 적는다.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass

from .db import Database, classify_os_error
from .textsafe import dbtext, from_raw
from .winpath import to_fs

PARTIAL_BYTES = 64 * 1024
CHUNK = 1024 * 1024


class ChangedWhileReading(Exception):
    pass


def hash_file(path: str, limit: int | None, expect_size: int, expect_mtime_ns: int) -> str:
    """파일을 읽기 전용으로 열어 해시를 낸다. limit 가 있으면 앞부분만."""
    h = hashlib.blake2b(digest_size=32)
    with open(to_fs(path), "rb") as f:
        st0 = os.fstat(f.fileno())
        if st0.st_size != expect_size or st0.st_mtime_ns != expect_mtime_ns:
            raise ChangedWhileReading("목록을 만든 뒤 크기나 수정 시각이 바뀌었습니다")
        remaining = expect_size if limit is None else min(limit, expect_size)
        while remaining > 0:
            chunk = f.read(min(CHUNK, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
        st1 = os.fstat(f.fileno())
        if st1.st_size != st0.st_size or st1.st_mtime_ns != st0.st_mtime_ns or remaining > 0:
            raise ChangedWhileReading("읽는 동안 파일이 바뀌었습니다")
    return h.hexdigest()


@dataclass
class HashStats:
    partial_done: int = 0
    full_done: int = 0
    bytes_read: int = 0
    reused: int = 0
    errors: int = 0


_PARTIAL_CANDIDATES = """
SELECT f.file_id, f.path_raw, f.path, f.size, f.mtime_ns FROM files f
JOIN (SELECT size FROM files WHERE seen_run=:run AND size>0 AND status='ok'
      GROUP BY size HAVING COUNT(*) > 1) s ON s.size = f.size
WHERE f.seen_run=:run AND f.status='ok' AND f.size>0
  AND (f.hash_status IS NULL OR (f.hash_status='ok' AND f.partial_hash IS NULL))
ORDER BY f.path
"""

_FULL_CANDIDATES = """
SELECT f.file_id, f.path_raw, f.path, f.size, f.mtime_ns FROM files f
JOIN (SELECT size, partial_hash FROM files
      WHERE seen_run=:run AND hash_status='ok' AND partial_hash IS NOT NULL AND size > :pb
      GROUP BY size, partial_hash HAVING COUNT(*) > 1) g
  ON g.size = f.size AND g.partial_hash = f.partial_hash
WHERE f.seen_run=:run AND f.hash_status='ok' AND f.full_hash IS NULL
ORDER BY f.path
"""


def _count_reusable(con, run_id: int) -> int:
    row = con.execute(
        "SELECT COUNT(*) FROM files WHERE seen_run=? AND hash_status='ok' AND hash_run < ?",
        (run_id, run_id)).fetchone()
    return int(row[0])


def compute(db: Database, run_id: int, progress=print, progress_every: float = 2.0) -> HashStats:
    con = db.con
    stats = HashStats(reused=_count_reusable(con, run_id))
    last_commit = time.monotonic()
    last_report = time.monotonic()

    def run_stage(sql: str, params: dict, stage: str):
        nonlocal last_commit, last_report
        rows = con.execute(sql, params).fetchall()
        total = len(rows)
        for i, (fid, raw, shown, size, mtime) in enumerate(rows, 1):
            path = from_raw(raw)
            try:
                if stage == "앞부분":
                    digest = hash_file(path, PARTIAL_BYTES, size, mtime)
                    full = digest if size <= PARTIAL_BYTES else None
                    con.execute("UPDATE files SET partial_hash=?, full_hash=?, hash_status='ok', hash_run=?"
                                " WHERE file_id=?", (digest, full, run_id, fid))
                    stats.partial_done += 1
                    stats.bytes_read += min(size, PARTIAL_BYTES)
                else:
                    digest = hash_file(path, None, size, mtime)
                    con.execute("UPDATE files SET full_hash=?, hash_run=? WHERE file_id=?",
                                (digest, run_id, fid))
                    stats.full_done += 1
                    stats.bytes_read += size
            except ChangedWhileReading as e:
                db.error(run_id, "해시", "읽는중변경", shown, str(e), None)
                con.execute("UPDATE files SET hash_status='error' WHERE file_id=?", (fid,))
                stats.errors += 1
            except OSError as e:
                kind, code = classify_os_error(e)
                db.error(run_id, "해시", kind, shown, dbtext(str(e)), code)
                con.execute("UPDATE files SET hash_status='error' WHERE file_id=?", (fid,))
                stats.errors += 1
            now = time.monotonic()
            if now - last_commit > 1.0:
                con.commit()
                last_commit = now
            if now - last_report > progress_every:
                progress(f"  해시({stage}): {i:,}/{total:,}")
                last_report = now
        con.commit()

    try:
        run_stage(_PARTIAL_CANDIDATES, {"run": run_id}, "앞부분")
        run_stage(_FULL_CANDIDATES, {"run": run_id, "pb": PARTIAL_BYTES}, "전체")
    finally:
        con.commit()  # 중단되어도 계산한 만큼은 남긴다
    return stats
