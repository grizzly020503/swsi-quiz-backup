
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

  try{var oldHome=renderHome;renderHome=function(){oldHome();var grid=document.querySelector('#app .swsi-other-grid');if(grid&&!grid.querySelector('.swsi-progress-entry')){var b=document.createElement('button');b.className='swsi-progress-entry';b.textContent='我的學習進度';b.onclick=function(){go('progress');};grid.appendChild(b);}};}catch(_e){}

  if(!document.getElementById('swsi-learning-loop-style')){var st=document.createElement('style');st.id='swsi-learning-loop-style';st.textContent=`
    .swsi-self-cause{margin:15px 0 12px;padding:13px;border:1px solid var(--line);border-radius:13px;background:#F8FAF9}.swsi-cause-title{font-size:var(--fs-b);font-weight:800;color:var(--ink);margin-bottom:3px}.swsi-cause-help{font-size:var(--fs-s);line-height:1.6;color:var(--ink-soft);margin-bottom:9px}.swsi-cause-row{display:flex;flex-wrap:wrap;gap:6px}.swsi-cause-chip{border:1px solid var(--line);background:#fff;color:var(--ink-soft);border-radius:999px;padding:7px 10px;font-family:inherit;font-size:var(--fs-s);font-weight:700;cursor:pointer}.swsi-cause-chip.on{border-color:var(--pine);background:var(--correct-bg);color:var(--pine-deep)}
    .swsi-review-stats{margin:15px 0 16px}.swsi-calm-note{margin:10px 0 0;padding:11px 13px;border:1px solid var(--line);border-radius:11px;background:#fff;color:var(--ink-soft);font-size:13px;line-height:1.6}.swsi-learning-section{margin-top:20px}.swsi-learning-h{font-size:14px;font-weight:900;color:var(--ink);margin:0 0 9px}.swsi-learning-muted{font-size:12px;line-height:1.65;color:var(--ink-soft);padding:2px 2px 8px}.swsi-learning-row{width:100%;display:flex;align-items:center;justify-content:space-between;gap:10px;text-align:left;border:1px solid var(--line);background:#fff;border-radius:12px;padding:11px 13px;margin-bottom:7px;color:var(--ink);font-family:inherit;cursor:pointer}.swsi-learning-row b{display:block;font-size:13.5px;line-height:1.45}.swsi-learning-row small{display:block;font-size:11.5px;color:var(--ink-soft);margin-top:2px}
    .swsi-progress-hero{margin-top:13px;border:1px solid var(--line);border-radius:17px;background:#fff;padding:16px}.swsi-progress-hero>div:first-child small{display:block;color:var(--ink-soft);font-size:12px}.swsi-progress-hero strong{display:block;font-size:36px;line-height:1.15;color:var(--pine-deep);margin:3px 0 13px}.swsi-progress-mini{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.swsi-progress-mini span{background:var(--paper2);border-radius:10px;padding:9px 6px;text-align:center;font-size:10.5px;color:var(--ink-soft)}.swsi-progress-mini b{display:block;color:var(--ink);font-size:14px;margin-bottom:1px}.swsi-progress-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:8px}.swsi-progress-strip>div{border:1px solid var(--line);border-radius:12px;background:#fff;padding:10px 7px;text-align:center}.swsi-progress-strip b{display:block;font-size:17px;color:var(--ink)}.swsi-progress-strip span{display:block;font-size:10.5px;line-height:1.4;color:var(--ink-soft);margin-top:2px}
    .swsi-next-card{margin-top:18px;padding:15px;border-radius:15px;background:var(--correct-bg);border:1px solid rgba(79,126,118,.22)}.swsi-next-copy b{display:block;font-size:14px;color:var(--pine-deep);line-height:1.45}.swsi-next-copy span{display:block;font-size:12px;line-height:1.65;color:var(--ink-soft);margin:3px 0 11px}.swsi-next-card .btn{margin:0}.swsi-progress-subject{width:100%;border:0;border-bottom:1px solid var(--line);background:transparent;padding:11px 2px;text-align:left;font-family:inherit;cursor:pointer}.swsi-progress-subject .top{display:flex;justify-content:space-between;gap:9px;font-size:13px}.swsi-progress-subject .top span{color:var(--ink-soft);white-space:nowrap}.swsi-progress-subject .accbar{margin:7px 0 4px}.swsi-progress-subject small{font-size:10.5px;color:var(--ink-3)}.swsi-cause-stat{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid var(--line);padding:10px 2px;font-size:13px}.swsi-cause-stat b{color:var(--ink-soft)}.swsi-progress-foot{margin-top:22px}.swsi-progress-foot .btn{margin-top:8px}.swsi-danger-link{display:block;width:100%;border:0;background:transparent;color:var(--wrong);font-family:inherit;font-size:12px;padding:15px 8px;cursor:pointer}
  `;document.head.appendChild(st);}

  decorateWrongCause();
  try{var scheduled=false;var mo=new MutationObserver(function(){if(scheduled)return;scheduled=true;Promise.resolve().then(function(){scheduled=false;decorateWrongCause();});});mo.observe(document.body,{childList:true,subtree:true});}catch(_e){}
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

