#!/usr/bin/env node
'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = process.cwd();
const newWorker = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
const port = Number(process.env.SWSI_SW_SMOKE_PORT || 4187);
let phase = 'old';
let mutableRequests = 0;

const oldWorker = `
const VERSION='v5';
const CACHE='swsi-shell-'+VERSION;
const SHELL=['/','/monthly_patch.js'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch',e=>{
  const u=new URL(e.request.url);
  if(u.origin!==self.location.origin||e.request.method!=='GET')return;
  if(u.pathname==='/monthly_patch.js'){
    e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(res=>{const copy=res.clone();caches.open(CACHE).then(c=>c.put(e.request,copy));return res;})));
  }
});
`;

const pageHtml = `<!doctype html><meta charset="utf-8"><title>SWSI SW Upgrade Smoke</title>
<script>
window.registerSWSI = async function(){
  const reg = await navigator.serviceWorker.register('/sw.js', {scope:'/'});
  await navigator.serviceWorker.ready;
  if(!navigator.serviceWorker.controller){
    await new Promise(resolve=>navigator.serviceWorker.addEventListener('controllerchange',resolve,{once:true}));
  }
  return reg;
};
</script>`;

function send(res, status, type, body){
  res.writeHead(status, {'content-type':type, 'cache-control':'no-store'});
  res.end(body);
}

const server = http.createServer((req,res)=>{
  const u = new URL(req.url, `http://127.0.0.1:${port}`);
  if(u.pathname === '/sw.js') return send(res,200,'application/javascript; charset=utf-8', phase === 'old' ? oldWorker : newWorker);
  if(u.pathname === '/monthly_patch.js'){
    mutableRequests++;
    return send(res,200,'application/javascript; charset=utf-8', `window.__assetVersion=${JSON.stringify(phase === 'old' ? 'old-v1' : 'new-v2')};`);
  }
  if(u.pathname === '/' || u.pathname === '/index.html') return send(res,200,'text/html; charset=utf-8',pageHtml);
  if(u.pathname.endsWith('.json')) return send(res,200,'application/json; charset=utf-8','{}');
  if(u.pathname.endsWith('.png')) return send(res,200,'image/png','x');
  return send(res,200,'text/plain; charset=utf-8','ok');
});

function listen(){return new Promise((resolve,reject)=>server.listen(port,'127.0.0.1',err=>err?reject(err):resolve()));}
function closeServer(){return new Promise(resolve=>server.close(()=>resolve()));}

(async()=>{
  await listen();
  const browser = await chromium.launch({headless:true});
  const context = await browser.newContext({serviceWorkers:'allow'});
  const page = await context.newPage();
  try{
    await page.goto(`http://127.0.0.1:${port}/`, {waitUntil:'domcontentloaded'});
    await page.evaluate(()=>window.registerSWSI());
    await page.waitForFunction(()=>navigator.serviceWorker.controller && navigator.serviceWorker.controller.scriptURL.endsWith('/sw.js'));

    const oldBody = await page.evaluate(()=>fetch('/monthly_patch.js').then(r=>r.text()));
    if(!oldBody.includes('old-v1')) throw new Error('v5 baseline did not serve/cache old mutable asset');
    const oldCaches = await page.evaluate(()=>caches.keys());
    if(!oldCaches.includes('swsi-shell-v5')) throw new Error('v5 baseline cache missing: '+JSON.stringify(oldCaches));

    phase = 'new';

    await page.evaluate(async()=>{
      const reg = await navigator.serviceWorker.getRegistration('/');
      if(!reg) throw new Error('registration missing');
      const previous = navigator.serviceWorker.controller;
      const changed = new Promise(resolve=>{
        const timer=setTimeout(resolve,10000);
        navigator.serviceWorker.addEventListener('controllerchange',()=>{clearTimeout(timer);resolve();},{once:true});
      });
      await reg.update();
      if(navigator.serviceWorker.controller === previous) await changed;
      await navigator.serviceWorker.ready;
    });

    await page.waitForFunction(async()=>{
      const keys=await caches.keys();
      return keys.includes('swsi-shell-v6') && !keys.includes('swsi-shell-v5');
    }, null, {timeout:15000});

    // v6 install itself pre-caches monthly_patch.js. Record the counter only
    // after activation so this assertion proves the runtime fetch is network-first.
    const requestsBeforeFinalFetch = mutableRequests;
    const body = await page.evaluate(()=>fetch('/monthly_patch.js').then(r=>r.text()));
    const cacheKeys = await page.evaluate(()=>caches.keys());
    if(!body.includes('new-v2')) throw new Error('v6 still served stale mutable asset: '+body);
    if(mutableRequests <= requestsBeforeFinalFetch) throw new Error('v6 mutable asset runtime fetch did not reach network; cache-first regression suspected');
    if(cacheKeys.includes('swsi-shell-v5') || !cacheKeys.includes('swsi-shell-v6')) throw new Error('cache upgrade invariant failed: '+JSON.stringify(cacheKeys));

    console.log('SERVICE WORKER UPGRADE SMOKE OK', JSON.stringify({oldBody,newBody:body,cacheKeys,requestsBeforeFinalFetch,mutableRequests}));
  } finally {
    await context.close();
    await browser.close();
    await closeServer();
  }
})().catch(async err=>{
  console.error(err && err.stack || err);
  try{await closeServer();}catch(_e){}
  process.exit(1);
});
