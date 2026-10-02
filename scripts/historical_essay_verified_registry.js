#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const VERIFIED_FILE_RE = /^essay_guide_audit_batch(\d+)_verified_(\d{8})\.md$/;
const LEGACY_ID_RE = /^(?:社會工作|社會工作直接服務|社會政策與社會立法|人類行為與社會環境|社會工作研究方法)-\d{3}-[12]-申論[12]$/;
const MIN_BASELINE_VERIFIED = 68;
const BASELINE_REQUIRED_IDS = new Set([
  '人類行為與社會環境-104-1-申論2',
  '社會工作-104-1-申論1',
  '社會工作-104-1-申論2',
  '社會工作-113-1-申論2',
  '社會工作-115-1-申論2'
]);

function fail(message) {
  throw new Error(`historical essay verified registry: ${message}`);
}

function cleanText(value, label) {
  if (typeof value !== 'string' || !value.trim()) fail(`${label} must be a non-empty string`);
  return value.trim();
}

function uniqueStrings(value, label, min = 1) {
  if (!Array.isArray(value) || value.length < min) fail(`${label} must contain at least ${min} item(s)`);
  const out = value.map((item, index) => cleanText(item, `${label}[${index}]`));
  if (new Set(out).size !== out.length) fail(`${label} contains duplicate values`);
  return out;
}

function dateFromStamp(stamp) {
  if (!/^\d{8}$/.test(stamp)) fail(`invalid date stamp: ${stamp}`);
  return `${stamp.slice(0, 4)}-${stamp.slice(4, 6)}-${stamp.slice(6, 8)}`;
}

function jsBlocks(markdown) {
  const blocks = [];
  const re = /```(?:js|javascript)\s*\n([\s\S]*?)```/gi;
  let match;
  while ((match = re.exec(markdown))) {
    if (/\bverified\s*\(/.test(match[1])) blocks.push(match[1]);
  }
  return blocks;
}

function loadHistoricalVerifiedRegistry(rootDir = path.resolve(__dirname, '..')) {
  const auditDir = path.join(rootDir, 'audit');
  const files = fs.readdirSync(auditDir)
    .map(name => ({ name, match: name.match(VERIFIED_FILE_RE) }))
    .filter(row => row.match)
    .sort((a, b) => Number(a.match[1]) - Number(b.match[1]));

  if (!files.length) fail('no verified audit files found');

  const records = [];
  const seen = new Map();
  const perFile = [];

  for (const row of files) {
    const fileName = row.name;
    const batch = Number(row.match[1]);
    const reviewedAt = dateFromStamp(row.match[2]);
    const filePath = path.join(auditDir, fileName);
    const markdown = fs.readFileSync(filePath, 'utf8');
    const blocks = jsBlocks(markdown);
    let count = 0;

    if (!blocks.length) fail(`${fileName}: no verified(...) JavaScript block found`);

    const verified = (rawId, rawPayload) => {
      const id = cleanText(rawId, `${fileName}.id`);
      if (!LEGACY_ID_RE.test(id)) fail(`${fileName}: unsupported legacy essay id ${id}`);
      if (!rawPayload || typeof rawPayload !== 'object' || Array.isArray(rawPayload)) {
        fail(`${fileName}: ${id} payload must be an object`);
      }
      if (seen.has(id)) {
        fail(`duplicate verified ID ${id}: ${seen.get(id)} and ${fileName}`);
      }

      const kao = cleanText(rawPayload.kao, `${fileName}:${id}.kao`);
      const dati = cleanText(rawPayload.dati, `${fileName}:${id}.dati`);
      const biaoti = uniqueStrings(rawPayload.biaoti, `${fileName}:${id}.biaoti`, 2);
      const guideMust = uniqueStrings(rawPayload.guideMust, `${fileName}:${id}.guideMust`, 1);
      const guideMustNot = uniqueStrings(rawPayload.guideMustNot, `${fileName}:${id}.guideMustNot`, 1);
      const kw = Array.isArray(rawPayload.kw) && rawPayload.kw.length
        ? uniqueStrings(rawPayload.kw, `${fileName}:${id}.kw`, 1)
        : guideMust.slice();

      seen.set(id, fileName);
      records.push({
        id,
        kao,
        dati,
        biaoti,
        kw,
        guideMust,
        guideMustNot,
        review_status: 'verified',
        reviewed_at: reviewedAt,
        review_batch: `historical-batch${batch}`,
        audit_file: `audit/${fileName}`,
        is_official: false,
        guide_source: `SWSI 自製複習參考架構；依 Batch ${batch} verified audit 定稿，非考選部官方標準答案`
      });
      count += 1;
    };

    for (let i = 0; i < blocks.length; i += 1) {
      const sandbox = Object.create(null);
      sandbox.verified = verified;
      vm.createContext(sandbox);
      try {
        vm.runInContext(blocks[i], sandbox, {
          filename: `${fileName}#verified-${i + 1}`,
          timeout: 1000
        });
      } catch (error) {
        fail(`${fileName}: cannot evaluate verified block ${i + 1}: ${error.message}`);
      }
    }

    if (!count) fail(`${fileName}: verified blocks produced zero records`);
    perFile.push({ file: fileName, batch, count });
  }

  records.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));

  if (records.length < MIN_BASELINE_VERIFIED) {
    fail(`verified record count regressed: ${records.length} < baseline ${MIN_BASELINE_VERIFIED}`);
  }
  for (const id of BASELINE_REQUIRED_IDS) {
    if (!seen.has(id)) fail(`baseline verified ID missing: ${id}`);
  }

  return {
    schema_version: 1,
    purpose: 'Machine-readable projection of repo-owned verified historical essay audit payloads. Official MOEX question text remains immutable.',
    files: perFile,
    records
  };
}

if (require.main === module) {
  const registry = loadHistoricalVerifiedRegistry();
  const summary = {
    ok: true,
    files: registry.files.length,
    records: registry.records.length,
    per_file: registry.files,
    first_id: registry.records[0]?.id || null,
    last_id: registry.records.at(-1)?.id || null
  };
  if (process.argv.includes('--full')) console.log(JSON.stringify(registry, null, 2));
  else console.log(JSON.stringify(summary, null, 2));
}

module.exports = {
  loadHistoricalVerifiedRegistry,
  LEGACY_ID_RE,
  MIN_BASELINE_VERIFIED
};
