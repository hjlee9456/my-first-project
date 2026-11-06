"""합성 정답셋 생성기 (인계서 8장).

가짜 '뒤죽박죽 업무 PC'를 만들고 정답 파일(answer.json)을 함께 쓴다.

    out/
      data/C/…  data/D/…  data/E/…   ← 가짜 드라이브 세 개 (진단기에는 --sim-drive 로 넘김)
      answer.json                    ← 파일마다 내용·묶음·라벨, 중복 묶음, 폴더 관계 정답
      meta_mock.json                 ← 리눅스용 '만든 날짜' 모의 값 (윈도우에서는 실제로 설정)

- 시드가 같으면 같은 결과(파일 이름·바이트·날짜·정답)가 나온다.
- 내용이 다른 파일은 문서 안에 고유 이름표(key)를 넣어 바이트가 우연히 같아지지 않게 한다.
- 이미 무언가 든 폴더에는 만들지 않는다(아무것도 지우거나 덮어쓰지 않는다).
"""
from __future__ import annotations

import calendar
import datetime as _dt
import json
import os
import random
import stat
import subprocess
import unicodedata
from dataclasses import dataclass, field

from . import formats as F
from . import winmeta
from .oracle import exact_dup_groups, folder_truth

IS_WINDOWS = os.name == "nt"
GENERATOR_VERSION = 1
MARKER_NAME = ".filetidy-output"
COPY_DATE_TOLERANCE_NS = 2_000_000_000


def ts(y: int, m: int, d: int, hh: int = 9, mm: int = 0, ss: int = 0) -> int:
    return calendar.timegm((y, m, d, hh, mm, ss)) * 1_000_000_000