/* SWSI Law Trust Layer V1 2026-08-26
   Official exam questions are immutable. This layer only corrects and labels SWSI-authored
   law/policy reference cards, links official sources, and distinguishes laws from policies/conventions.
*/
(function(){
  'use strict';

  var CHECKED_AT='2026-08-26';
  var MOJ='https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=';
  var VERIFY_CHECKED='checked';
  var VERIFY_SOURCE='source_only';

  function byName(name){
    try{return LAWS.find(function(x){return x&&x.n===name;})||null;}catch(_e){return null;}
  }
  function patch(name,data){
    var x=byName(name);if(!x)return null;
    Object.keys(data||{}).forEach(function(k){x[k]=data[k];});
    return x;
  }
  function add(row){
    if(!row||!row.n||byName(row.n))return;
    LAWS.push(row);
  }

  var SOURCES={
    '社會工作師法':{url:MOJ+'D0050125',kind:'law'},
    '社會工作人員執業安全方案':{url:'https://dep.mohw.gov.tw/DOSAASW/',kind:'policy'},
    '兒童及少年福利與權益保障法':{url:MOJ+'D0050001',kind:'law'},
    '兒童及少年性剝削防制條例':{url:MOJ+'D0050023',kind:'law'},
    '少年事件處理法':{url:MOJ+'C0010011',kind:'law'},
    '兒童權利公約 CRC':{url:'https://crc.sfaa.gov.tw/',kind:'convention'},
    '家庭暴力防治法':{url:MOJ+'D0050071',kind:'law'},
    '社會救助法':{url:MOJ+'D0050078',kind:'law'},
    '老人福利法':{url:MOJ+'D0050037',kind:'law'},
    '身心障礙者權益保障法':{url:MOJ+'D0050046',kind:'law'},
    '身心障礙者權利公約 CRPD':{url:'https://crpd.sfaa.gov.tw/',kind:'convention'},
    '長期照顧服務法':{url:MOJ+'L0070040',kind:'law'},
    '病人自主權利法':{url:MOJ+'L0020189',kind:'law'},
    '性別平等工作法':{url:MOJ+'N0030014',kind:'law'},
    '性別平等政策綱領':{url:'https://gec.ey.gov.tw/Page/FD420B6572C922EA',kind:'policy'},
    '入出國及移民法':{url:MOJ+'D0080132',kind:'law'},
    '公益勸募條例':{url:MOJ+'D0050138',kind:'law'},
    '公務人員退休資遣撫卹法':{url:MOJ+'S0080034',kind:'law'}
  };

  // Every existing card gets an official-government source link first. Content is not called verified
  // until it has been reviewed card-by-card.
  Object.keys(SOURCES).forEach(function(name){
    var x=byName(name),s=SOURCES[name];if(!x)return;
    x.source_url=s.url;x.source_kind=s.kind;x.source_label=s.kind==='law'?'全國法規資料庫':(s.kind==='policy'?'政府政策官方頁':'公約官方專區');
    x.checked_at=x.checked_at||'';
    x.verify_status=x.verify_status||VERIFY_SOURCE;
  });

  // ----- P0 corrections verified against official/current government sources -----
  patch('社會工作師法',{
    source_url:MOJ+'D0050125',source_kind:'law',source_label:'全國法規資料庫',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED,
    u:'112年6月9日修法的重點是：擴充不得充任／執業資格限制、建立社工師懲戒制度、強化執業安全與機關安全防護及法律協助，並增訂妨礙社工執業的處罰。專科社會工作師制度與「每六年完成繼續教育」並非112年才新設，勿混在同一批修法重點背誦。',
    trust_note:'112年修正的是第7、10、19條，並增訂第17-1至17-3、19-1、39-1條。'
  });

  patch('社會救助法',{
    source_url:MOJ+'D0050078',source_kind:'law',source_label:'全國法規資料庫',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED,
    c:'①低收入戶：家庭總收入平均分配全家人口，每人每月在「當地區公告最低生活費」以下，且家庭財產未超過公告限額 ②中低收入戶：收入門檻原則上不超過當地區最低生活費1.5倍，並另受家庭財產限額等條件限制 ③最低生活費由中央或直轄市主管機關依法定公式訂定，各地區不同、每年可能調整 ④制度並包括生活扶助、醫療、教育、住宅、急難與災害救助及協助自立等措施。',
    a:'貧窮、經濟安全題的法源。最重要的是寫清楚「家戶所得＋財產調查＋各地區公告標準」，不要背成全國只有一個固定金額；再連到資產調查、福利資格與協助自立。',
    u:'115年度最低生活費並非全國統一：例如臺灣省／臺南市15,515元、高雄市16,970元、臺北市20,744元等。考試若涉及當年度金額，應以中央與各直轄市最新公告為準。',
    trust_note:'已移除原本把「15,515元」與「23,273元」寫成全國統一門檻的表述。',
    secondary_url:'https://www.mohw.gov.tw/cp-190-231-1.html',secondary_label:'衛福部社會救助資訊'
  });

  patch('兒童及少年福利與權益保障法',{
    source_url:MOJ+'D0050001',source_kind:'law',source_label:'全國法規資料庫',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED,
    u:'現行法與修法草案要分開看。115年衛福部曾預告兒少權法修正草案，但「草案」不是現行條文；國考作答若談修法動態，必須清楚標成草案／政策方向，不可當成已生效規定。',
    trust_note:'平台只把已公布施行的條文列為現行法；115年修正草案另作動態提示。'
  });

  patch('兒童及少年性剝削防制條例',{
    source_url:MOJ+'D0050023',source_kind:'law',source_label:'全國法規資料庫',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED,
    u:'113年8月7日有修正；其中部分修正條文的施行日期由行政院另定。準備考試時要區分「已公布」與「已施行」，不能把尚待施行的內容直接當成現行規定。',
    trust_note:'數位性影像與網路平台責任是近年重要方向，但條文施行狀態須以全國法規資料庫的生效註記為準。'
  });

  patch('長期照顧服務法',{
    source_url:MOJ+'L0070040',source_kind:'law',source_label:'全國法規資料庫',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED,
    p:'規範長期照顧服務、長照人員與機構、服務使用者權益及照顧服務體系的法律框架；「長照2.0／3.0」則是政策計畫，兩者要分開。',
    c:'①長期照顧係對身心失能持續已達或預期達6個月以上者提供生活支持、協助、社會參與、照顧及相關醫護服務 ②法定長照服務包含居家式、社區式、機構住宿式、家庭照顧者支持及其他依法提供之服務 ③並規範長照人員、長照機構、服務契約、品質與權益保障。ABC社區整合服務網、給付支付細節屬政策／子法層次，不宜直接當成本法條文背。',
    a:'長照題先分兩層：引用《長期照顧服務法》說法律框架，再另列「長照3.0」政策談現行制度發展，避免把政策措施寫成法條。',
    u:'行政院於114年12月31日核定「長期照顧十年計畫3.0（115－124年）」，並自115年（2026）起正式實施。這是政策計畫，不等同於《長期照顧服務法》本身的條文。',
    trust_note:'已把原卡中「長照2.0 ABC據點」從法律核心重點移到政策層次。',
    secondary_url:'https://1966.gov.tw/LTC/cp-6572-85008-207.html',secondary_label:'衛福部長照3.0官方頁'
  });

  patch('性別平等工作法',{
    source_url:MOJ+'N0030014',source_kind:'law',source_label:'全國法規資料庫',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED,
    u:'因應#MeToo，法律於112年8月16日修正公布並更名為《性別平等工作法》；部分新制於113年3月8日施行。應區分「112年修正公布」與「113年部分規定施行」，不要簡化成「113年才修法」。',
    trust_note:'已修正原卡把修法年份直接寫成113年的表述。'
  });

  patch('入出國及移民法',{
    source_url:MOJ+'D0080132',source_kind:'law',source_label:'全國法規資料庫',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED,
    p:'規範國民入出國、無戶籍國民及外國人停留／居留／永久居留、移民輔導與相關權益事項。新住民權益另有《新住民基本法》，人口販運則有獨立的《人口販運防制法》，不宜全部塞進移民法。',
    c:'①國民入出國及無戶籍國民相關管理 ②外國人停留、居留與永久居留 ③移民輔導與相關權益保障 ④對移民歧視等事項的規範。人口販運被害人鑑別、保護與刑事規範，應另連結《人口販運防制法》。',
    a:'新住民／移民題可用它談身分與居留制度，但若題目核心是新住民基本權益，優先連《新住民基本法》；若是人口販運，改以《人口販運防制法》為主。',
    trust_note:'已把原本容易把移民法與人口販運防制混為一談的敘述拆開。'
  });

  // ----- High-priority laws missing from the old quick-reference list -----
  add({
    n:'社會福利基本法',d:'社會政策',p:'112年5月24日制定公布，是我國社會福利基本權利、基本方針與體制的總綱性法律。',
    c:'①社會福利範圍包含社會保險、社會救助、社會津貼、福利服務、醫療保健、國民就業與社會住宅 ②基本方針強調適足生活、尊嚴、潛能、社會參與與公平正義 ③福利服務應以人為本、家庭為中心、社區為基礎 ④中央應訂定社會福利政策綱領並至少每五年檢討一次。',
    a:'社會政策總論、福利國家、福利輸送與社會權題很適合用它當「法律總綱」開場，再接各領域專法。',u:'112年5月24日制定公布，自公布日施行。',
    k:['社會福利基本權利','社會包容','七大福利事項','家庭為中心','社區為基礎','公平正義'],
    source_url:MOJ+'D0050213',source_label:'全國法規資料庫',source_kind:'law',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED,
    secondary_url:'https://www.mohw.gov.tw/dl-95281-2c3b2cd8-8fe0-4dfe-9cd0-82a8715c0983.html',secondary_label:'衛福部法規全文'
  });

  add({
    n:'性騷擾防治法',d:'性別與保護',p:'處理不屬《性別平等教育法》或《性別平等工作法》優先適用範圍的性騷擾防治與被害人權益保護，是性騷擾防治三法體系的重要一環。',
    c:'①依事件場域與身分關係，校園與職場若各有專法規定，優先適用各該法律 ②現行法明定性騷擾與權勢性騷擾 ③建立申訴、調查、保護扶助與行為人責任等機制 ④作答時應先判斷事件落在哪一部性平法律。',
    a:'遇到性騷擾案例，第一步不是背罰則，而是先判斷「校園／職場／一般場域」的法律適用，再寫被害人保護、申訴調查與避免二次傷害。',
    u:'112年8月16日修正公布全文34條；部分條文自113年3月8日施行，其餘自公布日施行。',
    k:['權勢性騷擾','三法適用','被害人保護','申訴調查','二次傷害'],
    source_url:MOJ+'D0050074',source_label:'全國法規資料庫',source_kind:'law',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED
  });

  add({
    n:'性侵害犯罪防治法',d:'性別與保護',p:'防治性侵害犯罪並保障被害人權益，涵蓋預防通報、被害人保護與加害人處遇。',
    c:'①明定性侵害犯罪、被害人與加害人等用詞 ②由社政、衛生、教育、警政司法等跨網絡分工 ③被害人保護包含必要之醫療、心理、法律與社會支持 ④另規範加害人身心治療、輔導教育及相關管理。',
    a:'性侵害個案題可用「被害人安全與創傷知情＋跨網絡合作＋司法程序支持」作主架構；不要只寫刑事責任。',
    u:'112年2月15日修正公布全文56條；除第13條自公布後六個月施行外，其餘自公布日施行。',
    k:['性侵害防治','被害人保護','責任通報','跨網絡','加害人處遇'],
    source_url:MOJ+'D0080079',source_label:'全國法規資料庫',source_kind:'law',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED
  });

  add({
    n:'精神衛生法',d:'心理衛生與社區',p:'以心理健康促進、精神疾病預防與照護、社區支持及精神病人權益保障為核心的法律。',
    c:'①強化全民心理健康促進與社區心理衛生中心 ②布建多元社區支持、跨網絡照護與危機處理 ③保障精神病人權益並防止污名與歧視 ④嚴重病人強制住院新制採法官保留並導入專家參審。',
    a:'精神障礙、社區照顧、社安網與強制處遇倫理題，可同時寫「醫療需要、最小限制、人權保障、社區支持、跨網絡合作」。',
    u:'111年12月14日修正公布全文91條，多數規定自113年12月14日施行；第五章等涉及強制住院的新制自115年8月1日施行。',
    k:['心理健康促進','社區心理衛生中心','復元','人權保障','法官保留','專家參審'],
    source_url:MOJ+'L0020030',source_label:'全國法規資料庫',source_kind:'law',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED,
    secondary_url:'https://www.mohw.gov.tw/cp-7401-87291-1.html',secondary_label:'衛福部115年強制住院新制'
  });

  add({
    n:'人口販運防制法',d:'移民與多元',p:'防制人口販運、追訴犯罪並保護及協助被害人的專法；本國人與外國人都可能是被害人。',
    c:'①以預防、追訴、保護及夥伴合作等面向建構防制體系 ②建立疑似被害人鑑別、安置保護、醫療、通譯、法律與生活協助 ③對符合條件之外籍被害人提供居留及工作等保障 ④對新型態人口販運犯罪加強規範。',
    a:'移工、跨境犯罪、性剝削與勞動剝削題，先做被害人鑑別與安全保護，再談跨機關合作、居留工作權益與創傷知情服務。',
    u:'112年6月14日修正公布全文47條，行政院定自113年1月1日施行。',
    k:['人口販運','被害人鑑別','安置保護','4P','跨境','勞動剝削'],
    source_url:MOJ+'D0080177',source_label:'全國法規資料庫',source_kind:'law',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED
  });

  add({
    n:'新住民基本法',d:'移民與多元',p:'保障新住民基本權益、促進多元文化與社會融合的基本法，與《入出國及移民法》的身分／居留管理功能不同。',
    c:'以尊重多元文化、平等權益與社會參與為核心，要求政府就新住民之家庭、教育學習、就業、醫療、社會福利、語言文化與公共參與等需求建立整體政策與支持。',
    a:'新住民社會工作題不要只寫「文化適應」；可從基本權、人權、多元文化、反歧視、語言可近性、家庭支持與社會參與一起分析。',
    u:'113年8月12日制定公布。',
    k:['新住民權益','多元文化','反歧視','社會融合','公共參與','家庭支持'],
    source_url:MOJ+'D0080227',source_label:'全國法規資料庫',source_kind:'law',checked_at:CHECKED_AT,verify_status:VERIFY_CHECKED,
    secondary_url:'https://www.moi.gov.tw/News_Photo_Content.aspx?n=18&s=318835',secondary_label:'內政部新住民基本法重點'
  });

  function kindLabel(kind){return kind==='policy'?'政策／行政方案':kind==='convention'?'公約／人權框架':'現行法律';}
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

  var oldRenderLaws=renderLaws;
  renderLaws=function(){
    oldRenderLaws();
    try{
      var title=document.querySelector('#app .section-h');if(title&&title.textContent.indexOf('法規')>=0)title.textContent='法規與政策速查';
      var sub=document.querySelector('#app .section-s');
      if(sub)sub.innerHTML='先抓官方法規與政策的核心，再接回歷屆考題。<br><span style="color:var(--ink-soft);font-size:12px">✓「已逐卡核對」代表摘要已和官方來源重新比對；「待逐卡複核」只代表已找到官方來源，內容仍不冒充已核對。法律、政策與公約會分開標示。</span>';
      if(typeof lawOpen==='number'&&lawOpen>=0&&LAWS[lawOpen]){
        var open=document.querySelector('#app .ecard.open .ebodywrap');
        if(open&&!open.querySelector('.swsi-law-trust'))open.insertAdjacentHTML('beforeend',trustHTML(LAWS[lawOpen]));
      }
    }catch(e){console.warn('law trust render skipped',e);}
  };

  window.SWSI_LAW_TRUST={version:'SWSI Law Trust Layer V1 2026-08-26',checkedAt:CHECKED_AT,verifiedCount:function(){return LAWS.filter(function(x){return x.verify_status===VERIFY_CHECKED;}).length;}};
})();

/* SWSI Law Trust Escape Fix 2026-08-26 */
(function(){
  'use strict';
  if(typeof window.H!=='function'){
    window.H=function(v){
      return String(v==null?'':v).replace(/[&<>"']/g,function(c){
        return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
      });
    };
  }
})();

