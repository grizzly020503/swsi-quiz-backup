const fs = require('fs');
const vm = require('vm');

const file = process.argv[2] || 'index.html';
const html = fs.readFileSync(file, 'utf8');

function extractArray(name) {
  const marker = `window.${name}`;
  const pos = html.indexOf(marker);
  if (pos < 0) throw new Error(`missing ${marker}`);
  const eq = html.indexOf('=', pos + marker.length);
  if (eq < 0) throw new Error(`missing assignment for ${marker}`);
  const start = html.indexOf('[', eq + 1);
  if (start < 0) throw new Error(`missing array for ${marker}`);

  let depth = 0;
  let quote = null;
  let esc = false;
  for (let i = start; i < html.length; i++) {
    const ch = html[i];
    if (quote) {
      if (esc) { esc = false; continue; }
      if (ch === '\\') { esc = true; continue; }
      if (ch === quote) quote = null;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === '`') { quote = ch; continue; }
    if (ch === '[') depth++;
    else if (ch === ']') {
      depth--;
      if (depth === 0) return html.slice(start, i + 1);
    }
  }
  throw new Error(`unterminated array for ${marker}`);
}

function evaluateArray(name) {
  const raw = extractArray(name);
  const value = vm.runInNewContext(`(${raw})`, Object.create(null), { timeout: 1500 });
  if (!Array.isArray(value)) throw new Error(`${name} is not an array`);
  return value;
}

const theories = evaluateArray('THEORIES');
const laws = evaluateArray('LAWS');

function cleanTheory(t) {
  return {
    name: t.n || '',
    domain: t.d || '',
    scholar: t.s || '',
    core: t.c || '',
    essay_use: t.a || '',
    keywords: Array.isArray(t.k) ? t.k : []
  };
}

function cleanLaw(l) {
  return {
    name: l.n || '',
    domain: l.d || '',
    scope: l.p || '',
    core: l.c || '',
    essay_use: l.a || '',
    update_note: l.u || '',
    keywords: Array.isArray(l.k) ? l.k : []
  };
}

const catalog = {
  theories: theories.map(cleanTheory),
  laws: laws.map(cleanLaw)
};

function duplicateNames(rows) {
  const seen = new Set();
  const dup = new Set();
  for (const x of rows) {
    const n = String(x.name || '').trim();
    if (!n) continue;
    if (seen.has(n)) dup.add(n);
    seen.add(n);
  }
  return [...dup];
}

const emptyTheoryNames = catalog.theories.filter(x => !x.name).length;
const emptyLawNames = catalog.laws.filter(x => !x.name).length;
if (emptyTheoryNames || emptyLawNames) throw new Error(`empty names: theories=${emptyTheoryNames}, laws=${emptyLawNames}`);

const theoryDup = duplicateNames(catalog.theories);
const lawDup = duplicateNames(catalog.laws);
if (theoryDup.length || lawDup.length) {
  throw new Error(`duplicate names: theories=${theoryDup.join(',')}; laws=${lawDup.join(',')}`);
}

console.log(`KNOWLEDGE CATALOG OK: theories=${catalog.theories.length} laws=${catalog.laws.length}`);
console.log('SWSI_KNOWLEDGE_CATALOG_JSON=' + JSON.stringify(catalog));
