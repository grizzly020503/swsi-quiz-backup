#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const assets={'DS-113-2-13.png':'b2f03e6714f4cd9b55950ec947e47a0d8608485109ebc8c5e955f589dafe0d31','R-114-2-12.png':'ac947126d861db9c99a470ea58c262d52d1c6ffc251bc847bce59b0d302753e2'};
for(const [file,sha] of Object.entries(assets))for(const sub of ['official-figures','cdn/official-figures']){
 const raw=fs.readFileSync(path.join(root,sub,file));
 assert.equal(raw.subarray(0,8).toString('hex'),'89504e470d0a1a0a','PNG header');
 assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),sha,'visual original bytes: '+sub+'/'+file);
}
for(const file of ['index.html','cdn/index.html']){
 const html=fs.readFileSync(path.join(root,file),'utf8');
 for(const asset of Object.keys(assets))assert.ok(html.includes('official-figures/'+asset),file+' must render '+asset);
 for(const needle of ['function swsiOfficialFigureHTML(item)','function swsiOfficialFigureReady(item)','if(!swsiOfficialFigureReady(item))return','${swsiOfficialFigureHTML(item)}','function swsiOfficialVisibleStem(item)','class="swsi-official-image"'])assert.ok(html.includes(needle),file+' missing '+needle);
}
for(const file of ['sw.js','cdn/sw.js'])for(const asset of Object.keys(assets))assert.ok(fs.readFileSync(path.join(root,file),'utf8').includes('./official-figures/'+asset),file+' missing offline figure '+asset);
assert.ok(fs.readFileSync(path.join(root,'netlify.toml'),'utf8').includes('cp -R official-figures _site/'),'Netlify build missing official figures');
const audit=JSON.parse(fs.readFileSync(path.join(root,'audit/official_figure_assets.v1.json'),'utf8'));
assert.equal(audit.approved,false);assert.equal(audit.official_core_modified,false);assert.equal(audit.figures.length,2);
console.log('OFFICIAL FIGURES QA OK: two original MOEX images root/CDN parity, mobile display, offline/PWA, fails closed; not production approved');
