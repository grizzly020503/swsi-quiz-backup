# 申論參考架構逐題核對：Batch 9 Verified

日期：2026-08-26
狀態：`verified / audit only`

> 本批聚焦 114 年第二次社會工作師考試 5 題高風險錯配。題幹以考選部官方考畢試題 PDF 為準。以下為 SWSI 自製複習架構，不宣稱為考選部官方標準答案。
> 未修改 `index.html`、`essay_guides.js`、`monthly_patch_parts/`、`cdn/preview/`、`sw.js`、Cloudflare preview 或 Netlify 正式學生站。

## QA 結論

- 5/5 題官方題意重新核對完成。
- 研究方法兩題均屬 severe mismatch：一題把演繹／歸納誤套成量化／質性，一題把研究策略誤套成資料蒐集方法。
- 同志親職題採 affirming / child-centred 評估：父母性傾向本身不是兒童發展危險因子；需評估的是一般親職能力、家庭功能及污名／法律／支持網絡等脈絡。
- Life Model 題鎖定 Germain & Gitterman，而非只用 Bronfenbrenner 分層。
- New Right 題依考題要求固定拆成經濟、政治、社會／道德三面，再連到福利國家的市場化、選擇性、條件化與重整。

---

## 1. 社會工作研究方法-114-2-申論1

### 題意 QA

官方題目要求定義 deduction 與 induction，並舉例說明二者如何相輔相成形成研究循環。

現行 guide 卻是「量化 vs 質性」模板。這不只是過度概括，而是把不同分類軸混在一起：演繹與歸納是理論—觀察間的推理方向，量化／質性是研究資料與方法傳統，彼此不能一一等同。

### Verified payload

```js
verified('社會工作研究方法-114-2-申論1',{
  kao:'本題核心是「理論 ↔ 經驗觀察」的雙向循環。演繹（deduction）由既有理論／命題出發，推出可檢驗假設，再蒐集資料檢驗；歸納（induction）則從具體觀察與資料中的規律出發，形成概念、命題或修正理論。兩者不是量化＝演繹、質性＝歸納的一一對應；同一研究計畫可反覆使用兩種邏輯。',
  dati:'先定義演繹：Theory→proposition／hypothesis→operationalization→observation／data→test。再定義歸納：Observation／data→pattern→concept/category→proposition／theory。舉例可用家庭照顧者負荷：研究者先依壓力緩衝理論演繹出「社會支持越高，照顧負荷越低」的假設，將社會支持與照顧負荷操作化後蒐集資料檢驗；結果若發現真正與低負荷高度相關的不是一般情緒支持，而是「有人實際分擔照顧時數」，研究者再從資料歸納出「工具性照顧分擔可能比一般支持更關鍵」的新命題；接著由這個修正後理論再演繹出新假設，換一個樣本或設計重新檢驗。如此形成 theory→hypothesis→observation→pattern→theory refinement→new hypothesis→retest 的循環。',
  biaoti:[
    '一、演繹邏輯：由一般理論／命題推導較具體、可檢驗的假設，再以經驗資料驗證，是理論檢驗（theory testing）的方向。',
    '二、歸納邏輯：由具體觀察／資料發現規律，形成概念、命題或較一般的理論，是理論建構／修正（theory building）的方向。',
    '三、兩者關係：不是互斥方法，也不能簡化成量化＝演繹、質性＝歸納；研究可在不同階段交互使用。',
    '四、演繹例：由壓力緩衝理論推出「社會支持降低家庭照顧者負荷」→操作化→抽樣蒐集→檢驗。',
    '五、歸納修正：若資料顯示實際照顧分擔比一般情緒支持更有關，從觀察形成新的概念關係與理論命題。',
    '六、研究循環：修正理論→再推出新假設→再蒐集資料驗證；理論與經驗資料持續往返。'
  ],
  guideMust:['演繹或deduction','歸納或induction','理論','假設','觀察或資料','理論檢驗','理論建構或修正','循環','舉例','重新檢驗或retest'],
  guideMustNot:['量化等於演繹','質性等於歸納','量化vs質性作為主架構','只下定義不說循環']
});
```

### 來源核對

- 考選部 114 年第二次「社會工作研究方法」申論第1題。
- 社會科學研究方法教材：deduction 是由 theory 出發，以 empirical data 檢驗理論所推出的 pattern／hypothesis；induction 是由 observations 中辨識 pattern 並建立／修正 theoretical concepts。
- 研究方法文獻明確將二者視為 iterative research cycle 的互補兩半，亦提醒 deductive／inductive reasoning 不應被簡化成 quantitative／qualitative 的同義詞。

