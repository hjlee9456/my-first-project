"""진단 전체 흐름: 목록 → 해시 → 완전중복 → 폴더 중복 → 보고서."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from . import __version__, duplicates, folders, hashing, inventory, report
from .db import Database
from .exclusions import Exclusions
from .inventory import Root, prepare_roots
from .output import OutputDir

DB_NAME = "scan.sqlite"


@dataclass
class ScanResult:
    out_dir: str
    db_path: str
    run_id: int
    summary: dict
    stage_stats: dict


def run_scan(roots: list[str], out_dir: str, *, excludes: list[str] | None = None,
             exclude_patterns: list[str] | None = None, use_default_excludes: bool = True, dest: str | None = None,
             simulated: list[tuple[str, str]] | None = None, progress=print) -> ScanResult:
    root_objs: list[Root] = prepare_roots(roots, simulated, warn=progress)
    if not root_objs:
        raise ValueError("검사할 폴더를 하나 이상 지정하세요.")
    out = OutputDir(out_dir, [r.path for r in root_objs])
    con = out.connect_db(DB_NAME)
    db = Database(con)
    excl = Exclusions.build(excludes or [], exclude_patterns or [], use_default_excludes, out.path)
    options = {
        "roots": [r.path for r in root_objs],
        "simulated": [[r.letter, r.path] for r in root_objs if r.simulated],
        "excludes": list(excludes or []),
        "exclude_patterns": list(exclude_patterns or []),
        "default_excludes": use_default_excludes,
        "dest": dest,
    }
    run_id = db.start_run(__version__, options)
    stage: dict = {}
    try:
        t = time.monotonic()
        progress("1/5 목록 만들기 …")
        inv = inventory.collect(db, run_id, root_objs, excl, progress=progress)
        stage["목록"] = {**asdict(inv), "seconds": round(time.monotonic() - t, 2)}
        progress(f"    파일 {inv.files:,}개 · 폴더 {inv.dirs:,}개 · 오류 {inv.errors:,}건")

        t = time.monotonic()
        progress("2/5 해시 계산 (크기가 같은 파일만) …")
        hs = hashing.compute(db, run_id, progress=progress)
        stage["해시"] = {**asdict(hs), "seconds": round(time.monotonic() - t, 2)}
        progress(f"    앞부분 {hs.partial_done:,}개 · 전체 {hs.full_done:,}개 · 다시 씀 {hs.reused:,}개")

        t = time.monotonic()
        progress("3/5 완전 중복 묶기 …")
        ds = duplicates.analyze(con, run_id)
        stage["완전중복"] = {**asdict(ds), "seconds": round(time.monotonic() - t, 2)}

        t = time.monotonic()
        progress("4/5 중첩 백업(폴더 중복) 찾기 …")
        fs = folders.analyze(con, run_id)
        stage["폴더"] = {**asdict(fs), "seconds": round(time.monotonic() - t, 2)}

        db.finish_run(run_id, "완료", stage)
        t = time.monotonic()
        progress("5/5 보고서 쓰기 …")
        summary = report.write_reports(out, con, run_id, dest)
        stage["보고서"] = {"seconds": round(time.monotonic() - t, 2)}
        db.finish_run(run_id, "완료", stage)
    except BaseException:
        db.finish_run(run_id, "중단", stage)
        con.close()
        raise
    con.close()
    return ScanResult(out_dir=out.path, db_path=out.file_path(DB_NAME), run_id=run_id,
                      summary=summary, stage_stats=stage)


def rebuild_report(out_dir: str, dest: str | None = None, progress=print) -> dict:
    out = OutputDir(out_dir)
    con = out.connect_db(DB_NAME)
    db = Database(con)
    run_id = db.last_finished_run()
    if run_id is None:
        raise ValueError("끝까지 마친 진단이 없습니다. 먼저 scan 을 실행하세요.")
    progress(f"실행번호 {run_id} 의 보고서를 다시 씁니다 …")
    s = report.write_reports(out, con, run_id, dest)
    con.close()
    return s
