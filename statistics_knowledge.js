/* SWSI 原創統計學知識卡：學科通用概念，不複製第三方教材。
 * 只供作答後輔助理解，不參與官方答案、給分或題庫同步。
 */
(function(root){
  "use strict";
  var concepts=[
    {id:"chi",title:"卡方獨立性檢定",words:/卡方|卡方考驗|卡方檢定|卡方檢驗|χ²|chi.square/i,
      meaning:"用來評估兩個類別變項的分布是否有關聯，例如是否參與服務與是否完成轉介。",
      choose:"辨認關鍵：類別 × 類別；觀察各格次數，不是比較平均數。",
      warn:"期望次數太低時，要評估是否改用適合小樣本的確切檢定。"},
    {id:"paired_t",title:"成對樣本 t 考驗",words:/成對樣本|配對樣本|相依樣本|paired.{0,5}t|前後測.{0,10}t/i,
      meaning:"比較同一批對象兩次測量結果的平均差異，例如同一組學員課前與課後的分數。",
      choose:"辨認關鍵：同一個人測兩次，或成對配對的觀察值。",
      warn:"重點在配對差值的分布假設；不能把同一人兩次資料當成互相獨立。"},
    {id:"independent_t",title:"獨立樣本 t 考驗",words:/獨立樣本.{0,4}t|兩獨立樣本|independent.{0,5}t|welch/i,
      meaning:"比較兩個互不重疊群體的連續變項平均數，例如兩組不同參與者的壓力量表平均分。",
      choose:"辨認關鍵：兩個獨立群體 × 連續結果。變異數不齊時可考慮 Welch t 考驗。",
      warn:"須檢查觀察值獨立性、分布與離群值；顯著不代表有因果關係。"},
    {id:"one_t",title:"單一樣本 t 考驗",words:/單一樣本.{0,4}t|單樣本.{0,4}t|one.sample.{0,5}t/i,
      meaning:"將一組樣本的平均數與事先指定的基準值比較。",
      choose:"辨認關鍵：一組觀察值對照一個固定比較值。",
      warn:"比較值應事先有合理依據，而不是分析後才挑選。"},
    {id:"anova",title:"變異數分析（ANOVA）",words:/變異數分析|單因子.{0,5}分析|二因子.{0,5}分析|\bANOVA\b/i,
      meaning:"比較不同組別的平均數；若有兩個分組因子，亦可檢查交互作用。",
      choose:"辨認關鍵：類別分組因子 × 連續結果；三組以上平均數比較常使用單因子 ANOVA。",
      warn:"整體顯著不等於每一組都不同；需要適當的事後比較與效果量。"},
    {id:"ancova",title:"共變數分析（ANCOVA）",words:/共變數分析|\bANCOVA\b/i,
      meaning:"比較組別結果時，將前測或其他連續共變項納入模型，估計調整後的組別差異。",
      choose:"辨認關鍵：比較不同組別，同時控制一個或多個共變項。",
      warn:"要檢查模型假設，例如組別間迴歸斜率是否相近；控制變項不會自動消除所有偏誤。"},
    {id:"logistic",title:"羅吉斯迴歸",words:/羅吉斯|邏輯斯迴歸|邏輯迴歸|logistic/i,
      meaning:"用一個或多個變項解釋或預測二元結果，例如是否成功就業。",
      choose:"辨認關鍵：依變項常是是／否；結果可用勝算比（OR）表示。",
      warn:"勝算比不是風險比，尤其當事件發生比例不低時更應小心。"},
    {id:"spearman",title:"斯皮爾曼等級相關",words:/斯皮爾曼|史皮爾曼|等級相關|spearman/i,
      meaning:"評估兩個變項間的單調關係，適合以等級排序表示的資料或不符合 Pearson 假設的情境。",
      choose:"辨認關鍵：排序／等級資料、單調趨勢。",
      warn:"相關不代表因果；單調相關也不一定是直線關係。"},
    {id:"pearson",title:"皮爾森積差相關",words:/皮爾森|彼爾森|積差相關|pearson/i,
      meaning:"以相關係數 r 描述兩個數值型變項的線性關係方向與強度。",
      choose:"r 的範圍為 -1 到 +1；正負表示方向，絕對值越大通常代表線性關係越強。",
      warn:"離群值可能大幅影響 r；相關不代表一個變項造成另一個變項。"},
    {id:"multiple_regression",title:"多元線性迴歸",words:/多元.{0,4}迴歸|複迴歸|multiple.{0,6}regression/i,
      meaning:"同時以兩個以上預測變項解釋連續結果，觀察每一項在控制其他變項下的關聯。",
      choose:"辨認關鍵：連續依變項、多個自變項；留意係數、信賴區間、R²。",
      warn:"檢查多重共線性、殘差與模型設定；預測模型不等於因果證明。"},
    {id:"regression",title:"簡單線性迴歸",words:/迴歸分析|線性迴歸|簡單迴歸|回歸分析|regression/i,
      meaning:"以一個預測變項建立數值結果的線性預測模型。",
      choose:"看斜率估計（B）、不確定性與 R²；R² 描述模型解釋的變異比例。",
      warn:"沒有研究設計與理論支持，不應從迴歸係數直接宣稱因果。"},
    {id:"mediation",title:"中介效果",words:/中介變項|中介效果|中介分析|間接效果|mediation/i,
      meaning:"探討 X 與 Y 的關聯是否部分經由另一個變項 M 傳遞。",
      choose:"辨認關鍵：問「透過什麼機制」；常以間接效果及其信賴區間評估。",
      warn:"不能只看直接效果有沒有顯著，就判定是否存在中介；因果中介需要更嚴格的假設。"},
    {id:"moderation",title:"調節效果",words:/調節變項|調節效果|調節分析|交互作用|moderation/i,
      meaning:"探討 X 與 Y 的關聯是否因另一個條件 W 而改變，例如不同社會支持程度的效果不同。",
      choose:"辨認關鍵：問「在什麼條件下、對誰效果比較大」；檢查交互作用項。",
      warn:"中介與調節不同：中介談過程；調節談關係的強弱或方向改變。"},
    {id:"reliability",title:"信度",words:/再測信度|折半信度|內部一致性|克隆巴赫|cronbach|信度/i,
      meaning:"衡量測量結果是否具有一定程度的一致性或穩定性。",
      choose:"常見指標包括內部一致性（如 Cronbach's α）與再測信度；要看測量目的選擇。",
      warn:"信度高不代表一定測得正確；α 高也不保證量表只有單一構念。"},
    {id:"validity",title:"效度",words:/建構效度|構念效度|內容效度|效標效度|聚合效度|區別效度|預測效度|效度/i,
      meaning:"評估研究證據是否支持對測量分數所做的特定解釋與用途。",
      choose:"例如內容證據、與其他變項的關係、內部結構等；聚合效度看相關構念的收斂證據。",
      warn:"不能僅憑兩個量表高度相關就說具有「預測效度」；需要區分效度證據類型與研究時間設計。"},
    {id:"factor",title:"因素分析",words:/因素分析|因素負荷|探索性因素|驗證性因素|\bEFA\b|\bCFA\b/i,
      meaning:"探索性因素分析（EFA）探索題項的潛在結構；驗證性因素分析（CFA）檢驗事先提出的測量結構。",
      choose:"辨認關鍵：量表的潛在構念與題項如何組合。",
      warn:"因素結構需結合理論、模型適配與樣本條件判讀。"},
    {id:"measurement",title:"測量尺度",words:/名義尺度|順序尺度|區間尺度|比例尺度|測量尺度|李克特|likert/i,
      meaning:"名義只分類、順序可排序、區間有等距但沒有絕對零點、比例尺度另有絕對零點。",
      choose:"統計方法須看資料性質；單題李克特選項通常是順序資料，合成量表可依條件視為近似連續。",
      warn:"不要只因資料用數字編碼，就把類別變項當成可計算平均數的連續量。"},
    {id:"mean_sd",title:"描述統計",words:/描述統計|平均數|中位數|眾數|標準差|變異數|四分位距|次數分配/i,
      meaning:"使用次數、百分比、集中趨勢與離散程度描述樣本特徵。",
      choose:"偏斜或極端值明顯時，中位數與四分位距常比平均數、標準差更能代表典型情況。",
      warn:"描述統計僅描述現有資料；不能單靠樣本平均數推論方案造成的效果。"},
    {id:"hypothesis",title:"假設檢定與 p 值",words:/虛無假設|對立假設|假設檢定|假設檢驗|統計顯著|顯著水準|第一類錯誤|第二類錯誤|\bp\s*[<>=]/i,
      meaning:"p 值是：假定虛無假設成立時，得到目前結果或更極端結果的機率。",
      choose:"預先設定顯著水準（常見 .05），並同時閱讀效果量與信賴區間。",
      warn:"p 值不是「虛無假設成立的機率」；不顯著也不等於證明完全沒有效果。"},
    {id:"effect",title:"效果量與信賴區間",words:/效果量|信賴區間|cohen.?s?.?d|偏η|\beta\b|\bCI\b/i,
      meaning:"效果量描述差異或關係的程度；信賴區間呈現估計的不確定性。",
      choose:"同時看方向、大小、信賴區間與研究情境中的實務重要性。",
      warn:"統計顯著與實務重要性不同，不能只以 p 值判定方案值不值得推廣。"},
    {id:"sampling",title:"抽樣與推論",words:/隨機抽樣|分層抽樣|系統抽樣|集群抽樣|便利抽樣|非機率抽樣|抽樣誤差|樣本數|母體/i,
      meaning:"從母體中抽取樣本並依設計推論；機率抽樣讓抽樣機率可被定義，較容易估計抽樣不確定性。",
      choose:"區分抽樣方法、涵蓋誤差、選擇偏誤與無回應問題。",
      warn:"樣本數大不代表樣本就有代表性；便利抽樣不能直接推論全部母體。"},
    {id:"missing",title:"遺漏值與資料品質",words:/遺漏值|缺失值|缺漏值|資料清理|極端值|離群值/i,
      meaning:"先辨認空白或無效資料的形成原因，再決定是否排除、補值或使用適當的缺失資料處理方法。",
      choose:"比較不同處理方式是否改變主要結果，並報告缺失值數量。",
      warn:"直接用平均數填補可能低估變異並造成偏誤，不能不加判斷套用。"},
    {id:"method",title:"統計方法速判",words:/統計方法|統計檢定|統計考驗|推論統計|統計分析方法/i,
      meaning:"先辨認研究問題、結果變項尺度、比較組數與觀察值是否獨立，再選統計方法。",
      choose:"類別×類別常考慮卡方；兩組平均常考慮 t；多組平均常考慮 ANOVA；線性關聯可考慮相關或迴歸。",
      warn:"這是考試判斷起點，不是忽略樣本設計與統計假設的萬用規則。"}
  ];
  function asText(v){return Array.isArray(v)?v.join(" "):String(v==null?"":v);}
  function select(item){
    if(!item||typeof item!=="object")return null;
    var category=asText(item.subject)+" "+asText(item.major);
    if(!/研究|統計/.test(category))return null;
    var fields=[asText(item.question||item.q||item.question_text||item.text),
      asText(item.topic)+" "+asText(item.keywords)];
    for(var j=0;j<fields.length;j++){
      var source=fields[j];
      for(var i=0;i<concepts.length;i++)if(concepts[i].words.test(source))return concepts[i];
    }
    return null;
  }
  function htmlEscape(s){return String(s).replace(/[&<>"']/g,function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });}
  function render(item){
    var c=select(item);
    if(!c)return "";
    return '<details class="swsi-stat-learn"><summary>統計觀念補充｜'+htmlEscape(c.title)+'</summary>'+
      '<div class="swsi-stat-learn-body"><p>'+htmlEscape(c.meaning)+'</p>'+
      '<p><strong>怎麼判斷：</strong>'+htmlEscape(c.choose)+'</p>'+
      '<p><strong>容易搞錯：</strong>'+htmlEscape(c.warn)+'</p>'+
      '<small>平台原創學習補充，非考選部官方解析；不影響本題答案與計分。</small></div></details>';
  }
  var api=Object.freeze({version:"1",concepts:concepts.map(function(c){return {id:c.id,title:c.title};}),select:select,html:render});
  root.SWSI_STATS=api;
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
  if(typeof document!=="undefined"&&document.head&&!document.getElementById("swsi-stats-style")){
    var style=document.createElement("style");style.id="swsi-stats-style";
    style.textContent='.swsi-stat-learn{margin:13px 0 16px;border:1px solid var(--line,#DCE4DF);border-radius:12px;background:var(--paper2,#FFF);font-size:var(--fs-b,15px)}'+
      '.swsi-stat-learn summary{cursor:pointer;color:var(--pine-deep,#204F48);font-weight:700;padding:13px 14px;min-height:48px;line-height:1.6}'+
      '.swsi-stat-learn-body{padding:0 14px 13px;line-height:1.8}'+
      '.swsi-stat-learn-body p{margin:0 0 9px}'+
      '.swsi-stat-learn-body strong{color:var(--pine-deep,#204F48)}'+
      '.swsi-stat-learn-body small{display:block;color:var(--ink-soft,#52655D);font-size:var(--fs-s,12px)}';
    document.head.appendChild(style);
  }
})(typeof globalThis!=="undefined"?globalThis:this);
