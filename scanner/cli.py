"""명령줄 사용법.

    filetidy-scan scan --root C:\\Users --root D:\\ --root E:\\ --out E:\\파일정리_진단 --dest E:\\
    filetidy-scan report --out E:\\파일정리_진단
"""
from __future__ import annotations

import argparse
import sys

from . import TOOL_NAME, __version__
from .exclusions import DEFAULT_EXCLUDES
from .output import OutputDirError
from .report import human_bytes

INTRO = f"""{TOOL_NAME} {__version__} — 업무 PC 파일 진단기 (읽기 전용)
검사 대상 파일은 읽기만 합니다. 옮기거나 지우거나 고치지 않습니다.
결과(DB·보고서)는 --out 으로 지정한 출력 폴더에만 씁니다."""


def _sim_drive(text: str) -> tuple[str, str]:
    if len(text) < 3 or text[1] != "=" or not text[0].isalpha():
        raise argparse.ArgumentTypeError("형식: 문자=경로  (예: C=D:\\시험\\드라이브C)")
    return text[0].upper(), text[2:]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=TOOL_NAME, description=INTRO,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"{TOOL_NAME} {__version__}")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("scan", help="진단 실행", formatter_class=argparse.RawDescriptionHelpFormatter,
                       description="폴더를 훑어 중복과 중첩 백업을 진단하고 보고서를 씁니다.\n\n"
                                   "기본 제외 목록:\n  " + "\n  ".join(DEFAULT_EXCLUDES))
    s.add_argument("--root", action="append", default=[], metavar="경로",
                   help="검사할 폴더 (여러 번 쓸 수 있음). 예: --root D:\\ --root E:\\")
    s.add_argument("--out", required=True, metavar="폴더",
                   help="결과를 쓸 새 폴더 (같은 폴더로 다시 실행하면 이어서 함)")
    s.add_argument("--dest", metavar="경로", help="정리본을 모을 드라이브 (남은 공간 비교용). 예: E:\\")
    s.add_argument("--exclude", action="append", default=[], metavar="경로",
                   help="추가로 뺄 폴더(절대 경로). 예: --exclude D:\\설치파일")
    s.add_argument("--exclude-pattern", action="append", default=[], metavar="패턴",
                   help="추가로 뺄 이름 패턴. 예: /옛날프로그램, **/node_modules, /Users/*/OneDrive")
    s.add_argument("--no-default-excludes", action="store_true", help="기본 제외 목록을 쓰지 않음")
    s.add_argument("--sim-drive", action="append", default=[], type=_sim_drive, metavar="문자=경로",
                   help="(시험용) 폴더 하나를 드라이브 맨 위처럼 다룸. 합성 정답셋 검사에 씀")

    r = sub.add_parser("report", help="마지막 진단 결과로 보고서만 다시 쓰기")
    r.add_argument("--out", required=True, metavar="폴더")
    r.add_argument("--dest", metavar="경로")
    return p


def _setup_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # cp949 콘솔에서 ✓·이모지 이름 때문에 멈추지 않게
        except (AttributeError, ValueError):
            pass


def _pause_if_double_clicked() -> None:
    if getattr(sys, "frozen", False) and sys.stdin and sys.stdin.isatty():
        try:
            input("\nEnter 를 누르면 창이 닫힙니다 …")
        except EOFError:
            pass


def main(argv: list[str] | None = None) -> int:
    _setup_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        print(INTRO + "\n")
        parser.print_help()
        _pause_if_double_clicked()
        return 2
    from .scan import rebuild_report, run_scan
    try:
        if args.cmd == "scan":
            if not args.root and not args.sim_drive:
                parser.error("--root 를 하나 이상 지정하세요.")
            print(INTRO + "\n")
            res = run_scan(args.root, args.out, excludes=args.exclude,
                           exclude_patterns=args.exclude_pattern, use_default_excludes=not args.no_default_excludes, dest=args.dest,
                           simulated=args.sim_drive)
            s = res.summary
            print("\n진단을 마쳤습니다.")
            print(f"  파일 {s['총파일']:,}개 · {human_bytes(s['총용량'])}")
            print(f"  완전중복 {s['완전중복']['묶음수']:,}묶음 · 회수 가능 {human_bytes(s['완전중복']['회수가능용량'])}")
            print(f"  중첩 백업 폴더 {s['중첩백업']['폴더쌍수']:,}쌍 · 오류 {s['오류합계']:,}건")
            print(f"  보고서: {res.out_dir}")
        else:
            rebuild_report(args.out, args.dest)
            print("보고서를 다시 썼습니다.")
    except OutputDirError as e:
        print(f"\n출력 폴더 문제: {e}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("\n중단했습니다. 같은 --out 폴더로 다시 실행하면 계산한 해시를 다시 써서 이어 합니다.",
              file=sys.stderr)
        return 130
    return 0
