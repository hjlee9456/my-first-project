/*
 * 호환 시험 — 이미 뿌려 놓은 물품관리시스템으로 만든 백업 파일이
 * 어린이집 살림도우미 안의 물품관리로 그대로 들어가는지 본다.
 *
 * 감사를 나간 어린이집들이 이미 물품관리시스템 하나만으로 물품을 등록해
 * 쓰고 있다. 살림도우미를 나눠 준 뒤 그 어린이집들이 백업 파일을 들고 와
 * 불러올 텐데, 그때 물품·사진·재물조사 이력이 하나도 빠짐없이 들어와야 한다.
 * 그래서 그때 뿌린 파일을 tests/fixtures에 그대로 두고 여기서 맞춰 본다.
 *
 * 화면틀(iframe) 안이라는 점이 특히 걸린다 — 사진은 localStorage가 아니라
 * IndexedDB에 있고, 기존 자료가 있으면 복원 전에 안전 백업을 내려받는다.
 * 두 가지 모두 화면틀 안에서 되는지 본다.
 *
 * 실행 방법 (터미널에서):
 *   python3 build.py
 *   npm i playwright
 *   node tests/compat.js
 */
const { chromium } = require("playwright");
const fs = require("fs"), path = require("path");

const DEPLOYED = path.join(__dirname, "fixtures", "물품관리시스템_배포본.html");
const BUNDLE   = path.join(__dirname, "..", "어린이집살림도우미.html");
const OUT      = fs.mkdtempSync(require("os").tmpdir() + "/compat-");

const errs = [], ok = [];
const check = (n, c, x) => (c ? ok : errs).push(n + (x ? " → " + x : ""));

/* 실제로 쓰는 모양의 자료를 심는다 — 물품 3건(사진 1·불용사진 1), 재물조사 1건, 이력 1건 */
const SEED = `(async () => {
  const items = [
    { id:"2026-001", name:"냉장고", spec:"양문형 600L", qty:1, price:1200000,
      buyDate:"2026-03-05", place:"조리실", account:"자산취득비", kind:"일반비품",
      maker:"엘지", note:"", hasPhoto:true, disposed:false },
    { id:"2026-002", name:"블록교구", spec:"대형 원목", qty:5, price:350000,
      buyDate:"2026-04-11", place:"햇살반", account:"교재교구비", kind:"교재교구",
      maker:"", note:"", hasPhoto:false, disposed:false },
    { id:"2025-014", name:"노트북", spec:"사무용", qty:1, price:900000,
      buyDate:"2025-06-02", place:"사무실", account:"자산취득비", kind:"일반비품",
      maker:"삼성", note:"", hasPhoto:false, disposed:true,
      disposalDate:"2026-08-20", disposalReason:"내용연수 경과", hasDisposalPhoto:true }
  ];
  localStorage.setItem("items", JSON.stringify(items));
  localStorage.setItem("counters", JSON.stringify({ "2026": 2, "2025": 14 }));
  localStorage.setItem("centerName", "여수시립 햇살어린이집");
  localStorage.setItem("survey", JSON.stringify({
    id: 1757000000000, year:"2026", type:"정기", startDate:"2026-09-01", endDate:"2026-09-10",
    stage: 2, results: { "2026-001": { state:"양호", note:"", hasPhoto:true },
                         "2026-002": { state:"양호", note:"", hasPhoto:false } } }));
  localStorage.setItem("surveyHistory", JSON.stringify([
    { id: 1725000000000, year:"2025", type:"정기", startDate:"2025-09-01", endDate:"2025-09-09",
      items: [ { id:"2025-014", name:"노트북", state:"불량", note:"화면 깨짐", hasPhoto:true } ] }
  ]));

  /* 사진 3장을 IndexedDB에 넣는다 */
  const png = Uint8Array.from(atob(
    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAFUlEQVR42mNk+M9QzzCKRsEoGgWjAAB6VQMLDvKVAQAAAABJRU5ErkJggg=="
  ), c => c.charCodeAt(0));
  const blob = new Blob([png], { type: "image/png" });
  const db = await new Promise(res => {
    const r = indexedDB.open("mulpumPhotos", 2);
    r.onupgradeneeded = e => { const d = e.target.result;
      if (!d.objectStoreNames.contains("photos")) d.createObjectStore("photos");
      if (!d.objectStoreNames.contains("surveyPhotos")) d.createObjectStore("surveyPhotos"); };
    r.onsuccess = e => res(e.target.result);
    r.onerror = () => res(null);
  });
  if (!db) return "IndexedDB 열기 실패";
  await new Promise(res => { const tx = db.transaction("photos", "readwrite");
    tx.objectStore("photos").put(blob, "2026-001");
    tx.objectStore("photos").put(blob, "disposal-2025-014");
    tx.oncomplete = res; tx.onerror = res; });
  await new Promise(res => { const tx = db.transaction("surveyPhotos", "readwrite");
    tx.objectStore("surveyPhotos").put(blob, "2026-001");
    tx.objectStore("surveyPhotos").put(blob, "1725000000000:2025-014");
    tx.oncomplete = res; tx.onerror = res; });
  return "ok";
})()`;

