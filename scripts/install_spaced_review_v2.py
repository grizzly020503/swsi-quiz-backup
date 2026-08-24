#!/usr/bin/env python3
from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')

if '/* ===== 間隔複習 2.0 START ===== */' in s:
    print('spaced review v2 already installed')
    raise SystemExit(0)

old = "const LS_KEY='swsi_v2_history';\nconst app=document.getElementById('app');"
new = "const LS_KEY='swsi_v2_history';\nconst REVIEW_KEY='swsi_review_v2';\nconst REVIEW_DAY=24*60*60*1000;\nconst REVIEW_INTERVAL_DAYS=[1,3,7,14,30];\nconst app=document.getElementById('app');"
if old not in s:
    raise SystemExit('anchor 1 not found')
s = s.replace(old, new, 1)

old = """function record(item,picked,correct){ const h=loadHist();
  h.push({id:item.id,subject:item.subject,major:item.major,mistake:item.mistake||'',correct,ts:Date.now()}); saveHist(h); }

/* ---------- stats ---------- */"""
new = """function record(item,picked,correct){ const h=loadHist();
  h.push({id:item.id,subject:item.subject,major:item.major,mistake:item.mistake||'',correct,ts:Date.now()}); saveHist(h);
  updateReviewSchedule(item,correct); }

/* ===== 間隔複習 2.0 START ===== */
function loadReviewState(){
  try{
    const x=JSON.parse(localStorage.getItem(REVIEW_KEY)||'null');
    if(x&&x.version===2&&x.items&&typeof x.items==='object') return x;
  }catch(e){}
  return {version:2,migratedFromHistory:false,items:{}};
}
function saveReviewState(st){ try{localStorage.setItem(REVIEW_KEY,JSON.stringify(st));}catch(e){} }
function bootstrapReviewState(){
  const st=loadReviewState();
  if(st.migratedFromHistory) return st;
  const h=loadHist(), latest={}, wrongCount={};
  h.forEach(x=>{ if(!x||!x.id)return; latest[x.id]=x; if(x.correct===false) wrongCount[x.id]=(wrongCount[x.id]||0)+1; });
  const now=Date.now();
  Object.keys(latest).forEach(id=>{
    if(latest[id].correct===false && !st.items[id]){
      st.items[id]={id,step:0,streak:0,wrongCount:wrongCount[id]||1,correctCount:0,dueAt:now,lastAt:latest[id].ts||now,lastResult:'wrong',mastered:false};
    }
  });
  st.migratedFromHistory=true;
  saveReviewState(st);
  return st;
}
function updateReviewSchedule(item,correct){
  if(!item||!item.id) return;
  const st=bootstrapReviewState(), now=Date.now();
  let r=st.items[item.id];
  if(!correct){
    if(!r) r={id:item.id,step:0,streak:0,wrongCount:0,correctCount:0,dueAt:now,lastAt:now,lastResult:'wrong',mastered:false};
    r.step=0; r.streak=0; r.mastered=false; r.masteredAt=null;
    r.wrongCount=(r.wrongCount||0)+1; r.lastResult='wrong'; r.lastAt=now;
    r.dueAt=now+REVIEW_DAY;
    st.items[item.id]=r;
  }else if(r && !r.mastered){
    r.streak=(r.streak||0)+1; r.correctCount=(r.correctCount||0)+1; r.lastResult='correct'; r.lastAt=now;
    const i=Math.min(r.step||0,REVIEW_INTERVAL_DAYS.length-1);
    r.dueAt=now+REVIEW_INTERVAL_DAYS[i]*REVIEW_DAY;
    r.step=Math.min(i+1,REVIEW_INTERVAL_DAYS.length-1);
    if(r.streak>=3){ r.mastered=true; r.masteredAt=now; }
    st.items[item.id]=r;
  }
  saveReviewState(st);
}
function reviewSummary(){
  const st=bootstrapReviewState(), now=Date.now(), exists=new Set(ALL.map(q=>q.id));
  const activeIds=[], dueIds=[]; let masteredCount=0, nextDueAt=0;
  Object.values(st.items).forEach(r=>{
    if(!r||!r.id||!exists.has(r.id)) return;
    if(r.mastered){ masteredCount++; return; }
    activeIds.push(r.id);
    const due=Number(r.dueAt||0);
    if(!due||due<=now) dueIds.push(r.id);
    else if(!nextDueAt||due<nextDueAt) nextDueAt=due;
  });
  return {activeIds,dueIds,activeCount:activeIds.length,dueCount:dueIds.length,masteredCount,nextDueAt};
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
  if(!rv.dueIds.length){ alert(rv.activeCount?`目前沒有到期題，下一批 ${reviewDueLabel(rv.nextDueAt)}。`:'目前沒有待複習錯題。'); return; }
  const set=new Set(rv.dueIds); startQuiz(q=>set.has(q.id),0);
}
/* ===== 間隔複習 2.0 END ===== */

/* ---------- stats ---------- */"""
if old not in s:
    raise SystemExit('anchor 2 not found')
s = s.replace(old, new, 1)

old = """function wrongQuestionIds(){ const h=loadHist(), latest={}; h.forEach(x=>{latest[x.id]=x.correct;});
  return Object.keys(latest).filter(id=>latest[id]===false); }"""
new = """function wrongQuestionIds(){ return reviewSummary().activeIds; }"""
if old not in s:
    raise SystemExit('anchor 3 not found')
s = s.replace(old, new, 1)

