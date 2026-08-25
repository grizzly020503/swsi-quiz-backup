#!/usr/bin/env python3
"""Apply the SWSI monthly front-end patch to the Netlify build copy of index.html.

The repository keeps the historical monolithic index.html intact. Netlify copies it
into _site, this script applies a small, fail-closed set of exact transformations,
and monthly_patch.js (loaded last) supplies the maintained override layer.
"""
from __future__ import annotations

import argparse
from pathlib import Path

SEO_OLD = '<title>社工師國考題庫</title>'
SEO_NEW = '''<title>社工師國考免費題庫｜SWSI</title>
<meta name="description" content="免費社工師國考學習平台：歷屆試題、解析、錯題複習、模擬考與申論練習，不鎖題、不賣解答。">
<link rel="canonical" href="https://swsi-quiznetlify.netlify.app/">
<meta property="og:title" content="社工師國考免費題庫｜SWSI">
<meta property="og:description" content="免費練社工師國考歷屆試題、錯題複習、模擬考與申論。">
<meta property="og:type" content="website">
<meta property="og:url" content="https://swsi-quiznetlify.netlify.app/">'''

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


def transform(text: str) -> str:
    text = replace_exact(text, SEO_OLD, SEO_NEW, 'SEO title')
    text = replace_exact(text, '\ninit();\n', '\nwindow.__SWSI_BOOT_DEFERRED__=true;\n', 'legacy init deferral')
    text = replace_exact(text, MK_GRADE_OLD, MK_GRADE_NEW, 'simulation grading')
    text = replace_exact(text, MK_LABEL_OLD, MK_LABEL_NEW, 'simulation answer label')
    text = replace_exact(text, ROUND_1_OLD, ROUND_1_NEW, 'UIUX round 1')
    text = replace_exact(text, ROUND_2_OLD, ROUND_2_NEW, 'UIUX round 2')

    # MOEX private-use glyphs are font-dependent; normalize them in the built UI.
    text = text.replace('\uE129', '（一）').replace('\uE12A', '（二）').replace('\uE12B', '（三）')

    inject = '<script src="monthly_patch.js"></script>\n</body>'
    text = replace_exact(text, '</body>', inject, 'monthly patch injection')
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('index', nargs='?', default='_site/index.html')
    args = ap.parse_args()
    path = Path(args.index)
    text = path.read_text(encoding='utf-8')
    patched = transform(text)
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
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
