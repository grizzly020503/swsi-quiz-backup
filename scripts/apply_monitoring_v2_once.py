#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from pathlib import Path

OWNER = Path('monthly_patch_parts/89.public-branding-info.part')
PATCH = Path('cdn/monthly_patch.js')
UPTIME = Path('scripts/public_uptime_smoke.py')
MOEX = Path('.github/workflows/moex-social-worker-sync.yml')

s = OWNER.read_text(encoding='utf-8')

# Add small, safe link/status helpers to the existing Monitoring owner CSS.
css_anchor = "      .swsi-monitor-refresh{width:100%;min-height:42px;border:1px solid var(--pine);border-radius:11px;background:#fff;color:var(--pine-deep);font:800 12px/1.4 'Noto Sans TC',sans-serif;cursor:pointer}\n"
css_extra = """      .swsi-monitor-links{display:grid;gap:5px;margin-top:7px}\n      .swsi-monitor-links a{color:var(--pine-deep);font-size:11.5px;line-height:1.5;text-decoration:underline;text-underline-offset:2px;overflow-wrap:anywhere}\n      .swsi-monitor-cadence{display:flex;gap:5px 9px;flex-wrap:wrap;margin:8px 0 2px;color:var(--ink-soft);font-size:10.8px;line-height:1.5}\n"""
if css_extra not in s:
    if css_anchor not in s:
        raise SystemExit('monitor CSS anchor missing')
    s = s.replace(css_anchor, css_anchor + css_extra, 1)

monitor_block = r'''    monitor:{
      title:'SWSI 五大監測',
      sub:'新聞＋法規＋題庫＋系統＋回報｜持續監測，重要變更仍由人工確認',
      html:`
        <div id="swsi-public-monitor" data-running="0">
          <div class="swsi-monitor-summary">
            <strong id="swsi-monitor-summary-title">準備檢查中…</strong>
            <div id="swsi-monitor-summary-text">正在讀取 SWSI 的五個監測來源；不會呼叫 AI 模型，也不會寫入回報或學習資料。</div>
            <div class="swsi-monitor-cadence"><span>新聞：約每 6 小時</span><span>法規：完整核對約每 7 天</span><span>系統：開啟當下即時檢查</span></div>
          </div>
          <div class="swsi-monitor-grid">
            <div class="swsi-monitor-item" data-monitor-key="news"><span class="swsi-monitor-dot"></span><div><div class="swsi-monitor-label">新聞／時事監測</div><div class="swsi-monitor-detail">等待讀取社工、社福、長照與政策時事雷達。</div><div class="swsi-monitor-links" data-monitor-links="news"></div></div></div>
            <div class="swsi-monitor-item" data-monitor-key="law"><span class="swsi-monitor-dot"></span><div><div class="swsi-monitor-label">法規監測</div><div class="swsi-monitor-detail">等待讀取全國法規資料庫核對快照；異動只警示，不自動改答案。</div><div class="swsi-monitor-links" data-monitor-links="law"></div></div></div>
            <div class="swsi-monitor-item" data-monitor-key="questions"><span class="swsi-monitor-dot"></span><div><div class="swsi-monitor-label">題庫監測</div><div class="swsi-monitor-detail">等待核對 4,800 題／24 shards、health 與考選部同步狀態。</div></div></div>
            <div class="swsi-monitor-item" data-monitor-key="system"><span class="swsi-monitor-dot"></span><div><div class="swsi-monitor-label">系統監測</div><div class="swsi-monitor-detail">等待檢查主站、PWA、Service Worker 與 AI 入口。</div></div></div>
            <div class="swsi-monitor-item" data-monitor-key="feedback"><span class="swsi-monitor-dot"></span><div><div class="swsi-monitor-label">使用者回報監測</div><div class="swsi-monitor-detail">等待檢查回報入口；不會建立測試回報。</div></div></div>
          </div>
          <button type="button" class="swsi-monitor-refresh" data-swsi-monitor-refresh>重新檢查</button>
          <div id="swsi-monitor-time" class="swsi-monitor-meta">尚未執行檢查。</div>
          <div class="swsi-public-info-note">新聞來源是考試時事雷達，不等於官方考試答案；法規與正式考題仍以官方資料為最高依據。監測發現異常只產生警示，不自動修改題目、答案、法規解讀或權限。</div>
        </div>
      `
    },
    privacy:{'''
