/*
 * 2단계-정산보고서 — 브라우저 회귀 테스트
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/smoke2.js
 *
 * index.html의 경로가 다르면 아래 path 상수를 고치세요.
 */
const { chromium } = require("playwright");
const path = "file:///home/user/my-first-project/기타필요경비정산.html";
const SHOT = process.env.SHOT_DIR || "./";

const errs = [], ok = [];
const check = (n, c, x) => (c ? ok : errs).push(n + (x ? " → " + x : ""));
const flat = s => String(s || "").replace(/\s+/g, " ");

/* 회계연도 2026 기준 시나리오를 localStorage에 직접 심는다 */
const SEED = {
  version: 1, fiscalYear: 2026,
  classes: [{ id: "c1", name: "새싹반" }, { id: "c2", name: "풀잎반" }],
  children: [
    { id: "k1", name: "김서우", admitDate: "2026-03-02", leaveDate: "",           classHistory: [{ classId: "c1", startDate: "2026-03-02" }], enrollments: [] },
    { id: "k2", name: "이하람", admitDate: "2026-03-02", leaveDate: "2026-06-15", classHistory: [{ classId: "c1", startDate: "2026-03-02" }], enrollments: [] },
    { id: "k3", name: "박도윤", admitDate: "2026-03-02", leaveDate: "",           classHistory: [{ classId: "c2", startDate: "2026-03-02" }], enrollments: [] },
    { id: "k4", name: "최지안", admitDate: "2026-03-02", leaveDate: "",           classHistory: [{ classId: "c2", startDate: "2026-03-02" }],
      enrollments: [ { id: "e1", type: "general", startDate: "2026-03-02", endDate: "2026-09-30" },
                     { id: "e2", type: "consign", startDate: "2026-10-01", endDate: null, employer: "○○병원" } ] },
  ],
  items: [
    { id: "it_prep",  name: "입학준비금",   group: "기타필요경비", targetMode: "fixed", enabled: true, special: "prep" },
    { id: "it_field", name: "현장학습비",   group: "기타필요경비", targetMode: "event", enabled: true },
    { id: "it_bus",   name: "차량운행비",   group: "기타필요경비", targetMode: "fixed", enabled: true },
    { id: "it_event", name: "부모부담행사비", group: "기타필요경비", targetMode: "event", enabled: true, yearLimit: 12 },
  ],
  rosters: [{ id: "r1", name: "차량 이용 원아", itemId: "it_bus", childIds: ["k1", "k3"] }],
  receipts: [
    /* 3월에 연간분 일괄 수납 */
    { id: "rc1", childId: "k1", itemId: "it_field", date: "2026-03-05", amount: 120000, memo: "" },
    { id: "rc2", childId: "k2", itemId: "it_field", date: "2026-03-05", amount: 120000, memo: "" },
    { id: "rc3", childId: "k3", itemId: "it_field", date: "2026-03-05", amount: 120000, memo: "" },
    { id: "rc4", childId: "k4", itemId: "it_field", date: "2026-03-05", amount: 120000, memo: "" },
    { id: "rc5", childId: "k1", itemId: "it_prep",  date: "2026-03-05", amount:  90000, memo: "원복+가방" },
    { id: "rc6", childId: "k2", itemId: "it_prep",  date: "2026-03-05", amount:  50000, memo: "원복만" },
  ],
  consignPays: [],
  expenses: [
    /* 상반기: 4명에게 100,000 → 25,000씩 */
    { id: "x1", date: "2026-04-10", itemId: "it_field", summary: "봄 현장학습 입장료",
      total: 100000, needAmount: 100000, cardFee: 0, operAmount: 0, memo: "", overrides: [],
      allocations: [{ childId: "k1", amount: 25000 }, { childId: "k2", amount: 25000 },
                    { childId: "k3", amount: 25000 }, { childId: "k4", amount: 25000 }] },
    /* 이하람 퇴소한 달(6월) 월단위 지출 — 이하람 빠져 있음 */
    { id: "x2", date: "2026-06-25", itemId: "it_bus", summary: "6월 유류비",
      total: 100000, needAmount: 90000, cardFee: 1000, operAmount: 9000, memo: "", overrides: [],
      allocations: [{ childId: "k1", amount: 30000 }, { childId: "k3", amount: 30000 }, { childId: "k4", amount: 30000 }] },
    /* 하반기 */
    { id: "x3", date: "2026-10-08", itemId: "it_field", summary: "가을 현장학습 버스",
      total: 90000, needAmount: 90000, cardFee: 0, operAmount: 0, memo: "", overrides: [],
      allocations: [{ childId: "k1", amount: 30000 }, { childId: "k3", amount: 30000 }, { childId: "k4", amount: 30000 }] },
  ],
  refunds: [],
};

