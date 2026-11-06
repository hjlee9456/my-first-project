"""진단 DB(SQLite) 구조.

같은 출력 폴더로 다시 실행하면 같은 DB를 이어 쓴다.
- 파일·폴더 목록은 경로를 열쇠로 갱신한다.
- 크기·수정 시각·만든 시각이 그대로인 파일은 전에 계산한 해시를 다시 쓴다(이어 하기).
- 분석 결과는 실행 번호(run_id)별로 쌓는다(지우지 않는다).
"""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS runs(
    run_id INTEGER PRIMARY KEY,
    started_at TEXT, finished_at TEXT, status TEXT,
    tool_version TEXT, options_json TEXT, stats_json TEXT
);

CREATE TABLE IF NOT EXISTS volumes(
    volume_id INTEGER PRIMARY KEY,
    serial TEXT UNIQUE,          -- 드라이브 문자 대신 이것으로 구별 (규칙 13)
    label TEXT, fs_type TEXT, mount_root TEXT,
    last_letter TEXT, total_bytes INTEGER, free_bytes INTEGER, seen_run INTEGER
);

CREATE TABLE IF NOT EXISTS roots(
    root_id INTEGER PRIMARY KEY,
    path TEXT UNIQUE, anchor TEXT, letter TEXT, simulated INTEGER,
    volume_id INTEGER, seen_run INTEGER
);

CREATE TABLE IF NOT EXISTS dirs(
    dir_id INTEGER PRIMARY KEY,
    path TEXT UNIQUE, path_raw BLOB,
    parent_id INTEGER, root_id INTEGER, volume_id INTEGER,
    name TEXT, depth INTEGER,
    listed_ok INTEGER,           -- 0이면 목록을 끝까지 못 읽음(접근 거부 등) → 중복 판정에서 보수적으로 다룸
    seen_run INTEGER
);
CREATE INDEX IF NOT EXISTS dirs_run ON dirs(seen_run);

CREATE TABLE IF NOT EXISTS files(
    file_id INTEGER PRIMARY KEY,
    path TEXT UNIQUE, path_raw BLOB,
    dir_id INTEGER, root_id INTEGER, volume_id INTEGER, drive_letter TEXT,
    name TEXT, ext TEXT, size INTEGER,
    birth_ns INTEGER, mtime_ns INTEGER,
    attrs INTEGER, readonly INTEGER, hidden INTEGER, system INTEGER,
    status TEXT,                 -- 'ok' | 'placeholder'(내용이 이 PC에 없음)
    copy_by_date INTEGER, copy_name TEXT, is_temp INTEGER, name_issue INTEGER,
    stat_key TEXT,               -- 크기:수정:만든 — 바뀌면 해시를 버린다
    partial_hash TEXT, full_hash TEXT, hash_status TEXT, hash_run INTEGER,
    seen_run INTEGER
);
CREATE INDEX IF NOT EXISTS files_run_size ON files(seen_run, size);
CREATE INDEX IF NOT EXISTS files_full ON files(full_hash);
CREATE INDEX IF NOT EXISTS files_dir ON files(dir_id);

CREATE TABLE IF NOT EXISTS errors(
    error_id INTEGER PRIMARY KEY, run_id INTEGER,
    stage TEXT, kind TEXT, path TEXT, message TEXT, code INTEGER
);
CREATE INDEX IF NOT EXISTS errors_run ON errors(run_id);

CREATE TABLE IF NOT EXISTS skipped(
    run_id INTEGER, reason TEXT, kind TEXT, path TEXT
);
CREATE INDEX IF NOT EXISTS skipped_run ON skipped(run_id);

CREATE TABLE IF NOT EXISTS dup_groups(
    run_id INTEGER, group_no INTEGER, full_hash TEXT, size INTEGER,
    member_count INTEGER, reclaimable INTEGER,
    PRIMARY KEY(run_id, group_no)
);
CREATE TABLE IF NOT EXISTS dup_members(run_id INTEGER, group_no INTEGER, file_id INTEGER);
CREATE INDEX IF NOT EXISTS dup_members_run ON dup_members(run_id, group_no);