/* SWSI New Resident Basic Act Status Fix 2026-08-26
   Promulgated does not automatically mean effective: Article 19 leaves the effective date to the Executive Yuan.
*/
(function(){
  'use strict';
  var name='新住民基本法';
  var x=null;
  try{x=LAWS.find(function(v){return v&&v.n===name;})||null;}catch(_e){}
  if(x){
    x.source_kind='law_pending';
    x.checked_at='2026-08-26';
    x.verify_status='checked';
    x.u='113年8月12日制定公布；第19條明定「本法施行日期，由行政院定之」。截至平台本次核對，官方資料仍以「自新住民基本法施行日起」描述多項配套措施，未找到可據以把制定公布日直接當作全面施行日的行政院施行令。應試時請把「制定公布」與「施行」分開寫。';
    x.trust_note='已核對制定公布日期與第19條。此卡標示為「已制定公布・施行日另定」，不把尚待確認的施行日期冒充現行生效狀態。';
  }

  var prev=renderLaws;
  renderLaws=function(){
    prev();
    try{
      if(typeof lawOpen!=='number'||lawOpen<0||!LAWS[lawOpen]||LAWS[lawOpen].n!==name)return;
      var panel=document.querySelector('#app .ecard.open .swsi-law-trust');
      if(!panel)return;
      var badge=panel.querySelector('span');
      if(badge){
        badge.textContent='已制定公布・施行日另定';
        badge.style.color='#756E57';
        badge.style.borderColor='#E5DCC1';
      }
    }catch(e){console.warn('new resident act status render skipped',e);}
  };

  window.SWSI_NEW_RESIDENT_STATUS={version:'SWSI New Resident Basic Act Status Fix 2026-08-26'};
})();

/* SWSI Law Trust Batch 2 2026-08-26
   Second official-source review batch. Official exam questions remain untouched.
*/
(function(){
  'use strict';
  var CHECKED_AT='2026-08-26';
  var VERIFIED='checked';
  function law(name){try{return LAWS.find(function(x){return x&&x.n===name;})||null;}catch(_e){return null;}}
  function patch(name,data){var x=law(name);if(!x)return;Object.keys(data).forEach(function(k){x[k]=data[k];});}

  patch('家庭暴力防治法',{
    checked_at:CHECKED_AT,verify_status:VERIFIED,
    p:'防治家庭暴力並保障被害人權益的專法。家庭暴力包含家庭成員間身體、精神或經濟上的騷擾、控制、脅迫或其他不法侵害。',
    c:'①民事保護令分為通常、暫時、緊急三種 ②通常保護令有效期間為2年以下，期滿前得聲請延長，每次延長亦為2年以下 ③被害人有受家庭暴力急迫危險，依法聲請緊急保護令且法院認有急迫危險者，法院受理後應於4小時內以書面核發 ④通常保護令可包含禁止施暴／騷擾接觸跟蹤、命遷出或遠離、未成年子女權利義務與會面交往、扶養費、加害人處遇等命令 ⑤地方政府應設家庭暴力防治中心，提供24小時專線、緊急救援與安置，並辦理危險評估及跨機構網絡會議。',
    a:'家暴或親密關係暴力題，可用「安全優先→危險評估→保護令／緊急安置→跨網絡合作→中長期支持」作為處遇脈絡。寫數字時要精準：緊急令是符合要件後法院受理後4小時內核發；通常令是2年以下。',
    u:'全國法規資料庫現行版本修正日期為112年12月6日。112年修法新增／強化數位性暴力相關保護命令，例如禁止重製、散布或要求刪除、移除被害人性影像。',
    trust_note:'已依現行第2、8、9、14、15、16條重新核對「三種保護令、4小時、2年以下、家暴防治中心」等常考細節。'
  });

  patch('身心障礙者權益保障法',{
    checked_at:CHECKED_AT,verify_status:VERIFIED,
    p:'保障身心障礙者平等參與、人格與合法權益，促進自立及發展的核心法律。現行法以「功能損傷是否影響活動與社會參與」及專業團隊鑑定、需求評估作為重要制度基礎。',
    c:'①身心障礙者須經專業團隊鑑定及評估並領有身心障礙證明；需求評估會考量障礙類別與程度、家庭經濟、照顧、家庭生活與社會參與需求 ②禁止在教育、應考、進用、就業、居住、遷徙、醫療等權益上歧視，並要求公平使用公共設施 ③定額進用：政府機關、公立學校及公營事業34人以上，不得低於3%；私立學校、團體及民營事業67人以上，不得低於1%且至少1人 ④福利與服務應依需求評估提供個別化、多元化服務。',
    a:'身障題先用「權利／平等參與／自立」定調，再談鑑定與需求評估、合理調整／無障礙、就業與服務支持。若寫ICF，可把它當作我國身障鑑定制度的重要背景框架，不要寫成「本法條文明文規定ICF」。',
    u:'全國法規資料庫現行版本修正日期為114年8月1日。定額進用第38條目前仍維持公部門34人以上3%、私部門67人以上1%且至少1人的規定。',
    trust_note:'已依現行第1、5、7、16、19、38條核對；並把「ICF」從法條文字和制度背景中分開，避免過度簡化。'
  });

  patch('老人福利法',{
    checked_at:CHECKED_AT,verify_status:VERIFIED,
    p:'以年滿65歲以上者為「老人」，目的在維護尊嚴與健康、延緩失能、安定生活、保障權益並增進福利。',
    c:'①老人＝年滿65歲以上 ②老人因負照顧義務者疏忽、虐待、遺棄等致生命、身體、健康或自由發生危難，地方主管機關得依申請或職權予以保護及安置 ③老人無人扶養而有生命、身體危難或生活困境者，地方主管機關應予適當安置 ④醫事、社工、村里長／幹事、警察、司法及其他執行老人福利業務人員，執行職務知悉疑似前述情況時，應通報地方主管機關；主管機關接獲後應立即處理，必要時訪視調查 ⑤地方應結合警政、衛生、社政、民政與民間力量建立老人保護體系。',
    a:'老人保護題不要只寫「通報」兩字，可依序寫：辨識危險→依職務通報→主管機關立即處理／訪視→必要時保護安置→跨網絡老人保護體系。若涉及家庭暴力，再與《家庭暴力防治法》交叉。',
    u:'全國法規資料庫現行版本修正日期為114年8月1日。準備考試時，老人保護以現行第41至44條為主要法源。',
    trust_note:'已依現行第2、41、42、43、44條重新核對老人年齡、保護安置、職務通報與跨網絡保護。'
  });

  patch('病人自主權利法',{
    checked_at:CHECKED_AT,verify_status:VERIFIED,
    p:'保障病人知情、選擇與醫療自主的專法；具完全行為能力者可透過預立醫療照護諮商（ACP）事先作成預立醫療決定（AD）。',
    c:'①意願人可先接受預立醫療照護諮商，再以書面作成預立醫療決定並依法完成見證／公證與註記程序 ②預立醫療決定可就維持生命治療及人工營養與流體餵養表達接受或拒絕意願 ③適用的五類臨床條件：末期病人、不可逆轉昏迷、永久植物人、極重度失智，以及其他經中央主管機關公告且符合痛苦難忍、疾病無法治癒、依當時醫療水準無其他合適解決方法的疾病狀況或情形 ④病人當下仍具有清楚表達能力時，當下意思應受到尊重。',
    a:'醫務社工或生命倫理題可用「知情→自主→ACP溝通→AD→家屬／醫療團隊協調」來寫；不要把病主法簡化成只有「拒絕急救」，它處理的是更完整的醫療自主與善終規劃。',
    u:'病主法自108年1月6日施行。中央主管機關另可依第14條第1項第5款公告其他適用的疾病狀況或情形，因此考試若問最新適用範圍，應再查衛福部最新公告。',
    trust_note:'已依衛福部病主法官方說明重新核對ACP、AD與五類臨床條件；避免把「五類」誤寫成固定只有五個疾病名稱。',
    secondary_url:'https://www.mohw.gov.tw/cp-2704-44221-1.html',secondary_label:'衛福部病主法配套說明'
  });

  patch('少年事件處理法',{
    checked_at:CHECKED_AT,verify_status:VERIFIED,
    p:'處理12歲以上、未滿18歲少年之保護事件與少年刑事案件，核心目的在保障健全自我成長、調整成長環境並採取適合少年的保護與司法處遇。',
    c:'①本法少年＝12歲以上18歲未滿 ②少年觸犯刑罰法律之行為由少年法院依本法處理 ③現行第3條另保留三類「曝險」行為徵兆：無正當理由經常攜帶危險器械、施用毒品或迷幻物品而尚未觸犯刑罰法律、預備犯罪或犯罪未遂而為法所不罰 ④曝險少年自112年7月1日起採「行政輔導先行、司法處遇為後盾」：由地方少年輔導委員會整合福利、教育、心理、醫療等資源輔導，評估有必要時再請求少年法院處理 ⑤少年司法強調程序權、表意與避免過早司法化。',
    a:'少年偏差／司法社工題先分清「已觸法少年」與「曝險少年」；後者不是看到偏差就直接送法院，而應先寫少輔會跨資源行政輔導，必要時才由司法接續。',
    u:'全國法規資料庫現行版本修正日期為112年6月21日；曝險少年行政輔導先行制度自112年7月1日正式施行。',
    trust_note:'已依現行第2、3條及司法院曝險少年新制官方說明核對；「行政輔導先行、司法為後盾」已是現行制度，不是尚未上路的政策口號。',
    secondary_url:'https://www.judicial.gov.tw/tw/cp-1470-58175-6f029-1.html',secondary_label:'司法院少事法修正重點'
  });

  if(window.SWSI_LAW_TRUST){
    window.SWSI_LAW_TRUST.batch2='SWSI Law Trust Batch 2 2026-08-26';
  }
})();

