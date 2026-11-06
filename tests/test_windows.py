"""윈도우에서만 확인할 수 있는 것 — GitHub Actions 윈도우 환경에서 돈다.

(긴 경로·실제 만든 날짜·숨김 속성·정션·접근 거부는 다른 시험 파일이 윈도우에서도 그대로 돌며 확인한다.
 여기에는 윈도우 전용 동작만 따로 모았다.)
"""
import os
import re
import sqlite3

import pytest

pytestmark = [pytest.mark.windows,
              pytest.mark.skipif(os.name != "nt", reason="윈도우 전용")]


def test_volume_serial_format(tmp_path):
    from scanner.platform_info import volume_info
    vi = volume_info(str(tmp_path))
    assert re.fullmatch(r"[0-9A-F]{4}-[0-9A-F]{4}", vi.serial), vi.serial
    assert vi.fs_type, "파일 시스템 이름을 못 읽음"
    assert vi.mount_root and vi.mount_root.endswith("\\")


def test_real_root_records_letter_and_serial(tmp_path):
    from scanner.scan import run_scan
    root = tmp_path / "검사"
    root.mkdir()
    (root / "가.txt").write_bytes(b"1")
    (root / "나.txt").write_bytes(b"1")
    res = run_scan([str(root)], str(tmp_path / "out"), progress=lambda *_: None)
    con = sqlite3.connect(res.db_path)
    letters = {r[0] for r in con.execute("SELECT drive_letter FROM files")}
    serials = {r[0] for r in con.execute("SELECT serial FROM volumes")}
    con.close()
    assert letters == {str(tmp_path)[0].upper()}
    assert all(re.fullmatch(r"[0-9A-F]{4}-[0-9A-F]{4}", s) for s in serials)


def test_generator_sets_real_birthtime(base_dataset):
    ans = base_dataset["answer"]
    checked = 0
    for f in ans["files"]:
        if f["excluded"] or f["birth_ns"] is None:
            continue
        p = os.path.join(base_dataset["data"], *f["path"].split("/"))
        st = os.stat("\\\\?\\" + p)
        assert abs(st.st_birthtime_ns - f["birth_ns"]) < 10**7, f["path"]  # FILETIME 100ns 단위 오차
        assert st.st_mtime_ns == f["mtime_ns"]
        checked += 1
    assert checked > 100


def test_copy_changes_birthtime_like_windows_does(tmp_path):
    """윈도우 복사: 만든 날짜는 새로, 수정한 날짜는 원본 그대로 → '만든 > 수정' 표지가 붙는다."""
    import shutil
    import time
    from scanner.scan import run_scan
    src = tmp_path / "원본"
    src.mkdir()
    f = src / "문서.hwpx"
    f.write_bytes(b"x" * 100)
    old = time.time_ns() - 400 * 86400 * 10**9
    os.utime(f, ns=(old, old))
    dst = tmp_path / "사본"
    dst.mkdir()
    shutil.copy2(f, dst / "문서.hwpx")  # 시험 준비용 복사 (진단기는 복사하지 않음)
    res = run_scan([str(src), str(dst)], str(tmp_path / "out"), progress=lambda *_: None)
    con = sqlite3.connect(res.db_path)
    flags = dict(con.execute("SELECT path, copy_by_date FROM files"))
    con.close()
    assert flags[str(dst / "문서.hwpx")] == 1


def test_normalize_drive_only():
    from scanner.winpath import normalize_root
    assert normalize_root("C:") == "C:\\"
    assert normalize_root('"C:\\Users"') == "C:\\Users"
