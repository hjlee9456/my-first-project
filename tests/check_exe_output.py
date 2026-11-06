"""CI 에서 exe 로 진단한 결과가 정답과 같은지 확인한다.

    python tests/check_exe_output.py <정답셋 폴더> <진단 출력 폴더>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers import answer_rel, group_signature, results  # noqa: E402


def main(set_dir: str, out_dir: str) -> int:
    with open(os.path.join(set_dir, "answer.json"), encoding="utf-8") as f:
        ans = json.load(f)
    info = {"data": os.path.join(set_dir, "data"), "answer": ans}
    r = results(info, os.path.join(out_dir, "scan.sqlite"))
    checks = {
        "완전중복": {frozenset(g) for g in r["dup"]} ==
                {frozenset(answer_rel(p) for p in g) for g in ans["exact_dup_groups"]},
        "폴더묶음": {group_signature(g) for g in r["groups"]} ==
                {group_signature(g) for g in ans["folder_groups"]},
        "포함관계": {(c["inner"], c["outer"]) for c in r["contains"]} ==
                {(c["inner"], c["outer"]) for c in ans["folder_contains"]},
        "복사본날짜표지": {p for p, v in r["files"].items() if v["cd"]} ==
                    {answer_rel(p) for p in ans["expected_flags"]["copy_by_date"]},
        "오류없음": r["errors"] == [],
    }
    for k, ok in checks.items():
        print(f"{'통과' if ok else '실패'}  {k}")
    for name in ("진단보고서.html", "진단상세.xlsx", "요약숫자.json"):
        ok = os.path.exists(os.path.join(out_dir, name))
        checks[name] = ok
        print(f"{'통과' if ok else '실패'}  {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
