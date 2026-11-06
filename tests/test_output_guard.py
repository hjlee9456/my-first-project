"""출력 폴더 지킴이 시험 — 진단기가 쓰는 유일한 곳(scanner/output.py)이 밖으로 새지 않는지."""
import os

import pytest

from scanner.output import MARKER_NAME, OutputDir, OutputDirError


def test_creates_new_folder_with_marker(tmp_path):
    out = OutputDir(str(tmp_path / "새출력"))
    assert os.path.isfile(os.path.join(out.path, MARKER_NAME))


def test_refuses_foreign_nonempty_folder(tmp_path):
    d = tmp_path / "남의폴더"
    d.mkdir()
    (d / "중요문서.hwpx").write_bytes(b"x")
    with pytest.raises(OutputDirError):
        OutputDir(str(d))
    assert (d / "중요문서.hwpx").read_bytes() == b"x"
    assert not (d / MARKER_NAME).exists()


def test_reuses_own_folder(tmp_path):
    a = OutputDir(str(tmp_path / "o"))
    a.put_text("a.txt", "1")
    b = OutputDir(str(tmp_path / "o"))
    b.put_text("a.txt", "2")
    assert (tmp_path / "o" / "a.txt").read_text(encoding="utf-8") == "2"


@pytest.mark.parametrize("name", ["../밖.txt", "하위/파일.txt", "..", ".", "", "C:x.txt", "..\\밖.txt",
                                  ".숨김"])
def test_refuses_names_leaving_folder(tmp_path, name):
    out = OutputDir(str(tmp_path / "o"))
    with pytest.raises(OutputDirError):
        out.put_text(name, "x")
    assert not (tmp_path / "밖.txt").exists()


def test_refuses_output_equal_or_above_root(tmp_path):
    root = tmp_path / "검사대상"
    root.mkdir()
    with pytest.raises(OutputDirError):
        OutputDir(str(root), [str(root)])
    with pytest.raises(OutputDirError):
        OutputDir(str(tmp_path), [str(root)])


def test_put_writes_only_inside(tmp_path):
    out = OutputDir(str(tmp_path / "o"))
    before = set(os.listdir(tmp_path))
    out.put_bytes("x.bin", b"123")
    out.put_xlsx("x.xlsx", lambda wb: wb.add_worksheet("a").write_string(0, 0, "=1+1"))
    con = out.connect_db("x.sqlite")
    con.execute("CREATE TABLE t(a)")
    con.commit()
    con.close()
    assert set(os.listdir(tmp_path)) == before
    names = set(os.listdir(tmp_path / "o"))
    assert {"x.bin", "x.xlsx", "x.sqlite", MARKER_NAME} <= names
    assert not any(n.endswith(".작성중") for n in names)


def test_formula_like_names_stay_text(tmp_path):
    """'=' 로 시작하는 파일 이름이 엑셀에서 수식으로 바뀌지 않는다."""
    import zipfile
    out = OutputDir(str(tmp_path / "o"))
    p = out.put_xlsx("f.xlsx", lambda wb: wb.add_worksheet("a").write_string(0, 0, "=HYPERLINK(\"x\")"))
    with zipfile.ZipFile(p) as z:
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
        shared = z.read("xl/sharedStrings.xml").decode()
    assert "<f>" not in sheet and "HYPERLINK" in shared
