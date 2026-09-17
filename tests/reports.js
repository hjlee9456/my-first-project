/*
 * 산출물 회귀 테스트 — 대장·중간퇴소 정산서·정산보고서·보호자 안내문.
 * 자료를 직접 심어 놓고 숫자가 그대로 나오는지 본다.
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/reports.js
 */
const { chromium } = require("playwright");
const PATH = "file:///home/user/my-first-project/기타필요경비정산.html";

const errs = [], ok = [];
const check = (n, c, x) => (c ? ok : errs).push(n + (x ? " → " + x : ""));
const flat = s => String(s || "").replace(/\s+/g, " ");

const SEED = {
  version: 1, fiscalYear: 2026,
  classes: [{ id: "c1", name: "새싹반" }, { id: "c2", name: "풀잎반" }],
  children: [
    { id: "k1", name: "김서우", admitDate: "2026-03-02", leaveDate: "",
      classHistory: [{ classId: "c1", startDate: "2026-03-02" }], consignPeriods: [] },
    { id: "k2", name: "이하람", admitDate: "2026-03-02", leaveDate: "2026-06-15",
      classHistory: [{ classId: "c1", startDate: "2026-03-02" }], consignPeriods: [] },
    { id: "k3", name: "박도윤", admitDate: "2026-03-02", leaveDate: "",
      classHistory: [{ classId: "c2", startDate: "2026-03-02" }], consignPeriods: [] },
    /* 10월부터 위탁 — 10월 지출은 위탁보육료로 충당된다 */
    { id: "k4", name: "최지안", admitDate: "2026-03-02", leaveDate: "",
      classHistory: [{ classId: "c2", startDate: "2026-03-02" }],
      consignPeriods: [{ id: "cp1", startMonth: "2026-10", endMonth: null, employer: "○○병원" }] },
  ],
  items: [
    { id: "it_prep",  name: "입학준비금", group: "기타필요경비", targetMode: "fixed", enabled: true, special: "prep", stdAmount: 0 },
    { id: "it_field", name: "현장학습비", group: "기타필요경비", targetMode: "event", enabled: true, stdAmount: 30000 },
    { id: "it_bus",   name: "차량운행비", group: "기타필요경비", targetMode: "fixed", enabled: true, stdAmount: 0 },
  ],
  rosters: [],
  vouchers: [
    { id: "v1", date: "2026-03-20", voucherNo: "6", itemId: "it_field",
      summary: "기타필요경비-현장학습비 1분기", account: "신한12600409", perAmount: 120000,
      lines: [{ childId: "k1", amount: 120000, memo: "" }, { childId: "k2", amount: 120000, memo: "" },
              { childId: "k3", amount: 120000, memo: "" }, { childId: "k4", amount: 120000, memo: "" }],
      total: 480000 },
    { id: "v2", date: "2026-03-20", voucherNo: "7", itemId: "it_prep",
      summary: "기타필요경비-입학준비금", account: "신한12600409", perAmount: 0,
      lines: [{ childId: "k1", amount: 90000, memo: "원복+가방" }, { childId: "k2", amount: 50000, memo: "원복만" }],
      total: 140000 },
  ],
  receipts: [],
  expenses: [
    /* 상반기 — 4명에게 100,000 → 25,000씩 */
    { id: "x1", date: "2026-04-10", voucherNo: "31", itemId: "it_field", summary: "봄 현장학습 입장료",
      total: 100000, needAmount: 100000, cardFee: 0, operAmount: 0, memo: "", overrides: [],
      allocations: [{ childId: "k1", amount: 25000 }, { childId: "k2", amount: 25000 },
                    { childId: "k3", amount: 25000 }, { childId: "k4", amount: 25000 }] },
    /* 이하람이 퇴소한 달(6월) 월단위 지출 — 이하람은 빠져 있다 */
    { id: "x2", date: "2026-06-25", voucherNo: "58", itemId: "it_bus", summary: "6월 유류비",
      total: 100000, needAmount: 90000, cardFee: 1000, operAmount: 9000, memo: "", overrides: [],
      allocations: [{ childId: "k1", amount: 30000 }, { childId: "k3", amount: 30000 }, { childId: "k4", amount: 30000 }] },
    /* 하반기 10월 — 최지안은 이 달부터 위탁이라 위탁보육료로 충당된다 */
    { id: "x3", date: "2026-10-08", voucherNo: "104", itemId: "it_field", summary: "가을 현장학습 버스",
      total: 90000, needAmount: 90000, cardFee: 0, operAmount: 0, memo: "", overrides: [],
      allocations: [{ childId: "k1", amount: 30000 }, { childId: "k3", amount: 30000 }, { childId: "k4", amount: 30000 }] },
  ],
};