/* SWSI Law Trust Final Batch 2026-08-26
   Final verification pass for the remaining six law/policy/convention cards.
   Official exam questions remain untouched.
*/
(function(){
  'use strict';
  var CHECKED_AT='2026-08-26';
  var CHECKED='checked';
  function byName(name){
    try{return LAWS.find(function(x){return x&&x.n===name;})||null;}catch(_e){return null;}
  }
  function patch(name,data){
    var x=byName(name);if(!x)return;
    Object.keys(data||{}).forEach(function(k){x[k]=data[k];});
  }

  patch('社會工作人員執業安全方案',{
    source_kind:'policy',
    source_label:'衛福部社會救助及社工司',
    source_url:'https://dep.mohw.gov.tw/DOSAASW/cp-539-4620-103.html',
    checked_at:CHECKED_AT,verify_status:CHECKED,
    p:'衛生福利部推動的社工執業安全行政方案，不是法律。行政院核定後，由法制、訓練、防護設備、風險評估、通報、保險與督導等面向降低社工執業風險。',
    c:'①建立風險評估、安全防護指引與標準工作流程 ②辦理人身安全分級訓練 ③建置安全設備與防護措施 ④建立遭受侵害事件通報及重大事件輔導改善 ⑤推動執業安全督導、申訴救濟、保險與風險工作支持。112年《社會工作師法》另增強法制面的執業安全保障，兩者是「行政方案＋法律」的不同層次。',
    a:'遇到社工受暴、職場安全、外訪風險題，可先寫《社會工作師法》的法定保障，再補本方案的風險評估、訓練、設備、通報、督導與保險措施。',
    u:'衛福部目前仍保留執業安全方案與相關執業安全通報、訓練及保險措施；準備考試時不要把行政方案名稱當成法律名稱。',
    trust_note:'107年8月1日行政院核定之行政方案；112年社工師法修法後，執業安全同時具有更明確的法律層保障。',
    k:['行政方案（非法律）','風險評估','安全防護','分級訓練','危害通報','執業安全']
  });

  patch('兒童權利公約 CRC',{
    source_kind:'convention',
    source_label:'CRC官方資訊網',
    source_url:'https://crc.sfaa.gov.tw/',
    checked_at:CHECKED_AT,verify_status:CHECKED,
    p:'聯合國1989年通過的《兒童權利公約》。我國以《兒童權利公約施行法》使公約保障與促進兒少權利的規定具有國內法律效力，施行法自103年11月20日起施行。',
    c:'四項一般性原則：①禁止歧視（第2條）②兒童最佳利益（第3條）③生命、生存及發展權（第6條）④尊重兒童意見／表意並使意見獲得適當考量（第12條）。CRC的重點不是把兒少只當被保護者，而是把兒少視為權利主體。',
    a:'兒少題可用CRC拉高價值層次，但不要只背「最佳利益」四個字。若題目涉及安置、會面、教育、家庭決策或服務設計，可進一步問：兒少有沒有被聽見？是否受歧視？決策是否符合其最佳利益與發展權？',
    u:'CRC本身是國際公約；在台灣透過《兒童權利公約施行法》具有國內法律效力。不要把「公約」和「兒少權法」混成同一部法律。',
    trust_note:'已依CRC官方資訊網與施行法重新核對四項一般性原則與國內法效力。',
    k:['權利主體','禁止歧視','最佳利益','生存與發展','表意權','CRC施行法']
  });

  patch('身心障礙者權利公約 CRPD',{
    source_kind:'convention',
    source_label:'CRPD官方資訊網',
    source_url:'https://crpd.sfaa.gov.tw/',
    checked_at:CHECKED_AT,verify_status:CHECKED,
    p:'聯合國2006年通過的《身心障礙者權利公約》。我國以《身心障礙者權利公約施行法》使CRPD的人權保障規定具有國內法律效力，施行法自103年12月3日起施行。',
    c:'核心包括尊重固有尊嚴與個人自主、不歧視、充分有效參與及融合社會、尊重差異、機會均等、無障礙、性別平等及尊重身心障礙兒童發展能力等原則。常考概念包含合理調整、可及性、自立生活與融合社區，以及在法律之前平等獲得承認。',
    a:'身障題不要只寫福利補助。可從「障礙是否來自環境阻礙」「是否提供合理調整」「服務是否支持本人自主與社區生活」切入，再搭配身權法的具體制度。',
    u:'CRPD是國際人權公約；國內適用要和《CRPD施行法》及《身心障礙者權益保障法》分層理解。113年政府另公布各機關研訂合理調整指引之原則，合理調整已成實務的重要落實議題。',
    trust_note:'已依CRPD官方資訊網、施行法及一般性意見重新核對；「支持決策」屬CRPD第12條脈絡的重要方向，不宜簡化成一條台灣法條口號。',
    k:['人權模式','自主','不歧視','合理調整','可及性','自立生活','融合社區']
  });

  patch('性別平等政策綱領',{
    source_kind:'policy',
    source_label:'行政院性別平等會',
    source_url:'https://gec.ey.gov.tw/Page/FD420B6572C922EA',
    checked_at:CHECKED_AT,verify_status:CHECKED,
    p:'行政院用來統整我國性別平等政策方向的最高政策指導方針，是政策綱領，不是法律。100年函頒，110年5月再次修正函頒。',
    c:'110年修正版把原本7大領域與大量具體行動措施，重整為整體性的願景、理念、政策目標與6面向、33項推動策略，並納入CEDAW、SDGs、CRPD等國際人權與永續發展精神，特別關注不利處境與數位／網路性別暴力等議題。',
    a:'性別政策題可以用它說明政府整體政策方向；若題目問法律責任，仍要回到《性別平等工作法》《性騷擾防治法》等具體法律，不能拿政策綱領代替法源。',
    u:'目前平台以行政院110年5月修正函頒版本為基準。性別主流化工具可另作政策實務補充，不要把「六大工具」誤當成這部綱領的法定六條。',
    trust_note:'已依行政院性別平等會現行官方頁重新核對，明確區分「政策綱領」與「法律」。',
    k:['政策綱領（非法律）','性別平等','性別主流化','CEDAW','不利處境','數位性別暴力']
  });

  patch('公益勸募條例',{
    source_kind:'law',
    source_label:'全國法規資料庫',
    source_url:'https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=D0050138',
    checked_at:CHECKED_AT,verify_status:CHECKED,
    p:'規範公益勸募行為、勸募財物使用與公開透明的法律，目的在妥善運用社會資源並保障捐款人權益。現行條文最近修正日期為109年1月15日。',
    c:'①法定勸募主體有限定，政府機關原則上不得主動發起勸募，重大災害或國際救援例外 ②跨縣市勸募向中央主管機關申請，其餘向所在地地方主管機關申請許可 ③勸募活動最長一年 ④須開立專戶、收據並公開徵信 ⑤所得應依核准使用計畫使用，不得任意挪用；活動與使用完畢都有公告及備查義務。',
    a:'非營利組織、募款、資源開發與組織課責題可用。重點不是只背「要申請」，而是勸募主體、許可、專戶、收據、公開徵信、用途限制與主管機關監督。',
    u:'法規涉及支出比例、公告期限等精確數字時，以考試當下全國法規資料庫最新版為準。',
    trust_note:'已依全國法規資料庫現行條文重新核對，不再用模糊的「有比例與用途規範」帶過。',
    k:['勸募許可','勸募主體','捐款專戶','公開徵信','用途限制','課責透明']
  });

  patch('公務人員退休資遣撫卹法',{
    source_kind:'law',
    source_label:'全國法規資料庫',
    source_url:'https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=S0080034',
    checked_at:CHECKED_AT,verify_status:CHECKED,
    d:'延伸制度',
    p:'規範經銓敘審定公務人員的退休、資遣及撫卹制度，主管機關為銓敘部。它是職域退撫制度，不等同全民性的老人福利或社會保險制度。',
    c:'①退撫新制自84年7月1日起採政府與公務人員共同提撥的退撫基金制度 ②本法規範退休金、資遣給與、撫卹金、遺屬給與等 ③涉及退休所得替代率、基金提撥、財務精算與制度永續。現行法最近修正日期為114年12月26日，年金相關數字與調整機制應以最新法規及附表為準。',
    a:'只有在題目真的涉及年金改革、職業退休制度、世代公平或老年所得保障的制度比較時再引用；一般老人福利題不需要硬塞這部法。',
    u:'114年12月26日有最新修正。涉及所得替代率、調整機制或精確年金數值時，務必直接查當年度現行條文與附表。',
    trust_note:'已降為「延伸制度」：有助理解年金與社會政策，但不是一般社工實務題的核心法源。',
    k:['職域退撫','共同提撥','退休所得','年金改革','財務永續','世代公平']
  });

  window.SWSI_LAW_TRUST_FINAL={version:'SWSI Law Trust Final Batch 2026-08-26',checkedAt:CHECKED_AT};
})();

/* SWSI AI Copy Polish 2026-08-26
   Clarify that OCR-like recognition applies to photo uploads, not typed answers.
*/
(function(){
  'use strict';
  var old=window.aiFeedbackHTML;
  if(typeof old==='function'){
    window.aiFeedbackHTML=function(id){
      var h=old(id);
      return String(h).replace(
        '一次 1–3 張。AI 會先辨識你寫的內容，再提供練習回饋；若辨識錯誤，請以原稿為準。',
        '手寫照片可一次 1–3 張。照片模式會先辨識字跡，再提供練習回饋；若辨識有誤，請以原稿為準。打字作答不需要辨識。'
      );
    };
    try{aiFeedbackHTML=window.aiFeedbackHTML;}catch(_e){}
  }
  window.SWSI_AI_COPY_POLISH='SWSI AI Copy Polish 2026-08-26';
})();

