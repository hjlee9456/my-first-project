/*
 * 새 회계연도 승계 회귀 테스트.
 * 지난 해 자료가 그대로 남는지, 반 편성을 먼저 확정하고 원아를 배치하는지 본다.
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/rollover.js
 */
const { chromium } = require("playwright");
const SEED = require("../예시자료.json");

const errs = [], ok = [];
const check = (n, c, x) => (c ? ok : errs).push(n + (x ? " → " + x : ""));
const flat = s => String(s || "").replace(/\s+/g, " ");

(async () => {
  const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  p.on("pageerror", e => errs.push("PAGE ERROR: " + e.message));
  p.on("console", m => { if (m.type() === "error") errs.push("CONSOLE: " + m.text()); });

  await p.goto("file:///home/user/my-first-project/기타필요경비정산.html");
  await p.evaluate(([k, v]) => {
    localStorage.setItem(k, JSON.stringify(v));
    localStorage.setItem("centerName", "여수시립 힐스테이트죽림젠트리스어린이집");
  }, ["nursery-settlement-v1", SEED]);
  await p.reload();
  await p.waitForTimeout(400);

  // 한 해분만 담던 예전 자료가 연도 보관함으로 옮겨져야 한다
  const mig = await p.evaluate(() => ({
    ver: S.version, years: Object.keys(S.years), fy: S.fiscalYear,
    kids: S.children.length, vouchers: S.vouchers.length,
  }));
  check("예전 자료가 연도 보관함으로 옮겨짐",
    mig.ver === 2 && mig.years.join() === "2026" && mig.kids === 37 && mig.vouchers === 30,
    JSON.stringify(mig));

  // 회계연도 목록에는 보관 중인 해만 나온다
  const opts = await p.$$eval("#fyPick option", os => os.map(o => o.value));
  check("회계연도 목록은 보관 중인 해만", opts.join() === "2026", opts.join());

  await p.click('nav button[data-tab="setup"]');
  await p.click("#btnRollover");
  await p.waitForTimeout(400);

  // ---- 1단계: 반 구성 ----
  check("1단계는 반 구성", /1단계 — 2027년도 반 구성/.test(await p.textContent("#ro_stepname")));
  check("올해 반이 복사되어 있음", (await p.locator("#ro_cl tbody tr").count()) === 7);
  check("2단계 원아 배치는 아직 숨어 있음", await p.locator("#ro_s2").isHidden());

  // 반 이름을 고치고, 하나 지우고, 하나 더한다
  await p.locator("#ro_cl tbody tr").nth(0).locator("input").fill("햇살반(신)");
  await p.locator("#ro_cl tbody tr").nth(6).locator("button").click();   // 풀잎반 삭제
  await p.fill("#ro_newcl", "새싹3반");
  await p.click("#ro_addcl");
  await p.waitForTimeout(200);
  check("반을 고치고 더하고 뺄 수 있음", (await p.locator("#ro_cl tbody tr").count()) === 7);
  check("반 개수 표시", /반 7개/.test(await p.textContent("#ro_count")));

  // ---- 2단계: 원아 배치 ----
  await p.click("#ro_next");
  await p.waitForTimeout(300);
  check("2단계는 원아 배치", /2단계 — 원아 배치/.test(await p.textContent("#ro_stepname")));
  check("1단계는 숨음", await p.locator("#ro_s1").isHidden());

  // 1단계에서 정한 반만 고를 수 있어야 한다
  const clsOpts = await p.locator("#ro_list tbody tr").first().locator("select")
    .locator("option").allTextContents();
  check("1단계에서 정한 반이 선택지로 나옴",
    clsOpts.includes("햇살반(신)") && clsOpts.includes("새싹3반") && !clsOpts.includes("풀잎반"),
    clsOpts.join(", "));

  const rows = await p.$$eval("#ro_list tbody tr", trs => trs.map(tr => ({
    name: tr.children[1].textContent.trim(),
    keep: tr.querySelector('input[type="checkbox"]').checked,
  })));
  check("퇴소일이 적힌 원아는 미리 제외됨",
    rows.filter(r => /퇴소/.test(r.name)).every(r => !r.keep));
  check("승계 인원 표시", /올라감 35명 · 제외 2명/.test(await p.textContent("#ro_count")));

  // 지워진 반(풀잎반)에 있던 아이는 남은 반으로 옮겨져 있어야 한다
  const moved = await p.locator("#ro_list tbody tr", { hasText: "조유안" }).locator("select").inputValue();
  check("지운 반의 원아는 남은 반으로 배치됨", !!moved, moved);

  await p.locator("#ro_list tbody tr", { hasText: "이시은" }).locator("select")
    .selectOption({ label: "새싹3반" });

  const onDialog = d => d.accept();
  p.on("dialog", onDialog);
  await p.click(".modal .foot button.pri");
  await p.waitForTimeout(800);
  p.off("dialog", onDialog);

  // ---- 넘어간 뒤 ----
  const after = await p.evaluate(() => ({
    fy: S.fiscalYear, years: Object.keys(S.years).sort(),
    kids: S.children.length, classes: S.classes.map(c => c.name),
    vouchers: S.vouchers.length, expenses: S.expenses.length,
    leaveDates: S.children.filter(c => c.leaveDate).length,
    hist: S.children.every(c => c.classHistory.length === 1 && c.classHistory[0].startDate === "2027-03-01"),
    eseunCls: (S.classes.find(c => c.id ===
      (S.children.find(k => k.name === "이시은") || {}).classHistory[0].classId) || {}).name,
    std: (S.items.find(i => i.id === "it_field") || {}).stdAmount,
    consign: S.children.filter(c => (c.consignPeriods || []).length).length,
    prev: {
      kids: S.years["2026"].children.length,
      vouchers: S.years["2026"].vouchers.length,
      expenses: S.years["2026"].expenses.length,
      classes: S.years["2026"].classes.map(c => c.name),
    },
  }));

  check("2027년도로 넘어감", after.fy === 2027 && after.years.join() === "2026,2027", JSON.stringify(after.years));
  check("지난 2026년도 자료가 그대로 남음",
    after.prev.kids === 37 && after.prev.vouchers === 30 && after.prev.expenses === 27,
    JSON.stringify(after.prev));
  check("지난 해 반 이름도 그대로", after.prev.classes.includes("풀잎반") && after.prev.classes[0] === "햇살반",
    after.prev.classes.join(", "));
  check("새 해는 1단계에서 정한 반 구성",
    after.classes[0] === "햇살반(신)" && after.classes.includes("새싹3반") && !after.classes.includes("풀잎반"),
    after.classes.join(", "));
  check("새 해는 금액이 비어 있음", after.vouchers === 0 && after.expenses === 0);
  check("올라간 원아만 (37 → 35명)", after.kids === 35, String(after.kids));
  check("퇴소일은 지워짐", after.leaveDates === 0);
  check("반 이력은 새 연도 3월 1일 하나만", after.hist === true);
  check("고른 새 반이 반영됨 (이시은 → 새싹3반)", after.eseunCls === "새싹3반", after.eseunCls);
  check("세목은 1인당 수납액까지 넘어감", after.std === 29997, String(after.std));
  check("위탁 기간은 이어짐", after.consign === 2, String(after.consign));

  // ---- 회계연도 오가기 ----
  const opts2 = await p.$$eval("#fyPick option", os => os.map(o => o.value));
  check("회계연도 목록에 두 해가 나옴", opts2.join() === "2026,2027", opts2.join());

  await p.selectOption("#fyPick", "2026");
  await p.waitForTimeout(500);
  const back = await p.evaluate(() => ({
    fy: S.fiscalYear, kids: S.children.length, vouchers: S.vouchers.length,
    cls: S.classes.map(c => c.name).join(","),
  }));
  check("2026년도로 돌아가면 그때 자료가 그대로",
    back.fy === 2026 && back.kids === 37 && back.vouchers === 30 && /풀잎반/.test(back.cls),
    JSON.stringify(back));

  // 그 해 대장도 그대로 나와야 한다
  await p.click('nav button[data-tab="ledger"]');
  await p.selectOption("#lg_kind", "receipt");
  await p.waitForTimeout(500);
  const lg = flat(await p.textContent("#lg_body"));
  check("지난 해 대장이 그대로 나옴", /2026년 3월 ~ 2027년 2월/.test(lg) && /김도윤/.test(lg), lg.slice(0, 120));

  // 새로고침해도 보던 연도가 유지된다
  await p.reload();
  await p.waitForTimeout(500);
  check("새로고침해도 보던 연도 유지", (await p.evaluate(() => S.fiscalYear)) === 2026);

  // ---- 연도 삭제 ----
  await p.click('nav button[data-tab="setup"]');
  await p.waitForTimeout(300);
  check("보관 중인 회계연도 목록 표시", (await p.locator("#ro_years tbody tr").count()) === 2);
  p.on("dialog", onDialog);
  await p.locator("#ro_years tbody tr", { hasText: "2027년도" }).locator('[data-a="del"]').click();
  await p.waitForTimeout(600);
  p.off("dialog", onDialog);
  const left = await p.evaluate(() => Object.keys(S.years));
  check("연도를 지울 수 있음", left.join() === "2026", left.join());

  await b.close();
  console.log("=== 통과 ==="); ok.forEach(s => console.log("  ✓ " + s));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s => console.log("  ✗ " + s)); process.exit(1); }
  console.log("모두 통과");
})();
