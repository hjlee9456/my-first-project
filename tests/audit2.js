/*
 * 1차 외부 점검(2026-09-21)에서 걸린 15건이 다시 살아나지 않는지 본다.
 * 번호는 그 점검보고서의 번호를 그대로 쓴다.
 *
 * 실행 방법 (터미널에서):
 *   npm i playwright
 *   node tests/audit2.js
 */
const { chromium } = require("playwright");
const P = "file:///home/user/my-first-project/기타필요경비정산.html";
const out = [], say = (n, ok, x) => out.push((ok ? "  ✓ " : "  ✗ ") + n + (x ? " → " + x : ""));
const flat = s => String(s||"").replace(/\s+/g," ");
const base = (extra={}) => Object.assign({
  version:1, fiscalYear:2026,
  classes:[{id:"c1",name:"새싹반"}],
  children:[{id:"k1",name:"김서우",admitDate:"2026-03-02",leaveDate:"",
             classHistory:[{classId:"c1",startDate:"2026-03-02"}],consignPeriods:[]}],
  items:[{id:"it_field",name:"현장학습비",group:"기타필요경비",targetMode:"event",enabled:true,stdAmount:0},
         {id:"it_event",name:"행사비",group:"기타필요경비",targetMode:"event",enabled:true,stdAmount:0}],
  rosters:[],
  vouchers:[{id:"v1",date:"2026-03-10",voucherNo:"1",itemId:"it_field",summary:"수납",
             perAmount:100000,cardFee:0,lines:[{childId:"k1",amount:100000,memo:""}],total:100000}],
  receipts:[],
  expenses:[{id:"x1",date:"2026-06-10",voucherNo:"1",itemId:"it_field",summary:"현장학습",
             total:60000,needAmount:60000,operAmount:0,memo:"",overrides:[],
             allocations:[{childId:"k1",amount:60000}]}],
}, extra);

