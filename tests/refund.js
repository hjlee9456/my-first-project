/*
 * 반환 기록 회귀 테스트 —
 *   「반환 완료로 표시」를 누르면 그 금액이 반환 정산서에서 빠지고
 *   운영위 보고서의 「반환액」·검증 대사·원아별 현황에 그대로 따라붙는지,
 *   「반환 완료 취소」로 원래 숫자로 되돌아오는지.
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/refund.js
 */
const { chromium } = require("playwright");
const PATH = "file:///home/user/my-first-project/기타필요경비정산.html";

const errs = [], ok = [];
const check = (n, c, x) => (c ? ok : errs).push(n + (x ? " → " + x : ""));
const flat = s => String(s || "").replace(/\s+/g, " ");

/* 김서우는 재원 중, 이하람은 6월 15일 퇴소.
   현장학습비만 쓰므로 숫자를 손으로 따라갈 수 있다.
     이하람 수납 120,000 − 사용 25,000 = 반환할 금액 95,000 */
const SEED = {
  version: 1, fiscalYear: 2026,
  classes: [{ id: "c1", name: "새싹반" }],
  children: [
    { id: "k1", name: "김서우", admitDate: "2026-03-02", leaveDate: "",
      classHistory: [{ classId: "c1", startDate: "2026-03-02" }], consignPeriods: [] },
    { id: "k2", name: "이하람", admitDate: "2026-03-02", leaveDate: "2026-06-15",
      classHistory: [{ classId: "c1", startDate: "2026-03-02" }], consignPeriods: [] },
  ],
  items: [
    { id: "it_field", name: "현장학습비", group: "기타필요경비", targetMode: "event", enabled: true, stdAmount: 30000 },
  ],
  rosters: [],
  vouchers: [
    { id: "v1", date: "2026-03-20", voucherNo: "6", itemId: "it_field",
      summary: "기타필요경비-현장학습비 1분기", perAmount: 120000, cardFee: 0,
      lines: [{ childId: "k1", amount: 120000, memo: "" }, { childId: "k2", amount: 120000, memo: "" }],
      total: 240000 },
  ],
  receipts: [],
  expenses: [
    { id: "x1", date: "2026-04-10", voucherNo: "31", itemId: "it_field", summary: "봄 현장학습 입장료",
      total: 50000, needAmount: 50000, operAmount: 0, memo: "", overrides: [],
      allocations: [{ childId: "k1", amount: 25000 }, { childId: "k2", amount: 25000 }] },
  ],
};

