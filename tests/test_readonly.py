"""읽기 전용 시험 (완료 기준 2): 스캔 전후로 검사 대상 모든 파일의 경로·크기·수정 시각·속성·해시가 같다."""
from helpers import scan_dataset, snapshot


def test_scan_does_not_touch_targets(base_dataset, tmp_path):
    data = base_dataset["data"]
    before = snapshot(data)
    assert len(before) > 100
    res = scan_dataset(base_dataset, str(tmp_path / "out"))
    # 같은 출력 폴더로 한 번 더 (이어 하기 경로도 읽기 전용이어야 함)
    scan_dataset(base_dataset, str(tmp_path / "out"))
    after = snapshot(data)
    assert after == before
    assert res.out_dir.startswith(str(tmp_path))


def test_output_inside_scanned_tree_is_excluded_and_targets_untouched(tmp_path):
    """출력 폴더가 검사 대상 안에 있어도 자기 자신은 검사하지 않고, 다른 파일은 그대로다."""
    from testkit.generator import generate
    info = generate(str(tmp_path / "set"), seed=7)
    data = info["data"]
    before = snapshot(data)
    out_inside = info["roots"]["E"] + "/진단결과"
    from helpers import results
    res = scan_dataset(info, out_inside)
    r = results(info, res.db_path, res.run_id)
    assert not any(p.startswith("E/진단결과/") for p in r["files"])
    after = snapshot(data)
    added = set(after) - set(before)
    assert added and all(p.replace("\\", "/").startswith("E/진단결과") for p in added)
    for k in before:
        assert after[k] == before[k], k
