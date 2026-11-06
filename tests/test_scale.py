"""규모 시험 (완료 기준 6) — 합성 파일 수만~수십만 개에서 걸린 시간을 잰다.

    FILETIDY_SCALE=2000 python -m pytest tests/test_scale.py -s     # 약 10만 개
    FILETIDY_SCALE=5000 python -m pytest tests/test_scale.py -s     # 약 25만 개
결과는 표준 출력과, FILETIDY_SCALE_REPORT 로 준 파일(JSON)에 남긴다. 사람이 docs/규모시험.md 에 옮겨 적는다.
"""
import json
import os
import platform
import time

import pytest

from helpers import scan_dataset


@pytest.mark.slow
def test_scale(tmp_path):
    from testkit.generator import generate
    n = int(os.environ["FILETIDY_SCALE"])
    t0 = time.monotonic()
    info = generate(str(tmp_path / "set"), seed=99, scale=n)
    gen_s = time.monotonic() - t0
    t1 = time.monotonic()
    res = scan_dataset(info, str(tmp_path / "out"))
    scan_s = time.monotonic() - t1
    t2 = time.monotonic()
    again = scan_dataset(info, str(tmp_path / "out"))
    rescan_s = time.monotonic() - t2
    ans = info["answer"]
    s = res.summary
    assert s["총파일"] == ans["counts"]["files_scanned"]
    assert s["완전중복"]["묶음수"] == len(ans["exact_dup_groups"])
    assert s["오류합계"] == 0
    assert again.stage_stats["해시"]["partial_done"] == 0  # 두 번째는 해시를 다시 씀
    rec = {
        "날짜": time.strftime("%Y-%m-%d"),
        "환경": f"{platform.system()} {platform.release()} · Python {platform.python_version()} · CPU {os.cpu_count()}",
        "묶음수": n,
        "파일수": s["총파일"],
        "용량": s["총용량"],
        "생성초": round(gen_s, 1),
        "진단초": round(scan_s, 1),
        "단계별초": {k: v.get("seconds") for k, v in res.stage_stats.items()},
        "다시진단초(이어하기)": round(rescan_s, 1),
        "완전중복묶음": s["완전중복"]["묶음수"],
        "폴더묶음": s["중첩백업"]["구조까지같은묶음(a)"] + s["중첩백업"]["배치만다른묶음(b)"],
        "포함쌍": s["중첩백업"]["포함관계쌍(c)"],
    }
    print("\n규모 시험 결과:", json.dumps(rec, ensure_ascii=False, indent=1))
    path = os.environ.get("FILETIDY_SCALE_REPORT")
    if path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
