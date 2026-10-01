#!/usr/bin/env node
'use strict';

// Regression guard for dynamic links rendered from law/current-affairs data.
// HTML escaping alone is not enough for href: javascript: is still clickable.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const law = fs.readFileSync('monthly_patch_parts/86.law-trust-ui.part', 'utf8');
const installer = fs.readFileSync('scripts/install_current_affairs_ui.py', 'utf8');
const index = fs.readFileSync('index.html', 'utf8');

// Law cards: canonical part must scheme-check both primary and secondary links.
assert(law.includes('function safeHttpsHref(v)'), 'law source scheme guard missing');
assert(law.includes("if(!/^https:\\/\\//i.test(s))return '';"), 'law source must reject non-HTTPS schemes');
assert(law.includes("return u.protocol==='https:'?H(u.href):'';"), 'law source URL parser/protocol guard missing');
assert(law.includes('var sourceUrl=safeHttpsHref(x.source_url);'));
assert(law.includes('var secondaryUrl=safeHttpsHref(x.secondary_url);'));
assert(!law.includes('href="\'+H(x.source_url)+\'"'), 'law primary source regressed to escape-only href');
assert(!law.includes('href="\'+H(x.secondary_url)+\'"'), 'law secondary source regressed to escape-only href');

// Execute the real law layer with malicious schemes. The unsafe links must be
// omitted entirely, while a valid HTTPS link remains usable.
let insertedLawHtml = '';
const lawOpenNode = {
  querySelector() { return null; },
  insertAdjacentHTML(_where, html) { insertedLawHtml += html; },
};
const lawContext = {
  console,
  URL,
  window: {},
  LAWS: [{
    n: '測試法',
    source_url: 'javascript:alert(1)',
    secondary_url: 'data:text/html,<script>alert(2)</script>',
    source_label: '惡意來源',
    secondary_label: '惡意補充',
    verify_status: 'checked',
  }],
  lawOpen: 0,
  renderLaws() {},
  document: {
    querySelector(selector) {
      if (selector === '#app .ecard.open .ebodywrap') return lawOpenNode;
      return null;
    },
  },
};
vm.createContext(lawContext);
new vm.Script(law, { filename: '86.law-trust-ui.part' }).runInContext(lawContext);
lawContext.renderLaws();
assert(!insertedLawHtml.includes('javascript:'), 'law runtime leaked javascript: href');
assert(!insertedLawHtml.includes('data:text'), 'law runtime leaked data: href');
assert(!insertedLawHtml.includes('<a '), 'unsafe law sources should not render clickable anchors');

lawContext.LAWS[0].source_url = 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0000001';
insertedLawHtml = '';
lawContext.renderLaws();
assert(insertedLawHtml.includes('href="https://law.moj.gov.tw/'), 'valid HTTPS law source disappeared');

// Current-affairs owner already has safeHref(). The main source link must use it,
// just like evidence links do. Lock both the generator and installed runtime.
for (const [name, text] of [['installer', installer], ['index', index]]) {
  assert(text.includes('function safeHref(v)'), `${name}: safeHref helper missing`);
  assert(text.includes("return /^https:\\/\\//i.test(s)?E(s):'#';"), `${name}: HTTPS scheme allowlist missing`);
  assert(text.includes('href="\'+safeHref(ev.source_url)+\'"'), `${name}: event source link bypasses safeHref`);
  assert(!text.includes('href="\'+E(ev.source_url)+\'"'), `${name}: raw/escape-only event source href still present`);
}

// Execute the installed helper body too. Static ownership checks above ensure the
// event source link actually calls this helper; these assertions lock behavior.
const helperMatch = index.match(/function safeHref\(v\)\{([\s\S]*?)\n\s*\}/);
assert(helperMatch, 'installed current-affairs safeHref body not found');
const helperContext = {
  E(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  },
};
vm.createContext(helperContext);
new vm.Script(`function safeHref(v){${helperMatch[1]}\n}\nthis.safeHref=safeHref;`).runInContext(helperContext);
assert.equal(helperContext.safeHref('javascript:alert(1)'), '#');
assert.equal(helperContext.safeHref('data:text/html,boom'), '#');
assert.equal(helperContext.safeHref('http://example.test/insecure'), '#');
assert.equal(helperContext.safeHref('https://example.test/a?x=1&y=2'), 'https://example.test/a?x=1&amp;y=2');

console.log('FRONTEND URL SAFETY SMOKE OK: malicious schemes blocked at runtime; HTTPS sources preserved');
