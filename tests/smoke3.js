/*
 * 반환-수명주기 — 브라우저 회귀 테스트
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/smoke3.js
 *
 * index.html의 경로가 다르면 아래 path 상수를 고치세요.
 */
const { chromium } = require("playwright");
const path = "file:///home/user/my-first-project/기타필요경비정산.html";
const errs = [], ok = [];
const check = (n, c, x) => (c ? ok : errs).push(n + (x ? " → " + x : ""));
const flat = s => String(s || "").replace(/\s+/g, " ");

const SEED = {
  version: 1, fiscalYear: 2026,
  classes: [{ id: "c1", name: "새싹반" }],
  children: [
    { id: "k1", name: "김서우", admitDate: "2026-03-02", leaveDate: "",           classHistory: [{ classId: "c1", startDate: "2026-03-02" }], enrollments: [] },
    { id: "k2", name: "이하람", admitDate: "2026-03-02", leaveDate: "2026-06-15", classHistory: [{ classId: "c1", startDate: "2026-03-02" }], enrollments: [] },
  ],
  items: [{ id: "it_field", name: "현장학습비", group: "기타필요경비", targetMode: "event", enabled: true }],
  rosters: [], consignPays: [], refunds: [],
  receipts: [
    { id: "rc1", childId: "k1", itemId: "it_field", date: "2026-03-05", amount: 120000, memo: "" },
    { id: "rc2", childId: "k2", itemId: "it_field", date: "2026-03-05", amount: 120000, memo: "" },
  ],
  expenses: [
    { id: "x1", date: "2026-04-10", itemId: "it_field", summary: "봄 현장학습",
      total: 50000, needAmount: 50000, cardFee: 0, operAmount: 0, memo: "", overrides: [],
      allocations: [{ childId: "k1", amount: 25000 }, { childId: "k2", amount: 25000 }] },
  ],
};

(async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const page = await browser.newPage();
  page.on("pageerror", e => errs.push("PAGE ERROR: " + e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("CONSOLE: " + m.text()); });
  await page.goto(path);
  await page.evaluate(([k, v]) => localStorage.setItem(k, JSON.stringify(v)), ["nursery-settlement-v1", SEED]);
  await page.reload();
  await page.waitForTimeout(250);

  // 반환 확정 전 — 퇴소 원아가 하반기 보고서에 남아 미정산 상태가 드러나야 한다
  await page.click('nav button[data-tab="settle"]');
  await page.click('[data-m="half"]');
  await page.selectOption("#hp_period", "H2");
  let rep = flat(await page.textContent("#hp_body"));
  check("반환 확정 전 — 퇴소 원아가 하반기 보고서에 남음(미정산 표시)",
    /이하람/.test(rep) && /95,000/.test(rep), rep.slice(rep.indexOf("순번"), rep.indexOf("순번") + 170));

  // 중간퇴소 정산 → 반환금 확정
  await page.click('[data-m="exit"]');
  await page.selectOption("#st_child", "k2");
  await page.waitForTimeout(200);
  page.once("dialog", d => d.accept());
  await page.click("#ex_fix");
  await page.waitForTimeout(400);

  const refunds = await page.evaluate(() => JSON.parse(localStorage.getItem("nursery-settlement-v1")).refunds);
  check("반환 기록 생성 (95,000원 · 622목)",
    refunds.length === 1 && refunds[0].amount === 95000 && refunds[0].date === "2026-06-15"
    && /622목/.test(refunds[0].route), JSON.stringify(refunds));

  // 반환 확정 후 — 잔액이 0이 되어 하반기 보고서에서 자동으로 빠져야 한다
  await page.click('[data-m="half"]');
  await page.selectOption("#hp_period", "H2");
  rep = flat(await page.textContent("#hp_body"));
  check("반환 확정 후 — 하반기 보고서에서 자동으로 빠짐", !/이하람/.test(rep),
    rep.slice(rep.indexOf("순번"), rep.indexOf("순번") + 170));

  // 상반기 보고서에는 반환액이 잡혀야 한다
  await page.selectOption("#hp_period", "H1");
  rep = flat(await page.textContent("#hp_body"));
  check("상반기 보고서에 반환 95,000 반영", /이하람/.test(rep) && /95,000/.test(rep),
    rep.slice(rep.indexOf("순번"), rep.indexOf("순번") + 190));

  // 원아별 현황의 반환 열
  await page.click('nav button[data-tab="child"]');
  await page.selectOption("#c_pick", "k2");
  const sum = flat(await page.textContent("#c_sum"));
  check("원아별 현황 — 수납 120,000 / 사용 25,000 / 반환 95,000 / 잔액 0",
    /120,000 25,000 95,000 0/.test(sum), sum.slice(0, 190));

  await browser.close();
  console.log("=== 통과 ==="); ok.forEach(s => console.log("  ✓ " + s));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s => console.log("  ✗ " + s)); process.exit(1); }
  console.log("모두 통과");
})();