---

## 2. 社會工作研究方法-114-2-申論2

### 題意 QA

官方題目問的是不同「質性研究策略」具有哪些共同特質，再舉一個策略說明如何研究；不是要求列出深訪、焦點團體與觀察三種資料蒐集工具。

### Verified payload

```js
verified('社會工作研究方法-114-2-申論2',{
  kao:'先分清楚「研究策略」與「資料蒐集方法」：grounded theory、phenomenology、ethnography、case study、narrative 等是研究策略／取向；深度訪談、觀察、文件與焦點團體是策略中可能使用的蒐集方法。共同特質要從質性研究如何理解經驗、意義、過程與情境來答。',
  dati:'共同特質可整理為：①重視參與者主觀意義、經驗與過程；②資料通常置於自然情境／真實脈絡理解；③研究者是主要研究工具，需持續reflexivity；④設計具彈性與emergent特性，可隨資料調整問題、樣本與蒐集方式；⑤常採立意／理論等資訊導向取樣，而非以機率代表性為第一目標；⑥蒐集rich、厚實、脈絡化資料，可整合訪談／觀察／文件等多來源；⑦資料蒐集與分析通常交錯反覆，主要採歸納建構、亦可用既有概念做演繹式檢視；⑧重視participant meaning、情境整體性、差異與複雜性；⑨透過透明分析、反思、三角檢證／成員檢核等方式提升trustworthiness並妥善處理倫理。舉例選grounded theory：研究「兒保社工如何處理跨機構衝突」；先立意取樣有相關經驗的社工，進行半結構訪談／文件或必要觀察，邊蒐集邊initial coding與constant comparison，寫memo形成初步類別，再依類別進行theoretical sampling，直到核心範疇與關係足夠清楚，最後建立一個解釋跨機構協調歷程的實質理論。',
  biaoti:[
    '一、共同研究取向：關注意義、經驗、過程、差異及情境，而非只把社會現象化約成變項。',
    '二、自然情境與研究者角色：在真實脈絡理解現象；研究者是key instrument並需反思自身位置與影響。',
    '三、彈性／湧現設計：研究問題、取樣與資料蒐集可依新發現調整；強調資訊豐富個案而非機率代表性優先。',
    '四、資料與分析：rich contextual data、多元資料來源；資料蒐集與分析迭代，常由資料歸納概念並持續比較／檢驗。',
    '五、參與者意義、整體脈絡與信實度：保留多元聲音，使用反思、清楚分析歷程、三角檢證／厚描述等提升可信度。',
    '六、策略例—紮根理論：以兒保跨機構衝突為題，立意／理論取樣→訪談等資料→coding→constant comparison／memo→theoretical sampling→核心範疇→建立過程理論。'
  ],
  guideMust:['質性研究策略','自然情境','研究者是主要工具或key instrument','參與者意義','emergent或彈性設計','reflexivity或反思性','rich或脈絡資料','迭代或反覆分析','歸納','信實度','grounded theory或紮根理論','constant comparison或持續比較'],
  guideMustNot:['深訪焦點團體觀察三種方法作為主答案','把資料蒐集工具等同研究策略','只談Lincoln Guba而不回答共同特質','沒有研究策略例子']
});
```

### 來源核對

- 考選部 114 年第二次「社會工作研究方法」申論第2題。
- Creswell 等質性研究方法文獻整理的共同特質包括 natural setting、researcher as key instrument、multiple sources、inductive／deductive reasoning、participant meanings、emergent design、reflexivity及holistic/contextual interpretation。
- 質性研究方法教材同樣強調非標準化且可調整的研究歷程、厚實資料、對脈絡／參與者觀點的保存，以及資料蒐集與分析間的反覆互動。

---

## 3. 人類行為與社會環境-114-2-申論2

### 題意 QA

官方題目並不是一般「多元家庭有哪些」，而是：同志伴侶準備成為父母時應評估什麼、可能經歷哪些生理心理社會挑戰，以及社工能如何協助。

### Anti-bias QA

研究整體並不支持「父母為同志」本身導致兒童較差發展。較重要的家庭與兒童福祉因素包括家庭穩定、親職品質、社經條件、社會支持，以及污名／歧視與法律環境。故專業評估不能把性傾向列成風險因子，而應以所有準父母均需具備的親職能力為核心，再評估少數壓力與制度脈絡。

