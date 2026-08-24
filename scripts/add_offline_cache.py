from pathlib import Path

p = Path("index.html")
s = p.read_text(encoding="utf-8")

start = s.find("async function loadAll(){")
end = s.find("/* ---------- 啟動 ---------- */", start)
if start < 0 or end < 0:
    raise SystemExit("Cannot locate loadAll block")

replacement = r"""const OFFLINE_DB_NAME='swsi-quiz-offline';
const OFFLINE_DB_VERSION=1;
const OFFLINE_STORE='cache';
const OFFLINE_KEY='questions';

function openOfflineDB(){
  return new Promise((resolve,reject)=>{
    if(!('indexedDB' in window)){ reject(new Error('此瀏覽器不支援離線題庫')); return; }
    const req=indexedDB.open(OFFLINE_DB_NAME,OFFLINE_DB_VERSION);
    req.onupgradeneeded=()=>{
      const db=req.result;
      if(!db.objectStoreNames.contains(OFFLINE_STORE)) db.createObjectStore(OFFLINE_STORE);
    };
    req.onsuccess=()=>resolve(req.result);
    req.onerror=()=>reject(req.error||new Error('離線資料庫開啟失敗'));
  });
}

async function saveOfflineQuestions(rows){
  try{
    if(!Array.isArray(rows)||!rows.length) return;
    const db=await openOfflineDB();
    await new Promise((resolve,reject)=>{
      const tx=db.transaction(OFFLINE_STORE,'readwrite');
      tx.objectStore(OFFLINE_STORE).put({rows:rows,savedAt:Date.now()},OFFLINE_KEY);
      tx.oncomplete=resolve;
      tx.onerror=()=>reject(tx.error||new Error('離線題庫儲存失敗'));
      tx.onabort=()=>reject(tx.error||new Error('離線題庫儲存中止'));
    });
    db.close();
  }catch(err){
    console.warn('離線題庫備份失敗：',err);
  }
}

async function loadOfflineQuestions(){
  const db=await openOfflineDB();
  const record=await new Promise((resolve,reject)=>{
    const tx=db.transaction(OFFLINE_STORE,'readonly');
    const req=tx.objectStore(OFFLINE_STORE).get(OFFLINE_KEY);
    req.onsuccess=()=>resolve(req.result||null);
    req.onerror=()=>reject(req.error||new Error('離線題庫讀取失敗'));
  });
  db.close();
  if(!record||!Array.isArray(record.rows)||!record.rows.length) throw new Error('這台裝置還沒有離線題庫備份');
  return record;
}

async function loadAll(){
  let from=0; const size=1000; let out=[];
  try{
    while(true){
      const data=await fetchQuestionPage(from,from+size-1,3);
      out=out.concat(data);
      showLoadProgress(out.length,1);
      if(data.length<size) break;
      from+=size;
    }
    ALL=out.map(normalize);
    SUBJECTS=[...new Set(ALL.map(q=>q.subject))].filter(Boolean);
    window._usingOfflineBackup=false;
    saveOfflineQuestions(out);
    return;
  }catch(remoteErr){
    console.warn('遠端題庫載入失敗，嘗試本機離線備援：',remoteErr);
  }

  app.innerHTML=`<div class="empty"><div class="ico">◫</div><h3>正在開啟離線題庫</h3><p>網路或 Supabase 暫時無法使用，改讀這台裝置先前保存的完整題庫。</p></div>`;
  const record=await loadOfflineQuestions();
  ALL=record.rows.map(normalize);
  SUBJECTS=[...new Set(ALL.map(q=>q.subject))].filter(Boolean);
  window._usingOfflineBackup=true;
  window._offlineSavedAt=record.savedAt||0;
}

"""
s = s[:start] + replacement + s[end:]

old = "function renderHome(){\n  const opts="
new = """function renderHome(){
  const offlineNote=window._usingOfflineBackup?`<div style="margin-bottom:14px;padding:10px 13px;border:1px solid var(--line);border-radius:10px;background:#fff;font-size:12px;color:var(--ink-soft)">📦 目前使用這台裝置的離線題庫備援；恢復網路後重新開啟網站即可同步最新題庫。</div>`:'';
  const opts="""
if old in s and "offlineNote=window._usingOfflineBackup" not in s:
    s = s.replace(old, new, 1)

marker = 'app.innerHTML=`\n    <div class="hero">'
section_start = s.find("function renderHome(){")
section_end = s.find("function renderQuiz", section_start)
section = s[section_start:section_end] if section_start >= 0 and section_end >= 0 else ""
if marker in s and '${offlineNote}' not in section:
    s = s.replace(marker, 'app.innerHTML=`\n    ${offlineNote}\n    <div class="hero">', 1)

p.write_text(s, encoding="utf-8")

sw = Path("sw.js")
t = sw.read_text(encoding="utf-8")
if "const VERSION = 'v1';" in t:
    t = t.replace("const VERSION = 'v1';", "const VERSION = 'v2';")
elif "const VERSION = 'v2';" not in t:
    raise SystemExit("Unexpected service worker version")
if "'./essay_guides.js'" not in t:
    t = t.replace("'./index.html',", "'./index.html',\n  './essay_guides.js',")
sw.write_text(t, encoding="utf-8")
