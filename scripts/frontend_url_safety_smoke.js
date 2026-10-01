#!/usr/bin/env node
'use strict';

// Regression guard for dynamic links rendered from law/current-affairs data.
// HTML escaping alone is not enough for href: javascript: is still clickable.
const assert = require('node:assert/strict');
const fs = require('node:fs');

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

// Current-affairs owner already has safeHref(). The main source link must use it,
// just like evidence links do. Lock both the generator and installed runtime.
for (const [name, text] of [['installer', installer], ['index', index]]) {
  assert(text.includes('function safeHref(v)'), `${name}: safeHref helper missing`);
  assert(text.includes("return /^https:\\/\\//i.test(s)?E(s):'#';"), `${name}: HTTPS scheme allowlist missing`);
  assert(text.includes('href="\'+safeHref(ev.source_url)+\'"'), `${name}: event source link bypasses safeHref`);
  assert(!text.includes('href="\'+E(ev.source_url)+\'"'), `${name}: raw/escape-only event source href still present`);
}

console.log('FRONTEND URL SAFETY SMOKE OK: law/current-affairs dynamic hrefs require HTTPS');
