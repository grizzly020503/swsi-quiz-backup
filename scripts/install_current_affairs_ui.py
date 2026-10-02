#!/usr/bin/env python3
from pathlib import Path

PATH = Path('index.html')
MARKER = '<!-- SWSI CURRENT AFFAIRS RADAR V1 -->'

BLOCK = r'''
<!-- SWSI CURRENT AFFAIRS RADAR V1 -->
<script>
(function(){
  if(window.__SWSI_CURRENT_AFFAIRS_UI__) return;
  window.__SWSI_CURRENT_AFFAIRS_UI__=true;

  var liveItems=[];
  var signalItems=[];
  var eventItems=[];
  var trendItems=[];
  var loadPromise=null;
  var currentFilter='全部';
  var oldOpen=null, oldFilter=null;

  var TEMPLATES={
    '兒少保護':{
      points:['兒少最佳利益與權利主體','安全／風險評估與責任通報','跨網絡合作、資訊交換與社工督導','制度漏洞、社會安全網與預防'],
      exam:'可從兒少保護體系、社工專業角色、風險評估、跨網絡合作或制度改善設計申論。'
    },
    '家暴與性暴力':{
      points:['危險評估與安全計畫','保護令及被害人權益','創傷知情與被害人主體性','警政、司法、醫療與社政網絡合作'],
      exam:'可從保護制度是否有效、社工安全計畫、創傷知情及跨網絡合作分析。'
    },
    '心理健康與成癮':{
      points:['精神衛生與社區支持','危機介入及復元取向','去污名與人權保障','醫療、社政與社區跨專業合作'],
      exam:'可從精神衛生政策、社區支持、危機介入、復元與人權觀點設計申論。'
    },
    '長照與高齡':{
      points:['在地老化與活躍老化','長照3.0與醫照整合','家庭照顧者支持','服務可近性、連續性與城鄉差距'],
      exam:'可從超高齡社會、長照3.0、家庭照顧者與服務輸送體系分析。'
    },
    '社會救助與居住':{
      points:['最低生活保障與最後安全網','貧窮的結構性因素','住宅／居住權與服務可近性','資源整合與脫貧策略'],
      exam:'可從社會救助制度、貧窮成因、居住權或福利可近性設計申論。'
    },
    '身障與人權':{
      points:['CRPD與障礙社會模式','合理調整與無障礙','自立生活與社區融合','權益倡導與去機構化'],
      exam:'可從CRPD、人權模式、合理調整、自立生活及制度落差分析。'
    },
    '移工與新住民':{
      points:['文化能力與文化謙遜','勞動／社會權益保障','反歧視與社會融合','跨語言、跨制度服務可近性'],
      exam:'可從多元文化、移民／移工權益、反歧視與社工文化能力設計申論。'
    },
    '少年司法與犯罪防治':{
      points:['保護優先與去標籤','曝險少年與行政輔導','家庭、學校與社區支持','復歸與跨系統合作'],
      exam:'可從少年司法的保護理念、去標籤、預防與跨系統服務設計申論。'
    },
    '性別與家庭政策':{
      points:['性別權力與結構分析','家庭政策與照顧負荷','性別主流化與權益保障','工作家庭平衡與福利支持'],
      exam:'可從性別平等、家庭政策、照顧責任與制度回應分析。'
    },
    '災害與社區工作':{
      points:['危機介入與災民需求評估','安置、資源分配與弱勢保障','社區韌性與社會資本','復原、重建與跨部門協調'],
      exam:'可從災害社工各階段任務、社區韌性、資源分配正義與災後重建分析。'
    },
    '社工專業與社福制度':{
      points:['社工專業角色與倫理','服務輸送與跨網絡整合','人力、督導與組織責任','政策執行落差與制度改善'],
      exam:'可從社工專業責任、服務體系、組織與政策執行問題設計申論。'
    }
  };

  function E(s){return String(s==null?'':s).replace(/[&<>\"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c];});}
  function fmtDate(v){
    if(!v) return '';
    var d=new Date(v); if(isNaN(d.getTime())) return '';
    return d.toLocaleDateString('zh-TW',{year:'numeric',month:'numeric',day:'numeric'});
  }
  function templateFor(cat){return TEMPLATES[cat]||{points:['事件脈絡與問題界定','相關社會工作理論／政策','社工角色與服務體系','制度改善與權益保障'],exam:'先從事件轉成社工問題，再用理論、政策、實務與制度四層次作答。'};}
  function signalFor(id){
    for(var i=0;i<signalItems.length;i++){if(signalItems[i].id===id)return signalItems[i];}
    return null;
  }
  function trendFor(id){
    for(var i=0;i<trendItems.length;i++){if(trendItems[i].canonical_event_id===id)return trendItems[i];}
    return null;
  }
  function trendLabel(v){
    return v==='rising'?'升溫':v==='sustained'?'持續':v==='cooling'?'降溫':'單次觀察';
  }
  function safeHref(v){
    var s=String(v||''); return /^https:\/\//i.test(s)?E(s):'#';
  }
  function knowledgeHtml(item){
    item=item||{};
    var root=String(item.knowledge_root||'');
    var domains=item.management_domains||[];
    var topics=(item.subject_topics&&typeof item.subject_topics==='object')?item.subject_topics:{};
    var subjects=Object.keys(topics);
    if(!root||(!domains.length&&!subjects.length)) return '';
    var domainHtml=domains.slice(0,8).map(function(x){return '<span class="nlr-chip">'+E(x)+'</span>';}).join('');
    var primary=(item.primary_exam_subject_axes||[]).filter(function(subject){return subjects.indexOf(subject)>=0;});
    if(!primary.length) primary=subjects.slice(0,Math.min(2,subjects.length));
    var supporting=(item.supporting_exam_subject_axes||[]).filter(function(subject){
      return subjects.indexOf(subject)>=0&&primary.indexOf(subject)<0;
    });
    subjects.forEach(function(subject){
      if(primary.indexOf(subject)<0&&supporting.indexOf(subject)<0) supporting.push(subject);
    });
    function subjectGroup(label,list){
      if(!list.length) return '';
      var rows=list.slice(0,5).map(function(subject){
        var topicRows=(topics[subject]||[]).slice(0,4).map(function(topic){return '<li>'+E(topic)+'</li>';}).join('');
        return '<div class="nlr-knowledge-subject"><b>'+E(subject)+'</b>'+(topicRows?'<ul>'+topicRows+'</ul>':'')+'</div>';
      }).join('');
      return '<div class="nlr-knowledge-label">'+E(label)+'</div>'+rows;
    }
    return '<details class="nlr-detail nlr-knowledge"><summary>社會工作管理 × 國考五科</summary>'
      +'<div class="nlr-knowledge-root"><b>'+E(root)+'</b><span>跨科整合層，不是額外的國考科目</span></div>'
      +(domainHtml?'<div class="nlr-knowledge-label">管理面向</div><div class="nlr-chips">'+domainHtml+'</div>':'')
      +subjectGroup('主要考科',primary)
      +subjectGroup('延伸考科',supporting)
      +'</details>';
  }
  function eventCard(ev){
    var tr=trendFor(ev.canonical_event_id)||{};
    var subjects=(ev.subjects||[]).map(function(x){return '<span class="nlr-sub">'+E(x.replace('社會政策與社會立法','社政法').replace('社會工作直接服務','直接服務').replace('人類行為與社會環境','人行'))+'</span>';}).join('');
    var sourceCount=Number(ev.source_count||0), officialCount=Number(ev.official_source_count||0);
    var observationCount=Number(tr.observation_count||ev.observation_count||1);
    var trendReady=sourceCount>=2||observationCount>=2;
    var displayTrendState=trendReady?(tr.trend_state||'one-off'):'one-off';
    var displayTrendLabel=trendReady?trendLabel(tr.trend_state):'單次觀察';
    var strongMatches=Number(tr.historical_high_confidence_match_count||0);
    var allRelated=tr.related_exam_questions||ev.related_exam_questions||[];
    var related=strongMatches>0?allRelated.filter(function(q){return Number(q.match_score||0)>=5;}):[];
    if(strongMatches>0&&!related.length) related=allRelated.slice(0,Math.min(strongMatches,5));
    var whyItems=trendReady?(tr.why||[]):[
      officialCount?'目前有官方來源，可作制度／議題複習依據':'目前只有單一來源，先保留觀察',
      '尚未有第二來源或後續日期支持，不視為趨勢'
    ];
    var why=whyItems.slice(0,5).map(function(x){return '<li>'+E(x)+'</li>';}).join('');
    var evidence=(ev.evidence||[]).slice(0,4).map(function(x){
      return '<li><a class="nlr-link" href="'+safeHref(x.source_url)+'" target="_blank" rel="noopener noreferrer">'+E(x.source_name||'來源')+'</a>'
        +(fmtDate(x.published_at)?' ・ '+E(fmtDate(x.published_at)):'')+'</li>';
    }).join('');
    var mcq=tr.mcq_focus||ev.mcq_focus||[];
    var essay=tr.essay_direction||ev.essay_direction||'';
    var trendScore=tr.trend_score!=null?tr.trend_score:'';
    var signalHtml=(trendReady&&trendScore!=='')
      ?'<div class="nlr-signal"><b>趨勢訊號 '+E(trendScore)+'/10</b> ・ '+E(trendLabel(tr.trend_state))+'</div>'
      :'<div class="nlr-signal"><b>目前：單次觀察</b> ・ 尚不足以形成趨勢</div>';
    var summaryText=trendReady?(ev.exam_point_summary||''):'目前證據仍是單一來源／單次觀察，先當作制度或議題複習素材；待跨來源或後續更新後，再判斷是否形成命題趨勢。';
    var evidenceLabel=sourceCount>=2?'多來源證據':'來源依據';
    var note=trendReady?'同事件跨來源只計一次；趨勢用來安排複習，不代表命題保證。':'目前只有單一來源或單次觀察；不以分數宣稱趨勢，事實請以原始來源為準。';
    var knowledge=knowledgeHtml((tr.knowledge_root||tr.subject_topics)?tr:ev);
    return '<div class="nlr-card">'
      +'<div class="nlr-head"><span class="nlr-cat">'+E(ev.category||'時事')+'</span><span class="nlr-trend nlr-trend-'+E(displayTrendState)+'">'+E(displayTrendLabel)+'</span></div>'
      +'<div class="nlr-title">'+E(ev.title||'')+'</div>'
      +'<div class="nlr-meta">'+E(sourceCount)+' 個來源'+(officialCount?' ・ '+E(officialCount)+' 官方':'')+(fmtDate(ev.last_seen)?' ・ 更新 '+E(fmtDate(ev.last_seen)):'')+'</div>'
      +'<div class="nlr-subs">'+subjects+'</div>'
      +signalHtml
      +(summaryText?'<div class="nlr-signal-text">'+E(summaryText)+'</div>':'')
      +knowledge
      +(why?'<details class="nlr-detail"><summary>為什麼值得複習？</summary><ul>'+why+'</ul></details>':'')
      +(essay?'<details class="nlr-detail"><summary>值得練習的申論方向</summary><div class="nlr-exam">'+E(essay)+'</div></details>':'')
      +(mcq.length?'<details class="nlr-detail"><summary>選擇題可能抓哪些事實？</summary><div class="nlr-chips">'+mcq.slice(0,8).map(function(x){return '<span class="nlr-chip">'+E(x)+'</span>';}).join('')+'</div></details>':'')
      +(related.length?'<details class="nlr-detail"><summary>歷屆相關題</summary><ul>'+related.slice(0,5).map(function(q){var label=(q.year||'')+'-'+(q.round||'')+'-'+(q.qno||'');return '<li><b>'+E(q.id||label)+'</b> '+E(q.subject||'')+(q.topic?' ・ '+E(q.topic):'')+'</li>';}).join('')+'</ul></details>':'')
      +(evidence?'<details class="nlr-detail"><summary>'+E(evidenceLabel)+'</summary><ul>'+evidence+'</ul></details>':'')
      +'<div class="nlr-note">'+E(note)+'</div>'
      +'</div>';
  }
  function liveCard(ev){
    var t=templateFor(ev.category);
    var sig=signalFor(ev.id)||{};
    var pts=t.points.map(function(x){return '<li>'+E(x)+'</li>';}).join('');
    var tags=(ev.exam_tags||[]).slice(0,6).map(function(x){return '<span class="nlr-chip">'+E(x)+'</span>';}).join('');
    var subjects=(ev.subjects||[]).map(function(x){return '<span class="nlr-sub">'+E(x.replace('社會政策與社會立法','社政法').replace('社會工作直接服務','直接服務').replace('人類行為與社會環境','人行'))+'</span>';}).join('');
    var summary=String(ev.summary||''); if(summary.length>220) summary=summary.slice(0,220)+'…';
    var liveKnowledge=knowledgeHtml(ev);
    return '<div class="nlr-card">'
      +'<div class="nlr-head"><span class="nlr-cat">'+E(ev.category||'時事')+'</span><span class="nlr-score">關聯 '+E(ev.relevance_score||'')+'/10</span></div>'
      +'<div class="nlr-title">'+E(ev.title)+'</div>'
      +'<div class="nlr-meta">'+E(ev.source_name||'')+(fmtDate(ev.published_at)?' ・ '+E(fmtDate(ev.published_at)):'')+'</div>'
      +(summary?'<div class="nlr-summary">'+E(summary)+'</div>':'')
      +'<div class="nlr-subs">'+subjects+'</div>'
      +(tags?'<div class="nlr-chips">'+tags+'</div>':'')
      +liveKnowledge
      +(sig.signal_confidence?'<div class="nlr-signal"><b>命題訊號：'+E(sig.signal_confidence==='high'?'高':sig.signal_confidence==='medium'?'中':'低')+'</b>'+(sig.signal_score!=null?' ・ '+E(sig.signal_score)+'/10':'')+'</div>':'')
      +(sig.exam_point_summary?'<div class="nlr-signal-text">'+E(sig.exam_point_summary)+'</div>':'')
      +(sig.essay_direction?'<details class="nlr-detail"><summary>值得練習的申論方向</summary><div class="nlr-exam">'+E(sig.essay_direction)+'</div></details>':'')
      +(sig.mcq_focus&&sig.mcq_focus.length?'<details class="nlr-detail"><summary>選擇題可能抓哪些事實？</summary><div class="nlr-chips">'+sig.mcq_focus.slice(0,8).map(function(x){return '<span class="nlr-chip">'+E(x)+'</span>';}).join('')+'</div></details>':'')
      +(sig.related_exam_questions&&sig.related_exam_questions.length?'<details class="nlr-detail"><summary>歷屆相關題</summary><ul>'+sig.related_exam_questions.slice(0,4).map(function(q){var label=(q.year||'')+'-'+(q.round||'')+'-'+(q.qno||'');return '<li><b>'+E(q.id||label)+'</b> '+E(q.subject||'')+(q.topic?' ・ '+E(q.topic):'')+'</li>';}).join('')+'</ul></details>':'')
      +'<details class="nlr-detail"><summary>此類事件常見的申論思考方向</summary><ul>'+pts+'</ul><div class="nlr-exam">'+E(t.exam)+'</div></details>'
      +'<a class="nlr-link" href="'+safeHref(ev.source_url)+'" target="_blank" rel="noopener noreferrer">查看原始來源 ↗</a>'
      +'</div>';
  }
  function ensureStyle(){
    if(document.getElementById('swsi-nlr-style')) return;
    var st=document.createElement('style'); st.id='swsi-nlr-style';
    st.textContent=''
      +'.nlr-box{margin:14px 0 18px;padding:14px;border:1px solid var(--line,#ddd);border-radius:16px;background:var(--card,#fff)}'
      +'.nlr-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:4px}.nlr-h{font-weight:800;font-size:1.05rem}.nlr-badge{font-size:.75rem;padding:4px 8px;border-radius:999px;background:var(--soft,#f3f3f3);white-space:nowrap}'
      +'.nlr-help{font-size:.82rem;line-height:1.55;color:var(--muted,#666);margin:5px 0 12px}.nlr-grid{display:grid;gap:10px}'
      +'.nlr-card{border:1px solid var(--line,#ddd);border-radius:13px;padding:12px;background:var(--bg,#fff)}.nlr-head{display:flex;justify-content:space-between;gap:8px}.nlr-cat{font-size:.75rem;font-weight:700}.nlr-score{font-size:.72rem;color:var(--muted,#777)}'
      +'.nlr-title{font-weight:800;line-height:1.45;margin:6px 0}.nlr-meta,.nlr-summary{font-size:.8rem;color:var(--muted,#666);line-height:1.55}.nlr-summary{margin-top:7px}'
      +'.nlr-subs,.nlr-chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}.nlr-sub,.nlr-chip{font-size:.7rem;border-radius:999px;padding:3px 7px;background:var(--soft,#f2f2f2)}'
      +'.nlr-detail{margin-top:9px;font-size:.8rem;line-height:1.55}.nlr-detail summary{cursor:pointer;font-weight:700}.nlr-detail ul{padding-left:20px;margin:7px 0}.nlr-exam{margin-top:6px}.nlr-signal{margin-top:9px;font-size:.8rem}.nlr-signal-text{margin-top:5px;font-size:.78rem;line-height:1.5}.nlr-link{display:inline-block;margin-top:9px;font-size:.78rem;text-decoration:none;font-weight:700}.nlr-empty{font-size:.82rem;color:var(--muted,#777);padding:8px 0}.nlr-knowledge-root{display:flex;flex-wrap:wrap;gap:6px;align-items:baseline;margin-top:8px}.nlr-knowledge-root span,.nlr-knowledge-label{font-size:.72rem;color:var(--muted,#777)}.nlr-knowledge-label{font-weight:700;margin-top:8px}.nlr-knowledge-subject{margin-top:8px}.nlr-knowledge-subject ul{margin:3px 0 0;padding-left:18px}'+'.nlr-trend{font-size:.72rem;font-weight:800;padding:3px 7px;border-radius:999px;background:var(--soft,#f2f2f2)}.nlr-trend-rising{font-weight:900}.nlr-trend-sustained{font-weight:800}.nlr-trend-cooling{opacity:.72}.nlr-note{font-size:.72rem;color:var(--muted,#777);line-height:1.45;margin-top:9px}';
    document.head.appendChild(st);
  }
  function fetchJson(url){
    return fetch(url,{cache:'no-store'}).then(function(r){if(!r.ok) throw new Error(url+' HTTP '+r.status);return r.json();});
  }
  function loadLive(){
    if(loadPromise) return loadPromise;
    loadPromise=Promise.all([
      fetchJson('./auto/current_affairs.json').catch(function(){return null;}),
      fetchJson('./auto/current_affairs_signals.json').catch(function(){return null;}),
      fetchJson('./auto/current_affairs_events.json').catch(function(){return null;}),
      fetchJson('./auto/current_affairs_trends.json').catch(function(){return null;})
    ]).then(function(all){
      liveItems=all[0]&&Array.isArray(all[0].items)?all[0].items:[];
      signalItems=all[1]&&Array.isArray(all[1].items)?all[1].items:[];
      eventItems=all[2]&&Array.isArray(all[2].events)?all[2].events:[];
      trendItems=all[3]&&Array.isArray(all[3].trends)?all[3].trends:[];
      return eventItems.length?eventItems:liveItems;
    });
    return loadPromise;
  }
  function inject(filter){
    currentFilter=filter||currentFilter||'全部';
    var wrap=document.querySelector('.nl-wrap'); if(!wrap) return;
    var old=document.getElementById('nl-live-radar'); if(old) old.remove();
    var useV2=eventItems.length&&trendItems.length;
    var source=useV2?eventItems:liveItems;
    var list=source.filter(function(ev){return currentFilter==='全部'||(ev.subjects||[]).indexOf(currentFilter)>=0;}).slice(0,6);
    if(!source.length) return;
    var box=document.createElement('section'); box.id='nl-live-radar'; box.className='nlr-box';
    box.innerHTML=useV2
      ?'<div class="nlr-top"><div class="nlr-h">📈 命題趨勢雷達</div><div class="nlr-badge">事件聚類・證據分級</div></div>'
        +'<div class="nlr-help">同一事件會先合併；只有跨來源或持續觀察時才顯示趨勢分數。單一來源先當作複習素材，不直接宣稱形成趨勢。</div>'
        +(list.length?'<div class="nlr-grid">'+list.map(eventCard).join('')+'</div>':'<div class="nlr-empty">這個科目目前沒有新的高關聯事件。</div>')
      :'<div class="nlr-top"><div class="nlr-h">⚡ 最新雷達</div><div class="nlr-badge">V1 備援</div></div>'
        +'<div class="nlr-help">趨勢資料暫時不可用，先顯示原本的高關聯時事與命題訊號；事實細節請以原始來源為準。</div>'
        +(list.length?'<div class="nlr-grid">'+list.map(liveCard).join('')+'</div>':'<div class="nlr-empty">這個科目目前沒有新的高關聯時事。</div>');
    var chips=wrap.querySelector('.nl-chips');
    if(chips) wrap.insertBefore(box,chips); else wrap.appendChild(box);
  }
  function hook(){
    if(!window.NL||window.NL.__liveHooked) return false;
    ensureStyle();
    oldOpen=window.NL.open; oldFilter=window.NL.filter;
    window.NL.open=function(){
      currentFilter='全部'; oldOpen.apply(window.NL,arguments);
      loadLive().then(function(){inject(currentFilter);});
    };
    window.NL.filter=function(f){
      currentFilter=f||'全部'; oldFilter.apply(window.NL,arguments);
      loadLive().then(function(){inject(currentFilter);});
    };
    window.NL.__liveHooked=true;
    return true;
  }
  if(!hook()){
    var tries=0, timer=setInterval(function(){tries++;if(hook()||tries>40)clearInterval(timer);},100);
  }
})();
</script>
'''


def main():
    text = PATH.read_text(encoding='utf-8')
    if MARKER in text:
        # Upgrade the existing owner in place. The V1 marker also appears in
        # older pages that do not yet fetch or render exam signals.
        if text.count(MARKER) != 1:
            raise SystemExit('expected one current-affairs UI block')
        start = text.index(MARKER)
        script_start = text.find('<script>', start)
        if script_start < 0 or text[start + len(MARKER):script_start].strip():
            raise SystemExit('current-affairs UI script boundary is invalid')
        end = text.find('</script>', script_start)
        if end < 0:
            raise SystemExit('current-affairs UI script closing tag is missing')
        end += len('</script>')
        updated = text[:start] + BLOCK.strip() + text[end:]
        if updated != text:
            PATH.write_text(updated, encoding='utf-8')
            print('Updated current-affairs live UI with V2 event trends and V1 fallback.')
        else:
            print('Current-affairs live UI already current.')
        return
    if '</body>' not in text:
        raise SystemExit('index.html missing </body>')
    text = text.replace('</body>', BLOCK + '\n</body>', 1)
    PATH.write_text(text, encoding='utf-8')
    print('Installed current-affairs live radar UI.')


if __name__ == '__main__':
    main()
