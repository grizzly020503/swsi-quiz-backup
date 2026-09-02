from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

ANALYTICS_BLOCK = r'''

/* ===== SWSI Anonymous Usage Analytics V1 2026-09-02 ===== */
(function(){
  'use strict';
  var PRODUCTION_ORIGIN='https://wandering-wave-4418.c022050333.workers.dev';
  var ENDPOINT='https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/swsi-usage';
  if(location.origin!==PRODUCTION_ORIGIN)return;

  function recordPageView(){
    try{
      if(typeof window.swsiGetClientId!=='function')return;
      var client=window.swsiGetClientId();
      fetch(ENDPOINT,{
        method:'POST',
        headers:{'Content-Type':'application/json','X-SWSI-Client-ID':client},
        body:'{"event":"page_view"}',
        keepalive:true,
        credentials:'omit'
      }).catch(function(){});
    }catch(_e){}
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',recordPageView,{once:true});
  else setTimeout(recordPageView,0);
})();
/* ===== SWSI Anonymous Usage Analytics V1 END ===== */
'''

ANALYTICS_SECTION_OLD = '''<section id="tab-analytics" class="hidden"><div class="card empty section"><strong>匿名使用統計尚未啟用</strong><p>下一步才接「今日使用者、作答題數、模擬考、申論、AI 使用量」；有真實資料以前不顯示假數字。</p></div></section>'''

ANALYTICS_SECTION_NEW = '''<section id="tab-analytics" class="hidden"><div class="grid section"><div class="metric"><div class="k">今日使用者</div><div id="analyticsTodayUsers" class="v">—</div><div class="s">匿名瀏覽器約數</div></div><div class="metric"><div class="k">今日瀏覽量</div><div id="analyticsTodayViews" class="v">—</div><div class="s">正式站頁面開啟次數</div></div><div class="metric"><div class="k">近 7 日使用者</div><div id="analytics7dUsers" class="v">—</div><div class="s">7 日不重複匿名瀏覽器</div></div><div class="metric"><div class="k">累計使用者</div><div id="analyticsTotalUsers" class="v">—</div><div class="s">從啟用統計開始</div></div></div><div class="card section"><h2>累計與近 7 日</h2><div class="grid"><div class="metric"><div class="k">累計瀏覽量</div><div id="analyticsTotalViews" class="v">—</div><div class="s">從啟用統計開始</div></div><div class="metric"><div class="k">開始統計</div><div id="analyticsSince" class="v" style="font-size:18px">—</div><div class="s">舊的歷史訪客無法回補</div></div></div><div id="analyticsDaily" class="list" style="margin-top:14px"></div></div><div class="card section"><h2>統計方式</h2><div class="hint">只統計 SWSI 正式 Cloudflare 網址。使用者數以這台瀏覽器隨機產生的匿名 ID 估算；伺服器只保存 SHA-256 雜湊與每日瀏覽次數，不保存姓名、Email、原始 IP、User-Agent 或裝置指紋。同一人換瀏覽器／裝置會分開計算，清除網站資料後也可能被視為新的匿名使用者。</div></div></section>'''

STATUS_OLD = '''<div class="statusline"><span class="dot warn"></span><div><strong>使用統計</strong><div class="small">尚未啟用；下一步接匿名 Analytics</div></div></div>'''
STATUS_NEW = '''<div class="statusline"><span id="analyticsDot" class="dot warn"></span><div><strong>使用統計</strong><div id="analyticsHealth" class="small">尚未取得匿名統計資料</div></div></div>'''

