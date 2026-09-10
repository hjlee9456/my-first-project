# -*- coding: utf-8 -*-
"""
두 프로그램을 한 파일로 합쳐 index.html을 만든다.

    python3 build.py

어린이집에는 index.html 하나만 건네면 된다. 더블클릭하면 첫 화면이 뜨고
「기타필요경비 정산」과 「물품관리」 중 하나를 골라 들어간다.

각 프로그램은 손대지 않고 통째로 담는다. 서로 다른 화면틀에서 돌아가므로
CSS나 함수 이름이 부딪히지 않고, 저장 공간은 같은 자리를 쓰므로 지금까지
쌓아 둔 자료가 그대로 보인다.
"""
import base64
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))

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
<title>어린이집 관리</title>
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
#home .nameRow{display:flex;align-items:center;gap:8px;margin-bottom:2px}
#home .nameRow label{font-size:12px;color:var(--faint)}
#home .nameRow input{font:inherit;font-size:13px;text-align:center;padding:5px 10px;width:290px;
  border:1px solid transparent;border-radius:5px;background:transparent;color:var(--dim)}
#home .nameRow input:hover{border-color:var(--line);background:#fff}
#home .nameRow input:focus{outline:2px solid var(--accent-bg);border-color:var(--accent);
  background:#fff;color:var(--ink)}
#home .saved{font-size:11px;color:var(--accent);opacity:0;transition:.2s}
#home .saved.on{opacity:1}
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
  <div class="nameRow">
    <input id="centerName" placeholder="어린이집 이름을 적으세요 (인쇄물 머리글에 찍힙니다)"
           title="여기 적은 이름이 두 프로그램의 인쇄물에 모두 찍힙니다">
    <span class="saved" id="nameSaved">저장됨</span>
  </div>
  <h1>어린이집 관리</h1>
  <div class="lead">쓰실 프로그램을 고르세요.</div>
  <div class="cards">
__CARDS__
  </div>
  <div class="foot">
    입력한 자료는 이 컴퓨터의 브라우저에만 저장됩니다.<br>
    각 프로그램 안에서 <b>가끔 백업 파일을 받아 두세요.</b>
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
  document.title = "어린이집 관리";
  showCenterName();
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
var nameInput = document.getElementById("centerName");
var nameSaved = document.getElementById("nameSaved");

function showCenterName(){
  var n = "";
  try { n = localStorage.getItem("centerName") || ""; } catch (e) {}
  nameInput.value = n;
}
function saveCenterName(){
  try { localStorage.setItem("centerName", nameInput.value.trim()); } catch (e) {}
  nameSaved.classList.add("on");
  setTimeout(function(){ nameSaved.classList.remove("on"); }, 1200);
}
nameInput.addEventListener("change", saveCenterName);
nameInput.addEventListener("keydown", function(e){ if (e.key === "Enter") nameInput.blur(); });
showCenterName();

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
        html = io.open(path, encoding="utf-8").read()
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

    out = os.path.join(HERE, "index.html")
    io.open(out, "w", encoding="utf-8").write(page)
    print("만듦: index.html  %.0f KB" % (os.path.getsize(out) / 1024))


if __name__ == "__main__":
    main()