def iso(ns: int) -> str:
    return _dt.datetime.fromtimestamp(ns / 1e9, tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── 가짜 문장 재료 ──────────────────────────────────────────────
SUBJECTS = ["도로정비공사", "복지센터 위탁운영", "공용차량 구매", "청사 냉난방기 교체", "공원조성사업",
            "스마트 가로등 설치", "하수관로 정비", "문화센터 리모델링", "전산장비 유지보수", "주민참여 예산 운영",
            "체육관 보수공사", "도서관 위탁운영", "재난안전 통신망 구축", "어린이집 환경개선", "농로 포장공사"]
METHODS = ["일반경쟁입찰", "제한경쟁입찰", "협상에 의한 계약", "수의계약", "적격심사"]
TEMPLATES = [
    "{s}의 사업 목적과 추진 경위를 검토하였다.",
    "{s} 설계내역서의 단가 적용이 적정한지 확인하였다.",
    "계약 방법은 관계 법령에 따라 {m}으로 하는 것이 타당하다.",
    "{s}의 총사업비는 {n:,}천원이며 예산 편성 내역과 일치한다.",
    "현장 여건을 고려하여 사업 기간을 {d}일로 조정할 필요가 있다.",
    "검토 결과 {k}건의 개선 의견을 제시한다.",
    "{s} 관련 과업지시서의 산출 근거를 보완하기 바란다.",
    "유사 사업과 비교하여 물량 산출이 과다하지 않은지 재확인하였다.",
    "안전관리비와 품질관리비가 기준에 맞게 계상되었는지 확인하였다.",
    "{s}의 하자담보 책임기간과 지체상금률이 적정하게 정해졌다.",
]


@dataclass
class Content:
    key: str
    data: bytes
    kind: str


@dataclass
class Item:
    rel: str
    content: Content
    mtime_ns: int
    birth_ns: int | None
    labels: list[str]
    readonly: bool = False
    hidden: bool = False
    excluded: str | None = None
    info: dict = field(default_factory=dict)


@dataclass
class TreeFile:
    rel: str
    content: Content
    mtime_ns: int
    readonly: bool = False


class Gen:
    def __init__(self, seed: int):
        self.seed = seed
        self.rng = random.Random(seed)
        self.items: list[Item] = []
        self.links: list[dict] = []
        self.families: list[dict] = []
        self.series: list[dict] = []
        self.intended: list[dict] = []
        self._n = 0

    # ── 내용 만들기 ──
    def key(self, tag: str) -> str:
        self._n += 1
        return f"합성-{self.seed}-{tag}-{self._n:06d}"

    def paragraphs(self, subject: str, n: int) -> list[str]:
        r = self.rng
        return [r.choice(TEMPLATES).format(s=subject, m=r.choice(METHODS), n=r.randrange(5_000, 900_000),
                                           d=r.randrange(30, 365), k=r.randrange(1, 9)) for _ in range(n)]

    def doc(self, ext: str, title: str, year: int, *, paragraphs: list[str] | None = None,
            table: list[list[str]] | None = None, modified_ns: int | None = None, revision: int | None = None,
            author: str = "감사담당", saved_by: str | None = None, encoding: str = "utf-8") -> Content:
        r = self.rng
        subject = r.choice(SUBJECTS)
        k = self.key(ext.strip("."))
        if paragraphs is None:
            paragraphs = self.paragraphs(subject, r.randrange(3, 7))
        if table is None and ext in (".hwpx", ".docx", ".xlsx"):
            table = [["구분", "내용", "금액(천원)"]] + [
                [f"{i}", r.choice(SUBJECTS), f"{r.randrange(1_000, 500_000):,}"] for i in range(1, r.randrange(3, 7))]
        mod = modified_ns or ts(year, r.randrange(1, 13), r.randrange(1, 28), r.randrange(8, 19))
        spec = F.DocSpec(key=k, title=title, paragraphs=paragraphs, table=table or [], author=author,
                         last_saved_by=saved_by or author, created=iso(mod - 86_400 * 10**9 * r.randrange(1, 20)),
                         modified=iso(mod), revision=revision or r.randrange(1, 12))
        data = F.txt(spec, encoding) if ext == ".txt" else F.BUILDERS[ext](spec)
        return Content(k, data, ext)

    def blob(self, tag: str, size: int, head: bytes = b"", prefix: bytes | None = None) -> Content:
        k = self.key(tag)
        body = head + (prefix or b"") + k.encode() + b"\n"
        rnd = random.Random(f"{self.seed}:{k}")
        body += bytes(rnd.getrandbits(8) for _ in range(max(0, size - len(body))))
        return Content(k, body, tag)

    def empty(self, ext: str) -> Content:
        return Content("empty", b"", ext)

    # ── 배치 ──
    def add(self, rel: str, content: Content, mtime_ns: int, birth_ns: int | None, labels: list[str],
            **kw) -> Item:
        # 만든 날짜를 비워 두면 윈도우에서는 '지금'이 찍혀 복사본처럼 보이므로, 항상 정해 준다.
        if birth_ns is None:
            birth_ns = self.original_birth(mtime_ns)
        it = Item(rel, content, mtime_ns, birth_ns, list(labels), **kw)
        self.items.append(it)
        return it

    def original_birth(self, mtime_ns: int) -> int:
        return mtime_ns - self.rng.randrange(1, 72) * 3_600 * 10**9

    def tree(self, year: int, specs: list[tuple[str, ...]]) -> list[TreeFile]:
        out = []
        for spec in specs:
            rel = spec[0]
            flags = spec[1] if len(spec) > 1 else ""
            name = rel.rsplit("/", 1)[-1]
            ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
            mt = ts(year, self.rng.randrange(1, 13), self.rng.randrange(1, 28), self.rng.randrange(8, 19))
            c = self.empty(ext) if "empty" in flags else self.doc(ext, name.rsplit(".", 1)[0], year,
                                                                   modified_ns=mt)
            out.append(TreeFile(rel, c, mt, readonly="ro" in flags))
        return out

    def place(self, tree: list[TreeFile], prefix: str, labels: list[str], *, copy_time: int | None = None,
              rename=None) -> list[Item]:
        out = []
        for i, tf in enumerate(tree):
            rel = rename(i, tf.rel) if rename else tf.rel
            if copy_time is None:
                birth = self.original_birth(tf.mtime_ns)
            else:
                birth = copy_time + self.rng.randrange(0, 600) * 10**9
            out.append(self.add(f"{prefix}/{rel}", tf.content, tf.mtime_ns, birth, labels, readonly=tf.readonly))
        return out


# ── 시나리오 ──────────────────────────────────────────────────
def build_base(g: Gen, posix_traps: bool) -> None:
    r = g.rng
    ME = "C/Users/감사담당"

    # 1) 원본 업무 폴더들
    T2025 = g.tree(2025, [("01 도로정비공사 일상감사 의견서.hwpx",), ("02 복지센터 위탁운영 일상감사 의견서.hwpx",),
                          ("03 공용차량 구매 검토.xlsx",), ("04 일상감사 결과 통보.docx",),
                          ("붙임/설계내역서.pdf",), ("붙임/현장사진 목록.txt",)])
    g.place(T2025, f"{ME}/Documents/2025 일상감사", ["업무문서"])
    T2026 = g.tree(2026, [("하수관로 정비 계약심사.hwpx",), ("체육관 보수공사 계약심사.hwpx",),
                          ("계약심사 처리부.xlsx",), ("원가계산 검토.pdf",), ("심사 메모.txt",)])
    g.place(T2026, f"{ME}/Documents/2026 계약심사", ["업무문서"])
    g.add(f"{ME}/Desktop/바탕화면 메모.txt", g.doc(".txt", "바탕화면 메모", 2026), ts(2026, 10, 2), None,
          ["업무문서"])

    # 2) 전임자 백업 (C 바탕화면) — 안에 전전임자 백업이 겹쳐 있음
    T2023 = g.tree(2023, [("일상감사/2023 일상감사 처리 현황.xlsx",), ("일상감사/공원조성 일상감사 의견서.hwpx",),
                          ("일상감사/가로등 설치 일상감사 의견서.hwpx",), ("계약심사/하수관로 정비 계약심사.hwpx",),
                          ("계약심사/계약심사 결과 통보.docx",), ("계약심사/원가계산서.pdf",),
                          ("2023 업무계획.hwpx",), ("메모(빈).txt", "empty"), ("참고 법령 목록.txt",)])
    T2024 = g.tree(2024, [("2024 업무계획.hwpx",), ("일상감사/문화센터 리모델링 의견서.hwpx",),
                          ("일상감사/전산장비 유지보수 의견서.hwpx",), ("계약심사/청사 냉난방기 교체 심사.xlsx",),
                          ("계약심사/심사결과 통보(결재).pdf", "ro"), ("업무 인계 메모.txt",)])
    handover = ts(2025, 1, 6, 17)
    BK = f"{ME}/Desktop/전임자백업"
    nested = [
        *[TreeFile(f"전전임자백업/2023업무/{t.rel}", t.content, t.mtime_ns, t.readonly) for t in T2023],
        TreeFile("전전임자백업/전전임자 인수인계.txt", g.doc(".txt", "전전임자 인수인계", 2023), ts(2023, 12, 28)),
        *[TreeFile(f"2024업무/{t.rel}", t.content, t.mtime_ns, t.readonly) for t in T2024],
        TreeFile("인수인계서.hwpx", g.doc(".hwpx", "인수인계서", 2024), ts(2024, 12, 30)),
    ]
    g.place(nested, BK, ["중첩백업"], copy_time=handover)
    g.intended.append({"kind": "a", "paths": [BK, "D/백업/전임자백업"], "note": "백업 통째 복제"})

    # 3) D: 백업의 백업, 옛날 자료, 원본 2022, 새 판 2024
    g.place(nested, "D/백업/전임자백업", ["중첩백업"], copy_time=ts(2025, 2, 10, 13))
    g.add("D/백업/백업 안내.txt", g.doc(".txt", "백업 안내", 2025), ts(2025, 2, 10), None, ["업무문서"])
    g.place(T2023, "D/옛날자료/2023업무", ["중첩백업"], copy_time=ts(2024, 3, 4, 10))
    g.add("D/옛날자료/2022 회의록 모음.hwpx", g.doc(".hwpx", "2022 회의록 모음", 2022), ts(2022, 12, 20), None,
          ["업무문서"])
    g.intended.append({"kind": "a", "paths": ["D/옛날자료/2023업무", f"{BK}/전전임자백업/2023업무"],
                       "note": "상위가 접힌 짝은 '참고'로"})

    T2022 = g.tree(2022, [("2022 업무계획.hwpx",), ("감사/주민참여 예산 감사.hwpx",), ("감사/감사결과 보고.docx",),
                          ("감사/조치결과.xlsx",), ("회의록/1분기 회의록.hwpx",), ("회의록/2분기 회의록.hwpx",)])
    g.place(T2022, "D/업무/2022업무", ["업무문서"])
    g.place(T2022, "E/자료정리/2022_재배치", ["중첩백업", "재배치"], copy_time=ts(2025, 5, 7, 15),
            rename=lambda i, rel: f"{i + 1:02d}_{rel.rsplit('/', 1)[-1]}")
    g.add("E/자료정리/자료정리 메모.txt", g.doc(".txt", "자료정리 메모", 2025), ts(2025, 5, 7), None, ["업무문서"])
    g.intended.append({"kind": "b", "paths": ["D/업무/2022업무", "E/자료정리/2022_재배치"], "note": "이름·배치만 다름"})

    g.place(T2024, "D/자료/2024업무_최신", ["중첩백업"], copy_time=ts(2025, 3, 2, 9))
    for nm in ("2024 추가 검토의견.hwpx", "2024 연말 정산표.xlsx", "2024 감사 일정.txt"):
        ext = "." + nm.rsplit(".", 1)[-1]
        g.add(f"D/자료/2024업무_최신/{nm}", g.doc(ext, nm.rsplit(".", 1)[0], 2024), ts(2024, 12, 20), None,
              ["업무문서", "후판추가"])

    g.place(T2024, "E/USB백업/2024/2024업무", ["중첩백업", "감싼폴더"], copy_time=ts(2025, 4, 1, 11))
    g.add("E/USB백업/USB 안내.txt", g.doc(".txt", "USB 안내", 2025), ts(2025, 4, 1), None, ["업무문서"])
    g.intended.append({"kind": "b", "paths": ["E/USB백업/2024", f"{BK}/2024업무"], "note": "폴더 하나로 감싼 사본"})
    g.intended.append({"kind": "c", "paths": ["E/USB백업/2024", "D/자료/2024업무_최신"], "note": "후판이 파일을 더 담음"})

    g.place(T2025, "E/정리중/2025 일상감사_보완", ["중첩백업"], copy_time=ts(2026, 2, 3, 10))
    for nm in ("05 보완 의견.hwpx", "보완 요청 공문.pdf"):
        ext = "." + nm.rsplit(".", 1)[-1]
        g.add(f"E/정리중/2025 일상감사_보완/{nm}", g.doc(ext, nm.rsplit(".", 1)[0], 2026), ts(2026, 2, 5), None,
              ["업무문서", "후판추가"])
    g.intended.append({"kind": "c", "paths": [f"{ME}/Documents/2025 일상감사", "E/정리중/2025 일상감사_보완"],
                       "note": "후판이 파일을 더 담음"})

    # 4) 버전 가족 F1 (HWPX) — 뒤 판이 앞 판 문장을 품고 더 많음, 내부 저장 시각이 늘어남
    base = g.paragraphs("공원조성사업", 8)
    edited = list(base)
    edited[1] = edited[1].replace("검토", "재검토") if "검토" in edited[1] else edited[1] + " (수정)"
    versions = [
        ("계획(안).hwpx", base[:3], ts(2025, 3, 2, 10), 3),
        ("계획_수정.hwpx", edited[:5], ts(2025, 3, 10, 15), 6),
        ("계획_최종.hwpx", edited[:7], ts(2025, 3, 15, 11), 9),
        ("계획_최종2.hwpx", edited[:8] + ["시행 문서번호 감사담당관-1234(2025.3.20.)"], ts(2025, 3, 20, 16), 12),
    ]
    fam = {"id": "F1", "kind": "버전가족", "members": [], "final": []}
    P = "E/정리중/계획"
    contents = {}
    plan_table = [["구분", "내용", "금액(천원)"], ["1", "기본설계", "120,000"], ["2", "실시설계", "340,000"]]
    for rank, (nm, paras, saved, rev) in enumerate(versions, 1):
        tbl = plan_table + ([["3", "감리", "55,000"]] if rank >= 3 else [])
        c = g.doc(".hwpx", "공원조성사업 추진계획", 2025, paragraphs=paras, table=tbl, modified_ns=saved,
                  revision=rev)
        contents[nm] = c
        mt = saved + 120 * 10**9
        if nm == "계획_수정.hwpx":
            mt = ts(2025, 4, 1, 9)  # 함정: 파일 수정 날짜가 가장 늦지만 내용은 중간 판
        is_final = nm == "계획_최종2.hwpx"
        g.add(f"{P}/{nm}", c, mt, g.original_birth(saved), ["버전가족", "최종본" if is_final else "이전판"],
              info={"family": "F1", "rank": rank, "internal_saved": iso(saved), "revision": rev})
        fam["members"].append({"path": f"{P}/{nm}", "rank": rank, "role": "최종본" if is_final else "이전판"})
        if is_final:
            fam["final"].append(f"{P}/{nm}")
    pdf_c = g.doc(".pdf", "공원조성사업 추진계획", 2025, paragraphs=versions[-1][1], modified_ns=ts(2025, 3, 21, 9))
    g.add(f"{P}/계획_최종2.pdf", pdf_c, ts(2025, 3, 21, 9), ts(2025, 3, 21, 9), ["버전가족", "최종본", "PDF판"],
          info={"family": "F1", "rank": 4})
    fam["members"].append({"path": f"{P}/계획_최종2.pdf", "rank": 4, "role": "최종본"})
    fam["final"].append(f"{P}/계획_최종2.pdf")
    final1 = contents["계획_최종.hwpx"]
    mt1 = versions[2][2] + 120 * 10**9
    g.add(f"{P}/계획_최종 (1).hwpx", final1, mt1, ts(2025, 6, 2, 14), ["버전가족", "사본", "복사본이름:(숫자)"],
          info={"family": "F1", "rank": 3})
    g.add(f"{P}/계획_최종 - 복사본.hwpx", final1, mt1, ts(2025, 6, 9, 10), ["버전가족", "사본", "복사본이름: - 복사본"],
          info={"family": "F1", "rank": 3})
    fam["members"] += [{"path": f"{P}/계획_최종 (1).hwpx", "rank": 3, "role": "사본"},
                       {"path": f"{P}/계획_최종 - 복사본.hwpx", "rank": 3, "role": "사본"}]
    owner = Content(g.key("owner"), b"\x0c" + "감사담당".encode("utf-16-le").ljust(160, b"\x00"), ".hwpx")
    g.add(f"{P}/~$계획_최종2.hwpx", owner, ts(2025, 3, 20, 16, 5), ts(2025, 3, 20, 16, 5), ["임시파일"])
    g.families.append(fam)

    # 버전 가족 F2 (DOCX)
    base2 = g.paragraphs("복지센터 위탁운영", 6)
    P2 = "E/정리중/결과보고"
    fam2 = {"id": "F2", "kind": "버전가족", "members": [], "final": []}
    v2 = [("결과보고_초안.docx", base2[:3], ts(2025, 8, 1, 10), 2),
          ("결과보고.docx", base2[:5], ts(2025, 8, 5, 14), 5),
          ("결과보고_확정.docx", base2 + ["결재: 과장 ○○○, 감사담당관 ○○○"], ts(2025, 8, 8, 9), 7)]
    c2 = {}
    report_table = [["항목", "결과"], ["위탁기관 평가", "적정"], ["정산 검토", "보완 필요"]]
    for rank, (nm, paras, saved, rev) in enumerate(v2, 1):
        c = g.doc(".docx", "복지센터 위탁운영 결과보고", 2025, paragraphs=paras, table=report_table,
                  modified_ns=saved, revision=rev)
        c2[nm] = c
        role = "최종본" if rank == 3 else "이전판"
        g.add(f"{P2}/{nm}", c, saved + 60 * 10**9, g.original_birth(saved), ["버전가족", role],
              info={"family": "F2", "rank": rank, "internal_saved": iso(saved), "revision": rev})
        fam2["members"].append({"path": f"{P2}/{nm}", "rank": rank, "role": role})
        if rank == 3:
            fam2["final"].append(f"{P2}/{nm}")
    g.add(f"{P2}/Copy of 결과보고_확정.docx", c2["결과보고_확정.docx"], v2[2][2] + 60 * 10**9, ts(2025, 9, 1, 9),
          ["버전가족", "사본", "복사본이름:Copy of"], info={"family": "F2", "rank": 3})
    g.add(f"{P2}/결과보고_초안 - Copy.docx", c2["결과보고_초안.docx"], v2[0][2] + 60 * 10**9, ts(2025, 9, 1, 9),
          ["버전가족", "사본", "복사본이름: - Copy"], info={"family": "F2", "rank": 1})
    fam2["members"] += [{"path": f"{P2}/Copy of 결과보고_확정.docx", "rank": 3, "role": "사본"},
                        {"path": f"{P2}/결과보고_초안 - Copy.docx", "rank": 1, "role": "사본"}]
    g.families.append(fam2)

    # 시리즈 (버전 아님) + 빈 서식
    head = [["연번", "집행부서", "사업명", "사업비(천원)", "처리결과"]]
    ser = {"id": "S1", "kind": "시리즈", "members": [], "note": "연도별 처리대장 — 버전 관계가 아님"}
    for y in (2024, 2025):
        rows = head + [[str(i), "○○과", r.choice(SUBJECTS), f"{r.randrange(10_000, 900_000):,}", "적정"]
                       for i in range(1, 6)]
        c = g.doc(".xlsx", f"{y}년 일상감사 처리대장", y, table=rows, modified_ns=ts(y, 12, 30, 17))
        p = f"E/정리중/대장/일상감사처리대장_{y}.xlsx"
        g.add(p, c, ts(y, 12, 30, 17), ts(y, 1, 3, 9), ["시리즈"], info={"series": "S1", "year": y})
        ser["members"].append(p)
    g.series.append(ser)
    blank = g.doc(".xlsx", "일상감사 처리대장 서식", 2024, table=head, modified_ns=ts(2024, 1, 3, 9))
    g.add("E/정리중/대장/일상감사처리대장_서식.xlsx", blank, ts(2024, 1, 3, 9), ts(2024, 1, 3, 9), ["서식"])

    # 5) 함정
    T = "E/함정"
    g.add("D/업무/보고서.hwpx", g.doc(".hwpx", "보고서", 2022), ts(2022, 7, 1), None, ["같은이름다른내용"])
    g.add("E/정리중/보고서.hwpx", g.doc(".hwpx", "보고서", 2025), ts(2025, 7, 1), None, ["같은이름다른내용"])
    g.add(f"{T}/빈파일.txt", g.empty(".txt"), ts(2021, 1, 4), None, ["0바이트"])
    g.add(f"{T}/빈문서.hwpx", g.empty(".hwpx"), ts(2021, 1, 4), None, ["0바이트"])
    g.add("D/업무/빈문서.hwpx", g.empty(".hwpx"), ts(2020, 5, 6), None, ["0바이트"])
    g.add(f"{T}/읽기전용_결재문서.pdf", g.doc(".pdf", "결재문서", 2024), ts(2024, 6, 3), None, ["읽기전용"],
          readonly=True)
    hidden_name = "숨김_설정.ini" if IS_WINDOWS else ".숨김_설정.ini"
    g.add(f"{T}/{hidden_name}", g.blob("ini", 300, b"[settings]\n"), ts(2023, 3, 3), None, ["숨김"], hidden=True)
    whole = g.doc(".hwpx", "깨진 문서", 2024).data
    g.add(f"{T}/깨진문서.hwpx", Content(g.key("broken"), whole[: int(len(whole) * 0.6)] + g.key("tail").encode(),
                                          ".hwpx"), ts(2024, 2, 2), None, ["깨진파일"])
    g.add(f"{T}/암호문서.hwpx", g.blob("drm", 4_000, b"SCDSA004\x00\x00"), ts(2025, 2, 2), None, ["암호흉내"])
    g.add(f"{T}/옛한글문서.hwp", g.blob("hwp5", 3_000, bytes.fromhex("D0CF11E0A1B11AE1")), ts(2019, 9, 9), None,
          ["깨진파일", "HWP5흉내"])
    prefix = bytes(random.Random(f"{g.seed}:prefix").getrandbits(8) for _ in range(64 * 1024))
    big_a = g.blob("bigA", 200 * 1024, prefix=prefix)
    big_b = g.blob("bigB", 200 * 1024, prefix=prefix)
    assert len(big_a.data) == len(big_b.data)
    g.add(f"{T}/큰파일_A.bin", big_a, ts(2024, 4, 4), None, ["앞부분같은큰파일"])
    g.add(f"{T}/큰파일_B.bin", big_b, ts(2024, 4, 4), None, ["앞부분같은큰파일"])
    g.add("D/업무/큰파일_A_사본.bin", big_a, ts(2024, 4, 4), ts(2024, 5, 5), ["완전중복"])
    sp = "감사 결과 [최종] (붙임#1) & 검토!.hwpx"
    spc = g.doc(".hwpx", "감사 결과 최종", 2025)
    g.add(f"{T}/특수문자/{sp}", spc, ts(2025, 1, 15), None, ["특수문자이름"])
    g.add(f"D/업무/특수 사본/{sp}", spc, ts(2025, 1, 15), ts(2025, 2, 1), ["특수문자이름"])
    for nm in ("특수 ㈜·「」『』％＆ 문서.txt", "체크✓_①②.txt", "이모지😀 메모.txt", "여러   공백   이름.txt"):
        g.add(f"{T}/특수문자/{nm}", g.doc(".txt", nm.rsplit(".", 1)[0], 2025), ts(2025, 1, 16), None,
              ["특수문자이름"])
    g.add(f"{T}/특수문자/점.으로.나뉜.이름.v2.hwpx", g.doc(".hwpx", "점으로 나뉜 이름", 2025), ts(2025, 1, 16), None,
          ["특수문자이름"])
    mac = g.doc(".txt", "맥에서 온 문서", 2023)
    g.add("D/업무/맥에서 온 문서.txt", mac, ts(2023, 8, 8), None, ["NFC이름"])
    g.add(f"{T}/{unicodedata.normalize('NFD', '맥에서 온 문서.txt')}", mac, ts(2023, 8, 8), ts(2023, 9, 1),
          ["NFD이름"])
    ref = g.doc(".txt", "참고자료", 2022, encoding="cp949")
    g.add("D/업무/참고자료.txt", ref, ts(2022, 2, 2), None, ["업무문서", "cp949내용"])
    seg = "가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허"
    deep = "/".join(f"{seg}_{i}" for i in range(1, 9))
    g.add(f"{T}/긴경로/{deep}/긴경로_문서.hwpx", g.doc(".hwpx", "긴 경로 문서", 2023), ts(2023, 6, 6), None,
          ["긴경로"])
    g.add(f"{T}/긴경로/{deep}/긴경로_사본.txt", ref, ts(2022, 2, 2), ts(2023, 6, 6), ["긴경로"])
    g.add("D/업무/~WRL0001.tmp", g.blob("wrl", 900), ts(2024, 9, 9), None, ["임시파일"])
    g.add(f"{T}/작업중.tmp", g.blob("tmp", 1_200), ts(2025, 9, 9), None, ["임시파일"])
    if posix_traps:
        cp949_name = os.fsdecode(b"cp949_" + "한글".encode("cp949") + b".txt")
        g.add(f"{T}/{cp949_name}", g.doc(".txt", "cp949 이름", 2021), ts(2021, 3, 3), None, ["cp949이름"])
    g.links.append({"path": f"{T}/고리", "target": "E", "note": "자기 드라이브 맨 위를 가리키는 고리"})

    # 6) 제외 대상 (검사에 나오면 안 됨)
    rec_src = T2025[0]
    ex = [
        ("C/Windows/System32/가짜시스템.dll", g.blob("dll", 2_000, b"MZ"), "/Windows"),
        ("C/Program Files/가짜프로그램/프로그램.exe", g.blob("exe", 2_000, b"MZ"), "/Program Files"),
        ("C/Program Files (x86)/옛프로그램/설정.ini", g.blob("ini86", 300), "/Program Files (x86)"),
        ("C/ProgramData/가짜회사/데이터.dat", g.blob("dat", 500), "/ProgramData"),
        (f"{ME}/AppData/Local/Temp/임시작업.tmp", g.blob("apptmp", 700), "/Users/*/AppData"),
        (f"{ME}/AppData/Roaming/HNC/자동저장.asv", g.blob("asv", 900), "/Users/*/AppData"),
        ("C/$Recycle.Bin/S-1-5-21-0000/$R0001.hwpx", rec_src.content, "**/$Recycle.Bin"),
        ("C/System Volume Information/가짜.dat", g.blob("svi", 400), "**/System Volume Information"),
        ("C/pagefile.sys", g.blob("pagefile", 4_096), "/pagefile.sys"),
        (f"E/파일정리_진단_예전/{MARKER_NAME}", Content(g.key("marker"), "예전 출력 폴더 표지\n".encode(), ""),
         "출력 폴더 표지"),
        ("E/파일정리_진단_예전/scan.sqlite", g.blob("oldsqlite", 2_048, b"SQLite format 3\x00"), "출력 폴더 표지"),
        ("E/파일정리_진단_예전/진단보고서.html", g.blob("oldhtml", 800, b"<!doctype html>"), "출력 폴더 표지"),
    ]
    for rel, c, why in ex:
        g.add(rel, c, ts(2024, 1, 1), None, ["제외대상"], excluded=why)


def build_scale(g: Gen, n: int) -> None:
    """규모 시험용 대량 파일. 파일 수 ≈ 49 × n."""
    r = g.rng
    for i in range(n):
        base = f"D/대량/묶음_{i:05d}"
        tree = []
        for sub in ("가", "나", "다", "라"):
            for j in range(10):
                k = g.key("s")
                data = (f"{k}\r\n" + " ".join(g.paragraphs(r.choice(SUBJECTS), 2)) + "\r\n").encode("utf-8")
                mt = ts(2019 + r.randrange(8), r.randrange(1, 13), r.randrange(1, 28))
                tree.append(TreeFile(f"{sub}/문서_{j:02d}.txt", Content(k, data, ".txt"), mt))
        g.place(tree, base, ["대량"])
        if i % 5 == 0:
            g.place(tree, f"E/대량백업/묶음_{i:05d}", ["대량", "중첩백업"], copy_time=ts(2025, 1, 1))
        if i % 7 == 0:
            g.place(tree[:10], f"E/대량재배치/묶음_{i:05d}", ["대량", "재배치"], copy_time=ts(2025, 6, 1),
                    rename=lambda idx, rel: f"{idx:02d}_{rel.replace('/', '_')}")


# ── 디스크에 쓰기 ────────────────────────────────────────────
def _write_items(g: Gen, data_dir: str) -> list[dict]:
    problems: list[dict] = []
    made_dirs: set[str] = set()
    for it in g.items:
        full = os.path.join(data_dir, *it.rel.split("/"))
        parent = os.path.dirname(full)
        if parent not in made_dirs:
            os.makedirs(winmeta.to_fs(parent), exist_ok=True)
            made_dirs.add(parent)
        fs = winmeta.to_fs(full)
        with open(fs, "xb") as f:  # x: 이미 있으면 실패 (덮어쓰지 않음)
            f.write(it.content.data)
        os.utime(fs, ns=(it.mtime_ns, it.mtime_ns))
        if IS_WINDOWS:
            if it.birth_ns is not None:
                winmeta.set_birthtime(full, it.birth_ns)
            if it.hidden:
                winmeta.set_hidden(full)
        if it.readonly:
            os.chmod(fs, stat.S_IREAD | (0 if IS_WINDOWS else stat.S_IRGRP | stat.S_IROTH))
    for ln in g.links:
        link = os.path.join(data_dir, *ln["path"].split("/"))
        target = os.path.join(data_dir, *ln["target"].split("/"))
        try:
            if IS_WINDOWS:
                subprocess.run(["cmd", "/c", "mklink", "/J", link, target], check=True,
                               capture_output=True)
            else:
                os.symlink(target, link, target_is_directory=True)
            ln["made"] = True
        except (OSError, subprocess.CalledProcessError) as e:
            ln["made"] = False
            problems.append({"path": ln["path"], "error": str(e)})
    return problems


def _answer(g: Gen, seed: int, scale: int, problems: list[dict], with_folders: bool) -> dict:
    scanned = [it for it in g.items if not it.excluded]
    flist = [{"path": it.rel, "content": it.content.key, "size": len(it.content.data)} for it in scanned]
    ans: dict = {
        "schema": 1,
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "scale": scale,
        "platform": "windows" if IS_WINDOWS else "posix",
        "roots": {"C": "C", "D": "D", "E": "E"},
        "counts": {"files_total": len(g.items), "files_scanned": len(scanned),
                   "bytes_scanned": sum(f["size"] for f in flist)},
        "links": g.links,
        "problems": problems,
        "exact_dup_groups": exact_dup_groups(flist),
        "zero_byte_files": sorted(f["path"] for f in flist if f["size"] == 0),
        "excluded": sorted(({"path": it.rel, "why": it.excluded} for it in g.items if it.excluded),
                           key=lambda e: e["path"]),
        "expected_flags": {
            "temp": sorted(it.rel for it in scanned if "임시파일" in it.labels),
            "copy_name": {it.rel: lb.split(":", 1)[1] for it in scanned for lb in it.labels
                          if lb.startswith("복사본이름:")},
            "copy_by_date": sorted(it.rel for it in scanned if it.birth_ns is not None
                                   and it.birth_ns > it.mtime_ns + COPY_DATE_TOLERANCE_NS),
            "readonly": sorted(it.rel for it in scanned if it.readonly),
            "hidden": sorted(it.rel for it in scanned if it.hidden),
        },
        "intended": g.intended,
        "families": g.families,
        "series": g.series,
        "notes": [
            "모든 내용은 합성(가짜)이다.",
            "버전 가족의 최종본 정답은 2단계 판정기 시험용이다.",
            "HWP 5.0(OLE) 표본은 깨진 흉내 파일뿐이다(실제 표본 확보 방법 미정).",
        ],
    }
    dup_group_of = {}
    for i, grp in enumerate(ans["exact_dup_groups"], 1):
        for p in grp:
            dup_group_of[p] = i
    if scale == 0:
        ans["files"] = [{
            "path": it.rel, "size": len(it.content.data), "content": it.content.key, "labels": it.labels,
            "dup_group": dup_group_of.get(it.rel), "excluded": it.excluded, "readonly": it.readonly,
            "hidden": it.hidden, "mtime_ns": it.mtime_ns, "birth_ns": it.birth_ns, "info": it.info,
        } for it in g.items]
    if with_folders:
        ans.update(folder_truth(flist))
    return ans


def generate(out_dir: str, seed: int = 42, scale: int = 0, with_folders: bool | None = None) -> dict:
    out_dir = os.path.abspath(out_dir)
    if os.path.exists(out_dir) and os.listdir(out_dir):
        raise FileExistsError(f"비어 있지 않은 폴더에는 만들지 않습니다: {out_dir}")
    g = Gen(seed)
    build_base(g, posix_traps=not IS_WINDOWS)
    if scale:
        build_scale(g, scale)
    data_dir = os.path.join(out_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    problems = _write_items(g, data_dir)
    if with_folders is None:
        with_folders = scale == 0
    ans = _answer(g, seed, scale, problems, with_folders)
    answer_path = os.path.join(out_dir, "answer.json")
    with open(answer_path, "x", encoding="utf-8") as f:
        json.dump(ans, f, ensure_ascii=True, indent=1)
    mock_path = os.path.join(out_dir, "meta_mock.json")
    with open(mock_path, "x", encoding="utf-8") as f:
        json.dump({"birth_ns": {it.rel: it.birth_ns for it in g.items if not it.excluded}}, f,
                  ensure_ascii=True)
    return {
        "out": out_dir, "data": data_dir, "answer_path": answer_path, "mock_path": mock_path,
        "roots": {k: os.path.join(data_dir, v) for k, v in ans["roots"].items()},
        "answer": ans,
    }
