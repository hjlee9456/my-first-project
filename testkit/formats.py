"""합성 문서 만들기 — HWPX·DOCX·XLSX·PDF·TXT.

모두 가짜 내용이다. 같은 입력이면 어느 운영체제에서든 같은 바이트가 나오도록
ZIP 은 압축 없이(STORED), 날짜는 1980-01-01 로 고정한다.
HWPX 는 한글 문서 구조(OWPML)를 흉내 낸 최소 구성이다. 한글에서 열리는지는 아직 확인하지 않았다.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

ZIP_DATE = (1980, 1, 1, 0, 0, 0)


@dataclass
class DocSpec:
    key: str                       # 내용마다 다른 이름표 — 바이트가 우연히 같아지지 않게 문서 안에 넣는다
    title: str
    paragraphs: list[str] = field(default_factory=list)
    table: list[list[str]] = field(default_factory=list)
    author: str = "감사담당"
    last_saved_by: str = "감사담당"
    created: str = "2025-01-02T09:00:00Z"
    modified: str = "2025-01-02T09:00:00Z"
    revision: int = 1


def _zip(entries: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for name, data in entries:
            zi = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            zi.compress_type = zipfile.ZIP_STORED
            zi.create_system = 0
            zi.external_attr = 0
            z.writestr(zi, data)
    return buf.getvalue()


def _x(s: str) -> str:
    return escape(s, {'"': "&quot;"})


# ── HWPX ──────────────────────────────────────────────────────
def hwpx(d: DocSpec) -> bytes:
    paras = "".join(
        f'<hp:p id="{i}" paraPrIDRef="0" styleIDRef="0"><hp:run charPrIDRef="0"><hp:t>{_x(t)}</hp:t></hp:run></hp:p>'
        for i, t in enumerate([d.title] + d.paragraphs))
    table = ""
    if d.table:
        rows = "".join(
            "<hp:tr>" + "".join(
                f'<hp:tc><hp:subList><hp:p><hp:run><hp:t>{_x(c)}</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
                for c in row) + "</hp:tr>" for row in d.table)
        table = (f'<hp:p><hp:run><hp:tbl rowCnt="{len(d.table)}" colCnt="{len(d.table[0])}">{rows}'
                 f'</hp:tbl></hp:run></hp:p>')
    section = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
               '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
               'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">' + paras + table + '</hs:sec>')
    hpf = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
           '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/" version="" unique-identifier="" id="">'
           '<opf:metadata>'
           f'<opf:title>{_x(d.title)}</opf:title><opf:language>ko</opf:language>'
           f'<opf:meta name="creator" content="text">{_x(d.author)}</opf:meta>'
           f'<opf:meta name="lastsaveby" content="text">{_x(d.last_saved_by)}</opf:meta>'
           f'<opf:meta name="CreatedDate" content="text">{d.created}</opf:meta>'
           f'<opf:meta name="ModifiedDate" content="text">{d.modified}</opf:meta>'
           f'<opf:meta name="synthetic-key" content="text">{_x(d.key)}</opf:meta>'
           '</opf:metadata><opf:manifest>'
           '<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
           '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
           '</opf:manifest><opf:spine><opf:itemref idref="header" linear="yes"/>'
           '<opf:itemref idref="section0" linear="yes"/></opf:spine></opf:package>')
    version = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
               '<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" '
               'tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="0" buildNumber="1" os="1" '
               'xmlVersion="1.4" application="Hancom Office Hangul" appVersion="11, 0, 0, 0"/>')
    container = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
                 '<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<ocf:rootfiles><ocf:rootfile full-path="Contents/content.hpf" '
                 'media-type="application/hwpml-package+xml"/></ocf:rootfiles></ocf:container>')
    header = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
              '<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" version="1.4" secCnt="1"/>')
    preview = "\r\n".join([d.title] + d.paragraphs + ["\t".join(r) for r in d.table])
    return _zip([
        ("mimetype", b"application/hwp+zip"),
        ("version.xml", version.encode()),
        ("META-INF/container.xml", container.encode()),
        ("META-INF/manifest.xml", b'<?xml version="1.0" encoding="UTF-8"?>'
                                  b'<odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>'),
        ("Contents/content.hpf", hpf.encode()),
        ("Contents/header.xml", header.encode()),
        ("Contents/section0.xml", section.encode()),
        ("Preview/PrvText.txt", preview.encode("utf-8")),
    ])


# ── OOXML 공통 ────────────────────────────────────────────────
def _core(d: DocSpec) -> bytes:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{_x(d.title)}</dc:title><dc:creator>{_x(d.author)}</dc:creator>'
            f'<cp:lastModifiedBy>{_x(d.last_saved_by)}</cp:lastModifiedBy><cp:revision>{d.revision}</cp:revision>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{d.created}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{d.modified}</dcterms:modified>'
            f'<dc:description>{_x(d.key)}</dc:description></cp:coreProperties>').encode()


_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CORE_REL = "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"
_DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"


def docx(d: DocSpec) -> bytes:
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{_x(t)}</w:t></w:r></w:p>'
                   for t in [d.title] + d.paragraphs)
    if d.table:
        body += "<w:tbl>" + "".join(
            "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{_x(c)}</w:t></w:r></w:p></w:tc>" for c in row) + "</w:tr>"
            for row in d.table) + "</w:tbl>"
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f'<w:body>{body}</w:body></w:document>')
    ctypes_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                  '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                  '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                  '<Default Extension="xml" ContentType="application/xml"/>'
                  '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
                  'officedocument.wordprocessingml.document.main+xml"/>'
                  '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-'
                  'package.core-properties+xml"/></Types>')
    rels = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{_RELS_NS}">'
            f'<Relationship Id="rId1" Type="{_DOC_REL}" Target="word/document.xml"/>'
            f'<Relationship Id="rId2" Type="{_CORE_REL}" Target="docProps/core.xml"/></Relationships>')
    return _zip([("[Content_Types].xml", ctypes_xml.encode()), ("_rels/.rels", rels.encode()),
                 ("word/document.xml", document.encode()), ("docProps/core.xml", _core(d))])


def _col(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def xlsx(d: DocSpec) -> bytes:
    rows = [[d.title]] + d.table
    sheet_rows = "".join(
        f'<row r="{r}">' + "".join(
            f'<c r="{_col(c)}{r}" t="inlineStr"><is><t>{_x(v)}</t></is></c>' for c, v in enumerate(row)) + "</row>"
        for r, row in enumerate(rows, 1))
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             f'<sheetData>{sheet_rows}</sheetData></worksheet>')
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
    wb_rels = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{_RELS_NS}">'
               '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
               'relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
    ctypes_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                  '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                  '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                  '<Default Extension="xml" ContentType="application/xml"/>'
                  '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
                  'officedocument.spreadsheetml.sheet.main+xml"/>'
                  '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-'
                  'officedocument.spreadsheetml.worksheet+xml"/>'
                  '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-'
                  'package.core-properties+xml"/></Types>')
    rels = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{_RELS_NS}">'
            f'<Relationship Id="rId1" Type="{_DOC_REL}" Target="xl/workbook.xml"/>'
            f'<Relationship Id="rId2" Type="{_CORE_REL}" Target="docProps/core.xml"/></Relationships>')
    return _zip([("[Content_Types].xml", ctypes_xml.encode()), ("_rels/.rels", rels.encode()),
                 ("xl/workbook.xml", workbook.encode()), ("xl/_rels/workbook.xml.rels", wb_rels.encode()),
                 ("xl/worksheets/sheet1.xml", sheet.encode()), ("docProps/core.xml", _core(d))])


# ── PDF ───────────────────────────────────────────────────────
def _pdf_text(s: str) -> str:
    """PDF 정보 사전용 UTF-16BE 16진 문자열."""
    return "<FEFF" + s.encode("utf-16-be").hex().upper() + ">"


def pdf(d: DocSpec) -> bytes:
    """최소 PDF. 본문 글자는 ASCII 표지만, 한글 내용은 정보 사전(Title·Subject)에 넣는다."""
    stream = f"BT /F1 11 Tf 72 760 Td (synthetic {d.key.encode('utf-8').hex()}) Tj ET".encode("ascii")
    body = "\n".join([d.title] + d.paragraphs)
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> "
        b"/Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        (f"<< /Title {_pdf_text(d.title)} /Subject {_pdf_text(body)} /Author {_pdf_text(d.author)} "
         f"/Keywords {_pdf_text(d.key)} /CreationDate (D:{d.created[:4]}{d.created[5:7]}{d.created[8:10]}) >>"
         ).encode("ascii"),
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + o + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info 6 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def txt(d: DocSpec, encoding: str = "utf-8") -> bytes:
    text = "\r\n".join([d.title] + d.paragraphs + [f"[{d.key}]"]) + "\r\n"
    return text.encode(encoding, "replace")


BUILDERS = {".hwpx": hwpx, ".docx": docx, ".xlsx": xlsx, ".pdf": pdf, ".txt": txt}
