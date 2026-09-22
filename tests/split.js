/*
 * 「원아별로 나누기」 — 4분기에 원아마다 잔액이 달라 균등배분이 맞지 않을 때.
 *
 * 지출결의서는 달이 지나면 확정되어 나중에 쪼갤 수 없으므로,
 * 그 달에 등록하면서 잔액까지만 담고 남는 몫을 운영비 부담분으로 넘겨야 한다.
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/split.js
 */
const { chromium } = require("playwright");
const PATH = "file:///home/user/my-first-project/기타필요경비정산.html";
const errs = [], ok = [];
const check = (n, c, x) => (c ? ok : errs).push(n + (x ? " → " + x : ""));
const flat = s => String(s || "").replace(/\s+/g, " ");

/* 수납이 저마다 다르다 — 김서우 100,000 · 이하람 60,000 · 박도윤 30,000 */
const SEED = {
  version: 1, fiscalYear: 2026, classes: [{ id: "c1", name: "새싹반" }],
  children: ["김서우", "이하람", "박도윤"].map((name, i) => ({
    id: "k" + (i + 1), name, admitDate: "2026-03-02", leaveDate: "",
    classHistory: [{ classId: "c1", startDate: "2026-03-02" }], consignPeriods: [] })),
  items: [{ id: "it_field", name: "현장학습비", group: "기타필요경비",
            targetMode: "event", enabled: true, stdAmount: 0 }],
  rosters: [],
  vouchers: [{ id: "v1", date: "2026-03-10", voucherNo: "1", itemId: "it_field", summary: "수납",
               perAmount: 0, cardFee: 0, total: 190000,
               lines: [{ childId: "k1", amount: 100000, memo: "" },
                       { childId: "k2", amount: 60000, memo: "" },
                       { childId: "k3", amount: 30000, memo: "" }] }],
  receipts: [], expenses: [],
};

