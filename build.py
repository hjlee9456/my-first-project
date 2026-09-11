# -*- coding: utf-8 -*-
"""
두 프로그램을 한 파일로 합쳐 「어린이집 살림도우미」를 만든다.

    python3 build.py

어린이집에는 어린이집살림도우미.html 하나만 건네면 된다. 더블클릭하면 첫 화면이 뜨고
「기타필요경비 정산」과 「물품관리」 중 하나를 골라 들어간다.

각 프로그램은 손대지 않고 통째로 담는다. 서로 다른 화면틀에서 돌아가므로
CSS나 함수 이름이 부딪히지 않고, 저장 공간은 같은 자리를 쓰므로 지금까지
쌓아 둔 자료가 그대로 보인다.
"""
import base64
import io
import os
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))

# 통합본의 버전. 두 프로그램을 한 파일로 묶으면서 새로 매긴다.
# 고칠 일이 있으면 여기만 고치면 첫 화면에 그대로 나온다.
NAME    = "어린이집 살림도우미"
FILE    = "어린이집살림도우미.html"
VERSION = "v1.0.0"
MAKER   = "이현재"
MAIL    = "hjlee9446@korea.kr"

# ---------------------------------------------------------------------------
# 통합본에서만 걷어내는 부분
#
# 물품관리시스템.html은 혼자서도 돌아가는 완성품이라 손대지 않는다. 다만 한
# 파일로 합치면 어린이집 이름을 정하는 자리가 첫 화면과 물품관리 ⚙ 설정 두
# 군데가 되어 헷갈린다. 그래서 담을 때만 물품관리 쪽 이름 설정을 들어내고
# 첫 화면을 가리키게 한다. 원본 파일은 그대로 남는다.
# ---------------------------------------------------------------------------
PATCHES = {
    "물품관리시스템.html": [
        # ⚙ 설정 화면 — 이름 입력칸을 들어내고 어디서 정하는지 알려 준다
        ("""    <!-- 어린이집 이름 -->
    <div class="input-area">
      <div>
        <label style="width:100px; white-space:nowrap;">어린이집 이름</label>
        <input type="text" id="inp-center-name" placeholder="예) 여수시립 햇살어린이집" style="width:280px;">
        <button class="btn-blue" style="margin-left:10px;" onclick="saveCenterName()">저장</button>
      </div>
      <p style="margin:12px 0 0; font-size:13px; color:#888;">
        여기서 정한 이름은 화면 상단과 물품대장·재물조사 조서 인쇄물에 함께 표시됩니다.
      </p>
    </div>""",
         """    <!-- 어린이집 이름은 맨 처음 화면에서 정한다 -->"""),

        # 입력칸이 없어졌으므로 화면 상단 이름만 갱신한다
        ("""      document.getElementById('center-name-display').textContent = name;
      document.getElementById('inp-center-name').value = (name === 'OO어린이집') ? '' : name;""",
         """      document.getElementById('center-name-display').textContent = name;
      var inp = document.getElementById('inp-center-name');   // 통합본에는 없다
      if (inp) inp.value = (name === 'OO어린이집') ? '' : name;"""),

        # 설명서 — 설정 화면 소개
        ("""        <li>화면 위쪽 <b>⚙ 설정</b> : 어린이집 이름 설정·시스템 초기화</li>""",
         """        <li>화면 위쪽 <b>⚙ 설정</b> : 시스템 초기화</li>"""),

        # 설명서 — 상세본 4장
        ("""      <h2>4. 맨 처음 한 번만 — 어린이집 이름 넣기</h2>
      <p>인쇄물에 어린이집 이름이 자동으로 찍히게 하려면, 처음에 한 번만 설정하면 됩니다.</p>
      <ol>
        <li>화면 위 <b>⚙ 설정</b>을 누릅니다.</li>
        <li><b>「어린이집 이름」</b> 칸에 이름을 적습니다. (예: 여수시립 햇살어린이집)</li>
        <li><b>「저장」</b>을 누릅니다.</li>
      </ol>
      <p>이제 물품대장·재물조사 서류를 인쇄하면, 어린이집 이름이 자동으로 들어갑니다.</p>""",
         """      <h2>4. 맨 처음 한 번만 — 어린이집 이름 넣기</h2>
      <p>인쇄물에 어린이집 이름이 자동으로 찍히게 하려면, 처음에 한 번만 적어 두면 됩니다.</p>
      <ol>
        <li>화면 위 <b>「← 처음 화면」</b>을 눌러 <b>맨 처음 화면</b>으로 나갑니다.</li>
        <li>왼쪽 위 <b>「⚙ 어린이집 이름 설정」</b>을 누릅니다.</li>
        <li>이름을 적고 <b>「저장」</b>을 누릅니다. (예: 여수시립 햇살어린이집)</li>
      </ol>
      <p>이제 물품대장·재물조사 서류를 인쇄하면, 어린이집 이름이 자동으로 들어갑니다.
        <b>기타필요경비 정산</b>의 인쇄물에도 같은 이름이 함께 찍힙니다.</p>""") ,

        # 설명서 — 빠르게본
        ("""      <p><b>⚙ 설정 → 어린이집 이름 입력 → 「저장」.</b> (인쇄물에 자동으로 찍힙니다.)</p>""",
         """      <p><b>「← 처음 화면」 → 왼쪽 위 「⚙ 어린이집 이름 설정」 → 이름 적고 「저장」.</b>
        (두 프로그램 인쇄물에 모두 자동으로 찍힙니다.)</p>"""),

        # 이름 칸이 빠져 설정 화면 첫 칸이 되므로 위 여백을 없앤다
        ("""    <div class="input-area" style="margin-top:32px; border-top:2px solid #e74c3c; padding-top:20px;">""",
         """    <div class="input-area" style="border-top:2px solid #e74c3c; padding-top:20px;">"""),

        # 시스템 초기화 안내 문구
        ("""        &nbsp;&nbsp;※ 어린이집 이름 설정은 유지됩니다.<br>""",
         """        &nbsp;&nbsp;※ 어린이집 이름은 유지됩니다.<br>"""),

        # 버전·제작자 표시 — 통합본에서는 맨 처음 화면이 대신 갖는다
        ("""  <div class="app-version no-print">물품관리 시스템 v1.0.1 · 제작 이현재</div>""",
         """  <!-- 버전·제작자 표시는 통합본 맨 처음 화면에 있다 -->"""),
    ],
}