monitor_pattern = re.compile(r"    monitor:\{\n      title:'SWSI 監測',.*?\n    \},\n    privacy:\{", re.S)
if not monitor_pattern.search(s):
    raise SystemExit('existing monitor INFO block not found')
s = monitor_pattern.sub(monitor_block, s, count=1)

helpers_and_run = r'''  function monitorClearLinks(key){
    var root=document.getElementById('swsi-public-monitor');
    var box=root&&root.querySelector('[data-monitor-links="'+key+'"]');
    if(box)box.textContent='';
    return box;
  }

  function monitorLinks(key,rows){
    var box=monitorClearLinks(key);
    if(!box)return;
    (rows||[]).slice(0,3).forEach(function(row){
      var url=String(row&&row.url||'');
      if(!/^https:\/\//i.test(url))return;
      var a=document.createElement('a');
      a.href=url;a.target='_blank';a.rel='noopener noreferrer';
      a.textContent=String(row&&row.label||url).slice(0,120);
      box.appendChild(a);
    });
  }

  function monitorLocalTime(value){
    if(!value)return '時間未提供';
    var d=new Date(value);
    return isNaN(d.getTime())?String(value):d.toLocaleString('zh-TW');
  }

  async function runPublicMonitor(){
    var root=document.getElementById('swsi-public-monitor');
    if(!root||root.dataset.running==='1')return;
    root.dataset.running='1';
    var title=document.getElementById('swsi-monitor-summary-title');
    var summary=document.getElementById('swsi-monitor-summary-text');
    var time=document.getElementById('swsi-monitor-time');
    if(title)title.textContent='五大監測檢查中…';
    if(summary)summary.textContent='正在讀取新聞、法規、題庫、系統與回報狀態。';
    ['news','law','questions','system','feedback'].forEach(function(k){monitorItem(k,'','檢查中…');monitorClearLinks(k);});
    var ok=0,warn=0,bad=0,total=5;
    var bust='swsi_monitor_v2='+Date.now();

    try{
      var nr=await monitorFetch(location.origin+'/auto/current_affairs.json?'+bust);
      if(!nr.ok)throw new Error('HTTP '+nr.status);
      var news=await nr.json();
      var items=Array.isArray(news.items)?news.items:[];
      if(Number(news.schema_version)!==2||!items.length)throw new Error('時事快照格式或內容異常');
      items.sort(function(a,b){return String(b.published_at||'').localeCompare(String(a.published_at||''));});
      var newest=items[0]||{};
      monitorItem('news','ok','近期待追蹤 '+items.length+' 個議題；最新：'+String(newest.title||'未命名議題').slice(0,64)+'（'+monitorLocalTime(newest.published_at)+'）。');
      monitorLinks('news',items.map(function(x){return {url:x.source_url,label:(x.category?x.category+'｜':'')+String(x.title||'來源')};}));
      ok++;
    }catch(e){monitorItem('news','bad','新聞／時事快照讀取失敗：'+(e&&e.message?e.message:'無法讀取'));bad++;}

    try{
      var lr=await monitorFetch(location.origin+'/auto/legal_watch.json?'+bust);
      if(!lr.ok)throw new Error('HTTP '+lr.status);
      var law=await lr.json();
      var wc=Number(law.watch_count||0),mc=Number(law.matched_count||0),cc=Number(law.changed_count||0);
      if(wc<20||mc<20||mc>wc)throw new Error('法規核對基線異常');
      var changes=Array.isArray(law.changes)?law.changes:[];
      if(cc!==changes.length)throw new Error('法規變更統計不一致');
      if(cc>0){
        monitorItem('law','warn','發現 '+cc+' 部法規修正日期變動，等待人工核對後才可能影響正式內容。上次完整核對：'+monitorLocalTime(law.checked_at)+'。');
        monitorLinks('law',changes.map(function(x){return {url:x.official_url,label:String(x.name||'法規')+'｜'+String(x.previous_modified_date||'?')+' → '+String(x.official_modified_date||'?')};}));
        warn++;
      }else{
        monitorItem('law','ok','官方法規核對 '+mc+'/'+wc+' 部，這次沒有偵測到修正日期變動。上次完整核對：'+monitorLocalTime(law.checked_at)+'。');
        monitorLinks('law',(law.recently_modified||[]).map(function(x){return {url:x.official_url,label:String(x.name||'法規')+'｜官方頁'};}));
        ok++;
      }
    }catch(e){monitorItem('law','bad','法規快照讀取失敗：'+(e&&e.message?e.message:'無法讀取'));bad++;}

    try{
      var qr=await monitorFetch(location.origin+'/question-shards/manifest.json?'+bust);
      if(!qr.ok)throw new Error('manifest HTTP '+qr.status);
      var qm=await qr.json();
      if(Number(qm.total_questions)!==4800||Number(qm.shard_count)!==24||!Array.isArray(qm.shards)||qm.shards.length!==24)throw new Error('題庫 manifest 基線不符');
      var hr=await monitorFetch(location.origin+'/auto/health.json?'+bust);
      if(!hr.ok)throw new Error('health HTTP '+hr.status);
      var health=await hr.json();
      if(health.status!=='ok'||Number(health.expected_total_questions)!==4800)throw new Error('題庫 health 不正常');
      var sr=await monitorFetch(location.origin+'/auto/sync_state.json?'+bust);
      if(!sr.ok)throw new Error('sync HTTP '+sr.status);
      var sync=await sr.json();
      if(!Array.isArray(sync.included_exams))throw new Error('考選部同步狀態格式異常');
      var exams=sync.included_exams.map(function(x){return String(x&&x.exam_code||'');}).filter(Boolean);
      monitorItem('questions','ok','題庫 4,800 題／24 shards、health 正常；考選部自動同步考次：'+(exams.length?exams.join('、'):'目前無新增考次')+'。');
      ok++;
    }catch(e){monitorItem('questions','bad','題庫監測失敗：'+(e&&e.message?e.message:'無法核對'));bad++;}

    try{
      var sysParts=[];
      var mr=await monitorFetch(location.origin+'/manifest.json?'+bust);if(!mr.ok)throw new Error('manifest HTTP '+mr.status);var manifest=await mr.json();if(manifest.display!=='standalone'||!manifest.start_url)throw new Error('PWA manifest contract 不符');sysParts.push('PWA');
      var sw=await monitorFetch(location.origin+'/sw.js?'+bust);if(!sw.ok)throw new Error('Service Worker HTTP '+sw.status);sysParts.push('SW');
      var isOfficial=location.hostname==='wandering-wave-4418.c022050333.workers.dev';
      if(isOfficial){var ai=await monitorFetch(location.origin+'/api/ai',{method:'OPTIONS'});if(ai.status!==204)throw new Error('AI HTTP '+ai.status);sysParts.push('AI');monitorItem('system','ok','主站已載入；'+sysParts.join('／')+' 入口正常，AI 僅做 preflight、未呼叫模型。');ok++;}
      else{monitorItem('system','warn','預覽環境：主站資產、PWA、Service Worker 可讀；正式 AI CORS 只在正式站驗證。');warn++;}
    }catch(e){monitorItem('system','bad','系統監測失敗：'+(e&&e.message?e.message:'無法連線'));bad++;}

    try{
      var fb=await monitorFetch('https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/swsi-feedback',{method:'OPTIONS'});
      if(fb.status!==204)throw new Error('HTTP '+fb.status);
      monitorItem('feedback','ok','回報入口 preflight 正常（204）；未建立測試回報，也未讀取管理端個資。');ok++;
    }catch(e){monitorItem('feedback','bad','使用者回報入口檢查失敗：'+(e&&e.message?e.message:'無法連線'));bad++;}

    if(title)title.textContent=bad?'部分監測需要處理':(warn?'監測正常，但有待確認事項':'五大監測目前正常');
    if(summary){
      summary.textContent='五大監測：'+ok+' 正常、'+warn+' 注意、'+bad+' 異常。'+
        (bad?'異常只代表檢查當下有問題，可稍後重新檢查；正式資料不會因此自動修改。':warn?'注意項目會交由人工核對，不自動改答案。':'目前沒有發現阻斷性異常。');
    }
    if(time)time.textContent='最後檢查：'+new Date().toLocaleString('zh-TW');
    root.dataset.running='0';
  }
  window.swsiRunPublicMonitor=runPublicMonitor;'''