/* SWSI Theory Trust Batch 1 2026-08-26
   Official exam questions are immutable. This layer only corrects SWSI-authored theory cards.
*/
(function(){
  'use strict';

  var CHECKED_AT='2026-08-26';
  var VERIFY_CHECKED='checked';
  var VERIFY_PENDING='needs_review';
  var rows=window.THEORIES||[];

  function E(v){
    if(typeof window.swsiEsc==='function')return window.swsiEsc(v);
    if(typeof window.esc==='function')return window.esc(v);
    return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }
  function byName(name){return rows.find(function(x){return x&&x.n===name;})||null;}
  function patch(name,data){
    var x=byName(name);if(!x)return null;
    Object.keys(data||{}).forEach(function(k){x[k]=data[k];});
    return x;
  }
  function add(row){
    if(!row||!row.n||byName(row.n))return byName(row.n);
    rows.push(row);return row;
  }
  function verified(data){
    return Object.assign({theory_verify_status:VERIFY_CHECKED,theory_checked_at:CHECKED_AT},data||{});
  }

  // Existing cards are SWSI study notes. Unless this layer explicitly reviews one,
  // do not present it as already checked.
  rows.forEach(function(t){
    if(t&& !t.theory_verify_status)t.theory_verify_status=VERIFY_PENDING;
  });

  patch('生態系統理論',verified({
    s:'Urie Bronfenbrenner',
    c:'Bronfenbrenner 的生態系統理論把發展放在多層環境脈絡中理解：微視系統是個人直接參與的場域；中介系統是不同微視場域之間的關係；外部系統是個人未必直接參與、卻會影響其生活的場域；鉅視系統包括文化、價值、制度與社會結構；時間系統則提醒生命歷程與歷史變遷也會改變發展。',
    a:'題目明確要你分析「不同環境層次」時，可以依微視→中介→外部→鉅視→時間逐層整理。但不要把 Bronfenbrenner、生態觀點、人在環境（PIE）和 Germain／Gitterman 的生活模型全部當成同一套理論；若題目指定「生活模型」，要改談人與環境的適配、生活壓力與轉銜、環境資源等社工實務概念。',
    k:['微視/中介/外部/鉅視','時間系統','環境脈絡','系統互動','不等同生活模型'],
    theory_trust_note:'Bronfenbrenner 的發展生態系統、社工的生態觀點與 Germain／Gitterman 生活模型彼此相關，但來源、目的與常用概念並不完全相同。'
  }));

  patch('增強權能觀點',verified({
    s:'Barbara Solomon、Lorraine Gutiérrez 等',
    c:'增強權能（empowerment）關注權力與無力感如何由個人經驗、人際關係，以及制度與結構共同形成。它既可理解為一個參與、取得資源與增加控制感的過程，也可關注服務使用者是否更能影響與自己有關的決策。社工不是「把權力送給案主」，而是和案主建立合作關係，減少資訊與制度障礙，增加選擇、資源取得、參與及倡議的空間。',
    a:'先問：目前哪些決定由誰掌握？案主缺的是資訊、選擇、資源、發聲管道，還是受到制度性障礙？再從個人、人際、組織／社區或政治結構層次提出合作、共同決策、資源連結與倡議。不是所有困難都要硬解釋成「受壓迫」，要回到題目證據。',
    k:['權力/無力感','參與與選擇','共同決策','資源取得','個人到結構層次'],
    theory_trust_note:'增權與優勢觀點常一起使用，但增權更直接處理權力、參與、資源與制度障礙；兩者不是同義詞。'
  }));

  patch('優勢觀點',verified({
    s:'Dennis Saleebey；Charles Rapp 等',
    c:'優勢觀點要求評估不只看問題與缺陷，也要看個人、家庭與環境中的能力、興趣、過往成功、希望、關係與可動用資源。它不是否認創傷、暴力、自殺風險或實際困難，而是避免把「問題」當成案主的全部。',
    a:'實務上可以同時做安全／風險評估，再和案主盤點「已經做得到什麼、曾經怎麼撐過、誰願意支持、有哪些資源、希望往哪裡走」。不要為了寫優勢觀點而把真正的危險淡化。',
    k:['能力與資源','希望與目標','過往成功','去病理化','風險與優勢並看'],
    theory_trust_note:'優勢、復原力、增強權能彼此可以連結，但不是三個可以互換名稱的概念。Saleebey 是優勢觀點的重要代表；Rapp 的工作則和優勢模式／個案管理密切相關。'
  }));

  patch('復原力觀點',verified({
    s:'resilience research；Norman Garmezy、Emmy Werner 等',
    c:'復原力不是一種「天生很能撐」的固定人格，而是在顯著逆境下仍能維持、恢復或重新形成適應的動態歷程。結果會受到危險因子與保護因子，以及個人、家庭、同儕、學校與社區環境持續互動的影響。',
    a:'作答時先指出「逆境是什麼」與「要觀察的適應結果是什麼」，再分析危險／保護因子。處遇不只是叫案主更堅強，也可以降低環境風險、增加可信任關係、資源、能力與社會連結。',
    k:['逆境中的適應','動態歷程','危險因子','保護因子','個人與環境互動'],
    theory_trust_note:'復原力可以是優勢評估的一部分，但不等於「列出案主優點」；它的核心是逆境、適應與保護／危險機制之間的動態關係。'
  }));

  // Keep the umbrella card for backwards compatibility/search, but stop mixing schools.
  patch('家庭系統理論',verified({
    s:'家庭系統取向（不同學派各有重點）',
    c:'家庭系統取向把家庭視為相互依賴的互動系統：一位成員的行為改變，會透過循環互動、回饋、家庭規則與維持平衡的過程影響其他成員。不同家庭治療學派使用的概念並不相同：Bowen 重視自我分化、三角關係與多世代情緒歷程；Minuchin 的結構取向則重視次系統、界限、階層、聯盟與家庭結構。',
    a:'題目只寫「家庭系統」時，可先談整體性、相互依賴、循環因果、回饋與家庭規則。若題目出現「自我分化、三角關係、多世代傳遞」，轉用 Bowen；若出現「次系統、界限、階層、跨代聯盟」，轉用 Minuchin。不要把兩派名詞全部塞在同一段。',
    k:['整體性','相互依賴','循環因果','回饋/恆定','Bowen ≠ Minuchin'],
    theory_trust_note:'舊版把 Bowen 與 Minuchin 的核心名詞混在同一張卡。現在保留「家庭系統」總覽，並另外拆成兩張學派卡。'
  }));

  add(verified({
    n:'Bowen 家庭系統理論',d:'家庭',s:'Murray Bowen',
    c:'Bowen 把家庭視為情緒系統。常考概念包括自我分化、三角關係、核心家庭情緒歷程、家庭投射、多世代傳遞與情緒截斷；核心問題之一是人在親密連結中如何維持相對清楚的自我。',
    a:'遇到跨世代模式、三角關係、家庭焦慮或成員難以在親密與自主間取得平衡時可使用。家系圖有助於觀察多世代關係，但不要看到衝突就直接替家庭貼上「低分化」標籤。',
    k:['自我分化','三角關係','多世代傳遞','家庭投射','情緒截斷'],
    theory_trust_note:'三角關係、自我分化與多世代情緒歷程是 Bowen 取向的代表概念，不應和 Minuchin 的界限／次系統混成同一理論。'
  }));

  add(verified({
    n:'Minuchin 結構家庭治療',d:'家庭',s:'Salvador Minuchin',
    c:'結構家庭治療關注家庭互動如何組織成相對穩定的結構，常用次系統、界限、階層、聯盟／結盟等概念理解關係。界限可呈現較清楚、過度擴散或過度僵化等狀態，介入重點是改變互動與家庭結構，而不是只修理某一個「有問題的人」。',
    a:'題目出現夫妻／親子次系統、界限不清、跨代聯盟、權力階層或家庭結構重整時可用。分析時要描述「誰和誰如何互動」，不要只把界限寫成抽象標籤。',
    k:['次系統','界限','階層','聯盟/結盟','家庭結構重整'],
    theory_trust_note:'次系統、界限、階層與結構重整屬 Minuchin 結構取向的核心語彙，和 Bowen 的自我分化／三角概念要分開。'
  }));

  patch('依附理論',verified({
    s:'John Bowlby、Mary Ainsworth；Main & Solomon（紊亂／失序型）',
    c:'Bowlby 建構依附理論，Ainsworth 以陌生情境研究描述安全型、逃避型與抗拒／矛盾型等依附組織；紊亂／失序型則是在後續研究中由 Main 與 Solomon 加以提出與系統化。早期依附經驗會影響孩子對自己、他人與關係的「內在運作模式」，但不是一旦形成就終身不能改變。',
    a:'兒少保護、安置、收出養與早期創傷題可用。題目只有一小段行為描述時，不宜直接「診斷」孩子是哪一型；應看照顧是否穩定可預測、孩子尋求安慰與探索的方式、分離重聚反應，以及更完整的關係史。',
    k:['安全/不安全依附','陌生情境','內在運作模式','照顧可預測性','紊亂型為後續分類'],
    theory_trust_note:'Ainsworth 的經典陌生情境先形成三類分類；紊亂／失序型是後續由 Main 與 Solomon 等研究者發展出的第四類。'
  }));

  patch('Erikson心理社會發展理論',verified({
    s:'Erik Erikson',
    c:'Erikson 以生命全程八個心理社會階段描述發展，每一階段都有一組需要整合的心理社會張力，例如青少年的「認同 vs. 角色混淆」。這裡的「危機」是發展上的張力與課題，不等於精神疾病或必然失敗；各階段常見年齡是大致範圍，不是硬切的診斷界線。',
    a:'先看題目明示的年齡、生活情境與主要發展任務，再用相對應的心理社會張力分析。不要只因為「15歲」就下結論說他一定處於某種失敗狀態；同一階段也可能同時存在兩端經驗，前一階段的議題也可能持續影響後續。',
    k:['生命全程八階段','心理社會張力','認同vs角色混淆','發展任務','年齡為大致範圍'],
    theory_trust_note:'Erikson 的階段很適合整理發展任務，但不應把年齡表當成臨床診斷表，也不是某階段「解決一次就永遠結束」。'
  }));

  patch('精神分析理論',verified({
    s:'Sigmund Freud',
    c:'Freud 的精神分析同時涉及無意識、心理衝突、防衛機轉與本我／自我／超我等人格動力；另一條常考線是心理性慾發展，通常分為口腔期、肛門期、性器期、潛伏期與生殖期。這兩組概念相關，但題目問「人格結構」和問「發展階段」時，答題重點不同。',
    a:'題目指定 Freud 的發展階段時，先回答心理性慾階段及該階段關注；題目問人格或心理動力時，再談本我／自我／超我、無意識衝突與防衛機轉。不要把「某個行為」單憑一段描述就硬解釋成某階段固著。',
    k:['本我/自我/超我','無意識','防衛機轉','心理性慾五階段','發展≠人格結構'],
    theory_trust_note:'舊卡把人格結構與心理性慾發展放得太近，現在明確區分「題目問哪一條線，就答哪一條線」。'
  }));

  patch('Piaget認知發展理論',verified({
    s:'Jean Piaget',
    c:'Piaget 將認知發展概括為感覺動作、前運思、具體運思與形式運思四個階段；認知改變涉及基模、同化、調適與平衡化。常見年齡範圍是理解發展順序的參考，不是硬性的診斷門檻；即使進入青春期，也不表示在所有任務與情境都會穩定使用形式運思。',
    a:'先分辨題目是在問「階段名稱」還是「認知能力」。除了年齡，最好用題目中的實際表現佐證，例如物體恆存、守恆、具體邏輯、抽象思考或假設演繹。',
    k:['四階段','基模','同化/調適','平衡化','年齡非硬切點'],
    theory_trust_note:'年齡可以幫助定位典型階段，但不能只靠生日判定一個人的整體認知能力。'
  }));

  patch('Kohlberg道德發展理論',verified({
    s:'Lawrence Kohlberg',
    c:'Kohlberg 以三層次六階段描述「人如何說明一件事為什麼是對或錯」的道德推理：前習俗、習俗與後習俗。重點是判斷背後的理由，而不是只看一個人的行為好不好。階段與發展有關，但年齡不保證一個人一定到達哪一階段，後習俗層次也不是人人必然達到。',
    a:'如果正式題目已指定某個階段，先依題目要求回答；一般案例則不要看到「青少年」就直接判定一定在習俗後期或正走向後習俗。可以從他如何解釋規則、關係、法律、權利與原則，判斷道德推理的特徵。',
    k:['三層次六階段','道德推理理由','前習俗/習俗/後習俗','Heinz困境','年齡不等於階段'],
    theory_trust_note:'Kohlberg 測的是道德判斷的推理結構，不是把年齡直接換算成固定階段；理論也受到性別與文化普遍性方面的批評。'
  }));

  patch('任務中心模式',verified({
    s:'William J. Reid、Laura Epstein',
    c:'任務中心模式是一種短期、結構化、聚焦於特定目標問題的社會工作方法。社工與案主共同選定要處理的問題、訂出可觀察的目標，再把目標轉成雙方同意且可執行的任務；過程中持續檢查進度、阻礙與結果。',
    a:'不是社工替案主列一張待辦清單。答題可寫：共同界定目標問題→共同設定目標→規劃與協議任務→執行並檢討障礙→評估與結案。它通常是時限性的短期工作，但不要把「6–12次」背成所有情境都不能改的固定規則。',
    k:['共同界定問題','共同目標','具體任務','時限與結構','持續檢討評估'],
    theory_trust_note:'核心不是「任務越多越好」，而是問題與目標要由案主和社工共同確認，任務要直接服務於目標問題。'
  }));

  patch('危機介入模式',verified({
    s:'Gerald Caplan；Albert R. Roberts 等',
    c:'危機是壓力事件超出當事人當下可用的因應方式與支持資源，而出現急性失衡的狀態。介入首先要評估安全、致命風險與急迫危險，再建立工作關係、釐清觸發事件、協助穩定情緒與功能、探索可行替代方案，形成具體行動及後續追蹤。',
    a:'自殺、家暴、重大事故等題目先寫「安全與風險評估優先」。不要只背一個模糊的「黃金期」就跳到處遇；目標是先穩定、增加可用因應與支持並形成下一步，不必假設每個人都一定要恢復成危機前完全一樣的狀態。',
    k:['安全/致命風險評估','急性失衡','穩定與支持','替代方案/行動計畫','追蹤'],
    theory_trust_note:'危機介入強調迅速、主動與聚焦，但沒有一個適用所有危機的固定「黃金時數」可取代風險評估與臨床判斷。'
  }));

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
    version:'SWSI Theory Trust Batch 1 2026-08-26',
    checkedAt:CHECKED_AT,
    verifiedCount:function(){return rows.filter(function(t){return t&&t.theory_verify_status===VERIFY_CHECKED;}).length;},
    totalCount:function(){return rows.length;}
  };
})();

