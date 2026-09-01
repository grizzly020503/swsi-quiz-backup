#!/usr/bin/env python3
from pathlib import Path

p=Path('monthly_patch_parts/89.public-branding-info.part')
s=p.read_text(encoding='utf-8')

def one(old,new,label):
    global s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 occurrence, got {n}')
    s=s.replace(old,new,1)

one(".swsi-public-info-nav{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:0 0 14px}",
    ".swsi-public-info-nav{display:grid;grid-template-columns:repeat(auto-fit,minmax(72px,1fr));gap:6px;margin:0 0 14px}",'nav columns')

one("      .swsi-public-info-nav button.on{background:var(--pine);border-color:var(--pine);color:#fff}\n",
"""      .swsi-public-info-nav button.on{background:var(--pine);border-color:var(--pine);color:#fff}
      .swsi-monitor-summary{border:1px solid #D7E0DB;border-radius:14px;padding:12px 13px;background:#F7FAF8;margin-bottom:12px}
      .swsi-monitor-summary strong{display:block;font-size:15px;color:var(--pine-deep);margin-bottom:3px}
      .swsi-monitor-grid{display:grid;gap:8px;margin:10px 0 12px}
      .swsi-monitor-item{display:grid;grid-template-columns:12px 1fr;gap:9px;align-items:start;border:1px solid #E2E8E4;border-radius:12px;padding:10px 11px;background:#fff}
      .swsi-monitor-dot{width:10px;height:10px;border-radius:50%;margin-top:5px;background:#A8B1AC}
      .swsi-monitor-dot.ok{background:#16845B}.swsi-monitor-dot.warn{background:#D18B16}.swsi-monitor-dot.bad{background:#C13F3F}
      .swsi-monitor-label{font-weight:800;color:#303833}.swsi-monitor-detail{font-size:11.5px;line-height:1.55;color:var(--ink-soft);margin-top:2px}
      .swsi-monitor-meta{font-size:11px;line-height:1.6;color:var(--ink-soft);margin-top:8px}
      .swsi-monitor-refresh{width:100%;min-height:42px;border:1px solid var(--pine);border-radius:11px;background:#fff;color:var(--pine-deep);font:800 12px/1.4 'Noto Sans TC',sans-serif;cursor:pointer}
""",'monitor css')

monitor_block="""    monitor:{
      title:'SWSI 監測',
      sub:'開啟當下即時檢查｜背景另有低成本定期哨兵',
      html:`
        <div id="swsi-public-monitor" data-running="0">
          <div class="swsi-monitor-summary">
            <strong id="swsi-monitor-summary-title">準備檢查中…</strong>
            <div id="swsi-monitor-summary-text">SWSI 會檢查公開學習路徑是否可用；這不是每秒追蹤，也不蒐集你的個人資料。</div>
          </div>
          <div class="swsi-monitor-grid">
            <div class="swsi-monitor-item" data-monitor-key="site"><span class="swsi-monitor-dot"></span><div><div class="swsi-monitor-label">網站</div><div class="swsi-monitor-detail">等待檢查 Cloudflare 主站。</div></div></div>
            <div class="swsi-monitor-item" data-monitor-key="pwa"><span class="swsi-monitor-dot"></span><div><div class="swsi-monitor-label">PWA</div><div class="swsi-monitor-detail">等待檢查 manifest 與 Service Worker。</div></div></div>
            <div class="swsi-monitor-item" data-monitor-key="questions"><span class="swsi-monitor-dot"></span><div><div class="swsi-monitor-label">題庫完整性</div><div class="swsi-monitor-detail">等待核對 4,800 題／24 shards。</div></div></div>
            <div class="swsi-monitor-item" data-monitor-key="ai"><span class="swsi-monitor-dot"></span><div><div class="swsi-monitor-label">AI 入口</div><div class="swsi-monitor-detail">等待檢查 /api/ai；不會送出申論內容，也不會呼叫模型。</div></div></div>
            <div class="swsi-monitor-item" data-monitor-key="feedback"><span class="swsi-monitor-dot"></span><div><div class="swsi-monitor-label">問題回報</div><div class="swsi-monitor-detail">等待檢查回報 Edge Function 的公開 CORS 入口；不會寫入資料。</div></div></div>
            <div class="swsi-monitor-item" data-monitor-key="law"><span class="swsi-monitor-dot ok"></span><div><div class="swsi-monitor-label">法規監測</div><div class="swsi-monitor-detail">法規監測機制已建置；異動需經核對後才影響正式內容，不自動改答案。</div></div></div>
          </div>
          <button type="button" class="swsi-monitor-refresh" data-swsi-monitor-refresh>重新檢查</button>
          <div id="swsi-monitor-time" class="swsi-monitor-meta">尚未執行檢查。</div>
          <div class="swsi-public-info-note">監測結果只代表檢查當下的公開服務狀態；正式考題、答案與法規仍以官方資料及人工核對為準。</div>
        </div>
      `
    },
"""
one("    privacy:{\n",monitor_block+"    privacy:{\n",'monitor info block')
one('        <button type="button" data-swsi-public-info="sources">資料來源</button>\n','        <button type="button" data-swsi-public-info="sources">資料來源</button>\n        <button type="button" data-swsi-public-info="monitor">監測</button>\n','footer monitor link')
one("      var label={about:'關於',sources:'資料來源',privacy:'隱私',terms:'使用條款'}[k];","      var label={about:'關於',sources:'資料來源',monitor:'監測',privacy:'隱私',terms:'使用條款'}[k];",'monitor nav label')