old = """function renderHome(){
  const offlineNote=window._usingOfflineBackup?`<div style=\"margin-bottom:14px;padding:10px 13px;border:1px solid var(--line);border-radius:10px;background:#fff;font-size:12px;color:var(--ink-soft)\">📦 目前使用這台裝置的離線題庫備援；恢復網路後重新開啟網站即可同步最新題庫。</div>`:'';
  const opts=['全部科目',...SUBJECTS].map(s=>`<option ${s===subjFilter?'selected':''}>${s}</option>`).join('');
  app.innerHTML=`"""
new = """function renderHome(){
  const offlineNote=window._usingOfflineBackup?`<div style=\"margin-bottom:14px;padding:10px 13px;border:1px solid var(--line);border-radius:10px;background:#fff;font-size:12px;color:var(--ink-soft)\">📦 目前使用這台裝置的離線題庫備援；恢復網路後重新開啟網站即可同步最新題庫。</div>`:'';
  const opts=['全部科目',...SUBJECTS].map(s=>`<option ${s===subjFilter?'selected':''}>${s}</option>`).join('');
  const rv=reviewSummary();
  const reviewCard=rv.activeCount?`<div class=\"time-card\" onclick=\"${rv.dueCount?'startDueReview()':\"go('review')\"}\" style=\"margin-bottom:20px;border-color:${rv.dueCount?'var(--wrong)':'var(--pine)'};background:${rv.dueCount?'var(--wrong-bg)':'var(--correct-bg)'}\"><span class=\"t\">🧠 ${rv.dueCount?`今天待複習 ${rv.dueCount} 題`:'間隔複習已排程'}</span><span class=\"n\">${rv.dueCount?'現在複習':`下一批 ${reviewDueLabel(rv.nextDueAt)}`}</span></div>`:'';
  app.innerHTML=`"""
if old not in s:
    raise SystemExit('anchor 4 not found')
s = s.replace(old, new, 1)

old = """    </div>
    <div class=\"ask\">你今天有多少時間？</div>"""
new = """    </div>
    ${reviewCard}
    <div class=\"ask\">你今天有多少時間？</div>"""
# ensure this hits renderHome hero close, first occurrence after modified renderHome
pos=s.find('function renderHome(){')
idx=s.find(old,pos)
if idx<0:
    raise SystemExit('anchor 5 not found')
s=s[:idx]+s[idx:].replace(old,new,1)

start = s.find('function renderReview(){')
end = s.find('\nfunction practiceSet(i)', start)
if start < 0 or end < 0:
    raise SystemExit('renderReview block not found')
new_review = r'''function renderReview(){
  const rv=reviewSummary(), ids=rv.activeIds;
  if(!ids.length){ app.innerHTML=`<div class="empty"><div class="ico">✓</div><h3>${rv.masteredCount?'目前沒有未熟練錯題':'還沒有錯題'}</h3><p>${rv.masteredCount?`已經有 ${rv.masteredCount} 題完成三次連續答對。<br>之後再答錯會自動回到複習排程。`:'開始刷題後，答錯的題會自動排入<br>1、3、7、14、30 天間隔複習。'}</p><button class="btn" style="max-width:200px;margin:22px auto 0" onclick="go('home')">開始刷題</button></div>`; return; }
  const wrongQs=ids.map(id=>ALL.find(q=>q.id===id)).filter(Boolean);
  const byReason={}; wrongQs.forEach(q=>{const r=q.mistake||'未分類'; (byReason[r]=byReason[r]||[]).push(q);});
  window._rs=[{label:'全部未熟練錯題',ids:ids}];
  const re=Object.entries(byReason).sort((a,b)=>b[1].length-a[1].length);
  re.forEach(([reason,qs])=>{window._rs.push({label:reason,ids:qs.map(x=>x.id)});});
  let html=`<div class="section-h">錯題・間隔複習</div><div class="section-s">答錯後自動排程；連續答對 3 次才畢業，不再只靠「答對一次就消失」。</div>`;
  html+=`<div class="statrow" style="margin-bottom:18px"><div class="stat"><div class="v" style="color:var(--wrong)">${rv.dueCount}</div><div class="k">今天到期</div></div><div class="stat"><div class="v">${rv.activeCount}</div><div class="k">未熟練</div></div><div class="stat"><div class="v" style="color:var(--correct)">${rv.masteredCount}</div><div class="k">已畢業</div></div></div>`;
  if(rv.dueCount) html+=`<button class="btn" onclick="startDueReview()" style="margin-bottom:10px">開始今天的複習（${rv.dueCount} 題）</button>`;
  else html+=`<div style="margin-bottom:14px;padding:11px 13px;border:1px solid var(--line);border-radius:10px;background:#fff;font-size:13px;color:var(--ink-soft)">✓ 今天已沒有到期題，下一批 ${reviewDueLabel(rv.nextDueAt)}。</div>`;
  html+=`<button class="btn ghost" onclick="practiceSet(0)" style="margin-bottom:18px">重練全部未熟練錯題（${wrongQs.length} 題）</button>`;
  re.forEach(([reason,qs],i)=>{ html+=`<div class="gcard wrongcat" onclick="practiceSet(${i+1})"><div><div class="name">${reason}</div><div class="cnt">${qs.length} 題</div></div><span class="arrow">›</span></div>`; });
  app.innerHTML=html;
}'''
s = s[:start] + new_review + s[end:]

old = """onclick=\"if(confirm('清除所有刷題紀錄？無法復原。')){localStorage.removeItem(LS_KEY);render();}\">清除我的紀錄</button>"""
new = """onclick=\"if(confirm('清除所有刷題與間隔複習紀錄？無法復原。')){localStorage.removeItem(LS_KEY);localStorage.removeItem(REVIEW_KEY);render();}\">清除我的紀錄</button>"""
if old not in s:
    raise SystemExit('anchor 6 not found')
s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('installed spaced review v2')