def patch(filename, html):
    """통합본에 담기 전에 손볼 것이 있으면 손본다. 못 찾으면 바로 멈춘다."""
    for old, new in PATCHES.get(filename, []):
        if old not in html:
            raise SystemExit("build.py: %s 에서 고칠 자리를 찾지 못했습니다:\n%s"
                             % (filename, old[:80]))
        html = html.replace(old, new, 1)
    return html


APPS = [
    ("settle", "기타필요경비 정산", "💰", "기타필요경비정산.html",
     "받은 돈과 쓴 돈을 원아별로 맞춰<br>정산서·보고서를 뽑습니다"),
    ("goods", "물품관리", "📦", "물품관리시스템.html",
     "보유 물품을 등록하고<br>물품대장·재물조사 서류를 뽑습니다"),
]

PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__NAME__</title>
<!--
  이 파일은 build.py가 만듭니다. 직접 고치지 마세요.
  고칠 것이 있으면 기타필요경비정산.html이나 물품관리시스템.html을 고친 뒤
  python3 build.py 를 다시 돌리세요.
-->
<style>
:root{
  --bg:#f6f7f9; --panel:#fff; --line:#dde1e7; --ink:#1c2530;
  --dim:#66707d; --faint:#98a1ad; --accent:#2f6fd0; --accent-bg:#eaf1fc;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.6 -apple-system,BlinkMacSystemFont,"Malgun Gothic","맑은 고딕","Apple SD Gothic Neo",sans-serif}

/* ---------- 첫 화면 ---------- */
#home{min-height:100%;display:flex;flex-direction:column;
  align-items:center;justify-content:center;padding:40px 20px;gap:6px}
#home .corner{position:fixed;top:14px;left:14px;font:inherit;font-size:13px;
  padding:7px 14px;border:1px solid var(--line);background:var(--panel);
  border-radius:6px;cursor:pointer;color:var(--dim)}
#home .corner:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-bg)}
#home h1{margin:2px 0 4px;font-size:27px;font-weight:700}
#home .lead{font-size:13.5px;color:var(--dim);margin-bottom:26px}
.cards{display:flex;gap:18px;flex-wrap:wrap;justify-content:center}
.card{width:255px;background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:30px 22px;text-align:center;cursor:pointer;transition:.15s;
  font:inherit;color:inherit;display:block}
.card:hover{border-color:var(--accent);background:var(--accent-bg);
  transform:translateY(-3px);box-shadow:0 6px 20px rgba(47,111,208,.12)}
.card .ic{font-size:46px;line-height:1}
.card .tt{font-size:18px;font-weight:700;margin-top:14px}
.card .ds{font-size:12.5px;color:var(--dim);margin-top:9px;line-height:1.7}
#home .foot{margin-top:30px;font-size:12px;color:var(--faint);text-align:center;line-height:1.9}
#home .about{margin-top:16px;padding-top:14px;border-top:1px solid var(--line);
  max-width:580px;font-size:11.5px;color:var(--faint);text-align:center;line-height:1.9}