run_pattern = re.compile(r"  async function runPublicMonitor\(\)\{.*?\n  window\.swsiRunPublicMonitor=runPublicMonitor;", re.S)
if not run_pattern.search(s):
    raise SystemExit('runPublicMonitor block not found')
s = run_pattern.sub(helpers_and_run, s, count=1)

old_marker = "window.SWSI_PUBLIC_INFO={version:'2026-09-01.monitoring-v1.1',marker:'SWSI Public Branding / Monitoring Center V1.1 2026-09-01'};"
new_marker = "window.SWSI_PUBLIC_INFO={version:'2026-09-01.monitoring-v2',marker:'SWSI Public Branding / Monitoring Center V2 2026-09-01'};"
if old_marker not in s:
    raise SystemExit('V1.1 marker missing')
s = s.replace(old_marker, new_marker, 1)
OWNER.write_text(s, encoding='utf-8')

# Rebuild the generated CDN runtime from its canonical owner parts.
parts = sorted(Path('monthly_patch_parts').glob('*.part'))
PATCH.write_text(''.join(p.read_text(encoding='utf-8') for p in parts), encoding='utf-8')

# Extend the cheap daily external sentinel so all five monitoring areas have an outside signal.
u = UPTIME.read_text(encoding='utf-8')
anchor = "    cors_headers = {\n"
insert = r'''    body, _ = require_status("Current-affairs snapshot", PRIMARY + "/auto/current_affairs.json")
    news = json.loads(body)
    news_items = news.get("items") or []
    if int(news.get("schema_version", -1)) != 2 or not news_items:
        raise AssertionError("Current-affairs snapshot: contract mismatch")
    checks.append(f"news-{len(news_items)}")

    body, _ = require_status("Legal-watch snapshot", PRIMARY + "/auto/legal_watch.json")
    laws = json.loads(body)
    law_watch = int(laws.get("watch_count", -1))
    law_matched = int(laws.get("matched_count", -1))
    law_changed = int(laws.get("changed_count", -1))
    if law_watch < 20 or law_matched < 20 or law_changed != len(laws.get("changes") or []):
        raise AssertionError("Legal-watch snapshot: contract mismatch")
    checks.append(f"laws-{law_matched}/{law_watch}")

    body, _ = require_status("Question health", PRIMARY + "/auto/health.json")
    qhealth = json.loads(body)
    if qhealth.get("status") != "ok" or int(qhealth.get("expected_total_questions", -1)) != 4800:
        raise AssertionError("Question health: contract mismatch")
    checks.append("question-health")

'''
if insert not in u:
    if anchor not in u:
        raise SystemExit('uptime cors anchor missing')
    u = u.replace(anchor, insert + anchor, 1)
