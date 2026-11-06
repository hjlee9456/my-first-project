"""이어 하기 시험 (완료 기준 5): 중단 뒤 다시 실행하면 이미 계산한 해시를 다시 쓴다."""
import sqlite3

import pytest

from helpers import mocked_birthtimes, results, scan_dataset
from scanner import hashing
from scanner.scan import run_scan


def _hashed(db):
    con = sqlite3.connect(db)
    n = con.execute("SELECT COUNT(*) FROM files WHERE hash_status='ok'").fetchone()[0]
    con.close()
    return n


def test_resume_after_interrupt(tmp_path, monkeypatch):
    from testkit.generator import generate
    info = generate(str(tmp_path / "set"), seed=21)
    out = str(tmp_path / "out")
    calls = {"n": 0}
    real = hashing.hash_file

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] > 25:
            raise KeyboardInterrupt  # 사용자가 Ctrl+C 를 눌렀다고 침
        return real(*a, **k)

    monkeypatch.setattr(hashing, "hash_file", flaky)
    sims = sorted(info["roots"].items())
    with pytest.raises(KeyboardInterrupt), mocked_birthtimes(info):
        run_scan([], out, simulated=sims, progress=lambda *_: None)
    db = str(tmp_path / "out" / "scan.sqlite")
    assert _hashed(db) == 25, "중단 전까지 계산한 해시가 저장되지 않음"

    counted = {"n": 0}

    def counting(*a, **k):
        counted["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(hashing, "hash_file", counting)
    res = scan_dataset(info, out)
    st = res.stage_stats["해시"]
    assert st["reused"] == 25
    assert counted["n"] == st["partial_done"] + st["full_done"]

    # 처음부터 한 번에 한 것과 결과가 같아야 한다
    monkeypatch.setattr(hashing, "hash_file", real)
    fresh = scan_dataset(info, str(tmp_path / "fresh"))
    st2 = fresh.stage_stats["해시"]
    assert st["partial_done"] + st["full_done"] + 25 == st2["partial_done"] + st2["full_done"]
    a = results(info, res.db_path, res.run_id)
    b = results(info, fresh.db_path, fresh.run_id)
    assert {frozenset(g) for g in a["dup"]} == {frozenset(g) for g in b["dup"]}
    assert a["contains"] == b["contains"]

    # 아무것도 바뀌지 않았으면 세 번째 실행은 파일을 하나도 읽지 않는다
    counted["n"] = 0
    monkeypatch.setattr(hashing, "hash_file", counting)
    third = scan_dataset(info, out)
    assert counted["n"] == 0
    assert third.stage_stats["해시"]["reused"] == st2["partial_done"]


def test_changed_file_is_rehashed(tmp_path, monkeypatch):
    import os
    from testkit.generator import generate
    info = generate(str(tmp_path / "set"), seed=22)
    out = str(tmp_path / "out")
    scan_dataset(info, out)
    target = os.path.join(info["roots"]["E"], "함정", "큰파일_A.bin")
    st = os.stat(target)
    os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))  # 수정 시각만 바꿈
    seen = []
    real = hashing.hash_file

    def spy(p, *a, **k):
        seen.append(os.path.basename(p))
        return real(p, *a, **k)

    monkeypatch.setattr(hashing, "hash_file", spy)
    scan_dataset(info, out)
    assert seen.count("큰파일_A.bin") == 2  # 앞부분·전체를 다시 계산
    assert len(set(seen)) == 1