monitor_js="""
  function monitorItem(key,state,detail){
    var root=document.getElementById('swsi-public-monitor');
    if(!root)return;
    var item=root.querySelector('[data-monitor-key="'+key+'"]');
    if(!item)return;
    var dot=item.querySelector('.swsi-monitor-dot');
    var text=item.querySelector('.swsi-monitor-detail');
    if(dot)dot.className='swsi-monitor-dot '+state;
    if(text)text.textContent=detail;
  }

  async function monitorFetch(url,options){
    var opts=options||{};
    opts.cache='no-store';
    return fetch(url,opts);
  }

  async function runPublicMonitor(){
    var root=document.getElementById('swsi-public-monitor');
    if(!root||root.dataset.running==='1')return;
    root.dataset.running='1';
    var title=document.getElementById('swsi-monitor-summary-title');
    var summary=document.getElementById('swsi-monitor-summary-text');
    var time=document.getElementById('swsi-monitor-time');
    if(title)title.textContent='正在檢查公開服務…';
    if(summary)summary.textContent='只做公開讀取與 CORS preflight，不送出答案、聯絡方式或 AI prompt。';
    ['site','pwa','questions','ai','feedback'].forEach(function(k){monitorItem(k,'warn','檢查中…');});
    var bust='swsi_monitor='+Date.now();
    var passed=0,total=5;
    try{var home=await monitorFetch(location.origin+'/?'+bust);if(!home.ok)throw new Error('HTTP '+home.status);monitorItem('site','ok','Cloudflare 主站可連線（HTTP '+home.status+'）。');passed++;}catch(e){monitorItem('site','bad','主站檢查失敗：'+(e&&e.message?e.message:'無法連線'));}
    try{var pair=await Promise.all([monitorFetch(location.origin+'/manifest.json?'+bust),monitorFetch(location.origin+'/sw.js?'+bust)]);if(!pair[0].ok||!pair[1].ok)throw new Error('manifest '+pair[0].status+' / sw '+pair[1].status);var manifest=await pair[0].json();if(manifest.display!=='standalone'||!manifest.start_url)throw new Error('PWA contract 不完整');monitorItem('pwa','ok','manifest 與 Service Worker 均可讀取。');passed++;}catch(e){monitorItem('pwa','bad','PWA 檢查失敗：'+(e&&e.message?e.message:'無法讀取'));}
    try{var qr=await monitorFetch(location.origin+'/question-shards/manifest.json?'+bust);if(!qr.ok)throw new Error('HTTP '+qr.status);var qm=await qr.json();if(Number(qm.total_questions)!==4800||Number(qm.shard_count)!==24)throw new Error('題庫基線不符');monitorItem('questions','ok','題庫 manifest：4,800 題／24 shards。');passed++;}catch(e){monitorItem('questions','bad','題庫檢查失敗：'+(e&&e.message?e.message:'無法核對'));}
    try{var isOfficial=location.hostname==='wandering-wave-4418.c022050333.workers.dev';if(!isOfficial){monitorItem('ai','warn','預覽網址不放寬正式 AI CORS；正式站會檢查 /api/ai。');total--;}else{var ai=await monitorFetch(location.origin+'/api/ai',{method:'OPTIONS'});if(ai.status!==204)throw new Error('HTTP '+ai.status);monitorItem('ai','ok','AI 入口 preflight 正常（204），未呼叫模型。');passed++;}}catch(e){monitorItem('ai','bad','AI 入口檢查失敗：'+(e&&e.message?e.message:'無法連線'));}
    try{var fb=await monitorFetch('https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/swsi-feedback',{method:'OPTIONS'});if(fb.status!==204)throw new Error('HTTP '+fb.status);monitorItem('feedback','ok','回報入口 preflight 正常（204），未寫入資料。');passed++;}catch(e){monitorItem('feedback','bad','問題回報入口檢查失敗：'+(e&&e.message?e.message:'無法連線'));}
    var allGood=passed===total;if(title)title.textContent=allGood?'目前公開學習路徑正常':'部分服務需要注意';if(summary)summary.textContent=allGood?('即時檢查 '+passed+'/'+total+' 項通過；法規監測機制另以人工核對守門。'):('即時檢查 '+passed+'/'+total+' 項通過；異常不代表你的學習紀錄遺失，可稍後重新檢查。');if(time)time.textContent='最後檢查：'+new Date().toLocaleString('zh-TW');root.dataset.running='0';
  }
  window.swsiRunPublicMonitor=runPublicMonitor;

"""
one("  function openInfo(key,opener){\n",monitor_js+"  function openInfo(key,opener){\n",'monitor runtime')
one("    if(close)close.focus();\n  }\n","    if(close)close.focus();\n    if(key==='monitor')setTimeout(runPublicMonitor,0);\n  }\n",'monitor open trigger')
old_nav="""    var nav=ev.target&&ev.target.closest?ev.target.closest('[data-swsi-info-nav]'):null;
    if(nav){
      var ov=document.getElementById('swsi-public-info-backdrop');
      if(ov){ov.innerHTML=renderInfo(nav.getAttribute('data-swsi-info-nav'));var c=ov.querySelector('.swsi-public-info-close');if(c)c.focus();}
    }
"""
new_nav="""    var refresh=ev.target&&ev.target.closest?ev.target.closest('[data-swsi-monitor-refresh]'):null;
    if(refresh){ev.preventDefault();runPublicMonitor();return;}
    var nav=ev.target&&ev.target.closest?ev.target.closest('[data-swsi-info-nav]'):null;
    if(nav){
      var monitorKey=nav.getAttribute('data-swsi-info-nav');
      var ov=document.getElementById('swsi-public-info-backdrop');
      if(ov){ov.innerHTML=renderInfo(monitorKey);var c=ov.querySelector('.swsi-public-info-close');if(c)c.focus();if(monitorKey==='monitor')setTimeout(runPublicMonitor,0);}
    }
"""
one(old_nav,new_nav,'monitor nav/refresh delegation')
one("  window.SWSI_PUBLIC_INFO={version:'2026-08-28.v1',marker:'SWSI Public Branding / Information Center 2026-08-28'};","  window.SWSI_PUBLIC_INFO={version:'2026-09-01.monitoring-v1',marker:'SWSI Public Branding / Monitoring Center V1 2026-09-01'};",'public info version')
p.write_text(s,encoding='utf-8')