#home .about .ver{color:var(--dim);font-weight:600;margin-bottom:3px}
#home .about a{color:var(--accent);text-decoration:none;font-weight:600}
#home .about a:hover{text-decoration:underline}

/* ---------- 어린이집 이름 창 ---------- */
#nameMask{position:fixed;inset:0;background:rgba(20,26,34,.42);
  display:flex;align-items:center;justify-content:center;z-index:100;padding:20px}
#nameMask[hidden]{display:none}
#nameBox{background:var(--panel);border-radius:10px;padding:24px 26px 20px;
  width:100%;max-width:430px;box-shadow:0 16px 44px rgba(0,0,0,.22)}
#nameBox h2{margin:0 0 8px;font-size:17px}
#nameBox p{margin:0 0 16px;font-size:12.5px;color:var(--dim);line-height:1.8}
#nameBox input{font:inherit;font-size:14px;width:100%;padding:9px 11px;
  border:1px solid var(--line);border-radius:6px;color:var(--ink)}
#nameBox input:focus{outline:2px solid var(--accent-bg);border-color:var(--accent)}
#nameBox .btns{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}
#nameBox button{font:inherit;font-size:13px;padding:7px 16px;border:1px solid var(--line);
  background:#fff;border-radius:5px;cursor:pointer;color:var(--ink)}
#nameBox button:hover{background:var(--bg)}
#nameBox button.pri{background:var(--accent);border-color:var(--accent);color:#fff}
#nameBox button.pri:hover{filter:brightness(1.07)}

/* ---------- 프로그램 화면 ---------- */
#run{position:fixed;inset:0;display:none;flex-direction:column}
#run.on{display:flex}
#bar{flex:0 0 auto;background:var(--panel);border-bottom:1px solid var(--line);
  padding:7px 14px;display:flex;align-items:center;gap:12px}
#bar button{font:inherit;font-size:13px;padding:5px 12px;border:1px solid var(--line);
  background:#fff;border-radius:4px;cursor:pointer;color:var(--ink)}
#bar button:hover{background:var(--bg)}
#bar .name{font-size:13px;font-weight:600;color:var(--dim)}
#app{flex:1 1 auto;width:100%;border:0;display:block}

@media print{
  html,body{height:auto}
  #bar{display:none!important}
}
</style>
</head>
<body>

<div id="home">
  <button id="btnName" class="corner">⚙ 어린이집 이름 설정</button>
  <h1>__NAME__</h1>
  <div class="lead">쓰실 프로그램을 고르세요.</div>
  <div class="cards">
__CARDS__
  </div>
  <div class="foot">
    입력한 자료는 이 컴퓨터의 브라우저에만 저장됩니다.<br>
    각 프로그램 안에서 <b>가끔 백업 파일을 받아 두세요.</b>
  </div>

  <div class="about">
    <div class="ver">__NAME__ __VERSION__ · 제작 이현재</div>
    <div>
      더 있었으면 하는 기능이나 고칠 점이 있으면
      <a href="mailto:__MAIL__?subject=__SUBJECT__">__MAIL__</a>
      로 알려 주세요.<br>
      의견을 주신 분, 그리고 앞으로 <b>고쳐 나온 것을 계속 받아보고 싶은 어린이집</b>도
      같은 주소로 연락 주시면 됩니다.
    </div>
  </div>
</div>

<!-- 어린이집 이름 — 두 프로그램이 함께 쓰므로 여기서 한 번만 정한다 -->
<div id="nameMask" hidden>
  <div id="nameBox">
    <h2>어린이집 이름</h2>
    <p>여기 적은 이름이 <b>물품대장·재물조사 조서·정산서·보고서</b> 인쇄물 머리글에
      모두 찍힙니다. 한 번만 적어 두면 됩니다.</p>
    <input id="centerName" placeholder="예) 여수시립 햇살어린이집">
    <div class="btns">
      <button id="nameCancel">취소</button>
      <button id="nameSave" class="pri">저장</button>
    </div>
  </div>
</div>

<div id="run">
  <div id="bar">
    <button id="back">← 처음 화면</button>
    <span class="name" id="runName"></span>
  </div>
  <iframe id="app" title="프로그램"></iframe>
</div>

<script>
"use strict";

/* 각 프로그램의 HTML을 통째로 담아 둔다. 화면틀(iframe)을 따로 주므로
   서로의 CSS·함수와 부딪히지 않고, 저장 공간은 같은 자리를 쓴다. */
var APPS = __APPS__;

function fromB64(b64){
  var bin = atob(b64);
  var bytes = new Uint8Array(bin.length);
  for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder("utf-8").decode(bytes);
}

