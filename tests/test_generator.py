"""합성 정답셋 생성기 시험 — 같은 시드는 같은 결과, 아무것도 덮어쓰지 않음, 정답이 설계대로."""
import json
import os

import pytest

from helpers import snapshot
from testkit.generator import generate


def _strip_times_of_dirs(snap: dict) -> dict:
    return {k: v for k, v in snap.items() if v[0] != "dir"}


def test_same_seed_same_result(tmp_path):
    a = generate(str(tmp_path / "a"), seed=5)
    b = generate(str(tmp_path / "b"), seed=5)
    sa, sb = snapshot(a["data"]), snapshot(b["data"])
    assert _strip_times_of_dirs(sa) == _strip_times_of_dirs(sb)
    with open(a["answer_path"], "rb") as fa, open(b["answer_path"], "rb") as fb:
        assert fa.read() == fb.read()


def test_different_seed_differs(tmp_path):
    a = generate(str(tmp_path / "a"), seed=5)
    b = generate(str(tmp_path / "b"), seed=6)
    assert a["answer"]["exact_dup_groups"] != b["answer"]["exact_dup_groups"] or \
        snapshot(a["data"]) != snapshot(b["data"])


def test_refuses_nonempty_folder(tmp_path):
    d = tmp_path / "있음"
    d.mkdir()
    (d / "x.txt").write_text("원래 내용", encoding="utf-8")
    with pytest.raises(FileExistsError):
        generate(str(d), seed=1)
    assert (d / "x.txt").read_text(encoding="utf-8") == "원래 내용"


def test_answer_contains_required_cases(base_dataset):
    a = base_dataset["answer"]
    labels = {lb for f in a["files"] for lb in f["labels"]}
    for need in ["중첩백업", "버전가족", "최종본", "시리즈", "임시파일", "사본", "같은이름다른내용", "0바이트",
                 "읽기전용", "깨진파일", "암호흉내", "긴경로", "특수문자이름", "NFD이름", "제외대상",
                 "앞부분같은큰파일", "숨김", "서식"]:
        assert need in labels, need
    kinds = {i["kind"] for i in a["intended"]}
    assert kinds == {"a", "b", "c"}
    f1 = next(f for f in a["families"] if f["id"] == "F1")
    assert f1["final"] == ["E/정리중/계획/계획_최종2.hwpx", "E/정리중/계획/계획_최종2.pdf"]
    assert a["expected_flags"]["copy_by_date"], "만든>수정 복사본이 없음"
    assert all(f["dup_group"] is None for f in a["files"] if f["size"] == 0)


def test_hwpx_is_readable_zip(base_dataset):
    import zipfile
    p = os.path.join(base_dataset["data"], "E", "정리중", "계획", "계획_최종2.hwpx")
    with zipfile.ZipFile(p) as z:
        assert z.read("mimetype") == b"application/hwp+zip"
        sec = z.read("Contents/section0.xml").decode("utf-8")
        hpf = z.read("Contents/content.hpf").decode("utf-8")
    assert "시행 문서번호" in sec and "<hp:tbl" in sec
    assert 'name="lastsaveby"' in hpf


def test_version_family_contains_earlier_text(base_dataset):
    """후판이 전판 문장을 품는다 (2단계 판정기 시험용 정답이 설계대로인지)."""
    import zipfile
    import re
    d = os.path.join(base_dataset["data"], "E", "정리중", "계획")

    def text(name):
        with zipfile.ZipFile(os.path.join(d, name)) as z:
            return re.findall(r"<hp:t>(.*?)</hp:t>", z.read("Contents/section0.xml").decode())

    v3, v4 = text("계획_최종.hwpx"), text("계획_최종2.hwpx")
    assert set(v3) <= set(v4) and len(v4) > len(v3)


def test_answer_json_is_ascii_safe(base_dataset):
    with open(base_dataset["answer_path"], "rb") as f:
        raw = f.read()
    raw.decode("ascii")  # 인코딩 문제 없이 어디서나 읽히도록
    json.loads(raw)