/* SWSI Theory Trust Erikson Name Fix 2026-08-26
   Corrects only the SWSI-authored theory-card lookup. Official exam questions remain untouched.
*/
(function(){
  'use strict';
  var rows=window.THEORIES||[];
  var t=rows.find(function(x){return x&&x.n==='Erikson 心理社會發展';});
  if(!t)return;
  Object.assign(t,{
    s:'Erik Erikson',
    c:'Erikson 以生命全程八個心理社會階段描述發展，每一階段都有一組需要整合的心理社會張力，例如青少年的「認同 vs. 角色混淆」。這裡的「危機」是發展上的張力與課題，不等於精神疾病或必然失敗；各階段常見年齡是大致範圍，不是硬切的診斷界線。',
    a:'先看題目明示的年齡、生活情境與主要發展任務，再用相對應的心理社會張力分析。不要只因為「15歲」就下結論說他一定處於某種失敗狀態；同一階段也可能同時存在兩端經驗，前一階段的議題也可能持續影響後續。',
    k:['生命全程八階段','心理社會張力','認同vs角色混淆','發展任務','年齡為大致範圍'],
    theory_verify_status:'checked',
    theory_checked_at:'2026-08-26',
    theory_trust_note:'Erikson 的階段很適合整理發展任務，但不應把年齡表當成臨床診斷表，也不是某階段「解決一次就永遠結束」。'
  });
  window.SWSI_THEORY_ERIKSON_NAME_FIX='SWSI Theory Trust Erikson Name Fix 2026-08-26';
})();

/* SWSI Theory Trust Stage Name Fix 2026-08-26
   Exact-name corrections for SWSI-authored theory cards only. Official exam questions remain untouched.
*/
(function(){
  'use strict';
  var rows=window.THEORIES||[];
  function patch(name,data){
    var t=rows.find(function(x){return x&&x.n===name;});
    if(!t)return false;
    Object.assign(t,data,{theory_verify_status:'checked',theory_checked_at:'2026-08-26'});
    return true;
  }

  patch('Erikson 心理社會發展理論',{
    s:'Erik Erikson',
    c:'Erikson 以生命全程八個心理社會階段描述發展，每一階段都有一組需要整合的心理社會張力，例如青少年的「認同 vs. 角色混淆」。這裡的「危機」是發展上的張力與課題，不等於精神疾病或必然失敗；各階段常見年齡是大致範圍，不是硬切的診斷界線。',
    a:'先看題目明示的年齡、生活情境與主要發展任務，再用相對應的心理社會張力分析。不要只因為「15歲」就下結論說他一定處於某種失敗狀態；同一階段也可能同時存在兩端經驗，前一階段的議題也可能持續影響後續。',
    k:['生命全程八階段','心理社會張力','認同vs角色混淆','發展任務','年齡為大致範圍'],
    theory_trust_note:'Erikson 的階段很適合整理發展任務，但不應把年齡表當成臨床診斷表，也不是某階段「解決一次就永遠結束」。'
  });

  patch('Piaget 認知發展理論',{
    s:'Jean Piaget',
    c:'Piaget 將認知發展概括為感覺動作、前運思、具體運思與形式運思四個階段；認知改變涉及基模、同化、調適與平衡化。常見年齡範圍是理解發展順序的參考，不是硬性的診斷門檻；即使進入青春期，也不表示在所有任務與情境都會穩定使用形式運思。',
    a:'先分辨題目是在問「階段名稱」還是「認知能力」。除了年齡，最好用題目中的實際表現佐證，例如物體恆存、守恆、具體邏輯、抽象思考或假設演繹。',
    k:['四階段','基模','同化/調適','平衡化','年齡非硬切點'],
    theory_trust_note:'年齡可以幫助定位典型階段，但不能只靠生日判定一個人的整體認知能力。'
  });

  patch('Kohlberg 道德發展理論',{
    s:'Lawrence Kohlberg',
    c:'Kohlberg 以三層次六階段描述「人如何說明一件事為什麼是對或錯」的道德推理：前習俗、習俗與後習俗。重點是判斷背後的理由，而不是只看一個人的行為好不好。階段與發展有關，但年齡不保證一個人一定到達哪一階段，後習俗層次也不是人人必然達到。',
    a:'如果正式題目已指定某個階段，先依題目要求回答；一般案例則不要看到「青少年」就直接判定一定在習俗後期或正走向後習俗。可以從他如何解釋規則、關係、法律、權利與原則，判斷道德推理的特徵。',
    k:['三層次六階段','道德推理理由','前習俗/習俗/後習俗','Heinz困境','年齡不等於階段'],
    theory_trust_note:'Kohlberg 測的是道德判斷的推理結構，不是把年齡直接換算成固定階段；理論也受到性別與文化普遍性方面的批評。'
  });

  window.SWSI_THEORY_STAGE_NAME_FIX='SWSI Theory Trust Stage Name Fix 2026-08-26';
})();