var home = document.getElementById("home");
var run  = document.getElementById("run");
var app  = document.getElementById("app");

function openApp(key){
  var a = APPS[key];
  if (!a) return;
  document.getElementById("runName").textContent = a.name;
  document.title = a.name;
  app.srcdoc = fromB64(a.html);
  home.style.display = "none";
  run.classList.add("on");
  location.hash = key;
}

function goHome(){
  run.classList.remove("on");
  app.srcdoc = "";
  home.style.display = "";
  document.title = "__NAME__";
  if (location.hash) history.replaceState(null, "", location.pathname);
}

/* 인쇄
   프로그램 안의 「인쇄」 버튼은 그 화면틀만 인쇄하므로 잘리지 않는다.
   다만 바깥에서 Ctrl+P를 누르면 화면에 보이는 높이만큼만 잡히므로,
   그때는 화면틀을 내용 높이만큼 늘려 두었다가 인쇄가 끝나면 되돌린다. */
function fitForPrint(){
  try {
    var d = app.contentDocument;
    if (!d) return;
    run.style.position = "static";
    app.style.height = Math.max(d.documentElement.scrollHeight, d.body.scrollHeight) + "px";
  } catch (e) {}
}
function resetAfterPrint(){
  run.style.position = "";
  app.style.height = "";
}
window.addEventListener("beforeprint", fitForPrint);
window.addEventListener("afterprint", resetAfterPrint);

/* Ctrl+P를 눌러도 프로그램 화면만 인쇄되게 넘겨 준다.
   그래야 표 머리행이 쪽마다 다시 찍힌다. */
document.addEventListener("keydown", function(e){
  var p = (e.key === "p" || e.key === "P");
  if (p && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && run.classList.contains("on")) {
    e.preventDefault();
    if (app.contentWindow) app.contentWindow.print();
  }
}, true);

document.getElementById("back").onclick = goHome;
Array.prototype.forEach.call(document.querySelectorAll(".card"), function(el){
  el.onclick = function(){ openApp(el.getAttribute("data-app")); };
});

/* 어린이집 이름은 여기서 한 번만 정한다.
   두 프로그램이 같은 자리를 보므로 양쪽 인쇄물에 모두 찍힌다. */
var nameMask  = document.getElementById("nameMask");
var nameInput = document.getElementById("centerName");

function openNameBox(){
  var n = "";
  try { n = localStorage.getItem("centerName") || ""; } catch (e) {}
  nameInput.value = n;
  nameMask.hidden = false;
  nameInput.focus();
  nameInput.select();
}
function closeNameBox(){ nameMask.hidden = true; }
function saveCenterName(){
  try { localStorage.setItem("centerName", nameInput.value.trim()); } catch (e) {}
  closeNameBox();
}

document.getElementById("btnName").onclick   = openNameBox;
document.getElementById("nameSave").onclick   = saveCenterName;
document.getElementById("nameCancel").onclick = closeNameBox;
nameMask.addEventListener("click", function(e){ if (e.target === nameMask) closeNameBox(); });
nameInput.addEventListener("keydown", function(e){
  if (e.key === "Enter")  saveCenterName();
  if (e.key === "Escape") closeNameBox();
});

/* 새로고침해도 보던 프로그램으로 돌아온다 */
var h = (location.hash || "").replace("#", "");
if (APPS[h]) openApp(h); else goHome();
</script>
</body>
</html>
"""


def main():
    cards, apps = [], []
    for key, name, icon, filename, desc in APPS:
        path = os.path.join(HERE, filename)
        html = patch(filename, io.open(path, encoding="utf-8").read())
        b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
        apps.append('  "%s": { name: "%s", html: "%s" }' % (key, name, b64))
        cards.append(
            '    <button class="card" data-app="%s">\n'
            '      <div class="ic">%s</div>\n'
            '      <div class="tt">%s</div>\n'
            '      <div class="ds">%s</div>\n'
            '    </button>' % (key, icon, name, desc))
        print("  담음: %-22s %6.0f KB" % (filename, len(html.encode("utf-8")) / 1024))

    page = PAGE.replace("__CARDS__", "\n".join(cards))
    page = page.replace("__APPS__", "{\n" + ",\n".join(apps) + "\n}")
    page = page.replace("__VERSION__", VERSION).replace("__MAIL__", MAIL)
    page = page.replace("__NAME__", NAME)
    page = page.replace("__SUBJECT__", quote(NAME + " 의견"))

    out = os.path.join(HERE, FILE)
    io.open(out, "w", encoding="utf-8").write(page)
    print("만듦: %s  %.0f KB" % (FILE, os.path.getsize(out) / 1024))


if __name__ == "__main__":
    main()
