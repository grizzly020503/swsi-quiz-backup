const fs = require('fs');
const path = require('path');

const ROOT = process.cwd();
const AUDIT_DIR = path.join(ROOT, 'audit');
const files = fs.readdirSync(AUDIT_DIR)
  .filter(name => /^essay_guide_audit_batch\d+_verified_\d{8}\.md$/.test(name))
  .sort((a,b) => a.localeCompare(b, 'en', { numeric:true }));

const idRe = /verified\(\s*['"]([^'"]+)['"]\s*,\s*\{/g;
const byId = new Map();
const perFile = [];
const failures = [];

for(const name of files){
  const text = fs.readFileSync(path.join(AUDIT_DIR, name), 'utf8');
  const ids = [];
  let m;
  while((m = idRe.exec(text))){
    const id = m[1];
    ids.push(id);
    if(!byId.has(id)) byId.set(id, []);
    byId.get(id).push(name);
  }

  if(ids.length === 0){
    failures.push(`${name}: no verified(...) payload found`);
  }

  const payloadBlocks = text.split(/\n(?=##\s+\d+\.|\n#\s+)/);
  for(const id of ids){
    const pos = text.indexOf(`verified('${id}'`);
    const pos2 = pos >= 0 ? pos : text.indexOf(`verified("${id}"`);
    const tail = pos2 >= 0 ? text.slice(pos2, text.indexOf('\n```', pos2) >= 0 ? text.indexOf('\n```', pos2) : undefined) : '';
    if(!/guideMust\s*:/.test(tail)) failures.push(`${name}: ${id} missing guideMust`);
    if(!/guideMustNot\s*:/.test(tail)) failures.push(`${name}: ${id} missing guideMustNot`);
  }

  perFile.push({ file:name, count:ids.length, ids });
}

for(const [id, owners] of byId){
  if(owners.length > 1){
    failures.push(`duplicate verified ID across audit batches: ${id} -> ${owners.join(', ')}`);
  }
}

const result = {
  ok: failures.length === 0,
  files: files.length,
  unique_verified_ids: byId.size,
  per_file: perFile.map(x => ({ file:x.file, count:x.count })),
  failures
};

if(process.argv.includes('--json')){
  console.log(JSON.stringify(result, null, 2));
}else{
  console.log('SWSI ESSAY VERIFIED REGISTRY LINT');
  console.log(`verified audit files: ${result.files}`);
  console.log(`unique verified IDs: ${result.unique_verified_ids}`);
  for(const row of result.per_file) console.log(`  ${row.file}: ${row.count}`);
  for(const x of failures) console.error(`  ✗ ${x}`);
  console.log(`\nresult: ${result.ok ? 'PASS' : 'FAIL'} (${failures.length} issue${failures.length===1?'':'s'})`);
}

process.exit(result.ok ? 0 : 1);
