/*
 * 조작 감사 — 정산 프로그램의 버튼과 드롭다운이 제 몫을 하는지 본다.
 *
 *   ① 화면에 놓인 버튼·드롭다운에 눌렀을 때 할 일이 붙어 있는가 (허수아비 찾기)
 *   ② 드롭다운을 바꾸면 화면이 그 값을 그대로 붙들고 있는가
 *   ③ 수납 → 지출 → 현황 → 대장 → 정산서로 업무가 끝까지 이어지는가
 *
 * ①은 누르지 않고 확인한다. 눌러 보는 방식은 화면이 다시 그려지면서 자리가
 * 밀리고, 「수정」 같은 단추가 입력칸을 고침 상태로 바꿔 놓아 뒤따르는 검사를
 * 망가뜨렸다.
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/audit.js
 */
const { chromium } = require("playwright");
const SEED = require("../예시자료.json");

const errs = [], ok = [], dead = [];
const check = (n, c, x) => (c ? ok : errs).push(n + (x ? " → " + x : ""));
const flat = s => String(s || "").replace(/\s+/g, " ");

(async () => {
  const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
  p.on("pageerror", e => errs.push("PAGE ERROR: " + e.message));
  p.on("console", m => { if (m.type() === "error") errs.push("CONSOLE: " + m.text()); });
  p.on("dialog", d => d.dismiss().catch(() => {}));

  const seed = async () => {
    await p.evaluate(([k, v]) => {
      localStorage.setItem(k, JSON.stringify(v));
      localStorage.setItem("centerName", "여수시립 힐스테이트죽림젠트리스어린이집");
    }, ["nursery-settlement-v1", SEED]);
    await p.reload();
    await p.waitForTimeout(400);
  };

  await p.goto("file:///home/user/my-first-project/기타필요경비정산.html");
  await seed();

  /* ---------------- ① 할 일이 붙어 있는가 ---------------- */
  /* 고르는 순간이 아니라 옆 버튼을 누를 때 값을 읽어 가는 자리는 빼 준다 */
  const READ_BY_BUTTON = ["newItemGroup", "rc_roster", "e_roster"];
  async function auditHandlers(where){
    const idle = await p.$$eval("header button, header select, #panel button, #panel select, #panel input[type=file]",
      (els, skip) => els.filter(el => {
        if (el.disabled || el.offsetParent === null) return false;
        if (skip.includes(el.id)) return false;
        return !el.onclick && !el.onchange && !el.oninput;
      }).map(el => el.id || (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 18) || el.tagName),
      READ_BY_BUTTON);
    idle.forEach(t => dead.push(`${where} — 「${t}」에 눌렀을 때 할 일이 없음`));
  }

  /* 드롭다운을 다른 값으로 바꿔 놓고, 화면이 그 값을 붙들고 있는지 본다.
     자리(index)가 아니라 id로 집으므로 다시 그려져도 어긋나지 않는다. */
  async function auditSelects(where){
    const ids = await p.$$eval("#panel select", ss => ss
      .filter(el => el.id && !el.disabled && el.offsetParent !== null && el.options.length > 1)
      .map(el => el.id));
    for (const id of ids) {
      /* 앞 드롭다운을 돌리면 뒤 목록이 바뀌므로 선택지는 그때그때 다시 읽는다 */
      const vals = await p.$$eval("#" + id + " option", os => os.map(o => o.value)).catch(() => []);
      const se = { id };
      for (const v of vals.slice(0, 3)) {
        const el = p.locator("#" + se.id);
        if (!(await el.count())) break;
        await el.selectOption(v, { timeout: 3000 }).catch(() => {});
        await p.waitForTimeout(160);
        const now = await p.locator("#" + se.id).inputValue().catch(() => null);
        if (now !== null && now !== v) {
          dead.push(`${where} — 드롭다운 「${se.id}」에 ${v}를 골랐는데 ${now}로 되돌아감`);
          break;
        }
      }
    }
  }

  const TABS = [
    ["setup", "기초설정"], ["receipt", "수납 입력"], ["expense", "지출 등록"],
    ["child", "원아별 현황"], ["ledger", "대장"], ["check", "검증"], ["manual", "사용설명서"],
  ];
  for (const [t, name] of TABS) {
    await p.click(`nav button[data-tab="${t}"]`);
    await p.waitForTimeout(300);
    await auditHandlers(name);
    await auditSelects(name);
  }

  for (const [m, name] of [["half", "정산보고서"], ["notice", "보호자 안내문"],
                           ["back", "반환 정산서"], ["exit", "중간퇴소 정산"]]) {
    await p.click('nav button[data-tab="settle"]');
    await p.waitForTimeout(200);
    await p.click(`[data-m="${m}"]`);
    await p.waitForTimeout(350);
    await auditHandlers("정산·보고 / " + name);
    await auditSelects("정산·보고 / " + name);
  }

  check("모든 버튼과 드롭다운이 제 몫을 함", dead.length === 0, dead.join(" · ") || "");

  /* 훑어보며 드롭다운을 이리저리 돌려 놓았으니 자료를 다시 심고 시작한다 */
  await seed();

  /* ---------------- ② 드롭다운이 화면에 반영되는지 ---------------- */
  await p.click('nav button[data-tab="settle"]');
  await p.click('[data-m="notice"]');
  await p.waitForTimeout(300);
  await p.selectOption("#nt_class", { label: "한빛1반" });
  await p.waitForTimeout(400);
  check("안내문 — 반을 고르면 그 반이 유지됨",
    (await p.locator("#nt_class").inputValue()) === (await p.evaluate(() => S.classes.find(c => c.name === "한빛1반").id)));
  const names = await p.locator("#nt_child option").allTextContents();
  check("안내문 — 원아 목록이 그 반으로 좁혀짐",
    names.length === 7 && names.includes("고한빛"), names.join(", "));
  await p.selectOption("#nt_child", { label: "김시원" });
  await p.waitForTimeout(400);
  check("안내문 — 고른 원아의 안내문이 나옴",
    /김시원/.test(await p.textContent("#nt_body")));

  await p.click('[data-m="exit"]');
  await p.waitForTimeout(300);
  await p.selectOption("#st_class", { label: "한빛2반" });
  await p.waitForTimeout(400);
  const stNames = await p.locator("#st_child option").allTextContents();
  check("중간퇴소 — 반을 고르면 그 반 원아만", stNames.length === 7, stNames.join(", "));
  await p.selectOption("#st_child", await p.evaluate(() => S.children.find(c => c.name === "박준의").id));
  await p.waitForTimeout(400);
  check("중간퇴소 — 고른 원아로 정산서가 바뀜",
    /박준의/.test(await p.textContent("#st_sheet")));
  check("중간퇴소 — 퇴소일이 따라옴", (await p.inputValue("#st_asof")) === "2026-11-20");

  /* 기간은 고른 대로 있어야 한다 (예전에는 앞뒤가 뒤바뀌어 되돌아갔다) */
  await p.click('[data-m="back"]');
  await p.waitForTimeout(300);
  await p.selectOption("#bk_from", "2026-09");
  await p.waitForTimeout(300);
  await p.selectOption("#bk_to", "2026-12");
  await p.waitForTimeout(400);
  check("반환 정산서 — 고른 기간이 그대로 있음",
    (await p.inputValue("#bk_from")) === "2026-09" && (await p.inputValue("#bk_to")) === "2026-12",
    (await p.inputValue("#bk_from")) + " ~ " + (await p.inputValue("#bk_to")));
  check("반환 정산서 — 기간 버튼은 지금 기간일 때만 파랗게",
    (await p.locator('[data-p].pri').count()) === 0,
    String(await p.locator('[data-p].pri').count()));
  await p.click('[data-p="Y"]');
  await p.waitForTimeout(400);
  check("연간 버튼을 누르면 그 버튼이 파랗게",
    (await p.locator('[data-p="Y"].pri').count()) === 1);

  await p.click('nav button[data-tab="child"]');
  await p.waitForTimeout(300);
  await p.selectOption("#c_class", { label: "풀잎반" });
  await p.waitForTimeout(400);
  const cNames = await p.locator("#c_pick option").allTextContents();
  check("원아별 현황 — 반으로 좁혀짐", cNames.length === 7, cNames.join(", "));
  await p.selectOption("#c_pick", { label: "조유안" });
  await p.waitForTimeout(400);
  check("원아별 현황 — 고른 원아가 나옴", /조유안/.test(await p.textContent("#c_info")));

  /* ---------------- ③ 업무 흐름이 끝까지 이어지는지 ---------------- */
  /* 원아별 현황에서 한 세목 줄의 숫자를 읽어 온다 — 시험 자료에 이미 금액이
     들어 있으므로 「얼마가 찍혔나」가 아니라 「얼마만큼 움직였나」로 본다 */
  async function showChild(name){
    await p.click('nav button[data-tab="child"]');
    await p.waitForTimeout(300);
    await p.selectOption("#c_class", "");
    await p.waitForTimeout(200);
    await p.selectOption("#c_pick", { label: name });
    await p.waitForTimeout(400);
  }
  async function sumRow(itemName){
    return p.evaluate(n => {
      const tr = Array.from(document.querySelectorAll("#c_sum tbody tr"))
        .find(r => r.children[0] && r.children[0].textContent.trim() === n);
      if (!tr) return null;
      const num = td => +(td.textContent || "").replace(/[^0-9-]/g, "");
      const c = Array.from(tr.children);
      return { paid: num(c[2]), used: num(c[3]), left: num(c[c.length - 1]) };
    }, itemName);
  }

  await showChild("김도윤");
  const base = await sumRow("행사비");

  // 수납결의서를 하나 넣으면 → 원아별 현황·대장에 곧바로 반영되는가
  await p.click('nav button[data-tab="receipt"]');
  await p.waitForTimeout(300);
  await p.fill("#rc_date", "2026-05-11");
  await p.fill("#rc_no", "999");
  await p.selectOption("#rc_item", { label: "행사비" });
  await p.fill("#rc_summary", "감사 시험용 수납");
  await p.locator("#rc_pick .pk-class", { hasText: "햇살반" }).locator('[data-a="g-all"]').click();
  await p.waitForTimeout(200);
  await p.fill("#rc_per", "10000");
  await p.click("#rc_apply");
  await p.waitForTimeout(200);
  await p.click("#rc_save");
  await p.waitForTimeout(400);
  const added = await p.evaluate(() => S.vouchers.find(v => v.voucherNo === "999"));
  check("수납결의서 등록 → 자료에 들어감", !!added && added.total === 30000, JSON.stringify(added && added.total));

  await showChild("김도윤");
  const afterRc = await sumRow("행사비");
  check("수납 → 원아별 현황 수납액이 10,000원 늘어남",
    afterRc.paid - base.paid === 10000 && afterRc.left - base.left === 10000,
    `${base.paid}→${afterRc.paid} · 남은 ${base.left}→${afterRc.left}`);

  await p.click('nav button[data-tab="ledger"]');
  await p.selectOption("#lg_kind", "receipt");
  await p.selectOption("#lg_item", "it_event");
  await p.waitForTimeout(400);
  check("수납 → 수입대장 5월 칸에 들어감", /10,000/.test(await p.textContent("#lg_body")));

  // 지출을 하나 넣으면 → 배분·역추적·정산서까지 이어지는가
  await p.click('nav button[data-tab="expense"]');
  await p.waitForTimeout(300);
  await p.fill("#e_date", "2026-05-20");
  await p.fill("#e_no", "998");
  await p.selectOption("#e_item", { label: "행사비" });
  await p.fill("#e_summary", "감사 시험용 지출");
  await p.fill("#e_total", "9000");
  await p.click("#e_allNeed");
  await p.locator("#e_pick .pk-class", { hasText: "햇살반" }).locator('[data-a="g-all"]').click();
  await p.waitForTimeout(250);
  const prev = flat(await p.textContent("#e_preview"));
  check("지출 — 배분 미리보기 (3명 × 3,000)", /대상 3명/.test(prev) && /3,000원/.test(prev), prev.slice(0, 110));
  await p.click("#e_save");
  await p.waitForTimeout(400);
  check("지출 등록 → 자료에 들어감",
    await p.evaluate(() => S.expenses.some(e => e.voucherNo === "998")));

  await showChild("김도윤");
  const afterEx = await sumRow("행사비");
  check("지출 → 원아별 현황 사용액이 3,000원 늘고 남은 금액이 그만큼 줄어듦",
    afterEx.used - afterRc.used === 3000 && afterRc.left - afterEx.left === 3000,
    `사용 ${afterRc.used}→${afterEx.used} · 남은 ${afterRc.left}→${afterEx.left}`);

  // 역추적 팝업
  await p.locator("#c_use tbody tr", { hasText: "감사 시험용 지출" }).locator("button.link").click();
  await p.waitForTimeout(400);
  const modal = flat(await p.textContent(".modal"));
  check("역추적 — 금액을 누르면 그 지출건과 명단이 뜸",
    /감사 시험용 지출/.test(modal) && /998/.test(modal) && /김도윤/.test(modal), modal.slice(0, 130));
  await p.locator(".modal .foot button", { hasText: "닫기" }).click();
  await p.waitForTimeout(200);

  // 반환 정산서까지
  await p.click('nav button[data-tab="settle"]');
  await p.click('[data-m="back"]');
  await p.click('[data-p="Y"]');
  await p.waitForTimeout(600);
  check("지출·수납 → 반환 정산서에 반영",
    /김도윤/.test(await p.textContent("#bk_body")));

  // 지출을 고치면 다시 계산되는가
  await p.click('nav button[data-tab="expense"]');
  await p.waitForTimeout(300);
  await p.locator("#e_list tbody tr", { hasText: "감사 시험용 지출" }).locator('[data-a="edit"]').click();
  await p.waitForTimeout(400);
  await p.fill("#e_total", "6000");
  await p.click("#e_allNeed");
  await p.waitForTimeout(200);
  await p.click("#e_save");
  await p.waitForTimeout(400);
  await showChild("김도윤");
  const afterFix = await sumRow("행사비");
  check("지출 수정 (9,000 → 6,000) → 원아별 현황이 1인당 2,000원으로 다시 계산됨",
    afterEx.used - afterFix.used === 1000 && afterFix.used - afterRc.used === 2000,
    `사용 ${afterEx.used}→${afterFix.used}`);

  // 지출을 지우면 되돌아가는가
  await p.click('nav button[data-tab="expense"]');
  await p.waitForTimeout(300);
  p.removeAllListeners("dialog");
  p.on("dialog", d => d.accept());
  await p.locator("#e_list tbody tr", { hasText: "감사 시험용 지출" }).locator('[data-a="del"]').click();
  await p.waitForTimeout(500);
  check("지출 삭제 → 자료에서 빠짐",
    !(await p.evaluate(() => S.expenses.some(e => e.voucherNo === "998"))));

  // 수납결의서 수정·삭제
  await p.click('nav button[data-tab="receipt"]');
  await p.waitForTimeout(300);
  await p.locator("#rcf_body tbody tr", { hasText: "감사 시험용 수납" }).locator('[data-a="edit"]').click();
  await p.waitForTimeout(400);
  check("수납결의서 수정 — 그 건이 올라옴", (await p.inputValue("#rc_no")) === "999");
  await p.locator("#rcf_body tbody tr", { hasText: "감사 시험용 수납" }).locator('[data-a="del"]').click();
  await p.waitForTimeout(500);
  check("수납결의서 삭제 → 파생 수납 기록까지 사라짐",
    !(await p.evaluate(() => S.receipts.some(r => r.voucherNo === "999"))));

  await b.close();
  console.log("=== 통과 ==="); ok.forEach(s => console.log("  ✓ " + s));
  if (dead.length) { console.log("=== 반응 없는 조작 ==="); dead.forEach(s => console.log("  · " + s)); }
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s => console.log("  ✗ " + s)); process.exit(1); }
  console.log("모두 통과");
})();
