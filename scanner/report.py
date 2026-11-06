"""5. 진단 보고서 — HTML 1장, 엑셀 상세, 요약 숫자(JSON, 경로 없음).

보고서는 모두 출력 폴더에만 쓴다(OutputDir 를 거침).
"""
from __future__ import annotations

import datetime as _dt
import html
import json

from . import TOOL_NAME, __version__
from . import platform_info as pinfo

EXCEL_MAX_ROWS = 1_048_000


# ── 숫자 꾸미기 ────────────────────────────────────────────────
def human_bytes(n: int | None) -> str:
    if n is None:
        return "-"
    v = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(v) < 1024 or unit == "TB":
            return f"{v:,.0f} {unit}" if unit == "B" else f"{v:,.1f} {unit}"
        v /= 1024
    return f"{n} B"


def num(n) -> str:
    return f"{int(n or 0):,}"


# ── 요약 모으기 ────────────────────────────────────────────────
def collect_summary(con, run_id: int, dest: str | None = None) -> dict:
    q = lambda sql, *a: con.execute(sql, a).fetchall()  # noqa: E731
    one = lambda sql, *a: con.execute(sql, a).fetchone()  # noqa: E731
    run = one("SELECT started_at, finished_at, tool_version, options_json, stats_json FROM runs WHERE run_id=?",
              run_id)
    s: dict = {
        "도구": f"{TOOL_NAME} {__version__}",
        "실행번호": run_id,
        "시작": run[0] if run else None,
        "끝": run[1] if run else None,
        "작성": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    opts = json.loads(run[3]) if run and run[3] else {}
    s["옵션"] = opts
    s["단계통계"] = json.loads(run[4]) if run and run[4] else {}

    vols = []
    for vid, serial, letter, label, fs, total, free, nf, nb in q(
            """SELECT v.volume_id, v.serial, v.last_letter, v.label, v.fs_type, v.total_bytes, v.free_bytes,
                      COUNT(f.file_id), COALESCE(SUM(f.size),0)
               FROM volumes v LEFT JOIN files f ON f.volume_id=v.volume_id AND f.seen_run=?
               WHERE v.seen_run=? GROUP BY v.volume_id ORDER BY v.last_letter, v.serial""", run_id, run_id):
        roots = [r[0] for r in q("SELECT path FROM roots WHERE volume_id=? AND seen_run=? ORDER BY path",
                                 vid, run_id)]
        vols.append({"volume_id": vid, "일련번호": serial, "문자": letter, "이름": label, "형식": fs,
                     "전체": total, "남음": free, "파일수": nf, "용량": nb, "검사시작점": roots})
    s["드라이브"] = vols
    tf, tb = one("SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE seen_run=?", run_id)
    s["총파일"], s["총용량"] = tf, tb
    s["폴더수"] = one("SELECT COUNT(*) FROM dirs WHERE seen_run=?", run_id)[0]

    g = one("SELECT COUNT(*), COALESCE(SUM(member_count),0), COALESCE(SUM(member_count-1),0),"
            " COALESCE(SUM(reclaimable),0) FROM dup_groups WHERE run_id=?", run_id)
    s["완전중복"] = {"묶음수": g[0], "묶음속파일수": g[1], "남는사본수": g[2], "회수가능용량": g[3]}
    zb = one("SELECT COUNT(*) FROM files WHERE seen_run=? AND size=0", run_id)[0]
    s["0바이트파일"] = zb

    fg = q("SELECT level, COUNT(*), COALESCE(SUM(member_count-1),0) FROM folder_groups WHERE run_id=? "
           "GROUP BY level", run_id)
    fga = {lv: (c, p) for lv, c, p in fg}
    cp = one("SELECT COUNT(*), COUNT(DISTINCT inner_dir_id) FROM folder_contains WHERE run_id=?", run_id)
    st_f = s["단계통계"].get("폴더", {})
    s["중첩백업"] = {
        "구조까지같은묶음(a)": fga.get("a", (0, 0))[0],
        "배치만다른묶음(b)": fga.get("b", (0, 0))[0],
        "포함관계쌍(c)": cp[0],
        "포함되는폴더수": cp[1],
        "폴더쌍수": fga.get("a", (0, 0))[1] + fga.get("b", (0, 0))[1] + cp[0],
        "겹치는폴더용량": st_f.get("redundant_bytes"),
    }

    # 큰 중복 폴더 상위 20
    top = []
    for no, level, nfile, nbyte in q("SELECT group_no, level, file_count, total_bytes FROM folder_groups "
                                     "WHERE run_id=? ORDER BY total_bytes DESC, group_no LIMIT 20", run_id):
        mem = q("""SELECT d.path, m.a_class, m.role FROM folder_members m JOIN dirs d ON d.dir_id=m.dir_id
                   WHERE m.run_id=? AND m.group_no=? ORDER BY d.path""", run_id, no)
        top.append({"종류": "같은 내용(a)" if level == "a" else "같은 내용(b)", "번호": no,
                    "용량": nbyte, "파일수": nfile,
                    "폴더": [{"경로": p, "구조": c, "역할": r} for p, c, r in mem]})
    for ip, op, inf, inb, onf, onb in q(
            """SELECT di.path, dx.path, c.inner_files, c.inner_bytes, c.outer_files, c.outer_bytes
               FROM folder_contains c JOIN dirs di ON di.dir_id=c.inner_dir_id
               JOIN dirs dx ON dx.dir_id=c.outer_dir_id WHERE c.run_id=?
               ORDER BY c.inner_bytes DESC LIMIT 20""", run_id):
        top.append({"종류": "포함(c)", "번호": None, "용량": inb, "파일수": inf,
                    "폴더": [{"경로": ip, "구조": None, "역할": "안쪽"},
                           {"경로": op, "구조": None, "역할": f"바깥(파일 {onf:,}개)"}]})
    top.sort(key=lambda r: -r["용량"])
    s["큰중복폴더"] = top[:20]

    s["확장자"] = [{"확장자": e or "(없음)", "파일수": c, "용량": b} for e, c, b in q(
        "SELECT ext, COUNT(*), COALESCE(SUM(size),0) FROM files WHERE seen_run=? GROUP BY ext "
        "ORDER BY SUM(size) DESC, COUNT(*) DESC", run_id)]
    s["연도"] = [{"연도": y, "파일수": c, "용량": b} for y, c, b in q(
        "SELECT strftime('%Y', mtime_ns/1000000000, 'unixepoch', 'localtime') y, COUNT(*), "
        "COALESCE(SUM(size),0) FROM files WHERE seen_run=? GROUP BY y ORDER BY y", run_id)]
    s["표지"] = {
        "복사본_날짜(만든>수정)": one("SELECT COUNT(*) FROM files WHERE seen_run=? AND copy_by_date=1", run_id)[0],
        "복사본_이름": {k: c for k, c in q("SELECT copy_name, COUNT(*) FROM files WHERE seen_run=? AND "
                                         "copy_name IS NOT NULL GROUP BY copy_name ORDER BY copy_name", run_id)},
        "임시파일": one("SELECT COUNT(*) FROM files WHERE seen_run=? AND is_temp=1", run_id)[0],
        "읽기전용": one("SELECT COUNT(*) FROM files WHERE seen_run=? AND readonly=1", run_id)[0],
        "숨김": one("SELECT COUNT(*) FROM files WHERE seen_run=? AND hidden=1", run_id)[0],
        "이름글자문제": one("SELECT COUNT(*) FROM files WHERE seen_run=? AND name_issue=1", run_id)[0],
        "내용없는자리표시자": one("SELECT COUNT(*) FROM files WHERE seen_run=? AND status='placeholder'",
                          run_id)[0],
        "만든날짜모름": one("SELECT COUNT(*) FROM files WHERE seen_run=? AND birth_ns IS NULL", run_id)[0],
    }
    s["오류"] = [{"단계": a, "종류": b, "건수": c} for a, b, c in q(
        "SELECT stage, kind, COUNT(*) FROM errors WHERE run_id=? GROUP BY stage, kind ORDER BY COUNT(*) DESC",
        run_id)]
    s["오류합계"] = sum(e["건수"] for e in s["오류"])
    s["건너뜀"] = [{"사유": a, "건수": c} for a, c in q(
        "SELECT reason, COUNT(*) FROM skipped WHERE run_id=? GROUP BY reason ORDER BY COUNT(*) DESC", run_id)]

    # 정리본 용량 추정 — 같은 내용은 하나만 모은다고 할 때
    dest_info: dict = {"대상": dest}
    dest_vid = None
    if dest:
        try:
            vi = pinfo.volume_info(dest)
            row = one("SELECT volume_id FROM volumes WHERE serial=?", vi.serial)
            dest_vid = row[0] if row else None
            dest_info["대상일련번호"] = vi.serial
        except OSError as e:
            dest_info["오류"] = str(e)
        sp = pinfo.space(dest)
        dest_info["남은공간"] = sp[1] if sp else None
    single_all, single_copy = one(
        """SELECT COALESCE(SUM(size),0), COALESCE(SUM(CASE WHEN volume_id IS ? THEN 0 ELSE size END),0)
           FROM files WHERE seen_run=? AND file_id NOT IN (SELECT file_id FROM dup_members WHERE run_id=?)""",
        dest_vid, run_id, run_id)
    grp_all = grp_copy = 0
    for _, size, on_dest in q(
            """SELECT g.group_no, g.size, MAX(CASE WHEN f.volume_id IS ? THEN 1 ELSE 0 END)
               FROM dup_groups g JOIN dup_members m ON m.run_id=g.run_id AND m.group_no=g.group_no
               JOIN files f ON f.file_id=m.file_id WHERE g.run_id=? GROUP BY g.group_no""", dest_vid, run_id):
        grp_all += size
        if not on_dest:
            grp_copy += size
    dest_info["고유내용용량"] = single_all + grp_all
    dest_info["대상드라이브로복사할용량"] = single_copy + grp_copy if dest else None
    need = dest_info["대상드라이브로복사할용량"]
    if need is not None and dest_info.get("남은공간") is not None:
        dest_info["여유분포함필요량"] = int(need * 1.1)
        dest_info["충분한가"] = dest_info["남은공간"] >= int(need * 1.1)
    s["정리본용량"] = dest_info
    return s


def numbers_only(s: dict) -> dict:
    """경로·이름·일련번호를 뺀 요약 숫자 (개발자에게 전할 때 쓰는 용도)."""
    out = {k: s[k] for k in ("도구", "총파일", "총용량", "폴더수", "완전중복", "0바이트파일", "표지",
                             "오류합계", "오류", "건너뜀", "연도") if k in s}
    out["중첩백업"] = {k: v for k, v in s["중첩백업"].items()}
    out["드라이브"] = [{"문자": v["문자"], "형식": v["형식"], "전체": v["전체"], "남음": v["남음"],
                     "파일수": v["파일수"], "용량": v["용량"]} for v in s["드라이브"]]
    out["확장자_상위30"] = s["확장자"][:30]
    d = s["정리본용량"]
    out["정리본용량"] = {k: d.get(k) for k in ("고유내용용량", "대상드라이브로복사할용량", "남은공간",
                                           "여유분포함필요량", "충분한가")}
    out["단계시간초"] = {k: v.get("seconds") for k, v in s.get("단계통계", {}).items() if isinstance(v, dict)}
    return out


# ── HTML ──────────────────────────────────────────────────────
_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--sub:#5b6474;--line:#e3e6eb;--accent:#2f6fde;--warn:#c2410c;--ok:#15803d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "Malgun Gothic","맑은 고딕","Apple SD Gothic Neo",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:26px;margin:0 0 4px}
h2{font-size:19px;margin:36px 0 10px;padding-bottom:6px;border-bottom:2px solid var(--line)}
.sub{color:var(--sub);font-size:13px}
.notice{background:#eef4ff;border:1px solid #c9dafc;border-radius:8px;padding:10px 14px;margin:14px 0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-top:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.card .k{color:var(--sub);font-size:13px}.card .v{font-size:22px;font-weight:700;margin-top:2px}
.card .d{color:var(--sub);font-size:12px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;
  overflow:hidden;font-size:14px}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#f0f2f5;font-weight:600;white-space:nowrap}
td.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.path{font-family:Consolas,"D2Coding",monospace;font-size:12.5px;word-break:break-all}
.bar{height:10px;background:var(--accent);border-radius:5px;min-width:2px}
.tag{display:inline-block;padding:0 6px;border-radius:4px;font-size:12px;background:#eef1f5;color:var(--sub)}
.tag.ref{background:#fff4e5;color:var(--warn)}
.nw{white-space:nowrap}
.warn{color:var(--warn);font-weight:600}.ok{color:var(--ok);font-weight:600}
.wrap{overflow-x:auto}
dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:0}
dt{color:var(--sub)}dd{margin:0}
@media print{body{background:#fff}.card,table{break-inside:avoid}}
"""


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _table(headers: list[str], rows: list[list[str]], numeric: set[int] = frozenset()) -> str:
    th = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = []
    for r in rows:
        tds = "".join(f'<td class="n">{c}</td>' if i in numeric else f"<td>{c}</td>" for i, c in enumerate(r))
        body.append(f"<tr>{tds}</tr>")
    if not rows:
        body.append(f'<tr><td colspan="{len(headers)}" class="sub">없음</td></tr>')
    return f'<div class="wrap"><table><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _bar_rows(items: list[tuple[str, int, int]], key_index: int) -> list[list[str]]:
    mx = max((it[key_index] for it in items), default=0) or 1
    rows = []
    for label, cnt, size in items:
        w = 100 * (size if key_index == 2 else cnt) / mx
        rows.append([_e(label), num(cnt), human_bytes(size), f'<div class="bar" style="width:{w:.1f}%"></div>'])
    return rows


def render_html(s: dict) -> str:
    dup = s["완전중복"]
    nb = s["중첩백업"]
    dest = s["정리본용량"]
    cards = [
        ("검사한 파일", num(s["총파일"]) + "개", human_bytes(s["총용량"])),
        ("완전 중복", f'{num(dup["묶음수"])}묶음', f'남는 사본 {num(dup["남는사본수"])}개'),
        ("회수 가능 용량", human_bytes(dup["회수가능용량"]), "같은 내용 사본을 하나만 남길 때"),
        ("중첩 백업 폴더", f'{num(nb["폴더쌍수"])}쌍',
         f'같은 내용 {num(nb["구조까지같은묶음(a)"] + nb["배치만다른묶음(b)"])}묶음 · 포함 {num(nb["포함관계쌍(c)"])}쌍'),
        ("오류", f'{num(s["오류합계"])}건', "접근 거부 등 — 건너뛰고 계속함"),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="k">{_e(k)}</div><div class="v">{_e(v)}</div><div class="d">{_e(d)}</div></div>'
        for k, v, d in cards)

    vol_rows = []
    for v in s["드라이브"]:
        vol_rows.append([_e(v["문자"] or "-"), f'<span class="path">{_e(v["일련번호"])}</span>',
                         _e(v["형식"] or "-"), num(v["파일수"]), human_bytes(v["용량"]),
                         human_bytes(v["전체"]), human_bytes(v["남음"]),
                         "<br>".join(f'<span class="path">{_e(r)}</span>' for r in v["검사시작점"])])

    top_rows = []
    for i, t in enumerate(s["큰중복폴더"], 1):
        lines = []
        for f in t["폴더"]:
            tag = ""
            if f["역할"] == "참고":
                tag = ' <span class="tag ref">참고: 상위 폴더가 이미 중복</span>'
            elif f["구조"] is not None:
                tag = f' <span class="tag">구조 {f["구조"]}</span>'
            elif f["역할"]:
                tag = f' <span class="tag">{_e(f["역할"])}</span>'
            lines.append(f'<span class="path">{_e(f["경로"])}</span>{tag}')
        top_rows.append([str(i), f'<span class="nw">{_e(t["종류"])}</span>', human_bytes(t["용량"]),
                         num(t["파일수"]), "<br>".join(lines)])

    ext_items = [(e["확장자"], e["파일수"], e["용량"]) for e in s["확장자"][:20]]
    year_items = [(y["연도"] or "-", y["파일수"], y["용량"]) for y in s["연도"]]
    mk = s["표지"]
    mark_rows = [["복사본 표지 — 만든 날짜가 수정한 날짜보다 늦음", num(mk["복사본_날짜(만든>수정)"])]]
    for k, c in mk["복사본_이름"].items():
        mark_rows.append([f"복사본 표지 — 이름 '{_e(k)}'", num(c)])
    mark_rows += [["임시파일 (~$, .tmp)", num(mk["임시파일"])], ["0바이트 파일", num(s["0바이트파일"])],
                  ["읽기 전용", num(mk["읽기전용"])], ["숨김", num(mk["숨김"])],
                  ["이름 글자 문제(깨진 유니코드·cp949 등)", num(mk["이름글자문제"])],
                  ["내용이 이 PC에 없는 자리표시자(클라우드 등)", num(mk["내용없는자리표시자"])],
                  ["만든 날짜를 알 수 없음", num(mk["만든날짜모름"])]]
    err_rows = [[_e(e["단계"]), _e(e["종류"]), num(e["건수"])] for e in s["오류"]]
    skip_rows = [[_e(k["사유"]), num(k["건수"])] for k in s["건너뜀"]]

    if dest.get("대상"):
        if dest.get("충분한가") is None:
            verdict = '<span class="sub">남은 공간을 알 수 없음</span>'
        elif dest["충분한가"]:
            verdict = '<span class="ok">충분함</span>'
        else:
            verdict = '<span class="warn">부족함</span>'
        dest_html = f"""<dl>
<dt>정리본 대상</dt><dd class="path">{_e(dest["대상"])}</dd>
<dt>같은 내용을 하나씩만 남긴 전체 용량</dt><dd>{human_bytes(dest["고유내용용량"])}</dd>
<dt>그중 대상 드라이브로 복사해야 할 용량</dt><dd>{human_bytes(dest.get("대상드라이브로복사할용량"))}
  <span class="sub">(이미 대상 드라이브에 사본이 있는 내용은 같은 드라이브 안 이동이라 공간이 들지 않음)</span></dd>
<dt>여유분 10% 포함</dt><dd>{human_bytes(dest.get("여유분포함필요량"))}</dd>
<dt>대상 드라이브 남은 공간</dt><dd>{human_bytes(dest.get("남은공간"))} — {verdict}</dd>
</dl>"""
    else:
        dest_html = f"""<dl><dt>같은 내용을 하나씩만 남긴 전체 용량</dt><dd>{human_bytes(dest["고유내용용량"])}</dd></dl>
<p class="sub">정리본 대상 드라이브를 지정하지 않았습니다(--dest). 지정하면 남은 공간과 비교합니다.</p>"""

    opts = s.get("옵션", {})
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>파일 진단 보고서</title><style>{_CSS}</style></head>
<body><main>
<h1>파일 진단 보고서</h1>
<div class="sub">작성 {_e(s["작성"])} · 실행 {_e(s["시작"])} ~ {_e(s["끝"])} · {_e(s["도구"])} · 실행번호 {s["실행번호"]}</div>
<div class="notice"><b>읽기 전용 진단입니다.</b> 이 프로그램은 파일을 옮기거나 지우거나 고치지 않았습니다.
아래 숫자는 정리 계획을 세우기 위한 참고 자료이며, 무엇을 남길지는 사람이 검토해 정합니다.</div>
<div class="cards">{cards_html}</div>

<h2>드라이브별</h2>
{_table(["문자", "볼륨 일련번호", "형식", "파일 수", "검사한 용량", "드라이브 전체", "남은 공간", "검사 시작점"],
        vol_rows, {3, 4, 5, 6})}
<p class="sub">드라이브는 문자(C·D·E)가 아니라 볼륨 일련번호로 구별해 기록합니다.</p>

<h2>완전 중복 (내용이 똑같은 파일)</h2>
<dl>
<dt>중복 묶음</dt><dd>{num(dup["묶음수"])}개 (묶음에 든 파일 {num(dup["묶음속파일수"])}개)</dd>
<dt>하나만 남길 때 남는 사본</dt><dd>{num(dup["남는사본수"])}개</dd>
<dt>회수 가능 용량</dt><dd>{human_bytes(dup["회수가능용량"])}</dd>
<dt>0바이트 파일</dt><dd>{num(s["0바이트파일"])}개 <span class="sub">(내용이 없어 중복으로 묶지 않고 따로 셈)</span></dd>
</dl>
<p class="sub">묶음별 파일 목록은 엑셀 「중복파일」 시트에 있습니다.</p>

<h2>중첩 백업 (겹치는 폴더)</h2>
<dl>
<dt>같은 내용 폴더 묶음</dt><dd>{num(nb["구조까지같은묶음(a)"])}묶음은 구조·이름까지 같음(a),
  {num(nb["배치만다른묶음(b)"])}묶음은 이름·배치가 다른 것이 섞임(b)</dd>
<dt>포함 관계</dt><dd>{num(nb["포함관계쌍(c)"])}쌍 — 한 폴더의 파일이 다른 폴더에 모두 들어 있고, 다른 폴더가 더 많음(c)</dd>
<dt>중첩 백업 폴더 쌍</dt><dd>{num(nb["폴더쌍수"])}쌍</dd>
<dt>겹치는 폴더 용량(추정)</dt><dd>{human_bytes(nb["겹치는폴더용량"])}</dd>
</dl>
<p class="sub">상위 폴더가 이미 중복이면 그 아래 폴더는 따로 보고하지 않고 접었습니다.
'참고'는 접힌 쪽에 있는 짝을 보여 준 것입니다. '구조' 번호가 같은 폴더끼리는 안의 이름·배치까지 같습니다.</p>
<h3>큰 중복 폴더 상위 20</h3>
{_table(["#", "관계", "용량", "파일 수", "폴더"], top_rows, {2, 3})}

<h2>정리본 용량 추정</h2>
{dest_html}

<h2>확장자별 (용량 상위 20)</h2>
{_table(["확장자", "파일 수", "용량", ""], _bar_rows(ext_items, 2), {1, 2})}

<h2>연도별 (수정한 날짜 기준)</h2>
{_table(["연도", "파일 수", "용량", ""], _bar_rows(year_items, 1), {1, 2})}

<h2>복사본·임시파일 표지</h2>
{_table(["표지", "파일 수"], mark_rows, {1})}
<p class="sub">표지는 판정이 아니라 단서입니다. 예: '붙임(1)'처럼 정상 문서에도 (숫자) 표지가 붙을 수 있습니다.</p>

<h2>오류와 건너뜀</h2>
{_table(["단계", "종류", "건수"], err_rows, {2})}
<div style="height:10px"></div>
{_table(["건너뛴 사유", "건수"], skip_rows, {1})}
<p class="sub">오류가 난 파일·폴더는 건너뛰고 계속했습니다. 목록은 엑셀 「오류」「건너뜀」 시트에 있습니다.
목록을 끝까지 읽지 못한 폴더는 중복 판정에서 보수적으로(중복이 아닌 쪽으로) 다룹니다.</p>

<h2>실행 조건</h2>
<dl>
<dt>검사 시작점</dt><dd class="path">{"<br>".join(_e(r) for r in opts.get("roots", []))}</dd>
<dt>기본 제외 목록 사용</dt><dd>{"예" if opts.get("default_excludes", True) else "아니오"}</dd>
<dt>추가 제외 경로</dt><dd class="path">{"<br>".join(_e(x) for x in opts.get("excludes", [])) or "-"}</dd>
<dt>추가 제외 패턴</dt><dd class="path">{"<br>".join(_e(x) for x in opts.get("exclude_patterns", [])) or "-"}</dd>
</dl>
</main></body></html>
"""


# ── 엑셀 ───────────────────────────────────────────────────────
def _ts(ns) -> str:
    if ns is None:
        return ""
    try:
        return _dt.datetime.fromtimestamp(ns / 1e9).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return str(ns)


def build_xlsx(con, run_id: int, s: dict):
    def build(wb):
        head = wb.add_format({"bold": True, "bg_color": "#F0F2F5", "border": 1})
        intf = wb.add_format({"num_format": "#,##0"})

        def sheet(title, headers, rows, widths, int_cols=()):
            ws = wb.add_worksheet(title)
            for c, h in enumerate(headers):
                ws.write_string(0, c, h, head)
                ws.set_column(c, c, widths[c] if c < len(widths) else 14)
            r = 0
            for r, row in enumerate(rows, 1):
                if r > EXCEL_MAX_ROWS:
                    ws.write_string(r, 0, f"… 행이 너무 많아 {EXCEL_MAX_ROWS:,}행에서 끊었습니다. 전체는 scan.sqlite 에 있습니다.")
                    break
                for c, v in enumerate(row):
                    if v is None:
                        continue
                    if c in int_cols and isinstance(v, (int, float)):
                        ws.write_number(r, c, v, intf)
                    else:
                        ws.write_string(r, c, str(v))
            ws.freeze_panes(1, 0)
            if r:
                ws.autofilter(0, 0, min(r, EXCEL_MAX_ROWS), len(headers) - 1)
            return ws

        # 요약
        dup, nb, dest = s["완전중복"], s["중첩백업"], s["정리본용량"]
        summary_rows = [
            ("작성", s["작성"]), ("도구", s["도구"]), ("총 파일 수", s["총파일"]), ("총 용량(바이트)", s["총용량"]),
            ("폴더 수", s["폴더수"]), ("완전중복 묶음", dup["묶음수"]), ("묶음 속 파일", dup["묶음속파일수"]),
            ("남는 사본", dup["남는사본수"]), ("회수 가능 용량(바이트)", dup["회수가능용량"]),
            ("0바이트 파일", s["0바이트파일"]), ("같은 내용 폴더 묶음 a", nb["구조까지같은묶음(a)"]),
            ("같은 내용 폴더 묶음 b", nb["배치만다른묶음(b)"]), ("포함 관계 쌍 c", nb["포함관계쌍(c)"]),
            ("중첩 백업 폴더 쌍", nb["폴더쌍수"]), ("겹치는 폴더 용량(바이트)", nb["겹치는폴더용량"]),
            ("고유 내용 용량(바이트)", dest.get("고유내용용량")),
            ("대상 드라이브로 복사할 용량(바이트)", dest.get("대상드라이브로복사할용량")),
            ("대상 드라이브 남은 공간(바이트)", dest.get("남은공간")), ("오류 합계", s["오류합계"]),
        ]
        sheet("요약", ["항목", "값"], summary_rows, [34, 24], int_cols={1})
        sheet("드라이브", ["문자", "볼륨 일련번호", "이름", "형식", "파일 수", "검사 용량", "전체", "남음", "검사 시작점"],
              [(v["문자"], v["일련번호"], v["이름"], v["형식"], v["파일수"], v["용량"], v["전체"], v["남음"],
                " | ".join(v["검사시작점"])) for v in s["드라이브"]],
              [6, 14, 14, 8, 12, 16, 16, 16, 60], int_cols={4, 5, 6, 7})
        sheet("중복파일", ["묶음", "묶음 크기(바이트)", "묶음 파일 수", "회수 가능(바이트)", "경로", "이름",
                       "수정한 날짜", "만든 날짜", "복사본 표지(날짜)", "복사본 표지(이름)", "임시파일"],
              _dup_rows(con, run_id),
              [7, 14, 10, 14, 90, 40, 19, 19, 10, 12, 8], int_cols={0, 1, 2, 3})
        sheet("중복폴더", ["묶음", "수준", "폴더 경로", "구조 번호", "역할", "파일 수", "용량(바이트)"],
              con.execute("""SELECT g.group_no, g.level, d.path, m.a_class, m.role, g.file_count, g.total_bytes
                             FROM folder_groups g JOIN folder_members m ON m.run_id=g.run_id
                               AND m.group_no=g.group_no JOIN dirs d ON d.dir_id=m.dir_id
                             WHERE g.run_id=? ORDER BY g.group_no, d.path""", (run_id,)),
              [7, 6, 90, 9, 8, 10, 16], int_cols={0, 3, 5, 6})
        sheet("포함관계", ["안쪽 폴더", "안쪽 파일 수", "안쪽 용량", "바깥 폴더", "바깥 파일 수", "바깥 용량"],
              con.execute("""SELECT di.path, c.inner_files, c.inner_bytes, dx.path, c.outer_files, c.outer_bytes
                             FROM folder_contains c JOIN dirs di ON di.dir_id=c.inner_dir_id
                             JOIN dirs dx ON dx.dir_id=c.outer_dir_id WHERE c.run_id=?
                             ORDER BY c.inner_bytes DESC, di.path""", (run_id,)),
              [70, 10, 14, 70, 10, 14], int_cols={1, 2, 4, 5})
        sheet("복사본·임시", ["경로", "크기", "수정한 날짜", "만든 날짜", "날짜 표지", "이름 표지", "임시파일"],
              ((p, sz, _ts(m), _ts(b), "예" if cd else "", cn or "", "예" if t else "")
               for p, sz, m, b, cd, cn, t in con.execute(
                   """SELECT path, size, mtime_ns, birth_ns, copy_by_date, copy_name, is_temp FROM files
                      WHERE seen_run=? AND (copy_by_date=1 OR copy_name IS NOT NULL OR is_temp=1)
                      ORDER BY path""", (run_id,))),
              [90, 12, 19, 19, 8, 10, 8], int_cols={1})
        sheet("0바이트", ["경로"], ((p,) for (p,) in con.execute(
            "SELECT path FROM files WHERE seen_run=? AND size=0 ORDER BY path", (run_id,))), [100])
        sheet("오류", ["단계", "종류", "경로", "내용", "코드"],
              con.execute("SELECT stage, kind, path, message, code FROM errors WHERE run_id=? ORDER BY error_id",
                          (run_id,)), [8, 18, 90, 60, 8], int_cols={4})
        sheet("건너뜀", ["사유", "종류", "경로"],
              con.execute("SELECT reason, kind, path FROM skipped WHERE run_id=? ORDER BY reason, path",
                          (run_id,)), [26, 6, 100])
        sheet("확장자", ["확장자", "파일 수", "용량(바이트)"],
              [(e["확장자"], e["파일수"], e["용량"]) for e in s["확장자"]], [12, 12, 18], int_cols={1, 2})
        sheet("연도", ["연도(수정)", "파일 수", "용량(바이트)"],
              [(y["연도"], y["파일수"], y["용량"]) for y in s["연도"]], [12, 12, 18], int_cols={1, 2})
    return build


def _dup_rows(con, run_id: int):
    for no, size, cnt, rec, p, nm, m, b, cd, cn, t in con.execute(
            """SELECT g.group_no, g.size, g.member_count, g.reclaimable, f.path, f.name,
                      f.mtime_ns, f.birth_ns, f.copy_by_date, f.copy_name, f.is_temp
               FROM dup_groups g JOIN dup_members m ON m.run_id=g.run_id AND m.group_no=g.group_no
               JOIN files f ON f.file_id=m.file_id WHERE g.run_id=?
               ORDER BY g.group_no, f.path""", (run_id,)):
        yield (no, size, cnt, rec, p, nm, _ts(m), _ts(b), "예" if cd else "", cn or "", "예" if t else "")


def write_reports(out, con, run_id: int, dest: str | None) -> dict:
    s = collect_summary(con, run_id, dest)
    out.put_text("진단보고서.html", render_html(s))
    out.put_xlsx("진단상세.xlsx", build_xlsx(con, run_id, s))
    out.put_text("요약숫자.json", json.dumps(numbers_only(s), ensure_ascii=False, indent=2))
    return s
