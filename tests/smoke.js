/*
 * 1단계-기본흐름 — 브라우저 회귀 테스트
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/smoke.js
 *
 * index.html의 경로가 다르면 아래 path 상수를 고치세요.
 */
const { chromium } = require("playwright");
const path = "file:///home/user/my-first-project/기타필요경비정산.html";

const errs = [];
const ok = [];
function check(name, cond, extra) {
  (cond ? ok : errs).push(name + (extra ? " → " + extra : ""));
}

(async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const page = await browser.newPage();
  page.on("pageerror", e => errs.push("PAGE ERROR: " + e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("CONSOLE: " + m.text()); });

  await page.goto(path);

  // ---------- 기초설정: 반 2개 ----------
  for (const n of ["새싹반", "풀잎반"]) {
    await page.fill("#newClass", n);
    await page.click("#addClass");
  }
  check("반 2개 추가", (await page.locator("#classList tbody tr").count()) === 2);

  // ---------- 원아 5명 ----------
  const kids = [
    ["김서우", "새싹반", "2026-03-02", ""],
    ["이하람", "새싹반", "2026-03-02", ""],
    ["박도윤", "풀잎반", "2026-03-02", ""],
    ["최지안", "풀잎반", "2026-03-02", ""],
    ["정유나", "풀잎반", "2026-08-03", ""],   // 중간입소
  ];
  for (const [name, cls, admit, leave] of kids) {
    await page.click("#addChild");
    await page.fill("#m_name", name);
    await page.fill("#m_admit", admit);
    if (leave) await page.fill("#m_leave", leave);
    await page.click("#m_addClass");
    await page.selectOption("#m_classes select", { label: cls });
    await page.fill("#m_classes input[type=date]", admit);
    await page.click(".modal .foot button.pri");
    await page.waitForSelector(".mask", { state: "detached" });
  }
  check("원아 5명 등록", (await page.locator("#childList tbody tr").count()) === 5);

  // ---------- 수납: 현장학습비 60,000원 일괄 ----------
  await page.click('nav button[data-tab="receipt"]');
  await page.selectOption("#r_item", { label: "현장학습비" });
  await page.fill("#r_date", "2026-03-05");
  await page.fill("#r_base", "60000");
  await page.click("#r_apply");
  const total1 = await page.textContent("#r_total");
  // 3/5 기준 재원 4명(정유나는 8월 입소) → 240,000원
  check("재원 원아만 일괄 적용", /240,000원 \(4명\)/.test(total1), total1);

  page.once("dialog", d => d.accept());
  await page.click("#r_save");
  await page.waitForTimeout(300);

  // ---------- 지출: 필요경비 100,000원을 3명에게 배분(단수차 발생) ----------
  await page.click('nav button[data-tab="expense"]');
  await page.fill("#e_date", "2026-04-10");
  await page.selectOption("#e_item", { label: "현장학습비" });
  await page.fill("#e_summary", "봄 현장학습 입장료");
  await page.fill("#e_total", "100000");
  await page.click("#e_allNeed");

  // 정유나는 4/10 기준 미입소 → 선택 불가여야 함
  const disabled = await page.locator("#e_pick .pk-item.dis").count();
  check("재원기간 밖 원아 선택 잠금", disabled === 1, "잠긴 항목 " + disabled + "개");

  // 새싹반 전체(2명) + 박도윤 1명 = 3명
  await page.locator('#e_pick .pk-class', { hasText: "새싹반" }).locator('[data-a="g-all"]').click();
  await page.locator("#e_pick .pk-item", { hasText: "박도윤" }).locator("input").check();

  const prev = await page.textContent("#e_preview");
  check("배분 미리보기 단수차 처리",
    /대상 3명/.test(prev) && /33,333원/.test(prev) && /앞 순번 1명은 33,334원/.test(prev) && /= 필요경비 부담분/.test(prev),
    prev.replace(/\s+/g, " ").slice(0, 200));

  await page.click("#e_save");
  await page.waitForTimeout(300);
  check("지출 1건 저장", (await page.locator("#e_list tbody tr").count()) === 2); // 데이터 1행 + 합계행

  // ---------- 저장 차단 확인 ----------
  await page.fill("#e_total", "50000");
  await page.click("#e_allNeed");
  const guardDisabled = await page.locator("#e_save").isDisabled();
  check("대상 미지정 시 저장 차단", guardDisabled === true);

  // ---------- 원아별 현황 ----------
  await page.click('nav button[data-tab="child"]');
  await page.selectOption("#c_pick", { label: "김서우" });
  const sumTxt = (await page.textContent("#c_sum")).replace(/\s+/g, " ");
  check("김서우 수납 60,000 / 사용 33,334 / 잔액 26,666",
    /60,000/.test(sumTxt) && /33,334/.test(sumTxt) && /26,666/.test(sumTxt), sumTxt.slice(0, 220));

  const useTxt = (await page.textContent("#c_use")).replace(/\s+/g, " ");
  check("사용 건별 내역 표시", /봄 현장학습 입장료/.test(useTxt), useTxt.slice(0, 160));

  // 역추적 — 금액 클릭 시 지출 탭으로 이동
  await page.locator("#c_use button.link").first().click();
  await page.waitForTimeout(200);
  check("역추적 이동", (await page.locator('nav button[data-tab="expense"].on').count()) === 1);

  // ---------- 검증 ----------
  await page.click('nav button[data-tab="check"]');
  const chk = (await page.textContent("#chk")).replace(/\s+/g, " ");
  check("검증 탭 동작", chk.length > 0, chk.slice(0, 220));

  // ---------- 저장 지속성 ----------
  await page.reload();
  await page.waitForTimeout(300);
  await page.click('nav button[data-tab="child"]');
  const after = (await page.textContent("#c_sum")).replace(/\s+/g, " ");
  check("새로고침 후에도 데이터 유지", /60,000/.test(after));

  await page.screenshot({ path: process.env.SHOT_DIR ? process.env.SHOT_DIR + "shot.png" : "shot.png", fullPage: true });

  await browser.close();

  console.log("=== 통과 ===");
  ok.forEach(s => console.log("  ✓ " + s));
  if (errs.length) {
    console.log("=== 실패 ===");
    errs.forEach(s => console.log("  ✗ " + s));
    process.exit(1);
  }
  console.log("모두 통과");
})();