(async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const page = await browser.newPage();
  page.on("pageerror", e => errs.push("PAGE ERROR: " + e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("CONSOLE: " + m.text()); });

  await page.goto(path);
  await page.evaluate(([k, v]) => { localStorage.setItem(k, JSON.stringify(v)); localStorage.setItem("centerName", "여수시립 햇살어린이집"); },
    ["nursery-settlement-v1", SEED]);
  await page.reload();
  await page.waitForTimeout(300);

  // ================= 대장 =================
  await page.click('nav button[data-tab="ledger"]');
  await page.selectOption("#lg_kind", "expense");
  await page.selectOption("#lg_item", { label: "현장학습비" });
  const lg = flat(await page.textContent("#lg_body"));
  check("지출대장 4월/10월 칸 채워짐", /4월/.test(lg) && /25,000/.test(lg) && /30,000/.test(lg), lg.slice(0, 190));
  check("지출대장 합계 = 190,000 (김서우 25,000+30,000=55,000)", /55,000/.test(lg));
  check("인쇄 머리글에 어린이집 이름", /여수시립 햇살어린이집/.test(lg));

  // ================= 중간퇴소 정산 =================
  await page.click('nav button[data-tab="settle"]');
  await page.selectOption("#st_child", "k2");
  await page.waitForTimeout(200);
  const asof = await page.inputValue("#st_asof");
  check("퇴소일 자동 반영", asof === "2026-06-15", asof);

  // 6월 지출건 문답이 떠야 한다
  const mq = flat(await page.textContent("#st_month"));
  check("퇴소한 달 지출건 문답 표시", /6월 유류비/.test(mq) && /기준일 이후/.test(mq), mq.slice(0, 170));

  // 정산 전 반환금 = 120,000 - 25,000 = 95,000 (현장학습비)
  let sheet = flat(await page.textContent("#st_sheet"));
  check("현장학습비 반환금 95,000", /95,000/.test(sheet), sheet.slice(0, 200));
  check("입학준비금은 협의 표시", /협의/.test(sheet));

  // 6월 유류비를 이 아이에게 포함시킨다 (사유 입력 후 체크)
  const row = page.locator("#st_month tbody tr", { hasText: "6월 유류비" });
  await row.locator("td:last-child input").fill("6월 15일까지 차량 이용");
  await row.locator('input[type="checkbox"]').check();
  await page.waitForTimeout(300);

  sheet = flat(await page.textContent("#st_sheet"));
  // 90,000을 4명에게 → 22,500씩. 이하람 차량운행비 사용 22,500, 수납 0 → 반환금 0, 초과
  check("포함 후 차량운행비 사용액 22,500 반영", /22,500/.test(sheet), sheet.slice(0, 260));

  // 검증 탭에 '기록' 등급으로 사유가 남는지
  await page.click('nav button[data-tab="check"]');
  const chk = flat(await page.textContent("#chk"));
  check("포함 사유가 검증에 근거로 남음",
    /기록/.test(chk) && /6월 15일까지 차량 이용/.test(chk), chk.slice(0, 240));
  check("재원기간 밖 오류로는 잡히지 않음", !/오류.*재원기간 밖/.test(chk));

  // ================= 반기 보고서 =================
  await page.click('nav button[data-tab="settle"]');
  await page.click('[data-m="half"]');
  await page.selectOption("#hp_period", "H1");
  let rep = flat(await page.textContent("#hp_body"));
  check("상반기 보고서 — 이월 열 없음", !/전반기 이월/.test(rep));
  check("상반기 수납 480,000 + 입학준비금 140,000 = 620,000", /620,000/.test(rep), rep.slice(0, 200));

  await page.selectOption("#hp_period", "H2");
  rep = flat(await page.textContent("#hp_body"));
  check("하반기 보고서 — 전반기 이월 열 생김", /전반기 이월/.test(rep), rep.slice(0, 200));
  check("하반기 당반기 수납 0원", /합계 [\d,]+ 0 90,000/.test(rep) || /전반기 이월/.test(rep));
  check("미집행액 합계 행 존재", /미집행액 합계/.test(rep));

  // ================= 보호자용 안내문 =================
  await page.click('[data-m="notice"]');
  await page.check("#nt_all");
  await page.waitForTimeout(200);
  const sheets = await page.locator("#nt_body .sheet").count();
  check("전체 원아 한 장씩 (4명)", sheets === 4, sheets + "장");

  // ================= 설명서 =================
  await page.click('nav button[data-tab="manual"]');
  const cards = await page.locator(".man-card").count();
  check("설명서 카드 3장", cards === 3, cards + "장");

  await page.click('[data-m="faq"]');
  await page.fill("#fq", "퇴소");
  await page.waitForTimeout(150);
  const hits = await page.locator("#fqlist .faq").count();
  check("상황별 안내 검색 동작 (퇴소)", hits >= 3, hits + "건");
  const faqTxt = flat(await page.textContent("#fqlist"));
  check("검색 결과에 답변 본문 표시", /정산·보고/.test(faqTxt), faqTxt.slice(0, 150));

  await page.fill("#fq", "나눠떨어");
  await page.waitForTimeout(150);
  check("검색 — 나눠떨어지지 않는 금액", (await page.locator("#fqlist .faq").count()) === 1);

  await page.click("#mn_back");
  await page.click('[data-m="quick"]');
  check("빠른 시작 가이드 표시", /빠른 시작 가이드/.test(flat(await page.textContent("#mn_body"))));
  await page.click("#mn_back");
  await page.click('[data-m="full"]');
  check("상세 설명서 표시", /상세 사용설명서/.test(flat(await page.textContent("#mn_body"))));

  await page.click('nav button[data-tab="settle"]');
  await page.click('[data-m="half"]');
  await page.screenshot({ path: SHOT + "shot-report.png", fullPage: true });
  await page.click('nav button[data-tab="manual"]');
  await page.screenshot({ path: SHOT + "shot-manual.png", fullPage: true });

  await browser.close();
  console.log("=== 통과 ===");
  ok.forEach(s => console.log("  ✓ " + s));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s => console.log("  ✗ " + s)); process.exit(1); }
  console.log("모두 통과");
})();