### Verified payload

```js
verified('人類行為與社會環境-114-2-申論2',{
  kao:'評估原則要先表態：同志身分本身不是不適任親職或兒童發展危險因子。社工應採與其他準父母相同的child-centred親職評估，再加上同志家庭可能面對的minority stress、法律程序、家庭／社區支持與歧視環境。親職途徑不同，生理與法律議題也不同，不可預設每對同志伴侶都需要人工生殖或採取同一路徑。',
  dati:'評估面向包括：①成為父母的動機、期待與是否以兒童最佳利益為中心；②伴侶關係穩定度、溝通、衝突處理、共同親職／角色分工；③親職知能、兒童發展理解、紀律與照顧能力；④雙方身心健康、壓力因應與必要醫療需求；⑤經濟、居住、工作—照顧安排與托育資源；⑥原生家庭、朋友、同志社群及其他支持網絡；⑦實際親職途徑的法律身分、監護／收養／親權安排與可使用服務；⑧面對出櫃、污名、學校／醫療／社區歧視時的因應與兒童支持。生理面：若親職途徑涉及懷孕／生殖醫療，可能有生育能力、孕產健康、醫療決策等議題；若不涉及則不應硬套。心理面：角色轉換、成為父母的不確定、伴侶分工、焦慮與minority stress、內化污名或家庭拒絕。社會面：法律／行政程序、社會偏見、親族支持差異、學校／醫療環境歧視、可見的同質家庭榜樣與支持網絡不足。社工可提供肯認性且不批判的評估、親職與伴侶準備、coparenting／溝通、法律與收養／親權資源轉介、醫療／托育／福利資訊、支持團體與家庭會談，並在學校、醫療與社區進行反歧視倡議。',
  biaoti:[
    '一、評估原則：性傾向本身不是親職風險；以兒童最佳利益、親職能力、家庭功能及環境支持為核心。',
    '二、一般親職準備：動機與期待、伴侶穩定與溝通、共同親職分工、親職知能、身心健康、經濟住宅、工作照顧安排。',
    '三、支持與制度脈絡：原生家庭／朋友／社群支持、親職途徑的法律與行政安排、可用福利與照顧資源、社區／學校／醫療的接納程度。',
    '四、生理挑戰：依實際親職途徑評估生育／孕產／醫療需求，不預設所有同志伴侶皆需生殖醫療。',
    '五、心理挑戰：角色轉換、親職焦慮、伴侶角色協商、minority stress、內化污名、家庭拒絕與被歧視經驗。',
    '六、社會挑戰與社工協助：法律程序、偏見／歧視與支持網絡；提供affirming practice、親職教育／伴侶工作、法律資源、支持團體、服務連結及反歧視倡議。'
  ],
  guideMust:['同志伴侶','親職評估','兒童最佳利益','性傾向本身不是風險','伴侶溝通或共同親職','親職知能','經濟或住宅','支持網絡','minority stress或少數壓力','生理','心理','社會','法律或親權','affirming或肯認','反歧視'],
  guideMustNot:['把同志身分列為兒童發展風險','預設同志父母會造成兒童較差發展','預設所有同志伴侶都需人工生殖','只寫多元家庭去污名而無親職評估']
});
```

### 來源核對

- 考選部 114 年第二次「人類行為與社會環境」申論第2題。
- 同志親職 systematic reviews／meta-analyses：大多數兒童與家庭結果與異性戀父母家庭相近；父母性傾向本身不是重要的兒童發展決定因子。社會污名、歧視、支持不足、家庭穩定與法律環境反而是重要脈絡。
- 2023年我國司法院釋字第748號施行法修法後，同性配偶的共同收養範圍已擴及無血緣第三人子女；實際親職途徑仍須依當時法律與個案條件確認，不宜以單一路徑概括。

---

## 4. 社會工作-114-2-申論1

### 題意 QA

官方題目明確點名「生活模型」，要求分別回答個人與環境介入目標，再舉例說明評量重點。現行 Bronfenbrenner 多層系統模板雖同屬生態脈絡，但未回答 Germain & Gitterman Life Model 的特定概念與雙重介入目標。

### Verified payload

