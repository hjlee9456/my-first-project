/*
 * 예시자료.json 회귀 테스트 — 37명 규모 실제 자료로 모든 화면을 훑는다.
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/dummy.js
 */
const { chromium } = require("playwright");
const errs = [], ok = [];
const check = (n,c,x) => (c?ok:errs).push(n + (x?" → "+x:""));
const flat = s => String(s||"").replace(/\s+/g," ");
const SEED = require("/home/user/my-first-project/예시자료.json");
const OUT = process.env.SHOT_DIR || "./";

(async () => {
  const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const p = await b.newPage({ viewport:{width:1600,height:1000} });
  p.on("pageerror", e => errs.push("PAGE ERROR: " + e.message));
  p.on("console", m => { if (m.type()==="error") errs.push("CONSOLE: " + m.text()); });
  await p.goto("file:///home/user/my-first-project/기타필요경비정산.html");
  await p.evaluate(([k,v]) => { localStorage.setItem(k, JSON.stringify(v)); localStorage.setItem("centerName","여수시립 힐스테이트죽림젠트리스어린이집"); }, ["nursery-settlement-v1", SEED]);
  await p.reload(); await p.waitForTimeout(500);

  check("원아 37명 · 반 7개", await p.evaluate(() => S.children.length === 37 && S.classes.length === 7));
  check("수납결의서에서 수납 기록 파생", (await p.evaluate(() => S.receipts.length)) > 300);

  // 검증 탭 — 대사가 맞는지
  await p.click('nav button[data-tab="check"]');
  await p.waitForTimeout(300);
  const chk = flat(await p.textContent("#panel"));
  check("검증 대사 표시", /수납 합계/.test(chk) && /어린이집 부담/.test(chk), chk.slice(0, 230));
  const bad = await p.evaluate(() => runChecks().filter(i => i.level === "bad").length);
  check("저장 차단급 오류 없음", bad === 0, bad + "건");

  // 각 화면
  for (const [tab, label] of [["setup","기초설정"],["receipt","수납 입력"],["expense","지출 등록"],
                              ["child","원아별 현황"],["ledger","대장"]]) {
    await p.click(`nav button[data-tab="${tab}"]`);
    await p.waitForTimeout(250);
    check(label + " 화면이 뜸", (await p.locator("#panel").textContent()).length > 100);
  }

  // 원아별 현황 — 팝업
  await p.click('nav button[data-tab="child"]');
  await p.selectOption("#c_pick", { label: "김시원" });
  await p.waitForTimeout(250);
  const cs = flat(await p.textContent("#c_sum"));
  check("위탁 전환 원아에 「위탁 충당」 열", /위탁 충당/.test(cs), cs.slice(0,200));
  check("귀속액 문구", /원아 귀속액/.test(flat(await p.textContent("#c_use"))));
  await p.locator("#c_use button.link").first().click();
  await p.waitForTimeout(250);
  const modal = flat(await p.textContent(".modal"));
  check("금액 클릭 시 지출정보+명단 팝업",
    /지출건 내용 · 참여원아 명단/.test(modal) && /지출결의서 번호/.test(modal) && /1인당 배분/.test(modal),
    modal.slice(0,200));
  await p.screenshot({ path: OUT+"d-popup.png" });
  await p.locator(".modal .foot button", { hasText: "닫기" }).click();

  // 정산보고서 — 세목별 통계
  await p.click('nav button[data-tab="settle"]');
  await p.click('[data-m="half"]');
  await p.click('[data-p="Y"]');
  await p.waitForTimeout(350);
  const rep = flat(await p.textContent("#hp_body"));
  check("운영위 보고서가 세목별 통계",
    /수납 인원/.test(rep) && /지출 건수/.test(rep) && /입학준비금/.test(rep) && !/순번 성명/.test(rep),
    rep.slice(0,240));
  check("지출 내역이 함께 붙음", /지출 내역/.test(rep) && /입학식 기념품/.test(rep));
  await p.screenshot({ path: OUT+"d-report.png", fullPage: true });

  // 반환 정산서
  await p.click('[data-m="back"]');
  await p.click('[data-p="Y"]');
  await p.waitForTimeout(400);
  const bk = flat(await p.textContent("#bk_body"));
  check("반환 정산서 표시", /필요경비 반환 정산서/.test(bk) && /반환 합계/.test(bk), bk.slice(0,220));
  check("퇴소·위탁이 비고에 표시", /퇴소/.test(bk) && /위탁/.test(bk));
  await p.screenshot({ path: OUT+"d-back.png", fullPage: true });

  // 안내문 — 기간 버튼
  await p.click('[data-m="notice"]');
  check("안내문에 자주 쓰는 기간 버튼", (await p.locator('#panel [data-p="H1"]').count()) > 0);
  await p.click('[data-p="Y"]');
  await p.selectOption("#nt_child", { label: "이하진" });
  await p.waitForTimeout(300);
  const nt = flat(await p.textContent("#nt_body"));
  check("안내문에 지출건별 내역", /세목별 지출 내역/.test(nt), nt.slice(nt.indexOf("세목별 지출"), nt.indexOf("세목별 지출")+180));
  check("안내문에 반환 열 없음", !/반환/.test(nt.slice(0, nt.indexOf("세목별 지출"))));

  // 중간퇴소 정산
  await p.click('[data-m="exit"]');
  await p.selectOption("#st_child", await p.evaluate(() => S.children.find(c=>c.name==="이하진").id));
  await p.waitForTimeout(350);
  const ex = flat(await p.textContent("#st_sheet"));
  check("중간퇴소 정산서 — 반환할 금액", /반환할 금액/.test(ex) && !/기 반환/.test(ex), ex.slice(0,200));
  check("정산 내역 산식", /수납 .*원 − 사용 .*원 =/.test(ex));
  await p.screenshot({ path: OUT+"d-exit.png", fullPage: true });

  // 대장
  await p.click('nav button[data-tab="ledger"]');
  await p.selectOption("#lg_kind", "receipt");
  await p.waitForTimeout(400);
  const lg = flat(await p.textContent("#lg_body"));
  check("대장 비고에 입소·퇴소·위탁 표시", /퇴소/.test(lg) && /위탁/.test(lg), lg.slice(0,200));
  await p.screenshot({ path: OUT+"d-ledger.png", fullPage: true });

  await b.close();
  console.log("=== 통과 ==="); ok.forEach(s=>console.log("  ✓ "+s));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s=>console.log("  ✗ "+s)); process.exit(1); }
  console.log("모두 통과");
})();
