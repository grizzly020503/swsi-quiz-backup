from pathlib import Path
import re

p = Path('index.html')
s = p.read_text(encoding='utf-8')

if 'FOCUSED NAV V1 START' in s:
    print('Focused nav already installed.')
    raise SystemExit(0)

marker = "/* ---------- 導航 ---------- */\nfunction go(v){ view=v;"
if marker not in s:
    raise SystemExit('navigation marker not found')

helper = r'''/* ===== FOCUSED NAV V1 START ===== */
function applyFocusedTabbar(){
  const topics=document.getElementById('t-topics');
  const progress=document.getElementById('t-progress');
  const review=document.getElementById('t-review');
  const essay=document.getElementById('t-essay');
  if(topics) topics.style.display='none';
  if(progress) progress.style.display='none';
  /* 三個核心入口固定成：首頁 → 複習 → 申論 */
  if(tabbar && review && essay){
    try{ tabbar.insertBefore(review,essay); }catch(_e){}
  }
}
/* ===== FOCUSED NAV V1 END ===== */

'''
s = s.replace('/* ---------- 導航 ---------- */\n', '/* ---------- 導航 ---------- */\n' + helper, 1)

init_target = "    tabbar.style.display='flex';\n    if(ALL.length===0){ go('admin'); } else { go('home'); }"
if init_target not in s:
    raise SystemExit('init tabbar target not found')
s = s.replace(init_target, "    tabbar.style.display='flex';\n    applyFocusedTabbar();\n    if(ALL.length===0){ go('admin'); } else { go('home'); }", 1)

# 把「我的進度」收進學習工具頁，不刪功能。
needle = "    <div class=\"gcard\" onclick=\"SG.open()\" style=\"background:#7E7A66;border-color:#7E7A66\"><div><div class=\"name\" style=\"color:#fff\">📖 讀書指南</div><div class=\"cnt\" style=\"color:#ece9da\">學長姊應考心得 · 各科速查 · 申論策略</div></div><span class=\"arrow\" style=\"color:#fff\">›</span></div>\n"
if needle not in s:
    raise SystemExit('study-guide card target not found')
progress_card = needle + "    <div class=\"gcard\" onclick=\"go('progress')\"><div><div class=\"name\">📊 我的進度</div><div class=\"cnt\">各科正確率、常錯考點與錯因分布</div></div><span class=\"arrow\">›</span></div>\n"
s = s.replace(needle, progress_card, 1)

p.write_text(s, encoding='utf-8')
print('Installed focused three-tab navigation.')
