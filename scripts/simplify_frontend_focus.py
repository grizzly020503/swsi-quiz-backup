#!/usr/bin/env python3
from pathlib import Path
import re

p=Path('index.html')
s=p.read_text(encoding='utf-8')
MARK='/* ===== FOCUSED HOME V1 START ===== */'
if MARK in s:
    print('Focused home already installed.')
    raise SystemExit(0)

# 1) 智慧推薦：舊題保留，但明顯降權。
s2,n=re.subn(
    r"function yearWeight\(q\)\{[^\n]*\}",
    "function yearWeight(q){ const y=parseInt(q.year)||0, mx=maxExamYear(); if(!y) return 1; const d=mx-y; return d<=2?4:(d<=7?2:(d<=10?0.8:0.35)); }",
    s,
    count=1
)
if n!=1:
    raise SystemExit('yearWeight replacement failed')
s=s2

# 2) 用專注版首頁取代原首頁；保留後面的搜尋等既有功能。
pat=r"function renderHome\(\)\{[\s\S]*?\n\}\n\n/\* ---------- 全域搜尋 ---------- \*/"
m=re.search(pat,s)
if not m:
    raise SystemExit('renderHome block not found')

new_block=r'''/* ===== FOCUSED HOME V1 START ===== */
let homeQuizOpen=false;
let homeQuizScope='smart';
let homeQuizYear='';
let homeQuizRound='all';
let homeQuizCount=20;

function examYears(){
  return [...new Set(ALL.map(q=>parseInt(q.year,10)).filter(Number.isFinite))].sort((a,b)=>b-a);
}
function setHomeQuizScope(v){
  homeQuizScope=v;
  if(v==='specific'&&!homeQuizYear){ const ys=examYears(); homeQuizYear=ys.length?String(ys[0]):''; }
  render();
}
function setHomeQuizYear(v){ homeQuizYear=String(v||''); render(); }
function setHomeQuizRound(v){ homeQuizRound=String(v||'all'); render(); }
function setHomeQuizCount(v){ homeQuizCount=parseInt(v,10)||0; }
function toggleHomeQuiz(){ homeQuizOpen=!homeQuizOpen; render(); }
function focusedQuizFilter(q){
  if(subjFilter!=='全部科目' && q.subject!==subjFilter) return false;
  const y=parseInt(q.year,10)||0, mx=maxExamYear();
  if(homeQuizScope==='recent3') return y>=mx-2;
  if(homeQuizScope==='recent5') return y>=mx-4;
  if(homeQuizScope==='specific'){
    if(String(q.year)!==String(homeQuizYear)) return false;
    if(homeQuizRound!=='all' && canonicalRound(q.round)!==homeQuizRound) return false;
  }
  return true;
}
function startFocusedQuiz(){
  const pool=ALL.filter(focusedQuizFilter);
  if(!pool.length){ alert('這個條件目前沒有題目，請換一個年份、考次或科目。'); return; }
  startQuiz(focusedQuizFilter,homeQuizCount);
}
function renderHome(){
  const offlineNote=window._usingOfflineBackup?`<div style="margin-bottom:14px;padding:10px 13px;border:1px solid var(--line);border-radius:10px;background:#fff;font-size:12px;color:var(--ink-soft)">📦 目前使用這台裝置的離線題庫備援；恢復網路後重新開啟網站即可同步最新題庫。</div>`:'';
  const rv=reviewSummary();
  const years=examYears();
  if(!homeQuizYear&&years.length) homeQuizYear=String(years[0]);
  const oldest=years.length?years[years.length-1]:'';
  const newest=years.length?years[0]:'';
  const subjOpts=['全部科目',...SUBJECTS].map(x=>`<option value="${esc(x)}" ${x===subjFilter?'selected':''}>${esc(x)}</option>`).join('');
  const yearOpts=years.map(y=>`<option value="${y}" ${String(y)===String(homeQuizYear)?'selected':''}>${y} 年</option>`).join('');
  const specific=homeQuizScope==='specific';
  const reviewSub=rv.dueCount?`今天 ${rv.dueCount} 題到期`:(rv.nextDueAt?`下一批 ${reviewDueLabel(rv.nextDueAt)}`:'目前沒有待複習題');
  const scopeHint=homeQuizScope==='smart'?'近年與高頻考點優先；舊題保留但降低出現率。':homeQuizScope==='specific'?'只刷你指定的年度／考次。':homeQuizScope==='all'?'包含所有歷史題目。':'只從較新的歷屆題目抽題。';

  app.innerHTML=`
    ${offlineNote}
    <div class="hero" style="margin-bottom:18px">
      <h1>社工師國考<br>學習題庫</h1>
      <div class="tagline">刷題、複習錯題、練申論。其他工具需要時再打開。</div>
      <div class="chips">
        <span class="chip"><b>5</b> 科</span>
        <span class="chip"><b>${oldest}${oldest&&newest?'–':''}${newest}</b> 歷屆</span>
        <span class="chip"><b>${ALL.length}</b> 題</span>
      </div>
    </div>

    <div class="gcard" onclick="toggleHomeQuiz()" style="border-color:var(--pine);${homeQuizOpen?'background:var(--correct-bg)':''}">
      <div><div class="name">📝 開始刷題</div><div class="cnt">智慧推薦，或自己指定年份／考次</div></div><span class="arrow">${homeQuizOpen?'▾':'›'}</span>
    </div>

    ${homeQuizOpen?`<div style="border:1px solid var(--line);border-radius:14px;padding:14px;margin:-3px 0 12px;background:#fff">
      <div style="font-size:12px;color:var(--ink-soft);margin-bottom:6px">刷題範圍</div>
      <select class="subj" onchange="setHomeQuizScope(this.value)" style="margin-bottom:10px">
        <option value="smart" ${homeQuizScope==='smart'?'selected':''}>智慧推薦</option>
        <option value="recent3" ${homeQuizScope==='recent3'?'selected':''}>近 3 年</option>
        <option value="recent5" ${homeQuizScope==='recent5'?'selected':''}>近 5 年</option>
        <option value="specific" ${homeQuizScope==='specific'?'selected':''}>指定歷屆</option>
        <option value="all" ${homeQuizScope==='all'?'selected':''}>全部題庫（含歷史題）</option>
      </select>
      ${specific?`<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
        <select class="subj" onchange="setHomeQuizYear(this.value)" style="margin:0">${yearOpts}</select>
        <select class="subj" onchange="setHomeQuizRound(this.value)" style="margin:0">
          <option value="all" ${homeQuizRound==='all'?'selected':''}>全部考次</option>
          <option value="1" ${homeQuizRound==='1'?'selected':''}>第一次</option>
          <option value="2" ${homeQuizRound==='2'?'selected':''}>第二次</option>
        </select>
      </div>`:''}
      <select class="subj" onchange="subjFilter=this.value" style="margin-bottom:10px">${subjOpts}</select>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
        <select class="subj" onchange="setHomeQuizCount(this.value)" style="margin:0">
          <option value="10" ${homeQuizCount===10?'selected':''}>10 題</option>
          <option value="20" ${homeQuizCount===20?'selected':''}>20 題</option>
          <option value="50" ${homeQuizCount===50?'selected':''}>50 題</option>
          <option value="0" ${homeQuizCount===0?'selected':''}>全部符合題目</option>
        </select>
        <button class="btn" onclick="startFocusedQuiz()" style="margin:0">開始</button>
      </div>
      <div style="font-size:12px;color:var(--ink-soft);line-height:1.6">${scopeHint}</div>
    </div>`:''}

    <div class="gcard" onclick="${rv.dueCount?'startDueReview()':"go('review')"}" style="${rv.dueCount?'border-color:var(--wrong);background:var(--wrong-bg)':''}">
      <div><div class="name">🧠 今日複習${rv.dueCount?` · ${rv.dueCount} 題`:''}</div><div class="cnt">${reviewSub}</div></div><span class="arrow">›</span>
    </div>

    <div class="gcard" onclick="go('essay')">
      <div><div class="name">✍️ 申論練習</div><div class="cnt">歷屆申論、作答草稿與 AI 練習回饋</div></div><span class="arrow">›</span>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:18px">
      <button class="btn ghost" onclick="MK.open()" style="margin:0">計時模擬考</button>
      <button class="btn ghost" onclick="go('topics')" style="margin:0">學習工具</button>
    </div>
    <div style="font-size:11px;color:var(--ink-soft);line-height:1.6;margin-top:13px;text-align:center">歷史題不刪除；智慧推薦會優先較新的題目，需要時仍可指定任何年份。</div>
  `;
}
/* ===== FOCUSED HOME V1 END ===== */

/* ---------- 全域搜尋 ---------- */'''

s=s[:m.start()]+new_block+s[m.end():]
p.write_text(s,encoding='utf-8')
print('Installed focused home + year filters + historical downweighting.')