UPTIME.write_text(u, encoding='utf-8')

# Make full official legal-page verification weekly, while keeping daily MOEX/news sync.
m = MOEX.read_text(encoding='utf-8')
m = m.replace(
    '# 台灣時間每天 10:35（UTC 02:35）。國考與時事每日檢查；法規成功後 28 天才再抓，失敗至少隔 3 天再試。',
    '# 台灣時間每天 10:35（UTC 02:35）。國考與時事每日檢查；法規成功後 7 天再完整核對，失敗至少隔 3 天再試。',
    1,
)
needle = "            --attempt-state data/legal_watch_attempt.json \\\n            $force\n"
replacement = "            --attempt-state data/legal_watch_attempt.json \\\n            --min-days 7 \\\n            $force\n"
if replacement not in m:
    if needle not in m:
        raise SystemExit('MOEX legal-watch invocation anchor missing')
    m = m.replace(needle, replacement, 1)
MOEX.write_text(m, encoding='utf-8')

# Materialize privacy-safe snapshots into the public Cloudflare asset tree.
# legal_watch.json is generated by the workflow before this script runs.
for name in ('current_affairs.json','legal_watch.json','health.json','sync_state.json'):
    src = Path('auto') / name
    if not src.exists():
        raise SystemExit(f'missing auto snapshot: {src}')
    dst = Path('cdn/auto') / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

print('Monitoring V2 integration staged')
