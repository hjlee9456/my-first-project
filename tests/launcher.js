/*
 * 통합 첫 화면 회귀 테스트 — 한 파일 안에서 두 프로그램이 제대로 도는지 본다.
 * 저장 공간 공유·인쇄·백업 내려받기까지 확인한다.
 *
 * 실행 방법 (터미널에서):
 *   python3 build.py
 *   npm i playwright
 *   node tests/launcher.js
 */
const { chromium } = require("playwright");
const SEED = require("../예시자료.json");

const errs = [], ok = [];
const check = (n, c, x) => (c ? ok : errs).push(n + (x ? " → " + x : ""));
const flat = s => String(s || "").replace(/\s+/g, " ");

(async () => {
  const b = await chromium.launch({
    executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    downloadsPath: "/tmp",
  });
  const ctx = await b.newContext({ viewport: { width: 1500, height: 950 }, acceptDownloads: true });
  const p = await ctx.newPage();
  p.on("pageerror", e => errs.push("PAGE ERROR: " + e.message));
  p.on("console", m => { if (m.type() === "error") errs.push("CONSOLE: " + m.text()); });

  await p.goto("file:///home/user/my-first-project/어린이집살림도우미.html");
  await p.waitForTimeout(300);

  // ---- 첫 화면 ----
  check("첫 화면에 프로그램 두 개", (await p.locator(".card").count()) === 2);
  const home = flat(await p.textContent("#home"));
  check("두 프로그램 이름 표시",
    /기타필요경비 정산/.test(home) && /물품관리/.test(home), home.slice(0, 140));

  // 어린이집 이름은 두 프로그램이 같은 자리에 적으므로 첫 화면에도 뜬다
  await p.evaluate(() => localStorage.setItem("centerName", "여수시립 힐스테이트죽림젠트리스어린이집"));
  await p.reload();
  await p.waitForTimeout(300);
  check("첫 화면에 어린이집 이름", /힐스테이트죽림젠트리스/.test(await p.inputValue("#centerName")));

  // 버전·제작자·의견 주실 곳은 첫 화면 하나에만 둔다
  const about = flat(await p.textContent("#home .about"));
  check("첫 화면에 버전·제작자", /어린이집 살림도우미 v1\.0\.0 · 제작 이현재/.test(about), about.slice(0, 60));
  check("첫 화면에 의견 주실 곳", /hjlee9446@korea\.kr/.test(about) && /받아보고 싶은 어린이집/.test(about), about);
  check("메일 링크가 걸려 있음",
    (await p.locator('#home .about a[href^="mailto:hjlee9446@korea.kr"]').count()) === 1);

  // ---- 정산 프로그램 ----
  await p.locator('.card[data-app="settle"]').click();
  await p.waitForTimeout(700);
  const f = p.frameLocator("#app");
  check("정산 프로그램이 열림", (await f.locator("nav button").count()) === 8);

  // 바깥에서 심은 자료를 안에서 그대로 읽어야 한다 (저장 공간 공유)
  await p.evaluate(([k, v]) => localStorage.setItem(k, JSON.stringify(v)), ["nursery-settlement-v1", SEED]);
  await p.locator('.card, #back').first().waitFor().catch(() => {});
  await p.reload();
  await p.waitForTimeout(800);
  const f2 = p.frameLocator("#app");
  check("새로고침해도 보던 프로그램으로 돌아옴",
    (await p.locator("#run.on").count()) === 1 && (await f2.locator("nav button").count()) === 8);

  const inner = () => p.frames().find(fr => fr !== p.mainFrame());
  const kids = await inner().evaluate(() => S.children.length);
  check("바깥에서 심은 자료를 프로그램 안에서 읽음 (원아 37명)", kids === 37, String(kids));

  // 화면 이동
  await f2.locator('nav button[data-tab="settle"]').click();
  await p.waitForTimeout(400);
  await f2.locator('[data-m="back"]').click();
  await f2.locator('[data-p="Y"]').click();
  await p.waitForTimeout(600);
  const bk = flat(await f2.locator("#bk_body").textContent());
  check("정산 프로그램 안에서 반환 정산서가 나옴",
    /필요경비 반환 정산서/.test(bk) && /반환 합계/.test(bk), bk.slice(0, 130));

  // 백업 내려받기가 되는지 (파일 이름은 headless에서 확인되지 않아 받아졌는지만 본다)
  const dl = await Promise.all([
    p.waitForEvent("download", { timeout: 8000 }).catch(() => null),
    f2.locator("#btnExport").click(),
  ]);
  check("프로그램 안에서 백업 파일이 내려받아짐", !!dl[0]);
  check("백업을 받으면 알림이 사라짐",
    (await inner().evaluate(() => document.getElementById("backupWarn").textContent)) === "");

  // 프로그램 안에서 인쇄하면 그 화면만 잡혀야 한다 (잘리지 않음)
  await p.evaluate(() => { window.__top = false; window.addEventListener("beforeprint", () => window.__top = true); });
  await inner().evaluate(() => window.print());
  await p.waitForTimeout(300);
  check("프로그램 안 인쇄는 그 화면만 잡음", (await p.evaluate(() => window.__top)) === false);

  // 바깥에서 인쇄해도 잘리지 않게 화면틀이 내용 높이만큼 늘어난다
  await p.emulateMedia({ media: "print" });
  await p.evaluate(() => window.dispatchEvent(new Event("beforeprint")));
  await p.waitForTimeout(250);
  const fh = await p.evaluate(() => document.getElementById("app").getBoundingClientRect().height);
  const ih = await inner().evaluate(() => document.body.scrollHeight);
  check("바깥에서 인쇄해도 내용이 잘리지 않음", Math.abs(fh - ih) < 40, fh + "px vs " + ih + "px");
  check("인쇄할 때 위쪽 막대가 빠짐", !(await p.locator("#bar").isVisible()));
  await p.evaluate(() => window.dispatchEvent(new Event("afterprint")));
  await p.emulateMedia({ media: "screen" });

  // ---- 처음 화면으로 ----
  await p.click("#back");
  await p.waitForTimeout(300);
  check("처음 화면으로 돌아옴", (await p.locator("#run.on").count()) === 0);

  // ---- 물품관리 ----
  await p.locator('.card[data-app="goods"]').click();
  await p.waitForTimeout(800);
  const g = p.frameLocator("#app");
  const gtxt = flat(await g.locator("body").textContent());
  check("물품관리가 열림", /물품대장/.test(gtxt) && /재물조사/.test(gtxt), gtxt.slice(0, 150));

  // 물품관리도 같은 자리에 어린이집 이름을 적으므로 그대로 보여야 한다
  const gname = await p.frames().find(fr => fr !== p.mainFrame()).evaluate(() => localStorage.getItem("centerName"));
  check("물품관리도 같은 어린이집 이름을 봄", /힐스테이트죽림젠트리스/.test(gname || ""), gname);
  check("물품관리 화면 위에 그 이름이 찍힘",
    /힐스테이트죽림젠트리스/.test(await g.locator("#center-name-display").textContent()));

  // 이름을 정하는 자리는 첫 화면 하나뿐 — 물품관리 ⚙ 설정에서는 빠져 있어야 한다
  await g.locator(".btn-settings").click();
  await p.waitForTimeout(400);
  check("물품관리 ⚙ 설정에 이름 입력칸이 없음",
    (await g.locator("#inp-center-name").count()) === 0);
  const st = flat(await g.locator("#screen-settings").textContent());
  check("설정 화면이 첫 화면을 가리킴",
    /맨 처음 화면/.test(st) && /시스템 초기화/.test(st), st.slice(0, 150));
  await g.locator("#screen-settings .btn-home").click();
  await p.waitForTimeout(300);

  // 물품관리 쪽 버전 표시는 첫 화면으로 옮겼으므로 통합본에는 없어야 한다
  check("물품관리 화면에 버전 표시가 남아 있지 않음",
    (await g.locator(".app-version").count()) === 0);

  // 두 프로그램의 저장 자리가 서로 섞이지 않는지
  const keys = await p.evaluate(() => Object.keys(localStorage).sort());
  check("저장 자리가 서로 섞이지 않음",
    keys.includes("nursery-settlement-v1") && keys.includes("centerName"), keys.join(", "));

  await p.screenshot({ path: (process.env.SHOT_DIR || "./") + "launcher-goods.png" });
  await p.click("#back");
  await p.waitForTimeout(300);
  await p.screenshot({ path: (process.env.SHOT_DIR || "./") + "launcher-home.png" });

  await b.close();
  console.log("=== 통과 ==="); ok.forEach(s => console.log("  ✓ " + s));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s => console.log("  ✗ " + s)); process.exit(1); }
  console.log("모두 통과");
})();