(async () => {
  const b = await chromium.launch({
    executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    downloadsPath: OUT,
  });

  /* ---------- ① 지금 뿌린 파일에서 백업을 뽑는다 ---------- */
  const c1 = await b.newContext({ viewport: { width: 1400, height: 900 }, acceptDownloads: true });
  const p1 = await c1.newPage();
  p1.on("pageerror", e => errs.push("배포본 PAGE ERROR: " + e.message));
  await p1.goto("file://" + DEPLOYED);
  const seeded = await p1.evaluate(SEED);
  check("지금 뿌린 파일에 자료·사진을 심음", seeded === "ok", seeded);
  await p1.reload();
  await p1.waitForTimeout(500);

  const [dl] = await Promise.all([
    p1.waitForEvent("download", { timeout: 15000 }),
    p1.evaluate(() => exportBackup()),
  ]);
  const backupPath = path.join(OUT, "물품관리백업.json");
  await dl.saveAs(backupPath);
  const backup = JSON.parse(fs.readFileSync(backupPath, "utf8"));
  check("백업 파일이 만들어짐", backup.type === "물품관리백업" && backup.version === 3,
    backup.type + " v" + backup.version);
  check("백업에 물품 3건", (backup.data.items || []).length === 3, String((backup.data.items||[]).length));
  check("백업에 사진 2장 (물품·불용)", Object.keys(backup.photos || {}).length === 2,
    Object.keys(backup.photos || {}).join(", "));
  check("백업에 재물조사 사진 2장", Object.keys(backup.surveyPhotos || {}).length === 2,
    Object.keys(backup.surveyPhotos || {}).join(", "));
  check("백업에 조사이력 1건", (backup.data.surveyHistory || []).length === 1);
  await c1.close();

  /* ---------- ② 살림도우미의 물품관리로 불러온다 (자료 없는 새 컴퓨터) ---------- */
  const c2 = await b.newContext({ viewport: { width: 1400, height: 900 }, acceptDownloads: true });
  const p2 = await c2.newPage();
  p2.on("pageerror", e => errs.push("통합본 PAGE ERROR: " + e.message));
  p2.on("dialog", d => d.accept());
  await p2.goto("file://" + BUNDLE);
  await p2.waitForTimeout(300);
  await p2.locator('.card[data-app="goods"]').click();
  await p2.waitForTimeout(900);

  const g = p2.frameLocator("#app");
  const inner = () => p2.frames().find(fr => fr !== p2.mainFrame());

  // 화면틀 안에서 IndexedDB를 쓸 수 있는지부터 본다
  const idb = await inner().evaluate(() => new Promise(res => {
    try {
      const r = indexedDB.open("probe", 1);
      r.onsuccess = () => { r.result.close(); indexedDB.deleteDatabase("probe"); res("ok"); };
      r.onerror = () => res("열기 실패");
      r.onblocked = () => res("막힘");
    } catch (e) { res("예외: " + e.message); }
  }));
  check("통합본 화면틀 안에서 사진 저장소(IndexedDB)를 쓸 수 있음", idb === "ok", idb);

  /* 사람이 「백업 파일 가져오기」로 파일을 고르는 것과 같은 경로로 넣는다.
     (시험 도구의 setInputFiles는 숨은 입력칸에 파일을 넣지 못한다) */
  const picked = await inner().evaluate(text => {
    const inp = document.getElementById("import-file");
    const dt = new DataTransfer();
    dt.items.add(new File([text], "물품관리_백업_2026-09-15.json", { type: "application/json" }));
    inp.files = dt.files;
    inp.dispatchEvent(new Event("change", { bubbles: true }));
    return inp.files.length;
  }, fs.readFileSync(backupPath, "utf8"));
  check("백업 파일을 고르면 화면틀 안으로 전달됨", picked === 1, String(picked));
  await p2.waitForTimeout(3500);

  const after = await inner().evaluate(() => new Promise(async res => {
    const j = k => JSON.parse(localStorage.getItem(k) || "null");
    const db = await new Promise(r2 => {
      const r = indexedDB.open("mulpumPhotos", 2);
      r.onupgradeneeded = e => { const d = e.target.result;
        if (!d.objectStoreNames.contains("photos")) d.createObjectStore("photos");
        if (!d.objectStoreNames.contains("surveyPhotos")) d.createObjectStore("surveyPhotos"); };
      r.onsuccess = e => r2(e.target.result); r.onerror = () => r2(null);
    });
    const keys = store => new Promise(r2 => {
      if (!db) return r2([]);
      const q = db.transaction(store, "readonly").objectStore(store).getAllKeys();
      q.onsuccess = () => r2(q.result); q.onerror = () => r2([]);
    });
    const size = (store, key) => new Promise(r2 => {
      if (!db) return r2(0);
      const q = db.transaction(store, "readonly").objectStore(store).get(key);
      q.onsuccess = () => r2(q.result ? q.result.size : 0); q.onerror = () => r2(0);
    });
    res({
      items: j("items"), counters: j("counters"), centerName: localStorage.getItem("centerName"),
      survey: j("survey"), history: j("surveyHistory"),
      photoKeys: (await keys("photos")).sort(),
      surveyPhotoKeys: (await keys("surveyPhotos")).sort(),
      photoSize: await size("photos", "2026-001"),
    });
  }));

  if (!after.items) { console.log("=== 들어오지 않음 ==="); console.log(JSON.stringify(after).slice(0,500));
    ok.forEach(s => console.log("  ✓ " + s)); errs.forEach(s => console.log("  ✗ " + s)); process.exit(1); }
  check("물품 3건이 그대로 들어옴", (after.items || []).length === 3, String((after.items||[]).length));
  check("물품 내용이 같음 (고유번호·품명·금액)",
    after.items[0].id === "2026-001" && after.items[0].name === "냉장고" &&
    after.items[0].price === 1200000 && after.items[2].disposed === true,
    JSON.stringify(after.items[0]).slice(0, 90));
  check("고유번호 채번 상태가 이어짐", after.counters["2026"] === 2 && after.counters["2025"] === 14,
    JSON.stringify(after.counters));
  check("어린이집 이름도 함께 들어옴", after.centerName === "여수시립 햇살어린이집", after.centerName);
  check("진행 중 재물조사가 그대로", after.survey.year === "2026" && after.survey.stage === 2 &&
    Object.keys(after.survey.results).length === 2, JSON.stringify(after.survey).slice(0, 80));
  check("조사이력 1건이 그대로", (after.history || []).length === 1 &&
    after.history[0].items[0].note === "화면 깨짐");
  check("물품·불용 사진 2장이 되살아남",
    after.photoKeys.join() === "2026-001,disposal-2025-014", after.photoKeys.join());
  check("재물조사 사진 2장이 되살아남",
    after.surveyPhotoKeys.join() === "1725000000000:2025-014,2026-001", after.surveyPhotoKeys.join());
  check("사진이 빈 파일이 아님", after.photoSize > 0, after.photoSize + "바이트");

  // 화면에 실제로 그려지는지
  await g.locator('.card, [onclick*="ledger"]').first().waitFor({ timeout: 5000 }).catch(() => {});
  await inner().evaluate(() => showScreen("ledger"));
  await p2.waitForTimeout(700);
  const led = (await g.locator("#ledger-list").textContent()).replace(/\s+/g, " ");
  check("물품대장 화면에 그대로 나옴",
    /냉장고/.test(led) && /블록교구/.test(led), led.slice(0, 120));

  /* ---------- ③ 이미 쓰던 자료가 있는 채로 불러오는 경우 ----------
     이때는 복원 전에 「교체전 현재자료 백업」을 먼저 내려받는다.
     화면틀 안에서 그 내려받기가 막히면 복원까지 통째로 멈춘다. */
  const c3 = await b.newContext({ viewport: { width: 1400, height: 900 }, acceptDownloads: true });
  const p3 = await c3.newPage();
  p3.on("pageerror", e => errs.push("통합본 PAGE ERROR: " + e.message));
  p3.on("dialog", d => d.accept());
  let safety = null;
  p3.on("download", d => { safety = d; });
  await p3.goto("file://" + BUNDLE);
  await p3.evaluate(() => {
    localStorage.setItem("items", JSON.stringify([{ id:"2026-099", name:"이미 쓰던 물품",
      spec:"", qty:1, price:1000, buyDate:"2026-09-01", place:"", account:"수용비",
      kind:"일반비품", maker:"", note:"", hasPhoto:false, disposed:false }]));
    localStorage.setItem("counters", JSON.stringify({ "2026": 99 }));
  });
  await p3.locator('.card[data-app="goods"]').click();
  await p3.waitForTimeout(900);
  const in3 = () => p3.frames().find(fr => fr !== p3.mainFrame());
  await in3().evaluate(text => {
    const inp = document.getElementById("import-file");
    const dt = new DataTransfer();
    dt.items.add(new File([text], "물품관리_백업.json", { type: "application/json" }));
    inp.files = dt.files;
    inp.dispatchEvent(new Event("change", { bubbles: true }));
  }, fs.readFileSync(backupPath, "utf8"));
  await p3.waitForTimeout(4000);
  check("쓰던 자료가 있으면 교체 전에 안전 백업을 내려받음", !!safety);
  const items3 = await in3().evaluate(() => JSON.parse(localStorage.getItem("items") || "[]"));
  check("안전 백업 뒤에도 복원이 끝까지 진행됨",
    items3.length === 3 && items3[0].name === "냉장고",
    items3.length + "건 · " + (items3[0] || {}).name);

  await b.close();
  fs.rmSync(OUT, { recursive: true, force: true });

  console.log("=== 통과 ==="); ok.forEach(s => console.log("  ✓ " + s));
  if (errs.length) { console.log("=== 실패 ==="); errs.forEach(s => console.log("  ✗ " + s)); process.exit(1); }
  console.log("모두 통과");
})();
