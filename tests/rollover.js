/*
 * 새 회계연도 승계 회귀 테스트 — 넘어가는 것과 지워지는 것을 확인한다.
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

  // 백업을 한 번도 받지 않은 상태이므로 알림이 떠야 한다
  check("백업 알림 표시", /백업을 한 번도/.test(await p.textContent("#backupWarn")),
    await p.textContent("#backupWarn"));

  const before = await p.evaluate(() => ({
    fy: S.fiscalYear, kids: S.children.length,
    vouchers: S.vouchers.length, expenses: S.expenses.length,
    classes: S.classes.length, items: S.items.length, rosters: S.rosters.length,
  }));
  check("승계 전 상태", before.fy === 2026 && before.kids === 37 && before.vouchers === 30, JSON.stringify(before));

  await p.click('nav button[data-tab="setup"]');
  await p.click("#btnRollover");
  await p.waitForTimeout(300);

  // 백업 없이 저장하면 막혀야 한다
  p.once("dialog", d => d.accept());
  await p.click(".modal .foot button.pri");
  await p.waitForTimeout(250);
  check("백업 전에는 저장이 막힘", (await p.locator(".modal").count()) === 1);

  // 퇴소 원아는 미리 꺼져 있어야 한다
  const rows = await p.$$eval("#ro_list tbody tr", trs => trs.map(tr => ({
    name: tr.children[1].textContent.trim(),
    keep: tr.querySelector('input[type="checkbox"]').checked,
  })));
  const leavers = rows.filter(r => /퇴소/.test(r.name));
  check("퇴소일이 적힌 원아는 미리 제외됨",
    leavers.length === 2 && leavers.every(r => !r.keep), JSON.stringify(leavers));
  check("나머지는 올라감으로 켜져 있음", rows.filter(r => r.keep).length === 35);

  // 한빛2반 아이 하나를 졸업 처리하고, 새싹반 아이 하나를 나무반으로 올린다
  const cnt = flat(await p.textContent("#ro_count"));
  check("승계 인원 표시", /올라감 35명 · 제외 2명/.test(cnt), cnt);

  await p.check("#ro_ok");
  await p.locator("#ro_list tbody tr", { hasText: "이시은" }).locator("select")
    .selectOption({ label: "나무반" });

  const onDialog = d => d.accept();
  p.on("dialog", onDialog);            // 확인 + 완료 알림
  await p.click(".modal .foot button.pri");
  await p.waitForTimeout(700);
  p.off("dialog", onDialog);

  const after = await p.evaluate(() => ({
    fy: S.fiscalYear, kids: S.children.length,
    vouchers: S.vouchers.length, expenses: S.expenses.length, receipts: S.receipts.length,
    classes: S.classes.length, items: S.items.length,
    std: (S.items.find(i => i.id === "it_field") || {}).stdAmount,
    rosterMax: Math.max.apply(null, S.rosters.map(r => r.childIds.length)),
    leaveDates: S.children.filter(c => c.leaveDate).length,
    hist: S.children.every(c => c.classHistory.length === 1 && c.classHistory[0].startDate === "2027-03-01"),
    eseun: (S.children.find(c => c.name === "이시은") || {}).classHistory[0].classId,
    consign: S.children.filter(c => (c.consignPeriods || []).length).length,
    backup: S.lastBackupAt,
  }));

  check("회계연도가 2027로 넘어감", after.fy === 2027, String(after.fy));
  check("금액 자료는 모두 지워짐",
    after.vouchers === 0 && after.expenses === 0 && after.receipts === 0, JSON.stringify(after));
  check("올라간 원아만 남음 (37 → 35명)", after.kids === 35, String(after.kids));
  check("퇴소일은 지워짐", after.leaveDates === 0);
  check("반 이력은 새 연도 3월 1일 하나만", after.hist === true);
  check("고른 새 반이 반영됨 (이시은 → 나무반)", after.eseun === "cl_h1b", after.eseun);
  check("반·세목은 그대로 넘어감",
    after.classes === 7 && after.items === 8 && after.std === 29997, JSON.stringify(after));
  check("위탁 기간은 이어짐", after.consign === 2, String(after.consign));
  check("고정 명단이 남은 원아로 걸러짐", after.rosterMax <= 35, String(after.rosterMax));
  check("승계 후에는 다시 백업이 필요함", after.backup === null);

  // 화면이 새 연도로 정상 동작하는지
  for (const t of ["receipt", "expense", "child", "settle", "ledger", "check"]) {
    await p.click(`nav button[data-tab="${t}"]`);
    await p.waitForTimeout(200);
  }
  check("새 연도에서 모든 화면이 열림", errs.filter(e => /PAGE ERROR/.test(e)).length === 0);
  const range = await p.textContent("#fyRange");
  check("회계연도 범위 표시", /2027-03-01 ~ 2028-02-29/.test(range), range);

  await b.close();
  console.log("=== 통과 ==="); ok.forEach(s => console.log("  ✓ " + s));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s => console.log("  ✗ " + s)); process.exit(1); }
  console.log("모두 통과");
})();
