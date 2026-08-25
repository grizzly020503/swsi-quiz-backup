
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
