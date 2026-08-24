#!/usr/bin/env python3
from pathlib import Path
import re

PATH = Path('index.html')
START = '<!-- SWSI UIUX V1 START -->'
END = '<!-- SWSI UIUX V1 END -->'

block = r'''<!-- SWSI UIUX V1 START -->
<style id="swsi-uiux-v1-style">
/* UI/UX V1：只整理介面，不改題庫、答題、複習與 AI 邏輯 */
:root{--ux-radius:16px;--ux-touch:46px;}
body{font-family:'Noto Sans TC',sans-serif;}
.logo,.qtext,.section-h,.ux-home-intro h1,.ux-card-title{font-family:'Noto Serif TC',serif;}
.wrap{padding-bottom:calc(76px + env(safe-area-inset-bottom));}
header{padding:calc(12px + env(safe-area-inset-top)) 18px 10px;align-items:center;}
.logo{font-size:18px;line-height:1.3;}
.logo small{font-size:8px;margin-top:1px;letter-spacing:2.4px;}
.logo::after{margin-top:6px;width:86px;height:2px;}
.hdr-right{gap:7px;}
.fontctl{padding:2px;}
.fontctl button{width:36px;height:36px;min-width:36px;font-family:'Noto Sans TC',sans-serif;}
.gear{min-width:40px;min-height:40px;display:grid;place-items:center;padding:0;}
main{padding:18px 18px 26px;}
.tabbar{padding-bottom:env(safe-area-inset-bottom);}
.tabbar button{min-height:58px;padding:9px 4px 10px;font-family:'Noto Sans TC',sans-serif;font-size:12px;}
.tabbar .ico{font-size:19px;}
.gcard{border-radius:var(--ux-radius);padding:17px 18px;min-height:68px;box-shadow:0 2px 10px rgba(43,42,38,.025);}
.gcard .name{font-size:15px;}
.gcard .cnt{line-height:1.55;margin-top:2px;}
.btn,.fbtn,.dbtn{font-family:'Noto Sans TC',sans-serif;min-height:var(--ux-touch);letter-spacing:.4px;}
select.subj{font-family:'Noto Sans TC',sans-serif;min-height:var(--ux-touch);font-size:14px;}
.quit{font-family:'Noto Sans TC',sans-serif;min-height:40px;padding:7px 2px;margin-bottom:8px;display:inline-flex;align-items:center;}
.qcard{border-radius:18px;padding:22px 18px;box-shadow:0 5px 22px rgba(43,42,38,.045);}
.qtext{line-height:1.78;margin-bottom:20px;}
.opt{font-family:'Noto Sans TC',sans-serif;min-height:54px;padding:14px 15px;line-height:1.65;align-items:flex-start;}
.opt .lab{padding-top:1px;}
.exp,.exp p,.extra,.pending,.mistake{font-family:'Noto Sans TC',sans-serif;}
.exp-sec p{line-height:1.75;}
.section-s{font-family:'Noto Sans TC',sans-serif;line-height:1.65;}
.stat{padding:12px 6px;}
.stat .k{font-family:'Noto Sans TC',sans-serif;}

.ux-home-intro{background:linear-gradient(150deg,#4A766C,#3A5F57);border-radius:20px;padding:21px 20px;color:#fff;margin-bottom:16px;box-shadow:0 7px 24px rgba(43,62,57,.16);}
.ux-home-intro .eyebrow{font-size:11px;font-weight:700;letter-spacing:2px;opacity:.76;margin-bottom:4px;}
.ux-home-intro h1{font-size:24px;line-height:1.3;font-weight:900;letter-spacing:.4px;}
.ux-home-intro p{font-size:13px;line-height:1.65;opacity:.9;margin-top:6px;}
.ux-home-meta{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px;}
.ux-home-meta span{font-size:11px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.18);border-radius:999px;padding:4px 9px;}
.ux-main-card{background:var(--paper2);border:1px solid var(--line);border-radius:18px;padding:18px;margin-bottom:11px;}
.ux-main-card.primary{border-color:rgba(79,126,118,.55);background:linear-gradient(180deg,#F9FBFA,#F2F7F5);}
.ux-card-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;}
.ux-card-title{font-size:17px;font-weight:800;line-height:1.4;}
.ux-card-sub{font-size:12.5px;color:var(--ink-soft);line-height:1.6;margin-top:3px;}
.ux-badge{font-size:11px;font-weight:700;color:var(--wrong);background:var(--wrong-bg);border-radius:999px;padding:4px 9px;white-space:nowrap;}
.ux-actions{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:8px;margin-top:14px;}
.ux-btn-main,.ux-btn-soft{border:none;border-radius:12px;min-height:48px;font-family:'Noto Sans TC',sans-serif;font-size:14px;font-weight:700;cursor:pointer;}
.ux-btn-main{background:var(--pine-deep);color:#fff;}
.ux-btn-soft{background:#fff;color:var(--pine);border:1px solid var(--line);}
.ux-link-card{display:flex;align-items:center;justify-content:space-between;gap:12px;background:var(--paper2);border:1px solid var(--line);border-radius:16px;padding:16px 17px;margin-bottom:10px;cursor:pointer;min-height:70px;}
.ux-link-card.hot{border-color:rgba(158,97,85,.45);background:var(--wrong-bg);}
.ux-link-card .left{min-width:0;}
.ux-link-card .title{font-family:'Noto Serif TC',serif;font-weight:800;font-size:16px;}
.ux-link-card .sub{font-size:12.5px;color:var(--ink-soft);line-height:1.55;margin-top:2px;}
.ux-link-card .arrow{color:var(--ink-3);font-size:22px;flex:0 0 auto;}
.ux-tools{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:16px;}
.ux-tools button{min-height:46px;border-radius:12px;border:1px solid var(--line);background:transparent;color:var(--pine);font-family:'Noto Sans TC',sans-serif;font-weight:700;font-size:13px;}
.ux-custom{border:1px solid var(--line);border-radius:16px;padding:14px;margin:0 0 12px;background:#fff;}
.ux-custom-label{font-size:11px;color:var(--ink-soft);font-weight:700;margin:0 0 6px;}
.ux-note{font-size:11.5px;color:var(--ink-soft);line-height:1.6;margin-top:3px;}
.ux-page-head{margin-bottom:16px;}
.ux-page-head h2{font-family:'Noto Serif TC',serif;font-size:23px;line-height:1.35;font-weight:900;}
.ux-page-head p{font-size:13px;color:var(--ink-soft);line-height:1.65;margin-top:5px;}
.ux-review-rule{margin:12px 0 18px;border:1px solid var(--line);border-radius:12px;background:#fff;padding:0 13px;}
.ux-review-rule summary{cursor:pointer;min-height:44px;display:flex;align-items:center;font-size:12.5px;font-weight:700;color:var(--ink-soft);}
.ux-review-rule p{font-size:12px;color:var(--ink-soft);line-height:1.7;padding:0 0 12px;}
.ux-subhead{font-size:12px;color:var(--ink-soft);font-weight:700;letter-spacing:.5px;margin:18px 0 9px;}
@media (max-width:370px){
  header{padding-left:14px;padding-right:14px}.logo{font-size:16px}.fontctl button{width:33px;height:35px;min-width:33px}
  main{padding-left:14px;padding-right:14px}.ux-actions{grid-template-columns:1fr}.ux-home-intro{padding:19px 17px}
}
</style>
<script id="swsi-uiux-v1-script">
(function(){
  if(window.__SWSI_UIUX_V1__) return;
  window.__SWSI_UIUX_V1__=true;

  var vp=document.querySelector('meta[name="viewport"]');
  if(vp) vp.setAttribute('content','width=device-width, initial-scale=1.0, viewport-fit=cover');

  function relabelTabs(){
    var home=document.getElementById('t-home'), review=document.getElementById('t-review'), essay=document.getElementById('t-essay');
    var topics=document.getElementById('t-topics'), progress=document.getElementById('t-progress'), bar=document.getElementById('tabbar');
    if(home) home.innerHTML='<span class="ico">⌂</span>首頁';
    if(review) review.innerHTML='<span class="ico">↻</span>複習';
    if(essay) essay.innerHTML='<span class="ico">✒</span>申論';
    if(topics) topics.style.display='none';
    if(progress) progress.style.display='none';
    if(bar&&home&&review&&essay){ try{bar.appendChild(home);bar.appendChild(review);bar.appendChild(essay);}catch(_e){} }
  }
  relabelTabs();
  var oldFocused=typeof applyFocusedTabbar==='function'?applyFocusedTabbar:null;
  if(oldFocused){
    applyFocusedTabbar=function(){ oldFocused(); relabelTabs(); };
  }

  window.startQuickSmartV1=function(){
    homeQuizScope='smart'; homeQuizCount=20; homeQuizOpen=false; subjFilter='全部科目';
    startFocusedQuiz();
  };

  renderHome=function(){
    var offlineNote=window._usingOfflineBackup?'<div style="margin-bottom:12px;padding:10px 13px;border:1px solid var(--line);border-radius:12px;background:#fff;font-size:12px;color:var(--ink-soft)">📦 目前使用這台裝置的離線題庫備援；恢復網路後重新開啟網站即可同步最新題庫。</div>':'';
    var rv=reviewSummary();
    var years=examYears();
    if(!homeQuizYear&&years.length) homeQuizYear=String(years[0]);
    var newest=years.length?years[0]:'';
    var subjOpts=['全部科目'].concat(SUBJECTS).map(function(x){return '<option value="'+esc(x)+'" '+(x===subjFilter?'selected':'')+'>'+esc(x)+'</option>';}).join('');
    var yearOpts=years.map(function(y){return '<option value="'+y+'" '+(String(y)===String(homeQuizYear)?'selected':'')+'>'+y+' 年</option>';}).join('');
    var specific=homeQuizScope==='specific';
    var reviewSub=rv.dueCount?('今天 '+rv.dueCount+' 題到期'):(rv.nextDueAt?('下一批 '+reviewDueLabel(rv.nextDueAt)):'目前沒有待複習題');
    var scopeHint=homeQuizScope==='smart'?'最近 10 年為主，近 3 年與高頻考點優先。':homeQuizScope==='specific'?'只刷你指定的年度／考次。':homeQuizScope==='all'?'包含所有歷史題目。':'只從較新的歷屆題目抽題。';

    app.innerHTML=offlineNote+
      '<div class="ux-home-intro">'+
        '<div class="eyebrow">社工師國考</div><h1>今天要練什麼？</h1><p>選一件事開始就好，進階設定需要時再打開。</p>'+
        '<div class="ux-home-meta"><span>5 科</span><span>'+ALL.length+' 題</span>'+(newest?'<span>'+newest+' 最新</span>':'')+'</div>'+
      '</div>'+
      '<div class="ux-main-card primary">'+
        '<div class="ux-card-top"><div><div class="ux-card-title">📝 刷選擇題</div><div class="ux-card-sub">直接用智慧推薦練 20 題，或自己指定歷屆範圍。</div></div></div>'+
        '<div class="ux-actions"><button class="ux-btn-main" onclick="startQuickSmartV1()">智慧刷 20 題</button><button class="ux-btn-soft" onclick="toggleHomeQuiz()">'+(homeQuizOpen?'收起設定':'自訂範圍')+'</button></div>'+
      '</div>'+
      (homeQuizOpen?('<div class="ux-custom">'+
        '<div class="ux-custom-label">刷題範圍</div><select class="subj" onchange="setHomeQuizScope(this.value)" style="margin-bottom:9px">'+
          '<option value="smart" '+(homeQuizScope==='smart'?'selected':'')+'>智慧推薦</option><option value="recent3" '+(homeQuizScope==='recent3'?'selected':'')+'>近 3 年</option><option value="recent5" '+(homeQuizScope==='recent5'?'selected':'')+'>近 5 年</option><option value="specific" '+(homeQuizScope==='specific'?'selected':'')+'>指定歷屆</option><option value="all" '+(homeQuizScope==='all'?'selected':'')+'>全部題庫（含歷史題）</option></select>'+
        (specific?('<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><select class="subj" onchange="setHomeQuizYear(this.value)" style="margin-bottom:9px">'+yearOpts+'</select><select class="subj" onchange="setHomeQuizRound(this.value)" style="margin-bottom:9px"><option value="all" '+(homeQuizRound==='all'?'selected':'')+'>全部考次</option><option value="第一次" '+(homeQuizRound==='第一次'?'selected':'')+'>第一次</option><option value="第二次" '+(homeQuizRound==='第二次'?'selected':'')+'>第二次</option></select></div>'):'')+
        '<select class="subj" onchange="subjFilter=this.value" style="margin-bottom:9px">'+subjOpts+'</select>'+
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><select class="subj" onchange="setHomeQuizCount(this.value)" style="margin:0"><option value="10" '+(homeQuizCount===10?'selected':'')+'>10 題</option><option value="20" '+(homeQuizCount===20?'selected':'')+'>20 題</option><option value="50" '+(homeQuizCount===50?'selected':'')+'>50 題</option><option value="0" '+(homeQuizCount===0?'selected':'')+'>全部符合題目</option></select><button class="ux-btn-main" onclick="startFocusedQuiz()">開始刷題</button></div>'+
        '<div class="ux-note">'+scopeHint+'</div></div>'):'')+
      '<div class="ux-link-card '+(rv.dueCount?'hot':'')+'" onclick="'+(rv.dueCount?'startDueReview()':"go('review')")+'"><div class="left"><div class="title">🧠 今日複習</div><div class="sub">'+reviewSub+'</div></div>'+(rv.dueCount?'<span class="ux-badge">'+rv.dueCount+' 題</span>':'<span class="arrow">›</span>')+'</div>'+
      '<div class="ux-link-card" onclick="go(\'essay\')"><div class="left"><div class="title">✍️ 申論練習</div><div class="sub">歷屆申論、時事題材與 AI 作答回饋</div></div><span class="arrow">›</span></div>'+
      '<div class="ux-tools"><button onclick="MK.open()">計時模擬考</button><button onclick="go(\'topics\')">學習工具</button></div>';
    relabelTabs();
  };

  renderReview=function(){
    var rv=reviewSummary(), ids=rv.activeIds;
    if(!ids.length&&!rv.dueCount&&!rv.nextDueAt){
      app.innerHTML='<div class="empty"><div class="ico">✓</div><h3>'+(rv.masteredCount?'今天沒有待複習題':'還沒有錯題')+'</h3><p>'+(rv.masteredCount?('已有 '+rv.masteredCount+' 題完成學習與長期確認。'): '刷題答錯後，系統會自動安排之後的複習。')+'</p><button class="btn" style="max-width:200px;margin:22px auto 0" onclick="go(\'home\')">回首頁刷題</button></div>';
      return;
    }
    var wrongQs=ids.map(function(id){return ALL.find(function(q){return q.id===id;});}).filter(Boolean);
    var byReason={}; wrongQs.forEach(function(q){var r=q.mistake||'未分類';(byReason[r]=byReason[r]||[]).push(q);});
    window._rs=[{label:'全部未熟練錯題',ids:ids}];
    var reasons=Object.entries(byReason).sort(function(a,b){return b[1].length-a[1].length;});
    reasons.forEach(function(pair){window._rs.push({label:pair[0],ids:pair[1].map(function(x){return x.id;})});});
    var html='<div class="ux-page-head"><h2>今日複習</h2><p>先處理今天到期的錯題；其他未熟練題目需要時再重練。</p></div>';
    html+='<div class="statrow" style="margin-bottom:14px"><div class="stat"><div class="v" style="color:var(--wrong)">'+rv.dueCount+'</div><div class="k">今天到期</div></div><div class="stat"><div class="v">'+rv.activeCount+'</div><div class="k">未熟練</div></div><div class="stat"><div class="v" style="color:var(--correct)">'+rv.masteredCount+'</div><div class="k">已掌握</div></div></div>';
    if(rv.dueCount) html+='<button class="btn" onclick="startDueReview()" style="margin-bottom:10px">開始今天的複習 · '+rv.dueCount+' 題</button>';
    else if(rv.nextDueAt) html+='<div style="margin-bottom:12px;padding:11px 13px;border:1px solid var(--line);border-radius:12px;background:#fff;font-size:13px;color:var(--ink-soft)">✓ 今天已完成，下一批 '+reviewDueLabel(rv.nextDueAt)+'。</div>';
    if(wrongQs.length) html+='<button class="btn ghost" onclick="practiceSet(0)" style="margin-bottom:5px">重練全部未熟練 · '+wrongQs.length+' 題</button>';
    html+='<details class="ux-review-rule"><summary>複習規則</summary><p>答錯後 1 天再看；答對後逐步拉長到 3、7 天。連續答對 3 次後進入已掌握，再於 14、30 天做長期確認；之後若又答錯，會重新排入複習。</p></details>';
    if(reasons.length){
      html+='<div class="ux-subhead">依錯因加強</div>';
      reasons.forEach(function(pair,i){html+='<div class="gcard wrongcat" onclick="practiceSet('+(i+1)+')"><div><div class="name">'+esc(pair[0])+'</div><div class="cnt">'+pair[1].length+' 題</div></div><span class="arrow">›</span></div>';});
    }
    app.innerHTML=html; relabelTabs();
  };

  /* 畫面已經載入時立即套用一次；之後仍由原本 render/go 流程呼叫新版 renderHome/renderReview。 */
  try{ if(typeof view!=='undefined'&&(view==='home'||view==='review')) render(); }catch(_e){}
})();
</script>
<!-- SWSI UIUX V1 END -->'''

text = PATH.read_text(encoding='utf-8')
text = re.sub(r'<meta name="viewport" content="[^"]*">', '<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">', text, count=1)
pattern = re.compile(re.escape(START) + r'.*?' + re.escape(END), re.S)
if pattern.search(text):
    text = pattern.sub(block, text, count=1)
else:
    if '</body>' not in text:
        raise SystemExit('index.html missing </body>')
    text = text.replace('</body>', block + '\n</body>', 1)
PATH.write_text(text, encoding='utf-8')
print('UI/UX V1 installed.')
