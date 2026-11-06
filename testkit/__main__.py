"""합성 정답셋 만들기.

    python -m testkit generate --out 정답셋 [--seed 42] [--scale 0]
"""
import argparse
import sys

from testkit.generator import generate


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m testkit", description="합성(가짜) 정답셋 생성기")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="정답셋 만들기")
    g.add_argument("--out", required=True, help="만들 폴더 (비어 있거나 없어야 함)")
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--scale", type=int, default=0, help="규모 시험용 묶음 수 (파일 ≈ 49 × 묶음 수)")
    args = p.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    info = generate(args.out, seed=args.seed, scale=args.scale)
    a = info["answer"]
    print(f"만들었습니다: {info['out']}")
    print(f"  파일 {a['counts']['files_total']:,}개 (검사 대상 {a['counts']['files_scanned']:,}개)")
    print(f"  완전중복 묶음 {len(a['exact_dup_groups']):,}개")
    if "folder_groups" in a:
        print(f"  폴더 묶음 {len(a['folder_groups'])}개 · 포함 관계 {len(a['folder_contains'])}쌍")
    for k, v in info["roots"].items():
        print(f"  드라이브 {k}: {v}")
    if a["problems"]:
        print(f"  주의: 만들지 못한 함정 {len(a['problems'])}개 — answer.json 의 problems 참고")
    return 0


if __name__ == "__main__":
    sys.exit(main())
