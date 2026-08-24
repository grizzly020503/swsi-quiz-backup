#!/usr/bin/env python3
from pathlib import Path

p=Path('index.html')
s=p.read_text(encoding='utf-8')
start=s.find('/* ===== 間隔複習 2.0 START ===== */')
end=s.find('/* ===== 間隔複習 2.0 END ===== */',start)
if start<0 or end<0:
    raise SystemExit('review block not found')
end += len('/* ===== 間隔複習 2.0 END ===== */')
block=r'''/* ===== 間隔複習 2.0 START ===== */
function loadReviewState(){
  try{
    const x=JSON.parse(localStorage.getItem(REVIEW_KEY)||'null');
    if(x&&x.version===2&&x.items&&typeof x.items==='object') return x;
  }catch(e){}
  return {version:2,migratedFromHistory:false,items:{}};
}
function saveReviewState(st){ try{localStorage.setItem(REVIEW_KEY,JSON.stringify(st));}catch(e){} }
function bootstrapReviewState(){
  const st=loadReviewState(); let changed=false;
  if(!st.migratedFromHistory){
    const h=loadHist(), latest={}, wrongCount={};
    h.forEach(x=>{ if(!x||!x.id)return; latest[x.id]=x; if(x.correct===false) wrongCount[x.id]=(wrongCount[x.id]||0)+1; });
    const now=Date.now();
    Object.keys(latest).forEach(id=>{
      if(latest[id].correct===false && !st.items[id]){
        st.items[id]={id,streak:0,wrongCount:wrongCount[id]||1,correctCount:0,dueAt:now,lastAt:latest[id].ts||now,lastResult:'wrong',mastered:false,maintenanceStep:0,maintenanceDone:false};
      }
    });
    st.migratedFromHistory=true; changed=true;
  }
  Object.values(st.items).forEach(r=>{
    if(!r||!r.id)return;
    if(r.mastered && r.maintenanceStep==null){
      r.maintenanceStep=0; r.maintenanceDone=false;
      r.dueAt=(r.masteredAt||Date.now())+14*REVIEW_DAY; changed=true;
    }
  });
  if(changed) saveReviewState(st);
  return st;
}
function updateReviewSchedule(item,correct){
  if(!item||!item.id) return;
  const st=bootstrapReviewState(), now=Date.now();
  let r=st.items[item.id];
  if(!correct){
    if(!r) r={id:item.id,streak:0,wrongCount:0,correctCount:0,dueAt:now,lastAt:now,lastResult:'wrong',mastered:false,maintenanceStep:0,maintenanceDone:false};
    r.streak=0; r.mastered=false; r.masteredAt=null; r.maintenanceStep=0; r.maintenanceDone=false;
    r.wrongCount=(r.wrongCount||0)+1; r.lastResult='wrong'; r.lastAt=now; r.dueAt=now+REVIEW_INTERVAL_DAYS[0]*REVIEW_DAY;
    st.items[item.id]=r;
  }else if(r){
    r.correctCount=(r.correctCount||0)+1; r.lastResult='correct'; r.lastAt=now;
    if(!r.mastered){
      r.streak=(r.streak||0)+1;
      if(r.streak>=3){
        r.mastered=true; r.masteredAt=now; r.maintenanceStep=0; r.maintenanceDone=false;
        r.dueAt=now+REVIEW_INTERVAL_DAYS[3]*REVIEW_DAY;
      }else{
        const days=r.streak===1?REVIEW_INTERVAL_DAYS[1]:REVIEW_INTERVAL_DAYS[2];
        r.dueAt=now+days*REVIEW_DAY;
      }
    }else if(!r.maintenanceDone){
      if((r.maintenanceStep||0)===0){
        r.maintenanceStep=1; r.dueAt=now+REVIEW_INTERVAL_DAYS[4]*REVIEW_DAY;
      }else{
        r.maintenanceStep=2; r.maintenanceDone=true; r.dueAt=0;
      }
    }
    st.items[item.id]=r;
  }
  saveReviewState(st);
}
function reviewSummary(){
  const st=bootstrapReviewState(), now=Date.now(), exists=new Set(ALL.map(q=>q.id));
  const activeIds=[], dueIds=[], maintenanceDueIds=[]; let masteredCount=0, nextDueAt=0;
  Object.values(st.items).forEach(r=>{
    if(!r||!r.id||!exists.has(r.id)) return;
    const due=Number(r.dueAt||0);
    if(r.mastered){
      masteredCount++;
      if(!r.maintenanceDone){
        if(!due||due<=now){ dueIds.push(r.id); maintenanceDueIds.push(r.id); }
        else if(!nextDueAt||due<nextDueAt) nextDueAt=due;
      }
      return;
    }
    activeIds.push(r.id);
    if(!due||due<=now) dueIds.push(r.id);
    else if(!nextDueAt||due<nextDueAt) nextDueAt=due;
  });
  return {activeIds,dueIds,maintenanceDueIds,activeCount:activeIds.length,dueCount:dueIds.length,maintenanceDueCount:maintenanceDueIds.length,masteredCount,nextDueAt};
}
function reviewDueLabel(ts){
  if(!ts) return '等待下一次複習';
  const d=Math.max(0,Math.ceil((ts-Date.now())/REVIEW_DAY));
  if(d<=0) return '今天';
  if(d===1) return '明天';
  return `${d} 天後`;
}
function startDueReview(){
  const rv=reviewSummary();
  if(!rv.dueIds.length){ alert((rv.activeCount||rv.masteredCount)?`目前沒有到期題，下一批 ${reviewDueLabel(rv.nextDueAt)}。`:'目前沒有待複習錯題。'); return; }
  const set=new Set(rv.dueIds); startQuiz(q=>set.has(q.id),0);
}
/* ===== 間隔複習 2.0 END ===== */'''
s=s[:start]+block+s[end:]