(async () => {
  const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  p.on("pageerror", e => errs.push("PAGE ERROR: " + e.message));
  p.on("console", m => { if (m.type() === "error") errs.push("CONSOLE: " + m.text()); });
  p.on("dialog", d => d.accept());

  await p.goto(PATH);
  await p.evaluate(([k, v]) => {
    localStorage.setItem(k, JSON.stringify(v));
    localStorage.setItem("centerName", "여수시립 햇살어린이집");
  }, ["nursery-settlement-v1", SEED]);
  await p.reload();
  await p.waitForTimeout(350);

  const backSheet = async () => {
    await p.click('nav button[data-tab="settle"]');
    await p.click('[data-m="back"]');
    await p.click('[data-p="Y"]').catch(() => {});
    await p.waitForTimeout(250);
    return flat(await p.textContent("#bk_body"));
  };
  const halfSheet = async () => {
    await p.click('nav button[data-tab="settle"]');
    await p.click('[data-m="half"]');
    await p.click('[data-p="Y"]').catch(() => {});
    await p.waitForTimeout(250);
    return flat(await p.textContent("#hp_body"));
  };

  // ================= 표시하기 전 =================
  let bk = await backSheet();
  check("반환 정산서에 퇴소 원아가 돌려줄 금액과 함께 나옴",
    /이하람/.test(bk) && /95,000/.test(bk), bk.slice(bk.indexOf("순번"), bk.indexOf("순번") + 220));

  let hp = await halfSheet();
  check("아직 반환액 열은 없음", !/반환액/.test(hp));
  check("미집행액 합계는 190,000 (240,000 − 50,000)",
    /미집행액 합계 \(보호자에게 남은 금액\) 190,000원/.test(hp),
    hp.slice(hp.indexOf("미집행액"), hp.indexOf("미집행액") + 60));

  // ================= 중간퇴소 정산서에서 반환 완료로 표시 =================
  await p.click('[data-m="exit"]');
  await p.waitForTimeout(250);
  await p.selectOption("#st_child", "k2");
  await p.waitForTimeout(300);
  check("퇴소 원아 정산서에 반환할 금액 95,000", /95,000/.test(flat(await p.textContent("#st_sheet"))));
  check("표시하기 전에는 「반환 완료로 표시」 버튼", (await p.locator("#ex_mark").count()) === 1);

  await p.fill("#ex_rdate", "2026-06-25");
  await p.click("#ex_mark");
  await p.waitForTimeout(350);

  const saved = await p.evaluate(() => S.refunds.map(r => [r.date, r.childId, r.itemId, r.amount]));
  check("반환 기록이 세목별로 남음",
    saved.length === 1 && saved[0][0] === "2026-06-25" && saved[0][1] === "k2"
      && saved[0][2] === "it_field" && saved[0][3] === 95000, JSON.stringify(saved));
  const exSheet = flat(await p.textContent("#st_sheet"));
  check("정산서에 반환 완료가 날짜별로 뜸",
    /반환 완료 — 보호자반환금\(622목\)으로 95,000원/.test(exSheet) && /2026-06-25 95,000원/.test(exSheet),
    exSheet.slice(exSheet.indexOf("반환 완료"), exSheet.indexOf("반환 완료") + 110));
  check("표시한 뒤에는 「반환 완료 취소」 버튼", (await p.locator("#ex_unmark").count()) === 1);

  // ================= 표시한 뒤 각 화면 =================
  bk = await backSheet();
  const hrRow = flat(await p.locator("#bk_body tbody tr", { hasText: "이하람" }).textContent());
  check("반환 정산서에서 이미 돌려준 금액이 빠짐",
    /06\.25 반환완료 95,000원/.test(hrRow) && !/95,000 95,000/.test(hrRow), hrRow);
  check("돌려주지 않은 원아는 그대로 남음",
    /95,000 95,000/.test(flat(await p.locator("#bk_body tbody tr", { hasText: "김서우" }).textContent())));
  check("합계는 아직 돌려줄 95,000원만",
    /합계 \(2명\) 95,000 95,000/.test(bk), bk.slice(bk.indexOf("합계 (2명)"), bk.indexOf("합계 (2명)") + 40));

  hp = await halfSheet();
  check("운영위 보고서에 반환액 열이 붙고 연간 누계임을 밝힘",
    /반환액 \(연간 누계\)\(C\)/.test(hp),
    hp.slice(hp.indexOf("세목계정과목"), hp.indexOf("세목계정과목") + 200));
  check("미집행액 = 남은 금액 − 반환액 (190,000 − 95,000)",
    /남은 금액 \(수납 − 사용\)\(A\) 190,000원/.test(hp)
      && /반환액 \(622목 보호자반환금 · 연간 누계\)\(B\) 95,000원/.test(hp)
      && /미집행액 합계 \(보호자에게 남은 금액\)\(C = A − B\) 95,000원/.test(hp),
    hp.slice(hp.indexOf("남은 금액 (수납"), hp.indexOf("남은 금액 (수납") + 160));

  await p.click('nav button[data-tab="check"]');
  await p.waitForTimeout(250);
  const chk = flat(await p.textContent("main"));
  check("검증 대사에 이미 반환한 금액이 한 줄로 들어감",
    /이미 반환한 금액 \(622목 보호자반환금\)\(C\) 95,000원/.test(chk)
      && /장부 차액\(D = A − B − C\) 95,000원/.test(chk),
    chk.slice(chk.indexOf("보호자 수납 합계"), chk.indexOf("보호자 수납 합계") + 220));
  /* 세목을 서로 상계하지 않으므로 「돌려줄 돈」은 세목별 남은 몫의 합이다 */
  check("검증에 돌려줄 돈과 메워야 할 돈이 따로 나옴",
    /돌려줄 돈 \(세목별 남은 몫의 합\)\(A\) 95,000원/.test(chk)
      && /메워야 할 돈 \(세목별 모자란 몫의 합\)\(B\) 0원/.test(chk),
    chk.slice(chk.indexOf("돌려줄 돈과"), chk.indexOf("돌려줄 돈과") + 140));

  await p.click('nav button[data-tab="child"]');
  await p.waitForTimeout(200);
  await p.selectOption("#c_class", "");
  await p.waitForTimeout(150);
  await p.selectOption("#c_pick", "k2");
  await p.waitForTimeout(250);
  const cs = flat(await p.textContent("#c_sum"));
  check("원아별 현황에 반환액 열과 미집행액",
    /반환액 \(연간 누계\)\(C\)/.test(cs) && /미집행액\(D = A − B − C\)/.test(cs) && /95,000/.test(cs),
    cs.slice(cs.indexOf("세목구분"), cs.indexOf("세목구분") + 200));
  check("돌려준 내역이 622목 안내와 함께 적힘",
    /622목 보호자반환금.*이미 돌려준/.test(cs), cs.slice(cs.indexOf("622목"), cs.indexOf("622목") + 90));

  // ================= 새로고침해도 남는가 =================
  await p.reload();
  await p.waitForTimeout(350);
  check("새로고침해도 반환 기록이 그대로",
    (await p.evaluate(() => S.refunds.length)) === 1);
  check("백업 자료에 반환 기록이 담김",
    (await p.evaluate(() => JSON.parse(localStorage.getItem("nursery-settlement-v1")).years["2026"].refunds.length)) === 1);

  // ================= 반환 완료 취소 =================
  await p.click('nav button[data-tab="settle"]');
  await p.click('[data-m="back"]');
  await p.click('[data-p="Y"]').catch(() => {});
  await p.waitForTimeout(250);
  await p.locator("#bk_body tbody tr", { hasText: "이하람" }).locator("button").click();
  await p.waitForTimeout(350);
  check("취소하면 반환 기록이 지워짐", (await p.evaluate(() => S.refunds.length)) === 0);

  bk = flat(await p.textContent("#bk_body"));
  check("취소하면 다시 돌려줄 금액으로 잡힘",
    /이하람/.test(bk) && /95,000/.test(bk) && !/반환완료/.test(bk),
    bk.slice(bk.indexOf("이하람"), bk.indexOf("이하람") + 120));

  hp = await halfSheet();
  check("취소하면 보고서의 반환액 열도 사라지고 미집행액이 돌아옴",
    !/반환액/.test(hp) && /미집행액 합계 \(보호자에게 남은 금액\) 190,000원/.test(hp),
    hp.slice(hp.indexOf("미집행액"), hp.indexOf("미집행액") + 60));

  // ================= 입학준비금 협의금액이 저장되는가 =================
  await p.evaluate(() => {
    S.items.push({ id: "it_prep", name: "입학준비금", group: "기타필요경비",
                   targetMode: "fixed", enabled: true, special: "prep", stdAmount: 0 });
    S.vouchers.push({ id: "v2", date: "2026-03-20", voucherNo: "7", itemId: "it_prep",
                      summary: "입학준비금", perAmount: 0, cardFee: 0,
                      lines: [{ childId: "k2", amount: 90000, memo: "" }], total: 90000 });
    rebuildReceipts(); save(); render();
  });
  await p.waitForTimeout(300);
  await p.click('[data-m="exit"]');
  await p.waitForTimeout(250);
  await p.selectOption("#st_child", "k2");
  await p.waitForTimeout(300);
  await p.locator('#st_sheet [data-r="back"] input').fill("40,000");
  await p.locator('#st_sheet [data-r="back"] input').press("Enter");
  await p.waitForTimeout(350);
  await p.reload();
  await p.waitForTimeout(350);
  check("입학준비금 협의금액이 새로고침 뒤에도 남음",
    (await p.evaluate(() => childById("k2").prepBack)) === 40000,
    String(await p.evaluate(() => childById("k2").prepBack)));

  if (process.env.SHOT_DIR) await p.screenshot({ path: process.env.SHOT_DIR + "refund.png", fullPage: true });
  await b.close();

  console.log("=== 통과 ==="); ok.forEach(s => console.log("  ✓ " + s));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s => console.log("  ✗ " + s)); process.exit(1); }
  console.log("모두 통과");
})();