(async () => {
  const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const p = await b.newPage({ viewport: { width: 1500, height: 1000 } });
  p.on("pageerror", e => errs.push("PAGE ERROR: " + e.message));
  p.on("dialog", d => d.accept());

  await p.goto(PATH);
  await p.evaluate(v => localStorage.setItem("nursery-settlement-v1", JSON.stringify(v)), SEED);
  await p.reload(); await p.waitForTimeout(450);

  // 4분기(1월) 지출 150,000원을 3명에게
  await p.click('nav button[data-tab="expense"]'); await p.waitForTimeout(300);
  await p.fill("#e_date", "2027-01-20"); await p.dispatchEvent("#e_date", "change");
  await p.waitForTimeout(350);
  await p.fill("#e_summary", "겨울 현장학습");
  await p.fill("#e_total", "150,000"); await p.dispatchEvent("#e_total", "change");
  await p.click("#e_allNeed"); await p.waitForTimeout(250);
  await p.evaluate(() => { ["k1","k2","k3"].forEach(id => view.expenseForm.targets.add(id));
                           view.expenseForm.keep = true; render(); });
  await p.waitForTimeout(450);

  let pv = flat(await p.textContent("#e_preview"));
  check("균등배분이 기본", /1인당 50,000원/.test(pv) && /배분 합계 150,000원/.test(pv), pv.slice(0, 70));
  check("4분기라 잔액 부족 경고가 뜸", /잔액이 모자랍니다/.test(pv));
  check("경고가 「원아별로 나누기」를 가리킴", /원아별로 나누기/.test(pv));
  check("「원아별로 나누기」 버튼이 있음", (await p.locator("#e_split2").count()) === 1);

  // 창을 열고 잔액 확인
  await p.click("#e_split2"); await p.waitForTimeout(400);
  const rows = (await p.locator('#modalHost tbody[data-r="rows"] tr').allTextContents()).map(flat);
  check("원아마다 그 세목 잔액이 보임",
    rows.some(r => /김서우 100,000/.test(r)) && rows.some(r => /박도윤 30,000/.test(r)),
    rows.join(" | "));
  check("잔액을 넘기는 원아를 짚어 줌", rows.some(r => /박도윤/.test(r) && /잔액 넘김/.test(r)));

  // 잔액까지만 나누기
  await p.locator('#modalHost [data-a="cap"]').click(); await p.waitForTimeout(400);
  const foot = flat(await p.locator('#modalHost tbody[data-r="foot"]').textContent());
  check("잔액까지만 나누면 배분 합계 130,000 · 운영비 20,000",
    /배분 합계 → 필요경비 부담분이 됩니다 130,000원/.test(foot)
      && /남는 몫 → 운영비 부담분 20,000원/.test(foot), foot);
  check("지출결의서 총액은 그대로 150,000", /지출결의서 총액150,000원/.test(foot));

  await p.locator('#modalHost .modal .foot button', { hasText: "저장" }).click();
  await p.waitForTimeout(450);
  check("화면이 「원아별로 나눔」으로 바뀜",
    /원아별로 나눔 \(균등배분 아님\)/.test(flat(await p.textContent("#e_preview"))));
  check("필요경비·운영비 칸이 따라옴",
    (await p.inputValue("#e_need")) === "130,000" && (await p.inputValue("#e_oper")) === "20,000",
    (await p.inputValue("#e_need")) + " / " + (await p.inputValue("#e_oper")));
  check("경고가 사라짐", !/잔액이 모자랍니다/.test(flat(await p.textContent("#e_preview"))));

  // 저장
  await p.click("#e_save"); await p.waitForTimeout(500);
  const rec = await p.evaluate(() => {
    const e = S.expenses[0];
    return { need: e.needAmount, oper: e.operAmount, total: e.total, even: isEvenSplit(e),
             alloc: e.allocations.map(a => childName(a.childId) + " " + a.amount).join(", ") };
  });
  check("저장된 지출건이 잔액대로 나뉨",
    rec.need === 130000 && rec.oper === 20000 && rec.total === 150000
      && /박도윤 30000/.test(rec.alloc), JSON.stringify(rec));
  check("배분 합계 = 필요경비 부담분 (1원도 안 어긋남)", rec.need === 130000);
  check("균등배분이 아님을 알아봄", rec.even === false);

  // 명단 인쇄물에 배분 방식이 적힘
  await p.click('nav button[data-tab="child"]'); await p.waitForTimeout(350);
  await p.selectOption("#c_class", ""); await p.waitForTimeout(150);
  await p.selectOption("#c_pick", "k3"); await p.waitForTimeout(350);
  await p.locator("#c_use button.link").first().click(); await p.waitForTimeout(400);
  const modal = flat(await p.textContent("#modalHost"));
  check("명단에 「원아별 배분」과 그 사유가 적힘",
    /원아별 배분/.test(modal) && /잔액 한도로 나눴습니다/.test(modal),
    modal.slice(modal.indexOf("배분 방식"), modal.indexOf("배분 방식") + 90));
  await p.keyboard.press("Escape"); await p.waitForTimeout(200);

  // 고쳐 열면 그 금액을 이어받는다
  await p.evaluate(() => { view.expenseEditId = S.expenses[0].id; view.expenseForm = null; goTab("expense"); });
  await p.waitForTimeout(450);
  check("고쳐 열어도 원아별 금액을 이어받음",
    /원아별로 나눔/.test(flat(await p.textContent("#e_preview")))
      && (await p.inputValue("#e_need")) === "130,000");

  // 균등배분으로 되돌리기
  await p.click("#e_even"); await p.waitForTimeout(400);
  check("「균등배분으로 되돌리기」가 먹음",
    /1인당/.test(flat(await p.textContent("#e_preview")))
      && !/원아별로 나눔/.test(flat(await p.textContent("#e_preview"))));

  await b.close();
  console.log("=== 통과 ==="); ok.forEach(s => console.log("  ✓ " + s));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s => console.log("  ✗ " + s)); process.exit(1); }
  console.log("모두 통과");
})();
