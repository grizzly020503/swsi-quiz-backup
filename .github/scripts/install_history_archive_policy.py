from pathlib import Path

p=Path('index.html')
s=p.read_text(encoding='utf-8')

if 'HISTORY ARCHIVE POLICY V1' in s:
    print('History archive policy already installed.')
    raise SystemExit(0)

old = """function focusedQuizFilter(q){
  if(subjFilter!=='全部科目' && q.subject!==subjFilter) return false;
  const y=parseInt(q.year,10)||0, mx=maxExamYear();
  if(homeQuizScope==='recent3') return y>=mx-2;
  if(homeQuizScope==='recent5') return y>=mx-4;
  if(homeQuizScope==='specific'){
    if(String(q.year)!==String(homeQuizYear)) return false;
    if(homeQuizRound!=='all' && canonicalRound(q.round)!==homeQuizRound) return false;
  }
  return true;
}"""
new = """/* ===== HISTORY ARCHIVE POLICY V1 ===== */
function focusedQuizFilter(q){
  if(subjFilter!=='全部科目' && q.subject!==subjFilter) return false;
  const y=parseInt(q.year,10)||0, mx=maxExamYear();
  /* 智慧推薦只使用最近 10 個考試年度；更舊題目保留為歷史題庫。 */
  if(homeQuizScope==='smart') return !y || y>=mx-9;
  if(homeQuizScope==='recent3') return y>=mx-2;
  if(homeQuizScope==='recent5') return y>=mx-4;
  if(homeQuizScope==='specific'){
    if(String(q.year)!==String(homeQuizYear)) return false;
    if(homeQuizRound!=='all' && canonicalRound(q.round)!==homeQuizRound) return false;
  }
  return true;
}"""
if old not in s:
    raise SystemExit('focusedQuizFilter target not found')
s=s.replace(old,new,1)

s=s.replace(
    "const scopeHint=homeQuizScope==='smart'?'近年與高頻考點優先；舊題保留但降低出現率。':",
    "const scopeHint=homeQuizScope==='smart'?'預設使用最近 10 年；近 3 年與高頻考點優先，更舊題保留在歷史題庫。':",
    1
)
s=s.replace(
    "歷史題不刪除；智慧推薦會優先較新的題目，需要時仍可指定任何年份。",
    "10 年以前保留為歷史題庫；智慧推薦預設不抽，需要時仍可指定年份或選全部題庫。",
    1
)

old_meta = "${yearTier(item)==='高'?'<span class=\"tag year\" style=\"background:var(--correct-bg);color:var(--pine)\">近年</span>':''}${lawUpdated(item)?'<span class=\"tag year\" style=\"background:var(--wrong-bg);color:var(--wrong)\">⚠ 法規已更新</span>':''}"
new_meta = "${yearTier(item)==='高'?'<span class=\"tag year\" style=\"background:var(--correct-bg);color:var(--pine)\">近年</span>':''}${(maxExamYear()-(parseInt(item.year)||0)>9)?'<span class=\"tag year\" style=\"background:#ECE6D6;color:var(--ink-soft)\">歷史參考</span>':''}${lawUpdated(item)?'<span class=\"tag year\" style=\"background:var(--wrong-bg);color:var(--wrong)\">⚠ 法規已更新</span>':''}"
if old_meta not in s:
    raise SystemExit('quiz meta target not found')
s=s.replace(old_meta,new_meta,1)

p.write_text(s,encoding='utf-8')
print('Installed ten-year active/archive policy.')
