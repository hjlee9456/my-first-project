/*
 * 호환 시험 — 배포한 판으로 만든 백업 파일이 지금 판에서 그대로 열리는지 본다.
 *
 * 2026-09-18, 첫 어린이집에 프로그램을 건넸다. 그 어린이집은 이 판으로 자료를
 * 쌓는다. 앞으로 무엇을 고치든 그 백업 파일은 반드시 열려야 하고, 열었을 때
 * 숫자가 한 원도 달라져서는 안 된다. 어린이집이 이미 보호자에게 나눠 준
 * 정산서와 어긋나기 때문이다.
 *
 * 그래서 배포한 판(tests/fixtures/기타필요경비정산_배포본.html)으로 만든 백업
 * (tests/fixtures/정산_배포본_백업.json)을 붙박아 두고, 그 파일을 지금 판에
 * 넣어 배포판과 같은 숫자가 나오는지 맞춰 본다.
 *
 * 숫자는 미리 적어 두지 않는다. 배포판을 실제로 띄워 그 자리에서 읽어 와
 * 지금 판과 견준다. 그래야 「기대값을 고쳐 시험을 통과시키는」 일이 생기지 않는다.
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/compat-settle.js
 */
const { chromium } = require("playwright");
const path = require("path");

const DEPLOYED = path.join(__dirname, "fixtures", "기타필요경비정산_배포본.html");
const BACKUP   = path.join(__dirname, "fixtures", "정산_배포본_백업.json");
const NOW      = path.join(__dirname, "..", "기타필요경비정산.html");
const SAVED    = require("./fixtures/정산_배포본_백업.json");

const errs = [], ok = [];
const check = (n, c, x) => (c ? ok : errs).push(n + (x ? " → " + x : ""));
const flat = s => String(s || "").replace(/\s+/g, " ");

/** 두 판에서 똑같이 뽑아 볼 숫자들 — 계산의 뼈대를 모두 훑는다 */
const MEASURE = () => {
  const out = { years: {}, 방식: cardFeeMode() };
  for (const y of Object.keys(S.years).sort()) {
    switchYear(+y);
    const from = fyStart(S.fiscalYear), to = fyEnd(S.fiscalYear);
    const per = {};
    for (const c of S.children) {
      for (const it of S.items) {
        const b = balance(c.id, it.id, from, to);
        if (!b.paid && !b.totalUsed) continue;
        per[c.name + "/" + it.name] = [b.paid, b.transferIn, b.totalUsed, b.left];
      }
    }
    const cb = centerBurden(from, to);
    out.years[y] = {
      반: S.classes.map(c => c.name),
      원아: S.children.map(c => c.name),
      세목: S.items.map(i => i.name + (i.enabled ? "" : "(끔)")),
      명단: S.rosters.map(r => r.name + ":" + r.childIds.length),
      결의서: S.vouchers.map(v => [v.date, v.voucherNo, v.itemId, v.total, v.cardFee || 0].join("|")),
      지출: S.expenses.map(e => [e.date, e.voucherNo, e.itemId, e.total, e.needAmount,
                                 e.operAmount || 0, e.allocations.length].join("|")),
      잔액: per,
      부담: [cb.oper, cb.fee, cb.rounding, cb.total],
    };
  }
  return out;
};

async function measure(b, file) {
  const p = await b.newPage({ viewport: { width: 1400, height: 900 } });
  const bad = [];
  p.on("pageerror", e => bad.push(e.message));
  await p.goto("file://" + file);
  await p.evaluate(([k, v]) => { localStorage.setItem(k, JSON.stringify(v));
    localStorage.setItem("centerName", "여수시립 힐스테이트죽림젠트리스어린이집"); },
    ["nursery-settlement-v1", SAVED]);
  await p.reload();
  await p.waitForTimeout(700);
  const got = await p.evaluate(MEASURE);
  return { p, got, bad };
}

(async () => {
  const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });

  const A = await measure(b, DEPLOYED);   // 배포한 판
  const B = await measure(b, NOW);        // 지금 판

  check("배포판에서 오류 없이 열림", A.bad.length === 0, A.bad.join(" / "));
  check("지금 판에서 오류 없이 열림", B.bad.length === 0, B.bad.join(" / "));

  check("보관 중인 회계연도가 같음",
    Object.keys(A.got.years).join() === Object.keys(B.got.years).join(),
    Object.keys(A.got.years).join() + " vs " + Object.keys(B.got.years).join());
  check("카드수수료 처리 방식이 같음", A.got.방식 === B.got.방식,
    A.got.방식 + " vs " + B.got.방식);

  for (const y of Object.keys(A.got.years)) {
    const a = A.got.years[y], c = B.got.years[y] || {};
    const same = (k, label) => {
      const x = JSON.stringify(a[k]), z = JSON.stringify(c[k]);
      check(`${y}년도 ${label}`, x === z,
        x === z ? "" : "배포판 " + String(x).slice(0, 90) + " / 지금 " + String(z).slice(0, 90));
    };
    same("반", "반 구성");
    same("원아", "원아 명부");
    same("세목", "세목");
    same("명단", "고정 명단");
    same("결의서", `수납결의서 ${a.결의서.length}건`);
    same("지출", `지출 ${a.지출.length}건`);
    same("잔액", `원아×세목 잔액 ${Object.keys(a.잔액).length}칸`);
    same("부담", "어린이집 부담 집계");
  }

  /* 숫자만이 아니라 서류도 실제로 나와야 한다 */
  const pg = B.p;
  await pg.evaluate(() => switchYear(2026));
  await pg.waitForTimeout(500);
  await pg.click('nav button[data-tab="settle"]');
  await pg.click('[data-p="Y"]');
  await pg.waitForTimeout(700);
  check("불러온 자료로 정산보고서가 나옴",
    /필요경비 정산보고서/.test(await pg.textContent("#hp_body")));
  await pg.click('[data-m="back"]'); await pg.click('[data-p="Y"]');
  await pg.waitForTimeout(700);
  check("불러온 자료로 반환 정산서가 나옴",
    /필요경비 반환 정산서/.test(await pg.textContent("#bk_body")));
  await pg.click('nav button[data-tab="ledger"]');
  await pg.waitForTimeout(700);
  check("불러온 자료로 대장이 나옴",
    /개인별 원아 수입대장/.test(await pg.textContent("#lg_body")));
  await pg.click('nav button[data-tab="check"]');
  await pg.waitForTimeout(600);
  const chk = flat(await pg.textContent("#panel"));
  check("검증에 저장 차단급 오류가 없음", !/저장 차단/.test(chk) && /대사/.test(chk),
    chk.slice(chk.indexOf("점검 결과"), chk.indexOf("점검 결과") + 90));

  /* 한 장에 여러 세목을 담은 결의서가 그대로 살아 있는지 */
  await pg.click('nav button[data-tab="receipt"]');
  await pg.waitForTimeout(600);
  const multi = await pg.evaluate(() => {
    const by = {};
    for (const v of S.vouchers) { const k = v.date + "|" + v.voucherNo; (by[k] = by[k] || []).push(v.itemId); }
    return Object.values(by).filter(a => a.length > 1).length;
  });
  check("한 장에 여러 세목을 담은 결의서가 남아 있음", multi > 0, multi + "장");

  await b.close();
  console.log("=== 통과 ==="); ok.forEach(s => console.log("  ✓ " + s));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s => console.log("  ✗ " + s)); process.exit(1); }
  console.log("모두 통과");
})();