(async () => {
  const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  p.on("pageerror", e => errs.push("PAGE ERROR: " + e.message));
  p.on("console", m => { if (m.type() === "error") errs.push("CONSOLE: " + m.text()); });

  await p.goto(PATH);
  await p.evaluate(([k, v]) => {
    localStorage.setItem(k, JSON.stringify(v));
    localStorage.setItem("centerName", "여수시립 햇살어린이집");
  }, ["nursery-settlement-v1", SEED]);
  await p.reload();
  await p.waitForTimeout(350);

  check("수납결의서에서 원아별 수납 기록이 만들어짐",
    (await p.evaluate(() => S.receipts.length)) === 6);

  // ================= 대장 =================
  await p.click('nav button[data-tab="ledger"]');
  await p.selectOption("#lg_kind", "expense");
  await p.selectOption("#lg_item", "");
  let lg = flat(await p.textContent("#lg_body"));
  check("지출대장이 아동 × 계정과목 행 중첩 구조",
    /계정과목/.test(lg) && /현장학습비/.test(lg) && /차량운행비/.test(lg), lg.slice(0, 190));
  check("반·아동 칸이 세목 행만큼 병합됨",
    (await p.locator("#lg_body tbody td[rowspan]").count()) > 0);
  check("인쇄 머리글에 어린이집 이름", /여수시립 햇살어린이집/.test(lg));

  await p.selectOption("#lg_kind", "receipt");
  await p.selectOption("#lg_item", "it_field");
  lg = flat(await p.textContent("#lg_body"));
  check("수입대장에 수납결의서 금액이 수납일 달에 들어감",
    /120,000/.test(lg), lg.slice(0, 200));
  check("대장 비고에 퇴소·위탁이 자동으로 들어감",
    /06\.15 퇴소/.test(lg) && /10월부터 위탁/.test(lg), lg.slice(0, 300));

  // ================= 중간퇴소 정산 =================
  await p.click('nav button[data-tab="settle"]');
  await p.click('[data-m="exit"]');
  await p.selectOption("#st_child", "k2");
  await p.waitForTimeout(250);
  check("퇴소일이 자동으로 반영됨", (await p.inputValue("#st_asof")) === "2026-06-15");

  const mq = flat(await p.textContent("#st_month"));
  check("퇴소한 달 지출건을 하나씩 물어봄",
    /6월 유류비/.test(mq) && /기준일 이후/.test(mq), mq.slice(0, 150));

  let sheet = flat(await p.textContent("#st_sheet"));
  check("현장학습비 반환할 금액 95,000 (120,000 − 25,000)", /95,000/.test(sheet));
  check("입학준비금은 협의 표시", /협의/.test(sheet));
  check("정산 내역이 표로 맨 앞에 나옴",
    /정산 내역 세목 ?수납액 \(결제하신 금액\)\(A\)/.test(sheet) && /반환할 금액\(C = A − B\)/.test(sheet) && sheet.indexOf("정산 내역") < sheet.indexOf("산출 근거"),
    sheet.slice(sheet.indexOf("정산 내역"), sheet.indexOf("정산 내역") + 170));
  check("반환금 확정 버튼은 없음", (await p.locator("#ex_fix").count()) === 0);

  // 6월 유류비를 사유와 함께 포함시킨다
  const row = p.locator("#st_month tbody tr", { hasText: "6월 유류비" });
  await row.locator("td:last-child input").fill("6월 15일까지 차량 이용");
  await row.locator('input[type="checkbox"]').check();
  await p.waitForTimeout(350);
  sheet = flat(await p.textContent("#st_sheet"));
  check("포함시킨 지출이 기준일 밖이어도 사용액으로 잡힘 (90,000 ÷ 4 = 22,500)",
    /22,500/.test(sheet), sheet.slice(sheet.indexOf("차량운행비"), sheet.indexOf("차량운행비") + 140));

  await p.click('nav button[data-tab="check"]');
  const chk = flat(await p.textContent("#chk"));
  check("포함 사유가 검증에 근거로 남음",
    /기록/.test(chk) && /6월 15일까지 차량 이용/.test(chk), chk.slice(0, 200));
  check("재원기간 밖 오류로는 잡히지 않음", !/오류 재원기간 밖/.test(chk));

  // ================= 정산보고서 =================
  await p.click('nav button[data-tab="settle"]');
  await p.click('[data-m="half"]');
  await p.click('[data-p="H1"]');
  await p.waitForTimeout(200);
  let rep = flat(await p.textContent("#hp_body"));
  check("상반기(3~8월)는 이월 열이 없음", !/이월/.test(rep));
  check("상반기 수납 합계 620,000", /620,000/.test(rep), rep.slice(0, 170));

  await p.click('[data-p="H2"]');
  await p.waitForTimeout(200);
  rep = flat(await p.textContent("#hp_body"));
  check("하반기는 이월 열이 생김", /이월/.test(rep));
  check("미집행액 합계 행이 채워짐", /미집행액 합계/.test(rep));
  check("전입금 충당 열 표시", /전입금 충당/.test(rep));

  await p.selectOption("#hp_from", "2026-10");
  await p.selectOption("#hp_to", "2026-10");
  await p.waitForTimeout(200);
  rep = flat(await p.textContent("#hp_body"));
  check("시작월·마지막월을 골라 한 달만 정산", /10월 ~ 10월/.test(rep), rep.slice(0, 130));

  const cj = await p.evaluate(() => balance("k4", "it_field", "2026-10-01", "2026-10-31"));
  check("위탁 원아의 10월 — 전입금 30,000이 수입·지출 양쪽에 잡혀 남은 금액 0",
    cj.used === 0 && cj.transferIn === 30000 && cj.income === 30000 &&
    cj.totalUsed === 30000 && cj.left === 0, JSON.stringify(cj));
  const gen = await p.evaluate(() => balance("k1", "it_field", "2026-10-01", "2026-10-31"));
  check("일반 원아의 10월 지출은 그대로 사용액 30,000",
    gen.used === 30000 && gen.consign === 0, JSON.stringify(gen));

  /* 위탁 원아 몫이 수입으로도 잡혀 수입과 지출이 맞아떨어지는지 (전 원아·전 세목) */
  const rec = await p.evaluate(() => {
    const from = fyStart(S.fiscalYear), to = fyEnd(S.fiscalYear);
    let paid = 0, transfer = 0, spent = 0;
    for (const c of S.children) for (const it of S.items) {
      const b = balance(c.id, it.id, from, to);
      paid += b.paid; transfer += b.transferIn; spent += b.totalUsed;
    }
    return { paid, transfer, spent, left: paid + transfer - spent };
  });
  check("전입금을 수입으로 잡으면 수입 − 지출 = 보호자에게 돌려줄 몫",
    rec.transfer > 0 && rec.paid + rec.transfer - rec.spent === rec.left,
    `수납 ${rec.paid} + 전입금 ${rec.transfer} − 배분 ${rec.spent} = ${rec.left}`);

  await p.click('nav button[data-tab="check"]');
  await p.waitForTimeout(400);
  const recon = flat(await p.textContent("#panel"));
  check("검증 대사에 전입금 충당 줄이 나옴",
    /전입금 충당 \(위탁 원아 몫\)/.test(recon) && /수입 합계/.test(recon), recon.slice(0, 160));

  /* 수입결의서 한 장에 여러 세목 — 세목 칸을 늘려 한 번에 적는다 */
  await p.click('nav button[data-tab="receipt"]');
  await p.waitForTimeout(400);
  const blk = i => p.locator("#rc_blocks > .blk").nth(i);
  await p.fill("#rc_date", "2026-03-24");
  await p.fill("#rc_no", "777");
  await p.fill("#rc_summary", "기타필요경비 아이행복카드 결제분");
  await p.waitForTimeout(300);
  await blk(0).locator('[data-r="item"]').selectOption("it_prep");
  await p.waitForTimeout(300);
  await blk(0).locator(".pk-class").first().locator('[data-a="g-all"]').click();
  await blk(0).locator('[data-r="per"]').fill("100000");
  await blk(0).locator('[data-r="apply"]').click();
  await p.waitForTimeout(300);
  await p.click("#rc_addBlock");
  await p.waitForTimeout(400);
  await blk(1).locator('[data-r="item"]').selectOption("it_field");
  await p.waitForTimeout(300);
  await blk(1).locator(".pk-class").first().locator('[data-a="g-all"]').click();
  await blk(1).locator('[data-r="per"]').fill("50000");
  await blk(1).locator('[data-r="apply"]').click();
  await p.waitForTimeout(400);
  const grand = flat(await p.textContent("#rc_grand"));
  check("한 결의서에 세목 칸을 여럿 두고 합계가 나옴",
    /이 결의서 합계/.test(grand) && /2개 세목/.test(grand), grand.slice(0, 120));
  await p.click("#rc_save");
  await p.waitForTimeout(700);
  const made = await p.evaluate(() => S.vouchers.filter(v => v.voucherNo === "777")
    .map(v => ({ item: v.itemId, total: v.total, date: v.date })));
  check("세목마다 결의서 하나씩으로 나뉘어 같은 번호로 담김",
    made.length === 2 && made.every(m => m.date === "2026-03-24")
    && made.some(m => m.item === "it_prep") && made.some(m => m.item === "it_field"),
    JSON.stringify(made));
  await p.locator("#rcf_body tbody tr", { hasText: "아이행복카드" }).first()
    .locator('[data-a="edit"]').click();
  await p.waitForTimeout(700);
  check("아무 줄이나 고치면 그 번호의 세목 칸이 전부 올라옴",
    (await p.locator("#rc_blocks > .blk").count()) === 2
    && (await p.inputValue("#rc_no")) === "777",
    (await p.locator("#rc_blocks > .blk").count()) + "칸");
  await p.click("#rc_cancel");
  await p.waitForTimeout(400);

  /* 4분기 잔액 부족 알림 — 12월부터만 뜨고, 등록을 막지는 않는다 */
  async function 부족알림(date, total){
    await p.click('nav button[data-tab="expense"]');
    await p.waitForTimeout(300);
    await p.fill("#e_date", date);
    await p.waitForTimeout(250);
    await p.selectOption("#e_item", "it_field");
    await p.waitForTimeout(300);
    await p.fill("#e_total", String(total));
    await p.dispatchEvent("#e_total", "change");
    await p.click("#e_allNeed");
    await p.waitForTimeout(200);
    await p.locator("#e_pick .pk-class").first().locator('[data-a="g-all"]').click();
    await p.waitForTimeout(400);
    return { 알림: /잔액이 모자랍니다/.test(await p.textContent("#e_preview")),
             잠김: await p.locator("#e_save").isDisabled() };
  }
  const nov = await 부족알림("2026-11-20", 5000000);
  check("3분기(11월)에는 잔액이 모자라도 알리지 않음", !nov.알림 && !nov.잠김,
    JSON.stringify(nov));
  const dec = await 부족알림("2026-12-20", 5000000);
  check("4분기(12월)에는 잔액이 모자라면 알림", dec.알림, JSON.stringify(dec));
  check("알림이 떠도 지출 등록을 막지 않음", !dec.잠김, JSON.stringify(dec));
  const prev = flat(await p.textContent("#e_preview"));
  check("모자란 몫이 운영비 부담이라고 알려 줌",
    /어린이집 운영비에서 나가야 합니다/.test(prev) && /그대로 등록해도 됩니다/.test(prev)
      && /대상 원아/.test(prev),
    prev.slice(prev.indexOf("잔액이 모자랍니다"), prev.indexOf("잔액이 모자랍니다") + 120));

  // ================= 반환 정산서 (전 원아) =================
  await p.click('nav button[data-tab="settle"]');
  await p.waitForTimeout(300);
  await p.click('[data-m="back"]');
  await p.click('[data-p="Y"]');
  await p.waitForTimeout(300);
  const bk = flat(await p.textContent("#bk_body"));
  check("반환 정산서에 원아별 반환할 금액이 세목별로 나옴",
    /필요경비 반환 정산서/.test(bk) && /반환 합계/.test(bk) && /현장학습비/.test(bk), bk.slice(0, 220));
  check("퇴소·위탁이 비고에 표시", /06\.15 퇴소/.test(bk) && /위탁/.test(bk));

  // ================= 보호자용 안내문 =================
  await p.click('[data-m="notice"]');
  await p.click('[data-p="Y"]').catch(() => {});
  await p.selectOption("#nt_from", "2026-03");
  await p.selectOption("#nt_to", "2027-02");
  await p.selectOption("#nt_class", "");
  await p.waitForTimeout(150);
  await p.selectOption("#nt_child", "k1");
  await p.waitForTimeout(300);
  const nt = flat(await p.textContent("#nt_body"));
  check("안내문에 지출 내역이 날짜순으로 들어감",
    /산출 근거 — 지출 내역/.test(nt) && /봄 현장학습 입장료/.test(nt) && /가을 현장학습 버스/.test(nt) && /6월 유류비/.test(nt),
    nt.slice(nt.indexOf("산출 근거"), nt.indexOf("산출 근거") + 230));
  check("안내문에 지출결의서 번호는 넣지 않음",
    !/결의서/.test(nt.slice(nt.indexOf("산출 근거"))));

  await p.check("#nt_all");
  await p.waitForTimeout(300);
  check("전체 원아 한 장씩", (await p.locator("#nt_body .sheet").count()) === 4);

  if (process.env.SHOT_DIR) await p.screenshot({ path: process.env.SHOT_DIR + "reports.png", fullPage: true });
  await b.close();

  console.log("=== 통과 ==="); ok.forEach(s => console.log("  ✓ " + s));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s => console.log("  ✗ " + s)); process.exit(1); }
  console.log("모두 통과");
})();
