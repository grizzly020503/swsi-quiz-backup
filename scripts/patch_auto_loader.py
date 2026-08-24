#!/usr/bin/env python3
from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'index.html'
s = p.read_text(encoding='utf-8')
marker = '/* ===== MOEX AUTO DATA START ===== */'
if marker in s:
    print('auto loader already installed')
    raise SystemExit(0)

anchor = "const OFFLINE_KEY='questions';"
if anchor not in s:
    raise SystemExit('OFFLINE_KEY anchor not found')

helper = r'''

/* ===== MOEX AUTO DATA START ===== */
const AUTO_ESSAY_CACHE_KEY='swsi_auto_essays_v1';

function canonicalRound(v){
  const s=String(v||'').replace(/\s+/g,'');
  if(s.includes('二')||s.includes('2')) return '2';
  if(s.includes('一')||s.includes('1')) return '1';
  return s;
}

function logicalExamKey(x){
  const n=parseInt(String((x&&x.qno)||''),10);
  return [String((x&&x.subject)||''),String((x&&x.year)||''),canonicalRound(x&&x.round),Number.isFinite(n)?String(n):String((x&&x.qno)||'')].join('|');
}

async function fetchAutoJSON(path){
  try{
    const r=await fetch(path,{cache:'no-store'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    return await r.json();
  }catch(e){
    console.warn('增量題庫暫時無法讀取：',path,e);
    return [];
  }
}

async function loadAutoQuestions(){
  let rows=await fetchAutoJSON('auto/questions_auto.json');
  if(Array.isArray(rows)&&rows.length) return rows;
  // 若剛好斷網，嘗試從先前 IndexedDB 的完整題庫找回自動收錄題。
  try{
    const record=await loadOfflineQuestions();
    rows=(record.rows||[]).filter(x=>x&&x.source_exam_code);
    return Array.isArray(rows)?rows:[];
  }catch(_e){ return []; }
}

function mergeRawQuestions(base,extra){
  // 邏輯鍵以「科目＋年度＋考次＋題號」判斷同一題。
  // 先放 Supabase 母庫，增量檔只補不存在的題；因此已分析過的 Supabase 版本永遠優先。
  const m=new Map();
  (base||[]).forEach(x=>{ if(x) m.set(logicalExamKey(x),x); });
  (extra||[]).forEach(x=>{
    if(!x) return;
    const k=logicalExamKey(x);
    if(!m.has(k)) m.set(k,x);
  });
  return [...m.values()];
}

async function loadAutoEssays(){
  let rows=await fetchAutoJSON('auto/essays_auto.json');
  if(Array.isArray(rows)&&rows.length){
    try{ localStorage.setItem(AUTO_ESSAY_CACHE_KEY,JSON.stringify(rows)); }catch(e){}
  }else{
    try{ rows=JSON.parse(localStorage.getItem(AUTO_ESSAY_CACHE_KEY)||'[]'); }catch(e){ rows=[]; }
  }
  if(!Array.isArray(rows)) rows=[];
  const list=window.ESSAYS||[];
  const seen=new Set(list.map(logicalExamKey));
  let added=0;
  rows.forEach(x=>{
    if(!x) return;
    const k=logicalExamKey(x);
    if(seen.has(k)) return;
    const e=Object.assign({},x);
    e.round = canonicalRound(e.round)==='2' ? '第2次' : canonicalRound(e.round)==='1' ? '第1次' : e.round;
    e.major = e.major || e.subject || '';
    e.topic = e.topic || '官方新題（待考點分析）';
    e.keywords = Array.isArray(e.keywords)?e.keywords:[];
    e.theories = Array.isArray(e.theories)?e.theories:[];
    e.laws = Array.isArray(e.laws)?e.laws:[];
    e.related = Array.isArray(e.related)?e.related:[];
    list.push(e); seen.add(k); added++;
  });
  window._autoEssayCount=added;
}
/* ===== MOEX AUTO DATA END ===== */
'''
s=s.replace(anchor, anchor+helper, 1)

old = """    ALL=out.map(normalize);\n    SUBJECTS=[...new Set(ALL.map(q=>q.subject))].filter(Boolean);\n    window._usingOfflineBackup=false;\n    saveOfflineQuestions(out);"""
new = """    const autoRows=await loadAutoQuestions();\n    out=mergeRawQuestions(out,autoRows);\n    ALL=out.map(normalize);\n    SUBJECTS=[...new Set(ALL.map(q=>q.subject))].filter(Boolean);\n    window._usingOfflineBackup=false;\n    window._autoQuestionCount=Math.max(0,out.length-(out.length-autoRows.length));\n    saveOfflineQuestions(out);"""
if old not in s:
    raise SystemExit('online loadAll block not found')
s=s.replace(old,new,1)

old2 = """    await loadAll();\n    tabbar.style.display='flex';"""
new2 = """    await loadAll();\n    await loadAutoEssays();\n    tabbar.style.display='flex';"""
if old2 not in s:
    raise SystemExit('init loadAll block not found')
s=s.replace(old2,new2,1)

p.write_text(s,encoding='utf-8')
print('installed MOEX auto-data loader')