```js
verified('社會工作-114-2-申論1',{
  kao:'生活模型（Germain & Gitterman）把問題放在person–environment transactions與fit來看，不以個人病理為唯一原因。介入有雙重目標：一方面增強個人的coping、competence、self-direction與適應功能；另一方面使環境更能回應人的needs、goals與capacities，降低環境壓力／障礙並增加資源與機會，最終改善person-environment fit。',
  dati:'個人介入目標：釋放成長與健康潛能、增強自我效能／自我導向、因應能力、問題解決、關係能力與適應性社會功能。環境介入目標：降低不合理environmental pressures，改善組織／社區回應、動員正式與非正式資源、移除歧視／制度障礙、增加niche／habitat中的支持，使環境較能滿足人的需求與能力。評量不是一次性診斷，而是持續、合作、互動式 assessment；重點可依生活模型三大「problems in living」整理：①困難生命轉銜與創傷事件；②環境壓力／資源不足或障礙；③失功能的人際互動歷程。並評估coping、strengths、competence、自尊、社會支持、文化／生命歷程及個人與環境間的reciprocal transactions。例：中年失業者——個人面評估失落、自尊、技能、因應與家庭關係；環境面評估就業市場、年齡歧視、職訓、失業給付、交通與家庭經濟；介入既支持情緒／能力，也連結職訓、福利並倡議排除就業障礙。',
  biaoti:[
    '一、生活模型核心：Germain & Gitterman；人在環境的互惠交易（reciprocal transactions）、person-environment fit、優勢與生命歷程。',
    '二、個人介入目標：增強growth、coping、competence、self-direction／self-esteem及adaptive social functioning，不只處理病理。',
    '三、環境介入目標：使環境更回應needs/goals/capacities，降低壓力與制度障礙、動員資源／機會、改善組織與社區條件。',
    '四、評量一—生命轉銜／創傷：重大轉職、疾病、失落、遷移、家庭角色變化等life stressors及其意義。',
    '五、評量二—環境壓力與資源：住房、工作、福利、社區、歧視、服務可近性、habitat／niche與正式非正式支持。',
    '六、評量三—人際歷程與因應：家庭／重要關係互動、coping、strengths、competence、自尊及人環配適；評量持續且與案主合作。',
    '七、案例：中年失業同時處理心理／技能與家庭適應，也改變資源取得、職訓、福利及就業環境障礙。'
  ],
  guideMust:['Germain','Gitterman','Life Model或生活模型','person-environment fit或人環配適','reciprocal或互惠','個人介入目標','環境介入目標','coping','competence','life transition或生命轉銜','environmental pressure或環境壓力','interpersonal或人際歷程','strengths或優勢','持續或合作評量'],
  guideMustNot:['只寫Bronfenbrenner微視中介外部鉅視','只有個人改變沒有環境改變','把生活模型寫成個人病理診斷']
});
```

### 來源核對

- 考選部 114 年第二次「社會工作」申論第1題。
- Germain & Gitterman Life Model 原典及 Columbia University Press／Oxford Encyclopedia 資料：核心包括 reciprocal person-environment exchanges、person-environment fit、life stressors、coping、resilience、habitat／niche及環境回應性。
- Life Model 的介入同時著眼於「人」與「環境」：協助個人處理生活壓力並增強能力，也改變組織／社區／政策與資源，使環境更能回應人的需求與目標。
- 評量重點常圍繞 difficult life transitions／traumatic events、environmental pressures 與 dysfunctional interpersonal processes，並以優勢及持續互動評量取代固定病理診斷。

---

## 5. 社會政策與社會立法-114-2-申論1

### 題意 QA

官方題目明確要求從經濟、政治與社會三面說明 New Right 對福利國家的批判，再說明其如何影響福利國家發展。現行 guide 若只談福利意識形態光譜、殘補／制度或 Esping-Andersen，會漏掉指定架構。

### Verified payload