CREATE TABLE IF NOT EXISTS folder_groups(
    run_id INTEGER, group_no INTEGER, level TEXT,
    file_count INTEGER, total_bytes INTEGER, member_count INTEGER,
    PRIMARY KEY(run_id, group_no)
);
CREATE TABLE IF NOT EXISTS folder_members(
    run_id INTEGER, group_no INTEGER, dir_id INTEGER,
    a_class INTEGER,             -- 같은 묶음 안에서 구조·이름까지 같은 것끼리 같은 번호
    role TEXT                    -- '보고' | '참고'(상위 폴더가 이미 중복이라 접혀 있던 짝)
);
CREATE INDEX IF NOT EXISTS folder_members_run ON folder_members(run_id, group_no);
CREATE TABLE IF NOT EXISTS folder_contains(
    run_id INTEGER, inner_dir_id INTEGER, outer_dir_id INTEGER,
    inner_files INTEGER, inner_bytes INTEGER, outer_files INTEGER, outer_bytes INTEGER
);
"""


def now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


class Database:
    def __init__(self, con: sqlite3.Connection):
        self.con = con
        con.executescript(SCHEMA)
        cur = con.execute("SELECT value FROM meta WHERE key='schema_version'")
        row = cur.fetchone()
        if row is None:
            con.execute("INSERT INTO meta(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
        elif int(row[0]) != SCHEMA_VERSION:
            raise RuntimeError(f"DB 구조 판이 다릅니다({row[0]} ≠ {SCHEMA_VERSION}). 새 출력 폴더를 쓰세요.")
        con.commit()

    def start_run(self, tool_version: str, options: dict) -> int:
        cur = self.con.execute(
            "INSERT INTO runs(started_at, status, tool_version, options_json) VALUES(?,?,?,?)",
            (now(), "진행중", tool_version, json.dumps(options, ensure_ascii=False)))
        self.con.commit()
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str, stats: dict | None = None) -> None:
        self.con.execute("UPDATE runs SET finished_at=?, status=?, stats_json=? WHERE run_id=?",
                         (now(), status, json.dumps(stats or {}, ensure_ascii=False), run_id))
        self.con.commit()

    def last_finished_run(self) -> int | None:
        row = self.con.execute(
            "SELECT run_id FROM runs WHERE status='완료' ORDER BY run_id DESC LIMIT 1").fetchone()
        return int(row[0]) if row else None

    def error(self, run_id: int, stage: str, kind: str, path: str, message: str, code: int | None) -> None:
        self.con.execute(
            "INSERT INTO errors(run_id, stage, kind, path, message, code) VALUES(?,?,?,?,?,?)",
            (run_id, stage, kind, path, message, code))

    def skip(self, run_id: int, reason: str, kind: str, path: str) -> None:
        self.con.execute("INSERT INTO skipped(run_id, reason, kind, path) VALUES(?,?,?,?)",
                         (run_id, reason, kind, path))


def classify_os_error(e: OSError) -> tuple[str, int | None]:
    """윈도우·리눅스 오류를 사람이 읽는 종류로."""
    win = getattr(e, "winerror", None)
    if win is not None:
        kinds = {5: "접근거부", 32: "다른 프로그램이 사용중", 33: "다른 프로그램이 사용중",
                 2: "경로없음", 3: "경로없음", 206: "경로너무김", 123: "이름오류",
                 1920: "접근거부", 21: "장치준비안됨", 1005: "읽을수없는볼륨"}
        return kinds.get(win, "기타"), int(win)
    if isinstance(e, PermissionError):
        return "접근거부", e.errno
    if isinstance(e, FileNotFoundError):
        return "경로없음", e.errno
    import errno as _errno
    if e.errno == _errno.ENAMETOOLONG:
        return "경로너무김", e.errno
    return "기타", e.errno
