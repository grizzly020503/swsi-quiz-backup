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

async function fetchAutoJSON(path){
  try{
    const r=await fetch(path+'?v='+Date.now(),{cache:'no-store'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    return await r.json();
  }catch(e){
    console.warn('增量題庫暫時無法讀取：',path,e);
    return [];
  }
}

async function loadAutoQuestions(){
  const rows=await fetchAutoJSON('auto/questions_auto.json');
  return Array.isArray(rows)?rows:[];
}

function mergeRawQuestions(base,extra){
  const m=new Map();
  (base||[]).forEach(x=>{ if(x&&x.id) m.set(String(x.id),x); });
  (extra||[]).forEach(x=>{ if(x&&x.id) m.set(String(x.id),x); });
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
  const seen=new Set(list.map(x=>String(x.id)));
  rows.forEach(x=>{
    if(x&&x.id&&!seen.has(String(x.id))){ list.push(x); seen.add(String(x.id)); }
  });
  window._autoEssayCount=rows.length;
}
/* ===== MOEX AUTO DATA END ===== */
'''
s=s.replace(anchor, anchor+helper, 1)

old = """    ALL=out.map(normalize);\n    SUBJECTS=[...new Set(ALL.map(q=>q.subject))].filter(Boolean);\n    window._usingOfflineBackup=false;\n    saveOfflineQuestions(out);"""
new = """    const autoRows=await loadAutoQuestions();\n    out=mergeRawQuestions(out,autoRows);\n    ALL=out.map(normalize);\n    SUBJECTS=[...new Set(ALL.map(q=>q.subject))].filter(Boolean);\n    window._usingOfflineBackup=false;\n    window._autoQuestionCount=autoRows.length;\n    saveOfflineQuestions(out);"""
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