```js
verified('社會政策與社會立法-114-2-申論1',{
  kao:'作答固定拆成「經濟—政治—社會／道德—政策影響」四段。New Right並非完全單一學派，常含強調自由市場的neoliberal取向與重視責任／家庭／秩序的neoconservative取向；共同方向大致是質疑過度擴張的福利國家，主張有限政府、市場機制、個人責任與較具選擇性／條件性的福利。',
  dati:'經濟面：高稅負與公共支出被批評可能擠壓私人投資、削弱工作／儲蓄／投資誘因，政府獨占服務缺乏價格與競爭訊號而效率較差；主張支出約束、減稅、競爭及私人／準市場供給。政治面：public choice觀點質疑官僚與利益團體可能追求預算、權力與組織利益，福利官僚體系會擴張、造成government overload並限制個人選擇；主張縮小國家直接供給、分權、contracting out、consumer choice與較明確課責。社會／道德面：長期無條件給付被批評可能形成依賴、削弱自立／工作倫理與家庭／社群責任；主張個人責任、選擇性福利、條件化給付、workfare／activation及強化家庭／志願部門。對福利國家發展的影響不宜寫成「福利國家消失」，較準確是retrenchment與restructuring：支出控制、targeting／means-testing、私有化／外包／購買服務、quasi-market、福利多元化、就業啟動與條件化、分權與使用者選擇，使福利國家由直接供給者更多轉向規範／購買／促進者。',
  biaoti:[
    '一、經濟批判：高稅與公共支出、效率／競爭不足、工作／儲蓄／投資誘因受抑；偏好市場、競爭、支出限制與私人供給。',
    '二、政治批判：官僚／利益團體自利、國家與行政機器擴張、政府超載、個人選擇受限；偏好有限政府、分權、課責及consumer choice。',
    '三、社會／道德批判：福利依賴、個人責任／自立與工作倫理弱化、家庭／社群互助被國家取代；主張條件化、選擇性福利與責任。',
    '四、政策影響一—福利市場化：privatization、contracting out、quasi-market、購買服務與福利多元提供。',
    '五、政策影響二—福利選擇性／條件化：targeting、means-testing、workfare／activation、強調就業與自立。',
    '六、政策影響三—福利國家重整：支出控制、分權、使用者選擇；國家並未消失，而是由直接提供者部分轉向資助、規範、契約與監督角色。'
  ],
  guideMust:['New Right或新右派','經濟面','政治面','社會面或道德面','稅或公共支出','效率或市場','官僚或public choice','福利依賴','個人責任','privatization或民營化','contracting out或外包','means test或選擇性','workfare或activation','福利國家重整'],
  guideMustNot:['Esping-Andersen三類作為主答案','只談殘補vs制度','福利國家完全被取消','把所有福利國家變遷都歸因於New Right']
});
```

### 來源核對

- 考選部 114 年第二次「社會政策與社會立法」申論第1題。
- Oxford Handbook of the Welfare State／Encyclopedia of Social Work 相關文獻：New Right／neoliberal welfare critique主張較小國家、自由市場、個人責任，並推動福利市場化、私有化、外包與條件化。
- New Right 經濟批判集中在支出、稅負、效率及誘因；政治批判常由 public choice 指向官僚擴張、利益團體及政府過載；社會／道德批判則聚焦依賴、自立、工作倫理與家庭／社群責任。
- 政策效果宜描述為 welfare state retrenchment / restructuring，而不是「福利國家被廢除」；各國實際改革程度亦受既有制度、政黨與社會條件影響。

---

# Batch 9 後續施工規格

1. 正式施工窗口才把本批5題加入逐題 override。
2. 建立 Batch 9 smoke：每題 `guideMust` 全命中、`guideMustNot` 全不命中。
3. `社會工作研究方法-114-2-申論1`：加入 classification smoke；若把「量化＝演繹、質性＝歸納」直接畫等號，視為 fail。
4. `社會工作研究方法-114-2-申論2`：至少命中一個真正 qualitative strategy（如 grounded theory），只列深訪／焦點／觀察視為 fail。
5. `人類行為與社會環境-114-2-申論2`：加入 anti-bias smoke；若將同性性傾向本身列為親職／兒童發展風險，直接 fail。
6. `社會工作-114-2-申論1`：必須出現 Germain/Gitterman、個人與環境雙重介入目標及 Life Model 的三類生活問題；只有 Bronfenbrenner 分層視為 fail。
7. `社會政策與社會立法-114-2-申論1`：必須明確分經濟、政治、社會三面；只背福利意識形態／Esping-Andersen直接 fail。
8. Batch 1–9 essay smoke 應一次跑完，並搭配 duplicate-key source lint。
9. Batch 10 接續 114-2 剩餘 5 題：自立生活輔導系統／角色、個案工作結案、社區培力老人憂鬱方案、兒少性剝削法定樣態與服務、Skinner vs Bandura兒童中期比較。
10. Cloudflare preview 驗收通過前，不進 Netlify 正式學生端。
