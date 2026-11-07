#!/usr/bin/env node
'use strict';

// Regression for the evergreen current-affairs library: one entry on the
// canonical page; old case records stay available in a separate view.
// No browser, credentials, production requests or external libraries.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function owner(html) {
  const begin = '/* ===== 時事庫注入 START';
  const end = '/* ===== 時事庫注入 END';
  const a = html.indexOf(begin), b = html.indexOf(end, a);
  assert(a >= 0 && b > a, 'evergreen news owner must exist');
  assert.equal(html.indexOf(begin, a + 1), -1, 'do not install duplicate owners');
  const close = html.indexOf('*/', b);
  assert(close > b, 'evergreen closing comment missing');
  return html.slice(a, close + 2);
}

const html = fs.readFileSync('index.html', 'utf8');
const cdn = fs.readFileSync('cdn/index.html', 'utf8');
const text = owner(html);
assert.equal(text, owner(cdn), 'canonical and Cloudflare evergreen views must match');
assert(text.includes('NL.history()'), 'single entry action missing');
assert(text.includes('renderHistory()'), 'history screen missing');
assert(text.includes('historyFilter:function'), 'history subject filter missing');

const primary = { style: {} };
const mounted = [];
const head = [];
const overlay = {
  className: '', innerHTML: '', scrollTop: 0, children: [], parentNode: null,
  querySelector(sel) {
    if (sel === '.nl-wrap' && this.innerHTML.includes('class="nl-wrap"')) return primary;
    return null;
  },
  appendChild(node) { node.parentNode = this; this.children.push(node); },
  removeChild(node) {
    this.children = this.children.filter(item => item !== node);
    node.parentNode = null;
  },
};
const document = {
  documentElement: { getAttribute() { return null; } },
  head: { appendChild(n) { head.push(n); } },
  body: {
    appendChild(n) { n.parentNode = this; mounted.push(n); },
    removeChild(n) { const idx = mounted.indexOf(n); if (idx >= 0) mounted.splice(idx, 1); n.parentNode = null; },
  },
  createElement(tag) {
    if (tag === 'style') return { textContent: '', id: '' };
    if (tag === 'div') return overlay;
    if (tag === 'section') return {
      innerHTML: '', parentNode: null, className: '',
      querySelector(sel) { return sel === '.nl-back' ? { focus() {} } : null; },
    };
    throw Error('unexpected tag: ' + tag);
  },
};
const window = {};
new vm.Script(text, { filename: 'evergreen-news-owner.js' }).runInNewContext({ document, window });
assert.equal(typeof window.NL.open, 'function');
window.NL.open();
assert.equal(mounted.length, 1);
assert(overlay.innerHTML.includes('歷年重大事件與經典案例'));
assert(overlay.innerHTML.includes('onclick="NL.history()"'), 'entry should open history');
assert(!overlay.innerHTML.includes('剴剴案：'), 'legacy full cards must not appear on canonical page');
assert(!overlay.innerHTML.includes('花蓮馬太鞍溪'), 'second legacy card leaked onto canonical page');

overlay.scrollTop = 330;
window.NL.history();
assert.equal(primary.style.display, 'none');
assert.equal(overlay.children.length, 1, 'exactly one history pane');
let history = overlay.children[0].innerHTML;
assert(history.includes('剴剴案：出養兒童'), 'historical case data must be retained');
assert(history.includes('花蓮馬太鞍溪'), 'historical case list must remain reachable');
assert(history.includes('展開完整考點、法規與申論'));
assert(history.includes('‹ 返回時事庫'), 'back control must be visible');
window.NL.historyFilter('人類行為');
history = overlay.children[0].innerHTML;
assert(history.includes('剴剴案：'), 'filter should retain matching case');
assert(!history.includes('性平三法修法：'), 'filter should hide non-matching case');
window.NL.back();
assert.equal(overlay.children.length, 0);
assert.equal(primary.style.display, '');
assert.equal(overlay.scrollTop, 330, 'back must restore position');
assert(!overlay.innerHTML.includes('剴剴案：'), 'back must not leak entire library');

window.NL.filter('直接服務');
assert(overlay.innerHTML.includes('NL.history()'), 'main filters must preserve history entry');
window.NL.close();
assert.equal(mounted.length, 0, 'closing history should remove overlay');

window.NL.open();
window.NL.history();
window.NL.close();
assert.equal(mounted.length, 0, 'close inside history must clean up');
console.log('CURRENT AFFAIRS HISTORY NAVIGATION SMOKE OK: single entry, full case preservation, filters, back, close, root/CDN parity');
