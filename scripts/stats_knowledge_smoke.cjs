// Run: node scripts/stats_knowledge_smoke.cjs
const assert=require('node:assert/strict');
const stats=require('../statistics_knowledge.js');
function topic(text,subject='社會工作研究方法'){return {subject,question:text};}
assert.equal(stats.select(topic('兩個類別變項的卡方獨立性檢定')).id,'chi');
assert.equal(stats.select(topic('比較同一批個案前後測，使用成對樣本 t 考驗')).id,'paired_t');
assert.equal(stats.select(topic('皮爾森積差相關')).id,'pearson');
assert.equal(stats.select(topic('信度與再測信度')).id,'reliability');
assert.equal(stats.select(topic('調節效果和交互作用')).id,'moderation');
assert.equal(stats.select(topic('完全沒有統計關鍵字')),null);
assert.equal(stats.select(topic('卡方檢定','社會工作直接服務')),null);
assert.match(stats.html(topic('卡方檢定')),/<details class="swsi-stat-learn">/);
assert.match(stats.html(topic('卡方檢定')),/非考選部官方解析/);
assert.equal(stats.html(topic('卡方檢定','社會工作直接服務')),'');
console.log('SWSI statistics knowledge smoke: passed');
