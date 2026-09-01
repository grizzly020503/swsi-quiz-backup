#!/usr/bin/env python3
"""Apply the SWSI monthly front-end patch to the Netlify build copy of index.html.

The repository keeps the historical monolithic index.html intact. Netlify copies it
into _site, this script applies a small, fail-closed set of exact transformations,
and monthly_patch.js (loaded last) supplies the maintained override layer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEO_OLD = '<title>社工師國考題庫</title>'
SEO_NEW = '''<title>社工師國考免費題庫｜SWSI</title>
<meta name="description" content="免費社工師國考學習平台：歷屆試題、解析、錯題複習、模擬考與申論練習，不鎖題、不賣解答。">
<link rel="canonical" href="https://swsi-quiznetlify.netlify.app/">
<meta property="og:title" content="社工師國考免費題庫｜SWSI">
<meta property="og:description" content="免費練社工師國考歷屆試題、錯題複習、模擬考與申論。">
<meta property="og:type" content="website">
<meta property="og:url" content="https://swsi-quiznetlify.netlify.app/">'''

# Student first paint must not wait for third-party fonts or a client SDK that is
# not required by the CDN-first question path. The legacy code already has a
# REST fallback whenever window.supabase is unavailable.
FONT_OLD = '''<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@500;700;900&family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">'''
FONT_NEW = '<meta name="swsi-font-policy" content="system-font-first">'
SUPABASE_SDK_OLD = '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>'
SUPABASE_SDK_NEW = '<script>window.__SWSI_STUDENT_REST_ONLY__=true;</script>'
INITIAL_APP_OLD = '<main id="app"><div class="empty"><div class="spinner"></div><p style="margin-top:16px">載入題庫中…</p></div></main>'
INITIAL_APP_NEW = '''<main id="app"><div class="empty" aria-busy="true"><h3>正在開啟 SWSI</h3><p style="margin-top:8px">介面先顯示，題庫資料會在背景準備。</p></div></main>'''

MK_GRADE_OLD = '''    var correct=0, answered=0, bySubj={}, wrong=[];
    Q.forEach(function(q,i){
      var picked=ans[i]!=null?ans[i]:null;
      var ok=picked!=null&&(picked===q.answer||/一律給分|送分/.test(String(q.answer||'')));
      if(picked!=null){ answered++; if(ok)correct++;
        if(!bySubj[q.subject])bySubj[q.subject]={t:0,c:0};
        bySubj[q.subject].t++; if(ok)bySubj[q.subject].c++;
        try{ if(typeof record==='function') record(q,picked,ok); }catch(e){}
      }
      if(!ok) wrong.push({q:q,picked:picked});
    });'''

MK_GRADE_NEW = '''    var correct=0, answered=0, bySubj={}, wrong=[];
    Q.forEach(function(q,i){
      var picked=ans[i]!=null?ans[i]:null;
      var ok=(typeof isCorrectAnswer==='function')?isCorrectAnswer(q,picked):(picked!=null&&picked===q.answer);
      if(picked!=null) answered++;
      if(!bySubj[q.subject])bySubj[q.subject]={t:0,c:0};
      bySubj[q.subject].t++;
      if(ok){ correct++; bySubj[q.subject].c++; }
      try{ if(typeof record==='function') record(q,picked,ok); }catch(e){}
      if(!ok) wrong.push({q:q,picked:picked});
    });'''

MK_LABEL_OLD = '''<span class="mk-tag n">正解 '+E(q.answer||'')+'</span>'''
MK_LABEL_NEW = '''<span class="mk-tag n">'+E((typeof answerLabel==='function')?answerLabel(q):('正解 '+(q.answer||'')))+'</span>'''

ROUND_1_OLD = '''<option value="第一次" '+(homeQuizRound==='第一次'?'selected':'')+'>第一次</option>'''
ROUND_1_NEW = '''<option value="1" '+(homeQuizRound==='1'?'selected':'')+'>第一次</option>'''
ROUND_2_OLD = '''<option value="第二次" '+(homeQuizRound==='第二次'?'selected':'')+'>第二次</option>'''
ROUND_2_NEW = '''<option value="2" '+(homeQuizRound==='2'?'selected':'')+'>第二次</option>'''


def replace_exact(text: str, old: str, new: str, label: str, expected: int = 1) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f'{label}: expected {expected} occurrence(s), found {count}')
    return text.replace(old, new, expected)


def _array_span(text: str, name: str) -> tuple[int, int]:
    marker = f'window.{name}'
    pos = text.find(marker)
    if pos < 0:
        raise RuntimeError(f'knowledge canonical bootstrap: missing {marker}')
    eq = text.find('=', pos + len(marker))
    if eq < 0:
        raise RuntimeError(f'knowledge canonical bootstrap: missing assignment for {marker}')
    start = text.find('[', eq + 1)
    if start < 0:
        raise RuntimeError(f'knowledge canonical bootstrap: missing array for {marker}')
    depth = 0
    quote: str | None = None
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if quote is not None:
            if escaped:
                escaped = False
                continue
            if ch == '\\':
                escaped = True
                continue
            if ch == quote:
                quote = None
            continue
        if ch in ('"', "'", '`'):
            quote = ch
            continue
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise RuntimeError(f'knowledge canonical bootstrap: unterminated array for {marker}')


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_canonical_knowledge() -> tuple[str, str, dict]:
    laws_path = ROOT / 'data' / 'laws.canonical.json'
    theories_path = ROOT / 'data' / 'theories.canonical.json'
    manifest_path = ROOT / 'data' / 'knowledge_canonical_manifest.json'
    baseline_path = ROOT / 'data' / 'knowledge_runtime_baseline.json'
    for p in (laws_path, theories_path, manifest_path, baseline_path):
        if not p.exists():
            raise RuntimeError(f'knowledge canonical bootstrap: missing {p.relative_to(ROOT)}')

    laws_raw = laws_path.read_text(encoding='utf-8')
    theories_raw = theories_path.read_text(encoding='utf-8')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
    if manifest != baseline:
        raise RuntimeError('knowledge canonical bootstrap: canonical manifest differs from pinned runtime baseline')

    laws = json.loads(laws_raw)
    theories = json.loads(theories_raw)
    if not isinstance(laws, list) or not isinstance(theories, list):
        raise RuntimeError('knowledge canonical bootstrap: canonical payload must contain arrays')
    if len(laws) != int(manifest['laws']['count']) or len(theories) != int(manifest['theories']['count']):
        raise RuntimeError('knowledge canonical bootstrap: canonical count mismatch')
    if _sha256(laws_raw) != manifest['laws']['sha256'] or _sha256(theories_raw) != manifest['theories']['sha256']:
        raise RuntimeError('knowledge canonical bootstrap: canonical SHA-256 mismatch')
    for label, rows in (('laws', laws), ('theories', theories)):
        names = [str(row.get('n', '')).strip() for row in rows if isinstance(row, dict)]
        if len(names) != len(rows) or not all(names) or len(set(names)) != len(names):
            raise RuntimeError(f'knowledge canonical bootstrap: invalid or duplicate {label} names')
    return laws_raw.strip(), theories_raw.strip(), manifest


def replace_array_assignment(text: str, name: str, replacement_json: str) -> str:
    start, end = _array_span(text, name)
    return text[:start] + replacement_json + text[end:]


def transform(text: str, laws_json: str, theories_json: str, knowledge_manifest: dict) -> str:
    text = replace_array_assignment(text, 'LAWS', laws_json)
    text = replace_array_assignment(text, 'THEORIES', theories_json)
    text = replace_exact(text, SEO_OLD, SEO_NEW, 'SEO title')
    text = replace_exact(text, FONT_OLD, FONT_NEW, 'system-font-first policy')
    text = replace_exact(text, SUPABASE_SDK_OLD, SUPABASE_SDK_NEW, 'student Supabase SDK removal')
    text = replace_exact(text, INITIAL_APP_OLD, INITIAL_APP_NEW, 'first-paint placeholder')
    text = replace_exact(text, '\ninit();\n', '\nwindow.__SWSI_BOOT_DEFERRED__=true;\n', 'legacy init deferral')
    text = replace_exact(text, MK_GRADE_OLD, MK_GRADE_NEW, 'simulation grading')
    text = replace_exact(text, MK_LABEL_OLD, MK_LABEL_NEW, 'simulation answer label')
    text = replace_exact(text, ROUND_1_OLD, ROUND_1_NEW, 'UIUX round 1')
    text = replace_exact(text, ROUND_2_OLD, ROUND_2_NEW, 'UIUX round 2')

    # MOEX private-use glyphs are font-dependent; normalize them in the built UI.
    text = text.replace('\uE129', '（一）').replace('\uE12A', '（二）').replace('\uE12B', '（三）')

    bootstrap = {
        'version': '2026-08-27.canonical-build.v1',
        'laws': knowledge_manifest['laws'],
        'theories': knowledge_manifest['theories'],
    }
    marker = '<script>window.SWSI_KNOWLEDGE_CANONICAL_BOOTSTRAP=' + json.dumps(bootstrap, ensure_ascii=False, separators=(',', ':')) + ';</script>\n'
    inject = marker + '<script src="monthly_patch.js"></script>\n</body>'
    text = replace_exact(text, '</body>', inject, 'monthly patch injection')
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('index', nargs='?', default='_site/index.html')
    args = ap.parse_args()
    path = Path(args.index)
    text = path.read_text(encoding='utf-8')
    laws_json, theories_json, knowledge_manifest = load_canonical_knowledge()
    patched = transform(text, laws_json, theories_json, knowledge_manifest)
    path.write_text(patched, encoding='utf-8')

    # The current 115-2 auto essay payload contains three MOEX private-use glyphs.
    # Normalize the deployed copy without requiring a second production deploy.
    auto_essay = path.parent / 'auto' / 'essays_auto.json'
    if auto_essay.exists():
        raw = auto_essay.read_text(encoding='utf-8')
        clean = raw.replace('\uE129','（一）').replace('\uE12A','（二）').replace('\uE12B','（三）')
        clean = clean.replace('','（一）').replace('','（二）').replace('','（三）')
        auto_essay.write_text(clean, encoding='utf-8')

    print(f'Applied SWSI monthly front-end build patch: {path}')
    print('Applied canonical knowledge bootstrap: laws=' + str(knowledge_manifest['laws']['count']) + ' theories=' + str(knowledge_manifest['theories']['count']))
    print('Kept verified deferred student boot contract')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
