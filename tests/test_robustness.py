"""멈추지 않기 시험 (완료 기준 4): 긴 경로·한글 경로·접근 거부·읽는 중 변경에서도 끝까지 간다."""
import os
import subprocess

import pytest

from helpers import results, scan_dataset
from scanner import hashing


def test_long_and_korean_paths_scanned(base_dataset, tmp_path):
    res = scan_dataset(base_dataset, str(tmp_path / "out"))
    r = results(base_dataset, res.db_path, res.run_id)
    long_files = [p for p in r["files"] if "긴경로/" in p]
    assert len(long_files) == 2
    abs_len = max(len(os.path.join(base_dataset["data"], p)) for p in long_files)
    assert abs_len > 260, "긴 경로 함정이 260자를 넘지 않음"
    # 긴 경로 안의 사본도 해시되어 중복으로 묶였는지
    assert any(any("긴경로_사본" in p for p in g) for g in r["dup"])
    assert any("😀" in p for p in r["files"]) and any("✓" in p for p in r["files"])
    assert r["errors"] == []


def _deny(path: str):
    """읽기 거부를 만든다. 리눅스 root 는 권한을 무시하므로 None 을 돌려 모의로 대신한다."""
    if os.name == "nt":
        # *S-1-1-0 = Everyone (윈도우 언어와 무관한 고유 번호).
        # (RD) = 파일 내용 읽기 / 폴더 목록 보기만 막는다. (R) 전체를 막으면 권한 설정 읽기까지 막혀
        # 시험 뒤 되돌리기(/remove:d)가 거부된다(첫 윈도우 실행에서 확인됨).
        subprocess.run(["icacls", path, "/deny", "*S-1-1-0:(RD)"], check=True, capture_output=True)
        return lambda: subprocess.run(["icacls", path, "/remove:d", "*S-1-1-0"], capture_output=True).returncode
    if os.geteuid() != 0:
        os.chmod(path, 0)
        return lambda: os.chmod(path, 0o755 if os.path.isdir(path) else 0o644) or 0
    return None


def test_access_denied_is_recorded_and_scan_continues(tmp_path, monkeypatch):
    from testkit.generator import generate
    info = generate(str(tmp_path / "set"), seed=11)
    deny_dir = os.path.join(info["roots"]["D"], "업무", "2022업무", "감사")
    deny_file = os.path.join(info["roots"]["E"], "함정", "큰파일_A.bin")
    undo = []
    real = [_deny(deny_dir), _deny(deny_file)]
    if None in real:
        # root 권한 리눅스: scandir·open 이 그 경로에서 PermissionError 를 내도록 모의
        real_scandir, real_hash = os.scandir, hashing.hash_file

        def fake_scandir(p):
            if os.path.normpath(p) == os.path.normpath(deny_dir):
                raise PermissionError(13, "Permission denied (모의)", p)
            return real_scandir(p)

        def fake_hash(p, *a, **k):
            if os.path.normpath(p) == os.path.normpath(deny_file):
                raise PermissionError(13, "Permission denied (모의)", p)
            return real_hash(p, *a, **k)

        monkeypatch.setattr("scanner.inventory.os.scandir", fake_scandir)
        monkeypatch.setattr(hashing, "hash_file", fake_hash)
    else:
        undo = real
    undo_codes = []
    try:
        res = scan_dataset(info, str(tmp_path / "out"))
        r = results(info, res.db_path, res.run_id)
    finally:
        for u in undo:
            undo_codes.append(u())  # 되돌리기 실패가 시험 결과를 가리지 않게, 판정은 맨 끝에
    kinds = {(stage, kind) for stage, kind, _ in r["errors"]}
    assert ("목록", "접근거부") in kinds
    assert ("해시", "접근거부") in kinds
    # 나머지는 정상 진단
    assert len(r["files"]) > 100 and r["dup"]
    # 목록을 못 읽은 폴더와 그 위 폴더는 중복 판정에서 빠진다 (보수적)
    assert not any(g for g in r["groups"] if any(m["path"].startswith("D/업무/2022업무") for m in g["members"]))
    # 해시를 못 읽은 파일은 중복 묶음에 들지 않는다
    assert not any(any(p.endswith("큰파일_A.bin") for p in g) for g in r["dup"])
    assert all(c == 0 for c in undo_codes), f"접근 거부 되돌리기 실패: {undo_codes}"


def test_file_changed_while_reading(tmp_path, monkeypatch):
    from testkit.generator import generate
    info = generate(str(tmp_path / "set"), seed=12)
    target = os.path.join(info["roots"]["E"], "함정", "큰파일_B.bin")
    real_hash = hashing.hash_file

    def fake(p, limit, size, mtime):
        if os.path.normpath(p) == os.path.normpath(target):
            raise hashing.ChangedWhileReading("모의: 읽는 동안 바뀜")
        return real_hash(p, limit, size, mtime)

    monkeypatch.setattr(hashing, "hash_file", fake)
    res = scan_dataset(info, str(tmp_path / "out"))
    r = results(info, res.db_path, res.run_id)
    assert [(st, k) for st, k, _ in r["errors"]] == [("해시", "읽는중변경")]
    assert not any(any(p.endswith("큰파일_B.bin") for p in g) for g in r["dup"])


def test_missing_root_does_not_stop(tmp_path, base_dataset):
    from scanner.scan import run_scan
    res = run_scan([str(tmp_path / "없는폴더"), base_dataset["roots"]["D"]], str(tmp_path / "out"),
                   progress=lambda *_: None)
    assert res.summary["오류합계"] >= 1
    assert res.summary["총파일"] > 10


@pytest.mark.skipif(os.name == "nt", reason="cp949 바이트 이름은 리눅스에서만 만들 수 있음")
def test_cp949_name_on_posix(base_dataset, tmp_path):
    res = scan_dataset(base_dataset, str(tmp_path / "out"))
    r = results(base_dataset, res.db_path, res.run_id)
    weird = [p for p in r["files"] if "cp949_" in p]
    assert len(weird) == 1 and "\\x" in weird[0]
    assert res.summary["표지"]["이름글자문제"] == 1
