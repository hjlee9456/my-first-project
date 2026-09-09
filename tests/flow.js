/*
 * 전체 흐름 회귀 테스트 — 기초설정부터 정산·보고까지 화면으로 훑는다.
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/flow.js
 */
const { chromium } = require("playwright");
const errs = [], ok = [];
const check = (n,c,x) => (c?ok:errs).push(n + (x?" → "+x:""));
const flat = s => String(s||"").replace(/\s+/g," ");

(async () => {
  const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const p = await b.newPage({ viewport:{width:1500,height:950} });
  p.on("pageerror", e => errs.push("PAGE ERROR: " + e.message));
  p.on("console", m => { if (m.type()==="error") errs.push("CONSOLE: " + m.text()); });
  await p.goto("file:///home/user/my-first-project/기타필요경비정산.html");
  await p.waitForTimeout(300);

  // ---- 기초설정: 반 2개 ----
  for (const n of ["새싹반","풀잎반"]) { await p.fill("#newClass", n); await p.click("#addClass"); }

  // ---- 세목: 현장학습비 1인당 수납액 30,000 ----
  const stdIn = p.locator('#itemList tr[data-item="it_field"] input[data-k="std"]');
  await stdIn.fill("30000");
  await stdIn.blur();
  await p.waitForTimeout(150);

  // ---- 원아 4명: 반을 드롭다운에서 바로 선택 ----
  const kids = [["김서우","새싹반"],["이하람","새싹반"],["박도윤","풀잎반"],["최지안","풀잎반"]];
  for (const [name, cls] of kids) {
    await p.click("#addChild");
    await p.fill("#m_name", name);
    await p.selectOption("#m_class", { label: cls });
    await p.fill("#m_admit", "2026-03-02");
    await p.click(".modal .foot button.pri");
    await p.waitForSelector(".mask", { state: "detached" });
  }
  check("원아 추가 시 반을 바로 선택", (await p.locator("#childList tbody tr").count()) === 4);
  const setupTxt = flat(await p.textContent("#childList"));
  check("명부에 반이 채워짐", /새싹반/.test(setupTxt) && /풀잎반/.test(setupTxt), setupTxt.slice(0,140));

  // ---- 반 이동 버튼 ----
  await p.locator("#childList tbody tr", { hasText: "김서우" }).locator('[data-a="move"]').click();
  await p.selectOption("#mv_class", { label: "풀잎반" });
  await p.fill("#mv_date", "2026-09-01");
  await p.click(".modal .foot button.pri");
  await p.waitForSelector(".mask", { state: "detached" });
  const hist = await p.evaluate(() => S.children.find(c=>c.name==="김서우").classHistory.length);
  check("반 이동이 이력으로 쌓임", hist === 2, hist + "건");

  // ---- 최지안: 10월부터 위탁 ----
  await p.locator("#childList tbody tr", { hasText: "최지안" }).locator('[data-a="edit"]').click();
  await p.click("#m_addConsign");
  await p.fill('#m_consign input[data-k="s"]', "2026-10");
  await p.fill('#m_consign input[data-k="emp"]', "○○병원");
  await p.click(".modal .foot button.pri");
  await p.waitForSelector(".mask", { state: "detached" });
  check("위탁 기간이 월 단위로 저장", await p.evaluate(() =>
    S.children.find(c=>c.name==="최지안").consignPeriods[0].startMonth === "2026-10"));

  // ---- 수납결의서 ----
  await p.click('nav button[data-tab="receipt"]');
  await p.fill("#rc_date", "2026-03-20");
  await p.fill("#rc_no", "6");
  await p.selectOption("#rc_item", { label: "현장학습비" });
  await p.fill("#rc_summary", "기타필요경비-현장학습비 1분기");
  await p.fill("#rc_account", "신한12600409");
  await p.locator("#rc_pick .pk-class", { hasText: "새싹반" }).locator('[data-a="g-all"]').click();
  await p.waitForTimeout(150);
  await p.click("#rc_std");   // 기초설정 30,000원 쓰기
  await p.waitForTimeout(150);
  const amts = await p.$$eval("#rc_lines input.money", els => els.map(e => e.value));
  const totalCell = flat(await p.textContent("#rc_total"));
  check("기초설정 1인당 수납액이 자동으로 채워짐",
    amts.length === 2 && amts.every(a => a === "30,000") && totalCell === "60,000",
    amts.join(" / ") + " 합계 " + totalCell);
  await p.click("#rc_save");
  await p.waitForTimeout(300);
  const vlist = flat(await p.textContent("#rc_list"));
  check("수납결의서가 번호·계좌와 함께 기록됨",
    /신한12600409/.test(vlist) && /이하람/.test(vlist) && /김서우/.test(vlist) && /60,000/.test(vlist),
    vlist.slice(vlist.indexOf("2026-03-20"), vlist.indexOf("2026-03-20")+120));

  // 두 번째 결의서 (풀잎반, 다른 날짜)
  await p.fill("#rc_date", "2026-03-21");
  await p.fill("#rc_no", "13");
  await p.selectOption("#rc_item", { label: "현장학습비" });
  await p.locator("#rc_pick .pk-class", { hasText: "풀잎반" }).locator('[data-a="g-all"]').click();
  await p.waitForTimeout(150);
  await p.click("#rc_std");
  await p.click("#rc_save");
  await p.waitForTimeout(300);
  check("여러 날짜에 나눠 들어온 수납이 각각 기록됨",
    (await p.evaluate(() => S.vouchers.length)) === 2);
  check("수납 기록이 결의서에서 파생됨", (await p.evaluate(() => S.receipts.length)) === 4);

  // ---- 지출: 결의서 번호 + 10월(위탁월) 지출 ----
  await p.click('nav button[data-tab="expense"]');
  await p.fill("#e_date", "2026-10-08");
  await p.fill("#e_no", "104");
  await p.selectOption("#e_item", { label: "현장학습비" });
  await p.fill("#e_summary", "가을 현장학습 버스");
  await p.fill("#e_total", "80000");
  await p.click("#e_allNeed");
  await p.locator('#e_pick [data-a="all"]').click();
  await p.waitForTimeout(200);
  const prev = flat(await p.textContent("#e_preview"));
  check("배분 미리보기 (4명 × 20,000)", /대상 4명/.test(prev) && /20,000원/.test(prev), prev.slice(0,150));
  await p.click("#e_save");
  await p.waitForTimeout(300);
  const elist = flat(await p.textContent("#e_list"));
  check("지출 목록에 결의서 번호 표시", /104/.test(elist), elist.slice(0,180));

  // ---- 위탁 충당 확인: 최지안은 10월이 위탁월 ----
  await p.click('nav button[data-tab="child"]');
  await p.selectOption("#c_pick", { label: "최지안" });
  await p.waitForTimeout(200);
  const cs = flat(await p.textContent("#c_sum"));
  check("위탁 월 지출이 사용액이 아니라 「위탁 충당」으로 잡힘",
    /위탁 충당/.test(cs) && /30,000 0 20,000/.test(cs.replace(/,(?=\d{3}\b)/g, m=>m)) || /20,000/.test(cs),
    cs.slice(0,240));
  const leftJ = await p.evaluate(() => balance(S.children.find(c=>c.name==="최지안").id, "it_field", "2026-03-01","2027-02-28"));
  check("최지안 잔액 = 수납 30,000 − 사용 0 = 30,000 (위탁 충당 20,000 별도)",
    leftJ.paid===30000 && leftJ.used===0 && leftJ.consign===20000 && leftJ.left===30000, JSON.stringify(leftJ));
  const leftS = await p.evaluate(() => balance(S.children.find(c=>c.name==="김서우").id, "it_field", "2026-03-01","2027-02-28"));
  check("김서우(일반) 잔액 = 30,000 − 20,000 = 10,000",
    leftS.used===20000 && leftS.left===10000, JSON.stringify(leftS));

  // ---- 정산보고서: 임의 기간 ----
  await p.click('nav button[data-tab="settle"]');
  const order = await p.$$eval("#panel .row.no-print button.b", bs => bs.slice(0,3).map(b=>b.textContent.trim()));
  check("중간퇴소 버튼이 맨 오른쪽", order[2] && order[2].includes("중간퇴소"), order.join(" | "));
  await p.click('[data-m="half"]');
  await p.selectOption("#hp_from", "2026-09");
  await p.selectOption("#hp_to", "2026-11");
  await p.waitForTimeout(200);
  const rep = flat(await p.textContent("#hp_body"));
  check("시작월·마지막월을 골라 임의 기간으로 정산", /9월 ~ 11월/.test(rep) && /2026-09-01 ~ 2026-11-30/.test(rep), rep.slice(0,170));
  check("기간이 3월부터가 아니면 이월 열이 생김", /이월/.test(rep));
  check("본문 97p 인용문이 빠짐", !/본문 97p/.test(rep));
  check("위탁 충당 열 표시", /위탁 충당/.test(rep));

  // ---- 보호자용 안내문: 지출건별 내역 ----
  await p.click('[data-m="notice"]');
  await p.selectOption("#nt_child", { label: "김서우" });
  await p.waitForTimeout(250);
  const nt = flat(await p.textContent("#nt_body"));
  check("안내문에 세목별 지출건 내역이 들어감",
    /세목별 지출 내역/.test(nt) && /가을 현장학습 버스/.test(nt) && /104/.test(nt), nt.slice(nt.indexOf("세목별 지출"), nt.indexOf("세목별 지출")+220));

  // ---- 정산 반환 확정 버튼이 없어야 함 ----
  await p.click('[data-m="exit"]');
  await p.waitForTimeout(250);
  check("반환금 확정 버튼이 삭제됨", (await p.locator("#ex_fix").count()) === 0);

  // ---- 설명서 근거자료 ----
  await p.click('nav button[data-tab="manual"]');
  await p.click('[data-m="faq"]');
  const man = flat(await p.textContent("#mn_body"));
  check("설명서 상단에 근거자료 약칭 명시",
    /이 설명서가 인용하는 근거 자료/.test(man) && /보육사업안내/.test(man) && /재무회계 매뉴얼/.test(man), man.slice(0,200));
  await p.fill("#fq", "반납결의");
  await p.waitForTimeout(150);
  const faq = flat(await p.textContent("#fqlist"));
  check("반납결의를 쉽게 풀어 설명", /지출 결재를 올려/.test(faq), faq.slice(0,220));
  await p.fill("#fq", "한도액");
  await p.waitForTimeout(150);
  check("한도액 FAQ 삭제됨", /찾는 상황이 없습니다/.test(flat(await p.textContent("#fqlist"))));

  // ---- 목 이름 병기 ----
  await p.click('nav button[data-tab="setup"]');
  const grp = flat(await p.textContent("#itemList"));
  check("목 번호에 이름 병기", /221목 기타필요경비/.test(grp), grp.slice(0,150));

  if (process.env.SHOT_DIR) await p.screenshot({ path: process.env.SHOT_DIR + "flow.png", fullPage: true });
  await b.close();
  console.log("=== 통과 ==="); ok.forEach(s=>console.log("  ✓ "+s));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s=>console.log("  ✗ "+s)); process.exit(1); }
  console.log("모두 통과");
})();
