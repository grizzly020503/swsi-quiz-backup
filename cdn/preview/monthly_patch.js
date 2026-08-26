
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
const SWSI_ANY_ANSWER_LEGACY_IDS = new Set([
  'SW-105-1-17',
  'SW-106-1-36',
  'HBSE-108-2-039',
  'HBSE-110-2-034'
]);

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
function gradingMode(item){
  if(!item) return 'standard';
  const raw = swsiText(item.grading_mode).trim();
  if(SWSI_VALID_GRADING_MODES.has(raw)) return raw;
  if(SWSI_ANY_ANSWER_LEGACY_IDS.has(swsiText(item.id))) return 'any_answer';
  if(/一律給分|送分/.test(swsiText(item.answer))) return 'all_credit';
  return 'standard';
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
  if(mode === 'all_credit') return true;
  if(mode === 'any_answer') return !!p && /^[ABCD]$/.test(p);
  return !!p && acceptedAnswers(item).has(p);
}
function answerLabel(item){
  const mode = gradingMode(item);
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
    error: null
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
    const files = new Set();
    for(const meta of m.shards){
      if(!meta || !/^\d{3}$/.test(swsiText(meta.year)) || !/\.json$/.test(swsiText(meta.file))) throw new Error('題庫目錄考次資料不完整');
      if(Number(meta.question_count) !== 200) throw new Error('題庫目錄存在不完整考次');
      if(!/^[a-f0-9]{64}$/i.test(swsiText(meta.sha256))) throw new Error('題庫目錄缺少完整雜湊');
      if(files.has(meta.file)) throw new Error('題庫目錄出現重複 shard');
      files.add(meta.file);
    }
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
    q.grading_mode = SWSI_VALID_GRADING_MODES.has(swsiText(r && r.grading_mode))
      ? swsiText(r.grading_mode)
      : gradingMode(Object.assign({}, q, {id:r && r.id, answer:r && r.answer}));
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
      const mode = gradingMode(row);
      if(!SWSI_VALID_GRADING_MODES.has(mode)) throw new Error('題庫 shard grading_mode 不合法');
    }
    return payload;
  }

  function mergeRowsIntoAll(rows, file){
    const map = new Map(ALL.map(q=>[q.id,q]));
    for(const raw of rows){
      const q = normalize(raw);
      map.set(q.id,q);
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
        payload = validateShard(await fetchJSON(SWSI_QUESTION_CDN_BASE + '/' + encodeURIComponent(meta.file),{timeout:15000}), meta);
        idbPut('question-shard:'+meta.file,{payload,sha256:meta.sha256,savedAt:Date.now()}).catch(()=>{});
        QB.usingOffline = false;
      }catch(err){
        networkErr = err;
        console.warn('Cloudflare shard unavailable:', meta.file, err);
      }
      if(!payload){
        try{
          const rec = await idbGet('question-shard:'+meta.file);
          if(rec && rec.payload && (!rec.sha256 || rec.sha256 === meta.sha256)){
            payload = validateShard(rec.payload,meta);
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

  async function ensureShardMetasLoaded(metas){
    const xs = (metas || []).filter(Boolean);
    if(!xs.length) return;
    await Promise.all(xs.map(loadQuestionShard));
    if(QB.manifest && QB.loadedFiles.size >= QB.manifest.shards.length) QB.allComplete = true;
  }
  window.ensureShardMetasLoaded = ensureShardMetasLoaded;

  async function ensureAllQuestionsLoaded(){
    const m = await loadQuestionManifest();
    showLoading('正在準備完整題庫','第一次開啟全庫功能時會下載已發布的歷屆考次；之後會使用快取。');
    await ensureShardMetasLoaded(m.shards);
    QB.allComplete = true;
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
      ALL = [];
      SUBJECTS = SWSI_CORE_SUBJECTS.slice();
      QB.allComplete = false;
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

/* SWSI Product Philosophy Home 2026-08-26
   Keep the exam-prep flow calm and direct: study first, platform second.
   Core promise: free, no answer locks, no points, no anxiety-selling UI.
*/
(function(){
  'use strict';

  function installStyle(){
    if(document.getElementById('swsi-product-philosophy-style')) return;
    var style=document.createElement('style');
    style.id='swsi-product-philosophy-style';
    style.textContent=`
      .swsi-focus-hero{background:linear-gradient(155deg,#426D64,#355A52);color:#fff;border-radius:22px;padding:24px 21px 21px;margin-bottom:14px;box-shadow:0 7px 24px rgba(43,62,57,.14)}
      .swsi-focus-hero .kicker{font-size:var(--swsi-ui-small,11.5px);font-weight:800;letter-spacing:1.8px;opacity:.78;margin-bottom:5px}
      .swsi-focus-hero h1{font-family:'Noto Serif TC',serif;font-size:var(--swsi-ui-hero,25px);font-weight:900;line-height:1.35;letter-spacing:.2px;margin:0}
      .swsi-focus-hero p{font-size:var(--swsi-ui-body,14px);line-height:1.72;opacity:.92;margin:8px 0 0}
      .swsi-promise-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:15px}
      .swsi-promise-row span{font-size:var(--swsi-ui-small,11.5px);line-height:1.3;padding:5px 9px;border:1px solid rgba(255,255,255,.20);background:rgba(255,255,255,.11);border-radius:999px}

      .swsi-focus-primary{background:#fff;border:1px solid rgba(79,126,118,.48);border-radius:19px;padding:18px;margin-bottom:10px;box-shadow:0 3px 14px rgba(43,42,38,.035)}
      .swsi-focus-primary .label{font-size:var(--swsi-ui-small,11.5px);font-weight:800;color:var(--pine);letter-spacing:1px;margin-bottom:3px}
      .swsi-focus-primary h2{font-family:'Noto Serif TC',serif;font-size:var(--swsi-ui-title,15px);line-height:1.4;margin:0;font-weight:900}
      .swsi-focus-primary p{font-size:var(--swsi-ui-small,11.5px);line-height:1.65;color:var(--ink-soft);margin:4px 0 0}
      .swsi-focus-actions{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:8px;margin-top:14px}
      .swsi-focus-actions button{min-height:48px;border-radius:12px;font-family:'Noto Sans TC',sans-serif;font-size:var(--swsi-ui-control,14px);font-weight:800;cursor:pointer}
      .swsi-focus-actions .go{border:none;background:var(--pine-deep);color:#fff}
      .swsi-focus-actions .choose{border:1px solid var(--line);background:var(--paper2);color:var(--pine)}

      .swsi-focus-custom{background:#fff;border:1px solid var(--line);border-radius:16px;padding:14px;margin:-2px 0 11px}
      .swsi-focus-custom .field-label{font-size:var(--swsi-ui-small,11.5px);font-weight:800;color:var(--ink-soft);margin:0 0 5px}
      .swsi-focus-custom .hint{font-size:var(--swsi-ui-small,11.5px);line-height:1.6;color:var(--ink-soft);margin:1px 0 9px}

      .swsi-study-card{width:100%;display:flex;align-items:center;justify-content:space-between;gap:12px;text-align:left;background:var(--paper2);border:1px solid var(--line);border-radius:16px;padding:16px 17px;margin:0 0 9px;cursor:pointer;color:var(--ink);font-family:inherit}
      .swsi-study-card.due{border-color:rgba(158,97,85,.45);background:var(--wrong-bg)}
      .swsi-study-card .copy{min-width:0}
      .swsi-study-card .title{font-family:'Noto Serif TC',serif;font-weight:900;font-size:var(--swsi-ui-title,15px);line-height:1.4}
      .swsi-study-card .sub{font-size:var(--swsi-ui-small,11.5px);color:var(--ink-soft);line-height:1.6;margin-top:3px}
      .swsi-study-card .aside{flex:0 0 auto;color:var(--ink-3);font-size:22px}
      .swsi-study-card .count{font-size:var(--swsi-ui-small,11.5px);font-weight:800;color:var(--wrong);background:#fff;border-radius:999px;padding:5px 9px;white-space:nowrap}

      .swsi-other-tools{margin:14px 0 0;border-top:1px solid var(--line);padding-top:4px}
      .swsi-other-tools summary{list-style:none;cursor:pointer;min-height:44px;display:flex;align-items:center;justify-content:center;font-size:var(--swsi-ui-small,11.5px);font-weight:800;color:var(--ink-soft)}
      .swsi-other-tools summary::-webkit-details-marker{display:none}
      .swsi-other-tools summary::after{content:'＋';margin-left:7px;color:var(--ink-3)}
      .swsi-other-tools[open] summary::after{content:'－'}
      .swsi-other-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding-bottom:4px}
      .swsi-other-grid button{min-height:45px;border:1px solid var(--line);border-radius:12px;background:transparent;color:var(--pine);font-family:'Noto Sans TC',sans-serif;font-size:var(--swsi-ui-control,14px);font-weight:800}

      .swsi-principle-note{margin:15px 4px 2px;text-align:center;font-size:var(--swsi-ui-small,11.5px);line-height:1.65;color:var(--ink-soft)}
      .swsi-principle-note b{color:var(--ink);font-weight:800}
      @media(max-width:370px){.swsi-focus-actions,.swsi-other-grid{grid-template-columns:1fr}.swsi-focus-hero{padding:21px 18px}}
    `;
    document.head.appendChild(style);
  }

  window.swsiStartNow=function(){
    try{
      homeQuizScope='smart';
      homeQuizCount=20;
      subjFilter='全部科目';
      homeQuizOpen=false;
    }catch(_e){}
    if(typeof startFocusedQuiz==='function') startFocusedQuiz();
  };

  function safeReviewSummary(){
    try{return reviewSummary();}catch(_e){return {dueCount:0,nextDueAt:null};}
  }

  renderHome=function(){
    installStyle();
    var rv=safeReviewSummary();
    var years=examYears();
    if(!homeQuizYear&&years.length) homeQuizYear=String(years[0]);
    homeQuizRound=homeQuizRound==='all'?'all':canonicalRound(homeQuizRound);
    var newest=years[0]||'';
    var specific=homeQuizScope==='specific';
    var subjOpts=['全部科目'].concat(SUBJECTS).map(function(x){return '<option value="'+swsiEsc(x)+'" '+(x===subjFilter?'selected':'')+'>'+swsiEsc(x)+'</option>';}).join('');
    var yearOpts=years.map(function(y){return '<option value="'+y+'" '+(String(y)===String(homeQuizYear)?'selected':'')+'>'+y+' 年</option>';}).join('');
    var reviewSub=rv.dueCount?('今天有 '+rv.dueCount+' 題該再看一次'):(rv.nextDueAt?('今天沒有到期題；下一批 '+reviewDueLabel(rv.nextDueAt)):'目前沒有待複習題');
    var scopeHint=homeQuizScope==='smart'?'最近 10 年為主，近 3 年與高頻考點優先。':homeQuizScope==='specific'?'只刷你指定的年度與考次。':homeQuizScope==='all'?'從完整歷史題庫抽題。':'只從較新的歷屆題目抽題。';
    var offlineNote='';
    try{
      if(window.SWSI_QB&&window.SWSI_QB.usingOffline) offlineNote='<div style="margin-bottom:10px;padding:9px 12px;border:1px solid var(--line);border-radius:11px;background:#fff;font-size:var(--swsi-ui-small);color:var(--ink-soft)">目前使用這台裝置已儲存的離線題庫。</div>';
    }catch(_e){}

    app.innerHTML=offlineNote+
      '<section class="swsi-focus-hero" aria-label="SWSI 平台理念">'+
        '<div class="kicker">SWSI · 免費社工師國考工具</div>'+
        '<h1>把時間留給讀書。</h1>'+
        '<p>不鎖題、不賣解答、不用點數。做題、訂正、複習，然後離開。</p>'+
        '<div class="swsi-promise-row"><span>核心功能免費</span><span>'+questionTotal()+' 題</span>'+(newest?'<span>'+newest+' 最新考次</span>':'')+'</div>'+
      '</section>'+

      '<section class="swsi-focus-primary">'+
        '<div class="label">現在開始</div><h2>刷 20 題選擇題</h2>'+
        '<p>直接用智慧推薦開始；想指定年度、考次或科目時再打開設定。</p>'+
        '<div class="swsi-focus-actions"><button class="go" onclick="swsiStartNow()">直接開始 20 題</button><button class="choose" onclick="toggleHomeQuiz()">'+(homeQuizOpen?'收起設定':'自己選範圍')+'</button></div>'+
      '</section>'+

      (homeQuizOpen?('<section class="swsi-focus-custom">'+
        '<div class="field-label">範圍</div><select class="subj" aria-label="刷題範圍" onchange="setHomeQuizScope(this.value)" style="margin-bottom:9px">'+
          '<option value="smart" '+(homeQuizScope==='smart'?'selected':'')+'>智慧推薦</option><option value="recent3" '+(homeQuizScope==='recent3'?'selected':'')+'>近 3 年</option><option value="recent5" '+(homeQuizScope==='recent5'?'selected':'')+'>近 5 年</option><option value="specific" '+(homeQuizScope==='specific'?'selected':'')+'>指定歷屆</option><option value="all" '+(homeQuizScope==='all'?'selected':'')+'>全部題庫</option></select>'+
        (specific?('<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><select class="subj" aria-label="考試年度" onchange="setHomeQuizYear(this.value)" style="margin-bottom:9px">'+yearOpts+'</select><select class="subj" aria-label="考試考次" onchange="setHomeQuizRound(this.value)" style="margin-bottom:9px"><option value="all" '+(homeQuizRound==='all'?'selected':'')+'>全部考次</option><option value="1" '+(homeQuizRound==='1'?'selected':'')+'>第一次</option><option value="2" '+(homeQuizRound==='2'?'selected':'')+'>第二次</option></select></div>'):'')+
        '<div class="field-label">科目</div><select class="subj" aria-label="科目" onchange="subjFilter=this.value;render()" style="margin-bottom:9px">'+subjOpts+'</select>'+
        '<div class="field-label">題數</div><select class="subj" aria-label="題數" onchange="setHomeQuizCount(this.value)" style="margin-bottom:7px"><option value="10" '+(homeQuizCount===10?'selected':'')+'>10 題</option><option value="20" '+(homeQuizCount===20?'selected':'')+'>20 題</option><option value="40" '+(homeQuizCount===40?'selected':'')+'>40 題</option></select>'+
        '<div class="hint">'+swsiEsc(scopeHint)+'</div><button class="btn" onclick="startFocusedQuiz()" style="margin-top:2px">開始這組題目</button></section>'):'')+

      '<button class="swsi-study-card '+(rv.dueCount?'due':'')+'" onclick="'+(rv.dueCount?'startDueReview()':"go('review')")+'"><span class="copy"><span class="title">今天該複習的</span><span class="sub">'+swsiEsc(reviewSub)+'</span></span>'+(rv.dueCount?'<span class="count">'+rv.dueCount+' 題</span>':'<span class="aside">›</span>')+'</button>'+
      '<button class="swsi-study-card" onclick="go(\'essay\')"><span class="copy"><span class="title">練一題申論</span><span class="sub">先自己寫，再看作答骨架與 AI 練習回饋；AI 不冒充官方閱卷。</span></span><span class="aside">›</span></button>'+

      '<details class="swsi-other-tools"><summary>其他工具，需要時再開</summary><div class="swsi-other-grid"><button onclick="MK.open()">計時模擬考</button><button onclick="go(\'topics\')">學習工具</button></div></details>'+
      '<div class="swsi-principle-note"><b>SWSI 不賣焦慮。</b> 核心備考功能保持免費，沒有答案鎖與點數門檻。</div>';

    if(typeof relabelTabs==='function') try{relabelTabs();}catch(_e){}
  };

  installStyle();
  try{if(typeof view!=='undefined'&&view==='home') render();}catch(_e){}
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
   - fixed bottom navigation could cover content
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

main{padding-bottom:calc(145px + env(safe-area-inset-bottom))!important;}
.wrap{padding-bottom:calc(120px + env(safe-area-inset-bottom))!important;}
body:has(#app .qcard) main{padding-bottom:30px!important;}
body:has(#app .qcard) .wrap{padding-bottom:28px!important;}

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
  main{padding-bottom:calc(138px + env(safe-area-inset-bottom))!important;}
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

/* SWSI Home Spacing + Essay Entry Fix 2026-08-26
   - Home must not stretch a short study dashboard into a page of empty space.
   - Essay entry should be resilient even if auto essays need one last async load.
*/
(function(){
  'use strict';

  var style=document.createElement('style');
  style.id='swsi-home-spacing-essay-entry-style';
  style.textContent=`
/* Home is intentionally short. Do not let main flex-grow create a huge blank slab
   between the study actions and the footer. */
body:has(#app .swsi-focus-hero) main{
  flex:0 0 auto!important;
  padding-bottom:calc(92px + env(safe-area-inset-bottom))!important;
}
body:has(#app .swsi-focus-hero) .wrap{
  padding-bottom:0!important;
}
body:has(#app .swsi-focus-hero) footer{
  margin-top:18px!important;
  padding-bottom:calc(18px + env(safe-area-inset-bottom))!important;
}

/* Review can use the normal compact safe area; long essay pages keep the larger
   mobile-reading safe area from the previous patch. */
body:has(#app .ux-page-head) main,
body:has(#app .section-h) main{
  padding-bottom:calc(100px + env(safe-area-inset-bottom));
}
`;
  document.head.appendChild(style);

  var opening=false;
  window.swsiOpenEssay=async function(){
    if(opening) return;
    opening=true;
    try{
      /* Normally essays are already loaded during init. This covers slow/cache edge
         cases instead of letting a tap appear to do nothing. */
      try{
        if(typeof ESSAYS!=='undefined' && (!Array.isArray(ESSAYS) || ESSAYS.length===0) && typeof loadAutoEssays==='function'){
          await loadAutoEssays();
        }
      }catch(loadErr){
        console.warn('SWSI essay reload failed',loadErr);
      }

      try{
        if(typeof essaySubj!=='undefined') essaySubj='全部科目';
        if(typeof essayCluster!=='undefined') essayCluster=null;
        if(typeof openEssay!=='undefined') openEssay=null;
        if(typeof guideOpen!=='undefined') guideOpen=null;
        if(typeof dissectOpen!=='undefined') dissectOpen=null;
      }catch(_stateErr){}

      if(typeof go==='function'){
        go('essay');
      }else{
        view='essay';
        window.scrollTo(0,0);
        render();
      }
    }catch(err){
      console.error('SWSI essay entry failed',err);
      if(typeof app!=='undefined' && app){
        app.innerHTML='<div class="empty"><div class="ico">✒</div><h3>申論題暫時沒有開啟</h3><p>頁面載入時遇到問題，請點下面按鈕再試一次。</p><button type="button" class="btn" onclick="swsiOpenEssay()" style="max-width:220px;margin:18px auto 0">重新開啟申論題</button></div>';
      }
    }finally{
      opening=false;
    }
  };

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
/* ===== SWSI P0 mobile + AI guardrails (2026-08-26) ===== */
(function(){
  'use strict';

  var style=document.createElement('style');
  style.textContent=`
    :root{--tabbar-safe-space:124px;}
    .tabbar{bottom:calc(env(safe-area-inset-bottom,0px) + 10px)!important;}
    .tabbar button{padding:8px 4px 10px!important;min-height:58px;}
    .tabbar .ico{font-size:17px!important;}
    html{scroll-padding-bottom:calc(var(--tabbar-safe-space) + env(safe-area-inset-bottom,0px));}
    body{padding-bottom:env(safe-area-inset-bottom,0px)!important;}
    .wrap{padding-bottom:calc(var(--tabbar-safe-space) + env(safe-area-inset-bottom,0px))!important;}
    button:disabled{pointer-events:none;}
    @media (max-width:420px){:root{--tabbar-safe-space:136px;}}
    html[data-fs="2"]{--tabbar-safe-space:148px;}
    @media (display-mode:standalone),(display-mode:fullscreen){
      .tabbar{bottom:calc(env(safe-area-inset-bottom,0px) + 14px)!important;}
      :root{--tabbar-safe-space:132px;}
      html[data-fs="2"]{--tabbar-safe-space:154px;}
    }
  `;
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

  window.aiFeedbackHTML=function(id){
    return `<div style="margin-top:14px;border-top:1px dashed var(--line);padding-top:12px">
      <div class="aihelp" style="color:var(--ink-soft);margin-bottom:9px;background:#FBF8EF;border:1px solid var(--line);border-radius:8px;padding:9px 12px">🔒 作答文字／照片會送至外部 AI 服務處理；請勿輸入或上傳可識別真實個案、姓名、身分證字號、機構內部文件等資料。照片會先在本機縮小並轉成 JPEG，再送出。</div>
      <div class="aihelp" style="color:var(--ink-soft);margin-bottom:9px;background:#FBF8EF;border:1px solid var(--line);border-radius:8px;padding:9px 12px">💡 能打字的同學建議用「打字批改」——較快，也比照片省 AI 額度。平台提供的是申論練習回饋，並非考選部官方評分。</div>
      <button id="aitype_${id}" class="fbtn" style="width:100%;padding:11px;font-size:14px;color:var(--pine);font-weight:600" onclick="runAIFeedback('${id}')">🤖 我用打字的 · 請 AI 批改上面的作答</button>
      <input type="file" id="photo_${id}" accept="image/*" multiple style="display:none" onchange="gradePhoto('${id}',this)">
      <button id="aiphoto_${id}" class="fbtn" style="width:100%;padding:11px;font-size:14px;color:var(--pine);font-weight:600;margin-top:8px" onclick="document.getElementById('photo_${id}').click()">📷 我用手寫的 · 拍照上傳給 AI 批改</button>
      <div class="aihelp" style="color:var(--ink-soft);margin-top:7px">手寫可一次選 1–3 張。光線充足、字跡清楚、整頁入鏡會讀得更準；AI 會先顯示「我讀到的作答」，讀錯時請重拍，不要把錯誤辨識當成你的原文。</div>
      <div id="airesult_${id}"></div>
    </div>`;
  };

  window.swsiSetAIBusy=function(id,busy,mode){
    var t=document.getElementById('aitype_'+id),p=document.getElementById('aiphoto_'+id),f=document.getElementById('photo_'+id);
    if(t){t.disabled=!!busy;t.style.opacity=busy?'.55':'';t.style.cursor=busy?'not-allowed':'';t.textContent=(busy&&mode==='text')?'⏳ AI 批改中…':'🤖 我用打字的 · 請 AI 批改上面的作答';}
    if(p){p.disabled=!!busy;p.style.opacity=busy?'.55':'';p.style.cursor=busy?'not-allowed':'';p.textContent=(busy&&mode==='photo')?'⏳ 照片處理／批改中…':'📷 我用手寫的 · 拍照上傳給 AI 批改';}
    if(f)f.disabled=!!busy;
  };

  window.swsiAICacheKey=function(id){return 'essay_ai_cache_'+id;};
  window.swsiGetAICache=function(id,answer){
    try{var x=JSON.parse(localStorage.getItem(window.swsiAICacheKey(id))||'null');return x&&x.answer===answer&&x.feedback?x:null;}catch(e){return null;}
  };
  window.swsiSetAICache=function(id,answer,feedback){
    try{localStorage.setItem(window.swsiAICacheKey(id),JSON.stringify({answer:answer,feedback:feedback,at:Date.now()}));}catch(e){}
  };
  window.swsiFetchWithTimeout=async function(url,options,ms){
    var ctrl=new AbortController(),timer=setTimeout(function(){ctrl.abort();},ms);
    try{return await fetch(url,Object.assign({},options,{signal:ctrl.signal}));}
    finally{clearTimeout(timer);}
  };

  window.runAIFeedback=async function(id){
    var out=document.getElementById('airesult_'+id); if(!out)return;
    if(!AI_PROXY_URL||AI_PROXY_URL.indexOf('http')!==0){out.innerHTML='<div style="margin-top:10px;font-size:13px;color:var(--ink-soft);line-height:1.7">AI 批改尚未啟用（管理員還沒設定中間人網址）。</div>';return;}
    var ta=document.getElementById('ta_'+id),ans=(ta?ta.value:'').trim(),effective=window.effectiveEssayLength(ans);
    if(effective<30){out.innerHTML=`<div style="margin-top:10px;font-size:13px;color:var(--wrong);line-height:1.7">目前有效作答只有 ${effective} 字（格式編號、空白與標點不計）。請先寫至少 30 字的實際內容，再交給 AI 回饋；只有「一、（一）1、a. (i)」這類架構不會送出。</div>`;return;}

    var cached=window.swsiGetAICache(id,ans);
    if(cached){out.innerHTML=`<div style="margin-top:12px;font-size:11px;color:var(--ink-soft);margin-bottom:5px">✓ 這份作答內容沒有變動，顯示已儲存的上次 AI 回饋。</div><div style="background:#fff;border:1px solid var(--line);border-left:3px solid var(--pine);border-radius:10px;padding:14px;font-size:14px;line-height:1.8;color:var(--ink);white-space:pre-wrap">${esc(cached.feedback)}</div><div style="font-size:11px;color:var(--ink-soft);margin-top:6px;line-height:1.6">⚠ AI 練習回饋僅供參考、非官方評分；正式標準以老師與考選部為準。</div>`;return;}

    var e=(window.ESSAYS||[]).find(function(x){return x.id===id;})||{},g=(window.ESSAY_GUIDES||{})[id]||{};
    var skel='考點：'+(g.kao||'（無）')+'\n破題心法：'+(g.dati||'（無）')+'\n必踩大標：'+(g.biaoti||[]).join('；')+'\n搶分關鍵字：'+(g.kw||[]).join('、');
    var sys=`【最重要規則：整份回饋務必用「繁體中文」書寫，禁止使用英文句子或英文段落。】
你是台灣「社工師」國家考試的申論練習教練。會提供題目、這題的「校過骨架」（已人工核對的正確考點／破題／必踩大標／關鍵字），以及學生作答。請依骨架與你的社工專業知識，給「練習回饋」。

嚴格規則：
- 這是練習回饋、不是官方評分：不要給分數、不要自稱評分標準或官方細則。
- 不要自行編造法條條號、數字或學者；骨架沒有提到的就不要硬掰。
- 若學生作答是空白、亂打、與題目無關或明顯敷衍，直接只回這一句：「這份作答還無法給有意義的回饋，先用拆題五步把架構寫出來再來。」其他都不要寫。
- 繁體中文，鼓勵但誠實，分點寫，總長約 300 字內。

回饋結構：
一、方向與架構：有沒有抓到這題真正的核心考點？大標對不對？
二、可以補強：漏了哪些『必踩大標』或關鍵概念、可補哪個理論／法源（只從骨架與正確社工知識出發）。
三、一句鼓勵。`;
    var user='【題目】'+(e.q||'')+'（'+(e.points||20)+'分）\n【校過骨架】\n'+skel+'\n【學生作答】\n'+ans;

    window.swsiSetAIBusy(id,true,'text');
    out.innerHTML='<div style="margin-top:12px;font-size:14px;color:var(--ink-soft)">🤖 AI 批改中…你的作答已保存在這台裝置，可以安心等待。</div>';
    try{
      var r=await window.swsiFetchWithTimeout(AI_PROXY_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:GROQ_MODEL,reasoning_effort:'none',temperature:0.5,max_tokens:1200,messages:[{role:'user',content:sys+'\n\n'+user}]})},45000);
      if(!r.ok){
        var msg='AI 批改暫時無法使用，答案仍已保存在這台裝置，稍後再試即可。';
        if(r.status===400)msg='這次送出的作答格式無法處理，請稍微修改內容後再試。';
        else if(r.status===413)msg='這份作答資料太大，請縮短後再試。';
        else if(r.status===429)msg='目前 AI 使用量較高，請等一分鐘左右再試；你的答案不會消失。';
        else if(r.status===401||r.status===403)msg='AI 服務目前設定異常，請稍後再試或回報管理員。';
        else if(r.status>=500)msg='AI 服務目前忙碌或暫時異常，請稍後再試；你的答案已保存。';
        out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">'+msg+'</div>';return;
      }
      var data;try{data=await r.json();}catch(e2){throw new Error('bad_json');}
      var txt=((data&&data.choices&&data.choices[0]&&data.choices[0].message&&data.choices[0].message.content)||'').replace(/<think>[\s\S]*?<\/think>/gi,'').trim();
      if(!txt){out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong)">AI 沒有回傳可讀內容。你的答案已保存，稍後再試即可。</div>';return;}
      window.swsiSetAICache(id,ans,txt);
      out.innerHTML=`<div style="margin-top:12px;background:#fff;border:1px solid var(--line);border-left:3px solid var(--pine);border-radius:10px;padding:14px;font-size:14px;line-height:1.8;color:var(--ink);white-space:pre-wrap">${esc(txt)}</div><div style="font-size:11px;color:var(--ink-soft);margin-top:6px;line-height:1.6">⚠ AI 練習回饋僅供參考、非官方評分；正式標準以老師與考選部為準。修改作答後可再次送出取得新回饋。</div>`;
    }catch(err){
      var timeout=err&&err.name==='AbortError';
      out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">'+(timeout?'AI 回應時間過久，這次已自動停止。':'連線失敗，可能是網路暫時不穩。')+' 你的答案仍保存在這台裝置，稍後再試即可。</div>';
    }finally{window.swsiSetAIBusy(id,false,'text');}
  };

  window.gradePhoto=async function(id,inputEl){
    var out=document.getElementById('airesult_'+id); if(!out)return;
    if(!AI_PROXY_URL||AI_PROXY_URL.indexOf('http')!==0){out.innerHTML='<div style="margin-top:10px;font-size:13px;color:var(--ink-soft);line-height:1.7">AI 批改尚未啟用（管理員還沒設定中間人網址）。</div>';return;}
    var files=(inputEl&&inputEl.files)?Array.from(inputEl.files):[];
    if(!files.length)return;
    if(files.length>3){out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">一次最多 3 張照片，請重新選擇 1–3 張。</div>';if(inputEl)inputEl.value='';return;}
    if(files.some(function(f){return !String(f.type||'').startsWith('image/');})){out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">請只選擇照片檔案。</div>';if(inputEl)inputEl.value='';return;}

    window.swsiSetAIBusy(id,true,'photo');
    out.innerHTML='<div style="margin-top:12px;font-size:14px;color:var(--ink-soft)">📷 照片處理中…（'+files.length+' 張）</div>';
    try{
      var imgs=[];for(var i=0;i<files.length;i++)imgs.push(await shrinkImage(files[i],1200,0.78));
      if(inputEl)inputEl.value='';
      var approxBytes=imgs.reduce(function(n,u){return n+Math.ceil((u.length-(u.indexOf(',')+1))*3/4);},0);
      if(approxBytes>3200000){out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">照片壓縮後仍太大。請裁掉桌面／背景，只保留作答紙，再重新拍攝上傳。</div>';return;}

      var e=(window.ESSAYS||[]).find(function(x){return x.id===id;})||{},g=(window.ESSAY_GUIDES||{})[id]||{};
      var skel='考點：'+(g.kao||'（無）')+'\n破題心法：'+(g.dati||'（無）')+'\n必踩大標：'+(g.biaoti||[]).join('；')+'\n搶分關鍵字：'+(g.kw||[]).join('、');
      var sys=`【最重要規則：整份回覆務必用「繁體中文」書寫，禁止使用英文句子或英文段落。】
你是台灣「社工師」國家考試的申論練習教練。學生上傳了一張或多張「手寫作答」的照片（可能是同一份作答的正反面或多頁，請依順序合起來一起讀）。請依下列步驟回覆：

第一步：辨識所有照片中的手寫文字，依頁面順序盡量逐字呈現在【我讀到的作答】底下；看不清楚的字用「◌」代替，不要自己補字或改寫成別的意思。
第二步：若照片模糊、空白、不是申論作答、或幾乎讀不出字，就「只」回這一句：「這張照片我讀不太出來，請在光線充足的地方、把整頁字跡清楚地重拍一張。」其他都不要寫。
第三步：依提供的「校過骨架」（已人工核對的正確考點／破題／必踩大標／關鍵字）與你的社工專業，給練習回饋。

嚴格規則：
- 這是練習回饋、不是官方評分：不要給分數、不要自稱評分標準或官方細則。
- 不要自行編造法條條號、數字或學者；骨架沒有提到的就不要硬掰。
- 繁體中文，鼓勵但誠實，分點寫。

輸出格式（務必照這個格式）：
【我讀到的作答】
（把辨識到的字逐字寫出來）

【練習回饋】
一、方向與架構：有沒有抓到核心考點？大標對不對？
二、可以補強：漏了哪些必踩大標或關鍵概念、可補哪個理論／法源（只從骨架與正確社工知識出發）。
三、鼓勵：一句話。`;
      var userText='【題目】'+(e.q||'')+'（'+(e.points||20)+'分）\n【校過骨架】\n'+skel+'\n\n下面是學生手寫作答的照片（可能多張，是同一份作答的正反面或多頁），請依上面步驟辨識並批改。';
      var content=[{type:'text',text:sys+'\n\n'+userText}];imgs.forEach(function(u){content.push({type:'image_url',image_url:{url:u}});});
      out.innerHTML='<div style="margin-top:12px;font-size:14px;color:var(--ink-soft)">🤖 AI 正在讀 '+imgs.length+' 張照片並批改…照片會先在本機縮小後才送出。</div>';

      var r=await window.swsiFetchWithTimeout(AI_PROXY_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:GROQ_MODEL,reasoning_effort:'none',temperature:0.4,max_tokens:1100,messages:[{role:'user',content:content}]})},60000);
      if(!r.ok){
        var msg='AI 批改暫時無法使用，請稍後再試。';
        if(r.status===400)msg='這次照片資料無法處理，請重新拍攝後再試。';
        else if(r.status===413)msg='照片仍然太大，請裁切只留下作答內容後再試。';
        else if(r.status===429)msg='目前 AI 使用量較高，請等一分鐘左右再試。';
        else if(r.status===401||r.status===403)msg='AI 服務目前設定異常，請稍後再試或回報管理員。';
        else if(r.status>=500)msg='AI 服務目前忙碌或暫時異常，請稍後再試。';
        out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">'+msg+'</div>';return;
      }
      var data;try{data=await r.json();}catch(e2){throw new Error('bad_json');}
      var txt=((data&&data.choices&&data.choices[0]&&data.choices[0].message&&data.choices[0].message.content)||'').replace(/<think>[\s\S]*?<\/think>/gi,'').trim();
      if(!txt){out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong)">AI 沒有回傳可讀內容，請稍後重拍再試。</div>';return;}
      out.innerHTML=`<div style="margin-top:12px;background:#fff;border:1px solid var(--line);border-left:3px solid var(--pine);border-radius:10px;padding:14px;font-size:14px;line-height:1.8;color:var(--ink);white-space:pre-wrap">${esc(txt)}</div><div style="font-size:11px;color:var(--ink-soft);margin-top:6px;line-height:1.6">⚠ AI 練習回饋僅供參考、非官方評分；手寫辨識可能有誤，請先核對「我讀到的作答」。正式標準以老師與考選部為準。</div>`;
    }catch(err){
      if(inputEl)inputEl.value='';
      var timeout=err&&err.name==='AbortError',em=String(err&&err.message||''),loadFail=em.indexOf('load fail')>=0||em.indexOf('no size')>=0;
      out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">'+(loadFail?'有照片讀取失敗（這種格式可能不支援），請改用相機重拍。':timeout?'AI 讀取照片時間過久，這次已自動停止，請稍後再試。':'連線失敗或照片處理失敗，請檢查網路並重新拍攝後再試。')+'</div>';
    }finally{window.swsiSetAIBusy(id,false,'photo');}
  };
})();
/* ===== SWSI P0 mobile + AI guardrails END ===== *//* ===== SWSI stable anonymous AI client id (2026-08-26) ===== */
(function(){
  'use strict';
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

  // 99_p0_mobile_ai_guardrails.part 會先建立這個 helper；這裡最後覆寫，
  // 所有公開 AI request 都自動帶匿名 client id，後端可穩定套每日配額。
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
/* ===== SWSI stable anonymous AI client id END ===== */
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

  window.swsiOpenEssay=function(){
    try{ if(typeof view!=='undefined') view='essay'; }catch(_e){ window.view='essay'; }
    markEssayTab();
    try{ window.scrollTo(0,0); }catch(_e){}
    renderEssaySafely();
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

  function setNavButton(id,kind,label){
    var el=document.getElementById(id); if(!el) return;
    /* Do not compare serialized innerHTML. Browsers normalize SVG markup, so that
       comparison can stay unequal forever and make MutationObserver trigger itself. */
    var currentLabel=el.querySelector('.swsi-nav-label');
    var currentIcon=el.querySelector('.swsi-nav-ico');
    if(!currentLabel || !currentIcon || currentLabel.textContent!==label){
      el.innerHTML=icon(kind)+'<span class="swsi-nav-label">'+label+'</span>';
    }
    if(el.getAttribute('aria-label')!==label) el.setAttribute('aria-label',label);
  }

  function polishNav(){
    setNavButton('t-home','home','首頁');
    setNavButton('t-review','review','複習');
    setNavButton('t-essay','essay','申論');
  }

  function resetEssayState(){
    try{ if(typeof essaySubj!=='undefined') essaySubj='全部科目'; }catch(_e){}
    try{ if(typeof essayCluster!=='undefined') essayCluster=null; }catch(_e){}
    try{ if(typeof openEssay!=='undefined') openEssay=null; }catch(_e){}
    try{ if(typeof guideOpen!=='undefined') guideOpen=null; }catch(_e){}
    try{ if(typeof dissectOpen!=='undefined') dissectOpen=null; }catch(_e){}
  }

  window.swsiOpenEssay=function(){
    resetEssayState();
    try{ view='essay'; }catch(_e){ window.view='essay'; }
    try{ window.scrollTo(0,0); }catch(_e){}
    try{
      if(typeof renderEssay==='function') renderEssay();
      else if(typeof render==='function') render();
    }catch(err){
      console.error('[SWSI] essay library failed',err);
      if(typeof app!=='undefined'&&app) app.innerHTML='<div class="empty"><div class="ico">✒</div><h3>申論題暫時無法開啟</h3><p>你的作答草稿仍保存在這台裝置。請重新整理後再試。</p></div>';
    }
  };
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

/* SWSI Learning Loop V1 2026-08-26
   Wrong answers -> self reflection -> spaced review -> useful progress.
   This layer NEVER edits official exam question text or official answer data.
*/
(function(){
  'use strict';

  var CAUSE_KEY='swsi_wrong_cause_v1';
  var CAUSES=['概念不熟','看錯題目','兩個選項猶豫','法規／數字記錯','其實是猜的'];
  var DAY=24*60*60*1000;

  function H(v){
    return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});
  }
  function loadCauses(){
    try{var x=JSON.parse(localStorage.getItem(CAUSE_KEY)||'{}');return x&&typeof x==='object'?x:{};}catch(_e){return {};}
  }
  function saveCauses(x){try{localStorage.setItem(CAUSE_KEY,JSON.stringify(x));}catch(_e){}}
  function draftCount(){
    var n=0;
    try{for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);if(k&&k.indexOf('essay_draft_')===0&&(localStorage.getItem(k)||'').trim())n++;}}catch(_e){}
    return n;
  }
  function questionCorrect(item,picked){
    try{if(typeof isCorrectAnswer==='function')return !!isCorrectAnswer(item,picked);}catch(_e){}
    try{if(typeof ansCorrect==='function')return !!ansCorrect(picked,item.answer);}catch(_e){}
    return String(picked||'')===String(item&&item.answer||'');
  }

  window.swsiSetWrongCause=function(id,cause){
    var m=loadCauses();
    if(m[id]&&m[id].cause===cause) delete m[id];
    else m[id]={cause:cause,ts:Date.now()};
    saveCauses(m);
    decorateWrongCause();
  };

  function causeButton(id,cause,current){
    var on=current===cause;
    return '<button type="button" class="swsi-cause-chip'+(on?' on':'')+'" onclick="swsiSetWrongCause(\''+H(id)+'\',\''+H(cause)+'\')">'+H(cause)+(on?' ✓':'')+'</button>';
  }

  function decorateWrongCause(){
    var exp=document.querySelector('#app .qcard .exp');
    if(!exp)return;
    var item=null,picked=null,isAnswered=false;
    try{item=queue&&queue[idx];picked=selected;isAnswered=!!answered;}catch(_e){}
    if(!item||!isAnswered||questionCorrect(item,picked)){
      var old=exp.querySelector('.swsi-self-cause'); if(old)old.remove(); return;
    }
    var box=exp.querySelector('.swsi-self-cause');
    if(!box){
      box=document.createElement('section');
      box.className='swsi-self-cause';
      var next=exp.querySelector(':scope > .btn');
      if(next) exp.insertBefore(box,next); else exp.appendChild(box);
    }
    var cur=(loadCauses()[item.id]||{}).cause||'';
    box.innerHTML='<div class="swsi-cause-title">這題你為什麼會錯？</div>'+
      '<div class="swsi-cause-help">點一下就好，只存在這台裝置。之後錯題本會依你的原因整理。</div>'+
      '<div class="swsi-cause-row">'+CAUSES.map(function(c){return causeButton(item.id,c,cur);}).join('')+'</div>';
  }

  function latestWrongQuestionIds(){
    try{return reviewSummary().activeIds||[];}catch(_e){return [];}
  }
  function setFromIds(ids){var s=new Set(ids||[]);startQuiz(function(q){return s.has(q.id);},0);}
  window.swsiPracticeReviewSet=function(i){
    var sets=window._swsiReviewSets||[]; if(!sets[i])return; setFromIds(sets[i].ids);
  };
  window.swsiPracticeSubject=function(subj,n){
    startQuiz(function(q){return q.subject===subj;},n||20);
  };
  window.swsiPracticeTopic=function(topic,n){
    startQuiz(function(q){return (q.topic||q.major||'')===topic;},n||15);
  };
  window.swsiStartRecommended20=function(){startQuiz(function(){return true;},20);};

  function questionMap(ids){
    return (ids||[]).map(function(id){try{return ALL.find(function(q){return q.id===id;});}catch(_e){return null;}}).filter(Boolean);
  }
  function groupPush(obj,key,q){key=key||'未分類';(obj[key]=obj[key]||[]).push(q);}

  renderReview=function(){
    var rv=reviewSummary(), ids=rv.activeIds||[], wrongQs=questionMap(ids), causes=loadCauses();
    if(!ids.length&&!rv.dueCount&&!rv.nextDueAt){
      app.innerHTML='<div class="empty"><div class="ico">✓</div><h3>'+(rv.masteredCount?'目前沒有待複習題':'還沒有錯題')+'</h3><p>'+(rv.masteredCount?('已經有 '+rv.masteredCount+' 題完成錯題學習與長期確認。<br>之後再答錯仍會重新排入複習。'):'開始刷題後，答錯題會自動進入間隔複習。<br>你也可以自己標記「為什麼會錯」。')+'</p><button class="btn" style="max-width:200px;margin:22px auto 0" onclick="go(\'home\')">開始刷題</button><button class="btn ghost" style="max-width:200px;margin:10px auto 0" onclick="go(\'progress\')">看看我的進度</button></div>';
      return;
    }

    var byCause={},unmarked=[],byTopic={};
    wrongQs.forEach(function(q){
      var c=causes[q.id]&&causes[q.id].cause;
      if(c)groupPush(byCause,c,q);else unmarked.push(q);
      groupPush(byTopic,q.topic||q.major||'未分類',q);
    });
    var causeGroups=Object.entries(byCause).sort(function(a,b){return b[1].length-a[1].length;});
    var topicGroups=Object.entries(byTopic).sort(function(a,b){return b[1].length-a[1].length;}).slice(0,5);
    window._swsiReviewSets=[{label:'全部未熟練錯題',ids:ids.slice()}];
    causeGroups.forEach(function(x){window._swsiReviewSets.push({label:x[0],ids:x[1].map(function(q){return q.id;})});});
    var causeBase=1;
    topicGroups.forEach(function(x){window._swsiReviewSets.push({label:x[0],ids:x[1].map(function(q){return q.id;})});});
    var topicBase=1+causeGroups.length;

    var h='<div class="section-h">錯題複習</div><div class="section-s">先處理今天到期的，再看看自己到底為什麼常錯。沒有排行榜，也不用追連勝。</div>';
    h+='<div class="statrow swsi-review-stats"><div class="stat"><div class="v" style="color:var(--wrong)">'+rv.dueCount+'</div><div class="k">今天到期</div></div><div class="stat"><div class="v">'+rv.activeCount+'</div><div class="k">還沒熟</div></div><div class="stat"><div class="v" style="color:var(--correct)">'+rv.masteredCount+'</div><div class="k">已掌握</div></div></div>';
    if(rv.dueCount) h+='<button class="btn" onclick="startDueReview()">先複習今天這 '+rv.dueCount+' 題</button>';
    else if(rv.nextDueAt) h+='<div class="swsi-calm-note">✓ 今天沒有到期題，下一批 '+H(reviewDueLabel(rv.nextDueAt))+'。</div>';
    if(wrongQs.length) h+='<button class="btn ghost" onclick="swsiPracticeReviewSet(0)" style="margin-top:9px">重練全部未熟練錯題（'+wrongQs.length+' 題）</button>';

    h+='<section class="swsi-learning-section"><div class="swsi-learning-h">你自己標記的錯因</div>';
    if(causeGroups.length){
      causeGroups.forEach(function(x,i){h+='<button class="swsi-learning-row" onclick="swsiPracticeReviewSet('+(causeBase+i)+')"><span><b>'+H(x[0])+'</b><small>'+x[1].length+' 題</small></span><span>›</span></button>';});
      if(unmarked.length) h+='<div class="swsi-learning-muted">另外有 '+unmarked.length+' 題還沒標記原因。下次答錯時可以順手點一下。</div>';
    }else{
      h+='<div class="swsi-learning-muted">你還沒標記過錯因。下一次答錯後，解析下方會出現「概念不熟／看錯題目／兩個選項猶豫…」讓你點一下。</div>';
    }
    h+='</section>';

    if(topicGroups.length){
      h+='<section class="swsi-learning-section"><div class="swsi-learning-h">平台看到的弱點考點</div><div class="swsi-learning-muted" style="margin-bottom:8px">這是依你目前未熟練的題目分類，不代表平台知道你本人為什麼答錯。</div>';
      topicGroups.forEach(function(x,i){h+='<button class="swsi-learning-row" onclick="swsiPracticeReviewSet('+(topicBase+i)+')"><span><b>'+H(x[0])+'</b><small>目前 '+x[1].length+' 題未熟練</small></span><span>›</span></button>';});
      h+='</section>';
    }
    h+='<button class="btn ghost" style="margin-top:18px" onclick="go(\'progress\')">查看完整學習進度</button>';
    app.innerHTML=h;
  };

  function progressData(){
    var h=loadHist(),now=Date.now(),recent=h.filter(function(x){return Number(x.ts||0)>=now-7*DAY;});
    var bySubj={},wrongTopic={},byCause={},unique=new Set();
    h.forEach(function(x){
      if(x&&x.id)unique.add(x.id);
      var s=x.subject||'未分類';if(!bySubj[s])bySubj[s]={t:0,c:0};bySubj[s].t++;if(x.correct)bySubj[s].c++;
      if(!x.correct){var q=null;try{q=ALL.find(function(z){return z.id===x.id;});}catch(_e){};var t=(q&&(q.topic||q.major))||x.major||'未分類';wrongTopic[t]=(wrongTopic[t]||0)+1;}
    });
    var cm=loadCauses();Object.keys(cm).forEach(function(id){var c=cm[id]&&cm[id].cause;if(c)byCause[c]=(byCause[c]||0)+1;});
    return {hist:h,recent:recent,bySubj:bySubj,wrongTopic:wrongTopic,byCause:byCause,unique:unique};
  }
  function pct(c,t){return t?Math.round(c/t*100):0;}

  renderProgress=function(){
    var p=progressData(), total=p.hist.length, rv=reviewSummary(), essays=draftCount();
    if(!total){
      app.innerHTML='<div class="empty"><div class="ico">◴</div><h3>還沒有刷題紀錄</h3><p>開始刷題後，這裡會告訴你哪一科比較弱、最近有沒有進步，以及下一步建議做什麼。</p><button class="btn" style="max-width:200px;margin:22px auto 0" onclick="swsiStartRecommended20()">先刷 20 題</button>'+(essays?'<div style="margin-top:14px;color:var(--ink-soft);font-size:13px">這台裝置目前有 '+essays+' 題申論作答草稿。</div>':'')+'</div>';
      return;
    }
    var correct=p.hist.filter(function(x){return x.correct;}).length, rate=pct(correct,total);
    var rc=p.recent.filter(function(x){return x.correct;}).length, rr=p.recent.length?pct(rc,p.recent.length):null;
    var allCount=0;try{allCount=ALL.length||0;}catch(_e){}
    var coverage=allCount?Math.min(100,Math.round(p.unique.size/allCount*100)):0;
    var subjects=Object.entries(p.bySubj).map(function(x){return {name:x[0],t:x[1].t,c:x[1].c,r:pct(x[1].c,x[1].t)};});
    subjects.sort(function(a,b){return a.r-b.r||b.t-a.t;});
    var weak=subjects.filter(function(x){return x.t>=5;})[0]||subjects[0];
    var topTopics=Object.entries(p.wrongTopic).sort(function(a,b){return b[1]-a[1];}).slice(0,5);
    var causeRows=Object.entries(p.byCause).sort(function(a,b){return b[1]-a[1];});

    var action='';
    if(rv.dueCount){action='<div class="swsi-next-copy"><b>先把今天到期的錯題處理掉。</b><span>間隔複習比再刷一堆新題更值得。</span></div><button class="btn" onclick="startDueReview()">複習 '+rv.dueCount+' 題</button>';}
    else if(weak){action='<div class="swsi-next-copy"><b>目前最值得補：'+H(weak.name)+'</b><span>你在這科目前 '+weak.r+'%（'+weak.c+'/'+weak.t+'）。先用 20 題再確認一次。</span></div><button class="btn" onclick="swsiPracticeSubject(\''+H(weak.name)+'\',20)">練 '+H(weak.name)+' 20 題</button>';}
    else{action='<div class="swsi-next-copy"><b>繼續累積一點資料。</b><span>再刷 20 題後，弱點判斷會更有參考價值。</span></div><button class="btn" onclick="swsiStartRecommended20()">繼續刷 20 題</button>';}

    var subjHTML=subjects.map(function(s){
      var col=s.r>=70?'var(--correct)':s.r>=50?'var(--gold)':'var(--wrong)';
      return '<button class="swsi-progress-subject" onclick="swsiPracticeSubject(\''+H(s.name)+'\',20)"><div class="top"><b>'+H(s.name)+'</b><span>'+s.r+'%　('+s.c+'/'+s.t+')</span></div><div class="accbar"><i style="width:'+s.r+'%;background:'+col+'"></i></div><small>點一下練這科 20 題</small></button>';
    }).join('');

    var h='<div class="section-h">我的學習進度</div><div class="section-s">只看能幫你決定下一步的數據。重複作答會算進正確率；「題庫覆蓋」則同一題只算一次。</div>';
    h+='<section class="swsi-progress-hero"><div><small>總正確率</small><strong>'+rate+'%</strong></div><div class="swsi-progress-mini"><span><b>'+total+'</b>作答次數</span><span><b>'+p.unique.size+'</b>不同題目</span><span><b>'+coverage+'%</b>題庫覆蓋</span></div></section>';
    h+='<div class="swsi-progress-strip"><div><b>'+(rr==null?'—':rr+'%')+'</b><span>最近 7 天'+(p.recent.length?' · '+p.recent.length+' 題':' · 尚無紀錄')+'</span></div><div><b>'+rv.activeCount+'</b><span>未熟練錯題</span></div><div><b>'+essays+'</b><span>申論草稿</span></div></div>';
    h+='<section class="swsi-next-card"><div class="swsi-learning-h">今天下一步</div>'+action+'</section>';
    h+='<section class="swsi-learning-section"><div class="swsi-learning-h">各科狀況</div>'+subjHTML+'</section>';
    if(topTopics.length)h+='<section class="swsi-learning-section"><div class="swsi-learning-h">最常答錯的考點</div>'+topTopics.map(function(x){return '<button class="swsi-learning-row" onclick="swsiPracticeTopic(\''+H(x[0])+'\',15)"><span><b>'+H(x[0])+'</b><small>累計錯 '+x[1]+' 次</small></span><span>›</span></button>';}).join('')+'</section>';
    if(causeRows.length)h+='<section class="swsi-learning-section"><div class="swsi-learning-h">你自己標記的錯因</div>'+causeRows.map(function(x){return '<div class="swsi-cause-stat"><span>'+H(x[0])+'</span><b>'+x[1]+' 題</b></div>';}).join('')+'</section>';
    h+='<div class="swsi-progress-foot"><button class="btn ghost" onclick="go(\'review\')">回錯題複習</button><button class="btn ghost" onclick="exportDrafts()">備份申論草稿</button><button class="swsi-danger-link" onclick="if(confirm(\'清除所有刷題、間隔複習與自訂錯因紀錄？無法復原。\')){localStorage.removeItem(LS_KEY);localStorage.removeItem(REVIEW_KEY);localStorage.removeItem(\''+CAUSE_KEY+'\');render();}">清除學習紀錄</button></div>';
    app.innerHTML=h;
  };

  /* Progress is intentionally not another persistent bottom tab. Put it quietly in Home tools. */
  try{
    var oldHome=renderHome;
    renderHome=function(){
      oldHome();
      var grid=document.querySelector('#app .swsi-other-grid');
      if(grid&&!grid.querySelector('.swsi-progress-entry')){
        var b=document.createElement('button');b.className='swsi-progress-entry';b.textContent='我的學習進度';b.onclick=function(){go('progress');};grid.appendChild(b);
      }
    };
  }catch(_e){}

  if(!document.getElementById('swsi-learning-loop-style')){
    var st=document.createElement('style');st.id='swsi-learning-loop-style';st.textContent=`
      .swsi-self-cause{margin:15px 0 12px;padding:13px;border:1px solid var(--line);border-radius:13px;background:#F8FAF9}
      .swsi-cause-title{font-size:var(--fs-b);font-weight:800;color:var(--ink);margin-bottom:3px}.swsi-cause-help{font-size:var(--fs-s);line-height:1.6;color:var(--ink-soft);margin-bottom:9px}
      .swsi-cause-row{display:flex;flex-wrap:wrap;gap:6px}.swsi-cause-chip{border:1px solid var(--line);background:#fff;color:var(--ink-soft);border-radius:999px;padding:7px 10px;font-family:inherit;font-size:var(--fs-s);font-weight:700;cursor:pointer}.swsi-cause-chip.on{border-color:var(--pine);background:var(--correct-bg);color:var(--pine-deep)}
      .swsi-review-stats{margin:15px 0 16px}.swsi-calm-note{margin:10px 0 0;padding:11px 13px;border:1px solid var(--line);border-radius:11px;background:#fff;color:var(--ink-soft);font-size:13px;line-height:1.6}
      .swsi-learning-section{margin-top:20px}.swsi-learning-h{font-size:14px;font-weight:900;color:var(--ink);margin:0 0 9px}.swsi-learning-muted{font-size:12px;line-height:1.65;color:var(--ink-soft);padding:2px 2px 8px}
      .swsi-learning-row{width:100%;display:flex;align-items:center;justify-content:space-between;gap:10px;text-align:left;border:1px solid var(--line);background:#fff;border-radius:12px;padding:11px 13px;margin-bottom:7px;color:var(--ink);font-family:inherit;cursor:pointer}.swsi-learning-row b{display:block;font-size:13.5px;line-height:1.45}.swsi-learning-row small{display:block;font-size:11.5px;color:var(--ink-soft);margin-top:2px}
      .swsi-progress-hero{margin-top:13px;border:1px solid var(--line);border-radius:17px;background:#fff;padding:16px}.swsi-progress-hero>div:first-child small{display:block;color:var(--ink-soft);font-size:12px}.swsi-progress-hero strong{display:block;font-size:36px;line-height:1.15;color:var(--pine-deep);margin:3px 0 13px}.swsi-progress-mini{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.swsi-progress-mini span{background:var(--paper2);border-radius:10px;padding:9px 6px;text-align:center;font-size:10.5px;color:var(--ink-soft)}.swsi-progress-mini b{display:block;color:var(--ink);font-size:14px;margin-bottom:1px}
      .swsi-progress-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:8px}.swsi-progress-strip>div{border:1px solid var(--line);border-radius:12px;background:#fff;padding:10px 7px;text-align:center}.swsi-progress-strip b{display:block;font-size:17px;color:var(--ink)}.swsi-progress-strip span{display:block;font-size:10.5px;line-height:1.4;color:var(--ink-soft);margin-top:2px}
      .swsi-next-card{margin-top:18px;padding:15px;border-radius:15px;background:var(--correct-bg);border:1px solid rgba(79,126,118,.22)}.swsi-next-copy b{display:block;font-size:14px;color:var(--pine-deep);line-height:1.45}.swsi-next-copy span{display:block;font-size:12px;line-height:1.65;color:var(--ink-soft);margin:3px 0 11px}.swsi-next-card .btn{margin:0}
      .swsi-progress-subject{width:100%;border:0;border-bottom:1px solid var(--line);background:transparent;padding:11px 2px;text-align:left;font-family:inherit;cursor:pointer}.swsi-progress-subject .top{display:flex;justify-content:space-between;gap:9px;font-size:13px}.swsi-progress-subject .top span{color:var(--ink-soft);white-space:nowrap}.swsi-progress-subject .accbar{margin:7px 0 4px}.swsi-progress-subject small{font-size:10.5px;color:var(--ink-3)}
      .swsi-cause-stat{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid var(--line);padding:10px 2px;font-size:13px}.swsi-cause-stat b{color:var(--ink-soft)}
      .swsi-progress-foot{margin-top:22px}.swsi-progress-foot .btn{margin-top:8px}.swsi-danger-link{display:block;width:100%;border:0;background:transparent;color:var(--wrong);font-family:inherit;font-size:12px;padding:15px 8px;cursor:pointer}
      @media(max-width:370px){.swsi-progress-mini,.swsi-progress-strip{grid-template-columns:1fr 1fr 1fr}.swsi-progress-mini span,.swsi-progress-strip span{font-size:10px}}
    `;document.head.appendChild(st);
  }

  decorateWrongCause();
  try{
    var scheduled=false;
    var mo=new MutationObserver(function(){if(scheduled)return;scheduled=true;Promise.resolve().then(function(){scheduled=false;decorateWrongCause();});});
    mo.observe(document.body,{childList:true,subtree:true});
  }catch(_e){}

  try{if(typeof view!=='undefined'&&(view==='home'||view==='review'||view==='progress'))render();}catch(_e){}
})();
/* ===== SWSI Essay Trust Layer 2026-08-26 =====
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
      +'<div class="aihelp" style="color:var(--ink-soft);margin-top:7px;font-size:12px;line-height:1.7">一次 1–3 張。AI 會先辨識你寫的內容，再提供練習回饋；若辨識錯誤，請以原稿為準。</div>'
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
        var msg='AI 回饋暫時無法使用，你的作答仍保存在這台裝置。';
        if(r.status===429)msg='目前 AI 使用量較高，請稍後再試；你的作答不會消失。';
        else if(r.status===413)msg='這份作答資料太大，請縮短後再試。';
        else if(r.status===401||r.status===403)msg='AI 服務目前設定異常，請稍後再試。';
        out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">'+E(msg)+'</div>';return;
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
        var msg='AI 照片回饋暫時無法使用，請稍後再試。';
        if(r.status===429)msg='目前 AI 使用量較高，請稍後再試。';
        else if(r.status===413)msg='照片資料太大，請裁切後重新上傳。';
        else if(r.status===401||r.status===403)msg='AI 服務目前設定異常，請稍後再試。';
        out.innerHTML='<div style="margin-top:12px;font-size:13px;color:var(--wrong);line-height:1.7">'+E(msg)+'</div>';return;
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

  if(typeof render==='function'){
    var previousRenderEssayMeta=render;
    render=function(){
      var result=previousRenderEssayMeta.apply(this,arguments);
      polishEssayMetadataUI();
      return result;
    };
    try{window.render=render;}catch(_e){}
  }
  polishEssayMetadataUI();
})();
/* ===== SWSI Essay Metadata Labels END ===== */