/* SWSI Theory Trust Batch 2 2026-08-26
   Practice methods, values and critical perspectives. Official exam questions remain immutable.
*/
(function(){
  'use strict';
  var CHECKED_AT='2026-08-26';
  var rows=window.THEORIES||[];
  function patch(name,data){
    var t=rows.find(function(x){return x&&x.n===name;});
    if(!t)return false;
    Object.assign(t,data,{theory_verify_status:'checked',theory_checked_at:CHECKED_AT});
    return true;
  }

  patch('社會工作價值與專業倫理',{
    s:'臺灣《社會工作師倫理守則》；IFSW 全球社會工作倫理原則',
    c:'社會工作倫理不是背幾個漂亮口號，而是在尊重人的尊嚴、人權、社會正義、自我決定、參與、隱私與保密、專業誠信等價值之間做負責任的專業判斷。臺灣現行社會工作師倫理守則由社會工作師公會全國聯合會訂定並經主管機關核備，實務還要同時遵守法律、專業角色與機構責任。',
    a:'倫理題先分清楚「專業價值／倫理守則、法律義務、機構規定、服務使用者權益」各自是什麼，再看彼此是否衝突。自我決定與保密都很重要，但不是無條件絕對；遇到法定通報、重大安全風險或權利衝突時，要回到法源、比例與最小侵害等判斷。',
    k:['人的尊嚴','人權與社會正義','自我決定','隱私與保密','專業誠信'],
    theory_trust_note:'倫理不是單一理論，也不是「自決永遠第一」或「任何資料都不能說」。國考案例要把倫理原則、法律義務、權利衝突與專業判斷分開寫。'
  });

  patch('倫理兩難與抉擇',{
    s:'倫理決策架構（多種版本；非單一固定公式）',
    c:'倫理兩難是兩個以上重要倫理價值、權利或責任彼此衝突，而不是「我不知道該怎麼辦」就一定叫倫理兩難。實務可依序釐清事實與利害關係人、辨識衝突的倫理原則與法律義務、列出可行方案與可能傷害／利益、諮詢督導或專業資源、選擇較能保障權益且侵害較小的方案，並留下決策與後續評估紀錄。',
    a:'考題若指定 Reamer、Dolgoff 等架構，就照題目指定的方法回答；沒有指定時，不需要假裝全世界只有一套「標準七步」。先寫清楚衝突在哪，再說你如何查守則／法律、比較方案、諮詢、決策與紀錄。',
    k:['事實與利害關係人','價值/權利衝突','法律與倫理區分','方案與後果','諮詢/紀錄/評估'],
    theory_trust_note:'倫理決策有多種架構。SWSI 不把其中一套模板包裝成唯一正確公式；正式題目若指定學者或模式，以題目為準。'
  });

  patch('社會學習理論',{
    s:'Albert Bandura',
    c:'Bandura 的社會學習／社會認知取向指出，人可以透過觀察他人的行為及其後果而學習，不必每次都親身受到獎懲。常考概念包括示範／模仿、觀察學習的注意—保留—動作再現—動機歷程、自我效能，以及個人因素、行為與環境之間的交互影響。',
    a:'案例若出現同儕、家人、媒體或重要他人的示範，可分析「看到了什麼榜樣、注意與記住了什麼、是否有能力再現、什麼後果讓他願意做」。不要把社會學習理論縮成「獎勵就增加、處罰就減少」；那會把觀察學習與認知因素漏掉。',
    k:['觀察學習','示範/模仿','注意-保留-再現-動機','自我效能','人-行為-環境交互作用'],
    theory_trust_note:'Bandura 的取向和行為主義有連結，但不等於單純操作制約；觀察、認知、自我效能與環境互動都是核心。'
  });

  patch('綜融取向與四系統模型',{
    s:'Allen Pincus、Anne Minahan',
    c:'Pincus 與 Minahan 以四個基本系統幫助社工看清楚「誰在求助、誰要改變、誰一起行動、誰負責推動改變」：改變媒介系統是社工及其所屬的專業服務系統；案主系統是和社工建立工作協議並預期受益的人；標的系統是為達成目標而需要被影響或改變的人／組織／制度；行動系統則是和社工合作完成改變任務的人。',
    a:'四個系統不是四種固定身分。同一個人或單位在不同目標下可能扮演不同系統角色，而且案主系統不一定等於標的系統。答題時先寫「本案要改變的目標是什麼」，再依這個目標辨認四系統。',
    k:['改變媒介系統','案主系統','標的系統','行動系統','案主不一定是標的'],
    theory_trust_note:'四系統是社會工作實務分析框架；最常見陷阱是把「案主系統＝標的系統」或把角色當成永遠固定。'
  });

  patch('認知行為理論',{
    s:'Aaron Beck、Albert Ellis 等認知與行為取向',
    c:'認知行為取向關注情境、認知、情緒、生理反應與行為如何互相影響。介入通常是合作、目標導向與結構化的：辨識困擾情境與想法、檢視證據與替代解釋、練習新的因應或行為，並透過實際經驗修正原有模式。不同 CBT 學派的用語和技術不完全相同。',
    a:'不要把 CBT 寫成「叫案主正向思考」。題目若給自動化想法、逃避、焦慮或反覆失敗行為，可以先找觸發情境→想法／信念→情緒與行為→後果，再設計可測試的小步驟。若題目指定 Beck 或 Ellis，應使用該取向的概念，不要混成一包。',
    k:['認知-情緒-行為互動','自動化想法','合作實證','行為練習','不是正向思考'],
    theory_trust_note:'「認知行為」是一大類取向；Beck 認知治療、Ellis REBT 與各種行為技術有共同處也有差異，正式題目指定學者時需分開回答。'
  });

  patch('心理暨社會學派',{
    s:'Florence Hollis、Mary Woods；源自社會個案工作傳統',
    c:'心理暨社會學派強調「人在情境中」：理解個人的心理功能，同時分析家庭關係、社會角色、經濟與環境條件，以及過去經驗如何影響現在的適應。評估重點不是只往童年找原因，也不是只看外在資源，而是把個人內在與社會情境一起理解。',
    a:'案例題可從目前問題與壓力、重要關係與角色、環境資源／限制、發展與過往經驗，以及個人的因應與功能共同評估；介入也可同時包含直接與案主工作，以及間接調整環境／連結資源。',
    k:['人在情境中','心理與社會雙重評估','關係/角色','過往與現在','直接與環境介入'],
    theory_trust_note:'心理暨社會學派受到精神動力傳統影響，但不能簡化成「做精神分析」；社會情境與環境介入同樣是核心。'
  });

  patch('個案管理',{
    s:'社會服務方法／服務輸送策略（非單一理論）',
    c:'個案管理用來協助有多重、持續或跨系統需求的服務使用者取得並整合服務。常見功能包括接案與需求評估、共同擬定服務計畫、資源連結與轉介、跨專業協調、權益倡導、監測服務執行、再評估與結案。不同機構與模式對「經紀、臨床、優勢、密集」等角色比重會不同。',
    a:'不要把個案管理等同「幫忙轉介」。先看需求有沒有跨機構、服務是否碎片化、誰負責整合與追蹤，再說如何和案主共同排序需求、連結資源、協調、監測成效與調整計畫。',
    k:['需求評估','服務計畫','資源連結','協調/倡導','監測與再評估'],
    theory_trust_note:'個案管理是一種服務方法／策略，不是一套單一創始人的理論；考題若指定某種個案管理模式，再依該模式回答。'
  });

  patch('Biestek 專業關係原則',{
    s:'Felix P. Biestek',
    c:'Biestek 的個案工作關係七原則包括：個別化、有目的的情感表達、適度的情感涉入、接納、非批判態度、案主自我決定及保密。這些原則用來理解助人關係需要回應的基本需求，但不代表社工可以忽略法律、風險與專業界限。',
    a:'題目問專業關係時，可逐一辨認哪一個原則被遵守或違反。特別注意：自我決定不是「案主說什麼都照做」，保密也不是「任何情況都不能揭露」；需結合能力、權利、安全風險與法定義務。',
    k:['個別化','有目的情感表達','適度情感涉入','接納/非批判','自決/保密'],
    theory_trust_note:'七原則是經典個案工作關係框架；現代社工實務仍需放回人權、社會情境、法律義務與權力關係一起理解。'
  });

  patch('家庭生命週期理論',{
    s:'Monica McGoldrick、Betty Carter 等家庭生命週期取向',
    c:'家庭生命週期用「發展轉銜」理解家庭：例如離家成為成人、伴侶形成、育兒、子女進入青少年、子女離家與晚年等階段都會帶來角色、界限、關係與照顧責任的重新調整。不同版本的階段數量與名稱可能不同，且真實家庭也會受到離婚、再婚、單親、多元家庭、移民、疾病與文化脈絡影響。',
    a:'作答不要先拿一張「標準家庭階段表」硬套。先看家庭目前正經歷什麼轉銜、原本關係與角色要怎麼重新協商、有哪些同時發生的壓力，再用生命週期概念分析。',
    k:['家庭發展轉銜','角色重整','界限與關係','階段任務','多元家庭/文化脈絡'],
    theory_trust_note:'Carter／McGoldrick 的階段架構是理解轉銜的工具，不是判定「正常家庭」的唯一標準；不同家庭形式不必走同一條線性路徑。'
  });

  patch('反壓迫觀點',{
    s:'反壓迫社會工作（Lena Dominelli、Neil Thompson 等不同脈絡）',
    c:'反壓迫觀點關注權力如何透過制度、政策、組織、文化規範與日常互動製造或維持不平等，並要求社工也反思自己的專業權力與位置。實務不只協助個人適應，也要增加服務使用者參與、減少服務障礙、挑戰歧視性做法，必要時進行倡議或制度改變。',
    a:'先從題目證據找「誰有決定權、誰較難取得資源、哪些規則或偏見造成障礙」，再提出參與、共同決策、可近性、倡議等策略。不要預設所有個人問題都只能用壓迫解釋，也不要把社工寫成替弱勢者發言的救世主。',
    k:['權力與特權','制度性壓迫','反思專業權力','參與/共同決策','倡議與結構改變'],
    theory_trust_note:'反壓迫是一種批判性的實務取向，不是看到弱勢身分就自動得出同一結論；分析仍要有案例中的權力與制度證據。'
  });

  patch('女性主義觀點',{
    s:'女性主義社會工作（多種學派；非單一理論）',
    c:'女性主義社會工作分析性別化的權力、角色期待、照顧分工、暴力與制度如何影響個人生活，並強調把「個人經驗」連回社會與政治結構。當代取向也重視交織性：性別會和階級、族群、年齡、障礙、性／別身分等共同作用。',
    a:'不要把女性主義寫成「只服務女性」或「男性一定是壓迫者」。案例要看具體的性別權力、資源控制、角色規範與制度安排，並透過合作、增權、支持網絡與制度倡議減少不平等。',
    k:['性別化權力','個人即政治','交織性','平等與參與','結構改變'],
    theory_trust_note:'女性主義內部有自由、基進、社會主義、後現代與交織性等不同取向；SWSI 只整理共同的國考辨識重點，不把女性視為單一同質群體。'
  });

  patch('文化能力',{
    s:'跨文化實務；並結合 Tervalon & Murray-García 的文化謙遜概念',
    c:'文化能力要求社工持續提升對自身文化位置與偏見的覺察、了解不同社群的歷史與社會脈絡，並調整溝通、評估與服務方式。但文化不是一本可以背完的固定知識庫；文化謙遜進一步強調終身自我反思、看見助人關係中的權力不平衡，並和服務使用者及社群建立互惠合作。',
    a:'遇到移民、原住民族、宗教、性／別或跨文化案例時，先問「對這位當事人而言，什麼身分與文化經驗最重要」，必要時使用通譯與文化資源，檢查機構服務有沒有可近性障礙；不要靠族群標籤猜他的價值觀。',
    k:['文化自我覺察','文化脈絡','適切溝通','文化謙遜','權力反思/終身學習'],
    theory_trust_note:'「有文化能力」不等於把每個族群特徵背熟。文化謙遜提醒專業人員持續自我評估、修正權力不平衡並避免把文化刻板化。'
  });

  patch('障礙的社會模式',{
    s:'障礙者運動／UPIAS；Mike Oliver 推廣「社會模式」概念',
    c:'障礙社會模式把「個人的損傷或身體／心智差異」和「社會造成的障礙」區分開來，強調不友善的環境、制度、資訊、交通、偏見與排除會把差異轉化成參與限制。社工因此不能只問「這個人要怎麼被治好」，也要問「環境與制度要怎麼移除障礙」。',
    a:'案例可從無障礙環境、資訊與溝通可近性、合理調整、教育／就業機會、決策參與與歧視分析。社會模式不是否認疼痛、疾病、支持需求或醫療的價值，而是反對把所有限制都歸咎於個人缺陷。',
    k:['損傷vs社會障礙','環境/制度障礙','參與與可近性','合理調整','不是否定醫療需求'],
    theory_trust_note:'UPIAS 的障礙社會解釋是重要思想來源，Mike Oliver 後續提出／推廣「social model」用語；它和 ICF 的生物心理社會架構不宜混成同一模型。'
  });

  patch('結構社會工作／批判理論',{
    s:'結構社會工作與批判傳統（如 Maurice Moreau、Bob Mullaly 等）',
    c:'結構／批判取向認為個人的困境經常和階級、不平等、政策、勞動市場、父權、種族化或其他制度性權力關係相連。它要求社工不要只把問題個人化，同時仍需回應個人的立即需要與選擇，並在可行時結合倡議、集體行動與制度改革。',
    a:'題目若有貧窮、住房、勞動剝削、福利污名或制度排除，可把微觀經驗連回資源分配與制度。但不要把所有心理、人際或家庭困難都化約成「都是結構的錯」；好的答案會同時看到個人能動性與結構限制。',
    k:['個人問題社會化','結構性不平等','權力/資源分配','倡議與集體行動','個人能動性+結構限制'],
    theory_trust_note:'結構社會工作與廣義批判理論有共同關懷，但並非完全同一套理論；本卡整理的是國考最常用的共同分析方向。'
  });

  if(window.SWSI_THEORY_TRUST){
    window.SWSI_THEORY_TRUST.batch2='SWSI Theory Trust Batch 2 2026-08-26';
  }
})();

