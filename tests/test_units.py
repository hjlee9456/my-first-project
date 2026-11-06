"""작은 부품 시험 — 제외 목록, 표지, 긴 경로 접두사."""
import pytest

from scanner.exclusions import Exclusions
from scanner.markers import copy_name_marker, is_copy_by_date, is_temp, split_ext
from scanner.winpath import from_fs, rel_parts, to_fs


def parts(p: str):
    return rel_parts(p, "C:\\")


@pytest.mark.parametrize("path,excluded", [
    ("C:\\Windows", True),
    ("C:\\windows", True),
    ("C:\\Program Files", True),
    ("C:\\Program Files (x86)", True),
    ("C:\\ProgramData", True),
    ("C:\\Users\\홍길동\\AppData", True),
    ("C:\\Users\\홍길동\\Documents", False),
    ("C:\\Users\\홍길동\\Documents\\AppData", False),
    ("C:\\$Recycle.Bin", True),
    ("D:\\자료\\$RECYCLE.BIN", True),
    ("C:\\System Volume Information", True),
    ("C:\\pagefile.sys", True),
    ("C:\\자료\\Windows", False),            # 깊은 곳의 Windows 이름 폴더는 검사
    ("C:\\Windows.old\\Users\\a\\Documents", False),
    ("C:\\Windows.old\\Windows", True),
])
def test_default_exclusions(path, excluded):
    ex = Exclusions.build([], [], True, None)
    assert (ex.match(path, parts(path)) is not None) == excluded


def test_user_patterns_and_abs_paths(tmp_path):
    ex = Exclusions.build([str(tmp_path / "빼기")], ["**/node_modules", "/옛날설치파일", "임시보관"], False, None)
    assert ex.match("C:\\a\\b\\node_modules", parts("C:\\a\\b\\node_modules"))
    assert ex.match("C:\\a\\임시보관", parts("C:\\a\\임시보관"))
    assert ex.match("C:\\옛날설치파일", parts("C:\\옛날설치파일"))
    assert not ex.match("C:\\a\\옛날설치파일", parts("C:\\a\\옛날설치파일"))
    p = str(tmp_path / "빼기")
    assert ex.match(p, []) == "제외 경로"
    assert not Exclusions.build([], [], False, None).match("C:\\Windows", parts("C:\\Windows"))


@pytest.mark.parametrize("name,marker", [
    ("계획_최종 - 복사본.hwpx", " - 복사본"),
    ("계획_최종 - 복사본 (2).hwpx", " - 복사본"),
    ("Report - Copy.docx", " - Copy"),
    ("Copy of 결과보고.docx", "Copy of"),
    ("Copy (2) of 결과보고.docx", "Copy of"),
    ("계획_최종 (1).hwpx", "(숫자)"),
    ("계획_최종(12).hwpx", "(숫자)"),
    ("계획(안).hwpx", None),
    ("계획_최종2.hwpx", None),
    ("2024 업무계획.hwpx", None),
    ("붙임(1).hwpx", "(숫자)"),  # 알려진 오탐 — 표지는 단서일 뿐
])
def test_copy_name_marker(name, marker):
    assert copy_name_marker(name) == marker


def test_temp_and_ext():
    assert is_temp("~$계획.hwpx") and is_temp("~WRL0001.tmp") and is_temp("작업.TMP")
    assert not is_temp("계획.hwpx") and not is_temp("~계획.hwpx")
    assert split_ext("보고서.HWPX") == ("보고서", ".hwpx")
    assert split_ext(".숨김") == (".숨김", "")
    assert split_ext("확장자없음") == ("확장자없음", "")


def test_copy_by_date():
    s = 1_000_000_000
    assert is_copy_by_date(100 * s, 50 * s)
    assert not is_copy_by_date(51 * s, 50 * s)  # 2초 이내는 같은 시각으로 봄
    assert not is_copy_by_date(None, 50 * s)
    assert not is_copy_by_date(10 * s, 50 * s)


def test_long_path_prefix():
    assert to_fs("C:\\a\\b", windows=True) == "\\\\?\\C:\\a\\b"
    assert to_fs("\\\\서버\\공유\\a", windows=True) == "\\\\?\\UNC\\서버\\공유\\a"
    assert to_fs("\\\\?\\C:\\a", windows=True) == "\\\\?\\C:\\a"
    assert to_fs("/a/b", windows=False) == "/a/b"
    assert from_fs("\\\\?\\C:\\a") == "C:\\a"
    assert from_fs("\\\\?\\UNC\\서버\\공유") == "\\\\서버\\공유"
