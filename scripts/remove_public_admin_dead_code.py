#!/usr/bin/env python3
from pathlib import Path

P = Path('index.html')
text = P.read_text(encoding='utf-8')


def once(old, new, label):
    global text
    if old not in text:
        raise SystemExit(f'missing marker: {label}')
    text = text.replace(old, new, 1)

# PapaParse was only used by the old browser-side CSV admin importer.
once('<script src="https://cdn.jsdelivr.net/npm/papaparse@5.4.1/papaparse.min.js"></script>\n', '', 'PapaParse script')

# Remove unused admin-only styles.
once('  .adminbox{background:var(--paper2);border:1px solid var(--line);border-radius:16px;padding:22px;}\n', '', 'adminbox css')
text = text.replace('.time-card,.qcard,.ecard,.gcard,.sumcard,.adminbox{', '.time-card,.qcard,.ecard,.gcard,.sumcard{')
text = text.replace('.qcard,.sumcard,.adminbox{', '.qcard,.sumcard{')

once('let adminUser=null;\n', '', 'adminUser variable')

old_init = '''    if(window.supabase && typeof window.supabase.createClient==='function'){
      sb=window.supabase.createClient(CONFIG.url,CONFIG.key);
      try{
        const {data:{session}}=await sb.auth.getSession();
        adminUser=session?session.user:null;
      }catch(_authErr){ adminUser=null; }
    }else{
      sb=null;
      adminUser=null;
    }
    await loadAll();
    await loadAutoEssays();
    tabbar.style.display='flex';
    applyFocusedTabbar();
    if(ALL.length===0){ go('admin'); } else { go('home'); }
'''
new_init = '''    if(window.supabase && typeof window.supabase.createClient==='function'){
      sb=window.supabase.createClient(CONFIG.url,CONFIG.key);
    }else{
      sb=null;
    }
    await loadAll();
    await loadAutoEssays();
    tabbar.style.display='flex';
    applyFocusedTabbar();
    go('home');
'''
once(old_init, new_init, 'admin auth init')

# Remove login/logout/admin UI and CSV helper functions before parseExp.
start = text.find('/* ---------- 管理頁 ---------- */')
parse_start = text.find('function parseExp(raw){', start)
if start < 0 or parse_start < 0:
    raise SystemExit('admin block / parseExp boundary not found')
text = text[:start] + '/* ---------- 舊版題解標籤解析 ---------- */\n' + text[parse_start:]

# parseExp is still needed by normalize(); remove only importer mapping/upload code after it.
map_start = text.find('function mapRow(row){', text.find('function parseExp(raw){'))
font_marker = text.find('/* ---------- 文字大小 ---------- */', map_start)
if map_start < 0 or font_marker < 0:
    raise SystemExit('mapRow/import block boundary not found')
text = text[:map_start] + text[font_marker:]

P.write_text(text, encoding='utf-8')

final = P.read_text(encoding='utf-8')
for forbidden in (
    'renderAdmin', 'adminUser', 'adminLogin', 'adminLogout', 'doImport',
    'Papa.parse', 'papaparse', 'CSV UTF-8', '.adminbox', "go('admin')"
):
    if forbidden in final:
        raise SystemExit(f'admin dead code remains: {forbidden}')
if 'function parseExp(raw){' not in final:
    raise SystemExit('parseExp was accidentally removed')
if 'const pp=parseExp(blob);' not in final:
    raise SystemExit('normalize no longer references parseExp as expected')
print('Public admin dead code removed; parseExp preserved.')