/* SWSI Theory Trust Final Batch 2026-08-26
   Final review of SWSI-authored theory cards. Official exam questions remain immutable.
*/
(function(){
  'use strict';
  var CHECKED_AT='2026-08-26';
  var rows=window.THEORIES||[];

  function byName(name){return rows.find(function(x){return x&&x.n===name;})||null;}
  function patch(name,data){
    var t=byName(name);
    if(!t)return false;
    Object.assign(t,data||{},{theory_verify_status:'checked',theory_checked_at:CHECKED_AT});
    return true;
  }
  function add(data){
    if(!data||!data.n)return null;
    var old=byName(data.n);
    if(old){Object.assign(old,data,{theory_verify_status:'checked',theory_checked_at:CHECKED_AT});return old;}
    var row=Object.assign({},data,{theory_verify_status:'checked',theory_checked_at:CHECKED_AT});
    rows.push(row);return row;
  }

  patch('Rothman 社區工作三模式',{
    s:'Jack Rothman（經典三模式分類；後續版本持續修訂）',
    c:'Rothman 的經典社區組織三模式是三種理想型：地方發展（locality development）重視廣泛居民參與、能力建立與共識；社會計畫／政策（social planning/policy）較重視資料、專業分析與理性規劃；社會行動（social action）則關注權力與資源不均，透過組織、倡議與集體行動爭取改變。三者在改變目標、對問題的假設、策略、權力觀與工作者角色上不同。',
    a:'先依題目判斷主要問題是「居民參與與社區能力不足」、「需要專業規劃解決複雜問題」，還是「權力／資源不均需要倡議動員」，再選模式並寫工作者角色。實務可以混合運用；三模式不是依序必經的三個階段，也不是彼此絕對排斥。',
    k:['地方發展','社會計畫/政策','社會行動','居民參與','權力與資源','理想型非固定階段'],
    theory_trust_note:'國考常用的是 Rothman 經典三模式作為比較架構。它們是理想型，不是「先地方發展→再社會計畫→最後社會行動」的固定流程。'
  });

  patch('資產基礎社區發展 ABCD',{
    s:'John Kretzmann、John McKnight',
    c:'資產基礎社區發展（ABCD）從「社區已經擁有什麼」出發，而不只從缺陷與需求清單出發。常見資產包括居民個人的才能與能力、在地協會／非正式網絡、地方機構，以及可動員的空間、經濟與其他在地資源；重點是居民主導、建立關係、連結資產並由內而外形成集體行動。',
    a:'社區題可先盤點個人能力→協會／網絡→地方機構與其他在地資產，再說如何建立連結與居民參與。ABCD 不是假裝社區「沒有需求」，也不是拒絕外部資源；外部支持應補強而非取代在地能力。',
    k:['Kretzmann & McKnight','居民主導','資產盤點','協會與機構','由內而外','不是否認需求'],
    theory_trust_note:'ABCD 的「社區資產」不等於 Sherraden 所談的個人／家庭金融資產建構。兩者都使用 asset 一詞，但理論脈絡與政策工具不同。'
  });

  patch('團體發展階段理論',{
    s:'Bruce Tuckman；Garland、Jones & Kolodny（不同模型）',
    c:'團體發展有不同階段模型，不能把名稱混成同一套。Tuckman 原提出形成（forming）→風暴（storming）→規範（norming）→表現（performing），後與 Jensen 加入解散（adjourning）。社會團體工作常見 Garland、Jones 與 Kolodny 的模型則以聚集前／接近（preaffiliation）、權力與控制、親密、分化、分離等階段描述團體歷程。',
    a:'題目若指定 Tuckman，就依 forming→storming→norming→performing→adjourning；若指定 Garland 等人的社會團體工作階段，就依該模型回答。階段是理解團體動力的指引，不代表每個團體都線性、整齊地走過；可能重疊、停留或回到先前議題。',
    k:['Tuckman','形成/風暴/規範/表現/解散','Garland','權力與控制','親密/分化/分離','不同模型不可混用'],
    theory_trust_note:'舊版把 Tuckman 與 Garland 等人的階段名稱併成一套。現在明確分開；兩者不是彼此的中英文翻譯。'
  });

  patch('社會學三大觀點',{
    s:'結構功能論、衝突觀點、符號互動論（不同理論傳統）',
    c:'結構功能論主要從鉅觀層次看社會各部分如何相互依存、維持秩序，並分析顯性／潛在功能與失功能；衝突觀點主要從鉅觀層次追問權力、利益與稀少資源如何不均分配，以及制度較有利於誰；符號互動論則主要從微觀層次看人在互動中如何透過語言、符號與詮釋建構並協商意義。',
    a:'同一社會問題可分別問：它對制度秩序產生什麼功能／失功能？誰掌握較多資源與定義問題的權力？當事人在互動中如何形成標籤、身分與意義？不要把三者都寫成「宏觀理論」；符號互動論的主要分析層次是微觀互動。',
    k:['結構功能論','功能/失功能','衝突與權力','資源不均','符號互動','微觀意義建構'],
    theory_trust_note:'「三大觀點」是入門比較框架，不代表每個傳統內只有一位學者或只有一種版本。最大的常見錯誤是把符號互動論也寫成鉅觀觀點。'
  });

  patch('福利意識形態',{
    s:'Vic George、Paul Wilding（經典分類）',
    c:'George 與 Wilding 的經典福利意識形態分類常整理為反集體主義（anti-collectivism）、勉強集體主義（reluctant collectivism）、費邊社會主義（Fabian socialism）與馬克思主義（Marxism）。各取向對市場、自由、平等、國家責任、福利供給與資本主義的看法不同。這是一套經典分類，不是唯一的福利意識形態地圖。',
    a:'考題若直接問 George & Wilding，可依四類比較國家角色、市場、平等與福利態度；如果題目指定「新右派、社會民主、第三條路、新自由主義」等後來的政策論述，就應直接依那些概念比較，不要硬把每個名詞一對一塞回四分類。',
    k:['反集體主義','勉強集體主義','費邊社會主義','馬克思主義','國家與市場','經典分類非唯一'],
    theory_trust_note:'George & Wilding 四分類是經典考點，但不是所有後來福利政治論述的唯一分類法。題目指定哪個意識形態，就回答哪個。'
  });

  patch('Titmuss 福利三模式',{
    s:'Richard M. Titmuss',
    c:'Titmuss 的三種社會政策理想型包括：殘補福利模式（residual welfare model），家庭與私人市場失靈後公共福利才補位；工業成就表現模式（industrial achievement-performance model），福利與工作角色、經濟表現、身分及生產體系相連；制度再分配模式（institutional redistributive model），把福利視為現代社會正常制度的一部分，依社會需要與再分配原則提供，而非只在緊急失靈時介入。',
    a:'比較制度時從「福利何時介入、依什麼資格／原則提供、與市場和工作表現的關係、再分配程度」來寫。不要把工業成就表現模式簡化成只有「繳多少就領多少」；它更廣泛地把福利連結到經濟／職業表現與地位。',
    k:['殘補福利','工業成就表現','制度再分配','家庭/市場失靈','工作與經濟表現','社會需要/再分配'],
    theory_trust_note:'三模式是分析用的理想型；真實福利國家或單一制度可能同時具有多種模式特徵，不必硬判成純粹一類。'
  });

  patch('福利混合經濟與服務輸送',{
    s:'welfare mix / welfare pluralism；service delivery',
    c:'福利混合經濟／福利多元主義主要問「福利由誰負責、提供、出資與規範」：國家、市場、志願／社區部門，以及家庭與非正式網絡都可能參與。服務輸送則更關注服務實際如何到達使用者，例如可近性、連續性、整合／協調、回應性、品質與課責。兩者相關，但不是同一個問題。',
    a:'先分清楚供給結構與輸送品質：委外、民營化、購買服務（POSC）只是可能的政策工具，不等於福利混合經濟本身；政府即使不直接生產服務，也可能仍負責出資、規範與監督。再分析是否產生服務破碎、資訊落差、城鄉差距或品質／課責問題。',
    k:['國家/市場/志願部門/家庭','福利多元主義','可近性','連續性','整合與協調','POSC是工具'],
    theory_trust_note:'不要把「誰供給」和「服務怎麼送到人手上」混成同一層次，也不要把政府委外直接等同政府退出福利責任。'
  });

  patch('資產累積與基本收入',{
    s:'比較入口：Michael Sherraden（資產建構）／基本收入文獻（UBI）',
    c:'這張卡用來比較兩條不同的經濟安全政策路徑，而不是把它們當成同一理論。Sherraden 的資產建構／資產累積取向關心弱勢者是否有制度化機會累積可長期使用的資產，例如個人發展帳戶（IDA）與配合儲蓄；無條件基本收入（UBI）則主張以定期現金、個人為單位、普遍且無條件的方式提供基本收入，不以資產調查或工作要求作為資格條件。',
    a:'若題目是發展帳戶／資產脫貧，使用 Sherraden；若題目是 UBI，就分析普遍現金給付。比較時可從「存量資產 vs 當期所得、資格條件、行政與污名、財務成本、分配效果、與既有福利關係」切入。兩者不是同一套理論，也沒有必然的互相取代關係。',
    k:['Sherraden','資產建構','IDA/配合儲蓄','UBI','普遍無條件現金','兩種不同政策路徑'],
    theory_trust_note:'舊版把資產累積與 UBI 放在同一張容易造成誤解。現在保留比較入口，並新增兩張獨立卡。'
  });

  add({
    n:'資產建構／資產累積理論',d:'社會政策',s:'Michael Sherraden',
    c:'資產建構取向指出，長期經濟安全不只受到當期所得影響，也受到家庭是否能持有並累積資產，以及制度是否提供可近的儲蓄工具、誘因、配合款與支持所影響。個人發展帳戶（IDA）是代表性政策工具之一，透過制度安排協助低所得者為教育、住宅、創業等目標累積資產。',
    a:'遇到兒少發展帳戶、IDA、配合儲蓄或「脫貧不只靠當期現金所得」的題目可用。不要寫成「所得移轉沒有用」，也不要宣稱只要有帳戶就必然脫貧；應分析制度可近性、可負擔的儲蓄能力、配合款與長期效果。',
    k:['Michael Sherraden','資產建構','個人發展帳戶 IDA','配合儲蓄','制度化累積機會','經濟安全'],
    theory_trust_note:'這裡的 asset building 是個人／家庭經濟資產政策，不等於 Kretzmann 與 McKnight 的 ABCD 社區資產發展。'
  });

  add({
    n:'無條件基本收入 UBI',d:'社會政策',s:'basic income literature；BIEN 常用定義',
    c:'基本收入通常指由政治共同體定期以現金支付給個人，具有個人性、普遍性與無條件性：不因所得或資產調查而取消資格，也不以願意工作或完成特定行為作為領取前提。不同 UBI 提案對給付金額、財源、稅制，以及是否調整其他福利的設計可以非常不同。',
    a:'作答先交代定期、現金、個人、普遍、無條件五個核心特徵，再評估財政成本、給付是否足夠、所得分配、行政簡化與污名、工作與照顧行為、以及和醫療、住宅、身障等服務／給付如何搭配。不要寫成 UBI「必然取代全部福利」或「必然讓人不工作」。',
    k:['定期','現金','個人','普遍','無條件','無資產調查/工作要求'],
    theory_trust_note:'UBI 是一組政策設計理念，不同方案差異很大；是否替代既有福利、給多少、如何籌資都不是定義本身預先決定的。'
  });

  patch('社會投資觀點',{
    s:'social investment literature；Anton Hemerijck、Jane Jenson 等',
    c:'社會投資觀點強調以生命歷程看福利政策，透過早期兒童照顧與教育、教育與技能、人力資本、工作與家庭協調、積極勞動市場與社會包容等政策，提升個人面對生命轉銜與新社會風險的能力。它不是把所有福利支出都叫「投資」，也不是主張只做預防、不再做所得保障。',
    a:'托育、兒童早期介入、教育訓練、就業與工作家庭平衡題可用。分析時除了未來生產力與就業能力，也要寫社會權、所得保障與再分配的重要性，並注意無法順利進入勞動市場者是否被忽略。社會投資與傳統社會保護常是互補，而非二選一。',
    k:['生命歷程','兒童早期投資','教育/技能','工作家庭平衡','積極勞動市場','社會保護仍重要'],
    theory_trust_note:'社會投資不等於「有經濟報酬才值得做福利」。國考答題宜同時處理能力建構、社會保護、權利與分配效果。'
  });

  if(window.SWSI_THEORY_TRUST){
    window.SWSI_THEORY_TRUST.version='SWSI Theory Trust Final 2026-08-26';
    window.SWSI_THEORY_TRUST.final='SWSI Theory Trust Final Batch 2026-08-26';
    window.SWSI_THEORY_TRUST.pendingCount=function(){
      return rows.filter(function(t){return t&&t.theory_verify_status!=='checked';}).length;
    };
    window.SWSI_THEORY_TRUST.allChecked=function(){
      return rows.length===39 && this.verifiedCount()===39 && this.pendingCount()===0;
    };
  }
  window.SWSI_THEORY_TRUST_FINAL={
    version:'SWSI Theory Trust Final Batch 2026-08-26',
    total:function(){return rows.length;},
    checked:function(){return rows.filter(function(t){return t&&t.theory_verify_status==='checked';}).length;},
    pending:function(){return rows.filter(function(t){return t&&t.theory_verify_status!=='checked';}).map(function(t){return t.n;});}
  };
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

/* SWSI Feedback Context State Fix 2026-08-26 */
(function(){
  'use strict';
  function sync(){
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
  sync();
  document.addEventListener('click',function(){Promise.resolve().then(sync);},true);
  try{
    var scheduled=false;
    new MutationObserver(function(){
      if(scheduled)return;
      scheduled=true;
      Promise.resolve().then(function(){scheduled=false;sync();});
    }).observe(document.body,{childList:true,subtree:true});
  }catch(_e){}
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
      .swsi-report-dialog[data-swsi-compact="2"]{max-height:min(78vh,620px);padding:16px 16px 15px}
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
        .swsi-report-dialog[data-swsi-compact="2"]{max-height:82vh}
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
