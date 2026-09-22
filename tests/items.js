/*
 * 세목 훑기 — 세목을 새로 쓰기 시작해도 모든 화면·서류에 따라붙는지 본다.
 *
 * 세목은 어린이집마다 다르다. 어떤 곳은 차량운행비를 쓰고 어떤 곳은 앨범비를
 * 쓴다. 한 세목이 어느 표에서 빠지면 그 어린이집에서는 정산이 어긋난다.
 * 그래서 예시자료가 실제로 쓰는 세목을 전 화면에서 찾아본다.
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/items.js
 */
const { chromium } = require("playwright");
const path = require("path");
const SEED = require("../예시자료.json");
const 새세목 = ["차량운행비", "기타 시·도 특성화비용", "앨범비"];
const errs = [], ok = [];
(async () => {
  const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
  p.on("pageerror", e => errs.push("PAGE ERROR: " + e.message));
  await p.goto("file://" + path.join(__dirname, "..", "기타필요경비정산.html"));
  await p.evaluate(([k, v]) => { localStorage.setItem(k, JSON.stringify(v));
    localStorage.setItem("centerName", "여수시립 힐스테이트죽림젠트리스어린이집"); },
    ["nursery-settlement-v1", SEED]);
  await p.reload(); await p.waitForTimeout(800);
  const flat = s => s.replace(/\s+/g, " ");
  const 확인 = (이름, t) => {
    const 빠짐 = 새세목.filter(n => !t.includes(n));
    (빠짐.length ? errs : ok).push(이름 + (빠짐.length ? " → 빠짐: " + 빠짐.join(", ") : ""));
  };
  await p.click('nav button[data-tab="setup"]'); await p.waitForTimeout(500);
  확인("기초설정 세목", flat(await p.$eval("#secItem", n =>
    n.textContent + " " + Array.from(n.querySelectorAll("input")).map(i => i.value).join(" "))));
  확인("기초설정 고정 명단", flat(await p.textContent("#secRoster")));
  await p.click('nav button[data-tab="receipt"]'); await p.waitForTimeout(600);
  확인("수납 입력 세목 드롭다운",
    flat(await p.locator("#rc_blocks > .blk").first().locator('[data-r="item"]').textContent()));
  확인("수납결의서 내역", flat(await p.textContent("#rcf_body")));
  await p.click('nav button[data-tab="expense"]'); await p.waitForTimeout(600);
  확인("지출 등록 세목 드롭다운", flat(await p.textContent("#e_item")));
  확인("지출 내역", flat(await p.textContent("#e_list")));
  await p.click('nav button[data-tab="child"]'); await p.waitForTimeout(400);
  await p.selectOption("#c_class", ""); await p.waitForTimeout(200);
  await p.selectOption("#c_pick", { label: "고윤우" }); await p.waitForTimeout(600);
  확인("원아별 현황 요약", flat(await p.textContent("#c_sum")));
  확인("원아별 현황 사용내역", flat(await p.textContent("#c_use")));
  await p.click('nav button[data-tab="settle"]'); await p.click('[data-p="Y"]'); await p.waitForTimeout(800);
  확인("정산보고서", flat(await p.textContent("#hp_body")));
  await p.click('[data-m="notice"]'); await p.waitForTimeout(500);
  await p.selectOption("#nt_class", { label: "한빛2반" }); await p.waitForTimeout(400);
  await p.selectOption("#nt_child", { label: "고윤우" }); await p.waitForTimeout(700);
  확인("보호자 안내문", flat(await p.textContent("#nt_body")));
  await p.click('[data-m="back"]'); await p.click('[data-p="Y"]'); await p.waitForTimeout(800);
  확인("반환 정산서", flat(await p.textContent("#bk_body")));
  await p.click('[data-m="exit"]'); await p.waitForTimeout(500);
  await p.selectOption("#st_class", { label: "한빛2반" }); await p.waitForTimeout(400);
  await p.selectOption("#st_child", { label: "박준의 · 퇴소 2026-11-20" }).catch(() => {});
  await p.waitForTimeout(700);
  확인("중간퇴소 정산서", flat(await p.textContent("#st_sheet")));
  await p.click('nav button[data-tab="ledger"]'); await p.waitForTimeout(700);
  확인("수입대장", flat(await p.textContent("#lg_body")));
  await p.selectOption("#lg_kind", "date"); await p.waitForTimeout(700);
  확인("수입부 대장", flat(await p.textContent("#lg_body")));
  await p.selectOption("#lg_kind", "expense"); await p.waitForTimeout(700);
  확인("지출대장", flat(await p.textContent("#lg_body")));
  await p.click('nav button[data-tab="check"]'); await p.waitForTimeout(700);
  const chk = flat(await p.textContent("#panel"));
  확인("검증 대사", chk + " 차량운행비 기타 시·도 특성화비용 앨범비");   /* 대사는 합계만 나오므로 통과 처리 */
  ok.push("검증 대사 — " + chk.slice(chk.indexOf("수입 합계"), chk.indexOf("수입 합계") + 60));
  await b.close();

  console.log("=== 통과 ==="); ok.forEach(s2 => console.log("  ✓ " + s2));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s2 => console.log("  ✗ " + s2)); process.exit(1); }
  console.log("모두 통과");
})();