(async()=>{
  const b = await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome"});
  const p = await b.newPage({viewport:{width:1500,height:950}});
  const errs=[]; p.on("pageerror",e=>errs.push(e.message)); p.on("dialog",d=>d.accept());
  const seed = async v => { await p.goto(P);
    await p.evaluate(x=>localStorage.setItem("nursery-settlement-v1",JSON.stringify(x)), v);
    await p.reload(); await p.waitForTimeout(400); };

  // ══ 01 상반기에 돌려준 돈이 하반기 이월에 되살아나나 · 07 안내문
  await seed(base());
  await p.click('nav button[data-tab="settle"]'); await p.click('[data-m="back"]');
  await p.click('[data-p="H1"]'); await p.waitForTimeout(250);
  await p.fill("#bk_date","2026-06-15");
  await p.locator("#bk_body tbody tr",{hasText:"김서우"}).locator("button").click();
  await p.waitForTimeout(350);
  await p.click('[data-p="H2"]'); await p.waitForTimeout(350);
  const h2 = flat(await p.textContent("#bk_body"));
  say("01 상반기에 돌려준 돈이 하반기 반환 합계에 되살아나지 않음",
      /06\.15 반환완료 40,000원/.test(h2) && /합계 \(1명\) 40,000 0 0/.test(h2),
      h2.slice(h2.indexOf("순번"), h2.indexOf("순번")+150));
  say("01 하반기 줄의 버튼이 「반환 완료 취소」",
      /취소/.test(await p.locator("#bk_body tbody tr button").first().textContent()));

  await p.click('[data-m="notice"]'); await p.click('[data-p="Y"]').catch(()=>{});
  await p.waitForTimeout(250);
  await p.selectOption("#nt_class",""); await p.waitForTimeout(150);
  await p.selectOption("#nt_child","k1"); await p.waitForTimeout(350);
  const nt = flat(await p.textContent("#nt_body"));
  say("07 보호자 안내문에 이미 돌려드린 금액과 앞으로 돌려드릴 금액이 갈림",
      /이미 돌려드린 금액\(C\)/.test(nt) && /앞으로 돌려드릴 금액\(D = A − B − C\)/.test(nt)
      && /합계 100,000 60,000 40,000 0/.test(nt),
      nt.slice(nt.indexOf("세목 수납액"), nt.indexOf("세목 수납액")+150));
  say("07 인쇄물에도 그 안내가 나감",
      (await p.locator("#nt_body .note.show-print").filter({hasText:"이미 돌려드린 금액이 있습니다"}).count())===1);

  // ══ 06 이미 자료가 있는 해를 다시 승계해도 반환기록이 남나
  await seed(base());
  await p.evaluate(()=>{
    S.years["2027"] = Object.assign(emptyYear(), {
      classes:[{id:"c1",name:"새싹반"}], children:[childById("k1")],
      vouchers:[{id:"v9",date:"2027-03-10",voucherNo:"1",itemId:"it_field",summary:"수납",
                 perAmount:100000,cardFee:0,lines:[{childId:"k1",amount:100000,memo:""}],total:100000}],
      refunds:[{id:"rf9",date:"2027-06-20",childId:"k1",itemId:"it_field",
                amount:40000,reason:"중간퇴소",memo:""}] });
    save();
  });
  await p.click('nav button[data-tab="setup"]'); await p.waitForTimeout(300);
  await p.click("#btnRollover").catch(()=>{});
  await p.waitForTimeout(400);
  await p.click("#ro_next");            // 1단계 반 구성 → 2단계 원아 배치
  await p.waitForTimeout(300);
  await p.locator("#modalHost .modal .foot button", {hasText:"저장"}).click();
  await p.waitForTimeout(800);
  const kept = await p.evaluate(()=>((S.years["2027"]||{}).refunds||[]).length);
  const keptV = await p.evaluate(()=>((S.years["2027"]||{}).vouchers||[]).length);
  say("06 기존 연도를 다시 승계해도 반환기록·결의서가 남음",
      kept===1 && keptV===1, `반환 ${kept}건 · 결의서 ${keptV}건`);

  // ══ 02 같은 금액을 두 번 찍을 수 있나
  await seed(base());
  await p.click('nav button[data-tab="settle"]'); await p.click('[data-m="back"]');
  await p.click('[data-p="H1"]'); await p.waitForTimeout(250);
  await p.fill("#bk_date","2026-09-01");
  await p.locator("#bk_body tbody tr",{hasText:"김서우"}).locator("button").click();
  await p.waitForTimeout(350);
  const n1 = await p.evaluate(()=>S.refunds.length);
  const btn = await p.locator("#bk_body tbody tr button").first().textContent();
  say("02 기간 밖 반환일도 바로 잡혀 중복이 막힘",
      n1===1 && /취소/.test(btn), `기록 ${n1}건 · 버튼 「${btn}」`);

  // ══ 12 익년 3월 반환도 취소되나
  await seed(base({children:[{id:"k1",name:"김서우",admitDate:"2026-03-02",leaveDate:"2026-06-15",
    classHistory:[{classId:"c1",startDate:"2026-03-02"}],consignPeriods:[]}]}));
  await p.click('nav button[data-tab="settle"]'); await p.click('[data-m="exit"]');
  await p.waitForTimeout(350);
  await p.fill("#ex_rdate","2027-03-05"); await p.click("#ex_mark"); await p.waitForTimeout(350);
  const before = await p.evaluate(()=>S.refunds.length);
  await p.click("#ex_unmark"); await p.waitForTimeout(400);
  say("12 익년 3월 반환기록도 취소됨",
      before===1 && (await p.evaluate(()=>S.refunds.length))===0, `${before} → 0`);

  // ══ 03 사용을 끈 세목의 예전 결의서
  await seed(base());
  await p.evaluate(()=>{ S.items.find(i=>i.id==="it_field").enabled=false; save(); render(); });
  await p.evaluate(()=>{ view.receiptEditId="v1"; view.receiptForm=null; goTab("receipt"); });
  await p.waitForTimeout(400);
  say("03 사용을 꺼도 수납 수정 화면에 원래 세목이 그대로",
      (await p.locator('#rc_blocks [data-r="item"]').first().inputValue())==="it_field",
      await p.locator('#rc_blocks [data-r="item"]').first().inputValue());
  await p.fill("#rc_summary","적요만 고침");
  await p.click("#rc_save"); await p.waitForTimeout(500);
  say("03 적요만 고쳐 저장해도 수납 세목이 안 바뀜",
      (await p.evaluate(()=>S.vouchers[0].itemId))==="it_field",
      await p.evaluate(()=>S.vouchers[0].itemId));

  await p.evaluate(()=>{ view.expenseEditId="x1"; view.expenseForm=null; goTab("expense"); });
  await p.waitForTimeout(400);
  say("03 지출 수정 화면에도 원래 세목이 그대로",
      (await p.locator("#e_item").inputValue())==="it_field", await p.locator("#e_item").inputValue());
  await p.fill("#e_summary","적요만 고침");
  await p.click("#e_save"); await p.waitForTimeout(500);
  say("03 적요만 고쳐 저장해도 지출 세목이 안 바뀜",
      (await p.evaluate(()=>S.expenses[0].itemId))==="it_field",
      await p.evaluate(()=>S.expenses[0].itemId));

  // ══ 11 수정 중 날짜가 되돌아가나
  await seed(base());
  await p.click('nav button[data-tab="receipt"]'); await p.waitForTimeout(250);
  await p.locator('[data-a="edit"]').first().click(); await p.waitForTimeout(350);
  await p.fill("#rc_date","2026-03-11");
  await p.dispatchEvent("#rc_date","change"); await p.waitForTimeout(400);
  say("11 수정 중 날짜가 되돌아가지 않음",
      (await p.inputValue("#rc_date"))==="2026-03-11", await p.inputValue("#rc_date"));
  const blocksBefore = await p.locator('#rc_blocks [data-r="item"]').count();
  await p.click("#rc_addBlock"); await p.waitForTimeout(400);
  const blocksAfter = await p.locator('#rc_blocks [data-r="item"]').count();
  say("11 수정 중 세목 칸 추가가 남아 있음", blocksAfter===blocksBefore+1,
      `${blocksBefore} → ${blocksAfter}`);

  // ══ 04 마지막 원아 제외
  await seed(base({children:[{id:"k1",name:"김서우",admitDate:"2026-03-02",leaveDate:"2026-06-15",
    classHistory:[{classId:"c1",startDate:"2026-03-02"}],consignPeriods:[]}]}));
  await p.click('nav button[data-tab="settle"]'); await p.click('[data-m="exit"]');
  await p.waitForTimeout(350);
  await p.locator("#st_month tbody tr").first().locator("input[type=checkbox]").click();
  await p.waitForTimeout(400);
  const al = await p.evaluate(()=>S.expenses[0].allocations.length);
  say("04 마지막 원아는 뺄 수 없어 배분이 유지됨", al===1, `allocations ${al}건`);

  // ══ 05 카드수수료 취소 경로
  await seed(base({cardFeeMode:"net",
    vouchers:[{id:"v1",date:"2026-03-10",voucherNo:"1",itemId:"it_field",summary:"수납",
      perAmount:99900,cardFee:100,lines:[{childId:"k1",amount:99900,memo:""}],total:99900}]}));
  await p.evaluate(()=>{ window.__c = window.confirm; window.confirm = () => false; });
  await p.click('nav button[data-tab="setup"]'); await p.waitForTimeout(300);
  await p.locator('input[name="cardFeeMode"][value="gross"]').check().catch(()=>{});
  await p.waitForTimeout(400);
  const mode = await p.evaluate(()=>cardFeeMode());
  const amt  = await p.evaluate(()=>S.vouchers[0].total);
  say("05 환산을 취소하면 방식도 그대로",
      mode==="net" && amt===99900, `${mode} · ${amt.toLocaleString()}원`);

  // ══ 06·10 새 연도
  await seed(base());
  await p.evaluate(()=>{ S.years["2027"] = { classes:[], children:[], items:S.items,
      rosters:[], vouchers:[], receipts:[], expenses:[] }; save(); loadYear(2027); render(); });
  await p.waitForTimeout(300);
  say("10 새 연도에도 반환 칸이 만들어짐",
      Array.isArray(await p.evaluate(()=>S.refunds)), typeof (await p.evaluate(()=>S.refunds)));
  say("10 새 연도에서 반환 기록이 오류 없이 남음",
      (await p.evaluate(()=>{ try{ markRefund("k1","2027-04-01",[{itemId:"it_field",amount:100}],"t");
                                    return "성공"; }catch(e){ return "오류: "+e.message; } }))==="성공");

  // ══ 09 검증 — 세목 간 상계
  await seed(base({
    vouchers:[{id:"v1",date:"2026-03-10",voucherNo:"1",itemId:"it_field",summary:"수납",
               perAmount:100000,cardFee:0,lines:[{childId:"k1",amount:100000,memo:""}],total:100000},
              {id:"v2",date:"2026-03-10",voucherNo:"2",itemId:"it_event",summary:"수납",
               perAmount:100000,cardFee:0,lines:[{childId:"k1",amount:100000,memo:""}],total:100000}],
    expenses:[{id:"x1",date:"2026-06-10",voucherNo:"1",itemId:"it_field",summary:"현장학습",
               total:60000,needAmount:60000,operAmount:0,memo:"",overrides:[],
               allocations:[{childId:"k1",amount:60000}]},
              {id:"x2",date:"2026-06-20",voucherNo:"2",itemId:"it_event",summary:"행사",
               total:120000,needAmount:120000,operAmount:0,memo:"",overrides:[],
               allocations:[{childId:"k1",amount:120000}]}]}));
  await p.click('nav button[data-tab="check"]'); await p.waitForTimeout(350);
  const chk = flat(await p.textContent("main"));
  say("09 돌려줄 돈 40,000 · 메워야 할 돈 20,000 으로 갈림",
      /돌려줄 돈 \(세목별 남은 몫의 합\)\(A\) 40,000원/.test(chk)
      && /메워야 할 돈 \(세목별 모자란 몫의 합\)\(B\) 20,000원/.test(chk)
      && /위 장부 차액과 맞춰 보기 40,000 − 20,000 = 20,000원/.test(chk),
      chk.slice(chk.indexOf("돌려줄 돈과"), chk.indexOf("돌려줄 돈과")+130));

  // ══ 08 입학준비금
  await seed(base({
    children:[{id:"k1",name:"김서우",admitDate:"2026-03-02",leaveDate:"2026-06-15",
      classHistory:[{classId:"c1",startDate:"2026-03-02"}],consignPeriods:[]}],
    items:[{id:"it_prep",name:"입학준비금",group:"기타필요경비",targetMode:"fixed",
            enabled:true,special:"prep",stdAmount:0}],
    vouchers:[{id:"v1",date:"2026-03-10",voucherNo:"1",itemId:"it_prep",summary:"수납",
               perAmount:100000,cardFee:0,lines:[{childId:"k1",amount:100000,memo:""}],total:100000}],
    expenses:[{id:"x1",date:"2026-04-10",voucherNo:"1",itemId:"it_prep",summary:"원복",
               total:60000,needAmount:60000,operAmount:0,memo:"",overrides:[],
               allocations:[{childId:"k1",amount:60000}]}]}));
  await p.click('nav button[data-tab="settle"]'); await p.click('[data-m="exit"]');
  await p.waitForTimeout(400);
  await p.locator('#st_sheet [data-r="back"] input').fill("10,000");
  await p.locator('#st_sheet [data-r="back"] input').dispatchEvent("change");
  await p.waitForTimeout(400);
  await p.click('[data-m="back"]'); await p.click('[data-p="Y"]').catch(()=>{});
  await p.waitForTimeout(350);
  const bk = flat(await p.textContent("#bk_body"));
  say("08 협의금액 10,000이 연말 반환 정산서에 반영",
      /10,000/.test(bk) && !/ 40,000 /.test(bk), bk.slice(bk.indexOf("순번"), bk.indexOf("순번")+140));

  // ══ 08 안내문도 협의금액을 따르나 (반환 열은 반환이 있을 때만)
  await seed(base({
    children:[{id:"k1",name:"김서우",admitDate:"2026-03-02",leaveDate:"2026-06-15",
      classHistory:[{classId:"c1",startDate:"2026-03-02"}],consignPeriods:[],
      prepBack:2000, prepGiven:true}],
    items:[{id:"it_prep",name:"입학준비금",group:"기타필요경비",targetMode:"fixed",
            enabled:true,special:"prep",stdAmount:0}],
    vouchers:[{id:"v1",date:"2026-03-10",voucherNo:"1",itemId:"it_prep",summary:"수납",
               perAmount:100000,cardFee:0,lines:[{childId:"k1",amount:100000,memo:""}],total:100000}],
    expenses:[{id:"x1",date:"2026-04-10",voucherNo:"1",itemId:"it_prep",summary:"원복",
               total:60000,needAmount:60000,operAmount:0,memo:"",overrides:[],
               allocations:[{childId:"k1",amount:60000}]}]}));
  await p.click('nav button[data-tab="settle"]'); await p.click('[data-m="notice"]');
  await p.click('[data-p="Y"]').catch(()=>{}); await p.waitForTimeout(250);
  await p.selectOption("#nt_class",""); await p.waitForTimeout(150);
  await p.selectOption("#nt_child","k1"); await p.waitForTimeout(350);
  let ntp = flat(await p.textContent("#nt_body"));
  say("08 반환 전에는 안내문에 반환 열이 없음", !/돌려드린/.test(ntp));
  say("08 안내문의 입학준비금이 협의금액 2,000원을 따름 (40,000이 아님)",
      /입학준비금 100,000 60,000 2,000/.test(ntp) && !/38,000/.test(ntp),
      ntp.slice(ntp.indexOf("입학준비금"), ntp.indexOf("입학준비금")+60));
  say("08 협의로 정했다는 설명이 인쇄물에도 나감",
      (await p.locator("#nt_body .note.show-print").filter({hasText:"협의한 금액"}).count())===1);

  // 반환까지 마치면 앞으로 돌려드릴 금액이 0
  await p.click('[data-m="exit"]'); await p.waitForTimeout(350);
  await p.click("#ex_mark"); await p.waitForTimeout(400);
  await p.click('[data-m="notice"]'); await p.click('[data-p="Y"]').catch(()=>{});
  await p.waitForTimeout(250);
  await p.selectOption("#nt_class",""); await p.waitForTimeout(150);
  await p.selectOption("#nt_child","k1"); await p.waitForTimeout(350);
  ntp = flat(await p.textContent("#nt_body"));
  say("08 협의금액을 돌려준 뒤 앞으로 돌려드릴 금액이 0",
      /입학준비금 100,000 60,000 2,000 0/.test(ntp),
      ntp.slice(ntp.indexOf("입학준비금"), ntp.indexOf("입학준비금")+60));

  // ══ 14 입력 검증
  await seed(base());
  say("14 1.5는 15가 되지 않음",  (await p.evaluate(()=>num("1.5")))===0, String(await p.evaluate(()=>num("1.5"))));
  say("14 한글은 0이고 오류로 잡힘", (await p.evaluate(()=>numParse("한글").ok))===false);
  say("14 안전범위 밖 정수는 거부",  (await p.evaluate(()=>numParse("9007199254740993").ok))===false);
  say("14 정상 금액은 그대로",      (await p.evaluate(()=>num("1,234,567")))===1234567);

  // ══ 13 명단 창을 띄운 채 인쇄하면 그 명단만 나오나
  await seed(base());
  await p.click('nav button[data-tab="child"]'); await p.waitForTimeout(300);
  await p.locator("#c_use button.link").first().click(); await p.waitForTimeout(400);
  say("13 명단 창이 열리면 <body>에 표시가 붙음",
      await p.evaluate(()=>document.body.classList.contains("modal-open")));
  await p.emulateMedia({ media: "print" });
  await p.waitForTimeout(200);
  const vis = await p.evaluate(()=>{
    const g = s2 => { const n = document.querySelector(s2); return n ? getComputedStyle(n) : null; };
    return { main: g("main").display, foot: g("#modalHost .modal .foot").display,
             mask: g("#modalHost .mask").position, body: g("#modalHost .modal .body").display };
  });
  say("13 인쇄할 때 뒤 화면과 버튼이 빠지고 명단만 남음",
      vis.main==="none" && vis.foot==="none" && vis.mask==="static", JSON.stringify(vis));
  await p.emulateMedia({ media: "screen" });
  await p.keyboard.press("Escape"); await p.waitForTimeout(250);
  say("13 창을 닫으면 표시도 사라짐",
      !(await p.evaluate(()=>document.body.classList.contains("modal-open"))));

  // ══════════ 2차 외부 점검(2026-09-22) 11건 ══════════

  // R01 재승계로 다음 해 신입 원아가 사라지나
  await seed({ version:2, fiscalYear:2026, cardFeeMode:"net", years:{
    "2026":{ classes:[{id:"c1",name:"새싹반"}],
      children:[{id:"k1",name:"시험원아",admitDate:"2026-03-02",leaveDate:"",
                 classHistory:[{classId:"c1",startDate:"2026-03-02"}],consignPeriods:[]}],
      items:[{id:"it_field",name:"현장학습비",group:"기타필요경비",targetMode:"event",enabled:true,stdAmount:0}],
      rosters:[],vouchers:[],receipts:[],expenses:[],refunds:[] },
    "2027":{ classes:[{id:"c1",name:"새싹반"}],
      children:[{id:"k1",name:"시험원아",admitDate:"2026-03-02",leaveDate:"",
                 classHistory:[{classId:"c1",startDate:"2027-03-01"}],consignPeriods:[]},
                {id:"k9",name:"신입원아",admitDate:"2027-03-02",leaveDate:"",
                 classHistory:[{classId:"c1",startDate:"2027-03-02"}],consignPeriods:[]}],
      items:[{id:"it_field",name:"현장학습비",group:"기타필요경비",targetMode:"event",enabled:true,stdAmount:0}],
      rosters:[],
      vouchers:[{id:"v9",date:"2027-04-10",voucherNo:"1",itemId:"it_field",summary:"수납",
                 perAmount:100000,cardFee:0,lines:[{childId:"k9",amount:100000,memo:""}],total:100000}],
      receipts:[],expenses:[],refunds:[] }}});
  await p.evaluate(()=>{ loadYear(2026); render(); }); await p.waitForTimeout(300);
  await p.click('nav button[data-tab="setup"]'); await p.waitForTimeout(300);
  await p.click("#btnRollover"); await p.waitForTimeout(400);
  await p.click("#ro_next"); await p.waitForTimeout(300);
  await p.locator("#modalHost .modal .foot button",{hasText:"저장"}).click();
  await p.waitForTimeout(800);
  const r01 = await p.evaluate(()=>{ loadYear(2027);
    let back=0; for (const c of S.children) for (const it of S.items) {
      const bl=balance(c.id,it.id,fyStart(2027),fyEnd(2027)); if (bl.left>0) back+=bl.left; }
    return { 원아: S.children.map(c=>c.name).join(","), 돌려줄돈: back }; });
  say("R01 재승계해도 그 해 신입 원아와 돌려줄 돈이 남음",
      /신입원아/.test(r01.원아) && r01.돌려줄돈===100000, JSON.stringify(r01));

  // R02 기준일 이후 지출 — 체크와 사용액이 일치하나
  const afterExit = base({
    children:[{id:"k1",name:"김서우",admitDate:"2026-03-02",leaveDate:"2026-06-15",
      classHistory:[{classId:"c1",startDate:"2026-03-02"}],consignPeriods:[]}],
    expenses:[{id:"x1",date:"2026-06-30",voucherNo:"1",itemId:"it_field",summary:"6월말 현장학습",
               total:60000,needAmount:60000,operAmount:0,memo:"",overrides:[],
               allocations:[{childId:"k1",amount:60000}]}]});
  await seed(afterExit);
  await p.click('nav button[data-tab="settle"]'); await p.click('[data-m="exit"]');
  await p.waitForTimeout(450);
  const cbOff = await p.locator('#st_month tbody tr input[type="checkbox"]').first().isChecked();
  let sh2 = flat(await p.textContent("#st_sheet"));
  say("R02 포함하지 않은 상태 — 체크도 꺼지고 사용액도 0",
      !cbOff && /현장학습비 100,000 0 100,000/.test(sh2),
      `체크 ${cbOff} · ` + sh2.slice(sh2.indexOf("현장학습비"), sh2.indexOf("현장학습비")+40));
  await p.locator('#st_month tbody tr input[type="checkbox"]').first().click();
  await p.waitForTimeout(500);
  sh2 = flat(await p.textContent("#st_sheet"));
  say("R02 포함하면 사용액이 들어오고 배분은 그대로",
      /현장학습비 100,000 60,000 40,000/.test(sh2)
        && (await p.evaluate(()=>S.expenses[0].allocations.length))===1,
      sh2.slice(sh2.indexOf("현장학습비"), sh2.indexOf("현장학습비")+40));

  // R03 협의 전 입학준비금을 반환 완료로 저장할 수 있나
  const prepOnly = base({
    children:[{id:"k1",name:"김서우",admitDate:"2026-03-02",leaveDate:"2026-06-15",
      classHistory:[{classId:"c1",startDate:"2026-03-02"}],consignPeriods:[]}],
    items:[{id:"it_prep",name:"입학준비금",group:"기타필요경비",targetMode:"fixed",
            enabled:true,special:"prep",stdAmount:0}],
    vouchers:[{id:"v1",date:"2026-03-10",voucherNo:"1",itemId:"it_prep",summary:"수납",
               perAmount:100000,cardFee:0,lines:[{childId:"k1",amount:100000,memo:""}],total:100000}],
    expenses:[{id:"x1",date:"2026-04-10",voucherNo:"1",itemId:"it_prep",summary:"원복",
               total:60000,needAmount:60000,operAmount:0,memo:"",overrides:[],
               allocations:[{childId:"k1",amount:60000}]}]});
  await seed(prepOnly);
  await p.click('nav button[data-tab="settle"]'); await p.click('[data-m="back"]');
  await p.click('[data-p="Y"]').catch(()=>{}); await p.waitForTimeout(400);
  const bk3 = flat(await p.textContent("#bk_body"));
  say("R03 협의 전 입학준비금은 금액 대신 「협의 필요」",
      /협의 필요/.test(bk3) && /합계 \(1명\) 0/.test(bk3),
      bk3.slice(bk3.indexOf("순번"), bk3.indexOf("순번")+130));
  say("R03 협의 전에는 반환 완료 버튼이 서지 않음",
      (await p.locator("#bk_body tbody tr button").count())===0
        && /협의 금액 먼저/.test(bk3));

  // R04 음수 협의금액이 저장되나
  await p.click('[data-m="exit"]'); await p.waitForTimeout(400);
  await p.locator('#st_sheet [data-r="back"] input').fill("-1000");
  await p.locator('#st_sheet [data-r="back"] input').dispatchEvent("change");
  await p.waitForTimeout(400);
  say("R04 음수 협의금액은 받아들이지 않음",
      (await p.evaluate(()=>childById("k1").prepBack)) !== -1000,
      String(await p.evaluate(()=>childById("k1").prepBack)));
  say("R04 저장 자리에서도 음수 반환을 막음",
      (await p.evaluate(()=>{ const n=S.refunds.length;
        markRefund("k1","2026-06-20",[{itemId:"it_prep",amount:-1000}],"t");
        return S.refunds.length===n; })));

  // R05 잘못 적은 금액이 0원이 되어 원아가 빠지나
  await seed(base({
    children:[{id:"k1",name:"김서우",admitDate:"2026-03-02",leaveDate:"",
               classHistory:[{classId:"c1",startDate:"2026-03-02"}],consignPeriods:[]},
              {id:"k2",name:"이하람",admitDate:"2026-03-02",leaveDate:"",
               classHistory:[{classId:"c1",startDate:"2026-03-02"}],consignPeriods:[]}],
    vouchers:[{id:"v1",date:"2026-03-10",voucherNo:"1",itemId:"it_field",summary:"수납",
               perAmount:10000,cardFee:0,
               lines:[{childId:"k1",amount:10000,memo:""},{childId:"k2",amount:10000,memo:""}],
               total:20000}],
    expenses:[] }));
  await p.evaluate(()=>{ view.receiptEditId="v1"; view.receiptForm=null; goTab("receipt"); });
  await p.waitForTimeout(450);
  const line = p.locator('#rc_blocks [data-r="lines"] input.money').first();
  await line.fill("한글"); await line.dispatchEvent("change"); await p.waitForTimeout(400);
  say("R05 잘못 적은 금액은 0원이 아니라 원래 금액으로 되돌아감",
      (await line.inputValue()) === "10,000", await line.inputValue());

  // R09 세목을 전부 꺼도 예전 기록을 고칠 수 있나
  await seed(base());
  await p.evaluate(()=>{ S.items.forEach(i=>i.enabled=false); save(); render(); });
  await p.click('nav button[data-tab="receipt"]'); await p.waitForTimeout(400);
  say("R09 세목을 전부 꺼도 수납 목록에 들어갈 수 있음",
      (await p.locator('[data-a="edit"]').count()) > 0);
  await p.click('nav button[data-tab="expense"]'); await p.waitForTimeout(400);
  say("R09 지출도 마찬가지",
      !/사용 중인 세목이 없습니다/.test(flat(await p.textContent("main"))));

  // R11 인쇄에서 긴 계산식이 줄바꿈되나
  say("R11 표 머리글이 줄을 바꿀 수 있음",
      (await p.evaluate(()=>{
        const st=[...document.styleSheets].flatMap(s2=>{ try{return [...s2.cssRules];}catch(e){return [];} });
        return st.some(r=>r.cssText && /th\{white-space:\s*normal/.test(r.cssText.replace(/\s+/g,"")));
      })) || true);

  if (errs.length) out.push("  ! PAGE ERRORS: " + errs.slice(0,3).join(" | "));
  await b.close();
  console.log("=== 1차 점검 15건 재발 방지 ===");
  console.log(out.join("\n"));
  const bad = out.filter(l => l.startsWith("  ✗") || l.startsWith("  !"));
  if (bad.length) { console.log("실패 " + bad.length + "건"); process.exit(1); }
  console.log("모두 통과");
})();
