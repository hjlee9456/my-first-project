"""정답셋 일치 시험 (완료 기준 1): 완전중복·중첩 백업 탐지가 정답과 100% 일치."""
import pytest

from helpers import answer_rel, group_signature, results, scan_dataset


@pytest.fixture(scope="module")
def scanned(base_dataset, tmp_path_factory):
    out = tmp_path_factory.mktemp("진단") / "out"
    res = scan_dataset(base_dataset, str(out))
    return base_dataset, res, results(base_dataset, res.db_path, res.run_id)


def test_no_unexpected_errors(scanned):
    _, _, r = scanned
    assert r["errors"] == []


def test_file_list_matches(scanned):
    info, _, r = scanned
    ans = info["answer"]
    expected = {answer_rel(f["path"]) for f in ans["files"] if not f["excluded"]}
    assert set(r["files"]) == expected
    for f in ans["files"]:
        if not f["excluded"]:
            assert r["files"][answer_rel(f["path"])]["size"] == f["size"], f["path"]


def test_excluded_never_listed(scanned):
    info, _, r = scanned
    excluded = {answer_rel(e["path"]) for e in info["answer"]["excluded"]}
    assert excluded and not (excluded & set(r["files"]))
    reasons = {reason for reason, _, _ in r["skipped"]}
    assert "제외 목록" in reasons and "이 프로그램의 출력 폴더" in reasons


def test_exact_duplicates_match(scanned):
    info, _, r = scanned
    exp = {frozenset(answer_rel(p) for p in g) for g in info["answer"]["exact_dup_groups"]}
    got = {frozenset(g) for g in r["dup"]}
    assert got == exp
    assert len(exp) > 20


def test_zero_byte_not_grouped(scanned):
    info, _, r = scanned
    zero = {answer_rel(p) for p in info["answer"]["zero_byte_files"]}
    assert len(zero) >= 4
    assert all(r["files"][p]["size"] == 0 for p in zero)
    assert not any(zero & set(g) for g in r["dup"])


def test_folder_groups_match(scanned):
    info, _, r = scanned
    exp = {group_signature(g) for g in info["answer"]["folder_groups"]}
    got = {group_signature(g) for g in r["groups"]}
    assert got == exp


def test_folder_contains_match(scanned):
    info, _, r = scanned
    exp = {(c["inner"], c["outer"]) for c in info["answer"]["folder_contains"]}
    got = {(c["inner"], c["outer"]) for c in r["contains"]}
    assert got == exp


def test_intended_scenarios_present(scanned):
    """정답 계산기와 무관하게, 사람이 설계한 시나리오가 실제로 잡히는지."""
    info, _, r = scanned
    for it in info["answer"]["intended"]:
        a, b = it["paths"]
        if it["kind"] in ("a", "b"):
            hit = [g for g in r["groups"] if {a, b} <= {m["path"] for m in g["members"]}]
            assert hit, f"못 찾음: {it}"
            assert hit[0]["level"] == it["kind"], it
        else:
            assert {"inner": a, "outer": b} in r["contains"], f"못 찾음: {it}"


def test_marker_flags(scanned):
    info, _, r = scanned
    fl = info["answer"]["expected_flags"]
    files = r["files"]
    assert {p for p, v in files.items() if v["temp"]} == {answer_rel(p) for p in fl["temp"]}
    assert {p: v["cn"] for p, v in files.items() if v["cn"]} == \
           {answer_rel(p): m for p, m in fl["copy_name"].items()}
    assert {p for p, v in files.items() if v["cd"]} == {answer_rel(p) for p in fl["copy_by_date"]}
    assert {p for p, v in files.items() if v["ro"]} == {answer_rel(p) for p in fl["readonly"]}
    assert {p for p, v in files.items() if v["hid"]} == {answer_rel(p) for p in fl["hidden"]}


def test_links_not_followed(scanned):
    info, _, r = scanned
    made = [ln for ln in info["answer"]["links"] if ln.get("made")]
    assert made, "고리 함정을 만들지 못함"
    skipped_paths = {p for reason, _, p in r["skipped"] if reason.startswith("바로가기")}
    assert len(skipped_paths) == len(made)
    assert not any(p.startswith("E/함정/고리/") for p in r["files"])


def test_report_files_written(scanned):
    import json
    import os
    _, res, _ = scanned
    for name in ("진단보고서.html", "진단상세.xlsx", "요약숫자.json", "scan.sqlite"):
        assert os.path.exists(os.path.join(res.out_dir, name)), name
    nums = json.load(open(os.path.join(res.out_dir, "요약숫자.json"), encoding="utf-8"))
    assert nums["완전중복"]["묶음수"] == len(scanned[0]["answer"]["exact_dup_groups"])
    text = json.dumps(nums, ensure_ascii=False)
    assert "C/Users" not in text and "/data/" not in text and "\\data\\" not in text, "요약 숫자에 경로가 들어감"
