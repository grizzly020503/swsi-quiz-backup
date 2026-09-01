
/* SWSI Monthly Frontend Patch 2026-08-25
   Loaded last by Netlify build-time injection.
   Purpose: CDN manifest/shards, official grading semantics, front-end QA/security fixes.
*/
'use strict';

const SWSI_PATCH_VERSION = '2026-08-25.1';
const SWSI_QUESTION_CDN_BASE = 'https://wandering-wave-4418.c022050333.workers.dev/question-shards';
const SWSI_CORE_SUBJECTS = [
  '社會工作',
  '社會工作直接服務',
  '社會政策與社會立法',
  '人類行為與社會環境',
  '社會工作研究方法'
];
const SWSI_VALID_GRADING_MODES = new Set(['standard','all_credit','any_answer']);
const SWSI_SPECIAL_ANSWER_MARKERS = new Set(['一律給分','送分','全體給分']);
const SWSI_SHARD_INTEGRITY_VERSION = '2026-08-26.sha256.v2';

function swsiText(v){
  return String(v == null ? '' : v);
}
function swsiEsc(v){
  return swsiText(v)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#39;');
}
function swsiEscLines(v){
  return swsiEsc(v).replace(/\r?\n/g,'<br>');
}
function swsiCleanPUA(v){
  return swsiText(v)
    .replace(/\uE129/g,'（一）')
    .replace(/\uE12A/g,'（二）')
    .replace(/\uE12B/g,'（三）');
}
function swsiValidStandardMetadata(item){
  const answer = swsiText(item && item.answer).trim().toUpperCase();
  if(!/^[ABCD]$/.test(answer)) return false;
  const accepted = item && item.accepted_answers;
  if(accepted === undefined || accepted === null) return true;
  if(!Array.isArray(accepted) || accepted.length < 1 || accepted.length > 4) return false;
  const xs = accepted.map(x=>swsiText(x).trim().toUpperCase());
  return xs.every(x=>/^[ABCD]$/.test(x))
    && new Set(xs).size === xs.length
    && xs.includes(answer);
}
function gradingMode(item){
  if(!item) return 'invalid';
  const raw = swsiText(item.grading_mode).trim().toLowerCase();
  if(raw){
    if(!SWSI_VALID_GRADING_MODES.has(raw)) return 'invalid';
    if(raw === 'standard') return swsiValidStandardMetadata(item) ? raw : 'invalid';
    return swsiText(item.answer).trim() === '一律給分'
      && (item.accepted_answers === undefined || item.accepted_answers === null)
      ? raw
      : 'invalid';
  }
  if(SWSI_SPECIAL_ANSWER_MARKERS.has(swsiText(item.answer).trim())) return 'invalid';
  return swsiValidStandardMetadata(item) ? 'standard' : 'invalid';
}
function acceptedAnswers(item){
  const mode = gradingMode(item);
  if(mode === 'all_credit' || mode === 'any_answer'){
    return new Set(['A','B','C','D']);
  }
  const xs = Array.isArray(item && item.accepted_answers)
    ? item.accepted_answers.map(x=>swsiText(x).trim().toUpperCase()).filter(x=>/^[ABCD]$/.test(x))
    : [];
  if(xs.length) return new Set(xs);
  const a = swsiText(item && item.answer).trim().toUpperCase();
  return /^[ABCD]$/.test(a) ? new Set([a]) : new Set();
}
function isCorrectAnswer(item,picked){
  const mode = gradingMode(item);
  const p = picked == null ? null : swsiText(picked).trim().toUpperCase();
  if(mode === 'invalid') return false;
  if(mode === 'all_credit') return true;
  if(mode === 'any_answer') return !!p && /^[ABCD]$/.test(p);
  return !!p && acceptedAnswers(item).has(p);
}
function answerLabel(item){
  const mode = gradingMode(item);
  if(mode === 'invalid') return '官方給分資料不完整，這題暫停判分';
  if(mode === 'all_credit') return '官方一律給分（未作答也得分）';
  if(mode === 'any_answer') return 'A、B、C、D 任一作答皆給分；未作答不給分';
  const xs = [...acceptedAnswers(item)];
  if(xs.length > 1) return '官方可接受答案：' + xs.join('、');
  return '正確答案：' + (xs[0] || '—');
}
window.gradingMode = gradingMode;
window.acceptedAnswers = acceptedAnswers;
window.isCorrectAnswer = isCorrectAnswer;
window.answerLabel = answerLabel;
window.swsiEsc = swsiEsc;

(function(){
  // Make the site's legacy esc() use the same context-safe text encoder.
  try { esc = swsiEsc; } catch(_e) { window.esc = swsiEsc; }

  const QB = window.SWSI_QB = {
    manifest: null,
    loadedFiles: new Set(),
    loading: new Map(),
    allComplete: false,
    usingOffline: false,
    manifestSource: '',
    error: null,
    questionOwners: new Map()
  };

  function resetAllDerivedCaches(){
    try{ window._kpF = null; window._kpFmax = 1; }catch(_e){}
    try{ window._tmc = {}; window._cmc = {}; window._maxY = null; }catch(_e){}
  }

  function showLoading(title, detail){
    if(typeof app === 'undefined' || !app) return;
    app.innerHTML = '<div class="empty"><div class="spinner"></div><h3 style="margin-top:16px">'
      + swsiEsc(title || '正在準備題庫') + '</h3><p>' + swsiEsc(detail || '') + '</p></div>';
  }

  function showLoadError(err){
    if(typeof app === 'undefined' || !app) return;
    const msg = swsiEsc(err && err.message ? err.message : '暫時無法載入題庫');
    app.innerHTML = '<div class="empty"><div class="ico">⚠</div><h3>暫時無法載入題庫</h3><p>'
      + msg + '</p><button class="btn" style="max-width:220px;margin:20px auto 0" onclick="retryLoad()">重新連線</button></div>';
  }

  async function idbGet(key){
    const db = await openOfflineDB();
    try{
      return await new Promise((resolve,reject)=>{
        const tx = db.transaction(OFFLINE_STORE,'readonly');
        const req = tx.objectStore(OFFLINE_STORE).get(key);
        req.onsuccess = ()=>resolve(req.result || null);
        req.onerror = ()=>reject(req.error || new Error('離線題庫讀取失敗'));
      });
    }finally{
      try{ db.close(); }catch(_e){}
    }
  }

  async function idbPut(key, value){
    const db = await openOfflineDB();
    try{
      await new Promise((resolve,reject)=>{
        const tx = db.transaction(OFFLINE_STORE,'readwrite');
        tx.objectStore(OFFLINE_STORE).put(value,key);
        tx.oncomplete = resolve;
        tx.onerror = ()=>reject(tx.error || new Error('離線題庫儲存失敗'));
        tx.onabort = ()=>reject(tx.error || new Error('離線題庫儲存中止'));
      });
    }finally{
      try{ db.close(); }catch(_e){}
    }
  }

  function validateManifest(m){
    if(!m || m.schema_version !== 1 || !Array.isArray(m.shards)) throw new Error('題庫目錄格式不正確');
    if(Number(m.shard_count) !== m.shards.length) throw new Error('題庫目錄 shard 數量不一致');
    if(Number(m.total_questions) < 1) throw new Error('題庫目錄總題數不正確');
    const files = new Set(), sessions = new Set();
    let total = 0;
    for(const meta of m.shards){
      const year = swsiText(meta && meta.year);
      const round = canonicalRound(meta && meta.round);
      if(!meta || !/^\d{3}$/.test(year) || !/^[12]$/.test(round) || swsiText(meta.file) !== year+'-'+round+'.json') throw new Error('題庫目錄考次資料不完整');
      if(Number(meta.question_count) !== 200) throw new Error('題庫目錄存在不完整考次');
      if(!/^[a-f0-9]{64}$/i.test(swsiText(meta.sha256))) throw new Error('題庫目錄缺少完整雜湊');
      if(files.has(meta.file)) throw new Error('題庫目錄出現重複 shard');
      const session = year+'-'+round;
      if(sessions.has(session)) throw new Error('題庫目錄出現重複考次');
      files.add(meta.file);
      sessions.add(session);
      total += Number(meta.question_count);
    }
    if(total !== Number(m.total_questions)) throw new Error('題庫目錄總題數與 shards 不一致');
    return m;
  }

  async function fetchJSON(url, opts){
    const ctrl = new AbortController();
    const timer = setTimeout(()=>ctrl.abort(), (opts && opts.timeout) || 12000);
    try{
      const r = await fetch(url,{cache:(opts && opts.cache)||'no-store',signal:ctrl.signal,headers:(opts&&opts.headers)||undefined});
      if(!r.ok) throw new Error('HTTP ' + r.status);
      return await r.json();
    }finally{
      clearTimeout(timer);
    }
  }

  async function sha256Hex(buffer){
    if(!(window.crypto && crypto.subtle && crypto.subtle.digest)) throw new Error('此瀏覽器無法驗證題庫完整性');
    const digest = await crypto.subtle.digest('SHA-256',buffer);
    return Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,'0')).join('');
  }

  async function fetchVerifiedShard(meta){
    const expected = swsiText(meta && meta.sha256).trim().toLowerCase();
    if(!/^[a-f0-9]{64}$/.test(expected)) throw new Error('題庫目錄缺少有效 SHA-256');
    const ctrl = new AbortController();
    const timer = setTimeout(()=>ctrl.abort(),15000);
    try{
      const url = SWSI_QUESTION_CDN_BASE + '/' + encodeURIComponent(meta.file);
      const r = await fetch(url,{cache:'no-store',signal:ctrl.signal});
      if(!r.ok) throw new Error('HTTP ' + r.status);
      const rawBytes = await r.arrayBuffer();
      const actual = await sha256Hex(rawBytes);
      if(actual !== expected){
        console.error('[SWSI] shard SHA-256 mismatch',{file:meta.file,expected,actual});
        throw new Error('題庫版本完整性驗證失敗，已停止載入這份資料');
      }
      const text = new TextDecoder('utf-8',{fatal:true}).decode(rawBytes);
      return {payload:JSON.parse(text),rawBytes,sha256:actual};
    }finally{
      clearTimeout(timer);
    }
  }

  function cachedBytes(rec){
    if(!rec) return null;
    if(rec.rawBytes instanceof ArrayBuffer) return rec.rawBytes;
    if(ArrayBuffer.isView(rec.rawBytes)){
      return rec.rawBytes.buffer.slice(rec.rawBytes.byteOffset,rec.rawBytes.byteOffset+rec.rawBytes.byteLength);
    }
    return null;
  }

  async function readVerifiedCachedShard(rec, meta){
    const expected = swsiText(meta && meta.sha256).trim().toLowerCase();
    if(!rec || rec.integrityVersion !== SWSI_SHARD_INTEGRITY_VERSION || swsiText(rec.sha256).toLowerCase() !== expected) return null;
    const rawBytes = cachedBytes(rec);
    if(!rawBytes || await sha256Hex(rawBytes) !== expected) return null;
    const text = new TextDecoder('utf-8',{fatal:true}).decode(rawBytes);
    return validateShard(JSON.parse(text),meta);
  }
  window.swsiShardIntegrityVersion = SWSI_SHARD_INTEGRITY_VERSION;

  async function loadQuestionManifest(){
    if(QB.manifest) return QB.manifest;
    let networkErr = null;
    try{
      const m = validateManifest(await fetchJSON(SWSI_QUESTION_CDN_BASE + '/manifest.json',{timeout:10000}));
      QB.manifest = m;
      QB.manifestSource = 'cloudflare';
      QB.usingOffline = false;
      idbPut('question-manifest',{manifest:m,savedAt:Date.now()}).catch(()=>{});
      return m;
    }catch(err){
      networkErr = err;
      console.warn('Cloudflare manifest unavailable, trying IndexedDB.', err);
    }
    try{
      const rec = await idbGet('question-manifest');
      const m = validateManifest(rec && rec.manifest);
      QB.manifest = m;
      QB.manifestSource = 'indexeddb';
      QB.usingOffline = true;
      return m;
    }catch(_offlineErr){
      throw networkErr || new Error('題庫目錄暫時無法取得');
    }
  }
  window.loadQuestionManifest = loadQuestionManifest;

  function questionTotal(){
    return QB.manifest && Number(QB.manifest.total_questions) > 0 ? Number(QB.manifest.total_questions) : ALL.length;
  }
  window.questionTotal = questionTotal;

  function manifestYears(){
    if(!QB.manifest) return [];
    return [...new Set(QB.manifest.shards.map(x=>parseInt(x.year,10)).filter(Number.isFinite))].sort((a,b)=>b-a);
  }

  // normalize must retain official grading metadata from Supabase/CDN.
  const legacyNormalize = normalize;
  normalize = function(r){
    const q = legacyNormalize(r);
    const accepted = Array.isArray(r && r.accepted_answers)
      ? r.accepted_answers.map(x=>swsiText(x).trim().toUpperCase()).filter(x=>/^[ABCD]$/.test(x))
      : null;
    q.accepted_answers = accepted && accepted.length ? accepted : null;
    q.grading_mode = gradingMode(r);
    q.source_exam_code = (r && r.source_exam_code) || '';
    q.q = swsiCleanPUA(q.q);
    for(const k of ['A','B','C','D']) q.options[k] = swsiCleanPUA(q.options[k]);
    if(q.exp){
      for(const k of ['why','others','trap','raw']) if(q.exp[k]) q.exp[k] = swsiCleanPUA(q.exp[k]);
    }
    q.mnemonic = swsiCleanPUA(q.mnemonic);
    q.extension = swsiCleanPUA(q.extension);
    q.law = swsiCleanPUA(q.law);
    q.mistake = swsiCleanPUA(q.mistake);
    return q;
  };

  // Clean the current auto-essay payload after it is merged; future parser versions also normalize at source.
  const legacyLoadAutoEssays = loadAutoEssays;
  loadAutoEssays = async function(){
    await legacyLoadAutoEssays();
    try{ (window.ESSAYS||[]).forEach(e=>{ if(e&&e.q) e.q=swsiCleanPUA(e.q); }); }catch(_e){}
  };

  function validateShard(payload, meta){
    if(!payload || payload.schema_version !== 1 || !Array.isArray(payload.questions)) throw new Error('題庫 shard 格式不正確');
    if(swsiText(payload.year) !== swsiText(meta.year) || canonicalRound(payload.round) !== canonicalRound(meta.round)) throw new Error('題庫 shard 考次不符');
    if(Number(payload.question_count) !== 200 || payload.questions.length !== 200) throw new Error('題庫 shard 題數不完整');
    const ids = new Set();
    for(const row of payload.questions){
      if(!row || !row.id || ids.has(row.id)) throw new Error('題庫 shard ID 缺漏或重複');
      ids.add(row.id);
      if(swsiText(row.year) !== swsiText(meta.year) || canonicalRound(row.round) !== canonicalRound(meta.round)) throw new Error('題庫 shard 題目考次不符');
      const mode = gradingMode(row);
      if(!SWSI_VALID_GRADING_MODES.has(mode)) throw new Error('題庫 shard grading_mode 不合法');
    }
    return payload;
  }

  function mergeRowsIntoAll(rows, file){
    const map = new Map(ALL.map(q=>[q.id,q]));
    const normalized = rows.map(normalize);
    for(const q of normalized){
      const owner = QB.questionOwners.get(q.id);
      if(owner && owner !== file) throw new Error('題庫 shard 出現跨檔 ID 重複：' + q.id);
      if(map.has(q.id) && owner !== file) throw new Error('題庫載入遇到來源不明的重複 ID：' + q.id);
    }
    for(const q of normalized){
      map.set(q.id,q);
      QB.questionOwners.set(q.id,file);
    }
    ALL = [...map.values()];
    SUBJECTS = SWSI_CORE_SUBJECTS.slice();
    if(file) QB.loadedFiles.add(file);
    resetAllDerivedCaches();
  }

  async function fetchSupabaseExamSession(meta){
    const year = swsiText(meta.year);
    const round = swsiText(meta.round);
    if(sb && typeof sb.from === 'function'){
      const {data,error} = await sb.from('questions').select('*').eq('year',year).eq('round',round).order('subject',{ascending:true}).order('qno',{ascending:true});
      if(error) throw error;
      if(!Array.isArray(data) || data.length !== 200) throw new Error('Supabase scoped fallback 題數不完整');
      return {schema_version:1,year,round,question_count:200,questions:data};
    }
    const url = CONFIG.url.replace(/\/$/,'') + '/rest/v1/questions?select=*&year=eq.'
      + encodeURIComponent(year) + '&round=eq.' + encodeURIComponent(round) + '&limit=250';
    const r = await fetch(url,{headers:{apikey:CONFIG.key,Authorization:'Bearer '+CONFIG.key,Accept:'application/json'},cache:'no-store'});
    if(!r.ok) throw new Error('Supabase scoped fallback HTTP '+r.status);
    const data = await r.json();
    if(!Array.isArray(data) || data.length !== 200) throw new Error('Supabase scoped fallback 題數不完整');
    return {schema_version:1,year,round,question_count:200,questions:data};
  }

  async function loadQuestionShard(meta){
    if(!meta || !meta.file) throw new Error('缺少題庫 shard metadata');
    if(QB.loadedFiles.has(meta.file)) return;
    if(QB.loading.has(meta.file)) return QB.loading.get(meta.file);

    const p = (async()=>{
      let payload = null, networkErr = null;
      try{
        const verified = await fetchVerifiedShard(meta);
        payload = validateShard(verified.payload,meta);
        idbPut('question-shard:'+meta.file,{
          rawBytes:verified.rawBytes,
          sha256:verified.sha256,
          integrityVersion:SWSI_SHARD_INTEGRITY_VERSION,
          savedAt:Date.now()
        }).catch(()=>{});
        QB.usingOffline = false;
      }catch(err){
        networkErr = err;
        console.warn('Cloudflare shard unavailable:', meta.file, err);
      }
      if(!payload){
        try{
          const rec = await idbGet('question-shard:'+meta.file);
          payload = await readVerifiedCachedShard(rec,meta);
          if(payload){
            QB.usingOffline = true;
          }
        }catch(err){
          console.warn('IndexedDB shard unavailable:', meta.file, err);
        }
      }
      if(!payload){
        try{
          payload = validateShard(await fetchSupabaseExamSession(meta),meta);
        }catch(err){
          console.warn('Supabase scoped fallback unavailable:', meta.file, err);
          throw networkErr || err || new Error('無法載入 '+meta.file);
        }
      }
      mergeRowsIntoAll(payload.questions,meta.file);
    })().finally(()=>QB.loading.delete(meta.file));
    QB.loading.set(meta.file,p);
    return p;
  }
  window.loadQuestionShard = loadQuestionShard;

  function assertCompleteBank(){
    if(!QB.manifest) throw new Error('題庫目錄尚未載入');
    const expectedFiles = new Set(QB.manifest.shards.map(x=>x.file));
    if(QB.loadedFiles.size !== expectedFiles.size || [...expectedFiles].some(file=>!QB.loadedFiles.has(file))) throw new Error('題庫 shard 尚未完整載入');
    const ids = new Set(ALL.map(q=>q && q.id));
    const expectedTotal = Number(QB.manifest.total_questions);
    const hasMissingId = ALL.some(q=>!q || !swsiText(q.id).trim());
    if(hasMissingId || ids.size !== ALL.length || ALL.length !== expectedTotal || QB.questionOwners.size !== expectedTotal){
      throw new Error('完整題庫總量或跨 shard ID 驗證失敗');
    }
    QB.allComplete = true;
    return true;
  }
  window.swsiAssertCompleteQuestionBank = assertCompleteBank;

  async function ensureShardMetasLoaded(metas){
    const xs = (metas || []).filter(Boolean);
    if(!xs.length) return;
    await Promise.all(xs.map(loadQuestionShard));
    if(QB.manifest && QB.loadedFiles.size === QB.manifest.shards.length) assertCompleteBank();
  }
  window.ensureShardMetasLoaded = ensureShardMetasLoaded;

  async function ensureAllQuestionsLoaded(){
    const m = await loadQuestionManifest();
    showLoading('正在準備完整題庫','第一次開啟全庫功能時會下載已發布的歷屆考次；之後會使用快取。');
    await ensureShardMetasLoaded(m.shards);
    assertCompleteBank();
    // Preserve legacy full-cache compatibility after a complete load.
    try{
      const raw = ALL.map(q=>({
        id:q.id,subject:q.subject,year:q.year,round:q.round,qno:q.qno,major:q.major,topic:q.topic,keywords:q.keywords,
        question:q.q,opt_a:q.options.A,opt_b:q.options.B,opt_c:q.options.C,opt_d:q.options.D,answer:q.answer,
        accepted_answers:q.accepted_answers,grading_mode:q.grading_mode,exp_why:q.exp&&q.exp.why,exp_others:q.exp&&q.exp.others,
        exp_trap:q.exp&&q.exp.trap,exp_raw:q.exp&&q.exp.raw,mnemonic:q.mnemonic,extension:q.extension,law:q.law,mistake:q.mistake,
        legal_status:q.legal_status,legal_checked_at:q.legal_checked_at,legal_note:q.legal_note,legal_source_url:q.legal_source_url,
        source_exam_code:q.source_exam_code
      }));
      saveOfflineQuestions(raw);
    }catch(_e){}
  }
  window.ensureAllQuestionsLoaded = ensureAllQuestionsLoaded;

  function shardMetasForHomeScope(){
    if(!QB.manifest) return [];
    const shards = QB.manifest.shards.slice();
    const years = manifestYears();
    const newest = years[0] || 0;
    if(homeQuizScope === 'specific'){
      return shards.filter(m=>{
        if(swsiText(m.year) !== swsiText(homeQuizYear)) return false;
        return homeQuizRound === 'all' || canonicalRound(m.round) === canonicalRound(homeQuizRound);
      });
    }
    let minYear = -Infinity;
    if(homeQuizScope === 'recent3') minYear = newest - 2;
    else if(homeQuizScope === 'recent5') minYear = newest - 4;
    else if(homeQuizScope === 'smart') minYear = newest - 9;
    else if(homeQuizScope === 'all') return shards;
    return shards.filter(m=>(parseInt(m.year,10)||0) >= minYear);
  }
  window.shardMetasForHomeScope = shardMetasForHomeScope;

  const legacyLoadAll = loadAll;
  loadAll = async function(){
    try{
      showLoading('正在讀取題庫目錄','首頁先載入目錄，需要刷題時才下載對應考次。');
      await loadQuestionManifest();
      if(QB.loadedFiles.size === 0){
        ALL = [];
        QB.questionOwners.clear();
      }
      SUBJECTS = SWSI_CORE_SUBJECTS.slice();
      QB.allComplete = QB.loadedFiles.size === QB.manifest.shards.length ? assertCompleteBank() : false;
      window._usingOfflineBackup = QB.usingOffline;
      return;
    }catch(err){
      console.warn('Manifest-first 啟動失敗，退回舊完整題庫備援。',err);
      await legacyLoadAll();
      QB.allComplete = true;
      QB.usingOffline = !!window._usingOfflineBackup;
    }
  };

  // Manifest replaces ALL as catalog source on the home screen.
  examYears = function(){
    const ys = manifestYears();
    if(ys.length) return ys;
    return [...new Set(ALL.map(q=>parseInt(q.year,10)).filter(Number.isFinite))].sort((a,b)=>b-a);
  };
  maxExamYear = function(){
    const ys = examYears();
    return ys[0] || 115;
  };
  setHomeQuizRound = function(v){
    const x = swsiText(v || 'all');
    homeQuizRound = x === 'all' ? 'all' : canonicalRound(x);
    render();
  };

  // Partial-bank safe review summary: don't delete old review IDs merely because their shard isn't loaded yet.
  reviewSummary = function(){
    const st = bootstrapReviewState(), now = Date.now();
    const exists = QB.allComplete ? new Set(ALL.filter(q=>!lawConfirmedChanged(q)).map(q=>q.id)) : null;
    const activeIds=[], dueIds=[], maintenanceDueIds=[]; let masteredCount=0, nextDueAt=0;
    Object.values(st.items).forEach(r=>{
      if(!r || !r.id || (exists && !exists.has(r.id))) return;
      const due = Number(r.dueAt || 0);
      if(r.mastered){
        masteredCount++;
        if(!r.maintenanceDone){
          if(!due || due<=now){ dueIds.push(r.id); maintenanceDueIds.push(r.id); }
          else if(!nextDueAt || due<nextDueAt) nextDueAt=due;
        }
        return;
      }
      activeIds.push(r.id);
      if(!due || due<=now) dueIds.push(r.id);
      else if(!nextDueAt || due<nextDueAt) nextDueAt=due;
    });
    return {state:st,activeIds,dueIds,maintenanceDueIds,activeCount:activeIds.length,dueCount:dueIds.length,maintenanceDueCount:maintenanceDueIds.length,masteredCount,nextDueAt};
  };

  startFocusedQuiz = async function(){
    try{
      showLoading('正在準備這組題目',homeQuizScope==='specific'?(homeQuizYear+' 年 '+(homeQuizRound==='all'?'全部考次':(homeQuizRound==='1'?'第一次':'第二次'))):'只載入這個範圍需要的歷屆考次。');
      await ensureShardMetasLoaded(shardMetasForHomeScope());
      const pool=ALL.filter(focusedQuizFilter);
      if(!pool.length){ alert('這個條件目前沒有題目，換個範圍試試。'); render(); return; }
      const n=Math.min(Math.max(parseInt(homeQuizCount,10)||20,1),100,pool.length);
      startQuiz(function(q){return pool.includes(q);},n);
    }catch(err){ showLoadError(err); }
  };

  startDueReview = async function(){
    try{
      if(!QB.allComplete) await ensureAllQuestionsLoaded();
      const rv=reviewSummary();
      if(!rv.dueIds.length){alert('今天沒有到期題。');return;}
      const due=new Set(rv.dueIds);
      startQuiz(function(q){return due.has(q.id);},rv.dueIds.length);
    }catch(err){showLoadError(err);}
  };

  retryLoad=function(){ location.reload(); };

  const legacyGo = go;
  go = function(v){
    if(['search','topics','review','progress'].includes(v) && !QB.allComplete){
      showLoading('正在準備完整題庫','這個功能需要跨年度資料，第一次可能需要幾秒。');
      ensureAllQuestionsLoaded().then(()=>legacyGo(v)).catch(showLoadError);
      return;
    }
    legacyGo(v);
  };

  if(window.MK && typeof window.MK.open === 'function'){
    const oldOpen = window.MK.open.bind(window.MK);
    window.MK.open = async function(){
      try{
        if(!QB.allComplete) await ensureAllQuestionsLoaded();
        oldOpen();
      }catch(err){ showLoadError(err); }
    };
  }

  // ---------- Secure home ----------
  renderHome = function(){
    const rv = reviewSummary();
    const years = examYears();
    if(!homeQuizYear && years.length) homeQuizYear = String(years[0]);
    homeQuizRound = homeQuizRound === 'all' ? 'all' : canonicalRound(homeQuizRound);
    const newest = years[0] || '';
    const offlineNote = QB.usingOffline || window._usingOfflineBackup
      ? '<div style="margin-bottom:12px;padding:10px 13px;border:1px solid var(--line);border-radius:12px;background:#fff;font-size:12px;color:var(--ink-soft)">📦 目前使用這台裝置已快取的題庫資料；恢復網路後可同步其他考次與最新內容。</div>'
      : '';
    const subjOpts = ['全部科目'].concat(SWSI_CORE_SUBJECTS).map(x=>'<option value="'+swsiEsc(x)+'" '+(x===subjFilter?'selected':'')+'>'+swsiEsc(x)+'</option>').join('');
    const yearOpts = years.map(y=>'<option value="'+y+'" '+(String(y)===String(homeQuizYear)?'selected':'')+'>'+y+' 年</option>').join('');
    const specific = homeQuizScope === 'specific';
    const reviewSub = rv.dueCount ? ('今天 '+rv.dueCount+' 題到期') : (rv.nextDueAt ? ('下一批 '+reviewDueLabel(rv.nextDueAt)) : '目前沒有待複習題');
    const scopeHint = homeQuizScope==='smart'?'最近 10 年為主，近 3 年與高頻考點優先。':homeQuizScope==='specific'?'只刷你指定的年度／考次。':homeQuizScope==='all'?'包含所有歷史題目。':'只從較新的歷屆題目抽題。';

    app.innerHTML = offlineNote+
      '<div class="ux-home-intro">'+
        '<div class="eyebrow">免費社工師國考學習平台</div><h1>今天要練什麼？</h1>'+
        '<p>歷屆試題、解析、錯題複習與申論練習，不鎖題、不賣解答。</p>'+
        '<div class="ux-home-meta"><span>5 科</span><span>'+questionTotal()+' 題</span>'+(newest?'<span>'+newest+' 最新</span>':'')+'</div>'+
      '</div>'+
      '<div class="ux-main-card primary">'+
        '<div class="ux-card-top"><div><div class="ux-card-title">📝 刷選擇題</div><div class="ux-card-sub">智慧推薦 20 題，或自己指定年份／考次。</div></div></div>'+
        '<div class="ux-actions"><button class="ux-btn-main" onclick="startQuickSmartV1()">智慧刷 20 題</button><button class="ux-btn-soft" onclick="toggleHomeQuiz()">'+(homeQuizOpen?'收起設定':'自訂範圍')+'</button></div>'+
      '</div>'+
      (homeQuizOpen?('<div class="ux-custom">'+
        '<div class="ux-custom-label">刷題範圍</div><select class="subj" aria-label="刷題範圍" onchange="setHomeQuizScope(this.value)" style="margin-bottom:9px">'+
          '<option value="smart" '+(homeQuizScope==='smart'?'selected':'')+'>智慧推薦</option><option value="recent3" '+(homeQuizScope==='recent3'?'selected':'')+'>近 3 年</option><option value="recent5" '+(homeQuizScope==='recent5'?'selected':'')+'>近 5 年</option><option value="specific" '+(homeQuizScope==='specific'?'selected':'')+'>指定歷屆</option><option value="all" '+(homeQuizScope==='all'?'selected':'')+'>全部題庫（含歷史題）</option></select>'+
        (specific?('<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><select class="subj" aria-label="考試年度" onchange="setHomeQuizYear(this.value)" style="margin-bottom:9px">'+yearOpts+'</select><select class="subj" aria-label="考試考次" onchange="setHomeQuizRound(this.value)" style="margin-bottom:9px"><option value="all" '+(homeQuizRound==='all'?'selected':'')+'>全部考次</option><option value="1" '+(homeQuizRound==='1'?'selected':'')+'>第一次</option><option value="2" '+(homeQuizRound==='2'?'selected':'')+'>第二次</option></select></div>'):'')+
        '<div class="ux-custom-label">科目</div><select class="subj" aria-label="科目" onchange="subjFilter=this.value;render()" style="margin-bottom:9px">'+subjOpts+'</select>'+
        '<div class="ux-custom-label">題數</div><select class="subj" aria-label="題數" onchange="setHomeQuizCount(this.value)" style="margin-bottom:9px"><option value="10" '+(homeQuizCount===10?'selected':'')+'>10 題</option><option value="20" '+(homeQuizCount===20?'selected':'')+'>20 題</option><option value="40" '+(homeQuizCount===40?'selected':'')+'>40 題</option></select>'+
        '<div class="ux-custom-hint">'+swsiEsc(scopeHint)+'</div><button class="ux-btn-main" style="width:100%;margin-top:10px" onclick="startFocusedQuiz()">開始這組題目</button></div>'):'')+
      '<div class="ux-link-card '+(rv.dueCount?'hot':'')+'" onclick="'+(rv.dueCount?'startDueReview()':"go('review')")+'"><div class="left"><div class="title">🧠 今日複習</div><div class="sub">'+swsiEsc(reviewSub)+'</div></div>'+(rv.dueCount?'<span class="ux-badge">'+rv.dueCount+' 題</span>':'<span class="arrow">›</span>')+'</div>'+
      '<div class="ux-link-card" onclick="go(\'essay\')"><div class="left"><div class="title">✍️ 申論練習</div><div class="sub">歷屆申論、時事題材與 AI 作答回饋</div></div><span class="arrow">›</span></div>'+
      '<div class="ux-tools"><button onclick="MK.open()">計時模擬考</button><button onclick="go(\'topics\')">學習工具</button></div>';
    if(typeof relabelTabs === 'function') try{ relabelTabs(); }catch(_e){}
  };

  // ---------- Secure question rendering + official grading ----------
  renderQuiz = function(){
    if(!queue.length){
      app.innerHTML='<div class="empty"><div class="ico">∅</div><h3>沒有符合的題目</h3><button class="btn" style="max-width:200px;margin:18px auto 0" onclick="go(\'home\')">回首頁</button></div>';
      return;
    }
    const item=queue[idx], pct=Math.round((idx/queue.length)*100), mode=gradingMode(item), accepted=acceptedAnswers(item);
    let optHTML='';
    for(const k of ['A','B','C','D']){
      if(!item.options[k]) continue;
      let cls='opt', marker='';
      const selectedNow = k===selected;
      const standardAccepted = mode==='standard' && accepted.has(k);
      if(answered){
        if(standardAccepted || ((mode==='all_credit'||mode==='any_answer') && selectedNow)) cls+=' correct';
        else if(selectedNow) cls+=' wrong';
      }else if(selectedNow) cls+=' sel';
      if(answered && (standardAccepted || ((mode==='all_credit'||mode==='any_answer') && selectedNow))){
        marker='<span class="mk"><b class="ck ok">✓</b>'+(mode==='standard'?'官方答案':'給分')+'</span>';
      }else if(answered && selectedNow){
        marker='<span class="mk"><b class="ck no">✗</b>你選的</span>';
      }
      optHTML += '<button type="button" class="'+cls+'" role="radio" aria-checked="'+(selectedNow?'true':'false')+'" '+(answered?'disabled':'')+
        ' onclick="pick(\''+k+'\')" style="width:100%;text-align:left;font-family:inherit;color:inherit"><span class="lab">'+k+'</span><span>'+
        swsiEscLines(item.options[k])+'</span>'+marker+'</button>';
    }

    let expHTML='';
    if(answered){
      const wrong=!isCorrectAnswer(item,selected);
      let body='';
      if(mode==='all_credit') body+='<div class="pending" style="background:var(--correct-bg);color:var(--pine)"><b>⚖ 官方一律給分：</b>這題即使未作答也計分；解析僅供理解題意。</div>';
      else if(mode==='any_answer') body+='<div class="pending" style="background:var(--correct-bg);color:var(--pine)"><b>⚖ 官方特殊給分：</b>A～D 任一作答皆給分，但未作答不給分。</div>';
      if(item.exp&&(item.exp.why||item.exp.others||item.exp.trap)){
        if(item.exp.why) body+='<div class="exp-sec"><h4><span class="dot d-green"></span>為什麼對</h4><p>'+swsiEscLines(item.exp.why)+'</p></div>';
        if(item.exp.others) body+='<div class="exp-sec"><h4><span class="dot d-red"></span>其他選項為什麼錯</h4><p>'+swsiEscLines(item.exp.others)+'</p></div>';
        if(item.exp.trap) body+='<div class="exp-sec"><h4><span class="dot d-gold"></span>考場陷阱</h4><p>'+swsiEscLines(item.exp.trap)+'</p></div>';
      }else if(item.exp&&item.exp.raw){
        body+='<div class="exp-sec"><p>'+swsiEscLines(item.exp.raw)+'</p></div>';
      }else{
        body+='<div class="pending">此題<b>解析生成中</b>。'+swsiEsc(answerLabel(item))+'，先記下來，詳解之後補上。</div>';
      }
      let extra='';
      if(item.mnemonic) extra+='<div class="extra"><b>記憶法：</b>'+swsiEscLines(item.mnemonic)+'</div>';
      if(item.law) extra+='<div class="extra"><b>法源：</b>'+swsiEscLines(item.law)+'</div>';
      if(mode==='standard' && accepted.size>1) extra='<div class="extra"><b>'+swsiEsc(answerLabel(item))+'</b></div>'+extra;
      expHTML='<div class="exp"><div class="topic">考點：<b>'+swsiEsc(item.topic||item.major)+'</b></div>'+body+extra+
        (wrong&&item.mistake?'<div class="mistake">這題錯因：'+swsiEsc(item.mistake)+'</div>':'')+
        '<button class="btn" onclick="next()">'+(idx+1<queue.length?'下一題 →':'看結果 →')+'</button></div>';
    }

    app.innerHTML='<button class="quit" onclick="go(\'home\')">← 結束這次練習</button>'+
      '<div class="pstrip"><div class="pbar"><i style="width:'+pct+'%"></i></div><span class="pcount">'+(idx+1)+' / '+queue.length+'</span></div>'+
      '<div class="qcard"><div class="qmeta"><span class="tag subj">'+swsiEsc(item.subject)+'</span><span class="tag year">'+swsiEsc(item.year)+'年 '+swsiEsc(item.round)+'</span>'+
      (yearTier(item)==='高'?'<span class="tag year" style="background:var(--correct-bg);color:var(--pine)">近年</span>':'')+
      ((maxExamYear()-(parseInt(item.year)||0)>9)?'<span class="tag year" style="background:#ECE6D6;color:var(--ink-soft)">歷史參考</span>':'')+
      legalBadge(item)+'</div>'+legalNotice(item)+'<div class="qtext">'+swsiEscLines(item.q)+'</div>'+optHTML+
      (!answered?'<button class="btn" '+(selected?'':'disabled')+' onclick="submit()">送出答案</button>':'')+expHTML+'</div>';
  };

  submit = function(){
    if(!selected) return;
    answered=true;
    const item=queue[idx], correct=isCorrectAnswer(item,selected);
    sessionStats.done++;
    if(correct) sessionStats.correct++;
    else sessionStats.wrongTopics.push(item.topic||item.major);
    record(item,selected,correct);
    render();
  };

  renderSummary = function(){
    const rate=sessionStats.done?Math.round(sessionStats.correct/sessionStats.done*100):0;
    const weak=[...new Set(sessionStats.wrongTopics)].filter(Boolean);
    const weakHTML=weak.length
      ? '<div class="weak"><h4>⚠ 這次的弱點考點</h4>'+weak.map(t=>'<div class="item">· '+swsiEsc(t)+'</div>').join('')+'</div>'
      : '<div class="weak" style="background:var(--correct-bg)"><h4 style="color:var(--correct)">✓ 這次全對</h4><div class="item">維持下去，下次換個考點。</div></div>';
    app.innerHTML='<div class="sumcard"><div style="font-size:13px;color:var(--ink-soft);margin-bottom:6px">本次正確率</div>'+
      '<div class="big">'+rate+'%</div><div class="statrow"><div class="stat"><div class="v">'+sessionStats.done+'</div><div class="k">本次刷題</div></div>'+
      '<div class="stat"><div class="v" style="color:var(--correct)">'+sessionStats.correct+'</div><div class="k">答對</div></div>'+
      '<div class="stat"><div class="v" style="color:var(--wrong)">'+(sessionStats.done-sessionStats.correct)+'</div><div class="k">答錯</div></div></div>'+
      weakHTML+'<button class="btn" style="margin-top:20px" onclick="go(\'home\')">再來一輪</button>'+
      (weak.length?'<button class="btn ghost" style="margin-top:10px" onclick="go(\'review\')">複習錯題</button>':'')+'</div>';
  };

  // ---------- Topics: escape DB-derived aggregates and use numeric event keys ----------
  window.swsiOpenClusterEssay=function(i){
    const c=window.__swsiTopicClusters && window.__swsiTopicClusters[i];
    if(c) openClusterEssays(c.code);
  };
  window.swsiQuizCluster=function(i){
    const c=window.__swsiTopicClusters && window.__swsiTopicClusters[i];
    if(c) quizCluster(c.code);
  };
  renderTopics=function(){
    const cl={};
    ESSAYS.forEach(e=>{
      if(!e) return;
      const c=e.cluster||'其他';
      if(!cl[c]) cl[c]={code:c,name:e.cluster_name||c,n:0,freq:e.frequency||''};
      cl[c].n++;
    });
    const clusters=Object.values(cl).sort((a,b)=>b.n-a.n);
    window.__swsiTopicClusters=clusters;
    const clCards=clusters.map((c,i)=>{
      const m=ALL.length?clusterMcqCount(c.code):0;
      return '<div class="gcard" onclick="swsiOpenClusterEssay('+i+')"><div><div class="name">'+swsiEsc(c.name)+'</div><div class="cnt">申論 '+c.n+' 題'+(c.freq?' · '+swsiEsc(c.freq):'')+'</div></div>'+
        '<button type="button" onclick="event.stopPropagation();swsiQuizCluster('+i+')" style="font-family:inherit;font-size:12px;font-weight:700;color:#fff;background:var(--pine);border:none;border-radius:20px;padding:7px 14px;cursor:pointer;white-space:nowrap;flex-shrink:0">選擇 '+m+' ›</button></div>';
    }).join('');
    const opts=['全部科目'].concat(SWSI_CORE_SUBJECTS).map(s=>'<option value="'+swsiEsc(s)+'" '+(s===subjFilter?'selected':'')+'>'+swsiEsc(s)+'</option>').join('');
    const pool=subjFilter==='全部科目'?ALL:ALL.filter(q=>q.subject===subjFilter);
    const groups={}; pool.forEach(q=>{const m=q.major||'（未分類）';groups[m]=(groups[m]||0)+1;});
    const sorted=Object.entries(groups).sort((a,b)=>b[1]-a[1]); window._tg=sorted;
    const maxCnt=sorted.length?sorted[0][1]:1;
    const fT=(c)=>{const r=c/maxCnt,t=r>=0.4?'高頻':(r>=0.15?'中頻':'低頻'),col=r>=0.4?'background:var(--pine);color:#fff':(r>=0.15?'background:var(--correct-bg);color:var(--pine)':'background:#ECE6D6;color:var(--ink-soft)');return '<span class="tag" style="margin-left:6px;'+col+'">'+t+'</span>';};
    const cards=sorted.map(([name,cnt],i)=>'<div class="gcard" onclick="practiceTopic('+i+')"><div><div class="name">'+swsiEsc(name)+'</div><div class="cnt">'+cnt+' 題'+fT(cnt)+'</div></div><span class="arrow">›</span></div>').join('');
    const eOpen=topicsOpen==='essay',mOpen=topicsOpen==='mcq';
    app.innerHTML='<div class="section-h">考點</div><div class="section-s">挑一個主題開始：申論自己練、選擇題一鍵開。理論、法規、時事與讀書指南也能直接查。</div>'+ 
      '<div class="gcard" onclick="go(\'theories\')" style="background:var(--pine);border-color:var(--pine)"><div><div class="name" style="color:#fff">📖 核心理論小辭典</div><div class="cnt" style="color:#cfe3da">'+THEORIES.length+' 個申論必備理論</div></div><span class="arrow" style="color:#fff">›</span></div>'+ 
      '<div class="gcard" onclick="go(\'laws\')" style="background:var(--gold);border-color:var(--gold)"><div><div class="name" style="color:#fff">📜 重點法規速查</div><div class="cnt" style="color:#f5e9cf">'+LAWS.length+' 部常用法規 · 含修法動態</div></div><span class="arrow" style="color:#fff">›</span></div>'+ 
      '<div class="gcard" onclick="NL.open()" style="background:var(--pine-deep);border-color:var(--pine-deep)"><div><div class="name" style="color:#fff">📰 時事庫</div><div class="cnt" style="color:#cfe3da">近期社會事件 · 考點／理論／法規／可能怎麼考</div></div><span class="arrow" style="color:#fff">›</span></div>'+ 
      '<div class="gcard" onclick="SG.open()" style="background:#7E7A66;border-color:#7E7A66"><div><div class="name" style="color:#fff">📖 讀書指南</div><div class="cnt" style="color:#ece9da">學長姊應考心得 · 各科速查 · 申論策略</div></div><span class="arrow" style="color:#fff">›</span></div>'+ 
      '<div class="gcard" onclick="go(\'progress\')"><div><div class="name">📊 我的進度</div><div class="cnt">各科正確率、常錯考點與錯因分布</div></div><span class="arrow">›</span></div>'+ 
      '<div class="gcard" onclick="toggleTopics(\'essay\')" style="margin-top:14px'+(eOpen?';border-color:var(--pine);border-width:1.5px':'')+'"><div><div class="name">✍️ 申論題 · 依主題練</div><div class="cnt">'+clusters.length+' 個主題'+(eOpen?'（點我收合）':'')+'</div></div><span class="arrow">'+(eOpen?'▾':'›')+'</span></div>'+ 
      (eOpen?'<div style="margin-top:8px">'+clCards+'</div>':'')+
      '<div class="gcard" onclick="toggleTopics(\'mcq\')" style="margin-top:10px'+(mOpen?';border-color:var(--pine);border-width:1.5px':'')+'"><div><div class="name">📝 選擇題 · 依大類練</div><div class="cnt">'+sorted.length+' 個大類'+(mOpen?'（點我收合）':'')+'</div></div><span class="arrow">'+(mOpen?'▾':'›')+'</span></div>'+ 
      (mOpen?'<div style="margin-top:8px"><select class="subj" aria-label="選擇科目" onchange="subjFilter=this.value;render()">'+opts+'</select>'+cards+'</div>':'');
  };

  // ---------- Search/deep-link: never put DB/static names directly into inline JS ----------
  openTheory = function(name){
    theoryQ=swsiText(name);
    const i=THEORIES.findIndex(t=>t && t.n===name);
    theoryOpen=i>=0?i:null;
    go('theories');
  };
  openLawCard = function(name){
    lawQ=swsiText(name);
    const i=LAWS.findIndex(l=>l && l.n===name);
    lawOpen=i>=0?i:null;
    go('laws');
  };

  window.swsiSearchOpenMCQ=function(i){
    const q=window.__swsiSearchResults && window.__swsiSearchResults.mcq && window.__swsiSearchResults.mcq[i];
    if(q) studyOne(q.id);
  };
  window.swsiSearchOpenEssay=function(i){
    const e=window.__swsiSearchResults && window.__swsiSearchResults.essays && window.__swsiSearchResults.essays[i];
    if(e) openEssayCard(e.id,e.subject);
  };
  window.swsiSearchOpenTheory=function(i){
    const t=window.__swsiSearchResults && window.__swsiSearchResults.theories && window.__swsiSearchResults.theories[i];
    if(t) openTheory(t.n);
  };
  window.swsiSearchOpenLaw=function(i){
    const l=window.__swsiSearchResults && window.__swsiSearchResults.laws && window.__swsiSearchResults.laws[i];
    if(l) openLawCard(l.n);
  };

  renderSearch=function(){
    app.innerHTML='<div style="padding-top:6px"><input id="searchbox" value="'+swsiEsc(searchQ)+'" aria-label="搜尋題目、考點、理論、法規與申論" oninput="doSearch(this.value)" placeholder="搜尋題目、考點、理論、法規、申論…" autocomplete="off" style="width:100%;box-sizing:border-box;font-family:inherit;font-size:16px;padding:13px 15px;border:1.5px solid var(--line);border-radius:14px;background:#fff;color:var(--ink);outline:none"><div id="search-results"></div></div>';
    doSearch(searchQ);
    setTimeout(()=>{const el=document.getElementById('searchbox'); if(el){const v=el.value;el.focus();el.value='';el.value=v;}},50);
  };

  doSearch=function(val){
    searchQ=val;
    const box=document.getElementById('search-results'); if(!box) return;
    const q=swsiText(val).trim();
    if(!q){ box.innerHTML='<div style="color:var(--ink-soft);font-size:14px;line-height:1.95;padding:22px 4px">輸入關鍵字，一次搜尋選擇題、考點、理論、法規與申論。</div>'; return; }
    const r=searchAll(val); window.__swsiSearchResults=r;
    const total=r.mcq.length+r.essays.length+r.theories.length+r.laws.length;
    if(!total){ box.innerHTML='<div style="color:var(--ink-soft);font-size:14px;padding:24px 4px">找不到符合「<b style="color:var(--ink)">'+swsiEsc(q)+'</b>」的內容。</div>'; return; }
    const sec=t=>'<div style="font-size:12px;color:var(--ink-soft);font-weight:700;letter-spacing:.06em;margin:18px 0 9px">'+swsiEsc(t)+'</div>';
    const rowS='border:1px solid var(--line);border-radius:12px;padding:11px 13px;margin-bottom:8px;cursor:pointer;background:#fff';
    let h='<div style="font-size:12px;color:var(--ink-soft);padding:6px 2px 0">共 '+total+' 筆</div>';
    if(r.mcq.length){
      h+=sec('選擇題 · '+r.mcq.length+' 題')+'<button class="btn" style="margin-bottom:10px" onclick="searchQuizMcq()">▶ 把這 '+r.mcq.length+' 題練一遍</button>';
      r.mcq.slice(0,12).forEach((x,i)=>{h+='<div style="'+rowS+'" onclick="swsiSearchOpenMCQ('+i+')"><div style="font-size:14px;line-height:1.55;color:var(--ink);margin-bottom:5px">'+swsiEsc(snip(x.q,62))+'</div><div style="font-size:11.5px;color:var(--ink-soft)">'+swsiEsc(x.topic||x.major||'')+' · '+swsiEsc(x.year)+'年</div></div>';});
    }
    if(r.essays.length){
      h+=sec('申論題 · '+r.essays.length+' 題');
      r.essays.slice(0,10).forEach((x,i)=>{h+='<div style="'+rowS+'" onclick="swsiSearchOpenEssay('+i+')"><div style="font-size:14px;line-height:1.55;color:var(--ink);margin-bottom:5px">'+swsiEsc(snip(x.q,62))+'</div><div style="font-size:11.5px;color:var(--ink-soft)">'+swsiEsc(x.subject)+' · '+swsiEsc(x.year)+'年 · '+swsiEsc(x.topic||'')+'</div></div>';});
    }
    if(r.theories.length){
      h+=sec('核心理論 · '+r.theories.length+' 則');
      r.theories.slice(0,8).forEach((x,i)=>{h+='<div style="'+rowS+'" onclick="swsiSearchOpenTheory('+i+')"><div style="font-size:14px;font-weight:600;color:var(--pine);margin-bottom:4px">'+swsiEsc(x.n)+'</div><div style="font-size:12px;color:var(--ink-soft);line-height:1.5">'+swsiEsc(snip(x.c,56))+'</div></div>';});
    }
    if(r.laws.length){
      h+=sec('重點法規 · '+r.laws.length+' 則');
      r.laws.slice(0,8).forEach((x,i)=>{h+='<div style="'+rowS+'" onclick="swsiSearchOpenLaw('+i+')"><div style="font-size:14px;font-weight:600;color:var(--gold);margin-bottom:4px">'+swsiEsc(x.n)+'</div><div style="font-size:12px;color:var(--ink-soft);line-height:1.5">'+swsiEsc(snip(x.c,56))+'</div></div>';});
    }
    box.innerHTML=h;
  };

  // ---------- Secure review/progress ----------
  renderReview=function(){
    const rv=reviewSummary(), ids=rv.activeIds;
    if(!ids.length&&!rv.dueCount&&!rv.nextDueAt){
      app.innerHTML='<div class="empty"><div class="ico">✓</div><h3>'+(rv.masteredCount?'今天沒有待複習題':'還沒有錯題')+'</h3><p>'+(rv.masteredCount?('已有 '+rv.masteredCount+' 題完成學習與長期確認。'):'刷題答錯後，系統會自動安排之後的複習。')+'</p><button class="btn" style="max-width:200px;margin:22px auto 0" onclick="go(\'home\')">回首頁刷題</button></div>';
      return;
    }
    const wrongQs=ids.map(id=>ALL.find(q=>q.id===id)).filter(Boolean);
    const byReason={}; wrongQs.forEach(q=>{const r=q.mistake||'未分類';(byReason[r]=byReason[r]||[]).push(q);});
    window._rs=[{label:'全部未熟練錯題',ids:ids}];
    const reasons=Object.entries(byReason).sort((a,b)=>b[1].length-a[1].length);
    reasons.forEach(pair=>window._rs.push({label:pair[0],ids:pair[1].map(x=>x.id)}));
    let html='<div class="ux-page-head"><h2>今日複習</h2><p>先處理今天到期的錯題；其他未熟練題目需要時再重練。</p></div>'+
      '<div class="statrow" style="margin-bottom:14px"><div class="stat"><div class="v" style="color:var(--wrong)">'+rv.dueCount+'</div><div class="k">今天到期</div></div><div class="stat"><div class="v">'+rv.activeCount+'</div><div class="k">未熟練</div></div><div class="stat"><div class="v" style="color:var(--correct)">'+rv.masteredCount+'</div><div class="k">已掌握</div></div></div>';
    if(rv.dueCount) html+='<button class="btn" onclick="startDueReview()" style="margin-bottom:10px">開始今天的複習 · '+rv.dueCount+' 題</button>';
    else if(rv.nextDueAt) html+='<div style="margin-bottom:12px;padding:11px 13px;border:1px solid var(--line);border-radius:12px;background:#fff;font-size:13px;color:var(--ink-soft)">✓ 今天已完成，下一批 '+swsiEsc(reviewDueLabel(rv.nextDueAt))+'。</div>';
    if(wrongQs.length) html+='<button class="btn ghost" onclick="practiceSet(0)" style="margin-bottom:5px">重練全部未熟練 · '+wrongQs.length+' 題</button>';
    html+='<details class="ux-review-rule"><summary>複習規則</summary><p>答錯後 1 天再看；答對後逐步拉長到 3、7 天。連續答對 3 次後進入已掌握，再於 14、30 天做長期確認；之後若又答錯，會重新排入複習。</p></details>';
    if(reasons.length){
      html+='<div class="ux-subhead">依錯因加強</div>';
      reasons.forEach((pair,i)=>{html+='<div class="gcard wrongcat" onclick="practiceSet('+(i+1)+')"><div><div class="name">'+swsiEsc(pair[0])+'</div><div class="cnt">'+pair[1].length+' 題</div></div><span class="arrow">›</span></div>';});
    }
    app.innerHTML=html;
  };

  renderProgress=function(){
    const s=computeStats();
    if(s.total===0){
      app.innerHTML='<div class="empty"><div class="ico">◴</div><h3>還沒有刷題紀錄</h3><p>開始刷題後，這裡會顯示你的正確率與各科強弱。</p><button class="btn" style="max-width:200px;margin:22px auto 0" onclick="go(\'home\')">開始刷題</button>'+(hasDrafts()?'<button class="btn ghost" style="max-width:280px;margin:12px auto 0" onclick="exportDrafts()">匯出申論草稿（TXT）</button>':'')+'</div>';
      return;
    }
    const rate=Math.round(s.correct/s.total*100); let accHTML='';
    Object.entries(s.bySubj).sort((a,b)=>b[1].t-a[1].t).forEach(([subj,d])=>{
      const r=Math.round(d.c/d.t*100), col=r>=70?'var(--correct)':r>=50?'var(--gold)':'var(--wrong)';
      accHTML+='<div class="accrow"><div class="top"><b style="font-weight:500">'+swsiEsc(subj)+'</b><span style="color:var(--ink-soft)">'+r+'%　('+d.c+'/'+d.t+')</span></div><div class="accbar"><i style="width:'+r+'%;background:'+col+'"></i></div></div>';
    });
    const weakTop=Object.entries(s.wrongMajor).sort((a,b)=>b[1]-a[1]).slice(0,5);
    const weakHTML=weakTop.length?'<div class="weak"><h4>⚠ 最常錯的考點</h4>'+weakTop.map(([m,n])=>'<div class="item">· '+swsiEsc(m)+'（錯 '+n+' 題）</div>').join('')+'</div>':'';
    const mis=Object.entries(s.byMistake).sort((a,b)=>b[1]-a[1]);
    const misHTML=mis.length?'<div class="weak" style="background:#fff;border:1px solid var(--line)"><h4 style="color:var(--ink)">錯因分布</h4>'+mis.map(([m,n])=>'<div class="item">· '+swsiEsc(m)+' × '+n+'</div>').join('')+'</div>':'';
    app.innerHTML='<div class="section-h">我的進度</div><div class="section-s">沒有打卡、沒有連勝壓力，只有對你有用的數據。</div>'+
      '<div class="sumcard"><div style="font-size:13px;color:var(--ink-soft);margin-bottom:6px">總正確率</div><div class="big">'+rate+'%</div>'+
      '<div class="statrow"><div class="stat"><div class="v">'+s.total+'</div><div class="k">總刷題</div></div><div class="stat"><div class="v" style="color:var(--correct)">'+s.correct+'</div><div class="k">答對</div></div><div class="stat"><div class="v" style="color:var(--wrong)">'+(s.total-s.correct)+'</div><div class="k">答錯</div></div></div></div>'+
      '<div style="margin-top:22px"><div class="subj-pill">各科正確率</div>'+accHTML+'</div>'+
      (weakHTML?'<div style="margin-top:16px">'+weakHTML+'</div>':'')+(misHTML?'<div style="margin-top:14px">'+misHTML+'</div>':'')+
      '<button class="btn ghost" style="margin-top:20px" onclick="exportDrafts()">匯出申論草稿（TXT）</button>'+
      '<button class="btn ghost" style="margin-top:10px" onclick="if(confirm(\'清除所有刷題與間隔複習紀錄？無法復原。\')){localStorage.removeItem(LS_KEY);localStorage.removeItem(REVIEW_KEY);render();}">清除我的紀錄</button>';
  };

  // ---------- Storage status ----------
  window.__swsiStorageWarning=false;
  function storageStatus(id, ok){
    window.__swsiStorageWarning=!ok;
    const el=document.getElementById('storage_'+id);
    if(el){
      el.textContent=ok?'已儲存在這台裝置':'⚠ 無法儲存，請立即備份';
      el.style.color=ok?'var(--ink-soft)':'var(--wrong)';
    }
  }
  const oldSaveHist=saveHist;
  saveHist=function(h){
    try{ localStorage.setItem(LS_KEY,JSON.stringify(h)); window.__swsiStorageWarning=false; }
    catch(e){ window.__swsiStorageWarning=true; console.warn('學習紀錄無法儲存',e); }
  };
  saveReviewState=function(st){
    try{ localStorage.setItem(REVIEW_KEY,JSON.stringify(st)); window.__swsiStorageWarning=false; }
    catch(e){ window.__swsiStorageWarning=true; console.warn('複習排程無法儲存',e); }
  };

  const legacyWriteBoxHTML=writeBoxHTML;
  writeBoxHTML=function(id){
    const html=legacyWriteBoxHTML(id);
    return html.replace('<div class="wmeta"><span id="wc_'+id+'">','<div class="wmeta"><span id="storage_'+id+'">已儲存在這台裝置</span> · <span id="wc_'+id+'">');
  };
  saveDraft=function(id){
    const ta=document.getElementById('ta_'+id); if(!ta) return;
    let ok=true;
    try{ localStorage.setItem(essayDraftKey(id),ta.value); }catch(e){ ok=false; console.warn('申論草稿無法儲存',e); }
    storageStatus(id,ok);
    const wc=document.getElementById('wc_'+id); if(wc) wc.textContent=ta.value.length;
    const gb=document.getElementById('gbtn_'+id); if(gb) gb.style.display=ta.value.trim()?'':'none';
  };

  // ---------- AI client ID, precise errors, privacy, max 3 photos ----------
  const AI_CLIENT_ID_KEY='swsi_ai_client_id_v1';
  function getAIClientId(){
    try{
      let id=localStorage.getItem(AI_CLIENT_ID_KEY)||'';
      if(!/^[A-Za-z0-9_-]{16,128}$/.test(id)){
        id=(window.crypto&&crypto.randomUUID)?crypto.randomUUID():('swsi_'+Date.now()+'_'+Math.random().toString(36).slice(2));
        localStorage.setItem(AI_CLIENT_ID_KEY,id);
      }
      return id;
    }catch(_e){
      return 'swsi_'+Date.now()+'_'+Math.random().toString(36).slice(2);
    }
  }
  window.getAIClientId=getAIClientId;

  async function aiErrorInfo(r){
    let data=null;
    try{ data=await r.clone().json(); }catch(_e){}
    const e=data&&data.error;
    const code=swsiText((e&&e.code)||data&&data.code).trim();
    const message=swsiText((e&&e.message)||data&&data.message).trim();
    if(message) return {message,retry:!['CLIENT_DAILY_QUOTA','GLOBAL_DAILY_QUOTA'].includes(code),code};
    if(r.status===413) return {message:'照片太大了，請裁切或減少張數後再試。',retry:true,code:'PAYLOAD_TOO_LARGE'};
    if(r.status===429) return {message:'目前使用量較高，請稍後再試。',retry:true,code:'RATE_LIMIT'};
    if(r.status===502||r.status===503) return {message:'AI 服務暫時忙碌，請稍後再試。',retry:true,code:'UPSTREAM'};
    if(r.status===401||r.status===403) return {message:'AI 服務目前無法使用，請稍後再試。',retry:false,code:'FORBIDDEN'};
    return {message:'AI 批改暫時無法使用。',retry:true,code:'HTTP_'+r.status};
  }

  aiFeedbackHTML=function(id){
    return '<div style="margin-top:14px;border-top:1px dashed var(--line);padding-top:12px">'+
      '<div class="aihelp" style="color:var(--wrong);margin-bottom:9px;background:var(--wrong-bg);border:1px solid var(--line);border-radius:8px;padding:9px 12px">🔒 照片／文字會送至外部 AI 服務處理；請勿輸入或上傳可識別真實個案或個人的資料。需要舉例時請先匿名化。</div>'+
      '<div class="aihelp" style="color:var(--ink-soft);margin-bottom:9px;background:#FBF8EF;border:1px solid var(--line);border-radius:8px;padding:9px 12px">💡 平台提供的是申論練習回饋，並非考選部官方評分。</div>'+
      '<button class="fbtn" style="width:100%;padding:11px;font-size:14px;color:var(--pine);font-weight:600" onclick="runAIFeedback(\''+swsiEsc(id)+'\')">🤖 我用打字的 · 請 AI 批改</button>'+
      '<input type="file" id="photo_'+swsiEsc(id)+'" accept="image/*" multiple style="display:none" onchange="gradePhoto(\''+swsiEsc(id)+'\',this)">'+
      '<button class="fbtn" style="width:100%;padding:11px;font-size:14px;color:var(--pine);font-weight:600;margin-top:8px" onclick="document.getElementById(\'photo_'+swsiEsc(id)+'\').click()">📷 我用手寫的 · 拍照上傳給 AI 批改</button>'+
      '<div class="aihelp" style="color:var(--ink-soft);margin-top:7px">一次最多 3 張。光線充足、字跡清楚、整頁入鏡會讀得更準；AI 會先顯示辨識到的文字供你核對。</div><div id="airesult_'+swsiEsc(id)+'"></div></div>';
  };

  function essayPromptContext(id){
    const e=(window.ESSAYS||[]).find(x=>x.id===id)||{};
    const g=(window.ESSAY_GUIDES||{})[id]||{};
    const skel='考點：'+(g.kao||'（無）')+'\n破題心法：'+(g.dati||'（無）')+'\n必踩大標：'+(g.biaoti||[]).join('；')+'\n搶分關鍵字：'+(g.kw||[]).join('、');
    return {e,g,skel};
  }

  runAIFeedback=async function(id){
    const out=document.getElementById('airesult_'+id); if(!out) return;
    const ta=document.getElementById('ta_'+id), ans=(ta?ta.value:'').trim();
    if(ans.length<30){ out.innerHTML='<div style="margin-top:10px;font-size:13px;color:var(--wrong);line-height:1.7">先把架構寫出來（至少列個大綱），AI 才能給有意義的回饋。</div>'; return; }
    const {e,skel}=essayPromptContext(id);
    const sys='【最重要規則：整份回饋務必用繁體中文書寫。】\n你是台灣社工師國家考試的申論練習教練。平台會提供「參考骨架與關鍵字」以及學生作答，請依這些參考資料與正確社工專業知識給練習回饋。\n'+
      '嚴格規則：\n- 這是練習回饋、不是官方評分；不要給分數、不要自稱官方標準。\n- 不要自行編造法條條號、數字或學者。\n- 若作答空白、亂打或與題目無關，只提醒先用拆題五步建立架構。\n- 繁體中文、分點、約 300 字內。\n'+
      '回饋結構：\n一、方向與架構\n二、可以補強\n三、一句鼓勵。';
    const user='【題目】'+(e.q||'')+'（'+(e.points||20)+'分）\n【平台參考骨架與關鍵字】\n'+skel+'\n【學生作答】\n'+ans;
    out.innerHTML='<div style="margin-top:12px;font-size:14px;color:var(--ink-soft)">🤖 AI 批改中…</div>';
    try{
      const r=await fetch(AI_PROXY_URL,{method:'POST',headers:{'Content-Type':'application/json','X-SWSI-Client-ID':getAIClientId()},body:JSON.stringify({model:GROQ_MODEL,reasoning_effort:'none',temperature:0.5,max_tokens:1200,messages:[{role:'user',content:sys+'\n\n'+user}]})});
      if(!r.ok){
        const info=await aiErrorInfo(r);
        out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">'+swsiEsc(info.message)+(info.retry?' <button class="fbtn" style="margin-left:6px" onclick="runAIFeedback(\''+swsiEsc(id)+'\')">重試</button>':'')+'</div>';
        return;
      }
      const data=await r.json();
      const txt=swsiText(data&&data.choices&&data.choices[0]&&data.choices[0].message&&data.choices[0].message.content).replace(/<think>[\s\S]*?<\/think>/gi,'').trim();
      if(!txt){ out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong)">AI 沒有回傳內容，請稍後再試。</div>'; return; }
      out.innerHTML='<div style="margin-top:12px;background:#fff;border:1px solid var(--line);border-left:3px solid var(--pine);border-radius:10px;padding:14px;font-size:14px;line-height:1.8;color:var(--ink);white-space:pre-wrap">'+swsiEsc(txt)+'</div>'+
        '<div style="font-size:11px;color:var(--ink-soft);margin-top:6px;line-height:1.6">⚠ AI 練習回饋僅供參考、非官方評分；正式標準以老師與考選部為準。</div>';
    }catch(err){
      out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">連線失敗，請檢查網路後再試一次。</div>';
    }
  };

  gradePhoto=async function(id,inputEl){
    const out=document.getElementById('airesult_'+id); if(!out) return;
    let files=inputEl&&inputEl.files?Array.from(inputEl.files):[];
    if(!files.length) return;
    if(files.length>3){
      out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">一次最多 3 張照片，請重新選擇。</div>';
      if(inputEl) inputEl.value='';
      return;
    }
    out.innerHTML='<div style="margin-top:12px;font-size:14px;color:var(--ink-soft)">📷 照片處理中…（'+files.length+' 張）</div>';
    const imgs=[];
    try{ for(const f of files) imgs.push(await shrinkImage(f,1200,0.8)); }
    catch(err){ out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong)">有照片讀取失敗，請改用相機重拍。</div>'; if(inputEl) inputEl.value=''; return; }
    if(inputEl) inputEl.value='';
    const {e,skel}=essayPromptContext(id);
    const sys='【最重要規則：整份回覆務必用繁體中文書寫。】\n你是台灣社工師國家考試申論練習教練。學生上傳 1–3 張同一份手寫作答照片。\n'+
      '第一步：依頁面順序辨識手寫文字；看不清楚用「◌」，不要自行補字。\n第二步：若照片模糊、空白或幾乎讀不出字，只提醒重新拍攝。\n第三步：依平台提供的參考骨架與關鍵字，以及正確社工專業知識，給練習回饋。\n'+
      '不要給官方分數、不要編造法條條號或學者。\n輸出格式：\n【我讀到的作答】\n...\n\n【練習回饋】\n一、方向與架構\n二、可以補強\n三、一句鼓勵。';
    const user='【題目】'+(e.q||'')+'（'+(e.points||20)+'分）\n【平台參考骨架與關鍵字】\n'+skel;
    const content=[{type:'text',text:sys+'\n\n'+user}];
    imgs.forEach(u=>content.push({type:'image_url',image_url:{url:u}}));
    out.innerHTML='<div style="margin-top:12px;font-size:14px;color:var(--ink-soft)">🤖 AI 正在讀 '+imgs.length+' 張照片並批改…</div>';
    try{
      const r=await fetch(AI_PROXY_URL,{method:'POST',headers:{'Content-Type':'application/json','X-SWSI-Client-ID':getAIClientId()},body:JSON.stringify({model:GROQ_MODEL,reasoning_effort:'none',temperature:0.4,max_tokens:1100,messages:[{role:'user',content}]})});
      if(!r.ok){
        const info=await aiErrorInfo(r);
        out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">'+swsiEsc(info.message)+(info.retry?' <button class="fbtn" onclick="document.getElementById(\'photo_'+swsiEsc(id)+'\').click()">重試</button>':'')+'</div>';
        return;
      }
      const data=await r.json();
      const txt=swsiText(data&&data.choices&&data.choices[0]&&data.choices[0].message&&data.choices[0].message.content).replace(/<think>[\s\S]*?<\/think>/gi,'').trim();
      if(!txt){ out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong)">AI 沒有回傳內容，請稍後再試。</div>'; return; }
      out.innerHTML='<div style="margin-top:12px;background:#fff;border:1px solid var(--line);border-left:3px solid var(--pine);border-radius:10px;padding:14px;font-size:14px;line-height:1.8;color:var(--ink);white-space:pre-wrap">'+swsiEsc(txt)+'</div>'+
        '<div style="font-size:11px;color:var(--ink-soft);margin-top:6px;line-height:1.6">⚠ AI 練習回饋僅供參考、非官方評分；手寫辨識可能有誤，請先核對「我讀到的作答」。</div>';
    }catch(err){
      out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">連線失敗，請檢查網路後再試一次。</div>';
    }
  };

  // Block unsafe dynamically-produced external links before navigation.
  document.addEventListener('click',function(ev){
    const a=ev.target && ev.target.closest ? ev.target.closest('a[href]') : null;
    if(!a) return;
    try{
      const u=new URL(a.getAttribute('href'),location.href);
      if(u.protocol!=='https:' && u.protocol!=='http:'){
        ev.preventDefault();
        alert('已阻擋不安全的連結。');
      }
    }catch(_e){
      ev.preventDefault();
    }
  },true);

  // Accessibility for the legacy simulation overlay, which is rendered inside a private closure.
  const accessibilityStyle=document.createElement('style');
  accessibilityStyle.textContent='.mk-opt:focus-visible{outline:2px solid var(--pine);outline-offset:2px}.mk-opt{font-family:inherit}.mk-cell:focus-visible{outline:2px solid var(--pine);outline-offset:2px}';
  document.head.appendChild(accessibilityStyle);
  function enhanceLegacyInteractive(root){
    const scope=root&&root.querySelectorAll?root:document;
    scope.querySelectorAll('.mk-opt').forEach(el=>{
      el.tabIndex=0; el.setAttribute('role','radio'); el.setAttribute('aria-checked',el.classList.contains('sel')?'true':'false');
    });
    scope.querySelectorAll('.mk-cell').forEach(el=>{el.tabIndex=0;el.setAttribute('role','button');});
  }
  document.addEventListener('keydown',function(ev){
    const el=ev.target;
    if(!el||!(el.classList&&((el.classList.contains('mk-opt'))||(el.classList.contains('mk-cell'))))) return;
    if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();el.click();}
  });
  try{
    const a11yObserver=new MutationObserver(muts=>{muts.forEach(m=>m.addedNodes.forEach(n=>{if(n&&n.nodeType===1)enhanceLegacyInteractive(n);}));});
    a11yObserver.observe(document.body,{childList:true,subtree:true});
  }catch(_e){}

  // Accessibility labels for existing font controls.
  document.querySelectorAll('.fontctl button').forEach((b,i)=>{
    if(!b.getAttribute('aria-label')) b.setAttribute('aria-label',['小字','中字','大字'][i]||'調整字級');
  });

  // Clean existing essay text loaded before this patch.
  try{
    (window.ESSAYS||[]).forEach(e=>{ if(e&&e.q) e.q=swsiCleanPUA(e.q); });
  }catch(_e){}

  // Final boot: build-time patch suppresses the legacy init() call until this file is loaded.
  if(window.__SWSI_BOOT_DEFERRED__){
    window.__SWSI_BOOT_DEFERRED__=false;
    init().catch(showLoadError);
  }
})();

/* SWSI Font Size Control Fix 2026-08-26
   Restore visible 小／中／大 scaling across the UIUX layer and inline home controls.
   The legacy question/explanation typography already uses --fs-q/--fs-h/--fs-b/--fs-s.
*/
(function(){
  if(document.getElementById('swsi-font-size-control-fix')) return;
  var style=document.createElement('style');
  style.id='swsi-font-size-control-fix';
  style.textContent=`
:root{
  --swsi-ui-hero:25px;
  --swsi-ui-heading:18px;
  --swsi-ui-title:15px;
  --swsi-ui-body:14px;
  --swsi-ui-small:11.5px;
  --swsi-ui-control:14px;
  --swsi-ui-tab:12px;
}
html[data-fs="1"]{
  --swsi-ui-hero:29px;
  --swsi-ui-heading:20px;
  --swsi-ui-title:17px;
  --swsi-ui-body:16px;
  --swsi-ui-small:13px;
  --swsi-ui-control:16px;
  --swsi-ui-tab:14px;
}
html[data-fs="2"]{
  --swsi-ui-hero:33px;
  --swsi-ui-heading:23px;
  --swsi-ui-title:20px;
  --swsi-ui-body:18px;
  --swsi-ui-small:15px;
  --swsi-ui-control:18px;
  --swsi-ui-tab:16px;
}
main .hero h1,
main .ux-home-intro h1{
  font-size:var(--swsi-ui-hero)!important;
}
main .ask,
main .section-h,
main .ux-page-head h2{
  font-size:var(--swsi-ui-heading)!important;
}
main .gcard .name,
main .time-card .t,
main .ux-card-title,
main .ux-link-card .title{
  font-size:var(--swsi-ui-title)!important;
}
main .btn,
main .fbtn,
main .dbtn,
main select.subj,
main .ux-btn-main,
main .ux-btn-soft,
main .ux-tools button{
  font-size:var(--swsi-ui-control)!important;
}
main input:not([type="checkbox"]):not([type="radio"]),
main textarea{
  font-size:var(--fs-b)!important;
}
main .hero .tagline,
main .chip,
main .gcard .cnt,
main .time-card .n,
main .quote,
main .pcount,
main .quit,
main .tag,
main .stat .k,
main .weak h4,
main .ux-home-intro .eyebrow,
main .ux-home-intro p,
main .ux-home-meta span,
main .ux-card-sub,
main .ux-badge,
main .ux-link-card .sub,
main .ux-custom-label,
main .ux-note,
main .ux-page-head p,
main .ux-review-rule summary,
main .ux-review-rule p,
main .ux-subhead{
  font-size:var(--swsi-ui-small)!important;
}
main [style*="font-size:11px"],
main [style*="font-size:11.5px"],
main [style*="font-size:12px"],
main [style*="font-size:12.5px"]{
  font-size:var(--swsi-ui-small)!important;
}
main [style*="font-size:13px"],
main [style*="font-size:14px"],
main [style*="font-size:15px"]{
  font-size:var(--swsi-ui-body)!important;
}
.tabbar button{
  font-size:var(--swsi-ui-tab)!important;
}
.fontctl button[data-l="0"]{font-size:12px!important;}
.fontctl button[data-l="1"]{font-size:15px!important;}
.fontctl button[data-l="2"]{font-size:18px!important;}
`;
  document.head.appendChild(style);
})();

/* SWSI Layout Foundation V1 2026-08-29
   Layer 1: one owner for the global shell (header / main / footer / bottom nav).
   Layer 2: page templates are expressed only through body[data-swsi-page].
   Layer 3: feature modules own their cards/components, never the global shell.
*/
(function(){
  'use strict';

  var STYLE_ID='swsi-layout-foundation-v1';
  if(!document.getElementById(STYLE_ID)){
    var st=document.createElement('style');
    st.id=STYLE_ID;
    st.textContent=`
      :root{
        --swsi-shell-max:540px;
        --swsi-shell-x:22px;
        --swsi-main-y:24px;
        --swsi-tabbar-button-height:58px;
        --swsi-tabbar-clearance:calc(84px + env(safe-area-inset-bottom,0px));
      }

      html{
        min-height:100%;
        scroll-padding-bottom:var(--swsi-tabbar-clearance);
      }
      body{
        min-height:100vh;
        min-height:100dvh;
        padding-bottom:0!important;
      }
      .wrap{
        width:100%;
        max-width:var(--swsi-shell-max);
        margin:0 auto;
        min-height:100vh!important;
        min-height:100dvh!important;
        height:auto!important;
        display:flex!important;
        flex-direction:column!important;
        padding-bottom:var(--swsi-tabbar-clearance)!important;
      }
      header{
        padding-top:calc(20px + env(safe-area-inset-top,0px))!important;
      }
      main{
        flex:1 0 auto!important;
        min-height:0!important;
        height:auto!important;
        padding-bottom:24px!important;
      }
      footer{
        margin-top:auto!important;
        margin-bottom:0!important;
        padding:16px var(--swsi-shell-x) 18px!important;
      }

      .tabbar{
        position:fixed!important;
        left:50%!important;
        right:auto!important;
        bottom:0!important;
        width:100%!important;
        max-width:var(--swsi-shell-max)!important;
        transform:translateX(-50%)!important;
        padding-bottom:env(safe-area-inset-bottom,0px)!important;
        z-index:30!important;
      }
      .tabbar button{
        min-height:var(--swsi-tabbar-button-height)!important;
        padding:8px 4px 10px!important;
      }
      .tabbar .ico{font-size:17px!important;}

      /* Internal app pages do not repeat the large public footer. The complete
         footer is reserved for the platform entry/loading shell; public info is
         still available from Learning > 更多與平台資訊. */
      body.swsi-layout-ready footer{display:none!important;}
      body.swsi-layout-ready[data-swsi-page="home"] footer,
      body.swsi-layout-ready[data-swsi-page="loading"] footer{display:block!important;}

      /* Home is intentionally content-height so the public footer follows the
         home content naturally. Bottom-nav clearance still belongs to .wrap. */
      body[data-swsi-page="home"] .wrap{
        min-height:0!important;
        height:auto!important;
      }
      body[data-swsi-page="home"] main{
        flex:0 0 auto!important;
        min-height:0!important;
        padding-bottom:10px!important;
      }
      body[data-swsi-page="home"] footer{
        margin-top:12px!important;
        padding-bottom:18px!important;
      }

      /* Loading keeps the shell stable: the flexible main pushes attribution
         toward the lower part of the viewport without arbitrary spacer pixels. */
      body[data-swsi-page="loading"] main{flex:1 0 auto!important;}

      @media(max-width:720px){
        .tabbar{
          left:0!important;
          right:0!important;
          width:100%!important;
          max-width:none!important;
          transform:none!important;
          border-radius:0!important;
          box-shadow:none!important;
          border-left:0!important;
          border-right:0!important;
          border-bottom:0!important;
          border-top:1px solid var(--line)!important;
          background:rgba(248,250,249,.985)!important;
          padding-left:env(safe-area-inset-left,0px)!important;
          padding-right:env(safe-area-inset-right,0px)!important;
        }
      }
      @media(max-width:420px){
        :root{--swsi-tabbar-clearance:calc(88px + env(safe-area-inset-bottom,0px));}
      }
      html[data-fs="2"]{
        --swsi-tabbar-clearance:calc(94px + env(safe-area-inset-bottom,0px));
      }
      @media(display-mode:standalone),(display-mode:fullscreen){
        :root{--swsi-tabbar-clearance:calc(90px + env(safe-area-inset-bottom,0px));}
        html[data-fs="2"]{--swsi-tabbar-clearance:calc(98px + env(safe-area-inset-bottom,0px));}
      }
    `;
    document.head.appendChild(st);
  }

  function detectPage(){
    var app=document.getElementById('app');
    if(!app)return 'loading';
    var text=(app.textContent||'').trim();
    if(/正在開啟 SWSI|載入題庫|準備完整題庫|第一次開啟全庫功能|下載已發布的歷屆考次/.test(text))return 'loading';
    if(app.querySelector('.qcard'))return 'quiz';
    if(app.querySelector('.swsi-focus-hero'))return 'home';
    if(app.querySelector('.sumcard'))return 'result';
    if(app.querySelector('.swsi-myhub'))return 'learning';
    if(app.querySelector('.wta,.wbox'))return 'essay-write';

    /* Essay library is a router state, not a styling state. Later navigation
       polish is allowed to rewrite tab markup/classes, so do not make shell
       classification depend on the visual `.on` class. */
    try{
      if(typeof view!=='undefined'&&view==='essay')return 'essay-library';
    }catch(_e){}

    if(app.querySelector('.swsi-learning-section,.swsi-progress-hero'))return 'learning-detail';

    /* Compatibility fallback for older renderers that do not expose router state. */
    var essayTab=document.getElementById('t-essay');
    if(essayTab&&essayTab.classList.contains('on'))return 'essay-library';
    var h=app.querySelector('.section-h');
    if(h&&/申論/.test(h.textContent||''))return 'essay-library';
    return 'standard';
  }

  function syncLayout(){
    if(!document.body)return;
    var page=detectPage();
    document.body.setAttribute('data-swsi-page',page);
    document.body.classList.add('swsi-layout-ready');
    /* Compatibility marker for existing interaction QA and any older owner that
       only needs to know whether a question card is active. Geometry still lives here. */
    document.body.classList.toggle('swsi-question-active',page==='quiz');
  }

  syncLayout();
  var app=document.getElementById('app');
  if(app){
    try{
      var queued=false;
      new MutationObserver(function(){
        if(queued)return;
        queued=true;
        requestAnimationFrame(function(){queued=false;syncLayout();});
      }).observe(app,{childList:true,subtree:true,characterData:true});
    }catch(_e){}
  }
  window.addEventListener('pageshow',syncLayout);
  window.addEventListener('focus',syncLayout);
})();
/* SWSI Focused Study Home V2 2026-08-29
   UX simplification preview: one clear study action at a time.
   No grading, question-bank, AI or storage contract changes.
*/
(function(){
  'use strict';

  function installStyle(){
    if(document.getElementById('swsi-product-philosophy-style')) return;
    var style=document.createElement('style');
    style.id='swsi-product-philosophy-style';
    style.textContent=`
      .swsi-focus-hero{background:linear-gradient(155deg,#426D64,#355A52);color:#fff;border-radius:18px;padding:18px 18px 17px;margin-bottom:11px;box-shadow:0 5px 18px rgba(43,62,57,.11)}
      .swsi-focus-hero .kicker{font-size:var(--swsi-ui-small,11px);font-weight:800;letter-spacing:1.2px;opacity:.8;margin-bottom:4px}
      .swsi-focus-hero h1{font-family:'Noto Serif TC',serif;font-size:var(--swsi-ui-hero,22px);font-weight:900;line-height:1.35;letter-spacing:.1px;margin:0}
      .swsi-focus-hero p{font-size:var(--swsi-ui-body,13px);line-height:1.65;opacity:.9;margin:6px 0 0}
      .swsi-focus-primary{background:#fff;border:1px solid rgba(79,126,118,.44);border-radius:17px;padding:17px;margin-bottom:9px;box-shadow:0 2px 10px rgba(43,42,38,.025)}
      .swsi-focus-primary .label{font-size:var(--swsi-ui-small,11px);font-weight:800;color:var(--pine);letter-spacing:.8px;margin-bottom:3px}
      .swsi-focus-primary h2{font-family:'Noto Serif TC',serif;font-size:var(--swsi-ui-title,16px);line-height:1.4;margin:0;font-weight:900}
      .swsi-focus-primary p{font-size:var(--swsi-ui-small,11.5px);line-height:1.65;color:var(--ink-soft);margin:4px 0 0}
      .swsi-focus-actions{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(0,1fr);gap:8px;margin-top:13px}
      .swsi-focus-actions button{min-height:48px;border-radius:12px;font-family:'Noto Sans TC',sans-serif;font-size:var(--swsi-ui-control,14px);font-weight:800;cursor:pointer}
      .swsi-focus-actions .go{border:none;background:var(--pine-deep);color:#fff}.swsi-focus-actions .choose{border:1px solid var(--line);background:var(--paper2);color:var(--pine)}
      .swsi-focus-custom{background:#fff;border:1px solid var(--line);border-radius:15px;padding:14px;margin:-1px 0 10px}
      .swsi-focus-custom .field-label{font-size:var(--swsi-ui-small,11px);font-weight:800;color:var(--ink-soft);margin:0 0 5px}.swsi-focus-custom .hint{font-size:var(--swsi-ui-small,11px);line-height:1.6;color:var(--ink-soft);margin:1px 0 9px}
      .swsi-study-card{width:100%;display:flex;align-items:center;justify-content:space-between;gap:12px;text-align:left;background:#fff;border:1px solid var(--line);border-radius:15px;padding:15px 16px;margin:0 0 8px;cursor:pointer;color:var(--ink);font-family:inherit}
      .swsi-study-card.due{border-color:rgba(158,97,85,.42);background:#FBF6F4}.swsi-study-card .copy{min-width:0}.swsi-study-card .title{font-family:'Noto Serif TC',serif;font-weight:900;font-size:var(--swsi-ui-title,15px);line-height:1.4}.swsi-study-card .sub{font-size:var(--swsi-ui-small,11.5px);color:var(--ink-soft);line-height:1.55;margin-top:3px}.swsi-study-card .aside{flex:0 0 auto;color:var(--ink-3);font-size:21px}.swsi-study-card .count{font-size:var(--swsi-ui-small,11px);font-weight:800;color:var(--wrong);background:#fff;border-radius:999px;padding:5px 9px;white-space:nowrap}
      .swsi-other-tools{margin:12px 0 0;border-top:1px solid var(--line);padding-top:3px}.swsi-other-tools summary{list-style:none;cursor:pointer;min-height:44px;display:flex;align-items:center;justify-content:center;font-size:var(--swsi-ui-small,11.5px);font-weight:800;color:var(--ink-soft)}.swsi-other-tools summary::-webkit-details-marker{display:none}.swsi-other-tools summary::after{content:'＋';margin-left:7px;color:var(--ink-3)}.swsi-other-tools[open] summary::after{content:'－'}.swsi-other-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding-bottom:4px}.swsi-other-grid button{min-height:45px;border:1px solid var(--line);border-radius:12px;background:#fff;color:var(--pine);font-family:'Noto Sans TC',sans-serif;font-size:var(--swsi-ui-control,13.5px);font-weight:800}
      .swsi-principle-note{margin:12px 4px 2px;text-align:center;font-size:var(--swsi-ui-small,10.8px);line-height:1.6;color:var(--ink-soft)}
      @media(max-width:370px){.swsi-focus-actions,.swsi-other-grid{grid-template-columns:1fr}.swsi-focus-hero{padding:17px 16px}}
    `;
    document.head.appendChild(style);
  }

  window.swsiStartNow=function(){
    try{homeQuizScope='smart';homeQuizCount=20;subjFilter='全部科目';homeQuizOpen=false;}catch(_e){}
    if(typeof startFocusedQuiz==='function') startFocusedQuiz();
  };

  function safeReviewSummary(){
    try{return reviewSummary();}catch(_e){return {dueCount:0,activeCount:0,nextDueAt:null};}
  }

  renderHome=function(){
    installStyle();
    var rv=safeReviewSummary();
    var years=examYears();
    if(!homeQuizYear&&years.length) homeQuizYear=String(years[0]);
    homeQuizRound=homeQuizRound==='all'?'all':canonicalRound(homeQuizRound);
    var specific=homeQuizScope==='specific';
    var subjOpts=['全部科目'].concat(SUBJECTS).map(function(x){return '<option value="'+swsiEsc(x)+'" '+(x===subjFilter?'selected':'')+'>'+swsiEsc(x)+'</option>';}).join('');
    var yearOpts=years.map(function(y){return '<option value="'+y+'" '+(String(y)===String(homeQuizYear)?'selected':'')+'>'+y+' 年</option>';}).join('');
    var learnSub=rv.dueCount?('今天有 '+rv.dueCount+' 題到期，先處理最值得。'):(rv.activeCount?('還有 '+rv.activeCount+' 題尚未熟練。'):'查看錯題、弱點與學習進度。');
    var scopeHint=homeQuizScope==='smart'?'最近 10 年為主，近 3 年與高頻考點優先。':homeQuizScope==='specific'?'只刷你指定的年度與考次。':homeQuizScope==='all'?'從完整歷史題庫抽題。':'只從較新的歷屆題目抽題。';
    var offlineNote='';
    try{if(window.SWSI_QB&&window.SWSI_QB.usingOffline)offlineNote='<div style="margin-bottom:9px;padding:9px 12px;border:1px solid var(--line);border-radius:11px;background:#fff;font-size:var(--swsi-ui-small);color:var(--ink-soft)">目前使用這台裝置已儲存的離線題庫。</div>';}catch(_e){}

    app.innerHTML=offlineNote+
      '<section class="swsi-focus-hero"><div class="kicker">SWSI · 免費社工師國考學習平台</div><h1>今天想練什麼？</h1><p>做題、複習、申論。先完成一件就好。</p></section>'+
      '<section class="swsi-focus-primary"><div class="label">快速練題</div><h2>刷 20 題選擇題</h2><p>直接用智慧推薦開始；需要指定年度、考次或科目時再打開設定。</p><div class="swsi-focus-actions"><button class="go" onclick="swsiStartNow()">直接開始 20 題</button><button class="choose" onclick="toggleHomeQuiz()">'+(homeQuizOpen?'收起設定':'自己選範圍')+'</button></div></section>'+
      (homeQuizOpen?('<section class="swsi-focus-custom"><div class="field-label">範圍</div><select class="subj" aria-label="刷題範圍" onchange="setHomeQuizScope(this.value)" style="margin-bottom:9px"><option value="smart" '+(homeQuizScope==='smart'?'selected':'')+'>智慧推薦</option><option value="recent3" '+(homeQuizScope==='recent3'?'selected':'')+'>近 3 年</option><option value="recent5" '+(homeQuizScope==='recent5'?'selected':'')+'>近 5 年</option><option value="specific" '+(homeQuizScope==='specific'?'selected':'')+'>指定歷屆</option><option value="all" '+(homeQuizScope==='all'?'selected':'')+'>全部題庫</option></select>'+(specific?('<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><select class="subj" aria-label="考試年度" onchange="setHomeQuizYear(this.value)" style="margin-bottom:9px">'+yearOpts+'</select><select class="subj" aria-label="考試考次" onchange="setHomeQuizRound(this.value)" style="margin-bottom:9px"><option value="all" '+(homeQuizRound==='all'?'selected':'')+'>全部考次</option><option value="1" '+(homeQuizRound==='1'?'selected':'')+'>第一次</option><option value="2" '+(homeQuizRound==='2'?'selected':'')+'>第二次</option></select></div>'):'')+'<div class="field-label">科目</div><select class="subj" aria-label="科目" onchange="subjFilter=this.value;render()" style="margin-bottom:9px">'+subjOpts+'</select><div class="field-label">題數</div><select class="subj" aria-label="題數" onchange="setHomeQuizCount(this.value)" style="margin-bottom:7px"><option value="10" '+(homeQuizCount===10?'selected':'')+'>10 題</option><option value="20" '+(homeQuizCount===20?'selected':'')+'>20 題</option><option value="40" '+(homeQuizCount===40?'selected':'')+'>40 題</option></select><div class="hint">'+swsiEsc(scopeHint)+'</div><button class="btn" onclick="startFocusedQuiz()" style="margin-top:2px">開始這組題目</button></section>'):'')+
      '<button class="swsi-study-card '+(rv.dueCount?'due':'')+'" onclick="go(\'progress\')"><span class="copy"><span class="title">學習中心</span><span class="sub">'+swsiEsc(learnSub)+'</span></span>'+(rv.dueCount?'<span class="count">'+rv.dueCount+' 題</span>':'<span class="aside">›</span>')+'</button>'+
      '<button class="swsi-study-card" onclick="go(\'essay\')"><span class="copy"><span class="title">申論練習</span><span class="sub">歷屆申論、時事題材、草稿與 AI 練習回饋。</span></span><span class="aside">›</span></button>'+
      '<details class="swsi-other-tools"><summary>更多練習方式</summary><div class="swsi-other-grid"><button onclick="MK.open()">計時模擬考</button><button onclick="go(\'topics\')">理論、法規與時事</button></div></details>'+
      '<div class="swsi-principle-note">核心備考功能免費 · 不鎖答案 · 不用點數</div>';

    if(typeof relabelTabs==='function')try{relabelTabs();}catch(_e){}
  };

  installStyle();
  try{if(typeof view!=='undefined'&&view==='home')render();}catch(_e){}
})();

/* SWSI Focused Quiz UI 2026-08-26
   Presentation-only pass: make practice feel calm, direct, and study-first.
*/
(function(){
  if(document.getElementById('swsi-focused-quiz-style')) return;
  var style=document.createElement('style');
  style.id='swsi-focused-quiz-style';
  style.textContent=`
/* When a quiz is open, remove unrelated navigation noise. */
body:has(#app .qcard) .tabbar{display:none!important;}
body:has(#app .qcard) .wrap{padding-bottom:28px!important;}
body:has(#app .qcard) header{box-shadow:none;border-bottom:1px solid rgba(220,228,223,.75);}

/* Progress = orientation, not competition. */
#app .pstrip{gap:10px;margin:2px 0 13px;}
#app .pbar{height:3px;background:#E3E9E5;}
#app .pbar i{background:var(--pine);box-shadow:none;}
#app .pcount{font-family:'Noto Sans TC',sans-serif;font-size:var(--fs-s);font-weight:500;color:var(--ink-soft);}
#app .quit{font-family:'Noto Sans TC',sans-serif;text-decoration:none;color:var(--ink-soft);opacity:.8;margin-bottom:10px;}
#app .quit:hover{color:var(--ink);}

/* The question itself should own the page. */
#app .qcard{background:#fff;border:1px solid #E4E9E6;border-radius:18px;padding:22px 18px 20px;box-shadow:0 3px 16px rgba(42,44,42,.035);}
#app .qmeta{gap:6px;margin-bottom:14px;}
#app .tag{font-family:'Noto Sans TC',sans-serif;font-size:var(--fs-s);font-weight:600;line-height:1.25;padding:4px 8px;border-radius:999px;}
#app .tag.subj{background:#EAF1EE;color:var(--pine-deep);}
#app .tag.year{background:#F3F4F1;color:var(--ink-soft);}
#app .qtext{font-family:'Noto Serif TC',serif;font-weight:600;line-height:1.8;margin:0 0 21px;color:#202421;letter-spacing:.01em;}

/* Answers should read like four clean choices, not game buttons. */
#app .opt{position:relative;background:#FBFCFB;border:1px solid #DFE5E1;border-radius:14px;padding:14px 14px 14px 13px;margin-bottom:10px;gap:11px;min-height:54px;align-items:flex-start;line-height:1.65;box-shadow:none;}
#app .opt:hover{border-color:#BFCFC8;background:#F8FAF9;}
#app .opt .lab{display:grid;place-items:center;flex:0 0 auto;width:28px;height:28px;margin-top:0;border:1px solid #D6DEDA;border-radius:50%;font-family:'Noto Sans TC',sans-serif;font-size:12px;font-weight:700;color:#66706B;background:#fff;}
#app .opt.sel{border-color:var(--pine);background:#F0F6F3;}
#app .opt.sel .lab{border-color:var(--pine);background:var(--pine);color:#fff;}
#app .opt.correct{border-color:#AFCAC0;background:#EFF6F3;}
#app .opt.correct .lab{border-color:var(--correct);background:var(--correct);color:#fff;}
#app .opt.wrong{border-color:#D8BDB6;background:#FAF2EF;}
#app .opt.wrong .lab{border-color:var(--wrong);background:var(--wrong);color:#fff;}
#app .opt .mk{font-family:'Noto Sans TC',sans-serif;font-size:var(--fs-s);font-weight:600;}
#app .ck{width:18px;height:18px;font-size:10px;}

/* Primary action: plain language, no arcade-style letter spacing. */
#app .qcard > .btn,#app .qcard .btn{font-family:'Noto Sans TC',sans-serif;letter-spacing:.2px;font-size:var(--fs-b);font-weight:700;border-radius:12px;min-height:48px;margin-top:12px;box-shadow:none;}
#app .qcard .btn:not(.ghost){background:var(--pine-deep);}
#app .qcard .btn.ghost{background:#fff;border:1px solid #C9D7D1;color:var(--pine-deep);}

/* Explanation should feel like study notes, not a result screen. */
#app .exp{margin-top:22px;padding-top:20px;border-top:1px solid #E5EAE7;animation:none;}
#app .exp .topic{font-family:'Noto Sans TC',sans-serif;color:var(--ink-soft);margin-bottom:15px;}
#app .exp-sec{margin:0 0 17px;}
#app .exp-sec h4{font-family:'Noto Sans TC',sans-serif;font-size:var(--fs-h);font-weight:800;color:#34443E;letter-spacing:.1px;margin-bottom:7px;gap:0;}
#app .exp-sec h4 .dot{display:none;}
#app .exp-sec p{font-family:'Noto Sans TC',sans-serif;color:#363C38;line-height:1.8;}
#app .pending{background:#F7F8F6;border:1px solid #E2E6E3;color:var(--ink-soft);border-radius:12px;}
#app .extra{background:#FAFBFA;border:1px solid #E4E8E5;border-radius:11px;}
#app .mistake{font-family:'Noto Sans TC',sans-serif;border-radius:8px;padding:5px 8px;background:#F7EEEB;font-weight:600;}

/* Result page should inform, not rank or celebrate excessively. */
#app .sumcard{background:#fff;border:1px solid #E3E8E5;box-shadow:none;}
#app .sumcard .big{font-size:38px;color:var(--ink);}
#app .stat{background:#FAFBFA;border-color:#E4E8E5;}
#app .weak{background:#FAF4F2;}

@media (max-width:370px){
  #app .qcard{padding:19px 14px 18px;}
  #app .opt{padding:13px 12px;gap:9px;}
}
`;
  document.head.appendChild(style);
})();

/* SWSI Mobile Reading Polish 2026-08-26
   Feedback pass from real iPhone screenshots:
   - normal size was too large/loose for long explanations and essays
   - bottom navigation spacing is owned by 99_p0_mobile_ai_guardrails.part
   - essay formatting controls need clearer hierarchy
   - AI privacy disclosure should be available without dominating the writing flow
*/
(function(){
  if(document.getElementById('swsi-mobile-reading-polish')) return;

  var style=document.createElement('style');
  style.id='swsi-mobile-reading-polish';
  style.textContent=`
html{
  --fs-q:13pt;
  --fs-h:12pt;
  --fs-b:11pt;
  --fs-s:10pt;
}
html[data-fs="1"]{
  --fs-q:14.5pt;
  --fs-h:13pt;
  --fs-b:12pt;
  --fs-s:11pt;
}
html[data-fs="2"]{
  --fs-q:16.5pt;
  --fs-h:14.5pt;
  --fs-b:13.5pt;
  --fs-s:12.5pt;
}

#app .qtext{line-height:1.72;}
#app .exp{margin-top:18px;padding-top:17px;}
#app .exp-sec{margin-bottom:14px;}
#app .exp-sec h4{margin-bottom:5px;}
#app .exp-sec p{line-height:1.72;}
#app .extra{line-height:1.68;}
#app .mistake{margin-top:4px;}

#app .wbox{margin-bottom:6px;}
#app .wlabel{margin-bottom:7px;}
#app .swsi-fmt-help{
  font-family:'Noto Sans TC',sans-serif;
  font-size:var(--fs-s);
  color:var(--ink-soft);
  line-height:1.5;
  margin:0 0 7px;
}
#app .fmtbar{align-items:center;margin-bottom:9px;}
#app .fmtbar .fbtn{min-height:38px;padding:6px 10px;}
#app .fmtbar .fbtn.clear,
#app .fmtbar .swsi-clear-btn{
  margin-left:auto;
  color:var(--wrong)!important;
  background:transparent!important;
  border-color:transparent!important;
  font-weight:600!important;
  white-space:nowrap;
}
#app .fmtbar .fbtn.clear:hover,
#app .fmtbar .swsi-clear-btn:hover{
  background:var(--wrong-bg)!important;
  border-color:rgba(158,97,85,.25)!important;
}
#app .wta{line-height:1.78;min-height:190px;}

#app .swsi-ai-privacy{
  margin:0 0 10px;
  border:1px solid var(--line);
  border-radius:10px;
  background:#FBFCFB;
  overflow:hidden;
}
#app .swsi-ai-privacy summary{
  min-height:44px;
  padding:10px 12px;
  cursor:pointer;
  list-style:none;
  display:flex;
  align-items:center;
  gap:7px;
  font-family:'Noto Sans TC',sans-serif;
  font-size:var(--fs-s);
  font-weight:700;
  color:var(--ink-soft);
}
#app .swsi-ai-privacy summary::-webkit-details-marker{display:none;}
#app .swsi-ai-privacy summary:after{content:'展開';margin-left:auto;font-weight:500;color:var(--pine);}
#app .swsi-ai-privacy[open] summary:after{content:'收起';}
#app .swsi-ai-privacy .swsi-ai-privacy-body{
  border-top:1px solid var(--line);
  padding:10px 12px 11px;
  font-family:'Noto Sans TC',sans-serif;
  font-size:var(--fs-s);
  line-height:1.7;
  color:var(--ink-soft);
}
#app .swsi-ai-privacy .swsi-ai-privacy-body b{color:var(--wrong);}

@media (max-width:370px){
  #app .fmtbar{gap:5px;}
  #app .fmtbar .fbtn{padding-left:8px;padding-right:8px;}
}
`;
  document.head.appendChild(style);

  function polishEssayUI(root){
    root=root||document;

    root.querySelectorAll('.wbox').forEach(function(box){
      var bar=box.querySelector('.fmtbar');
      if(bar && !box.querySelector('.swsi-fmt-help')){
        var help=document.createElement('div');
        help.className='swsi-fmt-help';
        help.textContent='點一下插入答題層級';
        bar.parentNode.insertBefore(help,bar);
      }
      var clear=box.querySelector('.fmtbar .fbtn.clear');
      if(clear){
        if(!clear.classList.contains('swsi-clear-btn')) clear.classList.add('swsi-clear-btn');
        /* textContent mutates child nodes even when the text is identical. Guard it so
           the childList observer cannot recursively wake itself forever. */
        if(clear.textContent!=='清除作答') clear.textContent='清除作答';
        if(clear.getAttribute('aria-label')!=='清除這題作答') clear.setAttribute('aria-label','清除這題作答');
        if(clear.getAttribute('title')!=='清除這題作答（會再次確認）') clear.setAttribute('title','清除這題作答（會再次確認）');
      }
    });

    root.querySelectorAll('.aihelp').forEach(function(node){
      if(node.dataset.swsiPrivacyHandled==='1') return;
      var text=(node.textContent||'').trim();
      if(text.indexOf('照片／文字會送至外部 AI 服務處理')===-1) return;

      var next=node.nextElementSibling;
      var official='平台提供的是申論練習回饋，並非考選部官方評分。';
      if(next && (next.textContent||'').indexOf('申論練習回饋')!==-1){
        official=(next.textContent||'').replace(/^💡\s*/,'').trim();
        next.remove();
      }

      var details=document.createElement('details');
      details.className='swsi-ai-privacy';
      details.innerHTML='<summary>🔒 使用 AI 回饋前請先閱讀隱私說明</summary>'+
        '<div class="swsi-ai-privacy-body"><b>照片與文字會送至外部 AI 服務處理。</b> 請勿輸入或上傳可識別真實個案或個人的資料；需要舉例時請先匿名化。<br>'+swsiEsc(official)+'</div>';
      node.dataset.swsiPrivacyHandled='1';
      node.replaceWith(details);
    });
  }

  var appNode=document.getElementById('app');
  if(appNode){
    polishEssayUI(appNode);
    var observer=new MutationObserver(function(){ polishEssayUI(appNode); });
    observer.observe(appNode,{childList:true,subtree:true});
  }
})();

/* SWSI Essay Entry Binding 2026-08-29
   Layer 3 only: bind essay-entry controls.
   Global shell spacing is owned exclusively by 15.layout-foundation.part.
*/
(function(){
  'use strict';

  /* Essay navigation is owned by zzz_fix_essay_navigation.part. This module only binds entry controls. */
  function bindEssayEntries(root){
    var tab=document.getElementById('t-essay');
    if(tab && tab.dataset.swsiEssayBound!=='1'){
      tab.dataset.swsiEssayBound='1';
      tab.onclick=function(ev){ if(ev) ev.preventDefault(); window.swsiOpenEssay(); };
    }

    (root||document).querySelectorAll('.swsi-study-card').forEach(function(btn){
      var title=btn.querySelector('.title');
      if(!title || (title.textContent||'').indexOf('申論')===-1) return;
      btn.dataset.swsiEssayBound='1';
      btn.onclick=function(ev){ if(ev) ev.preventDefault(); window.swsiOpenEssay(); };
    });
  }

  bindEssayEntries(document);
  var appNode=document.getElementById('app');
  if(appNode){
    new MutationObserver(function(){ bindEssayEntries(appNode); }).observe(appNode,{childList:true,subtree:true});
  }
})();
/* ===== SWSI Storage Durability Guard 2026-08-27 ===== */
(function(){
  'use strict';

  var HISTORY_KEY='swsi_v2_history';
  var REVIEW_KEY_LOCAL='swsi_review_v2';
  var HISTORY_MAX_RECORDS=8000;
  var historyWriteBlocked=false;
  var reviewWriteBlocked=false;

  function storageWarning(message){
    window.__swsiStorageWarning=String(message||'學習進度無法儲存，請先不要清除瀏覽器資料。');
    try{
      var id='swsi-storage-warning';
      var el=document.getElementById(id);
      if(!el){
        el=document.createElement('div');
        el.id=id;
        el.setAttribute('role','alert');
        el.style.cssText='position:fixed;left:12px;right:12px;top:12px;z-index:2147483000;max-width:720px;margin:0 auto;padding:11px 14px;border-radius:12px;background:#fff4e5;color:#7a3f00;border:1px solid #e4b56c;box-shadow:0 8px 28px rgba(0,0,0,.18);font-size:14px;line-height:1.55;font-weight:700';
        document.body.appendChild(el);
      }
      el.textContent='⚠ '+window.__swsiStorageWarning;
      el.style.display='block';
    }catch(_e){}
  }

  function clearStorageWarning(){
    try{
      var el=document.getElementById('swsi-storage-warning');
      if(el)el.style.display='none';
      window.__swsiStorageWarning='';
    }catch(_e){}
  }

  function compactHistory(input){
    var h=Array.isArray(input)?input:[];
    if(h.length<=HISTORY_MAX_RECORDS)return h;
    return h.slice(h.length-HISTORY_MAX_RECORDS);
  }

  function validHistoryRow(row){
    return !!row
      &&typeof row==='object'
      &&!Array.isArray(row)
      &&typeof row.id==='string'
      &&!!row.id.trim()
      &&typeof row.correct==='boolean'
      &&Number.isFinite(Number(row.ts))
      &&Number(row.ts)>=0;
  }

  function validHistory(input){
    return Array.isArray(input)&&input.every(validHistoryRow);
  }

  function optionalNonNegativeNumber(value){
    return value===undefined
      ||value===null
      ||(Number.isFinite(Number(value))&&Number(value)>=0);
  }

  function validReviewItem(key,item){
    if(!item||typeof item!=='object'||Array.isArray(item))return false;
    if(typeof item.id!=='string'||!item.id.trim()||item.id!==key)return false;
    var numeric=['streak','wrongCount','correctCount','dueAt','lastAt','masteredAt','maintenanceStep'];
    if(numeric.some(function(name){return !optionalNonNegativeNumber(item[name]);}))return false;
    if(item.mastered!==undefined&&typeof item.mastered!=='boolean')return false;
    if(item.maintenanceDone!==undefined&&typeof item.maintenanceDone!=='boolean')return false;
    return item.lastResult===undefined||item.lastResult==='wrong'||item.lastResult==='correct';
  }

  function validReviewState(state){
    return !!state
      &&typeof state==='object'
      &&!Array.isArray(state)
      &&state.version===2
      &&state.items
      &&typeof state.items==='object'
      &&!Array.isArray(state.items)
      &&(state.migratedFromHistory===undefined||typeof state.migratedFromHistory==='boolean')
      &&Object.keys(state.items).every(function(key){return validReviewItem(key,state.items[key]);});
  }

  function quarantineCorruptStorage(key,raw,label){
    if(!raw)return true;
    var backupKey=key+'_corrupt_backup_'+Date.now();
    try{
      localStorage.setItem(backupKey,raw);
      localStorage.removeItem(key);
      storageWarning('偵測到損壞的'+label+'，已保留原始備份並建立乾淨資料。請勿清除瀏覽器資料。');
      return true;
    }catch(err){
      storageWarning(label+'格式損壞且無法建立備份。為避免覆寫原始資料，本次不會再儲存新的紀錄。');
      try{console.warn('SWSI corrupt storage backup failed',err);}catch(_e){}
      return false;
    }
  }

  function durableLoadHist(){
    var raw='';
    try{
      raw=localStorage.getItem(HISTORY_KEY)||'';
      if(!raw){historyWriteBlocked=false;return [];}
      var parsed=JSON.parse(raw);
      if(!validHistory(parsed))throw new Error('history schema invalid');
      historyWriteBlocked=false;
      return parsed;
    }catch(err){
      try{console.warn('SWSI history schema invalid',err);}catch(_e){}
      historyWriteBlocked=!quarantineCorruptStorage(HISTORY_KEY,raw,'學習歷程');
      return [];
    }
  }

  function durableLoadReviewState(){
    var empty={version:2,migratedFromHistory:false,items:{}};
    var raw='';
    try{
      raw=localStorage.getItem(REVIEW_KEY_LOCAL)||'';
      if(!raw){reviewWriteBlocked=false;return empty;}
      var parsed=JSON.parse(raw);
      if(!validReviewState(parsed))throw new Error('review state schema invalid');
      reviewWriteBlocked=false;
      return parsed;
    }catch(err){
      try{console.warn('SWSI review-state schema invalid',err);}catch(_e){}
      reviewWriteBlocked=!quarantineCorruptStorage(REVIEW_KEY_LOCAL,raw,'複習排程');
      return empty;
    }
  }

  function durableSaveHist(input){
    if(historyWriteBlocked){
      storageWarning('原始學習歷程尚未安全備份；為避免資料遺失，本次不會覆寫。');
      return false;
    }
    if(!validHistory(input)){
      storageWarning('新的學習歷程格式異常，已停止寫入以保護原有資料。');
      return false;
    }
    var compacted=compactHistory(input);
    try{
      localStorage.setItem(HISTORY_KEY,JSON.stringify(compacted));
      return true;
    }catch(err){
      storageWarning('學習歷程儲存失敗，這次作答可能不會被記錄。請先備份重要內容，並釋放瀏覽器儲存空間後再繼續。');
      try{console.warn('SWSI history storage failed',err);}catch(_e){}
      return false;
    }
  }

  function durableSaveReviewState(state){
    if(reviewWriteBlocked){
      storageWarning('原始複習排程尚未安全備份；為避免資料遺失，本次不會覆寫。');
      return false;
    }
    if(!validReviewState(state)){
      storageWarning('新的複習排程格式異常，已停止寫入以保護原有資料。');
      return false;
    }
    try{
      localStorage.setItem(REVIEW_KEY_LOCAL,JSON.stringify(state));
      return true;
    }catch(err){
      storageWarning('複習進度儲存失敗，間隔複習排程可能無法更新。請先備份重要內容，並釋放瀏覽器儲存空間後再繼續。');
      try{console.warn('SWSI review storage failed',err);}catch(_e){}
      return false;
    }
  }

  try{loadHist=durableLoadHist;}catch(_e){}
  window.loadHist=durableLoadHist;
  try{loadReviewState=durableLoadReviewState;}catch(_e){}
  window.loadReviewState=durableLoadReviewState;
  try{saveHist=durableSaveHist;}catch(_e){}
  window.saveHist=durableSaveHist;
  try{saveReviewState=durableSaveReviewState;}catch(_e){}
  window.saveReviewState=durableSaveReviewState;

  window.swsiStorageDurability={
    version:'2026-08-27.schema-guard.v3',
    historyMaxRecords:HISTORY_MAX_RECORDS,
    compactHistory:compactHistory,
    validateHistory:validHistory,
    validateReviewState:validReviewState,
    showWarning:storageWarning,
    clearWarning:clearStorageWarning
  };
  window.swsiStorageDurabilityVersion='2026-08-27.schema-guard.v3';
})();
/* ===== SWSI Storage Durability Guard END ===== */

/* SWSI Learning Loop V1 2026-08-26
   Wrong answers -> self reflection -> spaced review -> useful progress.
   This layer NEVER edits official exam question text or official answer data.
*/
(function(){
  'use strict';
  var CAUSE_KEY='swsi_wrong_cause_v1';
  var CAUSES=['概念不熟','看錯題目','兩個選項猶豫','法規／數字記錯','其實是猜的'];
  var DAY=24*60*60*1000;

  function H(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function loadCauses(){try{var x=JSON.parse(localStorage.getItem(CAUSE_KEY)||'{}');return x&&typeof x==='object'?x:{};}catch(_e){return {};}}
  function saveCauses(x){try{localStorage.setItem(CAUSE_KEY,JSON.stringify(x));}catch(_e){}}
  function draftCount(){var n=0;try{for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);if(k&&k.indexOf('essay_draft_')===0&&(localStorage.getItem(k)||'').trim())n++;}}catch(_e){}return n;}
  function questionCorrect(item,picked){try{if(typeof isCorrectAnswer==='function')return !!isCorrectAnswer(item,picked);}catch(_e){}try{if(typeof ansCorrect==='function')return !!ansCorrect(picked,item.answer);}catch(_e){}return String(picked||'')===String(item&&item.answer||'');}

  function causeButton(id,cause,current){var on=current===cause;return '<button type="button" class="swsi-cause-chip'+(on?' on':'')+'" onclick="swsiSetWrongCause(\''+H(id)+'\',\''+H(cause)+'\')">'+H(cause)+(on?' ✓':'')+'</button>';}
  function decorateWrongCause(){
    var exp=document.querySelector('#app .qcard .exp'); if(!exp)return;
    var item=null,picked=null,isAnswered=false;
    try{item=queue&&queue[idx];picked=selected;isAnswered=!!answered;}catch(_e){}
    if(!item||!isAnswered||questionCorrect(item,picked)){var old=exp.querySelector('.swsi-self-cause');if(old)old.remove();return;}
    var cur=(loadCauses()[item.id]||{}).cause||'';
    var key=String(item.id)+'|'+cur;
    var box=exp.querySelector('.swsi-self-cause');
    if(box&&box.dataset.swsiCauseKey===key)return;
    if(!box){box=document.createElement('section');box.className='swsi-self-cause';var next=exp.querySelector(':scope > .btn');if(next)exp.insertBefore(box,next);else exp.appendChild(box);}
    /* Set marker BEFORE changing children so our MutationObserver cannot trigger itself forever. */
    box.dataset.swsiCauseKey=key;
    box.innerHTML='<div class="swsi-cause-title">這題你為什麼會錯？</div><div class="swsi-cause-help">點一下就好，只存在這台裝置。之後錯題本會依你的原因整理。</div><div class="swsi-cause-row">'+CAUSES.map(function(c){return causeButton(item.id,c,cur);}).join('')+'</div>';
  }
  window.swsiSetWrongCause=function(id,cause){var m=loadCauses();if(m[id]&&m[id].cause===cause)delete m[id];else m[id]={cause:cause,ts:Date.now()};saveCauses(m);decorateWrongCause();};

  function setFromIds(ids){var s=new Set(ids||[]);startQuiz(function(q){return s.has(q.id);},0);}
  window.swsiPracticeReviewSet=function(i){var sets=window._swsiReviewSets||[];if(sets[i])setFromIds(sets[i].ids);};
  window.swsiPracticeSubject=function(subj,n){startQuiz(function(q){return q.subject===subj;},n||20);};
  window.swsiPracticeTopic=function(topic,n){startQuiz(function(q){return (q.topic||q.major||'')===topic;},n||15);};
  window.swsiStartRecommended20=function(){startQuiz(function(){return true;},20);};
  function questionMap(ids){return (ids||[]).map(function(id){try{return ALL.find(function(q){return q.id===id;});}catch(_e){return null;}}).filter(Boolean);}
  function groupPush(obj,key,q){key=key||'未分類';(obj[key]=obj[key]||[]).push(q);}

  renderReview=function(){
    var rv=reviewSummary(),ids=rv.activeIds||[],wrongQs=questionMap(ids),causes=loadCauses();
    if(!ids.length&&!rv.dueCount&&!rv.nextDueAt){app.innerHTML='<div class="empty"><div class="ico">✓</div><h3>'+(rv.masteredCount?'目前沒有待複習題':'還沒有錯題')+'</h3><p>'+(rv.masteredCount?('已經有 '+rv.masteredCount+' 題完成錯題學習與長期確認。<br>之後再答錯仍會重新排入複習。'):'開始刷題後，答錯題會自動進入間隔複習。<br>你也可以自己標記「為什麼會錯」。')+'</p><button class="btn" style="max-width:200px;margin:22px auto 0" onclick="go(\'home\')">開始刷題</button><button class="btn ghost" style="max-width:200px;margin:10px auto 0" onclick="go(\'progress\')">看看我的進度</button></div>';return;}
    var byCause={},unmarked=[],byTopic={};
    wrongQs.forEach(function(q){var c=causes[q.id]&&causes[q.id].cause;if(c)groupPush(byCause,c,q);else unmarked.push(q);groupPush(byTopic,q.topic||q.major||'未分類',q);});
    var causeGroups=Object.entries(byCause).sort(function(a,b){return b[1].length-a[1].length;});
    var topicGroups=Object.entries(byTopic).sort(function(a,b){return b[1].length-a[1].length;}).slice(0,5);
    window._swsiReviewSets=[{label:'全部未熟練錯題',ids:ids.slice()}];
    causeGroups.forEach(function(x){window._swsiReviewSets.push({label:x[0],ids:x[1].map(function(q){return q.id;})});});
    var topicBase=1+causeGroups.length;
    topicGroups.forEach(function(x){window._swsiReviewSets.push({label:x[0],ids:x[1].map(function(q){return q.id;})});});
    var h='<div class="section-h">錯題複習</div><div class="section-s">先處理今天到期的，再看看自己到底為什麼常錯。沒有排行榜，也不用追連勝。</div>';
    h+='<div class="statrow swsi-review-stats"><div class="stat"><div class="v" style="color:var(--wrong)">'+rv.dueCount+'</div><div class="k">今天到期</div></div><div class="stat"><div class="v">'+rv.activeCount+'</div><div class="k">還沒熟</div></div><div class="stat"><div class="v" style="color:var(--correct)">'+rv.masteredCount+'</div><div class="k">已掌握</div></div></div>';
    if(rv.dueCount)h+='<button class="btn" onclick="startDueReview()">先複習今天這 '+rv.dueCount+' 題</button>';else if(rv.nextDueAt)h+='<div class="swsi-calm-note">✓ 今天沒有到期題，下一批 '+H(reviewDueLabel(rv.nextDueAt))+'。</div>';
    if(wrongQs.length)h+='<button class="btn ghost" onclick="swsiPracticeReviewSet(0)" style="margin-top:9px">重練全部未熟練錯題（'+wrongQs.length+' 題）</button>';
    h+='<section class="swsi-learning-section"><div class="swsi-learning-h">你自己標記的錯因</div>';
    if(causeGroups.length){causeGroups.forEach(function(x,i){h+='<button class="swsi-learning-row" onclick="swsiPracticeReviewSet('+(1+i)+')"><span><b>'+H(x[0])+'</b><small>'+x[1].length+' 題</small></span><span>›</span></button>';});if(unmarked.length)h+='<div class="swsi-learning-muted">另外有 '+unmarked.length+' 題還沒標記原因。下次答錯時可以順手點一下。</div>';}else h+='<div class="swsi-learning-muted">你還沒標記過錯因。下一次答錯後，解析下方會出現「概念不熟／看錯題目／兩個選項猶豫…」讓你點一下。</div>';
    h+='</section>';
    if(topicGroups.length){h+='<section class="swsi-learning-section"><div class="swsi-learning-h">平台看到的弱點考點</div><div class="swsi-learning-muted" style="margin-bottom:8px">這是依你目前未熟練的題目分類，不代表平台知道你本人為什麼答錯。</div>';topicGroups.forEach(function(x,i){h+='<button class="swsi-learning-row" onclick="swsiPracticeReviewSet('+(topicBase+i)+')"><span><b>'+H(x[0])+'</b><small>目前 '+x[1].length+' 題未熟練</small></span><span>›</span></button>';});h+='</section>';}
    h+='<button class="btn ghost" style="margin-top:18px" onclick="go(\'progress\')">查看完整學習進度</button>';app.innerHTML=h;
  };

  function progressData(){
    var h=loadHist(),now=Date.now(),recent=h.filter(function(x){return Number(x.ts||0)>=now-7*DAY;}),bySubj={},wrongTopic={},byCause={},unique=new Set();
    h.forEach(function(x){if(x&&x.id)unique.add(x.id);var s=x.subject||'未分類';if(!bySubj[s])bySubj[s]={t:0,c:0};bySubj[s].t++;if(x.correct)bySubj[s].c++;if(!x.correct){var q=null;try{q=ALL.find(function(z){return z.id===x.id;});}catch(_e){}var t=(q&&(q.topic||q.major))||x.major||'未分類';wrongTopic[t]=(wrongTopic[t]||0)+1;}});
    var cm=loadCauses();Object.keys(cm).forEach(function(id){var c=cm[id]&&cm[id].cause;if(c)byCause[c]=(byCause[c]||0)+1;});
    return {hist:h,recent:recent,bySubj:bySubj,wrongTopic:wrongTopic,byCause:byCause,unique:unique};
  }
  function pct(c,t){return t?Math.round(c/t*100):0;}

  renderProgress=function(){
    var p=progressData(),total=p.hist.length,rv=reviewSummary(),essays=draftCount();
    if(!total){app.innerHTML='<div class="empty"><div class="ico">◴</div><h3>還沒有刷題紀錄</h3><p>開始刷題後，這裡會告訴你哪一科比較弱、最近有沒有進步，以及下一步建議做什麼。</p><button class="btn" style="max-width:200px;margin:22px auto 0" onclick="swsiStartRecommended20()">先刷 20 題</button>'+(essays?'<div style="margin-top:14px;color:var(--ink-soft);font-size:13px">這台裝置目前有 '+essays+' 題申論作答草稿。</div>':'')+'</div>';return;}
    var correct=p.hist.filter(function(x){return x.correct;}).length,rate=pct(correct,total),rc=p.recent.filter(function(x){return x.correct;}).length,rr=p.recent.length?pct(rc,p.recent.length):null;
    var allCount=0;try{allCount=ALL.length||0;}catch(_e){}var coverage=allCount?Math.min(100,Math.round(p.unique.size/allCount*100)):0;
    var subjects=Object.entries(p.bySubj).map(function(x){return {name:x[0],t:x[1].t,c:x[1].c,r:pct(x[1].c,x[1].t)};}).sort(function(a,b){return a.r-b.r||b.t-a.t;});
    var weak=subjects.filter(function(x){return x.t>=5;})[0]||subjects[0];
    var topTopics=Object.entries(p.wrongTopic).sort(function(a,b){return b[1]-a[1];}).slice(0,5),causeRows=Object.entries(p.byCause).sort(function(a,b){return b[1]-a[1];});
    var action='';
    if(rv.dueCount)action='<div class="swsi-next-copy"><b>先把今天到期的錯題處理掉。</b><span>間隔複習比再刷一堆新題更值得。</span></div><button class="btn" onclick="startDueReview()">複習 '+rv.dueCount+' 題</button>';
    else if(weak)action='<div class="swsi-next-copy"><b>目前最值得補：'+H(weak.name)+'</b><span>你在這科目前 '+weak.r+'%（'+weak.c+'/'+weak.t+'）。先用 20 題再確認一次。</span></div><button class="btn" onclick="swsiPracticeSubject(\''+H(weak.name)+'\',20)">練 '+H(weak.name)+' 20 題</button>';
    else action='<div class="swsi-next-copy"><b>繼續累積一點資料。</b><span>再刷 20 題後，弱點判斷會更有參考價值。</span></div><button class="btn" onclick="swsiStartRecommended20()">繼續刷 20 題</button>';
    var subjHTML=subjects.map(function(s){var col=s.r>=70?'var(--correct)':s.r>=50?'var(--gold)':'var(--wrong)';return '<button class="swsi-progress-subject" onclick="swsiPracticeSubject(\''+H(s.name)+'\',20)"><div class="top"><b>'+H(s.name)+'</b><span>'+s.r+'%　('+s.c+'/'+s.t+')</span></div><div class="accbar"><i style="width:'+s.r+'%;background:'+col+'"></i></div><small>點一下練這科 20 題</small></button>';}).join('');
    var h='<div class="section-h">我的學習進度</div><div class="section-s">只看能幫你決定下一步的數據。重複作答會算進正確率；「題庫覆蓋」則同一題只算一次。</div>';
    h+='<section class="swsi-progress-hero"><div><small>總正確率</small><strong>'+rate+'%</strong></div><div class="swsi-progress-mini"><span><b>'+total+'</b>作答次數</span><span><b>'+p.unique.size+'</b>不同題目</span><span><b>'+coverage+'%</b>題庫覆蓋</span></div></section>';
    h+='<div class="swsi-progress-strip"><div><b>'+(rr==null?'—':rr+'%')+'</b><span>最近 7 天'+(p.recent.length?' · '+p.recent.length+' 題':' · 尚無紀錄')+'</span></div><div><b>'+rv.activeCount+'</b><span>未熟練錯題</span></div><div><b>'+essays+'</b><span>申論草稿</span></div></div>';
    h+='<section class="swsi-next-card"><div class="swsi-learning-h">今天下一步</div>'+action+'</section><section class="swsi-learning-section"><div class="swsi-learning-h">各科狀況</div>'+subjHTML+'</section>';
    if(topTopics.length)h+='<section class="swsi-learning-section"><div class="swsi-learning-h">最常答錯的考點</div>'+topTopics.map(function(x){return '<button class="swsi-learning-row" onclick="swsiPracticeTopic(\''+H(x[0])+'\',15)"><span><b>'+H(x[0])+'</b><small>累計錯 '+x[1]+' 次</small></span><span>›</span></button>';}).join('')+'</section>';
    if(causeRows.length)h+='<section class="swsi-learning-section"><div class="swsi-learning-h">你自己標記的錯因</div>'+causeRows.map(function(x){return '<div class="swsi-cause-stat"><span>'+H(x[0])+'</span><b>'+x[1]+' 題</b></div>';}).join('')+'</section>';
    h+='<div class="swsi-progress-foot"><button class="btn ghost" onclick="go(\'review\')">回錯題複習</button><button class="btn ghost" onclick="exportDrafts()">備份申論草稿</button><button class="swsi-danger-link" onclick="if(confirm(\'清除所有刷題、間隔複習與自訂錯因紀錄？無法復原。\')){localStorage.removeItem(LS_KEY);localStorage.removeItem(REVIEW_KEY);localStorage.removeItem(\''+CAUSE_KEY+'\');render();}">清除學習紀錄</button></div>';app.innerHTML=h;
  };

  function decorateHomeProgressEntry(){
    var grid=document.querySelector('#app .swsi-other-grid');
    if(!grid||grid.querySelector('.swsi-progress-entry'))return;
    var b=document.createElement('button');
    b.className='swsi-progress-entry';
    b.textContent='我的學習進度';
    b.onclick=function(){go('progress');};
    grid.appendChild(b);
  }

  if(!document.getElementById('swsi-learning-loop-style')){var st=document.createElement('style');st.id='swsi-learning-loop-style';st.textContent=`
    .swsi-self-cause{margin:15px 0 12px;padding:13px;border:1px solid var(--line);border-radius:13px;background:#F8FAF9}.swsi-cause-title{font-size:var(--fs-b);font-weight:800;color:var(--ink);margin-bottom:3px}.swsi-cause-help{font-size:var(--fs-s);line-height:1.6;color:var(--ink-soft);margin-bottom:9px}.swsi-cause-row{display:flex;flex-wrap:wrap;gap:6px}.swsi-cause-chip{border:1px solid var(--line);background:#fff;color:var(--ink-soft);border-radius:999px;padding:7px 10px;font-family:inherit;font-size:var(--fs-s);font-weight:700;cursor:pointer}.swsi-cause-chip.on{border-color:var(--pine);background:var(--correct-bg);color:var(--pine-deep)}
    .swsi-review-stats{margin:15px 0 16px}.swsi-calm-note{margin:10px 0 0;padding:11px 13px;border:1px solid var(--line);border-radius:11px;background:#fff;color:var(--ink-soft);font-size:13px;line-height:1.6}.swsi-learning-section{margin-top:20px}.swsi-learning-h{font-size:14px;font-weight:900;color:var(--ink);margin:0 0 9px}.swsi-learning-muted{font-size:12px;line-height:1.65;color:var(--ink-soft);padding:2px 2px 8px}.swsi-learning-row{width:100%;display:flex;align-items:center;justify-content:space-between;gap:10px;text-align:left;border:1px solid var(--line);background:#fff;border-radius:12px;padding:11px 13px;margin-bottom:7px;color:var(--ink);font-family:inherit;cursor:pointer}.swsi-learning-row b{display:block;font-size:13.5px;line-height:1.45}.swsi-learning-row small{display:block;font-size:11.5px;color:var(--ink-soft);margin-top:2px}
    .swsi-progress-hero{margin-top:13px;border:1px solid var(--line);border-radius:17px;background:#fff;padding:16px}.swsi-progress-hero>div:first-child small{display:block;color:var(--ink-soft);font-size:12px}.swsi-progress-hero strong{display:block;font-size:36px;line-height:1.15;color:var(--pine-deep);margin:3px 0 13px}.swsi-progress-mini{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.swsi-progress-mini span{background:var(--paper2);border-radius:10px;padding:9px 6px;text-align:center;font-size:10.5px;color:var(--ink-soft)}.swsi-progress-mini b{display:block;color:var(--ink);font-size:14px;margin-bottom:1px}.swsi-progress-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:8px}.swsi-progress-strip>div{border:1px solid var(--line);border-radius:12px;background:#fff;padding:10px 7px;text-align:center}.swsi-progress-strip b{display:block;font-size:17px;color:var(--ink)}.swsi-progress-strip span{display:block;font-size:10.5px;line-height:1.4;color:var(--ink-soft);margin-top:2px}
    .swsi-next-card{margin-top:18px;padding:15px;border-radius:15px;background:var(--correct-bg);border:1px solid rgba(79,126,118,.22)}.swsi-next-copy b{display:block;font-size:14px;color:var(--pine-deep);line-height:1.45}.swsi-next-copy span{display:block;font-size:12px;line-height:1.65;color:var(--ink-soft);margin:3px 0 11px}.swsi-next-card .btn{margin:0}.swsi-progress-subject{width:100%;border:0;border-bottom:1px solid var(--line);background:transparent;padding:11px 2px;text-align:left;font-family:inherit;cursor:pointer}.swsi-progress-subject .top{display:flex;justify-content:space-between;gap:9px;font-size:13px}.swsi-progress-subject .top span{color:var(--ink-soft);white-space:nowrap}.swsi-progress-subject .accbar{margin:7px 0 4px}.swsi-progress-subject small{font-size:10.5px;color:var(--ink-3)}.swsi-cause-stat{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid var(--line);padding:10px 2px;font-size:13px}.swsi-cause-stat b{color:var(--ink-soft)}.swsi-progress-foot{margin-top:22px}.swsi-progress-foot .btn{margin-top:8px}.swsi-danger-link{display:block;width:100%;border:0;background:transparent;color:var(--wrong);font-family:inherit;font-size:12px;padding:15px 8px;cursor:pointer}
  `;document.head.appendChild(st);}

  decorateWrongCause();
  decorateHomeProgressEntry();
  try{var scheduled=false;var mo=new MutationObserver(function(){if(scheduled)return;scheduled=true;Promise.resolve().then(function(){scheduled=false;decorateWrongCause();decorateHomeProgressEntry();});});mo.observe(document.body,{childList:true,subtree:true});}catch(_e){}
  try{if(typeof view!=='undefined'&&(view==='home'||view==='review'||view==='progress'))render();}catch(_e){}
})();

/* SWSI Learning Center V3 2026-08-29
   Personal study hub: review, progress, quiz and essay in one place.
   The hub renders immediately from local learning state and never requires a full
   4,800-question load just to open the second tab.
*/
(function(){
  'use strict';

  var SUPABASE_PROJECT_REF='yumjtrdctaxyczpspuyo';
  var SUPABASE_URL='https://'+SUPABASE_PROJECT_REF+'.supabase.co';
  var SUPABASE_PUBLISHABLE_KEY='sb_publishable_6KL-X7KfkcfyP1kLxfokhA_0h2YuYMr';
  var ADMIN_ENDPOINT=SUPABASE_URL+'/functions/v1/swsi-admin';
  var AUTH_STORAGE_KEY='sb-'+SUPABASE_PROJECT_REF+'-auth-token';
  var STYLE_ID='swsi-my-learning-center-v3-style';

  if(!document.getElementById(STYLE_ID)){
    var st=document.createElement('style');
    st.id=STYLE_ID;
    st.textContent=`
      .swsi-myhub{margin:0 0 16px;display:grid;gap:10px}
      .swsi-myhub-card{background:#fff;border:1px solid var(--line);border-radius:17px;padding:16px;box-shadow:0 4px 16px rgba(35,48,42,.035)}
      .swsi-myhub-kicker{font:800 10.5px/1.3 'Noto Sans TC',sans-serif;letter-spacing:1px;color:var(--pine);margin-bottom:4px}
      .swsi-myhub-title{font-family:'Noto Serif TC',serif;font-size:19px;font-weight:900;line-height:1.4;color:var(--ink);margin:0}
      .swsi-myhub-sub{font:500 11.5px/1.65 'Noto Sans TC',sans-serif;color:var(--ink-soft);margin-top:4px}
      .swsi-myhub-primary{width:100%;margin-top:13px;border:0;border-radius:13px;background:var(--pine-deep);color:#fff;min-height:48px;padding:11px 13px;text-align:left;display:flex;align-items:center;justify-content:space-between;gap:12px;cursor:pointer;font-family:'Noto Sans TC',sans-serif}
      .swsi-myhub-primary b{display:block;font-size:14px;line-height:1.4}.swsi-myhub-primary small{display:block;font-size:10.5px;line-height:1.45;opacity:.86;margin-top:2px}.swsi-myhub-primary .arrow{font-size:21px;opacity:.9}
      .swsi-myhub-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:11px}
      .swsi-myhub-stat{background:#F7F9F8;border:1px solid var(--line);border-radius:11px;padding:9px 8px;text-align:center}.swsi-myhub-stat b{display:block;font:850 17px/1.1 'Noto Sans TC',sans-serif;color:var(--ink)}.swsi-myhub-stat span{display:block;margin-top:3px;font:600 9.8px/1.35 'Noto Sans TC',sans-serif;color:var(--ink-soft)}
      .swsi-myhub-list{display:grid;margin-top:11px;border:1px solid var(--line);border-radius:13px;overflow:hidden;background:#fff}
      .swsi-myhub-row{border:0;border-bottom:1px solid var(--line);background:#fff;min-height:52px;padding:9px 11px;display:flex;align-items:center;gap:10px;width:100%;text-align:left;color:var(--ink);cursor:pointer;font-family:'Noto Sans TC',sans-serif}.swsi-myhub-row:last-child{border-bottom:0}.swsi-myhub-row .ico{width:25px;height:25px;border-radius:8px;background:#F1F5F3;color:var(--pine-deep);display:grid;place-items:center;font-weight:800;flex:0 0 auto}.swsi-myhub-row .copy{min-width:0;flex:1}.swsi-myhub-row .label{display:block;font-size:12.5px;font-weight:780;line-height:1.35}.swsi-myhub-row .meta{display:block;font-size:10.3px;line-height:1.45;color:var(--ink-soft);margin-top:2px}.swsi-myhub-row .arrow{color:#8A9690;font-size:18px}
      .swsi-myhub-more{border:1px solid var(--line);border-radius:14px;background:#FAFBFA;overflow:hidden}.swsi-myhub-more>summary{list-style:none;min-height:44px;padding:10px 12px;display:flex;align-items:center;justify-content:space-between;cursor:pointer;font:750 11.5px/1.4 'Noto Sans TC',sans-serif;color:var(--ink-soft)}.swsi-myhub-more>summary::-webkit-details-marker{display:none}.swsi-myhub-more>summary::after{content:'＋';color:var(--ink-3);font-size:16px}.swsi-myhub-more[open]>summary::after{content:'－'}.swsi-myhub-more .swsi-myhub-list{margin:0;border:0;border-top:1px solid var(--line);border-radius:0}
      .swsi-myhub-row.admin{background:#F7F9FF}.swsi-myhub-row.admin .label{color:#2747A3}.swsi-myhub-row.admin-login{background:#FBFCFB}.swsi-myhub-row.admin-login .label{font-weight:650;color:#667085}.swsi-myhub-row[hidden]{display:none!important}
      .swsi-myhub-toast{position:fixed;left:50%;bottom:calc(88px + env(safe-area-inset-bottom));transform:translateX(-50%);z-index:980;background:#27322D;color:#fff;border-radius:999px;padding:9px 13px;font:650 12px/1.3 'Noto Sans TC',sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.2)}
      .swsi-admin-layer{position:fixed;inset:0;z-index:1200;background:#F5F7FB;display:flex;flex-direction:column;padding-top:env(safe-area-inset-top)}.swsi-admin-layer[hidden]{display:none!important}.swsi-admin-bar{min-height:54px;display:flex;align-items:center;gap:10px;padding:8px 12px;border-bottom:1px solid #E5E7EB;background:#fff;box-shadow:0 2px 10px rgba(20,32,51,.05);font-family:'Noto Sans TC',sans-serif}.swsi-admin-back{border:1px solid #D7DCE3;background:#fff;color:#27322D;border-radius:11px;padding:8px 11px;font-weight:750;cursor:pointer}.swsi-admin-title{font-weight:800;color:#18202A;font-size:14px}.swsi-admin-note{margin-left:auto;color:#667085;font-size:11px}.swsi-admin-frame{border:0;width:100%;flex:1;min-height:0;background:#F5F7FB}body.swsi-admin-open{overflow:hidden}
      @media(max-width:430px){.swsi-myhub-card{padding:14px;box-shadow:none}.swsi-admin-note{display:none}}
    `;
    document.head.appendChild(st);
  }

  function draftCount(){var n=0;try{for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);if(k&&k.indexOf('essay_draft_')===0&&(localStorage.getItem(k)||'').trim())n++;}}catch(_e){}return n;}
  function reviewMeta(){try{var r=reviewSummary();return {due:Number(r.dueCount||0),active:Number(r.activeCount||0),mastered:Number(r.masteredCount||0)};}catch(_e){return {due:0,active:0,mastered:0};}}
  function toast(msg){var old=document.querySelector('.swsi-myhub-toast');if(old)old.remove();var el=document.createElement('div');el.className='swsi-myhub-toast';el.textContent=msg;document.body.appendChild(el);setTimeout(function(){if(el.parentNode)el.remove();},1800);}

  window.swsiSharePlatform=async function(){
    var url=(location.origin&&location.origin!=='null')?location.origin+location.pathname:location.href;
    var data={title:'SWSI — Social Work Study Initiative',text:'社工師國考免費學習平台 SWSI',url:url};
    try{if(navigator.share){await navigator.share(data);return;}if(navigator.clipboard&&navigator.clipboard.writeText){await navigator.clipboard.writeText(url);toast('已複製 SWSI 網址');return;}}catch(err){if(err&&err.name==='AbortError')return;}
    try{var ta=document.createElement('textarea');ta.value=url;ta.setAttribute('readonly','');ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove();toast('已複製 SWSI 網址');}catch(_e){toast('請從瀏覽器分享這個頁面');}
  };

  function getStoredAdminToken(){try{var raw=localStorage.getItem(AUTH_STORAGE_KEY);if(!raw)return '';var data=JSON.parse(raw);return String(data&&data.access_token||'');}catch(_e){return '';}}
  function setAdminEntryVisible(visible){document.querySelectorAll('[data-swsi-admin-entry]').forEach(function(el){el.hidden=!visible;});document.querySelectorAll('[data-swsi-admin-login]').forEach(function(el){el.hidden=!!visible;});}
  async function verifyAdminAccess(){var token=getStoredAdminToken();if(!token){setAdminEntryVisible(false);return false;}try{var res=await fetch(ADMIN_ENDPOINT,{method:'GET',headers:{'apikey':SUPABASE_PUBLISHABLE_KEY,'Authorization':'Bearer '+token}});var ok=res.ok;setAdminEntryVisible(ok);return ok;}catch(_e){setAdminEntryVisible(false);return false;}}

  function ensureAdminLayer(){var layer=document.getElementById('swsi-admin-layer');if(layer)return layer;layer=document.createElement('section');layer.id='swsi-admin-layer';layer.className='swsi-admin-layer';layer.hidden=true;layer.setAttribute('aria-label','SWSI 管理中心');layer.innerHTML='<div class="swsi-admin-bar"><button type="button" class="swsi-admin-back" onclick="swsiCloseAdminCenter()">‹ 返回 SWSI</button><div class="swsi-admin-title">管理中心</div><div class="swsi-admin-note">管理者專用・權限仍由 Supabase 驗證</div></div><iframe class="swsi-admin-frame" title="SWSI 管理中心" loading="lazy"></iframe>';document.body.appendChild(layer);return layer;}
  function adminUrl(){var p=location.pathname||'/';if(/\/preview\/index\.html$/.test(p))return './admin/index.html';if(/\/index\.html$/.test(p))return './admin/index.html';if(/\/$/.test(p))return './admin/index.html';return 'admin/index.html';}
  window.swsiOpenAdminCenter=function(){var layer=ensureAdminLayer();var frame=layer.querySelector('iframe');if(frame&&!frame.getAttribute('src'))frame.setAttribute('src',adminUrl());layer.hidden=false;document.body.classList.add('swsi-admin-open');};
  window.swsiCloseAdminCenter=function(){var layer=document.getElementById('swsi-admin-layer');if(layer)layer.hidden=true;document.body.classList.remove('swsi-admin-open');verifyAdminAccess();};

  function row(icon,label,meta,onclick,extraClass,attrs){return '<button type="button" class="swsi-myhub-row'+(extraClass?' '+extraClass:'')+'" '+(attrs||'')+' onclick="'+onclick+'"><span class="ico">'+icon+'</span><span class="copy"><span class="label">'+label+'</span><span class="meta">'+meta+'</span></span><span class="arrow">›</span></button>';}

  function recommendation(rv,drafts){
    if(rv.due>0)return {title:'先複習今天到期的 '+rv.due+' 題',sub:'到期錯題比再刷一批新題更值得。',onclick:"swsiLearningAction('due')"};
    if(rv.active>0)return {title:'整理還沒熟的錯題',sub:'目前還有 '+rv.active+' 題在複習循環裡。',onclick:"swsiLearningAction('review')"};
    if(drafts>0)return {title:'繼續一份申論草稿',sub:'這台裝置還有 '+drafts+' 份草稿可以接著寫。',onclick:"swsiLearningAction('essay')"};
    return {title:'完成一組 20 題',sub:'先累積一點作答資料，平台才更知道你的弱點。',onclick:"swsiLearningAction('quiz')"};
  }

  function buildHub(){
    var rv=reviewMeta(),drafts=draftCount(),rec=recommendation(rv,drafts);
    return '<section class="swsi-myhub" aria-label="學習中心">'
      +'<div class="swsi-myhub-card"><div class="swsi-myhub-kicker">學習中心</div><h2 class="swsi-myhub-title">今天先做一件就好</h2><div class="swsi-myhub-sub">這裡只放和你自己的學習進度有關的東西。</div>'
      +'<button type="button" class="swsi-myhub-primary" onclick="'+rec.onclick+'"><span><b>'+rec.title+'</b><small>'+rec.sub+'</small></span><span class="arrow">›</span></button>'
      +'<div class="swsi-myhub-stats"><div class="swsi-myhub-stat"><b>'+rv.due+'</b><span>今天到期</span></div><div class="swsi-myhub-stat"><b>'+rv.active+'</b><span>還沒熟</span></div><div class="swsi-myhub-stat"><b>'+rv.mastered+'</b><span>已掌握</span></div></div>'
      +'<div class="swsi-myhub-list">'
      +row('↻','錯題複習',rv.due?('今天 '+rv.due+' 題到期'):(rv.active?('尚有 '+rv.active+' 題未熟練'):'目前沒有待複習題'),"swsiLearningAction('review')")
      +row('◎','快速刷題','智慧推薦 20 題',"swsiLearningAction('quiz')")
      +row('✎','申論練習',drafts?('這台裝置有 '+drafts+' 份草稿'):'歷屆申論與 AI 練習回饋',"swsiLearningAction('essay')")
      +'</div></div>'
      +'<details class="swsi-myhub-more"><summary>更多與平台資訊</summary><div class="swsi-myhub-list">'
      +'<button type="button" class="swsi-myhub-row admin" data-swsi-admin-entry hidden onclick="swsiOpenAdminCenter()"><span class="ico">⚙</span><span class="copy"><span class="label">管理中心</span><span class="meta">管理者專用</span></span><span class="arrow">›</span></button>'
      +row('↗','分享 SWSI','分享官方公開網址','swsiSharePlatform()')
      +row('i','關於 SWSI','平台目的與使用方式',"swsiOpenPublicInfo('about',this)")
      +row('源','資料來源','正式考題以官方資料為準',"swsiOpenPublicInfo('sources',this)")
      +row('隱','隱私說明','了解平台保存哪些資料',"swsiOpenPublicInfo('privacy',this)")
      +row('條','使用條款','免費分享與商業使用邊界',"swsiOpenPublicInfo('terms',this)")
      +'<button type="button" class="swsi-myhub-row admin-login" data-swsi-admin-login onclick="swsiOpenAdminCenter()"><span class="ico">⚙</span><span class="copy"><span class="label">管理者入口</span><span class="meta">僅管理者使用</span></span><span class="arrow">›</span></button>'
      +'</div></details></section>';
  }

  function setLearningNavActive(){
    var home=document.getElementById('t-home'),learning=document.getElementById('t-review'),essay=document.getElementById('t-essay');
    if(home)home.classList.remove('on');
    if(learning)learning.classList.add('on');
    if(essay)essay.classList.remove('on');
  }

  window.swsiLearningAction=function(kind){
    window.__SWSI_LEARNING_CENTER_OPEN__=false;
    if(kind==='due'){if(typeof startDueReview==='function')startDueReview();return;}
    if(kind==='review'){if(typeof go==='function')go('review');return;}
    if(kind==='progress'){if(typeof go==='function')go('progress');return;}
    if(kind==='essay'){if(typeof window.swsiOpenEssay==='function')window.swsiOpenEssay();else if(typeof go==='function')go('essay');return;}
    if(typeof window.swsiStartRecommended20==='function')window.swsiStartRecommended20();
    else if(typeof go==='function')go('home');
  };

  window.swsiRenderLearningCenter=function(){
    var root=document.getElementById('app');
    if(!root)return false;
    window.__SWSI_LEARNING_CENTER_OPEN__=true;
    root.innerHTML=buildHub();
    setLearningNavActive();
    try{window.scrollTo({top:0,left:0,behavior:'auto'});}catch(_e){try{window.scrollTo(0,0);}catch(_e2){}}
    verifyAdminAccess();
    return true;
  };

  window.swsiOpenLearningCenter=function(ev){
    if(ev&&typeof ev.preventDefault==='function')ev.preventDefault();
    return window.swsiRenderLearningCenter();
  };

  function installLearningTab(){
    var home=document.getElementById('t-home'),learning=document.getElementById('t-review'),essay=document.getElementById('t-essay'),progress=document.getElementById('t-progress');
    if(home)home.innerHTML='<span class="ico">◎</span>練題';
    if(learning){learning.innerHTML='<span class="ico">↻</span>學習';learning.setAttribute('onclick','return swsiOpenLearningCenter(event)');learning.setAttribute('aria-label','學習中心');}
    if(essay)essay.innerHTML='<span class="ico">✒</span>申論';
    if(progress)progress.style.display='none';
    if(window.__SWSI_LEARNING_CENTER_OPEN__)setLearningNavActive();
  }

  function decorate(){
    installLearningTab();
    var root=document.getElementById('app');if(!root)return;
    if(window.__SWSI_LEARNING_CENTER_OPEN__&&!root.querySelector('.swsi-myhub'))window.swsiRenderLearningCenter();
  }

  window.addEventListener('storage',function(ev){if(!ev.key||ev.key===AUTH_STORAGE_KEY)verifyAdminAccess();});
  window.addEventListener('focus',function(){decorate();verifyAdminAccess();});
  var root=document.getElementById('app');
  if(root){decorate();var pending=false;new MutationObserver(function(){if(pending)return;pending=true;queueMicrotask(function(){pending=false;decorate();});}).observe(root,{childList:true,subtree:true});}
  installLearningTab();
  try{if(new URLSearchParams(location.search).get('admin')==='1')setTimeout(window.swsiOpenAdminCenter,0);}catch(_e){}
})();
/* SWSI Prelaunch Mobile Polish V4 2026-08-29
   Layer 3 only: visual polish inside Learning Center.
   Global shell/footer/nav geometry is owned exclusively by 15.layout-foundation.part.
*/
(function(){
  'use strict';
  var STYLE_ID='swsi-prelaunch-mobile-polish-20260829';
  if(!document.getElementById(STYLE_ID)){
    var st=document.createElement('style');
    st.id=STYLE_ID;
    st.textContent=`
      .swsi-myhub-row.admin-login{opacity:.72;background:#FAFBFA!important}
      .swsi-myhub-row.admin-login .label{font-size:12px!important;font-weight:600!important}
      .swsi-myhub-row.admin-login .meta{font-size:10px!important}
      @media(max-width:720px){
        .swsi-public-footer-brand{padding-left:8px;padding-right:8px}
        .swsi-myhub{gap:9px;margin-bottom:18px}
        .swsi-myhub-card{box-shadow:none!important;border-radius:15px!important}
      }
    `;
    document.head.appendChild(st);
  }
})();

/* SWSI Launch Guidance + Exam Countdown V2 2026-08-29
   Compact first-use help and local-only exam countdown inside Learning Center.
   Notifications are intentionally NOT enabled in this preview.
*/
(function(){
  'use strict';
  var GUIDE_KEY='swsi_launch_guide_dismissed_v2';
  var EXAM_KEY='swsi_target_exam_date_v1';
  var STYLE_ID='swsi-launch-guidance-countdown-v2-style';
  var lastExamOpener=null;

  if(!document.getElementById(STYLE_ID)){
    var st=document.createElement('style');st.id=STYLE_ID;
    st.textContent=`
      .swsi-launch-guide{margin:-2px 0 10px;border:1px solid #D7E2DC;background:#FBFCFB;border-radius:12px;padding:9px 10px;display:flex;align-items:flex-start;gap:8px;font-family:'Noto Sans TC',sans-serif;color:var(--ink)}
      .swsi-launch-guide .copy{min-width:0;flex:1}.swsi-launch-guide b{display:block;font-size:11.5px;line-height:1.45;color:var(--ink)}.swsi-launch-guide span{display:block;font-size:10.5px;line-height:1.55;color:var(--ink-soft);margin-top:1px}.swsi-launch-guide-close{flex:0 0 auto;border:0;background:transparent;color:#7C8781;width:28px;height:28px;border-radius:50%;font-size:17px;cursor:pointer}
      .swsi-exam-reminder{margin-top:10px;border:1px solid var(--line);background:#F8FAF9;border-radius:11px;padding:9px 10px;display:flex;align-items:center;gap:8px;font-family:'Noto Sans TC',sans-serif}.swsi-exam-reminder-copy{min-width:0;flex:1;font-size:10.7px;line-height:1.5;color:var(--ink-soft)}.swsi-exam-reminder-copy b{color:var(--ink);font-weight:800}.swsi-exam-reminder-btn{flex:0 0 auto;border:1px solid #CBD8D1;background:#fff;color:var(--pine-deep);border-radius:9px;min-height:34px;padding:6px 9px;font:750 10.5px/1.2 'Noto Sans TC',sans-serif;cursor:pointer}
      .swsi-exam-backdrop{position:fixed;inset:0;z-index:1100;background:rgba(25,31,28,.38);display:flex;align-items:flex-end;justify-content:center;padding:14px 10px calc(14px + env(safe-area-inset-bottom));backdrop-filter:blur(2px);overflow:auto}.swsi-exam-dialog{width:min(100%,480px);max-height:calc(100dvh - 28px - env(safe-area-inset-bottom));overflow:auto;background:#FDFEFD;border:1px solid #D7E0DB;border-radius:19px;padding:17px 16px 16px;box-shadow:0 22px 60px rgba(25,31,28,.22);font-family:'Noto Sans TC',sans-serif;color:var(--ink)}.swsi-exam-dialog h2{font-family:'Noto Serif TC',serif;font-size:19px;margin:0 0 5px}.swsi-exam-dialog p{font-size:11.5px;line-height:1.65;color:var(--ink-soft);margin:0 0 13px}.swsi-exam-dialog input{width:100%;box-sizing:border-box;min-height:46px;border:1px solid #CCD7D1;border-radius:11px;background:#fff;color:var(--ink);font:700 14px 'Noto Sans TC',sans-serif;padding:10px 11px}.swsi-exam-actions{display:grid;grid-template-columns:1fr 1.3fr;gap:8px;margin-top:12px}.swsi-exam-actions button{min-height:43px;border-radius:10px;font:800 12.5px 'Noto Sans TC',sans-serif;cursor:pointer}.swsi-exam-clear{background:#fff;border:1px solid var(--line);color:var(--ink-soft)}.swsi-exam-save{background:var(--pine-deep);border:0;color:#fff}body.swsi-modal-open{overflow:hidden}
      @media(min-width:620px){.swsi-exam-backdrop{align-items:center}}@media(max-width:390px){.swsi-exam-actions{grid-template-columns:1fr}}
    `;
    document.head.appendChild(st);
  }

  function getExamDate(){try{return String(localStorage.getItem(EXAM_KEY)||'').trim();}catch(_e){return '';}}
  function setExamDate(v){try{if(v)localStorage.setItem(EXAM_KEY,v);else localStorage.removeItem(EXAM_KEY);}catch(_e){}}
  function parseLocalDate(v){var m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(String(v||''));if(!m)return null;var d=new Date(Number(m[1]),Number(m[2])-1,Number(m[3]),12,0,0,0);return Number.isNaN(d.getTime())?null:d;}
  function daysUntil(v){var d=parseLocalDate(v);if(!d)return null;var now=new Date();var today=new Date(now.getFullYear(),now.getMonth(),now.getDate(),12,0,0,0);return Math.ceil((d.getTime()-today.getTime())/86400000);}
  function examText(){var v=getExamDate();if(!v)return '<b>考試倒數</b>　尚未設定日期；需要時再設定，只會存在這台裝置。';var n=daysUntil(v);if(n===null)return '<b>考試倒數</b>　日期格式無法讀取，請重新設定。';if(n>1)return '<b>距離考試還有 '+n+' 天</b>　照今天的學習節奏走就好。';if(n===1)return '<b>明天就是考試日</b>　今天以整理與休息為主。';if(n===0)return '<b>今天是你設定的考試日</b>　祝你穩穩作答。';return '<b>設定的考試日期已過</b>　可以更新下一個目標日期。';}

  window.swsiDismissLaunchGuide=function(){try{localStorage.setItem(GUIDE_KEY,'1');}catch(_e){}var el=document.querySelector('.swsi-launch-guide');if(el)el.remove();};
  function guideDismissed(){try{return localStorage.getItem(GUIDE_KEY)==='1';}catch(_e){return false;}}
  function decorateHome(){if(guideDismissed())return;var hero=document.querySelector('#app .swsi-focus-hero');if(!hero||document.querySelector('#app .swsi-launch-guide'))return;var box=document.createElement('section');box.className='swsi-launch-guide';box.setAttribute('aria-label','第一次使用 SWSI');box.innerHTML='<div class="copy"><b>第一次來？不用先學整個平台。</b><span>「練題」直接刷題；「學習」看錯題與進度；「申論」專心練申論。</span></div><button type="button" class="swsi-launch-guide-close" aria-label="不再顯示首次使用說明" onclick="swsiDismissLaunchGuide()">×</button>';hero.insertAdjacentElement('afterend',box);}

  function onExamKeydown(ev){if(ev.key==='Escape')window.swsiCloseExamDate();}
  window.swsiOpenExamDate=function(){
    var old=document.getElementById('swsi-exam-backdrop');if(old)old.remove();
    lastExamOpener=document.activeElement&&document.activeElement.classList&&document.activeElement.classList.contains('swsi-exam-reminder-btn')?document.activeElement:null;
    var ov=document.createElement('div');ov.id='swsi-exam-backdrop';ov.className='swsi-exam-backdrop';
    ov.innerHTML='<div class="swsi-exam-dialog" role="dialog" aria-modal="true" aria-labelledby="swsi-exam-title" onclick="event.stopPropagation()"><h2 id="swsi-exam-title">設定考試日期</h2><p>日期只儲存在這台裝置，用來顯示倒數。這個預覽版不會要求通知權限，也不會把日期上傳。</p><input id="swsi-exam-date-input" type="date" value="'+getExamDate()+'"><div class="swsi-exam-actions"><button type="button" class="swsi-exam-clear" onclick="swsiClearExamDate()">清除日期</button><button type="button" class="swsi-exam-save" onclick="swsiSaveExamDate()">儲存日期</button></div></div>';
    ov.addEventListener('click',window.swsiCloseExamDate);document.body.appendChild(ov);document.body.classList.add('swsi-modal-open');document.addEventListener('keydown',onExamKeydown);
    var input=ov.querySelector('#swsi-exam-date-input');if(input)setTimeout(function(){try{input.focus();}catch(_e){}},0);
  };
  window.swsiCloseExamDate=function(){var ov=document.getElementById('swsi-exam-backdrop');if(ov)ov.remove();document.body.classList.remove('swsi-modal-open');document.removeEventListener('keydown',onExamKeydown);var opener=lastExamOpener;lastExamOpener=null;if(opener&&document.contains(opener))setTimeout(function(){try{opener.focus();}catch(_e){}},0);};
  window.swsiSaveExamDate=function(){var input=document.getElementById('swsi-exam-date-input');setExamDate(input?input.value:'');window.swsiCloseExamDate();decorateReminder(true);};
  window.swsiClearExamDate=function(){setExamDate('');window.swsiCloseExamDate();decorateReminder(true);};

  function decorateReminder(force){var card=document.querySelector('#app .swsi-myhub-card');if(!card)return;var row=card.querySelector('.swsi-exam-reminder');if(!row){row=document.createElement('div');row.className='swsi-exam-reminder';row.innerHTML='<div class="swsi-exam-reminder-copy"></div><button type="button" class="swsi-exam-reminder-btn" onclick="swsiOpenExamDate()">設定日期</button>';var list=card.querySelector('.swsi-myhub-list');card.insertBefore(row,list||null);}var copy=row.querySelector('.swsi-exam-reminder-copy'),text=examText();if(force||copy.innerHTML!==text)copy.innerHTML=text;var btn=row.querySelector('.swsi-exam-reminder-btn'),label=getExamDate()?'修改日期':'設定日期';if(btn&&btn.textContent!==label)btn.textContent=label;}

  function run(){decorateHome();decorateReminder(false);}run();var root=document.getElementById('app')||document.body,pending=false;new MutationObserver(function(){if(pending)return;pending=true;queueMicrotask(function(){pending=false;run();});}).observe(root,{childList:true,subtree:true});window.addEventListener('focus',run);
})();

/* SWSI Accessibility Touch Guard 2026-08-28
   Public-launch ergonomics only. Ensures primary bottom navigation targets
   stay comfortably tappable on narrow phones without changing navigation logic.
*/
(function(){
  'use strict';
  var STYLE_ID='swsi-accessibility-touch-20260828';
  if(document.getElementById(STYLE_ID))return;
  var st=document.createElement('style');
  st.id=STYLE_ID;
  st.textContent=`
    .tabbar button{
      min-height:48px;
    }
  `;
  document.head.appendChild(st);
})();

/* SWSI Prelaunch Resilience 2026-08-28
   Mobile modal safety only: viewport containment, background scroll lock,
   Escape close, keyboard focus containment, and focus restoration.
   Does not own grading, questions, AI, storage schemas, or runtime routes.
*/
(function(){
  'use strict';

  var STYLE_ID='swsi-prelaunch-resilience-20260828';
  if(!document.getElementById(STYLE_ID)){
    var st=document.createElement('style');
    st.id=STYLE_ID;
    st.textContent=`
      body.swsi-modal-open{overflow:hidden!important;overscroll-behavior:none}
      .swsi-exam-backdrop{overflow-y:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch}
      .swsi-exam-dialog{box-sizing:border-box;max-height:calc(100vh - 28px - env(safe-area-inset-top) - env(safe-area-inset-bottom));max-height:calc(100dvh - 28px - env(safe-area-inset-top) - env(safe-area-inset-bottom));overflow-y:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch}
      @media(max-width:430px){
        .swsi-exam-backdrop{padding-top:calc(10px + env(safe-area-inset-top));align-items:flex-end}
        .swsi-exam-dialog{max-height:calc(100vh - 20px - env(safe-area-inset-top) - env(safe-area-inset-bottom));max-height:calc(100dvh - 20px - env(safe-area-inset-top) - env(safe-area-inset-bottom))}
      }
    `;
    document.head.appendChild(st);
  }

  var lastFocus=null;

  function currentDialog(){return document.querySelector('#swsi-exam-backdrop .swsi-exam-dialog');}
  function currentBackdrop(){return document.getElementById('swsi-exam-backdrop');}
  function focusables(){
    var dialog=currentDialog();
    if(!dialog)return [];
    return Array.from(dialog.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href],[tabindex]:not([tabindex="-1"])')).filter(function(el){
      return !!(el.offsetWidth||el.offsetHeight||el.getClientRects().length);
    });
  }
  function lock(){document.body.classList.add('swsi-modal-open');}
  function unlock(){if(!currentBackdrop())document.body.classList.remove('swsi-modal-open');}
  function focusInitial(){
    var input=document.getElementById('swsi-exam-date-input');
    var target=input||focusables()[0];
    if(target&&typeof target.focus==='function'){
      try{target.focus({preventScroll:true});}catch(_e){try{target.focus();}catch(_e2){}}
    }
  }
  function restoreFocus(){
    var target=lastFocus;lastFocus=null;
    if(target&&target.isConnected&&typeof target.focus==='function'){
      try{target.focus({preventScroll:true});}catch(_e){try{target.focus();}catch(_e2){}}
    }
  }

  if(typeof window.swsiOpenExamDate==='function'&&!window.swsiOpenExamDate.__swsiResilienceWrapped){
    var openOriginal=window.swsiOpenExamDate;
    var openWrapped=function(){
      lastFocus=document.activeElement;
      openOriginal.apply(this,arguments);
      lock();
      requestAnimationFrame(focusInitial);
    };
    openWrapped.__swsiResilienceWrapped=true;
    window.swsiOpenExamDate=openWrapped;
  }

  if(typeof window.swsiCloseExamDate==='function'&&!window.swsiCloseExamDate.__swsiResilienceWrapped){
    var closeOriginal=window.swsiCloseExamDate;
    var closeWrapped=function(){
      closeOriginal.apply(this,arguments);
      unlock();
      restoreFocus();
    };
    closeWrapped.__swsiResilienceWrapped=true;
    window.swsiCloseExamDate=closeWrapped;
  }

  document.addEventListener('keydown',function(ev){
    if(!currentBackdrop())return;
    if(ev.key==='Escape'){
      ev.preventDefault();
      if(typeof window.swsiCloseExamDate==='function')window.swsiCloseExamDate();
      return;
    }
    if(ev.key!=='Tab')return;
    var list=focusables();if(!list.length)return;
    var first=list[0],last=list[list.length-1],active=document.activeElement;
    if(ev.shiftKey&&active===first){ev.preventDefault();last.focus();}
    else if(!ev.shiftKey&&active===last){ev.preventDefault();first.focus();}
  },true);

  var observer=new MutationObserver(function(){
    if(currentBackdrop())lock();else unlock();
  });
  observer.observe(document.body,{childList:true});
})();

/* SWSI Learning Typography Bridge V1 2026-08-29
   Accessibility contract: Learning Center / review / progress typography follows
   the existing global A/A/A variables (--fs-q/--fs-h/--fs-b/--fs-s).
   This layer owns typography only; it must not own shell geometry or routing.
*/
(function(){
  'use strict';
  var STYLE_ID='swsi-learning-font-scale-v1';
  if(document.getElementById(STYLE_ID))return;
  var st=document.createElement('style');
  st.id=STYLE_ID;
  st.textContent=`
    /* Learning Center hub: preserve the current visual hierarchy at the default
       size, but make every user-facing text tier respond to html[data-fs]. */
    .swsi-myhub-kicker{font-size:calc(var(--fs-s) - 4px)!important}
    .swsi-myhub-title{font-size:calc(var(--fs-h) + 2px)!important}
    .swsi-myhub-sub{font-size:calc(var(--fs-s) - 3px)!important}
    .swsi-myhub-primary b{font-size:calc(var(--fs-b) - 2px)!important}
    .swsi-myhub-primary small{font-size:calc(var(--fs-s) - 4px)!important}
    .swsi-myhub-stat b{font-size:var(--fs-h)!important}
    .swsi-myhub-stat span{font-size:calc(var(--fs-s) - 5px)!important}
    .swsi-myhub-row .label{font-size:calc(var(--fs-b) - 3px)!important}
    .swsi-myhub-row .meta{font-size:calc(var(--fs-s) - 4px)!important}
    .swsi-myhub-more>summary{font-size:calc(var(--fs-s) - 3px)!important}
    .swsi-myhub-toast{font-size:calc(var(--fs-s) - 2px)!important}

    /* Wrong-answer review / learning progress. */
    body[data-swsi-page="learning-detail"] .section-h{
      font-size:calc(var(--fs-h) + 5px)!important;
    }
    body[data-swsi-page="learning-detail"] .section-s{
      font-size:var(--fs-s)!important;
    }
    body[data-swsi-page="learning-detail"] .btn{
      font-size:calc(var(--fs-b) - .5px)!important;
    }
    body[data-swsi-page="learning-detail"] .empty h3{
      font-size:calc(var(--fs-h) + 2px)!important;
    }
    body[data-swsi-page="learning-detail"] .empty p{
      font-size:calc(var(--fs-b) - 3px)!important;
    }
    .swsi-review-stats .stat .v{font-size:calc(var(--fs-h) + 5px)!important}
    .swsi-review-stats .stat .k{font-size:calc(var(--fs-s) - 3px)!important}
    .swsi-calm-note{font-size:calc(var(--fs-b) - 3px)!important}
    .swsi-learning-h{font-size:calc(var(--fs-b) - 2px)!important}
    .swsi-learning-muted{font-size:calc(var(--fs-s) - 2px)!important}
    .swsi-learning-row b{font-size:calc(var(--fs-b) - 2px)!important}
    .swsi-learning-row small{font-size:calc(var(--fs-s) - 3px)!important}
    .swsi-progress-hero>div:first-child small{font-size:calc(var(--fs-s) - 2px)!important}
    .swsi-progress-hero strong{font-size:calc(var(--fs-q) + 17px)!important}
    .swsi-progress-mini span{font-size:calc(var(--fs-s) - 4px)!important}
    .swsi-progress-mini b{font-size:calc(var(--fs-b) - 2px)!important}
    .swsi-progress-strip b{font-size:var(--fs-h)!important}
    .swsi-progress-strip span{font-size:calc(var(--fs-s) - 4px)!important}
    .swsi-next-copy b{font-size:calc(var(--fs-b) - 2px)!important}
    .swsi-next-copy span{font-size:calc(var(--fs-s) - 2px)!important}
    .swsi-progress-subject .top{font-size:calc(var(--fs-b) - 3px)!important}
    .swsi-progress-subject small{font-size:calc(var(--fs-s) - 4px)!important}
    .swsi-cause-stat{font-size:calc(var(--fs-b) - 3px)!important}
    .swsi-danger-link{font-size:calc(var(--fs-s) - 2px)!important}

    /* Text generated by the learning loop with an inline legacy 13px size. */
    body[data-swsi-page="learning-detail"] .empty [style*="font-size:13px"]{
      font-size:calc(var(--fs-b) - 3px)!important;
    }
  `;
  document.head.appendChild(st);
})();

/* SWSI Knowledge Path V1 2026-08-26
   One query -> understand -> see exam patterns -> practice.
   Keeps theory/law summaries distinct from official exam questions.
*/
(function(){
  'use strict';

  var STYLE_ID='swsi-knowledge-path-v1-style';
  if(!document.getElementById(STYLE_ID)){
    var st=document.createElement('style');
    st.id=STYLE_ID;
    st.textContent=`
      .swsi-k-search-shell{padding-top:4px}
      .swsi-k-searchbox{width:100%;box-sizing:border-box;font-family:'Noto Sans TC',sans-serif;font-size:16px;padding:13px 15px;border:1.5px solid var(--line);border-radius:14px;background:#fff;color:var(--ink);outline:none}
      .swsi-k-searchbox:focus{border-color:var(--pine);box-shadow:0 0 0 3px rgba(79,126,118,.08)}
      .swsi-k-empty{padding:18px 2px 2px;color:var(--ink-soft);font-family:'Noto Sans TC',sans-serif;font-size:var(--fs-s);line-height:1.75}
      .swsi-k-examples{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}
      .swsi-k-examples button{border:1px solid var(--line);background:#fff;color:var(--pine-deep);border-radius:999px;padding:7px 10px;font-family:'Noto Sans TC',sans-serif;font-size:12px;font-weight:700;cursor:pointer}

      .swsi-k-path{margin:13px 0 5px;background:linear-gradient(150deg,#F7FAF8,#EEF4F1);border:1px solid #D5E2DC;border-radius:16px;padding:14px 15px}
      .swsi-k-path b{display:block;font-family:'Noto Serif TC',serif;font-size:16px;color:var(--ink);line-height:1.45}
      .swsi-k-path span{display:block;font-family:'Noto Sans TC',sans-serif;font-size:12px;color:var(--ink-soft);line-height:1.65;margin-top:3px}
      .swsi-k-counts{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
      .swsi-k-counts i{font-style:normal;background:#fff;border:1px solid var(--line);border-radius:999px;padding:4px 8px;font-family:'Noto Sans TC',sans-serif;font-size:11px;color:var(--ink-soft)}

      .swsi-k-sec{margin-top:19px}
      .swsi-k-sec-h{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:8px}
      .swsi-k-sec-h b{font-family:'Noto Serif TC',serif;font-size:15px;color:var(--ink)}
      .swsi-k-sec-h span{font-family:'Noto Sans TC',sans-serif;font-size:11.5px;color:var(--ink-soft)}
      .swsi-k-card{width:100%;display:block;text-align:left;border:1px solid var(--line);border-radius:13px;padding:12px 13px;margin-bottom:8px;background:#fff;color:var(--ink);font-family:inherit;cursor:pointer}
      .swsi-k-card .type{font-family:'Noto Sans TC',sans-serif;font-size:10.5px;font-weight:800;letter-spacing:.05em;color:var(--pine);margin-bottom:3px}
      .swsi-k-card.law .type{color:#756E57}
      .swsi-k-card .name{font-family:'Noto Serif TC',serif;font-size:14.5px;font-weight:800;line-height:1.45}
      .swsi-k-card .desc{font-family:'Noto Sans TC',sans-serif;font-size:12px;color:var(--ink-soft);line-height:1.6;margin-top:4px}
      .swsi-k-question{border:1px solid var(--line);border-radius:12px;padding:11px 13px;margin-bottom:8px;background:#fff;cursor:pointer}
      .swsi-k-question .q{font-size:13.5px;line-height:1.58;color:var(--ink)}
      .swsi-k-question .meta{font-family:'Noto Sans TC',sans-serif;font-size:11px;color:var(--ink-soft);line-height:1.5;margin-top:5px}
      .swsi-k-more{font-family:'Noto Sans TC',sans-serif;font-size:11.5px;color:var(--ink-soft);margin:2px 2px 7px}
      .swsi-k-muted{border:1px dashed var(--line);border-radius:12px;padding:11px 12px;font-family:'Noto Sans TC',sans-serif;font-size:12px;line-height:1.65;color:var(--ink-soft);background:rgba(255,255,255,.45)}
      .swsi-k-action{width:100%;min-height:43px;border:none;border-radius:11px;background:var(--pine-deep);color:#fff;font-family:'Noto Sans TC',sans-serif;font-size:13px;font-weight:800;cursor:pointer;margin-bottom:9px}
      .swsi-k-action.ghost{border:1px solid var(--line);background:#fff;color:var(--pine-deep)}

      .swsi-k-net{margin-top:15px;padding-top:14px;border-top:1px solid var(--line)}
      .swsi-k-net-title{font-family:'Noto Serif TC',serif;font-size:14px;font-weight:800;color:var(--pine);margin-bottom:9px}
      .swsi-k-related-label{font-family:'Noto Sans TC',sans-serif;font-size:11.5px;font-weight:800;color:var(--ink-soft);margin:11px 0 6px}
      .swsi-k-related{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
      .swsi-k-related button{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 9px;color:var(--pine-deep);font-family:'Noto Sans TC',sans-serif;font-size:11.5px;font-weight:700;cursor:pointer}
      .swsi-k-net .swsi-k-question{background:var(--paper2)}
      .swsi-k-search-all{width:100%;min-height:41px;border:1px solid var(--pine);border-radius:10px;background:transparent;color:var(--pine-deep);font-family:'Noto Sans TC',sans-serif;font-size:12.5px;font-weight:800;cursor:pointer;margin-bottom:8px}

      .swsi-k-pagelead{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:4px 0 10px}
      .swsi-k-pagelead button{border:none;background:none;color:var(--pine);font-family:'Noto Sans TC',sans-serif;font-size:12px;font-weight:700;cursor:pointer;padding:5px 0}
      @media(max-width:370px){.swsi-k-sec-h{display:block}.swsi-k-sec-h span{display:block;margin-top:2px}}
    `;
    document.head.appendChild(st);
  }

  function H(v){
    return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});
  }
  function E(v){return encodeURIComponent(String(v==null?'':v)).replace(/'/g,'%27');}
  function N(v){return String(v==null?'':v).toLowerCase().replace(/[\s　（）()《》〈〉「」『』【】·・,，.。:：;；/\\_-]+/g,'');}
  function A(v){return Array.isArray(v)?v:(v?String(v).split(/[、,，;；]/).filter(Boolean):[]);}
  function sn(v,n){var s=String(v||'').replace(/\s+/g,' ').trim();return s.length>n?s.slice(0,n)+'…':s;}
  function yearNum(v){var n=parseInt(String(v||'').replace(/\D/g,''),10);return Number.isFinite(n)?n:0;}
  function uniqPush(arr,item,key){var k=key(item);if(!arr.some(function(x){return key(x)===k;}))arr.push(item);}

  var ALIASES={
    '充權':['增強權能','賦權'],
    '增強權能':['充權','賦權'],
    '賦權':['充權','增強權能'],
    '艾瑞克森':['Erikson'],
    'erikson':['艾瑞克森'],
    '依附':['Bowlby','Ainsworth'],
    '生態系統':['生態系統理論','生態觀點']
  };

  function smartSearch(query){
    var q=String(query||'').trim();
    var out={mcq:[],theories:[],laws:[],essays:[]};
    if(!q)return out;
    var variants=[q];
    if(!/\s/.test(q)){
      var al=ALIASES[q]||ALIASES[q.toLowerCase()]||[];
      al.forEach(function(x){if(!variants.includes(x))variants.push(x);});
    }
    variants.forEach(function(v){
      var r=typeof searchAll==='function'?searchAll(v):{mcq:[],theories:[],laws:[],essays:[]};
      (r.mcq||[]).forEach(function(x){uniqPush(out.mcq,x,function(z){return z.id;});});
      (r.theories||[]).forEach(function(x){uniqPush(out.theories,x,function(z){return z.n;});});
      (r.laws||[]).forEach(function(x){uniqPush(out.laws,x,function(z){return z.n;});});
      (r.essays||[]).forEach(function(x){uniqPush(out.essays,x,function(z){return z.id;});});
    });
    var nq=N(q);
    function scoreName(x){var n=N(x||'');if(!nq)return 0;if(n===nq)return 50;if(n.indexOf(nq)>=0)return 30;if(nq.indexOf(n)>=0)return 20;return 0;}
    out.theories.sort(function(a,b){return scoreName(b.n)-scoreName(a.n);});
    out.laws.sort(function(a,b){return scoreName(b.n)-scoreName(a.n);});
    out.mcq.sort(function(a,b){var sa=(N(a.topic).indexOf(nq)>=0?10:0)+(N(a.law).indexOf(nq)>=0?8:0);var sb=(N(b.topic).indexOf(nq)>=0?10:0)+(N(b.law).indexOf(nq)>=0?8:0);return sb-sa||yearNum(b.year)-yearNum(a.year);});
    out.essays.sort(function(a,b){var sa=(N(a.topic).indexOf(nq)>=0?10:0);var sb=(N(b.topic).indexOf(nq)>=0?10:0);return sb-sa||yearNum(b.year)-yearNum(a.year);});
    return out;
  }

  window.swsiKnowledgeSearch=function(q){
    try{searchQ=String(q||'');}catch(_e){window.searchQ=String(q||'');}
    try{go('search');}catch(_e){try{view='search';render();}catch(_x){}}
  };
  window.swsiFillKnowledgeSearch=function(encoded){
    var q='';try{q=decodeURIComponent(encoded||'');}catch(_e){q=encoded||'';}
    var box=document.getElementById('searchbox');
    if(box){box.value=q;box.focus();}
    if(typeof doSearch==='function')doSearch(q);
  };

  openTheory=function(name){
    var idx=-1;try{idx=THEORIES.findIndex(function(t){return t.n===name;});}catch(_e){}
    try{theoryQ='';theoryOpen=idx>=0?idx:null;}catch(_e){}
    go('theories');
    setTimeout(function(){var open=document.querySelector('#app .ecard.open');if(open)open.scrollIntoView({block:'start'});},60);
  };
  openLawCard=function(name){
    var idx=-1;try{idx=LAWS.findIndex(function(l){return l.n===name;});}catch(_e){}
    try{lawQ='';lawOpen=idx>=0?idx:null;}catch(_e){}
    go('laws');
    setTimeout(function(){var open=document.querySelector('#app .ecard.open');if(open)open.scrollIntoView({block:'start'});},60);
  };
  window.swsiOpenTheoryEncoded=function(x){try{openTheory(decodeURIComponent(x));}catch(_e){}};
  window.swsiOpenLawEncoded=function(x){try{openLawCard(decodeURIComponent(x));}catch(_e){}};
  window.swsiOpenEssayEncoded=function(id,subj){try{openEssayCard(decodeURIComponent(id),decodeURIComponent(subj));}catch(_e){}};
  window.swsiStudyOneEncoded=function(id){try{studyOne(decodeURIComponent(id));}catch(_e){}};

  renderSearch=function(){
    app.innerHTML='<div class="swsi-k-search-shell">'+
      '<input id="searchbox" class="swsi-k-searchbox" value="'+H(searchQ||'')+'" oninput="doSearch(this.value)" placeholder="查考點、理論、法規、選擇題、申論…" autocomplete="off" aria-label="搜尋國考知識">'+
      '<div id="search-results"></div></div>';
    doSearch(searchQ||'');
    setTimeout(function(){var el=document.getElementById('searchbox');if(el){var v=el.value;el.focus();el.setSelectionRange(v.length,v.length);}},40);
  };

  doSearch=function(val){
    try{searchQ=val;}catch(_e){}
    var box=document.getElementById('search-results');if(!box)return;
    var q=String(val||'').trim();
    if(!q){
      box.innerHTML='<div class="swsi-k-empty"><b style="color:var(--ink)">查一個你正在讀的東西。</b><br>平台會把辭典、法規、選擇題和申論排成同一條路，不用自己在四個頁面來回找。'+
        '<div class="swsi-k-examples">'+['Erikson','增強權能','社會救助法','保護令','依附'].map(function(x){return '<button type="button" onclick="swsiFillKnowledgeSearch(\''+E(x)+'\')">'+H(x)+'</button>';}).join('')+'</div></div>';
      return;
    }
    var r=smartSearch(q);
    var total=r.mcq.length+r.essays.length+r.theories.length+r.laws.length;
    if(!total){
      box.innerHTML='<div class="swsi-k-empty">找不到符合「<b style="color:var(--ink)">'+H(q)+'</b>」的內容。可以把詞拆短一點，例如「兒少 保護」改成「兒少」。</div>';
      return;
    }
    var h='<section class="swsi-k-path"><b>查「'+H(q)+'」的完整考法</b><span>先理解概念與法規，再看題目怎麼問，最後直接練。</span><div class="swsi-k-counts">'+
      (r.theories.length?'<i>理論 '+r.theories.length+'</i>':'')+(r.laws.length?'<i>法規 '+r.laws.length+'</i>':'')+(r.mcq.length?'<i>選擇 '+r.mcq.length+'</i>':'')+(r.essays.length?'<i>申論／練習 '+r.essays.length+'</i>':'')+'</div></section>';

    h+='<section class="swsi-k-sec"><div class="swsi-k-sec-h"><b>1　先理解</b><span>平台整理，不冒充官方題目</span></div>';
    if(r.theories.length||r.laws.length){
      r.theories.slice(0,5).forEach(function(t){h+='<button class="swsi-k-card" onclick="swsiOpenTheoryEncoded(\''+E(t.n)+'\')"><div class="type">核心理論</div><div class="name">'+H(t.n)+'</div><div class="desc">'+H(sn(t.c,72))+'</div></button>';});
      r.laws.slice(0,5).forEach(function(l){h+='<button class="swsi-k-card law" onclick="swsiOpenLawEncoded(\''+E(l.n)+'\')"><div class="type">重點法規</div><div class="name">'+H(l.n)+'</div><div class="desc">'+H(sn(l.c||l.p,72))+'</div></button>';});
    }else h+='<div class="swsi-k-muted">這個詞目前沒有獨立的理論／法規卡，可以直接從歷屆題目的問法反推考點。</div>';
    h+='</section>';

    h+='<section class="swsi-k-sec"><div class="swsi-k-sec-h"><b>2　看選擇題怎麼考</b><span>'+r.mcq.length+' 題</span></div>';
    if(r.mcq.length){
      h+='<button class="swsi-k-action" onclick="searchQuizMcq()">直接練這 '+r.mcq.length+' 題</button>';
      r.mcq.slice(0,8).forEach(function(x){h+='<div class="swsi-k-question" onclick="swsiStudyOneEncoded(\''+E(x.id)+'\')"><div class="q">'+H(sn(x.q,76))+'</div><div class="meta">'+H(x.subject||'')+' · '+H(x.year||'')+' 年 · '+H(x.topic||x.major||'')+'</div></div>';});
      if(r.mcq.length>8)h+='<div class="swsi-k-more">還有 '+(r.mcq.length-8)+' 題；上面的按鈕會把全部符合題目排成一組。</div>';
    }else h+='<div class="swsi-k-muted">目前沒有搜尋到直接命中的選擇題。</div>';
    h+='</section>';

    h+='<section class="swsi-k-sec"><div class="swsi-k-sec-h"><b>3　看申論怎麼出</b><span>'+r.essays.length+' 題</span></div>';
    if(r.essays.length){
      r.essays.slice(0,8).forEach(function(e){var kind=e.qtype||'申論題';h+='<div class="swsi-k-question" onclick="swsiOpenEssayEncoded(\''+E(e.id)+'\',\''+E(e.subject||'全部科目')+'\')"><div class="q">'+H(sn(e.q,82))+'</div><div class="meta">'+H(kind)+' · '+H(e.subject||'')+(e.year?' · '+H(e.year)+' 年':'')+(e.topic?' · '+H(e.topic):'')+'</div></div>';});
      if(r.essays.length>8)h+='<div class="swsi-k-more">先列前 8 題；縮短或增加搜尋詞可以再聚焦。</div>';
    }else h+='<div class="swsi-k-muted">目前沒有搜尋到直接相關的申論題。</div>';
    h+='</section>';
    box.innerHTML=h;
  };

  function theoryRelatedLaws(t){
    var es=[];try{es=theoryEssays(t)||[];}catch(_e){}
    var names=[];es.forEach(function(e){A(e.laws).forEach(function(x){if(x&&!names.includes(x))names.push(x);});});
    var found=[];
    names.forEach(function(name){
      var nn=N(name), hit=null;
      try{hit=LAWS.find(function(l){var ln=N(l.n);return ln===nn||ln.indexOf(nn)>=0||nn.indexOf(ln)>=0;});}catch(_e){}
      if(hit&&!found.some(function(x){return x.n===hit.n;}))found.push(hit);
    });
    return found.slice(0,5);
  }

  knowledgeNetHTML=function(t,gi){
    var es=[];try{es=theoryEssays(t)||[];}catch(_e){}
    var mc=0;try{mc=theoryMcqCount(t)||0;}catch(_e){}
    var laws=theoryRelatedLaws(t);
    var h='<div class="swsi-k-net"><div class="swsi-k-net-title">從理論接到考題</div>'+
      '<button class="swsi-k-search-all" onclick="event.stopPropagation();swsiKnowledgeSearch(\''+H(t.n).replace(/'/g,'&#39;')+'\')">搜尋「'+H(t.n)+'」全部考法</button>';
    if(mc)h+='<button class="swsi-k-action" onclick="event.stopPropagation();quizTheory('+gi+')">練這個理論的選擇題（'+mc+' 題）</button>';
    if(laws.length){
      h+='<div class="swsi-k-related-label">申論資料裡常一起出現的法規</div><div class="swsi-k-related">';
      laws.forEach(function(l){h+='<button type="button" onclick="event.stopPropagation();swsiOpenLawEncoded(\''+E(l.n)+'\')">'+H(l.n)+'</button>';});
      h+='</div>';
    }
    if(es.length){
      h+='<div class="swsi-k-related-label">相關申論／練習題（'+es.length+'）</div>';
      es.slice(0,6).forEach(function(e){h+='<div class="swsi-k-question" onclick="event.stopPropagation();swsiOpenEssayEncoded(\''+E(e.id)+'\',\''+E(e.subject||'全部科目')+'\')"><div class="q">'+H(sn(e.topic||e.q,58))+'</div><div class="meta">'+H(e.qtype||'申論題')+(e.year?' · '+H(e.year)+' 年':'')+' · '+H(e.subject||'')+'</div></div>';});
      if(es.length>6)h+='<div class="swsi-k-more">還有 '+(es.length-6)+' 題，可用上方「搜尋全部考法」繼續看。</div>';
    }
    if(!mc&&!es.length)h+='<div class="swsi-k-muted">目前還沒有建立到考題的直接連結；可以用「搜尋全部考法」從題目文字繼續找。</div>';
    return h+'</div>';
  };

  function lawShortName(l){return N(l&&l.n).replace(/(施行細則|條例|辦法|規則|法)$/,'');}
  function lawMcqScore(q,l){
    var blob=N((q.q||'')+' '+(q.topic||'')+' '+(q.major||'')+' '+(q.keywords||'')+' '+(q.law||''));
    var full=N(l.n),short=lawShortName(l),score=0;
    if(full&&blob.indexOf(full)>=0)score+=10;
    else if(short.length>=4&&blob.indexOf(short)>=0)score+=5;
    A(l.k).forEach(function(k){var nk=N(k);if(nk.length>=3&&blob.indexOf(nk)>=0)score++;});
    return score;
  }
  function lawMcqs(l){
    var list=[];try{list=ALL.filter(function(q){return lawMcqScore(q,l)>=2;});}catch(_e){}
    return list.sort(function(a,b){return lawMcqScore(b,l)-lawMcqScore(a,l)||yearNum(b.year)-yearNum(a.year);});
  }
  function lawEssayScore(e,l){
    var explicit=N(A(e.laws).join(' ')),full=N(l.n),short=lawShortName(l),score=0;
    if(full&&explicit.indexOf(full)>=0)score+=12;
    else if(short.length>=4&&explicit.indexOf(short)>=0)score+=7;
    var blob=N((e.q||'')+' '+(e.topic||'')+' '+A(e.keywords).join(' ')+' '+explicit);
    A(l.k).forEach(function(k){var nk=N(k);if(nk.length>=3&&blob.indexOf(nk)>=0)score++;});
    return score;
  }
  function lawEssays(l){
    var list=[];try{list=ESSAYS.filter(function(e){return lawEssayScore(e,l)>=2;});}catch(_e){}
    return list.sort(function(a,b){return lawEssayScore(b,l)-lawEssayScore(a,l)||yearNum(b.year)-yearNum(a.year);});
  }
  function lawRelatedTheories(l){
    var counts={};lawEssays(l).forEach(function(e){A(e.theories).forEach(function(x){if(x)counts[x]=(counts[x]||0)+1;});});
    var names=Object.entries(counts).sort(function(a,b){return b[1]-a[1];}).map(function(x){return x[0];});
    var found=[];
    names.forEach(function(name){var nn=N(name),hit=null;try{hit=THEORIES.find(function(t){var tn=N(t.n);return tn===nn||tn.indexOf(nn)>=0||nn.indexOf(tn)>=0;});}catch(_e){}if(hit&&!found.some(function(x){return x.n===hit.n;}))found.push(hit);});
    return found.slice(0,5);
  }
  window.swsiQuizLaw=function(gi){
    var l=null;try{l=LAWS[gi];}catch(_e){}if(!l)return;
    var ids=new Set(lawMcqs(l).map(function(q){return q.id;}));
    if(!ids.size)return;
    startQuiz(function(q){return ids.has(q.id);},0);
  };

  function lawKnowledgeNetHTML(l,gi){
    var mc=lawMcqs(l),es=lawEssays(l),ths=lawRelatedTheories(l);
    var h='<div class="swsi-k-net"><div class="swsi-k-net-title">從法規接到考題</div>'+
      '<button class="swsi-k-search-all" onclick="event.stopPropagation();swsiKnowledgeSearch(\''+H(l.n).replace(/'/g,'&#39;')+'\')">搜尋「'+H(l.n)+'」全部考法</button>';
    if(mc.length)h+='<button class="swsi-k-action" onclick="event.stopPropagation();swsiQuizLaw('+gi+')">練這部法規的選擇題（'+mc.length+' 題）</button>';
    if(ths.length){
      h+='<div class="swsi-k-related-label">申論資料裡常一起出現的理論</div><div class="swsi-k-related">';
      ths.forEach(function(t){h+='<button type="button" onclick="event.stopPropagation();swsiOpenTheoryEncoded(\''+E(t.n)+'\')">'+H(t.n)+'</button>';});
      h+='</div>';
    }
    if(es.length){
      h+='<div class="swsi-k-related-label">相關申論／練習題（'+es.length+'）</div>';
      es.slice(0,6).forEach(function(e){h+='<div class="swsi-k-question" onclick="event.stopPropagation();swsiOpenEssayEncoded(\''+E(e.id)+'\',\''+E(e.subject||'全部科目')+'\')"><div class="q">'+H(sn(e.topic||e.q,58))+'</div><div class="meta">'+H(e.qtype||'申論題')+(e.year?' · '+H(e.year)+' 年':'')+' · '+H(e.subject||'')+'</div></div>';});
      if(es.length>6)h+='<div class="swsi-k-more">還有 '+(es.length-6)+' 題，可用搜尋繼續縮小。</div>';
    }
    if(!mc.length&&!es.length)h+='<div class="swsi-k-muted">目前還沒有建立到考題的直接連結；可用「搜尋全部考法」從題目文字繼續找。</div>';
    return h+'</div>';
  }

  renderLaws=function(){
    var q=String(lawQ||'').trim(),list=LAWS;
    if(q)list=LAWS.filter(function(l){return (l.n+' '+l.d+' '+l.p+' '+l.c+' '+l.a+' '+(l.u||'')+' '+A(l.k).join(' ')).toLowerCase().indexOf(q.toLowerCase())>=0;});
    var order=[],byD={};
    list.forEach(function(l){if(!byD[l.d]){byD[l.d]=[];order.push(l.d);}byD[l.d].push(l);});
    var groups=order.map(function(d){
      var cards=byD[d].map(function(l){
        var gi=LAWS.indexOf(l),open=lawOpen===gi;
        return '<div class="ecard '+(open?'open':'')+'"><div class="ehead" onclick="toggleLaw('+gi+')"><div class="etopic">'+H(l.n)+'</div>'+(open?'':'<div class="ehint">點開看重點與歷屆考法 ›</div>')+'</div>'+
          (open?'<div class="ebodywrap" onclick="event.stopPropagation()"><div style="margin-bottom:13px;line-height:1.7"><b style="color:var(--ink-soft)">管什麼</b><br>'+H(l.p)+'</div><div style="margin-bottom:13px;line-height:1.7"><b style="color:var(--pine)">核心重點</b><br>'+H(l.c)+'</div><div style="margin-bottom:13px;line-height:1.7"><b style="color:var(--gold)">申論怎麼用</b><br>'+H(l.a)+'</div>'+
          (l.u?'<div style="margin-bottom:13px;line-height:1.7;background:var(--wrong-bg);padding:10px 12px;border-radius:10px"><b style="color:var(--wrong)">⚠ 修法動態</b><br>'+H(l.u)+'</div>':'')+
          '<div class="kws">'+A(l.k).map(function(k){return '<span class="kw">'+H(k)+'</span>';}).join('')+'</div>'+lawKnowledgeNetHTML(l,gi)+'<button class="ecollapse" onclick="toggleLaw('+gi+')">▲ 收合</button></div>':'')+'</div>';
      }).join('');
      return '<div class="subj-pill" style="margin-top:16px">'+H(d)+'</div>'+cards;
    }).join('');
    app.innerHTML='<div class="swsi-k-pagelead"><button onclick="go(\'topics\')">‹ 回學習工具</button><button onclick="swsiKnowledgeSearch(\'\')">⌕ 全域搜尋</button></div><div class="section-h">重點法規速查</div><div class="section-s">先抓法規重點，再直接看它曾經怎麼出現在選擇題與申論。<br><span style="color:var(--ink-soft);font-size:12px">※ 法規會修正，應試前仍以全國法規資料庫最新版為準。</span></div><input placeholder="搜尋法規或關鍵詞…" value="'+H(lawQ||'')+'" oninput="lawQ=this.value;lawOpen=null;render()" style="width:100%;box-sizing:border-box;padding:11px 14px;border:1px solid var(--line);border-radius:12px;font-family:inherit;font-size:14px;margin-bottom:4px;background:#fff;color:var(--ink)">'+(list.length?groups:'<div class="empty" style="padding:40px 0"><p>找不到符合的法規。</p></div>');
  };

  var oldRenderTheories=renderTheories;
  renderTheories=function(){
    oldRenderTheories();
    var back=document.querySelector('#app > button');
    if(back&&/回考點/.test(back.textContent||''))back.textContent='‹ 回學習工具';
    if(!document.querySelector('#app .swsi-k-pagelead')){
      var lead=document.createElement('div');lead.className='swsi-k-pagelead';lead.innerHTML='<span></span><button type="button" onclick="swsiKnowledgeSearch(\'\')">⌕ 全域搜尋</button>';
      var first=document.querySelector('#app .section-h');if(first)first.insertAdjacentElement('beforebegin',lead);
    }
    var sub=document.querySelector('#app .section-s');if(sub)sub.innerHTML='先理解理論，再直接看它和哪些歷屆選擇題、申論與法規連在一起。';
  };

})();
/* SWSI Law Trust UI Contract 2026-08-27
   Law card data is canonicalized at build time. This module owns presentation and runtime markers only.
*/
(function(){
  'use strict';

  var CHECKED_AT='2026-08-26';
  var VERIFY_CHECKED='checked';
  var NEW_RESIDENT_BASIC_ACT='新住民基本法';

  function H(v){
    return String(v==null?'':v).replace(/[&<>"']/g,function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function kindLabel(kind){
    return kind==='policy'?'政策／行政方案':kind==='convention'?'公約／人權框架':'現行法律';
  }

  function statusText(x){
    if(x.verify_status===VERIFY_CHECKED)return '✓ 官方來源已逐卡核對';
    return '○ 已連結官方來源・摘要待逐卡複核';
  }

  function trustHTML(x){
    if(!x)return '';
    var checked=x.checked_at?(' · '+x.checked_at):'';
    var good=x.verify_status===VERIFY_CHECKED;
    var bg=good?'#EEF5F1':'#F7F4EA',bd=good?'#CFE0D8':'#E5DCC1',fg=good?'#3F6961':'#756E57';
    var h='<div class="swsi-law-trust" style="margin:14px 0 3px;padding:12px 13px;border:1px solid '+bd+';border-radius:12px;background:'+bg+';font-family:\'Noto Sans TC\',sans-serif">'+
      '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap"><b style="font-size:12.5px;color:'+fg+'">'+statusText(x)+checked+'</b><span style="font-size:10.5px;border:1px solid '+bd+';background:#fff;border-radius:999px;padding:3px 8px;color:'+fg+'">'+kindLabel(x.source_kind)+'</span></div>';
    if(x.trust_note)h+='<div style="font-size:11.5px;line-height:1.65;color:var(--ink-soft);margin-top:7px">'+H(x.trust_note)+'</div>';
    if(x.source_url)h+='<div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:9px"><a href="'+H(x.source_url)+'" target="_blank" rel="noopener noreferrer" style="display:inline-block;text-decoration:none;border:1px solid var(--line);background:#fff;color:var(--pine-deep);border-radius:9px;padding:6px 9px;font-size:11.5px;font-weight:700">開啟'+H(x.source_label||'官方來源')+' ↗</a>'+
      (x.secondary_url?'<a href="'+H(x.secondary_url)+'" target="_blank" rel="noopener noreferrer" style="display:inline-block;text-decoration:none;border:1px solid var(--line);background:#fff;color:var(--pine-deep);border-radius:9px;padding:6px 9px;font-size:11.5px;font-weight:700">'+H(x.secondary_label||'官方補充')+' ↗</a>':'')+'</div>';
    return h+'</div>';
  }

  function applySpecialLawStatus(x){
    if(!x||x.n!==NEW_RESIDENT_BASIC_ACT)return;
    var panel=document.querySelector('#app .ecard.open .swsi-law-trust');
    if(!panel)return;
    var badge=panel.querySelector('span');
    if(!badge)return;
    badge.textContent='已制定公布・施行日另定';
    badge.style.color='#756E57';
    badge.style.borderColor='#E5DCC1';
  }

  var oldRenderLaws=renderLaws;
  renderLaws=function(){
    oldRenderLaws();
    try{
      var title=document.querySelector('#app .section-h');
      if(title&&title.textContent.indexOf('法規')>=0)title.textContent='法規與政策速查';
      var sub=document.querySelector('#app .section-s');
      if(sub)sub.innerHTML='先抓官方法規與政策的核心，再接回歷屆考題。<br><span style="color:var(--ink-soft);font-size:12px">✓「已逐卡核對」代表摘要已和官方來源重新比對；「待逐卡複核」只代表已找到官方來源，內容仍不冒充已核對。法律、政策與公約會分開標示。</span>';
      if(typeof lawOpen==='number'&&lawOpen>=0&&LAWS[lawOpen]){
        var item=LAWS[lawOpen];
        var open=document.querySelector('#app .ecard.open .ebodywrap');
        if(open&&!open.querySelector('.swsi-law-trust'))open.insertAdjacentHTML('beforeend',trustHTML(item));
        applySpecialLawStatus(item);
      }
    }catch(e){console.warn('law trust render skipped',e);}
  };

  window.SWSI_LAW_TRUST={
    version:'SWSI Law Trust Layer V1 2026-08-26',
    checkedAt:CHECKED_AT,
    verifiedCount:function(){return LAWS.filter(function(x){return x&&x.verify_status===VERIFY_CHECKED;}).length;}
  };

  window.SWSI_NEW_RESIDENT_STATUS={version:'SWSI New Resident Basic Act Status Fix 2026-08-26'};

  window.SWSI_LAW_TRUST_FINAL={
    version:'SWSI Law Trust Final Batch 2026-08-26',
    checkedAt:CHECKED_AT
  };
})();
/* SWSI Theory Trust UI Contract 2026-08-27
   Theory card data is canonicalized at build time. This module owns presentation and runtime markers only.
*/
(function(){
  'use strict';

  var CHECKED_AT='2026-08-26';
  var VERIFY_CHECKED='checked';
  var rows=window.THEORIES||[];

  function E(v){
    if(typeof window.swsiEsc==='function')return window.swsiEsc(v);
    if(typeof window.esc==='function')return window.esc(v);
    return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  function statusText(t){
    return t&&t.theory_verify_status===VERIFY_CHECKED?'✓ 理論內容已逐卡核對':'△ 平台整理・待逐卡複核';
  }

  function trustHTML(t){
    if(!t)return '';
    var good=t.theory_verify_status===VERIFY_CHECKED;
    var bg=good?'#EEF5F1':'#F7F4EA',bd=good?'#CFE0D8':'#E5DCC1',fg=good?'#3F6961':'#756E57';
    var date=t.theory_checked_at?(' · '+t.theory_checked_at):'';
    var note=t.theory_trust_note||'這是 SWSI 整理的學習卡；尚未完成本階段逐卡校正，請搭配課本與老師教材理解。';
    return '<div class="swsi-theory-trust" style="margin:14px 0 10px;padding:12px 13px;border:1px solid '+bd+';border-radius:12px;background:'+bg+';font-family:\'Noto Sans TC\',sans-serif">'
      +'<div style="font-size:12.5px;font-weight:700;color:'+fg+'">'+E(statusText(t)+date)+'</div>'
      +'<div style="font-size:11.5px;line-height:1.65;color:var(--ink-soft);margin-top:7px">'+E(note)+'</div>'
      +'<div style="font-size:10.8px;line-height:1.6;color:var(--ink-soft);margin-top:6px">理論卡是 SWSI 學習整理，不是考選部官方答案；正式題目若指定特定理論、學者或階段，以題目要求為準。</div>'
      +'</div>';
  }

  var previousRenderTheories=window.renderTheories||renderTheories;
  window.renderTheories=function(){
    previousRenderTheories();
    try{
      var sub=document.querySelector('#app .section-s');
      if(sub)sub.innerHTML='先理解理論，再直接看它和哪些歷屆選擇題、申論與法規連在一起。<br><span style="color:var(--ink-soft);font-size:12px">✓「已逐卡核對」代表這張 SWSI 理論摘要已重新拆解概念與學派；△「待逐卡複核」則還不能當成完成版。理論卡不是考選部官方答案。</span>';
      var t=null;
      try{if(typeof theoryOpen==='number'&&theoryOpen>=0)t=rows[theoryOpen]||null;}catch(_e){}
      var open=document.querySelector('#app .ecard.open .ebodywrap');
      if(open&&t&&!open.querySelector('.swsi-theory-trust')){
        var net=open.querySelector('.swsi-k-net'),collapse=open.querySelector('.ecollapse');
        var holder=document.createElement('div');holder.innerHTML=trustHTML(t);
        var panel=holder.firstElementChild;
        if(panel)open.insertBefore(panel,net||collapse||null);
      }
    }catch(e){console.warn('theory trust render skipped',e);}
  };
  try{renderTheories=window.renderTheories;}catch(_e){}

  window.SWSI_THEORY_TRUST={
    version:'SWSI Theory Trust Final 2026-08-26',
    checkedAt:CHECKED_AT,
    batch1:'SWSI Theory Trust Batch 1 2026-08-26',
    batch2:'SWSI Theory Trust Batch 2 2026-08-26',
    final:'SWSI Theory Trust Final Batch 2026-08-26',
    verifiedCount:function(){return rows.filter(function(t){return t&&t.theory_verify_status===VERIFY_CHECKED;}).length;},
    totalCount:function(){return rows.length;},
    pendingCount:function(){return rows.filter(function(t){return t&&t.theory_verify_status!==VERIFY_CHECKED;}).length;},
    allChecked:function(){return rows.length===39 && this.verifiedCount()===39 && this.pendingCount()===0;}
  };

  window.SWSI_THEORY_TRUST_FINAL={
    version:'SWSI Theory Trust Final Batch 2026-08-26',
    total:function(){return rows.length;},
    checked:function(){return rows.filter(function(t){return t&&t.theory_verify_status===VERIFY_CHECKED;}).length;},
    pending:function(){return rows.filter(function(t){return t&&t.theory_verify_status!==VERIFY_CHECKED;}).map(function(t){return t.n;});}
  };
})();

/* SWSI Public Branding / Information Center 2026-08-28
   Public attribution, source notice, privacy summary and use terms.
   This layer does not change quiz/grading/AI runtime contracts.
*/
(function(){
  'use strict';

  var STYLE_ID='swsi-public-info-20260828-style';
  if(!document.getElementById(STYLE_ID)){
    var st=document.createElement('style');
    st.id=STYLE_ID;
    st.textContent=`
      .swsi-public-footer-brand{font-family:'Noto Sans TC',sans-serif;font-size:10.8px;line-height:1.7;color:var(--ink-soft)}
      .swsi-public-footer-brand strong{font-family:'Noto Serif TC',serif;color:var(--ink);font-size:11.5px}
      .swsi-public-footer-links{display:flex;justify-content:center;align-items:center;gap:4px 10px;flex-wrap:wrap;margin-top:5px}
      .swsi-public-footer-links button{border:0;background:transparent;color:#68736E;font:700 10.8px/1.45 'Noto Sans TC',sans-serif;cursor:pointer;padding:4px 2px;text-decoration:underline;text-decoration-color:#B9C2BD;text-underline-offset:3px}
      .swsi-public-footer-links button:hover,.swsi-public-footer-links button:focus-visible{color:var(--pine-deep)}
      .swsi-public-info-backdrop{position:fixed;inset:0;z-index:990;background:rgba(25,31,28,.4);display:flex;align-items:flex-end;justify-content:center;padding:14px 10px calc(14px + env(safe-area-inset-bottom));backdrop-filter:blur(2px)}
      .swsi-public-info-dialog{width:min(100%,540px);max-height:min(86vh,760px);max-height:min(86dvh,760px);overflow:auto;background:#FDFEFD;border:1px solid #D7E0DB;border-radius:20px;box-shadow:0 22px 60px rgba(25,31,28,.22);padding:19px 18px;color:var(--ink);font-family:'Noto Sans TC',sans-serif;overscroll-behavior:contain}
      .swsi-public-info-head{display:flex;gap:12px;align-items:flex-start;margin-bottom:12px}
      .swsi-public-info-head h2{font-family:'Noto Serif TC',serif;font-size:21px;line-height:1.35;margin:0}
      .swsi-public-info-head p{font-size:11.5px;line-height:1.6;color:var(--ink-soft);margin:3px 0 0}
      .swsi-public-info-close{margin-left:auto;flex:0 0 auto;width:36px;height:36px;border:1px solid var(--line);border-radius:50%;background:#fff;color:var(--ink-soft);font-size:19px;cursor:pointer}
      .swsi-public-info-body{font-size:13px;line-height:1.85;color:#414743}
      .swsi-public-info-body h3{font-family:'Noto Serif TC',serif;color:var(--pine-deep);font-size:15px;margin:17px 0 5px}
      .swsi-public-info-body h3:first-child{margin-top:0}
      .swsi-public-info-body p{margin:0 0 10px}
      .swsi-public-info-body ul{margin:5px 0 11px 20px;padding:0}
      .swsi-public-info-body li{margin:3px 0}
      .swsi-public-info-note{background:#F3F7F5;border-left:3px solid #91A9A0;border-radius:0 10px 10px 0;padding:10px 11px;margin:10px 0;color:#5D6762}
      .swsi-public-info-nav{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:0 0 14px}
      .swsi-public-info-nav button{border:1px solid var(--line);background:#fff;color:var(--ink-soft);border-radius:9px;min-height:36px;font:700 11px/1.3 'Noto Sans TC',sans-serif;cursor:pointer;padding:6px 3px}
      .swsi-public-info-nav button.on{background:var(--pine);border-color:var(--pine);color:#fff}
      @media(min-width:620px){.swsi-public-info-backdrop{align-items:center}.swsi-public-info-dialog{border-radius:18px}}
      @media(max-width:370px){.swsi-public-info-nav{grid-template-columns:1fr 1fr}.swsi-public-info-dialog{padding:16px 14px}}
    `;
    document.head.appendChild(st);
  }

  var INFO={
    about:{
      title:'關於 SWSI',
      sub:'Social Work Study Initiative｜社工師國考免費學習平台',
      html:`
        <h3>SWSI 是什麼？</h3>
        <p><b>SWSI</b> 代表 <b>Social Work Study Initiative</b>。這是一個以免費、集中、低門檻為方向的社工師國考學習平台。</p>
        <h3>為什麼開始做？</h3>
        <p>專案起點來自對社工學習環境的觀察：歷屆題庫與相關學習資源分散在不同地方；同時也看到同學使用各種刷題工具時，在資料整理、學習流程與使用體驗上仍有改善空間，因此開始嘗試把常用的學習工具集中到同一個平台。</p>
        <h3>誰發起的？</h3>
        <p><b>發起人暨產品規劃：熊品澄。</b></p>
        <p>產品方向、需求整理、功能取捨、實際測試與迭代由專案發起人主導；程式實作主要透過生成式 AI 協作完成，並搭配自動 QA、版本控制與部署流程持續維護。</p>
        <div class="swsi-public-info-note">SWSI 並非考選部、學校或補習班官方網站，也不代表任何補習班或教育機構。</div>
      `
    },
    sources:{
      title:'資料來源',
      sub:'正式考題以官方來源為最高依據',
      html:`
        <h3>歷屆考題與答案</h3>
        <p>正式歷屆試題與答案以<b>考選部公開之官方資料</b>為最高依據。SWSI 會進行資料整理、分類、顯示與學習輔助，但不把官方考題宣稱為平台原創內容。</p>
        <h3>法規與理論</h3>
        <p>法規整理會盡量連結或核對政府／主管機關等官方來源；理論、解析、考點、提示與申論學習內容屬 SWSI 的整理與學習輔助內容，可能包含 AI 協作產生或整理的文字。</p>
        <h3>AI 回饋</h3>
        <p>AI 批改與回饋只供練習與學習參考，<b>不是考選部官方評分，也不是正式考試成績</b>。若平台整理內容與官方資料不一致，應以官方資料為準。</p>
        <div class="swsi-public-info-note">SWSI 不主張超出原始資料來源、實際權利歸屬或適用法律範圍的權利。</div>
      `
    },
    privacy:{
      title:'隱私說明',
      sub:'只收平台運作真正需要的資料',
      html:`
        <h3>學習紀錄</h3>
        <p>部分刷題、錯題、設定與草稿資料會儲存在使用者自己的瀏覽器／裝置中，讓學習功能可以持續使用。</p>
        <h3>問題回報</h3>
        <p>使用「回報問題／提供建議」時，平台可能保存回報類型、文字內容、所在頁面或題目脈絡、應用版本、瀏覽器資訊，以及你<b>自願填寫</b>的聯絡方式。平台使用匿名化的 client identifier 雜湊協助防止濫用；回報資料表不設計成公開資料來源。</p>
        <h3>AI 功能</h3>
        <p>使用 AI 批改或 AI 回饋時，為完成該功能，你提交的文字或影像內容會經平台的 AI 代理服務傳送至模型服務供應商處理。請不要輸入密碼、身分證字號、醫療紀錄或其他不必要的敏感個資。</p>
        <h3>匿名使用統計</h3>
        <p>平台未來可能啟用匿名使用統計，用來了解訪客量、作答量與功能是否正常；設計原則是不以追蹤個人身分為目的，也不蒐集營運上不必要的敏感個資。</p>
      `
    },
    terms:{
      title:'使用條款',
      sub:'免費使用不等於可以冒用來源或重新包裝販售',
      html:`
        <h3>免費學習使用</h3>
        <p>SWSI 目前以免費學習平台方式提供。個人學生可以直接使用；老師、同學、社群或補習班也可以分享<b>官方公開網址</b>給學習者使用。</p>
        <h3>分享時請保留來源</h3>
        <p>分享 SWSI 網址不需要把它說成自己的服務。不得冒用 SWSI、熊品澄或其他來源名義，也不得讓使用者誤以為 SWSI 與某補習班、學校、政府機關存在未經確認的官方合作或背書。</p>
        <h3>商業整合／重新包裝</h3>
        <p>若機構希望進行白牌化、嵌入自家付費產品、批量整合、客製化、重新包裝、轉售，或把 SWSI 品牌／介面／平台整理內容作為自身商業服務的一部分，應先取得明確同意並另談合作條件。</p>
        <h3>內容責任</h3>
        <p>平台盡力維護題庫與學習內容，但不能保證所有整理、解析、AI 回饋或法規摘要永遠零錯誤。正式考題、答案與法規應回到官方來源核對；重要決策不應只依賴 AI 回覆。</p>
        <div class="swsi-public-info-note">第三方或政府來源資料之權利依原始來源及適用法律處理；本條款不把非 SWSI 所有的內容宣稱為 SWSI 所有。</div>
      `
    }
  };

  var lastOpener=null;

  function footer(){return document.querySelector('.wrap > footer')||document.querySelector('footer');}

  function ensureFooterBrand(){
    var f=footer();
    if(!f||f.querySelector('.swsi-public-footer-brand'))return;
    var box=document.createElement('div');
    box.className='swsi-public-footer-brand';
    box.innerHTML=`
      <strong>SWSI — Social Work Study Initiative</strong><br>
      社工師國考免費學習平台<br>
      發起人暨產品規劃：熊品澄 · AI 協作開發
      <div class="swsi-public-footer-links" aria-label="SWSI 公開資訊">
        <button type="button" data-swsi-public-info="about">關於 SWSI</button>
        <button type="button" data-swsi-public-info="sources">資料來源</button>
        <button type="button" data-swsi-public-info="privacy">隱私</button>
        <button type="button" data-swsi-public-info="terms">使用條款</button>
      </div>
      <div style="margin-top:3px">© 2026 SWSI · 免費公開學習工具</div>
      <div>正式考題以考選部官方資料為準；AI 回饋僅供練習參考</div>
    `;
    while(f.firstChild)f.removeChild(f.firstChild);
    f.appendChild(box);
  }

  function closeInfo(){
    var ov=document.getElementById('swsi-public-info-backdrop');
    if(ov)ov.remove();
    document.body.style.overflow='';
    try{if(lastOpener&&lastOpener.focus)lastOpener.focus();}catch(_e){}
    lastOpener=null;
  }
  window.swsiClosePublicInfo=closeInfo;

  function renderInfo(key){
    var info=INFO[key]||INFO.about;
    var nav=Object.keys(INFO).map(function(k){
      var label={about:'關於',sources:'資料來源',privacy:'隱私',terms:'使用條款'}[k];
      return '<button type="button" data-swsi-info-nav="'+k+'" class="'+(k===key?'on':'')+'">'+label+'</button>';
    }).join('');
    return '<div class="swsi-public-info-dialog" role="dialog" aria-modal="true" aria-labelledby="swsi-public-info-title" onclick="event.stopPropagation()">'+
      '<div class="swsi-public-info-head"><div><h2 id="swsi-public-info-title">'+info.title+'</h2><p>'+info.sub+'</p></div><button type="button" class="swsi-public-info-close" aria-label="關閉" onclick="swsiClosePublicInfo()">×</button></div>'+
      '<div class="swsi-public-info-nav">'+nav+'</div><div class="swsi-public-info-body">'+info.html+'</div></div>';
  }

  function openInfo(key,opener){
    closeInfo();
    lastOpener=opener||document.activeElement;
    var ov=document.createElement('div');
    ov.id='swsi-public-info-backdrop';
    ov.className='swsi-public-info-backdrop';
    ov.onclick=closeInfo;
    ov.innerHTML=renderInfo(key);
    document.body.appendChild(ov);
    document.body.style.overflow='hidden';
    var close=ov.querySelector('.swsi-public-info-close');
    if(close)close.focus();
  }
  window.swsiOpenPublicInfo=openInfo;

  document.addEventListener('click',function(ev){
    var b=ev.target&&ev.target.closest?ev.target.closest('[data-swsi-public-info]'):null;
    if(b){ev.preventDefault();openInfo(b.getAttribute('data-swsi-public-info'),b);return;}
    var nav=ev.target&&ev.target.closest?ev.target.closest('[data-swsi-info-nav]'):null;
    if(nav){
      var ov=document.getElementById('swsi-public-info-backdrop');
      if(ov){ov.innerHTML=renderInfo(nav.getAttribute('data-swsi-info-nav'));var c=ov.querySelector('.swsi-public-info-close');if(c)c.focus();}
    }
  });
  document.addEventListener('keydown',function(ev){if(ev.key==='Escape'&&document.getElementById('swsi-public-info-backdrop'))closeInfo();});

  ensureFooterBrand();
  var obs=new MutationObserver(function(){ensureFooterBrand();});
  obs.observe(document.body,{childList:true,subtree:true});

  window.SWSI_PUBLIC_INFO={version:'2026-08-28.v1',marker:'SWSI Public Branding / Information Center 2026-08-28'};
})();

/* SWSI Feedback / Quality Report V1 2026-08-26
   Quiet in-context reporting for MCQ, essay, theory, law and general site feedback.
   Reports go through a protected Supabase Edge Function; official exam content stays read-only.
*/
(function(){
  'use strict';

  var ENDPOINT='https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/swsi-feedback';
  var VERSION='SWSI Feedback V1 2026-08-26';
  var STYLE_ID='swsi-feedback-v1-style';
  var activeOpener=null;
  var lastContextKey='';

  if(!document.getElementById(STYLE_ID)){
    var st=document.createElement('style');
    st.id=STYLE_ID;
    st.textContent=`
      .swsi-report-mini{border:0;background:transparent;color:#68736E;font-family:'Noto Sans TC',sans-serif;font-size:11.5px;font-weight:700;line-height:1.3;padding:6px 2px;cursor:pointer;text-decoration:none;white-space:nowrap}
      .swsi-report-mini:hover,.swsi-report-mini:focus-visible{color:var(--pine-deep);text-decoration:underline;text-underline-offset:3px}
      .qmeta>.swsi-report-mini{margin-left:auto}
      .swsi-report-inline{display:flex;justify-content:flex-end;align-items:center;margin:4px 0 9px}
      .ecard.open>.swsi-report-inline{margin:10px 0 2px;padding-top:7px;border-top:1px solid rgba(220,228,223,.7)}
      .swsi-report-footer-btn{border:0;background:transparent;color:#68736E;font-family:'Noto Sans TC',sans-serif;font-size:11px;font-weight:700;cursor:pointer;padding:5px 8px;margin-top:3px;text-decoration:underline;text-decoration-color:#B9C2BD;text-underline-offset:3px}

      .swsi-report-backdrop{position:fixed;inset:0;z-index:1000;background:rgba(25,31,28,.38);display:flex;align-items:flex-end;justify-content:center;padding:18px 12px calc(18px + env(safe-area-inset-bottom));backdrop-filter:blur(2px)}
      .swsi-report-dialog{width:min(100%,520px);max-height:min(86vh,720px);overflow:auto;background:#FDFEFD;border:1px solid #D7E0DB;border-radius:20px;box-shadow:0 22px 60px rgba(25,31,28,.22);padding:18px 17px 17px;color:var(--ink);font-family:'Noto Sans TC',sans-serif}
      .swsi-report-head{display:flex;align-items:flex-start;gap:12px;margin-bottom:11px}
      .swsi-report-head h2{font-family:'Noto Serif TC',serif;font-size:20px;line-height:1.35;margin:0;color:var(--ink)}
      .swsi-report-head p{font-size:11.5px;color:var(--ink-soft);line-height:1.55;margin:3px 0 0}
      .swsi-report-close{margin-left:auto;flex:0 0 auto;width:36px;height:36px;border:1px solid var(--line);border-radius:50%;background:#fff;color:var(--ink-soft);font-size:19px;line-height:1;cursor:pointer}
      .swsi-report-context{background:#F3F7F5;border:1px solid #DDE8E2;border-radius:12px;padding:10px 11px;margin-bottom:11px;font-size:11.5px;line-height:1.6;color:#5F6964;word-break:break-word}
      .swsi-report-context b{color:var(--pine-deep)}
      .swsi-report-trust{border-left:3px solid #91A9A0;background:#F8FAF9;border-radius:0 10px 10px 0;padding:9px 10px;margin-bottom:13px;font-size:11.5px;line-height:1.65;color:#626D68}
      .swsi-report-trust.official{border-left-color:#8E8061;background:#FBF8F1}
      .swsi-report-field{display:block;margin:0 0 12px}
      .swsi-report-field>span{display:block;font-size:12px;font-weight:800;color:var(--ink);margin-bottom:6px}
      .swsi-report-field select,.swsi-report-field textarea,.swsi-report-field input{width:100%;box-sizing:border-box;border:1px solid #CCD7D1;border-radius:11px;background:#fff;color:var(--ink);font:inherit;font-size:14px;outline:none}
      .swsi-report-field select,.swsi-report-field input{min-height:45px;padding:10px 11px}
      .swsi-report-field textarea{min-height:126px;resize:vertical;padding:11px 12px;line-height:1.65}
      .swsi-report-field select:focus,.swsi-report-field textarea:focus,.swsi-report-field input:focus{border-color:var(--pine);box-shadow:0 0 0 3px rgba(79,126,118,.08)}
      .swsi-report-help{display:flex;justify-content:space-between;gap:8px;margin-top:4px;color:var(--ink-soft);font-size:10.5px;line-height:1.45}
      .swsi-report-actions{display:grid;grid-template-columns:1fr 1.45fr;gap:8px;margin-top:2px}
      .swsi-report-actions button{min-height:45px;border-radius:11px;font-family:'Noto Sans TC',sans-serif;font-size:13.5px;font-weight:800;cursor:pointer}
      .swsi-report-cancel{background:#fff;color:var(--ink-soft);border:1px solid var(--line)}
      .swsi-report-submit{background:var(--pine-deep);color:#fff;border:0}
      .swsi-report-submit:disabled{opacity:.55;cursor:wait}
      .swsi-report-status{min-height:20px;margin-top:9px;font-size:11.5px;line-height:1.55;color:var(--ink-soft)}
      .swsi-report-status.err{color:#92584E}.swsi-report-status.ok{color:var(--pine-deep);font-weight:700}
      .swsi-report-receipt{padding:18px 5px 4px;text-align:center}
      .swsi-report-receipt .check{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;background:#E4EFEA;color:var(--pine-deep);font-size:23px;font-weight:900;margin:0 auto 10px}
      .swsi-report-receipt h3{font-family:'Noto Serif TC',serif;font-size:19px;margin-bottom:6px}
      .swsi-report-receipt p{font-size:12.5px;line-height:1.7;color:var(--ink-soft);margin:0}
      .swsi-report-receipt .no{font-size:11px;margin-top:7px;color:#78817D}
      .swsi-report-done{width:100%;min-height:44px;border:0;border-radius:11px;background:var(--pine-deep);color:#fff;font-family:'Noto Sans TC',sans-serif;font-size:13.5px;font-weight:800;margin-top:15px;cursor:pointer}
      @media(min-width:620px){.swsi-report-backdrop{align-items:center}.swsi-report-dialog{border-radius:18px}}
      @media(max-width:370px){.swsi-report-actions{grid-template-columns:1fr}.swsi-report-dialog{padding:16px 14px}}
    `;
    document.head.appendChild(st);
  }

  function H(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function S(v,n){var s=String(v==null?'':v).replace(/\s+/g,' ').trim();return s.length>n?s.slice(0,n)+'…':s;}
  function num(v){var n=parseInt(v,10);return Number.isFinite(n)?n:null;}

  function currentContext(){
    var c={context_type:'general',context_id:null,context_title:'網站整體',source_kind:'swsi',subject:null,exam_year:null,exam_round:null,question_no:null};
    try{
      var item=(typeof queue!=='undefined'&&Array.isArray(queue)&&typeof idx!=='undefined')?queue[idx]:null;
      if(item&&document.querySelector('#app .qcard')){
        var official=!/時事|預測|自製/.test(String(item.qtype||'')+' '+String(item.id||''));
        return {
          context_type:'mcq',context_id:item.id||null,context_title:S(item.question||item.q||item.topic||'選擇題',480),source_kind:official?'official_exam':'swsi',
          subject:item.subject||null,exam_year:num(item.year),exam_round:num(item.round),question_no:num(item.qno||item.question_no)
        };
      }
    }catch(_e){}
    try{
      if(typeof openEssay!=='undefined'&&openEssay){
        var rows=(typeof ESSAYS!=='undefined'&&Array.isArray(ESSAYS))?ESSAYS:(Array.isArray(window.ESSAYS)?window.ESSAYS:[]);
        var e=rows.find(function(x){return x&&String(x.id)===String(openEssay);});
        if(e){
          var off=!/時事|預測|自製/.test(String(e.qtype||'')+' '+String(e.id||'')+' '+String(e.subject||''));
          return {context_type:'essay',context_id:e.id||null,context_title:S(e.q||e.topic||'申論題',480),source_kind:off?'official_exam':'swsi',subject:e.subject||null,exam_year:num(e.year),exam_round:num(e.round),question_no:num(e.qno||e.question_no)};
        }
      }
    }catch(_e){}
    try{
      if(typeof theoryOpen!=='undefined'&&theoryOpen!==null&&theoryOpen!==undefined&&Array.isArray(THEORIES)&&THEORIES[theoryOpen]){
        var t=THEORIES[theoryOpen];
        return {context_type:'theory',context_id:t.n||null,context_title:t.n||'理論整理',source_kind:'swsi',subject:null,exam_year:null,exam_round:null,question_no:null};
      }
    }catch(_e){}
    try{
      if(typeof lawOpen!=='undefined'&&lawOpen!==null&&lawOpen!==undefined&&Array.isArray(LAWS)&&LAWS[lawOpen]){
        var l=LAWS[lawOpen];
        return {context_type:'law',context_id:l.n||null,context_title:l.n||'法規整理',source_kind:'swsi',subject:null,exam_year:null,exam_round:null,question_no:null};
      }
    }catch(_e){}
    return c;
  }

  function contextKey(c){return [c.context_type,c.context_id||'',c.exam_year||'',c.exam_round||'',c.question_no||''].join('|');}
  function contextLine(c){
    var bits=[];
    if(c.subject)bits.push(c.subject);
    if(c.exam_year)bits.push(c.exam_year+' 年');
    if(c.exam_round)bits.push('第 '+c.exam_round+' 次');
    if(c.question_no)bits.push('第 '+c.question_no+' 題');
    var type={mcq:'選擇題',essay:'申論題',theory:'理論',law:'法規',general:'網站'}[c.context_type]||'網站';
    return type+(bits.length?' · '+bits.join(' · '):'')+(c.context_id?' · '+S(c.context_id,80):'');
  }

  function defaultCategory(c){
    if(c.context_type==='law')return 'law_outdated';
    if(c.context_type==='theory')return 'theory_question';
    if(c.context_type==='mcq'||c.context_type==='essay')return 'explanation_error';
    return 'site_bug';
  }

  var CATS=[
    ['question_display','題目顯示問題'],['answer_question','答案疑問'],['explanation_error','解析／參考內容可能有誤'],['law_outdated','法規可能過期'],['theory_question','理論內容疑問'],['site_bug','網站功能異常'],['ai_feedback','AI 回饋問題'],['suggestion','功能建議'],['other','其他']
  ];

  function closeReport(){
    var ov=document.getElementById('swsi-report-backdrop');
    if(ov)ov.remove();
    document.body.style.overflow='';
    try{if(activeOpener&&activeOpener.focus)activeOpener.focus();}catch(_e){}
    activeOpener=null;
  }
  window.swsiCloseReport=closeReport;

  function modalHTML(c){
    var official=c.source_kind==='official_exam';
    var options=CATS.map(function(x){return '<option value="'+x[0]+'"'+(x[0]===defaultCategory(c)?' selected':'')+'>'+H(x[1])+'</option>';}).join('');
    return '<div class="swsi-report-dialog" role="dialog" aria-modal="true" aria-labelledby="swsi-report-title" onclick="event.stopPropagation()">'+
      '<div class="swsi-report-head"><div><h2 id="swsi-report-title">回報問題</h2><p>不用找題號，我們會自動附上目前位置。</p></div><button class="swsi-report-close" type="button" aria-label="關閉回報視窗" onclick="swsiCloseReport()">×</button></div>'+
      '<div class="swsi-report-context"><b>目前位置</b><br>'+H(contextLine(c))+(c.context_title?'<br>'+H(S(c.context_title,150)):'')+'</div>'+
      '<div class="swsi-report-trust'+(official?' official':'')+'">'+(official?'正式歷屆試題以考選部官方資料為準。若題目、答案或顯示疑似有問題，我們會先核對官方來源，不會直接修改正式試題。':'SWSI 整理內容可能有疏漏，歡迎協助回報；收到後會先核對再修正。')+'</div>'+
      '<form id="swsi-report-form">'+
        '<label class="swsi-report-field"><span>你想回報什麼？</span><select id="swsi-report-category" required>'+options+'</select></label>'+
        '<label class="swsi-report-field"><span>請告訴我發生什麼事</span><textarea id="swsi-report-message" minlength="3" maxlength="2000" required placeholder="例如：這題解析提到的法規好像已經修正，可以再確認嗎？"></textarea><div class="swsi-report-help"><i style="font-style:normal">請不要填密碼、身分證或其他敏感資料。</i><i id="swsi-report-count" style="font-style:normal">0 / 2000</i></div></label>'+
        '<label class="swsi-report-field"><span>聯絡方式（選填）</span><input id="swsi-report-contact" maxlength="200" autocomplete="off" placeholder="Email 或其他方便聯絡的方式"><div class="swsi-report-help"><i style="font-style:normal">只在需要釐清問題時使用，不會顯示在網站上。</i></div></label>'+
        '<input id="swsi-report-website" value="" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute;left:-9999px;width:1px;height:1px;opacity:0">'+
        '<div class="swsi-report-actions"><button type="button" class="swsi-report-cancel" onclick="swsiCloseReport()">取消</button><button id="swsi-report-submit" type="submit" class="swsi-report-submit">送出回報</button></div><div id="swsi-report-status" class="swsi-report-status" aria-live="polite"></div>'+
      '</form></div>';
  }

  window.swsiOpenReport=function(trigger){
    var c=currentContext();
    activeOpener=trigger&&trigger.nodeType===1?trigger:document.activeElement;
    closeReport();
    activeOpener=trigger&&trigger.nodeType===1?trigger:activeOpener;
    var ov=document.createElement('div');ov.id='swsi-report-backdrop';ov.className='swsi-report-backdrop';ov.onclick=closeReport;ov.innerHTML=modalHTML(c);document.body.appendChild(ov);document.body.style.overflow='hidden';
    ov._swsiContext=c;
    var msg=document.getElementById('swsi-report-message');
    var count=document.getElementById('swsi-report-count');
    if(msg){msg.addEventListener('input',function(){if(count)count.textContent=msg.value.length+' / 2000';});setTimeout(function(){try{msg.focus();}catch(_e){}},30);}
    var form=document.getElementById('swsi-report-form');if(form)form.addEventListener('submit',submitReport);
  };

  async function submitReport(ev){
    ev.preventDefault();
    var ov=document.getElementById('swsi-report-backdrop');if(!ov)return;
    var c=ov._swsiContext||currentContext();
    var message=(document.getElementById('swsi-report-message').value||'').trim();
    var contact=(document.getElementById('swsi-report-contact').value||'').trim();
    var category=document.getElementById('swsi-report-category').value;
    var honeypot=(document.getElementById('swsi-report-website').value||'').trim();
    var status=document.getElementById('swsi-report-status');
    var btn=document.getElementById('swsi-report-submit');
    if(message.length<3){status.className='swsi-report-status err';status.textContent='請至少寫 3 個字。';return;}
    if(honeypot){closeReport();return;}
    btn.disabled=true;btn.textContent='送出中…';status.className='swsi-report-status';status.textContent='';
    var payload={
      category:category,context_type:c.context_type,context_id:c.context_id,context_title:c.context_title,source_kind:c.source_kind,
      subject:c.subject,exam_year:c.exam_year,exam_round:c.exam_round,question_no:c.question_no,message:message,contact:contact||null,
      page_path:location.pathname+location.search+location.hash,app_version:VERSION,
      metadata:{screen_width:window.screen&&window.screen.width||null,screen_height:window.screen&&window.screen.height||null,locale:navigator.language||null,referrer_host:(function(){try{return document.referrer?new URL(document.referrer).host:null;}catch(_e){return null;}})()}
    };
    try{
      var client=(typeof window.swsiGetClientId==='function')?window.swsiGetClientId():('swsi_feedback_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2));
      var res=await fetch(ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json','X-SWSI-Client-ID':client},body:JSON.stringify(payload)});
      var data={};try{data=await res.json();}catch(_e){}
      if(!res.ok)throw new Error(data&&data.error&&data.error.message?data.error.message:'回報暫時無法送出，請稍後再試。');
      var dialog=ov.querySelector('.swsi-report-dialog');
      dialog.innerHTML='<div class="swsi-report-receipt"><div class="check">✓</div><h3>收到</h3><p>'+H(data.message||'我們會核對這個問題。你可以繼續作答。')+'</p>'+(data.report_no?'<div class="no">回報編號 #'+H(data.report_no)+'</div>':'')+'<button class="swsi-report-done" type="button" onclick="swsiCloseReport()">繼續使用 SWSI</button></div>';
    }catch(err){
      status.className='swsi-report-status err';status.textContent=err&&err.message?err.message:'回報暫時無法送出，請稍後再試。';btn.disabled=false;btn.textContent='送出回報';
    }
  }

  function makeMini(cls){var b=document.createElement('button');b.type='button';b.className=cls||'swsi-report-mini';b.textContent='⚑ 回報問題';b.setAttribute('aria-label','回報目前內容的問題');b.onclick=function(){window.swsiOpenReport(b);};return b;}

  function ensureFooter(){
    var f=document.querySelector('footer');if(!f||f.querySelector('.swsi-report-footer-btn'))return;
    var b=makeMini('swsi-report-footer-btn');b.textContent='回報問題／提供建議';b.setAttribute('aria-label','回報網站問題或提供建議');f.appendChild(b);
  }

  function ensureContextButton(){
    var c=currentContext(),key=contextKey(c);lastContextKey=key;
    if(c.context_type==='mcq'){
      var meta=document.querySelector('#app .qcard .qmeta');if(meta&&!meta.querySelector('.swsi-report-mini'))meta.appendChild(makeMini());
      return;
    }
    if(c.context_type==='theory'||c.context_type==='law'){
      var card=document.querySelector('#app .ecard.open');if(card&&!card.querySelector(':scope > .swsi-report-inline')){var row=document.createElement('div');row.className='swsi-report-inline';row.appendChild(makeMini());card.appendChild(row);}return;
    }
    if(c.context_type==='essay'){
      var ta=document.querySelector('#app .wta');if(ta&&!document.querySelector('#app .swsi-report-inline[data-swsi-essay-report="1"]')){var r=document.createElement('div');r.className='swsi-report-inline';r.dataset.swsiEssayReport='1';r.appendChild(makeMini());ta.parentNode.insertBefore(r,ta);}return;
    }
  }

  function enhance(){ensureFooter();ensureContextButton();}
  window.SWSI_FEEDBACK={version:VERSION,endpoint:ENDPOINT,currentContext:currentContext,open:function(){window.swsiOpenReport();}};
  enhance();
  document.addEventListener('keydown',function(ev){if(ev.key==='Escape'&&document.getElementById('swsi-report-backdrop'))closeReport();});
  try{var pending=false;new MutationObserver(function(){if(pending)return;pending=true;Promise.resolve().then(function(){pending=false;enhance();});}).observe(document.body,{childList:true,subtree:true});}catch(_e){}
})();

/* SWSI Feedback Context State Owner 2026-08-27
   Keep context cleanup local to the feedback action instead of continuously
   watching the whole document. The core feedback module still owns context
   derivation; this compatibility owner clears stale cross-view state before a
   report is opened and protects the legacy honeypot from Safari AutoFill false
   positives without adding another swsiOpenReport owner.
*/
(function(){
  'use strict';

  var baseOpen=window.swsiOpenReport;
  if(typeof baseOpen!=='function') return;
  if(baseOpen.__swsiContextStateOwner==='2026-08-27') return;

  function syncForCurrentView(){
    var v='';
    try{v=String(view||'');}catch(_e){}
    try{
      if(v==='laws' && typeof theoryOpen!=='undefined' && theoryOpen!==null) theoryOpen=null;
      if(v==='theories' && typeof lawOpen!=='undefined' && lawOpen!==null) lawOpen=null;
      if(v==='essay'){
        if(typeof theoryOpen!=='undefined' && theoryOpen!==null) theoryOpen=null;
        if(typeof lawOpen!=='undefined' && lawOpen!==null) lawOpen=null;
      }
    }catch(_e){}
  }

  function protectHoneypot(){
    var form=document.getElementById('swsi-report-form');
    var hp=document.getElementById('swsi-report-website');
    if(!form||!hp)return;

    /* Safari may ignore autocomplete="off" and populate off-screen fields.
       A real user's report must never be silently discarded for that reason.
       Server-side origin validation + DB rate limits remain authoritative. */
    try{
      hp.value='';
      hp.readOnly=true;
      hp.setAttribute('autocomplete','new-password');
      hp.setAttribute('data-lpignore','true');
      hp.setAttribute('data-1p-ignore','true');
    }catch(_e){}

    if(form.dataset.swsiHoneypotGuard==='1')return;
    form.dataset.swsiHoneypotGuard='1';
    form.addEventListener('submit',function(){
      try{hp.value='';}catch(_e){}
    },true);
  }

  function openWithCurrentContext(){
    syncForCurrentView();
    var result=baseOpen.apply(this,arguments);
    protectHoneypot();
    return result;
  }
  openWithCurrentContext.__swsiContextStateOwner='2026-08-27';
  openWithCurrentContext.__swsiBaseOpen=baseOpen;
  window.swsiOpenReport=openWithCurrentContext;
  window.SWSI_FEEDBACK_SAFARI_GUARD={version:'2026-08-29'};
})();

/* SWSI Feedback Compact UI V2 2026-08-26
   Keep report metadata in the payload, but make the student-facing form short and contextual.
*/
(function(){
  'use strict';

  var STYLE_ID='swsi-feedback-compact-v2-style';
  if(!document.getElementById(STYLE_ID)){
    var st=document.createElement('style');
    st.id=STYLE_ID;
    st.textContent=`
      .swsi-report-backdrop{overscroll-behavior:contain}
      .swsi-report-dialog[data-swsi-compact="2"]{max-height:min(78vh,620px);max-height:min(78dvh,620px);padding:16px 16px 15px;overscroll-behavior:contain}
      .swsi-report-dialog[data-swsi-compact="2"] .swsi-report-head{margin-bottom:8px}
      .swsi-report-dialog[data-swsi-compact="2"] .swsi-report-head h2{font-size:19px}
      .swsi-report-dialog[data-swsi-compact="2"] .swsi-report-head p{margin-top:2px}
      .swsi-report-dialog[data-swsi-compact="2"] .swsi-report-context{display:none!important}
      .swsi-report-dialog[data-swsi-compact="2"] .swsi-report-trust{padding:7px 9px;margin-bottom:10px;font-size:10.8px;line-height:1.55}
      .swsi-report-dialog[data-swsi-compact="2"] .swsi-report-field{margin-bottom:10px}
      .swsi-report-dialog[data-swsi-compact="2"] .swsi-report-field>span{margin-bottom:5px}
      .swsi-report-dialog[data-swsi-compact="2"] .swsi-report-field textarea{min-height:92px}
      .swsi-report-dialog[data-swsi-compact="2"] .swsi-report-help{font-size:10px}
      .swsi-report-dialog[data-swsi-compact="2"] .swsi-report-contact-help{display:none}
      @media(max-height:700px){
        .swsi-report-dialog[data-swsi-compact="2"]{max-height:82vh;max-height:82dvh}
        .swsi-report-dialog[data-swsi-compact="2"] .swsi-report-field textarea{min-height:78px}
      }
    `;
    document.head.appendChild(st);
  }

  var LABELS={
    question_display:'題目顯示異常',
    answer_question:'答案好像不對',
    explanation_error:'解析有疑問',
    law_outdated:'法規可能過期',
    theory_question:'理論內容疑問',
    site_bug:'網站功能異常',
    ai_feedback:'AI 回饋問題',
    suggestion:'功能建議',
    other:'其他'
  };

  function modeOf(dialog){
    var sel=dialog.querySelector('#swsi-report-category');
    var v=sel?sel.value:'';
    if(v==='law_outdated')return 'law';
    if(v==='theory_question')return 'theory';
    if(dialog.querySelector('.swsi-report-trust.official'))return 'exam';
    return 'general';
  }

  function allowedFor(mode){
    if(mode==='exam')return ['answer_question','explanation_error','question_display','other'];
    if(mode==='law')return ['law_outdated','other'];
    if(mode==='theory')return ['theory_question','other'];
    return ['site_bug','ai_feedback','suggestion','other'];
  }

  function compact(dialog){
    if(!dialog || dialog.dataset.swsiCompact==='2')return;
    var sel=dialog.querySelector('#swsi-report-category');
    if(!sel)return;

    var mode=modeOf(dialog);
    var oldValue=sel.value;
    var allowed=allowedFor(mode);
    sel.innerHTML=allowed.map(function(v){
      return '<option value="'+v+'">'+LABELS[v]+'</option>';
    }).join('');
    sel.value=allowed.indexOf(oldValue)>=0?oldValue:allowed[0];

    var title=dialog.querySelector('#swsi-report-title');
    if(title)title.textContent=mode==='general'?'回報／提供建議':'回報這個問題';

    var headP=dialog.querySelector('.swsi-report-head p');
    if(headP)headP.textContent=mode==='general'?'簡單告訴我們你的問題或建議。':'簡單告訴我們哪裡怪怪的。';

    var trust=dialog.querySelector('.swsi-report-trust');
    if(trust){
      if(mode==='exam')trust.textContent='歷屆題目會先核對考選部資料後再處理。';
      else if(mode==='law'||mode==='theory')trust.textContent='SWSI 整理內容收到回報後會先核對再修正。';
      else trust.style.display='none';
    }

    var catField=sel.closest('.swsi-report-field');
    var catLabel=catField&&catField.querySelector(':scope > span');
    if(catLabel)catLabel.textContent=mode==='general'?'你想告訴我們什麼？':'你發現什麼問題？';

    var msg=dialog.querySelector('#swsi-report-message');
    if(msg){
      var msgField=msg.closest('.swsi-report-field');
      var msgLabel=msgField&&msgField.querySelector(':scope > span');
      if(msgLabel)msgLabel.textContent='簡單說明一下';
      if(mode==='exam')msg.placeholder='例如：我上課學到的內容好像不太一樣，可以再確認嗎？';
      else if(mode==='law')msg.placeholder='例如：這個法規內容好像已經修正，可以再確認嗎？';
      else if(mode==='theory')msg.placeholder='例如：這個理論的說法和課本不太一樣，可以再確認嗎？';
      else msg.placeholder='例如：哪裡不好用，或你希望增加什麼？';
    }

    var contact=dialog.querySelector('#swsi-report-contact');
    if(contact){
      var contactField=contact.closest('.swsi-report-field');
      var help=contactField&&contactField.querySelector('.swsi-report-help');
      if(help)help.classList.add('swsi-report-contact-help');
      contact.placeholder='Email（不填也可以）';
    }

    dialog.dataset.swsiCompact='2';
  }

  function forceGeneralFooter(btn){
    if(!btn || btn.dataset.swsiGeneralBound==='1')return;
    btn.dataset.swsiGeneralBound='1';
    btn.onclick=function(){
      var qcards=Array.from(document.querySelectorAll('#app .qcard'));
      var saved=[];
      for(var i=0;i<qcards.length;i++){
        saved.push(qcards[i].className);
        qcards[i].classList.remove('qcard');
      }
      var hasEssay=false,hasTheory=false,hasLaw=false;
      var saveEssay,saveTheory,saveLaw;
      try{saveEssay=openEssay;openEssay=null;hasEssay=true;}catch(_e){}
      try{saveTheory=theoryOpen;theoryOpen=null;hasTheory=true;}catch(_e){}
      try{saveLaw=lawOpen;lawOpen=null;hasLaw=true;}catch(_e){}
      try{
        window.swsiOpenReport(btn);
      }finally{
        for(var j=0;j<qcards.length;j++)qcards[j].className=saved[j];
        try{if(hasEssay)openEssay=saveEssay;}catch(_e){}
        try{if(hasTheory)theoryOpen=saveTheory;}catch(_e){}
        try{if(hasLaw)lawOpen=saveLaw;}catch(_e){}
      }
    };
  }

  function scan(root){
    if(root&&root.matches&&root.matches('.swsi-report-dialog'))compact(root);
    var list=(root&&root.querySelectorAll)?root.querySelectorAll('.swsi-report-dialog'):[];
    for(var i=0;i<list.length;i++)compact(list[i]);
    var footerBtn=document.querySelector('footer .swsi-report-footer-btn');
    if(footerBtn)forceGeneralFooter(footerBtn);
  }

  scan(document);
  var obs=new MutationObserver(function(records){
    for(var i=0;i<records.length;i++){
      for(var j=0;j<records[i].addedNodes.length;j++){
        var n=records[i].addedNodes[j];
        if(n&&n.nodeType===1)scan(n);
      }
    }
    var footerBtn=document.querySelector('footer .swsi-report-footer-btn');
    if(footerBtn)forceGeneralFooter(footerBtn);
  });
  obs.observe(document.body,{childList:true,subtree:true});

  window.SWSI_FEEDBACK_COMPACT={version:'V2',marker:'SWSI Feedback Compact UI V2 2026-08-26'};
})();

/* SWSI Feedback Error Copy 2026-08-28
   Student-facing wording only. Keeps the feedback transport/API contract intact.
*/
(function(){
  'use strict';

  function friendly(raw){
    var s=String(raw||'').trim();
    var low=s.toLowerCase();
    if(!s)return '回報暫時無法送出，請稍後再試。';
    if(/429|too many|rate.?limit|頻繁|稍後.*分鐘/.test(low+s))return '送出得有點太頻繁了，請稍等一分鐘再試。';
    if(/failed to fetch|network|networkerror|load failed|internet|offline|連線|網路/.test(low+s))return '目前無法連線到回報服務，請確認網路後再試。';
    if(/500|502|503|504|internal server|service unavailable|gateway/.test(low))return '回報服務暫時忙碌，請稍後再試。';
    if(/timeout|timed out|逾時|超時/.test(low+s))return '回報服務回應較慢，請稍後再試一次。';
    return s;
  }

  function polish(){
    document.querySelectorAll('.swsi-report-status.err').forEach(function(el){
      var next=friendly(el.textContent);
      if(el.textContent!==next)el.textContent=next;
    });
  }

  var pending=false;
  new MutationObserver(function(){
    if(pending)return;
    pending=true;
    queueMicrotask(function(){pending=false;polish();});
  }).observe(document.documentElement,{childList:true,subtree:true,characterData:true});
  polish();
})();
/* ===== SWSI P0 AI utilities (2026-08-29) ===== */
(function(){
  'use strict';

  /* Layer 3 interaction guard only. Global mobile shell geometry now belongs to
     15.layout-foundation.part so later feature modules cannot fight over it. */
  var style=document.createElement('style');
  style.textContent=`button:disabled{pointer-events:none;}`;
  document.head.appendChild(style);

  window.effectiveEssayText=function(s){
    return String(s||'')
      .replace(/(^|\n)\s*(?:[一二三四五六七八九十百]+、|（[一二三四五六七八九十百]+）|\d+、|[a-zA-Z]\.|\([ivxlcdmIVXLCDM]+\))\s*/g,'$1')
      .replace(/[^\u3400-\u9FFF\uF900-\uFAFFa-zA-Z0-9]/g,'');
  };
  window.effectiveEssayLength=function(s){return window.effectiveEssayText(s).length;};

  window.writeBoxHTML=function(id){
    var saved=getDraft(id);
    return `<div class="wbox">
      <div class="wlabel">✍ 我的作答（自動儲存在這台裝置）</div>
      <div class="fmtbar">
        ${[['cn','一、'],['cnp','（一）'],['num','1、'],['lat','a.'],['rom','(i)']].map(function(p){return `<button class="fbtn" onclick="insertFmt('${id}','${p[0]}')">${p[1]}</button>`;}).join('')}
        <button class="fbtn clear" onclick="clearDraft('${id}')">清空</button>
      </div>
      <textarea id="ta_${id}" class="wta" placeholder="先別看骨架，自己試著寫。寫不出來就點上面的「拆題五步」。" oninput="saveDraft('${id}')">${esc(saved)}</textarea>
      <div class="wmeta"><span id="save_${id}">已儲存在這台裝置</span> · <span id="wc_${id}">${saved.length}</span> 字</div>
      ${aiFeedbackHTML(id)}
    </div>`;
  };

  window.saveDraft=function(id){
    var ta=document.getElementById('ta_'+id); if(!ta)return;
    var savedOK=true;
    try{localStorage.setItem(essayDraftKey(id),ta.value);}catch(e){savedOK=false;}
    var wc=document.getElementById('wc_'+id); if(wc)wc.textContent=ta.value.length;
    var st=document.getElementById('save_'+id);
    if(st){st.textContent=savedOK?'已儲存在這台裝置':'⚠ 尚未儲存';st.style.color=savedOK?'':'var(--wrong)';}
    var gb=document.getElementById('gbtn_'+id);
    if(gb)gb.style.display=window.effectiveEssayLength(ta.value)>0?'':'none';
  };

  window.swsiSetAIBusy=function(id,busy,mode){
    var t=document.getElementById('aitype_'+id),p=document.getElementById('aiphoto_'+id),f=document.getElementById('photo_'+id);
    if(t){t.disabled=!!busy;t.style.opacity=busy?'.55':'';t.style.cursor=busy?'not-allowed':'';t.textContent=(busy&&mode==='text')?'⏳ AI 回饋中…':'🤖 請 AI 看我的作答';}
    if(p){p.disabled=!!busy;p.style.opacity=busy?'.55':'';p.style.cursor=busy?'not-allowed':'';p.textContent=(busy&&mode==='photo')?'⏳ 照片處理／回饋中…':'📷 手寫作答 · 拍照請 AI 看';}
    if(f)f.disabled=!!busy;
  };

  window.swsiAICacheKey=function(id){return 'essay_ai_cache_'+id;};
  window.swsiGetAICache=function(id,answer){
    try{var x=JSON.parse(localStorage.getItem(window.swsiAICacheKey(id))||'null');return x&&x.answer===answer&&x.feedback?x:null;}catch(e){return null;}
  };
  window.swsiSetAICache=function(id,answer,feedback){
    try{localStorage.setItem(window.swsiAICacheKey(id),JSON.stringify({answer:answer,feedback:feedback,at:Date.now()}));}catch(e){}
  };

  var CLIENT_ID_KEY='swsi_ai_client_id_v1';
  window.swsiGetClientId=function(){
    var id='';
    try{id=(localStorage.getItem(CLIENT_ID_KEY)||'').trim();}catch(e){}
    if(/^[A-Za-z0-9_-]{16,128}$/.test(id))return id;

    try{
      if(crypto&&typeof crypto.randomUUID==='function'){
        id='swsi_'+crypto.randomUUID().replace(/-/g,'_');
      }else if(crypto&&typeof crypto.getRandomValues==='function'){
        var bytes=new Uint8Array(18);crypto.getRandomValues(bytes);
        id='swsi_'+Array.from(bytes).map(function(b){return b.toString(16).padStart(2,'0');}).join('');
      }
    }catch(e){}

    if(!id)id='swsi_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2)+Math.random().toString(36).slice(2);
    id=id.replace(/[^A-Za-z0-9_-]/g,'').slice(0,128);
    if(id.length<16)id=(id+'_anonymous_client_0000000000').slice(0,24);
    try{localStorage.setItem(CLIENT_ID_KEY,id);}catch(e){}
    return id;
  };

  window.swsiFetchWithTimeout=async function(url,options,ms){
    var ctrl=new AbortController(),timer=setTimeout(function(){ctrl.abort();},ms);
    var opts=Object.assign({},options||{});
    var headers=new Headers(opts.headers||{});
    headers.set('X-SWSI-Client-ID',window.swsiGetClientId());
    opts.headers=headers;
    opts.signal=ctrl.signal;
    try{return await fetch(url,opts);}
    finally{clearTimeout(timer);}
  };
})();
/* ===== SWSI P0 AI utilities END ===== *//* ===== SWSI Essay Trust Layer 2026-08-26 =====
   IMPORTANT: This layer never edits official past-exam question text.
   It only changes SWSI-authored guidance labels, trust status, and AI feedback prompts.
*/
(function(){
  'use strict';

  var GUIDE_VERSION='essay-trust-v1-20260826';
  window.SWSI_ESSAY_TRUST_VERSION=GUIDE_VERSION;

  function E(v){
    if(typeof window.swsiEsc==='function')return window.swsiEsc(v);
    if(typeof window.esc==='function')return window.esc(v);
    return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }
  function T(v){return String(v==null?'':v);}

  /* Existing guide rows were historically grouped by topic templates.
     Until a row is explicitly reviewed question-by-question, treat it as unverified.
     This metadata is SWSI guidance metadata only; official question records are untouched. */
  var guideMap=window.ESSAY_GUIDES||{};
  Object.keys(guideMap).forEach(function(id){
    var g=guideMap[id];
    if(g&&typeof g==='object'&&!g.review_status)g.review_status='needs_review';
  });

  window.swsiEssayGuideStatus=function(id){
    var g=(window.ESSAY_GUIDES||{})[id]||{};
    return g.review_status==='verified'?'verified':'needs_review';
  };
  window.swsiEssayGuideIsVerified=function(id){return window.swsiEssayGuideStatus(id)==='verified';};

  /* Beginner-friendly, non-score-claiming labels. */
  window.guideHTML=function(g){
    g=g||{};
    var verified=g.review_status==='verified';
    var badge=verified
      ? '<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:999px;background:var(--correct-bg);color:var(--pine);font-size:11px;font-weight:700">✓ 已逐題核對</span>'
      : '<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:999px;background:#FBF8EF;color:#7C704F;font-size:11px;font-weight:700">△ 參考架構待確認</span>';
    var note=verified
      ? '這是 SWSI 整理的學習參考，不是考選部官方答案。'
      : '這份內容尚未完成逐題核對，請把它當成思考提示，不要當成標準答案。';
    return '<div class="guide">'
      +'<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px"><b style="font-size:var(--fs-b)">參考架構</b>'+badge+'</div>'
      +'<div style="font-size:var(--fs-s);color:var(--ink-soft);line-height:1.7;margin:-4px 0 14px">'+E(note)+'</div>'
      +'<div class="gsec"><div class="glabel">這題主要在問</div><div class="gtext">'+E(g.kao||'尚未整理')+'</div></div>'
      +'<div class="gsec"><div class="glabel">可以先怎麼想</div><div class="gtext">'+E(g.dati||'尚未整理')+'</div></div>'
      +'<div class="gsec"><div class="glabel">可以分成這幾段</div><ul class="glist">'+(g.biaoti||[]).map(function(b){return '<li>'+E(b)+'</li>';}).join('')+'</ul></div>'
      +'<div class="gsec"><div class="glabel">可能用到的關鍵字</div><div class="kws">'+(g.kw||[]).map(function(k){return '<span class="kw">'+E(k)+'</span>';}).join('')+'</div></div>'
      +'</div>';
  };
  try{guideHTML=window.guideHTML;}catch(_e){}

  /* Version the cache so older feedback generated from over-trusted guide templates
     cannot silently reappear after this trust-layer change. */
  window.swsiAICacheKey=function(id){return 'essay_ai_cache_v2_'+GUIDE_VERSION+'_'+id;};

  function essayContext(id){
    var e=(window.ESSAYS||[]).find(function(x){return x&&x.id===id;})||{};
    var g=(window.ESSAY_GUIDES||{})[id]||{};
    var verified=window.swsiEssayGuideIsVerified(id);
    var reference='';
    if(verified){
      reference='【SWSI 已逐題核對的參考架構】\n'
        +'這題主要在問：'+T(g.kao||'')+'\n'
        +'可以先怎麼想：'+T(g.dati||'')+'\n'
        +'可以分成這幾段：'+(g.biaoti||[]).join('；')+'\n'
        +'可能用到的關鍵字：'+(g.kw||[]).join('、');
    }
    return {e:e,g:g,verified:verified,reference:reference};
  }

  function trustPrompt(extra){
    return '【最重要規則：整份回饋務必使用繁體中文。】\n'
      +'你是台灣社會工作師國家考試的「申論練習教練」，不是閱卷委員。\n'
      +'請把「正式考題本身」視為最高依據，先判斷題目究竟要求回答哪些事情，再閱讀學生作答。\n'
      +'若有附 SWSI 參考架構，它只能是輔助；如果參考架構與題意衝突、範圍過大或有疑義，必須以題目為準，不得強迫學生照參考架構回答。\n\n'
      +'規則：\n'
      +'- 這是練習回饋，不是官方評分，不給分數、不猜閱卷配分、不使用「必得分」「標準答案」等說法。\n'
      +'- 不要自行編造法條條號、年份、統計數字、學者或政策內容；不確定時直接說需要再核對。\n'
      +'- 題目若有多個子題，先確認學生是否每一問都有回答。\n'
      +'- 優先用新手看得懂的中文，避免只丟術語。\n'
      +'- 回饋總長約 250～400 字，具體但不要替學生寫完整標準答案。\n'
      +'- 回饋格式：一、題目要你答什麼；二、你已經做到什麼；三、下一步可以補什麼；最後一句簡短鼓勵。\n'
      +(extra||'');
  }

  function renderAIResult(id,out,txt,mode){
    if(typeof window.swsiSetAICache==='function'&&mode==='text'){
      var ta=document.getElementById('ta_'+id);
      try{window.swsiSetAICache(id,(ta?ta.value:'').trim(),txt);}catch(_e){}
    }
    out.innerHTML='<div style="margin-top:12px;background:#fff;border:1px solid var(--line);border-left:3px solid var(--pine);border-radius:10px;padding:14px;font-size:14px;line-height:1.8;color:var(--ink);white-space:pre-wrap">'+E(txt)+'</div>'
      +'<div style="font-size:11px;color:var(--ink-soft);margin-top:6px;line-height:1.6">⚠ AI 只提供申論練習回饋，不是考選部官方評分；法規、政策或年代內容若有疑義，請再查課本、老師或官方資料。</div>';
  }

  async function postAI(payload,timeoutMs){
    if(typeof window.swsiFetchWithTimeout==='function'){
      return window.swsiFetchWithTimeout(AI_PROXY_URL,payload,timeoutMs);
    }
    return fetch(AI_PROXY_URL,payload);
  }

  window.swsiReadAIError=async function(response){
    var data=null;
    try{data=await response.clone().json();}catch(_e){}
    var err=data&&data.error;
    var code=T(err&&err.code||data&&data.code).trim();
    var serverMessage=T(err&&err.message||data&&data.message).trim().slice(0,300);
    var daily=code==='CLIENT_DAILY_QUOTA'||code==='GLOBAL_DAILY_QUOTA';
    var fallback='AI 回饋暫時無法使用，請稍後再試。';
    if(response.status===413)fallback='這份資料太大，請縮短文字或裁切照片後再試。';
    else if(response.status===429)fallback='目前 AI 使用量較高，請稍後再試。';
    else if(response.status===401||response.status===403)fallback='AI 服務目前設定異常，請稍後再試。';
    else if(response.status===502||response.status===503)fallback='AI 服務暫時忙碌，請稍後再試。';
    return {
      code:code||('HTTP_'+response.status),
      message:serverMessage||fallback,
      retry:!daily&&response.status!==401&&response.status!==403,
      retryAfter:T(response.headers&&response.headers.get&&response.headers.get('retry-after')).trim()
    };
  };
  window.swsiAIErrorContractVersion='2026-08-26.typed-errors.v2';

  window.aiFeedbackHTML=function(id){
    var verified=window.swsiEssayGuideIsVerified(id);
    var guideLine=verified
      ? '✓ 這題的 SWSI 參考架構已逐題核對；AI 仍會以正式題目為最高依據。'
      : '△ 這題的參考架構尚待逐題確認；AI 不會把它當標準答案，會直接以正式題目與你的作答為主。';
    return '<div style="margin-top:14px;border-top:1px dashed var(--line);padding-top:12px">'
      +'<details style="margin-bottom:9px;background:#FBF8EF;border:1px solid var(--line);border-radius:8px;padding:9px 12px"><summary style="cursor:pointer;color:var(--ink-soft);font-size:13px;font-weight:600">🔒 使用 AI 前請先閱讀</summary><div style="font-size:12px;color:var(--ink-soft);line-height:1.75;margin-top:8px">作答文字／照片會送至外部 AI 服務處理。請勿輸入或上傳真實個案姓名、身分證字號、電話、地址、病歷、機構內部文件或其他可識別資料。照片會先在本機縮小再送出。</div></details>'
      +'<div class="aihelp" style="color:var(--ink-soft);margin-bottom:9px;font-size:12px;line-height:1.7">'+E(guideLine)+'</div>'
      +'<button id="aitype_'+E(id)+'" class="fbtn" style="width:100%;padding:11px;font-size:14px;color:var(--pine);font-weight:600" onclick="runAIFeedback(\''+E(id)+'\')">🤖 請 AI 看我的作答</button>'
      +'<input type="file" id="photo_'+E(id)+'" accept="image/*" multiple style="display:none" onchange="gradePhoto(\''+E(id)+'\',this)">'
      +'<button id="aiphoto_'+E(id)+'" class="fbtn" style="width:100%;padding:11px;font-size:14px;color:var(--pine);font-weight:600;margin-top:8px" onclick="document.getElementById(\'photo_'+E(id)+'\').click()">📷 手寫作答 · 拍照請 AI 看</button>'
      +'<div class="aihelp" style="color:var(--ink-soft);margin-top:7px;font-size:12px;line-height:1.7">手寫可一次選 1–3 張。照片模式會先辨識字跡，再提供練習回饋；若辨識有誤，請以原稿為準。打字作答不需要辨識。</div>'
      +'<div id="airesult_'+E(id)+'"></div></div>';
  };
  try{aiFeedbackHTML=window.aiFeedbackHTML;}catch(_e){}

  window.runAIFeedback=async function(id){
    var out=document.getElementById('airesult_'+id);if(!out)return;
    if(!AI_PROXY_URL||AI_PROXY_URL.indexOf('http')!==0){out.innerHTML='<div style="margin-top:10px;font-size:13px;color:var(--ink-soft)">AI 回饋目前未啟用。</div>';return;}
    var ta=document.getElementById('ta_'+id),ans=(ta?ta.value:'').trim();
    var effective=typeof window.effectiveEssayLength==='function'?window.effectiveEssayLength(ans):ans.replace(/\s/g,'').length;
    if(effective<30){out.innerHTML='<div style="margin-top:10px;font-size:13px;color:var(--wrong);line-height:1.7">先寫至少 30 字的實際內容，再請 AI 看。只有標題或「一、（一）、1.」這些格式還不夠。</div>';return;}

    var cached=typeof window.swsiGetAICache==='function'?window.swsiGetAICache(id,ans):null;
    if(cached){renderAIResult(id,out,cached.feedback,'cache');return;}

    var c=essayContext(id);
    var sys=trustPrompt('');
    var user='【正式考題】\n'+T(c.e.q||'')+'\n\n【學生作答】\n'+ans+(c.reference?'\n\n'+c.reference:'');
    if(typeof window.swsiSetAIBusy==='function')window.swsiSetAIBusy(id,true,'text');
    out.innerHTML='<div style="margin-top:12px;font-size:14px;color:var(--ink-soft)">🤖 AI 正在閱讀題目與你的作答…</div>';
    try{
      var r=await postAI({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:GROQ_MODEL,reasoning_effort:'none',temperature:0.35,max_tokens:1200,messages:[{role:'user',content:sys+'\n\n'+user}]})},45000);
      if(!r.ok){
        var info=await window.swsiReadAIError(r);
        out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">'+E(info.message)+'<br>你的作答仍保存在這台裝置。</div>';return;
      }
      var data=await r.json();
      var txt=T(data&&data.choices&&data.choices[0]&&data.choices[0].message&&data.choices[0].message.content).replace(/<think>[\s\S]*?<\/think>/gi,'').trim();
      if(!txt){out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong)">AI 沒有回傳內容，請稍後再試。</div>';return;}
      if(typeof window.swsiSetAICache==='function')window.swsiSetAICache(id,ans,txt);
      renderAIResult(id,out,txt,'text');
    }catch(err){
      var timeout=err&&err.name==='AbortError';
      out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">'+(timeout?'AI 回應時間過久，這次已自動停止。':'連線失敗，可能是網路暫時不穩。')+' 你的作答仍保存在這台裝置。</div>';
    }finally{if(typeof window.swsiSetAIBusy==='function')window.swsiSetAIBusy(id,false,'text');}
  };
  try{runAIFeedback=window.runAIFeedback;}catch(_e){}

  window.gradePhoto=async function(id,inputEl){
    var out=document.getElementById('airesult_'+id);if(!out)return;
    var files=(inputEl&&inputEl.files)?Array.from(inputEl.files):[];
    if(!files.length)return;
    if(files.length>3){out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong)">一次最多 3 張照片，請重新選擇。</div>';if(inputEl)inputEl.value='';return;}
    if(files.some(function(f){return !String(f.type||'').startsWith('image/');})){out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong)">請只選擇照片檔案。</div>';if(inputEl)inputEl.value='';return;}

    if(typeof window.swsiSetAIBusy==='function')window.swsiSetAIBusy(id,true,'photo');
    out.innerHTML='<div style="margin-top:12px;font-size:14px;color:var(--ink-soft)">📷 正在整理照片…</div>';
    try{
      var imgs=[];
      for(var i=0;i<files.length;i++)imgs.push(await shrinkImage(files[i],1200,0.78));
      if(inputEl)inputEl.value='';
      var approxBytes=imgs.reduce(function(n,u){var comma=u.indexOf(',');return n+Math.ceil((u.length-(comma+1))*3/4);},0);
      if(approxBytes>3200000){out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">照片仍太大。請裁掉桌面或背景，只保留作答紙後再上傳。</div>';return;}

      var c=essayContext(id);
      var sys=trustPrompt('\n照片處理規則：\n- 先逐頁辨識作答文字，標題寫【我讀到的作答】；看不清楚的字用「◌」，不要自行補字。\n- 如果照片模糊、不是申論作答或幾乎無法辨識，只請學生重拍，不要猜內容。\n- 辨識完成後再寫【練習回饋】。\n');
      var user='【正式考題】\n'+T(c.e.q||'')+(c.reference?'\n\n'+c.reference:'')+'\n\n下面照片是學生同一份手寫作答，請依頁面順序閱讀。';
      var content=[{type:'text',text:sys+'\n\n'+user}];
      imgs.forEach(function(u){content.push({type:'image_url',image_url:{url:u}});});
      out.innerHTML='<div style="margin-top:12px;font-size:14px;color:var(--ink-soft)">🤖 AI 正在讀 '+imgs.length+' 張作答照片…</div>';

      var r=await postAI({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:GROQ_MODEL,reasoning_effort:'none',temperature:0.25,max_tokens:1300,messages:[{role:'user',content:content}]})},60000);
      if(!r.ok){
        var info=await window.swsiReadAIError(r);
        out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">'+E(info.message)+'</div>';return;
      }
      var data=await r.json();
      var txt=T(data&&data.choices&&data.choices[0]&&data.choices[0].message&&data.choices[0].message.content).replace(/<think>[\s\S]*?<\/think>/gi,'').trim();
      if(!txt){out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong)">AI 沒有回傳內容，請稍後再試。</div>';return;}
      renderAIResult(id,out,txt,'photo');
    }catch(err){
      var timeout=err&&err.name==='AbortError';
      out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">'+(timeout?'AI 讀取照片時間過久，這次已自動停止。':'照片處理或連線失敗，請重新拍攝後再試。')+'</div>';
    }finally{if(typeof window.swsiSetAIBusy==='function')window.swsiSetAIBusy(id,false,'photo');if(inputEl)inputEl.value='';}
  };
  try{gradePhoto=window.gradePhoto;}catch(_e){}

  function polishEssayTrustUI(){
    document.querySelectorAll('.gbtn').forEach(function(btn){
      var t=T(btn.textContent).trim();
      if(t.indexOf('對照核心骨架')>=0||t.indexOf('對照核心架構')>=0)btn.textContent='寫完了？看看參考架構 ›';
    });
    document.querySelectorAll('.pending b').forEach(function(el){if(T(el.textContent).indexOf('參考骨架')>=0)el.textContent='參考架構整理中';});
    document.querySelectorAll('textarea.wta').forEach(function(ta){
      if(T(ta.placeholder).indexOf('骨架')>=0)ta.placeholder='先自己試著寫。卡住時可以看上面的 5 步；寫完再看參考架構。';
    });
  }

  if(typeof render==='function'){
    var prevRenderTrust=render;
    render=function(){var v=prevRenderTrust.apply(this,arguments);polishEssayTrustUI();return v;};
    try{window.render=render;}catch(_e){}
  }
  polishEssayTrustUI();
})();
/* ===== SWSI Essay Trust Layer END ===== */

/* ===== SWSI essay navigation hardening 2026-08-26 ===== */
(function(){
  'use strict';

  function markEssayTab(){
    try{
      ['home','topics','essay','review','progress'].forEach(function(t){
        var el=document.getElementById('t-'+t);
        if(el) el.classList.toggle('on',t==='essay');
      });
    }catch(_e){}
  }

  function renderEssaySafely(){
    try{
      if(typeof renderEssay!=='function') throw new Error('renderEssay is unavailable');
      renderEssay();
      return true;
    }catch(err){
      console.error('[SWSI] essay render failed; resetting essay state',err);
      try{
        if(typeof openEssay!=='undefined') openEssay=null;
        if(typeof essayCluster!=='undefined') essayCluster=null;
        if(typeof essaySubj!=='undefined') essaySubj='全部科目';
        if(typeof guideOpen!=='undefined') guideOpen=null;
        if(typeof dissectOpen!=='undefined') dissectOpen=null;
        renderEssay();
        return true;
      }catch(err2){
        console.error('[SWSI] essay render retry failed',err2);
        try{
          if(typeof app!=='undefined'&&app){
            app.innerHTML='<div class="empty"><div class="ico">✒</div><h3>申論頁暫時無法開啟</h3><p>頁面載入發生錯誤，你的作答草稿仍保存在這台裝置。</p><button class="btn" style="max-width:220px;margin:18px auto 0" onclick="location.reload()">重新整理</button></div>';
          }
        }catch(_e){}
        return false;
      }
    }
  }

  var essayOpening=false;
  function resetEssayState(){
    try{ if(typeof essaySubj!=='undefined') essaySubj='全部科目'; }catch(_e){}
    try{ if(typeof essayCluster!=='undefined') essayCluster=null; }catch(_e){}
    try{ if(typeof openEssay!=='undefined') openEssay=null; }catch(_e){}
    try{ if(typeof guideOpen!=='undefined') guideOpen=null; }catch(_e){}
    try{ if(typeof dissectOpen!=='undefined') dissectOpen=null; }catch(_e){}
  }

  window.swsiOpenEssay=async function(){
    if(essayOpening) return;
    essayOpening=true;
    /* The Learning Center owns #app while this flag is true and will restore its
       hub after any DOM replacement. Release that ownership before the essay
       renderer changes #app, including navigation from the fixed bottom tab. */
    window.__SWSI_LEARNING_CENTER_OPEN__=false;
    try{
      /* Keep the original slow/cache recovery without leaving a separate late owner. */
      try{
        if(typeof ESSAYS!=='undefined' && (!Array.isArray(ESSAYS) || ESSAYS.length===0) && typeof loadAutoEssays==='function'){
          await loadAutoEssays();
        }
      }catch(loadErr){
        console.warn('SWSI essay reload failed',loadErr);
      }
      resetEssayState();
      try{ if(typeof view!=='undefined') view='essay'; }catch(_e){ window.view='essay'; }
      markEssayTab();
      try{ window.scrollTo(0,0); }catch(_e){}
      renderEssaySafely();
    }finally{
      essayOpening=false;
    }
  };

  /*
    iOS Safari / in-app webviews occasionally fail to execute a dynamically
    generated inline onclick reliably after several DOM replacement passes.
    Capture the two primary essay entry points before their inline handlers.
  */
  document.addEventListener('click',function(ev){
    var target=ev.target;
    if(!target||!target.closest) return;
    var tab=target.closest('#t-essay');
    var card=target.closest('.swsi-study-card');
    var isHomeEssay=!!(card&&/練一題申論/.test(card.textContent||''));
    if(!tab&&!isHomeEssay) return;
    ev.preventDefault();
    ev.stopPropagation();
    window.swsiOpenEssay();
  },true);

  /* Give the fixed bottom tab an explicit non-inline fallback as well. */
  function wireTab(){
    var tab=document.getElementById('t-essay');
    if(!tab||tab.dataset.swsiEssayWired==='1') return;
    tab.dataset.swsiEssayWired='1';
    tab.setAttribute('aria-label','開啟申論練習');
  }
  wireTab();
  try{
    var mo=new MutationObserver(wireTab);
    mo.observe(document.body,{childList:true,subtree:true});
  }catch(_e){}
})();
/* SWSI Product V1 Lock 2026-08-26
   Product principle: open -> study -> review -> leave.
   - one-tap essay practice + separate choose-your-own entry
   - concise explanations with optional full notes
   - unified monochrome core navigation
   - quiet, transparent question-bank version information
*/
(function(){
  'use strict';

  var STYLE_ID='swsi-product-v1-lock-style';
  if(!document.getElementById(STYLE_ID)){
    var style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      .swsi-study-card .sub,.swsi-principle-note,.swsi-data-version,
      .swsi-essay-action-card .sub,footer{color:#636B67!important;}

      .swsi-essay-action-card{background:var(--paper2);border:1px solid var(--line);border-radius:16px;padding:15px 16px;margin:0 0 9px;}
      .swsi-essay-action-card .title{font-family:'Noto Serif TC',serif;font-weight:900;font-size:var(--swsi-ui-title,15px);line-height:1.4;color:var(--ink);}
      .swsi-essay-action-card .sub{font-family:'Noto Sans TC',sans-serif;font-size:var(--swsi-ui-small,11.5px);line-height:1.6;margin-top:3px;}
      .swsi-essay-action-card .actions{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:8px;margin-top:11px;}
      .swsi-essay-action-card button{min-height:44px;border-radius:11px;font-family:'Noto Sans TC',sans-serif;font-size:var(--swsi-ui-control,14px);font-weight:800;cursor:pointer;}
      .swsi-essay-action-card .go{border:none;background:var(--pine-deep);color:#fff;}
      .swsi-essay-action-card .choose{border:1px solid var(--line);background:#fff;color:var(--pine-deep);}

      .swsi-answer-line{font-family:'Noto Sans TC',sans-serif;font-size:var(--fs-s);line-height:1.55;color:var(--pine-deep);font-weight:800;background:#F1F6F4;border:1px solid #D8E5DF;border-radius:10px;padding:8px 10px;margin:0 0 13px;}
      .swsi-explanation-more{margin:12px 0 3px;border:1px solid var(--line);border-radius:11px;background:#FBFCFB;overflow:hidden;}
      .swsi-explanation-more summary{list-style:none;cursor:pointer;min-height:43px;padding:9px 11px;display:flex;align-items:center;font-family:'Noto Sans TC',sans-serif;font-size:var(--fs-s);font-weight:800;color:var(--pine-deep);}
      .swsi-explanation-more summary::-webkit-details-marker{display:none;}
      .swsi-explanation-more summary:after{content:'＋';margin-left:auto;color:var(--ink-3);font-size:16px;}
      .swsi-explanation-more[open] summary:after{content:'－';}
      .swsi-explanation-more .body{border-top:1px solid var(--line);padding:13px 11px 2px;}
      .swsi-explanation-more .body .exp-sec:last-child,.swsi-explanation-more .body .extra:last-child{margin-bottom:10px;}

      .tabbar .ico.swsi-nav-ico{width:21px;height:21px;display:grid;place-items:center;font-size:0;line-height:1;}
      .tabbar .ico.swsi-nav-ico svg{width:20px;height:20px;display:block;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;}
      .tabbar .swsi-nav-label{font-family:'Noto Sans TC',sans-serif;line-height:1.1;}

      .swsi-data-version{margin:10px 4px 0;border-top:1px solid rgba(220,228,223,.85);padding-top:7px;font-family:'Noto Sans TC',sans-serif;font-size:var(--swsi-ui-small,11.5px);line-height:1.6;}
      .swsi-data-version summary{cursor:pointer;list-style:none;min-height:36px;display:flex;align-items:center;justify-content:center;text-align:center;color:#636B67;font-weight:700;}
      .swsi-data-version summary::-webkit-details-marker{display:none;}
      .swsi-data-version summary:after{content:'＋';margin-left:6px;color:var(--ink-3);}
      .swsi-data-version[open] summary:after{content:'－';}
      .swsi-data-version .body{text-align:center;padding:2px 8px 5px;color:#69716D;}

      footer.swsi-footer-clean{padding-top:10px!important;line-height:1.65!important;}
      footer.swsi-footer-clean .sub{font-family:'Noto Sans TC',sans-serif;font-size:11px;color:#737A76;margin-top:2px;}
      @media(max-width:370px){.swsi-essay-action-card .actions{grid-template-columns:1fr;}}
    `;
    document.head.appendChild(style);
  }

  function icon(kind){
    if(kind==='home') return '<span class="ico swsi-nav-ico" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 10.5 12 4l8 6.5V20H7v-7h10v7"></path><path d="M9 20v-7h6"></path></svg></span>';
    if(kind==='review') return '<span class="ico swsi-nav-ico" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M20 7v5h-5"></path><path d="M19 12a7.5 7.5 0 1 1-2.2-5.3L20 9"></path></svg></span>';
    return '<span class="ico swsi-nav-ico" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m5 19 3.8-.8L19 8a2.1 2.1 0 0 0-3-3L5.8 15.2 5 19Z"></path><path d="m14.8 6.2 3 3"></path><path d="M4 21h16"></path></svg></span>';
  }

  function setNavButton(id,kind,label,route){
    var el=document.getElementById(id); if(!el) return;
    /* Learning Center V2 may already have installed a simple icon + label.
       Accept either markup shape so product polish and learning-center observers
       do not continuously rewrite each other. */
    var currentLabel=el.querySelector('.swsi-nav-label');
    var currentText=(el.textContent||'').trim();
    var hasLabel=currentLabel ? currentLabel.textContent===label : currentText.slice(-label.length)===label;
    if(!hasLabel){
      el.innerHTML=icon(kind)+'<span class="swsi-nav-label">'+label+'</span>';
    }
    if(el.getAttribute('aria-label')!==label) el.setAttribute('aria-label',label);
    if(route&&el.getAttribute('onclick')!==route) el.setAttribute('onclick',route);
  }

  window.swsiOpenLearningCenter=function(){
    if(typeof go==='function') go('progress');
    /* Learning Center V2 decorates the progress surface on focus. Trigger that
       owner synchronously instead of relying on MutationObserver timing. */
    try{window.dispatchEvent(new Event('focus'));}catch(_e){}
    var home=document.getElementById('t-home');
    var learning=document.getElementById('t-review');
    var essay=document.getElementById('t-essay');
    if(home)home.classList.remove('on');
    if(learning)learning.classList.add('on');
    if(essay)essay.classList.remove('on');
  };

  function polishNav(){
    setNavButton('t-home','home','練題',"go('home')");
    setNavButton('t-review','review','學習',"swsiOpenLearningCenter()");
    setNavButton('t-essay','essay','申論',"go('essay')");
  }

  /* Essay navigation is owned by zzz_fix_essay_navigation.part. */
  window.swsiChooseEssay=function(){ window.swsiOpenEssay(); };

  function latestVersionText(){
    var total='';
    try{ total=typeof questionTotal==='function'?questionTotal():''; }catch(_e){}
    var year='';
    try{ var ys=typeof examYears==='function'?examYears():[]; year=ys&&ys.length?String(ys[0]):''; }catch(_e){}
    var round='';
    try{
      var m=window.SWSI_QB&&window.SWSI_QB.manifest;
      if(m&&Array.isArray(m.shards)&&year){
        var rs=m.shards.filter(function(s){return String(s.year)===year;}).map(function(s){return String(s.round||'');});
        if(rs.some(function(r){return r==='2'||/二|第二/.test(r);})) round='第二次';
        else if(rs.length) round='第一次';
      }
    }catch(_e){}
    return {total:total,latest:year?(year+' 年'+round):''};
  }

  function enhanceHome(){
    if(typeof view!=='undefined'&&view!=='home') return;
    var card=null;
    document.querySelectorAll('#app .swsi-study-card').forEach(function(c){
      var t=c.querySelector('.title');
      if(!card&&t&&/申論/.test(t.textContent||'')) card=c;
    });
    if(card){
      var box=document.createElement('section');
      box.className='swsi-essay-action-card';
      box.innerHTML='<div class="title">練一題申論</div><div class="sub">直接抽一題近期歷屆題開始寫；想指定科目或題目時再自己選。</div>'+
        '<div class="actions"><button type="button" class="go" onclick="swsiStartEssayNow()">直接練一題</button><button type="button" class="choose" onclick="swsiChooseEssay()">自己選題</button></div>';
      card.replaceWith(box);
    }

    if(!document.querySelector('#app .swsi-data-version')){
      var anchor=document.querySelector('#app .swsi-principle-note');
      if(anchor){
        var v=latestVersionText();
        var d=document.createElement('details');
        d.className='swsi-data-version';
        d.innerHTML='<summary>題庫資料版本'+(v.total?' · '+v.total+' 題':'')+(v.latest?' · 最新 '+v.latest:'')+'</summary>'+
          '<div class="body">題目以考選部官方資料為準；官方多重答案、一律給分與任一作答給分規則已納入判題。</div>';
        anchor.insertAdjacentElement('afterend',d);
      }
    }
  }

  function cleanFooter(){
    var f=document.querySelector('footer'); if(!f) return;
    if(f.classList.contains('swsi-footer-clean')) return;
    f.classList.add('swsi-footer-clean');
    f.innerHTML='<div>© 2026 熊品澄 · 免費公開學習工具</div><div class="sub">社工師國考題目以考選部官方資料為準</div>';
  }

  function collapseExplanation(){
    var exp=document.querySelector('#app .qcard .exp');
    if(!exp||exp.dataset.swsiCompact==='1') return;
    exp.dataset.swsiCompact='1';

    var item=null;
    try{ item=queue&&queue[idx]; }catch(_e){}
    var topic=exp.querySelector('.topic');
    if(item&&!exp.querySelector('.swsi-answer-line')){
      var line=document.createElement('div');
      line.className='swsi-answer-line';
      line.textContent=typeof answerLabel==='function'?answerLabel(item):('答案：'+(item.answer||'—'));
      if(topic) topic.insertAdjacentElement('afterend',line); else exp.insertBefore(line,exp.firstChild);
    }

    var hidden=[];
    exp.querySelectorAll(':scope > .exp-sec').forEach(function(sec){
      var h=sec.querySelector('h4');
      var label=(h&&h.textContent||'').trim();
      if(/其他選項|考場陷阱/.test(label)) hidden.push(sec);
    });
    exp.querySelectorAll(':scope > .extra').forEach(function(x){hidden.push(x);});
    if(!hidden.length) return;

    var details=document.createElement('details');
    details.className='swsi-explanation-more';
    details.innerHTML='<summary>看完整解析</summary><div class="body"></div>';
    var body=details.querySelector('.body');
    hidden.forEach(function(x){body.appendChild(x);});
    var next=exp.querySelector(':scope > .btn');
    if(next) exp.insertBefore(details,next); else exp.appendChild(details);
  }

  function enhance(){
    polishNav();
    cleanFooter();
    enhanceHome();
    collapseExplanation();
  }

  enhance();
  try{
    var scheduled=false;
    var observer=new MutationObserver(function(){
      if(scheduled) return;
      scheduled=true;
      Promise.resolve().then(function(){
        scheduled=false;
        enhance();
      });
    });
    observer.observe(document.body,{childList:true,subtree:true});
  }catch(_e){}
})();

/* SWSI quick-essay scope hardening 2026-08-26
   The legacy ESSAYS collection may live in the page's lexical scope rather than window.
*/
(function(){
  'use strict';

  function essayRowsNow(){
    try{ if(typeof ESSAYS!=='undefined' && Array.isArray(ESSAYS)) return ESSAYS; }catch(_e){}
    return Array.isArray(window.ESSAYS)?window.ESSAYS:[];
  }

  function usablePool(){
    var xs=essayRowsNow();
    var official=xs.filter(function(e){return e&&e.id&&e.q&&!/(時事|預測)/.test(String(e.qtype||''));});
    return official.length?official:xs.filter(function(e){return e&&e.id&&e.q;});
  }

  window.swsiStartEssayNow=async function(){
    try{
      if(!essayRowsNow().length && typeof loadAutoEssays==='function') await loadAutoEssays();
    }catch(err){ console.warn('[SWSI] essay preload failed',err); }

    var pool=usablePool();
    if(!pool.length){ if(typeof window.swsiOpenEssay==='function') window.swsiOpenEssay(); return; }

    var years=pool.map(function(e){return parseInt(e.year,10);}).filter(Number.isFinite);
    var latest=years.length?Math.max.apply(null,years):0;
    var recent=latest?pool.filter(function(e){var y=parseInt(e.year,10);return Number.isFinite(y)&&y>=latest-4;}):pool.slice();
    if(recent.length) pool=recent;

    var last=''; try{last=localStorage.getItem('swsi_last_quick_essay')||'';}catch(_e){}
    var choices=pool.filter(function(e){return String(e.id)!==last;});
    if(!choices.length) choices=pool;
    var e=choices[Math.floor(Math.random()*choices.length)];
    try{localStorage.setItem('swsi_last_quick_essay',String(e.id));}catch(_e){}

    try{ essaySubj=e.subject||'全部科目'; essayCluster=null; openEssay=e.id; guideOpen=null; dissectOpen=null; }catch(_e){}
    try{ view='essay'; }catch(_e){ window.view='essay'; }
    try{ window.scrollTo(0,0); }catch(_e){}
    try{ if(typeof renderEssay==='function') renderEssay(); else if(typeof render==='function') render(); }
    catch(err){ console.error('[SWSI] quick essay failed',err); if(typeof window.swsiOpenEssay==='function') window.swsiOpenEssay(); }
  };
})();

/* SWSI Essay Exam Dissection Method 2026-08-26
   Beginner-first version: simple enough to use when a student is stuck.
   This is a study aid synthesized from common social-worker exam preparation principles,
   not an official MOEX answer formula.
*/
(function(){
  'use strict';

  dissectHTML=function(id){
    const open = dissectOpen===id;
    const steps = [
      ['① 看題目要你答什麼','先不要急著寫，把題目完整看完，確認它到底要你回答哪些事情。'],
      ['② 分成幾個問題','題目問三件事，就準備答三段；不要把全部答案擠在同一大段裡。'],
      ['③ 想幾個關鍵字','把你記得的理論、人物、法規或重要概念先寫在旁邊，不用一開始就排得很漂亮。'],
      ['④ 一點一點寫','用「一、（一）、1.」分開來寫。每一點先講重點，再補一兩句說明。'],
      ['⑤ 寫完再看一次','最後回頭看題目，確認有沒有漏掉其中一問；有時間再補一小段結尾。']
    ];
    const note='這是給卡住時用的簡單提醒，不是考選部官方作答公式。';
    return `<button class="dbtn" onclick="toggleDissect('${id}')">${open?'▾':'▸'} 不知道怎麼下筆？先照這 5 步</button>`
      + (open?`<div class="dsteps">${steps.map(s=>`<div class="dstep"><b>${s[0]}</b><span>${s[1]}</span></div>`).join('')}<div style="margin-top:10px;padding-top:9px;border-top:1px solid var(--line);font-family:'Noto Sans TC',sans-serif;font-size:var(--fs-s);line-height:1.6;color:var(--ink-soft)">${note}</div></div>`:'');
  };
})();

/* SWSI Learning Center Direct Route 2026-08-29
   Final navigation owner for the preview simplification.
   Opening Learning must never route through progress/full-bank loading.
*/
(function(){
  'use strict';

  /* Preserve the existing CDN-aware go() contract, but once the user leaves the
     Learning surface, stop its self-healing observer from restoring the hub. */
  var routedGo=window.go;
  if(typeof routedGo==='function'&&!routedGo.__swsiLearningAware){
    var wrapped=function(v){
      if(v!=='learning')window.__SWSI_LEARNING_CENTER_OPEN__=false;
      return routedGo(v);
    };
    wrapped.__swsiLearningAware=true;
    window.go=wrapped;
    try{go=wrapped;}catch(_e){}
  }

  window.swsiOpenLearningCenter=function(ev){
    if(ev&&typeof ev.preventDefault==='function')ev.preventDefault();
    if(typeof window.swsiRenderLearningCenter==='function')return window.swsiRenderLearningCenter();
    return false;
  };

  function bind(){
    var route='return swsiOpenLearningCenter(event)';
    var learning=document.getElementById('t-review');
    if(learning){
      if(learning.getAttribute('onclick')!==route)learning.setAttribute('onclick',route);
      if(learning.getAttribute('aria-label')!=='學習中心')learning.setAttribute('aria-label','學習中心');
    }

    /* Home also exposes a Learning Center card. Keep it on the same direct local
       route as the bottom Learning tab instead of falling back to legacy progress. */
    document.querySelectorAll('#app .swsi-study-card').forEach(function(card){
      var title=card.querySelector('.title');
      if(title&&(title.textContent||'').trim()==='學習中心'&&card.getAttribute('onclick')!==route){
        card.setAttribute('onclick',route);
      }
    });
  }

  /* Home is re-rendered often, so bind its Learning card immediately after the
     canonical home renderer runs instead of watching every app DOM mutation. */
  var previousRenderHome=window.renderHome;
  try{if(typeof previousRenderHome!=='function'&&typeof renderHome==='function')previousRenderHome=renderHome;}catch(_e){}
  if(typeof previousRenderHome==='function'&&!previousRenderHome.__swsiLearningDirectRoute){
    var wrappedHome=function(){
      var out=previousRenderHome.apply(this,arguments);
      bind();
      return out;
    };
    wrappedHome.__swsiLearningDirectRoute=true;
    window.renderHome=wrappedHome;
    try{renderHome=wrappedHome;}catch(_e){}
  }

  /* Clear the local Learning-surface flag before the legacy inline handlers for
     the other two bottom tabs run. This works even if go() is a lexical global
     rather than a window property in an older browser build. */
  document.addEventListener('click',function(ev){
    var el=ev.target&&ev.target.closest?ev.target.closest('#t-home,#t-essay'):null;
    if(el)window.__SWSI_LEARNING_CENTER_OPEN__=false;
  },true);

  var queued=false;
  function queueBind(){
    if(queued)return;
    queued=true;
    queueMicrotask(function(){queued=false;bind();});
  }

  bind();
  try{
    var bar=document.querySelector('.tabbar');
    if(bar)new MutationObserver(queueBind).observe(bar,{childList:true,subtree:true,attributes:true,attributeFilter:['onclick','aria-label']});
  }catch(_e){}
})();
/* ===== SWSI Essay Metadata Labels 2026-08-26 =====
   UI-only trust polish. Never mutates official past-exam question text or exam facts.
*/
(function(){
  'use strict';

  window.SWSI_ESSAY_METADATA_LABELS_VERSION='essay-meta-v1-20260826';

  function txt(v){return String(v==null?'':v).trim();}
  function frequencyLabel(v){
    var s=txt(v);
    var map={
      '高頻':'主題頻率：高',
      '中頻':'主題頻率：中',
      '低頻':'主題頻率：低',
      '高頻預測':'平台預測：較值得留意',
      '中頻預測':'平台預測：可留意',
      '低頻預測':'平台預測：一般留意'
    };
    return map[s]||s;
  }
  function difficultyLabel(v){
    var s=txt(v);
    var map={
      '基礎':'平台難度：基礎',
      '中等':'平台難度：中等',
      '困難':'平台難度：較難',
      '偏難':'平台難度：較難'
    };
    return map[s]||s;
  }
  window.swsiEssayFrequencyLabel=frequencyLabel;
  window.swsiEssayDifficultyLabel=difficultyLabel;

  function replaceMetadataTail(s){
    var out=String(s==null?'':s);
    out=out.replace(/ · 高頻預測\s*$/,' · 平台預測：較值得留意');
    out=out.replace(/ · 中頻預測\s*$/,' · 平台預測：可留意');
    out=out.replace(/ · 低頻預測\s*$/,' · 平台預測：一般留意');
    out=out.replace(/ · 高頻\s*$/,' · 主題頻率：高');
    out=out.replace(/ · 中頻\s*$/,' · 主題頻率：中');
    out=out.replace(/ · 低頻\s*$/,' · 主題頻率：低');
    return out;
  }

  function polishEssayMetadataUI(){
    var root=document.getElementById('app');
    if(!root)return;

    /* Detail-page chips: make clear these are SWSI metadata, not examiner labels. */
    root.querySelectorAll('.emeta .tag').forEach(function(tag){
      var s=txt(tag.textContent);
      var next=frequencyLabel(s);
      if(next===s)next=difficultyLabel(s);
      if(next!==s)tag.textContent=next;
    });

    /* Theory/law associations are platform inferences unless explicitly stated in the official question. */
    root.querySelectorAll('.ehint').forEach(function(el){
      var s=txt(el.textContent);
      if(s.indexOf('理論：')===0)el.textContent='平台整理・可能相關理論：'+s.slice(3);
      else if(s.indexOf('法規：')===0)el.textContent='平台整理・可能相關法規：'+s.slice(3);
    });

    /* Topic cards use one representative frequency value; label it as a theme statistic. */
    root.querySelectorAll('.cnt').forEach(function(el){
      var s=txt(el.textContent),next=replaceMetadataTail(s);
      if(next!==s)el.textContent=next;
    });

    /* Essay-list metadata lines are plain divs, so only touch leaf nodes that look exactly like list metadata.
       Never operate inside official question bodies or guide/answer content. */
    root.querySelectorAll('div').forEach(function(el){
      if(el.children.length)return;
      if(el.closest('.ebody,.qtext,.guide,.dsteps,.wbox,.aihelp,#airesult'))return;
      var s=txt(el.textContent);
      if(!/^\S.*\d{3}年\s/.test(s)&&!/^\d{3}年\s/.test(s))return;
      var next=replaceMetadataTail(s);
      if(next!==s)el.textContent=next;
    });
  }
  window.swsiPolishEssayMetadataUI=polishEssayMetadataUI;

  polishEssayMetadataUI();
  try{
    var scheduled=false;
    var observer=new MutationObserver(function(){
      if(scheduled)return;
      scheduled=true;
      Promise.resolve().then(function(){
        scheduled=false;
        polishEssayMetadataUI();
      });
    });
    observer.observe(document.getElementById('app')||document.body,{childList:true,subtree:true});
  }catch(_e){}
})();
/* ===== SWSI Essay Metadata Labels END ===== */
/* ===== SWSI Essay Review Batch 01 2026-08-26 =====
   IMPORTANT: official historical exam questions are read-only.
   This file only replaces SWSI-authored guidance for five manually reviewed high-risk essays.
*/
(function(){
  'use strict';
  var G=window.ESSAY_GUIDES=window.ESSAY_GUIDES||{};
  var meta={review_status:'verified',reviewed_at:'2026-08-26',review_batch:'batch01'};

  G['社會政策與社會立法-108-1-申論2']=Object.assign({},meta,{
    kao:'這題分成兩大部分：先按「申請入住、入住之中、離院之後」三個階段說明住宿型機構社工的角色，再說明面對各階段倫理議題時可採取的倫理原則。不是只寫一般倫理決策模型。',
    dati:'先照題目三個服務階段逐段作答，每一階段都寫「社工角色＋具體工作」；最後另開一段整理跨階段倫理原則。角色名稱要和工作內容配對，不要只列名詞。倫理部分可從自決與知情、隱私保密、安全與不傷害、公平正義、專業界限及服務連續性來分析。',
    biaoti:[
      '申請入住：接案／評估者、資訊提供者、資源仲介與協調者——評估需求與機構適切性，協助理解服務內容、權利義務及可用資源',
      '入住之中：個案管理／協調者、支持與輔導者、倡導者、家庭與跨專業溝通者——持續評估適應、需求、權益與照顧品質',
      '離院之後：出院／離院準備者、資源連結者、追蹤與轉銜協調者——安排返家或轉介、銜接社區資源並降低服務中斷',
      '倫理原則：尊重自我決定與知情參與、隱私與保密、避免傷害與維護安全、公平與資源正義、專業界限／利益衝突、服務連續性與可近性'
    ],
    kw:['三階段服務','角色與任務配對','入住評估','個案管理','離院準備／轉銜','自我決定','知情參與','隱私保密','不傷害','公平正義'],
    review_basis:'逐題依正式題幹重寫；移除原本只套用一般倫理兩難模板的錯配。'
  });

  G['社會政策與社會立法-108-2-申論1']=Object.assign({},meta,{
    kao:'這題先考「平等」作為社會政策價值的基本概念，再考 Le Grand（1982）所區分的五種 equality of what，並要求用長期照顧服務去對應說明。重點不是福利由誰提供或服務輸送。',
    dati:'先說明平等不必然等於每個人拿到完全相同的東西，而要先問「要讓什麼變得平等」。接著依 Le Grand 五種平等逐一寫定義，再各配一個長照例子。答題時把「投入／所得／使用／負擔成本／結果」五個層次分清楚。',
    biaoti:[
      '平等的基本概念：社會政策追求減少不利與不平等，但不同政策可能追求不同層次的平等，因此要先界定 equality of what',
      '公共支出的平等（equality of public expenditure）：公共服務支出以相等方式配置；長照可用每位符合條件者獲得相同基準公共投入作例',
      '最終所得的平等（equality of final income）：藉公共支出或補助縮小原有所得差距；長照可用對經濟弱勢提高補助、降低自付負擔作例',
      '使用的平等（equality of use）：相同需要者能實際獲得相當程度的服務使用；長照要處理城鄉、交通、資訊等造成的使用落差',
      '成本的平等（equality of cost）：使用者取得每單位服務所承擔的金錢、時間等成本趨於相當；長照可比較偏鄉交通時間、自付額等障礙',
      '成果的平等（equality of outcome）：政策著眼於服務後的結果差距；長照可用維持功能、照顧負荷或生活品質改善是否因地區／所得而差距過大作例'
    ],
    kw:['Le Grand','equality of what','公共支出平等','最終所得平等','使用平等','成本平等','成果平等','長期照顧','垂直重分配'],
    review_basis:'依 Julian Le Grand, The Strategy of Equality (1982) 的五類平等逐題核對；移除原福利混合經濟模板。'
  });

  G['人類行為與社會環境-110-2-申論1']=Object.assign({},meta,{
    kao:'這題第一問是記憶並解釋 2018 年第一期「強化社會安全網計畫」的三項正式目標；第二問才是以未來社工的角度評析其優點、限制並針對限制提出建議。不能用一般福利服務輸送模板取代三大目標。',
    dati:'先把三大目標完整寫對，再分成「優點—限制—建議」三段。評析可以從預防、以家庭與社區為基礎、單一窗口與流程效率、跨體系整合等優點切入；限制則避免空泛，可談跨網絡資訊與權責協調、人力負荷、區域資源落差、服務銜接等，建議要一一對應限制。',
    biaoti:[
      '三大目標一：家庭社區為基石，前端預防更落實',
      '三大目標二：簡化受理窗口，提升流程效率',
      '三大目標三：整合服務體系，綿密安全網絡',
      '可能的優點：由個人問題轉向家庭／社區脈絡、提高早期辨識與預防、降低多頭通報與行政斷裂、促進跨體系合作',
      '可能的限制：第一線人力與負荷、不同網絡權責與資訊整合困難、城鄉資源不均、轉介後服務連續性仍可能中斷',
      '建議：補足與穩定專業人力、建立明確跨網絡分工與回饋機制、強化偏鄉與社區資源、用個案追蹤與成效資料檢查是否真的「不漏接」'
    ],
    kw:['強化社會安全網','2018','家庭社區為基石','前端預防','簡化受理窗口','提升流程效率','整合服務體系','綿密安全網絡','跨網絡整合'],
    review_basis:'三大目標依行政院107年核定第一期強化社會安全網計畫核對；評析段落為 SWSI 學習參考。'
  });

  G['社會工作研究方法-106-2-申論2']=Object.assign({},meta,{
    kao:'這題只問兩件事：什麼是「非反應式研究（non-reactive research）」；哪些研究方法屬於非反應式研究。舊版把它套成一般質性資料蒐集題，方向過大。',
    dati:'先抓住核心：研究對象不因「知道自己正被研究」而改變行為，研究者盡量不介入原本社會行為，因此也常稱非干擾／不介入式方法。第二段直接分類並舉例，不需要展開整套質性研究信實度。',
    biaoti:[
      '定義：研究者以不直接干擾研究對象的方式取得資料，使被研究者通常不因研究情境而產生反應性改變',
      '內容分析：分析既存文字、影像、媒體、文件或紀錄，例如新聞報導、政策文件、社群公開內容',
      '既有統計／次級資料分析：重新分析政府統計、行政資料、既有調查資料等已存在資料',
      '物理痕跡／非干擾測量：從人們自然留下的使用痕跡或實體證據推論行為',
      '比較歷史／檔案研究亦常利用既存史料與紀錄進行，不必直接向當事人施測',
      '補充優缺點：可降低反應性與部分蒐集成本，但資料可能不是為目前研究問題而產生，需注意資料品質、效度、遺漏與倫理'
    ],
    kw:['非反應式研究','non-reactive research','unobtrusive measures','反應性','內容分析','既有統計','次級資料','物理痕跡','檔案資料'],
    review_basis:'依社會研究方法中 nonreactive/unobtrusive research 的標準定義與常見方法逐題重寫。'
  });

  G['社會工作研究方法-105-2-申論1']=Object.assign({},meta,{
    kao:'題目已指定科學方法的五項特性：暫時性、反覆論證性、觀察、無偏見、透明化。作答就是逐項「說明意義＋為什麼重要」，不是比較量化與質性研究典範。',
    dati:'最穩的寫法是五個小標，每一項先用一句話定義，再補一句它如何讓科學知識更可信。不要自行換成其他科學方法特徵，也不要漏掉題目指定的任何一項。',
    biaoti:[
      '暫時性（tentative）：科學結論不是永遠不可推翻的真理；有新證據或更好的解釋時應修正，因此能持續累積與自我修正',
      '反覆論證性（replication）：研究程序與結果應能被其他研究者重複檢驗；可確認結果不是偶然、個別研究者偏差或一次性情境造成',
      '觀察（observation）：主張要建立在可觀察、可蒐集的經驗資料上；讓推論有證據基礎而非只靠權威、直覺或信念',
      '無偏見（unbiased）：研究設計、蒐集、分析與解釋應盡量降低研究者立場與偏見的影響；提高結果的客觀性與可信度',
      '透明化（transparent）：研究問題、方法、樣本、測量、分析與限制應清楚揭露；使他人可以檢查、批判、重製與累積知識'
    ],
    kw:['科學方法','暫時性','tentative','反覆論證','replication','觀察','observation','無偏見','unbiased','透明化','transparent'],
    review_basis:'完全依正式題幹指定的五項特性逐項重寫；移除原量化／質性典範模板。'
  });

  window.SWSI_ESSAY_REVIEW_BATCH01='2026-08-26';
})();

/* SWSI Essay Guide Audit Batch 1 2026-08-26
   Per-question review of five known high-risk / mismatched historical essay guides.
   IMPORTANT: This patch only replaces SWSI-authored guidance. It never edits official exam question text.
*/
(function(){
  'use strict';

  var G=window.ESSAY_GUIDES=window.ESSAY_GUIDES||{};
  var REVIEWED_AT='2026-08-26';
  var AUDIT_VERSION='essay-guide-audit-b1-20260826';

  function verified(id,data){
    G[id]=Object.assign({},G[id]||{},data,{
      review_status:'verified',
      reviewed_at:REVIEWED_AT,
      audit_version:AUDIT_VERSION
    });
  }

  verified('社會政策與社會立法-108-1-申論2',{
    kao:'題目有兩層：先依「申請入住、入住之中、離院之後」三個階段說明住宿型機構社工的角色，再說明面對各階段可能的倫理議題時應依哪些倫理原則處理。重點不是只背倫理決策模型。',
    dati:'先照題目指定的三個服務階段作答，每一階段都寫「主要任務＋社工角色」；再另立一段談倫理。角色可以從評估者、資訊提供者、倡導者、協調／個案管理者、支持者、轉銜與資源連結者等功能切入。倫理部分以服務對象最佳利益、人性尊嚴、自我決定、知情選擇、隱私保密、專業界限與最少損害為主；若價值衝突，再說明需依倫理決策程序、督導與法規審慎處理。',
    biaoti:[
      '一、申請入住：需求與適配性評估、權益及服務資訊說明、協助知情選擇，並連結家庭與相關資源。',
      '二、入住之中：持續評估與個案管理、心理社會支持、權益倡導、跨專業協調，並留意安全與生活適應。',
      '三、離院之後：離院／轉銜規劃、社區與家庭資源連結、必要的追蹤，維持服務連續性。',
      '四、倫理原則：最佳利益與尊嚴、自我決定與知情、隱私保密、專業關係／利益衝突、最少損害；遇衝突時依倫理守則、法規、督導與專業判斷處理。'
    ],
    kw:['入住評估','知情選擇','自我決定','個案管理','權益倡導','跨專業合作','離院轉銜','資源連結','保密','最佳利益','最少損害','專業界限'],
    review_sources:[
      '衛生福利部社會工作師倫理守則（97年備查版本之倫理衝突、自我決定、知情與保密原則）',
      '衛生福利部所屬住宿式機構社工業務：入院審核、入出院、轉銜與追蹤等實務職掌'
    ]
  });

  verified('人類行為與社會環境-110-2-申論1',{
    kao:'題目要完整回答三件事：第一，2018年第一期「強化社會安全網計畫」的三項目標；第二，從社工實務角度分析計畫的優點與限制；第三，針對自己提出的限制給出相對應的改善建議。不能用後來版本取代2018年的歷史脈絡。',
    dati:'第一段先把107年核定本的三項目標精確寫出；第二段再談優點，例如家庭／社區為基礎、前端預防、通報窗口簡化、跨體系整合；第三段把限制寫成「實施時可能遇到的問題」，例如跨網絡協作、人力與案量、區域資源差異、資訊共享與隱私，再逐項提出可操作的建議。限制與建議屬分析，不要冒充核定本的官方結論。',
    biaoti:[
      '一、三項目標：家庭社區為基石，前端預防更落實；簡化受理窗口，提升流程效率；整合服務體系，綿密安全網絡。',
      '二、可能優點：介入焦點由個人擴及家庭、連結社區支持；提早辨識脆弱／危機家庭；簡化通報與分流；促進社政、衛政、教育、勞政、警政等跨網絡服務。',
      '三、可能限制：跨機關權責與協作仍可能斷裂；社工人力、案量與督導量能；城鄉／區域資源不均；跨系統資料共享與隱私界線。',
      '四、建議：穩定人力與督導、建立明確跨網絡分工與個案協作機制、補強在地資源與社區支持、訂定必要且合比例的資訊共享規範，並以服務結果持續評估。'
    ],
    kw:['家庭社區為基石','前端預防','簡化受理窗口','流程效率','整合服務體系','社福中心','以家庭為中心','跨網絡合作','脆弱家庭','人力與案量','資訊共享'],
    review_sources:[
      '行政院107年2月26日核定／衛生福利部《強化社會安全網計畫》核定本，第47頁三項計畫目標及後續架構說明'
    ]
  });

  verified('社會工作研究方法-106-2-申論2',{
    kao:'先定義非反應式研究（non-reactive research），再舉出屬於非反應式研究的方法並說明為何。它的核心是研究者不以提問或實驗刺激直接介入受研究者，使被研究者不會因「知道正在被研究」而改變反應。',
    dati:'先用「降低反應性／研究者介入」下定義，再列方法。典型類型可寫非介入式或不顯眼測量（含行為留下的物理痕跡）、內容分析、既有統計／文件分析，以及既有資料的次級資料分析。要特別避免把深度訪談、焦點團體直接列為典型非反應式方法，因為它們會直接與受訪者互動。',
    biaoti:[
      '一、定義：研究者不直接以訪問、問卷或實驗情境刺激受研究者，資料蒐集本身盡量不造成受研究者因被研究而改變行為的反應性。',
      '二、不顯眼／非介入式測量：例如觀察公開可得的行為痕跡或人們自然留下的物理痕跡。',
      '三、內容分析：系統分析既有文字、影像、媒體或其他傳播內容。',
      '四、既有統計、文件與次級資料分析：運用政府統計、行政資料或他人先前蒐集的資料重新分析。',
      '五、補充限制：資料原先如何形成、測量品質與推論範圍仍需檢查；「非反應」不代表沒有研究倫理問題。'
    ],
    kw:['non-reactive research','unobtrusive research','反應性','內容分析','既有統計','次級資料分析','物理痕跡','非介入式測量'],
    review_sources:[
      'Neuman, Social Research Methods：Nonreactive Research and Secondary Analysis',
      'Foundations of Social Work Research：unobtrusive data、content analysis、physical traces'
    ]
  });

  verified('社會工作研究方法-105-2-申論1',{
    kao:'題目已指定科學方法的五項特性，作答要逐項說明「它是什麼」以及「為什麼科學研究需要它」。不是比較量化與質性研究，也不是只列五個名詞。',
    dati:'用五個小標逐一作答，每一項都採「定義→功能／必要性」兩句式最清楚。無偏見應寫成透過系統程序盡量降低個人偏誤，而不是宣稱研究者能做到完全沒有價值或偏誤。透明化則要讓他人知道資料如何取得、分析如何完成，才有可能檢驗與重複。',
    biaoti:[
      '一、暫時性（tentative）：科學結論是依目前證據形成的暫時解釋，遇到更好的證據可修正；可避免把知識當成不可挑戰的定論。',
      '二、反覆論證性（replication）：研究程序需能被重做或重新檢驗；藉重複研究確認結果是否穩健，而不是一次結果就定論。',
      '三、觀察（observation）：主張要建立在可觀察、可蒐集的經驗資料上；讓判斷能接受實證檢驗，而非只憑權威、直覺或信念。',
      '四、無偏見（unbiased）：以明確的抽樣、測量、分析與查核程序盡量降低研究者偏見及選擇性解釋；提升結論的可信度。',
      '五、透明化（transparent）：清楚交代研究問題、方法、資料來源與分析程序，使他人可以理解、檢查、批評並在適當條件下重複研究。'
    ],
    kw:['tentative','replication','observation','unbiased','transparent','可修正','可重複','實證觀察','降低偏誤','研究透明'],
    review_sources:[
      '考選部105年第二次社會工作師考試原題（五項特性）',
      'Open science / social science transparency literature：replication、data/method transparency and reproducibility'
    ]
  });

  verified('社會政策與社會立法-108-2-申論1',{
    kao:'先說明社會政策中的「平等」不是只有每個人拿到完全相同的東西，再回答 Le Grand 所問的 equality of what：公共支出、最終所得、服務使用、使用成本與最終結果五種平等，並逐一用長期照顧服務舉例。',
    dati:'先簡短區分形式上的相同對待與依需要調整資源的實質平等，再依 Le Grand 五個面向逐項寫「平等的是什麼＋長照例子」。五個面向彼此相關，但不要混成機會平等／結果平等的一般口號，也不要把後續政策硬塞回108年考題。',
    biaoti:[
      '一、平等的基本概念：平等要先回答「哪一個面向要平等」；相同對待未必能處理不同需要，因此社會政策還會討論資源、使用、成本與結果等不同層次。',
      '二、公共支出的平等（equality of public expenditure）：公共服務支出在人與人之間如何分配；長照可檢視每位服務對象可獲公共資源的分配是否相等。',
      '三、最終所得的平等（equality of final income）：把私人所得加上公共服務／補助的價值後，所得差距是否縮小；長照補助可從是否減輕弱勢家庭照顧支出負擔來分析。',
      '四、使用的平等（equality of use）：相同需要者是否能有相當的服務使用；長照可比較同等照顧需要者在不同地區、身分下實際使用服務的差異。',
      '五、成本的平等（equality of cost）：相關使用者取得一單位服務所承擔的金錢、時間或交通等成本是否相當；長照可檢視偏鄉交通與取得服務成本。',
      '六、結果的平等（equality of outcome）：資源配置是否促進服務結果的平等；長照可從功能維持、生活品質、照顧負荷等結果是否因背景差異而出現可避免的不平等來討論。'
    ],
    kw:['equality of what','公共支出平等','最終所得平等','使用平等','成本平等','結果平等','Le Grand','長期照顧','實質平等'],
    review_sources:[
      'Julian Le Grand, The Strategy of Equality (1982)：five dimensions of equality',
      '後續同儕審查文獻對 Le Grand 五面向之整理：public expenditure、final income、use、cost、outcome'
    ]
  });

  window.SWSI_ESSAY_AUDIT_BATCH1={
    version:AUDIT_VERSION,
    reviewedAt:REVIEWED_AT,
    verifiedIds:[
      '社會政策與社會立法-108-1-申論2',
      '人類行為與社會環境-110-2-申論1',
      '社會工作研究方法-106-2-申論2',
      '社會工作研究方法-105-2-申論1',
      '社會政策與社會立法-108-2-申論1'
    ]
  };
})();
/* ===== SWSI Code Health P0 Runtime Guard 2026-08-26 ===== */
(function(){
  'use strict';

  /* 00.part is the canonical grading owner. Keep only this public edge guard:
     invalid grading metadata must never expose accepted choices directly. */
  var baseAcceptedAnswers=typeof acceptedAnswers==='function'?acceptedAnswers:null;
  if(baseAcceptedAnswers){
    acceptedAnswers=function(item){
      if(typeof gradingMode==='function'&&gradingMode(item)==='invalid')return new Set();
      return baseAcceptedAnswers(item);
    };
    window.acceptedAnswers=acceptedAnswers;
  }
  window.swsiGradingContractVersion='2026-08-26.fail-closed.v2';

  /* normalize is owned by 00.part. Its body resolves gradingMode at call time. */

  /* Fail closed before a bad special-credit row can reach scoring UI. */
  var oldRenderQuiz=typeof renderQuiz==='function'?renderQuiz:null;
  if(oldRenderQuiz){
    renderQuiz=function(){
      try{
        var item=(typeof queue!=='undefined'&&queue&&queue.length)?queue[idx]:null;
        if(item&&typeof gradingMode==='function'&&gradingMode(item)==='invalid'){
          app.innerHTML='<div class="empty"><div class="ico">⚠</div><h3>這題暫停判分</h3><p>官方給分資料不完整或格式異常。平台不會自行猜測答案，請回首頁改練其他題目。</p><button class="btn" style="max-width:220px;margin:20px auto 0" onclick="go(\'home\')">回首頁</button></div>';
          return;
        }
      }catch(_e){}
      return oldRenderQuiz();
    };
  }
})();
/* ===== SWSI Code Health P0 Runtime Guard END ===== */
/* ===== SWSI MK Record Policy 2026-08-27 ===== */
(function(){
  'use strict';

  /* all_credit is a score rule, not an answered choice. An unanswered
     all-credit row must not be written into learner wrong-answer history. */
  window.swsiShouldRecordMockAnswer=function(gm,picked){
    if(gm==='all_credit'&&picked==null)return false;
    return true;
  };

  window.swsiMockRecordPolicyVersion='2026-08-27.v1';
})();
/* ===== SWSI MK Record Policy END ===== */
/* ===== SWSI MK Unified Grading Contract 2026-08-26 ===== */
(function(){
  'use strict';
  if(!window.MK)return;

  var legacyMK=window.MK;
  var ov=null,Q=[],idx=0,ans={},timer=null,left=0,limited=true,t0=0,scope='全部科目',running=false;
  var mode='random',exYear='',exRound='',legacyStyleReady=false;

  function E(v){return typeof window.swsiEsc==='function'?window.swsiEsc(v):String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function W(q){try{return typeof drawWeight==='function'?(drawWeight(q)||1):1;}catch(_e){return 1;}}
  function fmt(s){if(s<0)s=0;var m=Math.floor(s/60),x=s%60;return m+':'+(x<10?'0':'')+x;}
  function bank(){return typeof ALL!=='undefined'&&Array.isArray(ALL)?ALL:[];}
  function subs(){return typeof SUBJECTS!=='undefined'&&Array.isArray(SUBJECTS)?SUBJECTS:[];}
  function gradeMode(q){return typeof window.gradingMode==='function'?window.gradingMode(q):'invalid';}
  function correct(q,picked){return typeof window.isCorrectAnswer==='function'?window.isCorrectAnswer(q,picked):false;}
  function label(q){return typeof window.answerLabel==='function'?window.answerLabel(q):('正確答案：'+E(q&&q.answer||''));}

  async function prepareLegacyStyle(){
    if(legacyStyleReady)return;
    legacyStyleReady=true;
    try{
      var out=legacyMK.open&&legacyMK.open();
      if(out&&typeof out.then==='function')await out;
      if(legacyMK.close)legacyMK.close();
    }catch(_e){}
    if(!document.getElementById('mk-style')){
      var st=document.createElement('style');st.id='mk-style';
      st.textContent='.mk-ov{position:fixed;inset:0;z-index:9999;background:var(--paper,#EFF3F0);overflow-y:auto;font-family:inherit;color:var(--ink,#2A2C2A)}.mk-wrap{max-width:680px;margin:0 auto;padding:16px 16px 80px}.mk-top{position:sticky;top:0;background:var(--paper,#EFF3F0);padding:10px 0 12px;border-bottom:1px solid var(--line,#DCE4DF);display:flex;align-items:center;justify-content:space-between;gap:10px;z-index:5}.mk-timer{font-size:21px;font-weight:800;color:var(--pine,#4F7E76)}.mk-timer.warn{color:var(--wrong,#9E6155)}.mk-prog,.mk-sub{font-size:var(--fs-b);color:var(--ink-soft,#757A75)}.mk-x{background:none;border:none;font-size:22px;cursor:pointer}.mk-btn{font-family:inherit;border:none;border-radius:12px;padding:13px 18px;font-size:var(--fs-h);font-weight:700;cursor:pointer}.mk-btn.go{background:var(--pine,#4F7E76);color:#fff}.mk-btn.ghost{background:var(--paper2,#F8FAF9);border:1px solid var(--line,#DCE4DF)}.mk-btn:disabled{opacity:.4}.mk-h1{font-size:23px;font-weight:800;margin:18px 0 6px}.mk-lab{font-size:var(--fs-b);font-weight:700;color:var(--ink-soft,#757A75);margin:18px 0 8px}.mk-sel{width:100%;font-family:inherit;font-size:var(--fs-h);padding:13px 14px;border:1px solid var(--line,#DCE4DF);border-radius:12px;background:var(--paper2,#F8FAF9)}.mk-row{display:flex;gap:10px;flex-wrap:wrap}.mk-pill{flex:1;min-width:90px;text-align:center;background:var(--paper2,#F8FAF9);border:1px solid var(--line,#DCE4DF);border-radius:13px;padding:16px 10px;cursor:pointer}.mk-pill .b{font-size:var(--fs-q);font-weight:800;color:var(--pine,#4F7E76);display:block}.mk-pill .s{font-size:var(--fs-s);color:var(--ink-soft,#757A75)}.mk-toggle{display:inline-flex;border:1px solid var(--line,#DCE4DF);border-radius:999px;padding:9px 15px;cursor:pointer}.mk-qcard{background:var(--paper2,#F8FAF9);border:1px solid var(--line,#DCE4DF);border-radius:18px;padding:20px 18px;margin-top:14px}.mk-qmeta{font-size:var(--fs-s);color:var(--ink-soft,#757A75);margin-bottom:10px}.mk-q{font-size:var(--fs-q);line-height:1.7;font-weight:600;margin-bottom:16px}.mk-opt{display:flex;gap:12px;align-items:flex-start;border:1px solid var(--line,#DCE4DF);border-radius:13px;padding:14px 15px;margin-bottom:10px;cursor:pointer}.mk-opt.sel{border-color:var(--pine,#4F7E76);background:var(--correct-bg,#E3EDE9)}.mk-nav{display:flex;gap:10px;margin-top:14px}.mk-nav .mk-btn{flex:1}.mk-pal{display:grid;grid-template-columns:repeat(8,1fr);gap:7px;margin-top:18px}.mk-cell{aspect-ratio:1;display:flex;align-items:center;justify-content:center;border:1px solid var(--line,#DCE4DF);border-radius:9px;cursor:pointer}.mk-cell.done{background:var(--pine,#4F7E76);color:#fff}.mk-cell.cur{outline:2px solid var(--pine,#4F7E76)}.mk-score{text-align:center;background:var(--paper2,#F8FAF9);border:1px solid var(--line,#DCE4DF);border-radius:18px;padding:26px 18px;margin-top:8px}.mk-score .big{font-size:46px;font-weight:800;color:var(--pine,#4F7E76)}.mk-score .pct{font-size:var(--fs-h);color:var(--ink-soft,#757A75)}.mk-bar{height:9px;border-radius:5px;background:var(--line,#DCE4DF);overflow:hidden}.mk-bar i{display:block;height:100%;background:var(--pine,#4F7E76)}.mk-rev{background:var(--paper2,#F8FAF9);border:1px solid var(--line,#DCE4DF);border-radius:14px;padding:15px 16px;margin-bottom:10px}.mk-rev .rq{font-size:var(--fs-b);font-weight:600}.mk-rev .ln{font-size:var(--fs-b);line-height:1.6;margin:3px 0}.mk-tag{display:inline-block;font-size:var(--fs-s);padding:2px 8px;border-radius:6px;margin-right:6px}.mk-tag.w{background:var(--wrong-bg,#F3EBE7);color:var(--wrong,#9E6155)}.mk-tag.n{background:var(--line,#DCE4DF);color:var(--ink-soft,#757A75)}';
      document.head.appendChild(st);
    }
  }
  function mount(){if(!ov){ov=document.createElement('div');ov.className='mk-ov';document.body.appendChild(ov);}}
  function shut(){if(timer){clearInterval(timer);timer=null;}if(ov&&ov.parentNode)ov.parentNode.removeChild(ov);ov=null;running=false;}

  function usableRandomBank(){return bank().filter(function(q){return gradeMode(q)!=='invalid'&&(scope==='全部科目'||q.subject===scope);});}
  function papers(){
    var seen={},out=[];
    bank().forEach(function(q){var y=String(q.year||'').trim(),r=String(q.round||'').trim();if(!y)return;var k=y+'|'+r;if(!seen[k]){seen[k]=1;out.push({year:y,round:r});}});
    out.sort(function(a,b){var yd=(parseInt(b.year,10)||0)-(parseInt(a.year,10)||0);return yd!==0?yd:(b.round||'').localeCompare(a.round||'');});
    out.forEach(function(p){p.label=p.year+' 年'+(p.round?(' '+p.round):'');});return out;
  }
  function rawExam(){
    var order=subs();
    var arr=bank().filter(function(q){if(scope!=='全部科目'&&q.subject!==scope)return false;return String(q.year||'').trim()===exYear&&String(q.round||'').trim()===exRound;});
    arr.sort(function(a,b){if(scope==='全部科目'){var sa=order.indexOf(a.subject),sb=order.indexOf(b.subject);if(sa!==sb)return sa-sb;}return (parseInt(a.qno,10)||0)-(parseInt(b.qno,10)||0);});
    return arr;
  }
  function build(n){
    var arr=usableRandomBank();
    arr=arr.map(function(q){return {q:q,k:Math.pow(Math.random(),1/W(q))};}).sort(function(a,b){return b.k-a.k;}).map(function(x){return x.q;});
    return n&&arr.length>n?arr.slice(0,n):arr;
  }

  function setup(){
    if(timer){clearInterval(timer);timer=null;}running=false;
    var opts=['全部科目'].concat(subs()).map(function(s){return '<option '+(s===scope?'selected':'')+'>'+E(s)+'</option>';}).join('');
    var modeRow='<div class="mk-row"><div class="mk-pill" style="'+(mode==='random'?'border-color:var(--pine);background:var(--correct-bg)':'')+'" onclick="MK.setMode(\'random\')"><span class="b" style="font-size:var(--fs-h)">🎲 隨機抽題</span><span class="s">從可判分題庫隨機出</span></div><div class="mk-pill" style="'+(mode==='exam'?'border-color:var(--pine);background:var(--correct-bg)':'')+'" onclick="MK.setMode(\'exam\')"><span class="b" style="font-size:var(--fs-h)">📅 指定歷屆</span><span class="s">寫某年整卷</span></div></div>';
    var bottom='';
    if(mode==='exam'){
      var ps=papers();if((!exYear||!ps.some(function(p){return p.year===exYear&&p.round===exRound;}))&&ps.length){exYear=ps[0].year;exRound=ps[0].round;}
      var popt=ps.map(function(p){return '<option value="'+E(p.year+'|'+p.round)+'"'+(p.year===exYear&&p.round===exRound?' selected':'')+'>'+E(p.label)+'</option>';}).join('');
      var raw=rawExam(),bad=raw.filter(function(q){return gradeMode(q)==='invalid';}).length;
      bottom='<div class="mk-lab">選擇年份／考次</div><select class="mk-sel" onchange="MK.setPaper(this.value)">'+popt+'</select><div class="mk-sub" style="margin-top:10px">共 <b>'+raw.length+'</b> 題'+(bad?'；其中 <b style="color:var(--wrong)">'+bad+' 題給分資料異常，修正前不允許開考</b>':'')+'。</div><button class="mk-btn go" style="width:100%" onclick="MK.beginExam()">開始寫這份歷屆</button>';
    }else{
      bottom='<div class="mk-lab">選擇題數</div><div class="mk-row"><div class="mk-pill" onclick="MK.begin(20)"><span class="b">20</span><span class="s">題</span></div><div class="mk-pill" onclick="MK.begin(40)"><span class="b">40</span><span class="s">題</span></div><div class="mk-pill" onclick="MK.begin(80)"><span class="b">80</span><span class="s">題</span></div></div>';
    }
    ov.innerHTML='<div class="mk-wrap"><div class="mk-top"><div class="mk-timer" style="color:var(--ink)">📝 計時模擬考</div><button class="mk-x" onclick="MK.close()">✕</button></div><div class="mk-h1">設定這場模擬考</div><div class="mk-sub">所有模式都使用與一般刷題相同的官方 grading contract；特殊給分資料不完整時不猜答案。</div><div class="mk-lab">考試範圍</div><select class="mk-sel" onchange="MK.setScope(this.value)">'+opts+'</select><div class="mk-lab">出題方式</div>'+modeRow+'<div class="mk-lab">時間模式</div><div class="mk-toggle" onclick="MK.toggleTimed()"><span id="mk-tg">'+(limited?'⏱ 倒數計時':'∞ 不限時')+'</span></div>'+bottom+'</div>';
  }

  function run(){
    var q=Q[idx],letters=['A','B','C','D'];
    var options=letters.map(function(L){var t=q.options&&q.options[L];if(t==null||t==='')return '';return '<div class="mk-opt'+(ans[idx]===L?' sel':'')+'" id="mk-opt-'+L+'" onclick="MK.pick(\''+L+'\')"><span class="lab">('+L+')</span><span>'+E(t)+'</span></div>';}).join('');
    var pal=Q.map(function(_,i){return '<div class="mk-cell'+(ans[i]!=null?' done':'')+(i===idx?' cur':'')+'" onclick="MK.jump('+i+')">'+(i+1)+'</div>';}).join('');
    ov.innerHTML='<div class="mk-wrap"><div class="mk-top"><div class="mk-timer'+(limited&&left<=60?' warn':'')+'" id="mk-timer">'+(limited?fmt(left):'∞')+'</div><div class="mk-prog">第 '+(idx+1)+' / '+Q.length+' 題　已答 '+Object.keys(ans).length+'</div><button class="mk-btn go" onclick="MK.submit()">交卷</button></div><div class="mk-qcard"><div class="mk-qmeta">'+E(q.subject||'')+'　'+E(q.year||'')+' '+E(q.round||'')+'</div><div class="mk-q">'+E(q.q||'').replace(/\n/g,'<br>')+'</div>'+options+'</div><div class="mk-nav"><button class="mk-btn ghost" onclick="MK.go(-1)" '+(idx===0?'disabled':'')+'>‹ 上一題</button><button class="mk-btn ghost" onclick="MK.go(1)" '+(idx===Q.length-1?'disabled':'')+'>下一題 ›</button></div><div class="mk-pal">'+pal+'</div><button class="mk-btn go" style="width:100%;margin-top:18px" onclick="MK.submit()">交卷看結果</button></div>';
    window.scrollTo(0,0);
  }
  function tick(){left--;var el=document.getElementById('mk-timer');if(el){el.textContent=fmt(left);if(left<=60)el.classList.add('warn');}if(left<=0){if(timer)clearInterval(timer);timer=null;grade(true);}}

  function evaluateMockAnswers(items,answers){
    var rows=Array.isArray(items)?items:[];
    var picks=answers&&typeof answers==='object'?answers:{};
    var invalid=rows.filter(function(q){return gradeMode(q)==='invalid';});
    if(invalid.length){
      return {blocked:true,total:rows.length,correct:0,answered:0,bySubj:{},wrong:[],results:[],invalidIds:invalid.map(function(q){return q&&q.id||'';})};
    }
    var out={blocked:false,total:rows.length,correct:0,answered:0,bySubj:{},wrong:[],results:[],invalidIds:[]};
    rows.forEach(function(q,i){
      var picked=picks[i]!=null?picks[i]:null;
      var gm=gradeMode(q),ok=correct(q,picked);
      if(picked!=null)out.answered++;
      if(ok)out.correct++;
      if(!out.bySubj[q.subject])out.bySubj[q.subject]={t:0,c:0};
      out.bySubj[q.subject].t++;if(ok)out.bySubj[q.subject].c++;
      var row={q:q,picked:picked,gradingMode:gm,correct:ok,dataError:false};
      out.results.push(row);
      if(!ok)out.wrong.push(row);
    });
    return out;
  }
  window.swsiEvaluateMockAnswers=evaluateMockAnswers;

  function grade(auto){
    if(timer){clearInterval(timer);timer=null;}running=false;
    var scored=evaluateMockAnswers(Q,ans);
    if(scored.blocked){
      ov.innerHTML='<div class="mk-wrap"><div class="empty"><div class="ico">⚠</div><h3>這份模擬考暫停判分</h3><p>其中有 '+scored.invalidIds.length+' 題官方給分資料不完整。平台沒有計分，也沒有寫入學習紀錄。</p><button class="mk-btn go" onclick="MK.retry()">回設定頁</button></div></div>';
      return;
    }
    scored.results.forEach(function(row){
      try{
        if(typeof record==='function'){
          var should=typeof window.swsiShouldRecordMockAnswer==='function'
            ?window.swsiShouldRecordMockAnswer(row.gradingMode,row.picked)
            :!(row.gradingMode==='all_credit'&&row.picked==null);
          if(should)record(row.q,row.picked,row.correct);
        }
      }catch(_e){}
    });
    var used=Math.max(0,Math.floor((Date.now()-t0)/1000)),pct=scored.total?Math.round(scored.correct/scored.total*100):0;
    var subjHtml=Object.keys(scored.bySubj).map(function(s){var o=scored.bySubj[s],r=o.t?Math.round(o.c/o.t*100):0;return '<div style="margin-top:10px"><div style="display:flex;justify-content:space-between"><span>'+E(s)+'</span><span>'+o.c+'/'+o.t+'（'+r+'%）</span></div><div class="mk-bar"><i style="width:'+r+'%"></i></div></div>';}).join('');
    var revHtml=scored.wrong.map(function(w){
      var q=w.q,p=w.picked,exp=q.exp||{},ex='';
      if(exp.why)ex+='<div class="ln"><b>為什麼答案對：</b>'+E(exp.why)+'</div>';
      if(exp.others)ex+='<div class="ln"><b>其他選項：</b>'+E(exp.others)+'</div>';
      if(exp.trap)ex+='<div class="ln"><b>考場陷阱：</b>'+E(exp.trap)+'</div>';
      var tag=p!=null?'<span class="mk-tag w">你選 '+E(p)+'</span>':'<span class="mk-tag n">未作答</span>';
      return '<div class="mk-rev"><div class="rq">'+E(q.q||'').slice(0,140)+'</div><div class="ln">'+tag+'<span class="mk-tag n">'+E(w.dataError?'給分資料異常':label(q))+'</span></div>'+ex+'</div>';
    }).join('');
    ov.innerHTML='<div class="mk-wrap"><div class="mk-top"><div class="mk-timer" style="color:var(--ink)">模擬考結果</div><button class="mk-x" onclick="MK.close()">✕</button></div>'+(auto?'<div class="mk-sub" style="color:var(--wrong);margin-top:14px">⏰ 時間到，已自動交卷。</div>':'')+'<div class="mk-score"><div class="big">'+scored.correct+' / '+scored.total+'</div><div class="pct">答對率 '+pct+'%　·　實際作答 '+scored.answered+' 題　·　用時 '+fmt(used)+'</div></div><div class="mk-lab">各科表現（未作答也列入分母）</div>'+subjHtml+(revHtml?'<div class="mk-lab">錯題與未作答（'+scored.wrong.length+' 題）</div>'+revHtml:'<div class="mk-sub" style="margin-top:16px">🎉 全部計分正確！</div>')+'<div class="mk-nav"><button class="mk-btn ghost" onclick="MK.retry()">再考一次</button><button class="mk-btn go" onclick="MK.close()">完成</button></div></div>';
    window.scrollTo(0,0);
  }

  window.MK={
    contractVersion:'2026-08-26.unified-grading.v2',
    open:async function(){
      try{if(window.SWSI_QB&&!window.SWSI_QB.allComplete&&typeof window.ensureAllQuestionsLoaded==='function')await window.ensureAllQuestionsLoaded();}catch(err){if(typeof showLoadError==='function')showLoadError(err);return;}
      await prepareLegacyStyle();mount();setup();
    },
    close:function(){if(running&&!confirm('模擬考進行中，確定要離開？這次未交卷的作答不會記錄。'))return;shut();},
    setScope:function(v){scope=v;if(mode==='exam')setup();},
    setMode:function(v){mode=v;setup();},
    setPaper:function(v){var p=String(v).split('|');exYear=p[0];exRound=p.slice(1).join('|');setup();},
    toggleTimed:function(){limited=!limited;var el=document.getElementById('mk-tg');if(el)el.textContent=limited?'⏱ 倒數計時':'∞ 不限時';},
    begin:function(n){var pool=build(n);if(!pool.length){alert('這個範圍目前沒有可安全判分的題目。');return;}Q=pool;idx=0;ans={};running=true;t0=Date.now();left=Math.round(Q.length*1.2)*60;if(timer)clearInterval(timer);timer=limited?setInterval(tick,1000):null;run();},
    beginExam:function(){var raw=rawExam(),bad=raw.filter(function(q){return gradeMode(q)==='invalid';});if(!raw.length){alert('這份考卷目前沒有題目。');return;}if(bad.length){alert('這份考卷有 '+bad.length+' 題官方給分資料不完整。為避免算錯分，修正前暫不開放整卷模擬。');return;}Q=raw;idx=0;ans={};running=true;t0=Date.now();left=Math.round(Q.length*1.2)*60;if(timer)clearInterval(timer);timer=limited?setInterval(tick,1000):null;run();},
    pick:function(L){ans[idx]=L;['A','B','C','D'].forEach(function(x){var el=document.getElementById('mk-opt-'+x);if(el)el.classList.toggle('sel',x===L);});var cells=ov.querySelectorAll('.mk-cell');if(cells[idx])cells[idx].classList.add('done');var pr=ov.querySelector('.mk-prog');if(pr)pr.textContent='第 '+(idx+1)+' / '+Q.length+' 題　已答 '+Object.keys(ans).length;},
    go:function(d){var n=idx+d;if(n<0||n>=Q.length)return;idx=n;run();},
    jump:function(i){if(i<0||i>=Q.length)return;idx=i;run();},
    submit:function(){var un=Q.length-Object.keys(ans).length;if(un>0&&!confirm('還有 '+un+' 題未作答，確定交卷？未作答普通題會計為錯誤。'))return;grade(false);},
    retry:function(){setup();}
  };
})();
/* ===== SWSI MK Unified Grading Contract END ===== */
/* ===== SWSI Full Question Bank Integrity Guard 2026-08-27 ===== */
(function(){
  'use strict';

  function txt(v){return String(v==null?'':v).trim();}
  function roundKey(v){
    try{return typeof canonicalRound==='function'?String(canonicalRound(v)):txt(v);}
    catch(_e){return txt(v);}
  }
  function fail(message){throw new Error('題庫完整性驗證失敗：'+message);}

  function assertCompleteBank(rows,manifest,loadedFiles){
    if(!manifest||!Array.isArray(manifest.shards))fail('缺少 manifest shards');
    var total=Number(manifest.total_questions);
    if(!Number.isInteger(total)||total<1)fail('manifest total_questions 不合法');

    var expectedTotal=0;
    var expectedSessions=new Map();
    var expectedFiles=new Set();
    manifest.shards.forEach(function(meta){
      var file=txt(meta&&meta.file);
      var count=Number(meta&&meta.question_count);
      var key=txt(meta&&meta.year)+'|'+roundKey(meta&&meta.round);
      if(!file)fail('manifest shard file 空白');
      if(expectedFiles.has(file))fail('manifest shard file 重複：'+file);
      expectedFiles.add(file);
      if(!Number.isInteger(count)||count<1)fail('manifest shard 題數不合法：'+file);
      if(expectedSessions.has(key))fail('manifest 考次重複：'+key);
      expectedSessions.set(key,count);
      expectedTotal+=count;
    });
    if(expectedTotal!==total)fail('manifest shard 題數總和 '+expectedTotal+' != total_questions '+total);

    var loaded=loadedFiles instanceof Set?loadedFiles:new Set(Array.isArray(loadedFiles)?loadedFiles:[]);
    if(loaded.size!==expectedFiles.size||Array.from(expectedFiles).some(function(file){return !loaded.has(file);})){
      fail('尚未載完 manifest 全部 shard');
    }

    if(!Array.isArray(rows))fail('ALL 不是陣列');
    if(rows.length!==total)fail('實際題數 '+rows.length+' != manifest '+total);

    var ids=new Set();
    var actualSessions=new Map();
    rows.forEach(function(row){
      var id=txt(row&&row.id);
      if(!id)fail('題目 ID 空白');
      if(ids.has(id))fail('跨 shard 題目 ID 重複：'+id);
      ids.add(id);
      var key=txt(row&&row.year)+'|'+roundKey(row&&row.round);
      actualSessions.set(key,(actualSessions.get(key)||0)+1);
    });
    if(ids.size!==total)fail('unique ID 數 '+ids.size+' != manifest '+total);

    expectedSessions.forEach(function(expected,key){
      var actual=actualSessions.get(key)||0;
      if(actual!==expected)fail('考次 '+key+' 實際 '+actual+' 題 != manifest '+expected+' 題');
    });
    actualSessions.forEach(function(_count,key){
      if(!expectedSessions.has(key))fail('ALL 含 manifest 未列出的考次：'+key);
    });

    return {ok:true,total:total,uniqueIds:ids.size,sessions:expectedSessions.size};
  }

  window.swsiAssertCompleteQuestionBank=assertCompleteBank;
  window.swsiQuestionBankIntegrityVersion='2026-08-27.full-bank.v1';

  function guardAfterLoad(previous,args){
    return Promise.resolve(previous.apply(window,args)).then(function(result){
      var qb=window.SWSI_QB;
      if(qb&&qb.manifest&&qb.loadedFiles&&qb.loadedFiles.size>=qb.manifest.shards.length){
        try{
          var rows=(typeof ALL!=='undefined'&&Array.isArray(ALL))?ALL:[];
          var report=assertCompleteBank(rows,qb.manifest,qb.loadedFiles);
          qb.allComplete=true;
          qb.error=null;
          window.__swsiQuestionBankIntegrity=report;
        }catch(err){
          qb.allComplete=false;
          qb.error=err;
          throw err;
        }
      }
      return result;
    });
  }

  if(typeof window.ensureShardMetasLoaded==='function'){
    var previousEnsureShardMetasLoaded=window.ensureShardMetasLoaded;
    window.ensureShardMetasLoaded=function(){return guardAfterLoad(previousEnsureShardMetasLoaded,arguments);};
    try{ensureShardMetasLoaded=window.ensureShardMetasLoaded;}catch(_e){}
  }

  if(typeof window.ensureAllQuestionsLoaded==='function'){
    var previousEnsureAllQuestionsLoaded=window.ensureAllQuestionsLoaded;
    window.ensureAllQuestionsLoaded=function(){
      return Promise.resolve(previousEnsureAllQuestionsLoaded.apply(window,arguments)).then(function(result){
        var qb=window.SWSI_QB;
        try{
          var rows=(typeof ALL!=='undefined'&&Array.isArray(ALL))?ALL:[];
          var report=assertCompleteBank(rows,qb&&qb.manifest,qb&&qb.loadedFiles);
          qb.allComplete=true;
          qb.error=null;
          window.__swsiQuestionBankIntegrity=report;
          return result;
        }catch(err){
          if(qb){qb.allComplete=false;qb.error=err;}
          throw err;
        }
      });
    };
    try{ensureAllQuestionsLoaded=window.ensureAllQuestionsLoaded;}catch(_e){}
  }
})();
/* ===== SWSI Full Question Bank Integrity Guard END ===== */

/* SWSI Preview Component Polish 2026-08-29
   Layer 3 only. Global shell, footer visibility and bottom-nav geometry are owned
   exclusively by 15.layout-foundation.part.
*/
(function(){
  'use strict';

  var STYLE_ID='swsi-preview-component-polish-20260829';
  if(!document.getElementById(STYLE_ID)){
    var st=document.createElement('style');
    st.id=STYLE_ID;
    st.textContent=`
      /* Closed disclosures consume only their summary row. */
      #app details.swsi-other-tools:not([open]),
      #app details.swsi-data-version:not([open]){
        padding-bottom:0!important;
      }
      #app details.swsi-other-tools:not([open]) .swsi-other-grid,
      #app details.swsi-data-version:not([open]) .body{
        display:none!important;
      }
      #app .swsi-principle-note{margin-bottom:0!important;}
      #app .swsi-data-version{margin-bottom:0!important;}
    `;
    document.head.appendChild(st);
  }
})();