RENDER_ANALYTICS = r'''
  function renderAnalytics(){
    const a=payload?.analytics||{};
    const enabled=a.enabled===true;
    const dot=$('analyticsDot'),health=$('analyticsHealth');
    if(dot)dot.className='dot '+(enabled?'ok':'warn');
    if(health)health.textContent=enabled?'匿名使用統計正常':'匿名使用統計尚未啟用或暫時無法讀取';
    const setNum=(id,v)=>{const el=$(id);if(el)el.textContent=(v===null||v===undefined)?'—':Number(v).toLocaleString('zh-TW');};
    setNum('analyticsTodayUsers',enabled?a.today_users:null);
    setNum('analyticsTodayViews',enabled?a.today_page_views:null);
    setNum('analytics7dUsers',enabled?a.seven_day_users:null);
    setNum('analyticsTotalUsers',enabled?a.total_users:null);
    setNum('analyticsTotalViews',enabled?a.total_page_views:null);
    const since=$('analyticsSince');if(since)since.textContent=enabled?(a.since||'今天'):'—';
    const daily=$('analyticsDaily');
    if(!daily)return;
    const rows=enabled&&Array.isArray(a.daily_7d)?a.daily_7d:[];
    if(!rows.length){daily.innerHTML='<div class="empty">統計啟用後，這裡會顯示近 7 日使用趨勢。</div>';return;}
    daily.innerHTML=rows.slice().reverse().map(r=>'<div class="feedback" style="padding:11px 13px"><div class="row"><strong>'+esc(r.date||'')+'</strong><div class="spacer"></div><span class="small">使用者 '+esc(Number(r.users||0).toLocaleString('zh-TW'))+'　·　瀏覽 '+esc(Number(r.page_views||0).toLocaleString('zh-TW'))+'</span></div></div>').join('');
  }
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one anchor, got {count}')
    return text.replace(old, new, 1)


def patch_runtime():
    owner = ROOT / 'monthly_patch_parts' / '99_p0_mobile_ai_guardrails.part'
    text = owner.read_text(encoding='utf-8')
    if 'SWSI Anonymous Usage Analytics V1 2026-09-02' not in text:
        anchor = '/* ===== SWSI P0 AI utilities END ===== */'
        text = replace_once(text, anchor, anchor + ANALYTICS_BLOCK, 'runtime analytics anchor')
        owner.write_text(text, encoding='utf-8')

    parts = sorted((ROOT / 'monthly_patch_parts').glob('*.part'), key=lambda p: p.name)
    built = b''.join(p.read_bytes() for p in parts)
    (ROOT / 'cdn' / 'monthly_patch.js').write_bytes(built)


def patch_admin(path: Path):
    text = path.read_text(encoding='utf-8')
    if 'analyticsTodayUsers' not in text:
        text = replace_once(text, ANALYTICS_SECTION_OLD, ANALYTICS_SECTION_NEW, f'{path}: analytics section')
    if 'id="analyticsDot"' not in text:
        text = replace_once(text, STATUS_OLD, STATUS_NEW, f'{path}: analytics status')
    if 'function renderAnalytics(){' not in text:
        text = replace_once(text, '  function feedbackWhere(f){', RENDER_ANALYTICS + '\n  function feedbackWhere(f){', f'{path}: renderAnalytics')
    if 'renderAnalytics();renderFeedback();}' not in text:
        text = replace_once(text, "$('lastUpdated').textContent='最後更新：'+new Date(payload.generated_at).toLocaleString('zh-TW');renderFeedback();}", "$('lastUpdated').textContent='最後更新：'+new Date(payload.generated_at).toLocaleString('zh-TW');renderAnalytics();renderFeedback();}", f'{path}: render call')
    path.write_text(text, encoding='utf-8')


def patch_admin_function():
    path = ROOT / 'supabase' / 'functions' / 'swsi-admin' / 'index.ts'
    text = path.read_text(encoding='utf-8')
    if 'analyticsRes' not in text:
        text = replace_once(
            text,
            'const [questionsRes, essaysRes, feedbackRes, feedbackCountRes, pendingRes, legalHitsRes] = await Promise.all([',
            'const [questionsRes, essaysRes, feedbackRes, feedbackCountRes, pendingRes, legalHitsRes, analyticsRes] = await Promise.all([',
            'swsi-admin promise destructure',
        )
        text = replace_once(
            text,
            '    admin.from("legal_watch_hits").select("id", { count: "exact", head: true }).is("resolved_at", null),\n  ]);',
            '    admin.from("legal_watch_hits").select("id", { count: "exact", head: true }).is("resolved_at", null),\n    admin.rpc("swsi_usage_summary"),\n  ]);',
            'swsi-admin analytics rpc',
        )
        text = replace_once(text, '      analytics: "not_enabled",', '      analytics: analyticsRes.error ? "unavailable" : "enabled",', 'swsi-admin analytics status')
        text = replace_once(
            text,
            '    feedback_clusters: feedbackClusters,\n    feedback: rawFeedbackRows,',
            '    analytics: analyticsRes.error ? { enabled: false, status: "unavailable" } : (analyticsRes.data ?? { enabled: false, status: "empty" }),\n    feedback_clusters: feedbackClusters,\n    feedback: rawFeedbackRows,',
            'swsi-admin analytics payload',
        )
    path.write_text(text, encoding='utf-8')


def main():
    patch_runtime()
    patch_admin(ROOT / 'admin' / 'index.html')
    patch_admin(ROOT / 'cdn' / 'admin' / 'index.html')
    patch_admin_function()
    print('USAGE ANALYTICS V1 PATCH APPLIED')


if __name__ == '__main__':
    main()
