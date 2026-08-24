from pathlib import Path
import re

p = Path('index.html')
s = p.read_text(encoding='utf-8')

if 'LEGAL QUALITY GUARD V1 START' in s:
    print('Legal quality guard already installed.')
    raise SystemExit(0)

def replace_once(old, new, label):
    global s
    if old not in s:
        raise SystemExit(f'Missing target: {label}')
    s = s.replace(old, new, 1)

# 1) 把 Supabase 的法規品質欄位帶進前端題目物件。
n, count = re.subn(
    r"law:r\.law\|\|'',mistake:r\.mistake\|\|''\};",
    "law:r.law||'',mistake:r.mistake||'',legal_status:r.legal_status||'unreviewed',legal_checked_at:r.legal_checked_at||'',legal_note:r.legal_note||'',legal_source_url:r.legal_source_url||''};",
    s,
    count=1,
)
if count != 1:
    raise SystemExit('Could not patch normalize() legal fields')
s = n

# 2) 以資料庫明確狀態為準；舊題只做 watch，不自行宣告法律已改。
pat = re.compile(r"const LAW_UPDATED = new Set\(\[.*?\]\);\nfunction lawUpdated\(q\)\{.*?\}\n", re.S)
block = r'''/* ===== LEGAL QUALITY GUARD V1 START ===== */
const LAW_UPDATED = new Set([ /* 舊版人工清單仍保留相容；正式狀態以 legal_status='changed' 為主 */ ]);
function lawSensitive(q){
  return !!q && (q.legal_status!=='not_applicable') && (q.subject==='社會政策與社會立法' || !!q.law || q.legal_status==='verified_current' || q.legal_status==='changed');
}
function lawConfirmedChanged(q){
  return !!q && (q.legal_status==='changed' || LAW_UPDATED.has(q.id) || q.law_updated===true || q.law_updated==='1' || q.law_updated==='是');
}
function lawNeedsWatch(q){
  if(!q || lawConfirmedChanged(q) || q.legal_status==='verified_current' || !lawSensitive(q)) return false;
  const y=parseInt(q.year,10)||0;
  return !!y && (maxExamYear()-y)>=3;
}
function lawUpdated(q){ return lawConfirmedChanged(q); }
function legalWeight(q){
  if(lawConfirmedChanged(q)) return 0.05;
  if(lawNeedsWatch(q)) return 0.35;
  return 1;
}
function legalBadge(q){
  if(lawConfirmedChanged(q)) return '<span class="tag year" style="background:var(--wrong-bg);color:var(--wrong)">⚠ 法規已變更</span>';
  if(q&&q.legal_status==='verified_current') return '<span class="tag year" style="background:var(--correct-bg);color:var(--pine)">法規已核對</span>';
  if(lawNeedsWatch(q)) return '<span class="tag year" style="background:#F1ECDD;color:#756B4B">法規年代較舊</span>';
  return '';
}
function legalNotice(q){
  if(lawConfirmedChanged(q)){
    const note=q&&q.legal_note?`<br>${esc(q.legal_note)}`:'';
    return `<div style="margin:0 0 14px;padding:10px 12px;border-radius:10px;background:var(--wrong-bg);color:var(--wrong);font-size:12px;line-height:1.7"><b>⚠ 法規已確認變更：</b>這是當年國考題，原答案僅代表當時標準，不作現行法規依據。${note}</div>`;
  }
  if(lawNeedsWatch(q)) return '<div style="margin:0 0 14px;padding:10px 12px;border-radius:10px;background:#F5F1E5;color:#756B4B;font-size:12px;line-height:1.7"><b>法規年代較舊：</b>目前沒有把它判定為「已修法」，但相關規定可能隨時間調整；請把本題視為歷屆考題，現行內容以最新法規為準。</div>';
  return '';
}
/* ===== LEGAL QUALITY GUARD V1 END ===== */
'''
s, count = pat.subn(block, s, count=1)
if count != 1:
    raise SystemExit('Could not replace legacy lawUpdated block')

# 3) 舊法規敏感題降低抽題權重；已確認變更幾乎不主動抽。
replace_once(
    "function drawWeight(q){ return yearWeight(q)*kpWeight(q); }",
    "function drawWeight(q){ return yearWeight(q)*kpWeight(q)*legalWeight(q); }",
    'drawWeight',
)

# 4) 已確認變更的法規題，不進一般智慧推薦／近年快速刷；指定歷屆仍可查看。
replace_once(
    "if(homeQuizScope==='smart') return !y || y>=mx-9;",
    "if(homeQuizScope==='smart') return (!y || y>=mx-9) && !lawConfirmedChanged(q);",
    'smart history filter',
)
replace_once(
    "if(homeQuizScope==='recent3') return y>=mx-2;",
    "if(homeQuizScope==='recent3') return y>=mx-2 && !lawConfirmedChanged(q);",
    'recent3 filter',
)
replace_once(
    "if(homeQuizScope==='recent5') return y>=mx-4;",
    "if(homeQuizScope==='recent5') return y>=mx-4 && !lawConfirmedChanged(q);",
    'recent5 filter',
)

# 5) 已確認變更的題目不再進間隔複習，避免反覆背舊法規答案。
replace_once(
    "const st=bootstrapReviewState(), now=Date.now(), exists=new Set(ALL.map(q=>q.id));",
    "const st=bootstrapReviewState(), now=Date.now(), exists=new Set(ALL.filter(q=>!lawConfirmedChanged(q)).map(q=>q.id));",
    'review exclusion',
)

# 6) 題目頁顯示保守、明確的狀態提示。
s, count = re.subn(
    r"\$\{lawUpdated\(item\)\?'<span class=\\\"tag year\\\" style=\\\"background:var\(--wrong-bg\);color:var\(--wrong\)\\\">⚠ 法規已更新</span>':''\}",
    "${legalBadge(item)}",
    s,
    count=1,
)
if count != 1:
    # HTML 原始碼內通常不是跳脫引號，處理第二種形式。
    s, count = re.subn(
        r"\$\{lawUpdated\(item\)\?'<span class=\"tag year\" style=\"background:var\(--wrong-bg\);color:var\(--wrong\)\">⚠ 法規已更新</span>':''\}",
        "${legalBadge(item)}",
        s,
        count=1,
    )
if count != 1:
    raise SystemExit('Could not replace legal badge')

replace_once(
    "</div>\n      <div class=\"qtext\">${item.q}</div>${optHTML}",
    "</div>\n      ${legalNotice(item)}\n      <div class=\"qtext\">${item.q}</div>${optHTML}",
    'question legal notice',
)

p.write_text(s, encoding='utf-8')
print('Installed legal quality guard.')