old="const reviewCard=rv.activeCount?`<div class=\"time-card\" onclick=\"${rv.dueCount?'startDueReview()':\"go('review')\"}\" style=\"margin-bottom:20px;border-color:${rv.dueCount?'var(--wrong)':'var(--pine)'};background:${rv.dueCount?'var(--wrong-bg)':'var(--correct-bg)'}\"><span class=\"t\">🧠 ${rv.dueCount?`今天待複習 ${rv.dueCount} 題`:'間隔複習已排程'}</span><span class=\"n\">${rv.dueCount?'現在複習':`下一批 ${reviewDueLabel(rv.nextDueAt)}`}</span></div>`:'';"
new="const reviewCard=(rv.activeCount||rv.dueCount||rv.nextDueAt)?`<div class=\"time-card\" onclick=\"${rv.dueCount?'startDueReview()':\"go('review')\"}\" style=\"margin-bottom:20px;border-color:${rv.dueCount?'var(--wrong)':'var(--pine)'};background:${rv.dueCount?'var(--wrong-bg)':'var(--correct-bg)'}\"><span class=\"t\">🧠 ${rv.dueCount?`今天待複習 ${rv.dueCount} 題`:(rv.activeCount?'間隔複習已排程':'長期複習已排程')}</span><span class=\"n\">${rv.dueCount?'現在複習':`下一批 ${reviewDueLabel(rv.nextDueAt)}`}</span></div>`:'';"
if old not in s: raise SystemExit('home review card anchor not found')
s=s.replace(old,new,1)

rs=s.find('function renderReview(){')
re=s.find('\nfunction practiceSet(i)',rs)
if rs<0 or re<0: raise SystemExit('renderReview not found')
new_render=r'''function renderReview(){
  const rv=reviewSummary(), ids=rv.activeIds;
  if(!ids.length && !rv.dueCount && !rv.nextDueAt){ app.innerHTML=`<div class="empty"><div class="ico">✓</div><h3>${rv.masteredCount?'目前沒有待複習題':'還沒有錯題'}</h3><p>${rv.masteredCount?`已經有 ${rv.masteredCount} 題完成錯題學習與長期確認。<br>之後再答錯仍會自動回到複習排程。`:'開始刷題後，答錯題會依<br>1、3、7、14、30 天安排複習。'}</p><button class="btn" style="max-width:200px;margin:22px auto 0" onclick="go('home')">開始刷題</button></div>`; return; }
  const wrongQs=ids.map(id=>ALL.find(q=>q.id===id)).filter(Boolean);
  const byReason={}; wrongQs.forEach(q=>{const r=q.mistake||'未分類'; (byReason[r]=byReason[r]||[]).push(q);});
  window._rs=[{label:'全部未熟練錯題',ids:ids}];
  const reasons=Object.entries(byReason).sort((a,b)=>b[1].length-a[1].length);
  reasons.forEach(([reason,qs])=>{window._rs.push({label:reason,ids:qs.map(x=>x.id)});});
  let html=`<div class="section-h">錯題・間隔複習</div><div class="section-s">答錯後 1 天再看；答對後拉到 3、7 天。連續答對 3 次畢業，再於 14、30 天做長期確認。</div>`;
  html+=`<div class="statrow" style="margin-bottom:18px"><div class="stat"><div class="v" style="color:var(--wrong)">${rv.dueCount}</div><div class="k">今天到期</div></div><div class="stat"><div class="v">${rv.activeCount}</div><div class="k">未熟練</div></div><div class="stat"><div class="v" style="color:var(--correct)">${rv.masteredCount}</div><div class="k">已畢業</div></div></div>`;
  if(rv.dueCount) html+=`<button class="btn" onclick="startDueReview()" style="margin-bottom:10px">開始今天的複習（${rv.dueCount} 題${rv.maintenanceDueCount?`，含 ${rv.maintenanceDueCount} 題長期確認`:''}）</button>`;
  else if(rv.nextDueAt) html+=`<div style="margin-bottom:14px;padding:11px 13px;border:1px solid var(--line);border-radius:10px;background:#fff;font-size:13px;color:var(--ink-soft)">✓ 今天已沒有到期題，下一批 ${reviewDueLabel(rv.nextDueAt)}。</div>`;
  if(wrongQs.length) html+=`<button class="btn ghost" onclick="practiceSet(0)" style="margin-bottom:18px">重練全部未熟練錯題（${wrongQs.length} 題）</button>`;
  reasons.forEach(([reason,qs],i)=>{ html+=`<div class="gcard wrongcat" onclick="practiceSet(${i+1})"><div><div class="name">${reason}</div><div class="cnt">${qs.length} 題</div></div><span class="arrow">›</span></div>`; });
  app.innerHTML=html;
}'''
s=s[:rs]+new_render+s[re:]

p.write_text(s,encoding='utf-8')
print('upgraded spaced review maintenance')
