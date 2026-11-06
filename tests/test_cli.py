"""명령줄 시험 — exe 와 같은 진입점으로 끝까지 돈다."""
import json
import os

from helpers import mocked_birthtimes
from scanner.cli import main


def test_no_args_shows_help(capsys):
    assert main([]) == 2
    assert "읽기 전용" in capsys.readouterr().out


def test_scan_and_report_commands(base_dataset, tmp_path, capsys):
    out = str(tmp_path / "out")
    args = ["scan", "--out", out, "--dest", base_dataset["roots"]["E"]]
    for k, v in sorted(base_dataset["roots"].items()):
        args += ["--sim-drive", f"{k}={v}"]
    with mocked_birthtimes(base_dataset):
        assert main(args) == 0
    text = capsys.readouterr().out
    assert "진단을 마쳤습니다" in text
    html = open(os.path.join(out, "진단보고서.html"), encoding="utf-8").read()
    assert "파일 진단 보고서" in html and "<script" not in html
    nums = json.load(open(os.path.join(out, "요약숫자.json"), encoding="utf-8"))
    assert nums["정리본용량"]["충분한가"] is True
    assert main(["report", "--out", out]) == 0


def test_refuses_foreign_output_folder(base_dataset, tmp_path, capsys):
    d = tmp_path / "남의폴더"
    d.mkdir()
    (d / "문서.txt").write_text("x", encoding="utf-8")
    code = main(["scan", "--out", str(d), "--sim-drive", f"D={base_dataset['roots']['D']}"])
    assert code == 3
    assert "출력 폴더 문제" in capsys.readouterr().err
